"""Transactional archives and safe state transitions when bank content changes."""
import copy
from types import SimpleNamespace

from sqlalchemy import select

from app import bank_personal
from app.models import BankVersion, BankStateArchive, BankState
from app.study_retention import digest, manifest, migrate


def save_version(db, subject, run_id, build_id, bank, source='publication'):
    if not bank or not build_id:
        return
    key = digest([subject, run_id, build_id, bank])
    if db.get(BankVersion, key) is None:
        db.add(BankVersion(id=key, subject=subject, run_id=run_id, build_id=build_id,
                           bank=copy.deepcopy(bank), source=source))
        db.flush()


def archive_state(db, user_id, subject, run_id, build_id, state, source='replacement', created_at=None):
    key = digest([user_id, subject, run_id, build_id, state])
    if db.get(BankStateArchive, key) is None:
        extra = {'created_at': created_at} if created_at is not None else {}
        db.add(BankStateArchive(id=key, user_id=user_id, subject=subject, run_id=run_id,
            build_id=build_id, state=copy.deepcopy(state), source=source, **extra))
        db.flush()


def archive_row(db, state, source='replacement'):
    old = state.previous or {}
    if old.get('state') is not None and old.get('build_id'):
        archive_state(db, state.user_id, state.subject, state.run_id,
                      old['build_id'], old['state'], source + ':previous')
    archive_state(db, state.user_id, state.subject, state.run_id, state.build_id, state.state, source)


def proven_manifest(db, subject, run_id, build):
    versions = list(db.scalars(select(BankVersion).where(BankVersion.subject == subject,
        BankVersion.run_id == run_id, BankVersion.build_id == build)))
    if not versions:
        return {}
    manifests = [manifest(v.bank) for v in versions]
    # A reused build with conflicting content cannot establish that question's identity.
    return {qid: sig for qid, sig in manifests[0].items()
            if sig and all(m.get(qid) == sig for m in manifests)}


def retained_sources(db, state):
    snapshots = {}
    for archived in db.scalars(select(BankStateArchive).where(
            BankStateArchive.user_id == state.user_id, BankStateArchive.subject == state.subject,
            BankStateArchive.run_id == state.run_id).order_by(BankStateArchive.created_at, BankStateArchive.id)):
        snapshots[archived.build_id] = archived.state
    previous = state.previous or {}
    if previous.get('build_id') and previous.get('state') is not None:
        snapshots[previous['build_id']] = previous['state']
    snapshots[state.build_id] = state.state
    result = []
    for build, value in snapshots.items():
        value = copy.deepcopy(value)
        if '_question_fingerprints' not in value:
            value['_question_fingerprints'] = proven_manifest(db, state.subject, state.run_id, build)
        result.append((build, None, value))
    return result


def augmented(db, row, bank, user_id, build_id, state=None):
    view = SimpleNamespace(subject=row.subject, run_id=row.run_id, build_id=build_id,
                           bank=bank, validation=row.validation)
    result = bank_personal.augment(db, view, user_id)
    if state:
        from app.bank_excluded import records
        ids = {q['question_id'] for q in result.get('questions', [])}
        restored = [entry for qid, entry in records(view).items() if qid not in ids
                    and state.get('excluded_question_decisions', {}).get(qid) == 'restored']
        if restored:
            result = copy.deepcopy(result)
            for entry in restored:
                result['questions'].append(copy.deepcopy(entry['question']))
                for key, field in [('concept', 'concepts'), ('plan', 'retrieval_plan')]:
                    value = entry.get(key)
                    if value and not any(c['concept_id'] == value['concept_id'] for c in result[field]):
                        result[field].append(copy.deepcopy(value))
    return result


def transition(db, state, row):
    """Caller holds the state row lock. No timestamps or grades are fabricated."""
    archive_row(db, state)
    old_state, old_build = copy.deepcopy(state.state), state.build_id
    target = augmented(db, row, row.bank, state.user_id, row.build_id, state.state)
    sources = retained_sources(db, state)
    value = migrate(target, sources)
    if old_build == row.build_id:
        session = copy.deepcopy(old_state.get('session'))
        if session:
            indices = [i for i, h in enumerate(value['history']) if h.get('session_id') == session['id']]
            session['start_index'] = min(indices) if indices else len(value['history'])
            value['session'] = session
        value['sessions'] = copy.deepcopy(old_state.get('sessions', []))
        served = old_state.get('served') or {}
        qid = served.get('question_id')
        if qid and old_state.get('_question_fingerprints', {}).get(qid) == manifest(target).get(qid):
            value['served'] = copy.deepcopy(served)
    state.previous = {'build_id': state.build_id, 'state': copy.deepcopy(state.state)}
    state.build_id, state.state = row.build_id, value
    state.state['_study_build_id'] = row.build_id


def content_changed(db, state, row):
    saved = state.state.get('_question_fingerprints') or {}
    current = manifest(row.bank or {})
    # Personal restores/additions and removal from active study do not erase
    # history. A reused ID with changed content does require a safe transition.
    return any(qid in current and current[qid] != sig for qid, sig in saved.items())


def replace_bank(db, row, incoming, new_build):
    """Archive bank + every affected state before changing either; one DB commit."""
    save_version(db, row.subject, row.run_id, row.build_id, row.bank)
    save_version(db, row.subject, row.run_id, new_build, incoming)
    old_build, old_bank = row.build_id, row.bank
    states = list(db.scalars(select(BankState).where(BankState.subject == row.subject,
                  BankState.run_id == row.run_id).with_for_update()))
    # Capture exact manifests for the bank currently in force before replacing it.
    for state in states:
        archive_row(db, state)
        if state.build_id == old_build and old_bank:
            value = copy.deepcopy(state.state)
            if '_question_fingerprints' not in value:
                value['_question_fingerprints'] = manifest(augmented(db, row, old_bank, state.user_id, old_build, value))
            state.state = value
    row.bank, row.build_id = incoming, new_build
    for state in states:
        if (old_build == new_build and state.build_id == new_build
                and state.state.get('_question_fingerprints') == manifest(augmented(
                    db, row, incoming, state.user_id, new_build, state.state))):
            continue
        transition(db, state, row)
