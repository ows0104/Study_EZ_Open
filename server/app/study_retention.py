"""Conservative content matching and deterministic replay of actual review facts.

IDs and concept labels are not evidence of identical content. Matching keeps
prompts, answers, formats, directions, authored choices and visual source references.
Only Unicode composition and whitespace differences are ignored.
"""
import copy
import hashlib
import json
import re
import unicodedata
from collections import defaultdict

from app.study_engine.engine import empty_state, record_review, dimension_key, reschedule_bank

CONTENT = ('format', 'retrieval_direction', 'question', 'answer', 'answer_units',
           'options', 'correct_option_ids', 'matching_left', 'matching_right',
           'answer_pairs', 'sequence_items', 'correct_order', 'option_pools')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def normalized(value):
    if isinstance(value, str):
        return ' '.join(unicodedata.normalize('NFC', value).split())
    if isinstance(value, list):
        return [normalized(v) for v in value]
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items()}
    return value


def fingerprint(question):
    if not question.get('question') or not question.get('format') or not question.get('answer'):
        return None
    content = {key: question.get(key) or ([] if key not in
        ('question', 'answer', 'format', 'retrieval_direction') else '') for key in CONTENT}
    # Reference lists often expand during evidence audits without changing a
    # self-contained text question. A visual-dependent prompt needs the same image.
    if re.search(r'그림|사진|도식|화살표|표시된|이미지|위\s*표|아래\s*표|다음\s*표|figure|image|diagram',
                 question['question'], re.I):
        content['visual_sources'] = question.get('source_refs', [])
    return digest(normalized(content))


def manifest(bank):
    return {q['question_id']: fingerprint(q) for q in bank.get('questions', [])}


def question_map(old_bank, new_bank, saved_manifest=None):
    targets = defaultdict(list)
    new = manifest(new_bank)
    for qid, sig in new.items():
        if sig:
            targets[sig].append(qid)
    old = saved_manifest if saved_manifest is not None else manifest(old_bank or {})
    result = {}
    for qid, sig in old.items():
        if not sig:
            continue
        if new.get(qid) == sig:
            result[qid] = qid
        elif len(targets[sig]) == 1:
            result[qid] = targets[sig][0]
    return result


def event_identity(build, entry):
    return entry.get('origin_event_id') or digest([build, entry.get('question_id'),
                                                  entry.get('timestamp'), entry.get('rating')])


def migrate(new_bank, sources):
    """sources: (build_id, source bank or None, authoritative state) tuples.

    Replays matching reviews at their original times, without inventing success
    or transferring a shared concept's mastery from changed/unmatched questions.
    All originals must be archived by the caller before this result is saved.
    """
    facts = {}
    maps = []
    questions = {q['question_id']: q for q in new_bank.get('questions', [])}
    signatures = manifest(new_bank)
    signature_ids = defaultdict(list)
    for qid, sig in signatures.items():
        if sig:
            signature_ids[sig].append(qid)
    tombstones = {key for _, _, state in sources for key in state.get('review_tombstones', [])}
    for build, bank, state in sources:
        mapping = question_map(bank, new_bank, state.get('_question_fingerprints'))
        maps.append(mapping)
        for event in state.get('history', []):
            qid = mapping.get(event.get('question_id'))
            if event.get('question_fingerprint'):
                sig = event['question_fingerprint']
                qid = (event['question_id'] if signatures.get(event['question_id']) == sig
                       else signature_ids[sig][0] if len(signature_ids[sig]) == 1 else None)
            if not qid or event.get('rating') not in ('Again', 'Hard', 'Good', 'Easy'):
                continue
            if not isinstance(event.get('timestamp'), (int, float)) or event['timestamp'] <= 0:
                continue
            origin = event_identity(build, event)
            if origin in tombstones:
                continue
            facts[origin] = (qid, event, build)
    out = empty_state()
    out['review_tombstones'] = sorted(tombstones)
    # Preserve explicit preferences on identical questions only.
    for field in ('question_tiers', 'excluded_question_decisions'):
        out[field] = {}
        for (_, _, state), mapping in zip(sources, maps):
            out[field].update({mapping[qid]: copy.deepcopy(value) for qid, value in state.get(field, {}).items() if qid in mapping})
    out['suspended_question_ids'] = sorted({mapping[qid] for (_, _, state), mapping in zip(sources, maps)
                                          for qid in state.get('suspended_question_ids', []) if qid in mapping})
    out['seen_question_ids'] = sorted({mapping[qid] for (_, _, state), mapping in zip(sources, maps)
                                      for qid in state.get('seen_question_ids', []) if qid in mapping})
    for origin, (qid, event, build) in sorted(facts.items(), key=lambda pair: (pair[1][1]['timestamp'], pair[0])):
        out = record_review(new_bank, out, qid, event['rating'], event['timestamp'])
        last = out['history'][-1]
        last.update(origin_event_id=origin,
                    question_fingerprint=signatures[qid],
                    session_id=event.get('session_id'),
                    origin_build_id=event.get('origin_build_id', build),
                    origin_question_id=event.get('origin_question_id', event['question_id']))
    # If an entire dimension's evidence is unchanged, retain its original
    # mastery/stability rather than recalculating it under today's policy.
    target_events = defaultdict(set)
    for origin, (qid, _, _) in facts.items():
        target_events[dimension_key(questions[qid])].add(origin)
    for (build, _, state), mapping in zip(sources, maps):
        by_dimension = defaultdict(list)
        for event in state.get('history', []):
            by_dimension[event.get('dimension')].append(event)
        for dim, entries in by_dimension.items():
            saved = state.get('dimensions', {}).get(dim)
            if not saved or any(e.get('question_id') not in mapping for e in entries):
                continue
            targets = {dimension_key(questions[mapping[e['question_id']]]) for e in entries}
            if len(targets) != 1:
                continue
            target = next(iter(targets))
            ids = {event_identity(build, e) for e in entries}
            if ids == target_events[target] and saved.get('reviews') == len(entries):
                out['dimensions'][target] = copy.deepcopy(saved)
                # Restore the matching review snapshots as well as the aggregate.
                originals = {event_identity(build, e): e for e in entries}
                for event in out['history']:
                    original = originals.get(event['origin_event_id'])
                    if original:
                        for key in ('mastery_before', 'mastery_after', 'stability_after', 'policy_version', 'policy_hash'):
                            if key in original:
                                event[key] = copy.deepcopy(original[key])
                for e in entries:
                    qid = mapping[e['question_id']]
                    if state.get('items', {}).get(e['question_id']):
                        out['items'][qid] = copy.deepcopy(state['items'][e['question_id']])
    out['_question_fingerprints'] = manifest(new_bank)
    return reschedule_bank(new_bank, out)
