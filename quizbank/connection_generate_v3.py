"""root-generation/3: add-only coverage, one job per judgment, minimal stage inputs.

docs/changes/2026-11-10-root-generation-3 (spec.md, plan.md). The /2 producer (connection_generate_v2) is
not changed; this module reuses its normalize/context/medical stages and its document assembly.

Order: intake bank → normalize (+ brief-fix) → coverage → map check → off-goal points → add ≤2
→ item review/fix by batch → context per conflict (+ one repair) → assembly → medical (once) → result.

A judgment value never stops the lecture (docs/changes/2026-11-10-gen3-item-scope): it reaches the goal,
question or conflict record it names. Only a stage that did not run to an accepted output stops, and that
is resumable. The assembly runs before the medical review, so what it refuses is found before that spend.

Every model call goes through `invoke(stage, ctx, material, model)` (runner.root_native_json.NativeJson).
Inputs, raw outputs and usage are written next to the ledger; nothing is retried automatically, except the two
named reruns of one call that judged nothing: review-retry/1 (Stages.judged) and transport-retry/1 (Stages._call,
a call the network dropped). A failed or interrupted stage continues only with an operator reason (`resume`);
completed stages are kept, and the add rounds and fix attempts recorded in the ledger are never reset.
"""
import copy
import hashlib
import json
import re
import threading
from pathlib import Path

from studyez_llm import codex
from studyez_contracts.roots import document_hash
from studyez_contracts.roots import generation_v2 as v2
from studyez_contracts.roots import generation_v3 as v3
from studyez_contracts.roots import map_tree
from studyez_contracts.roots.automation import validate_checks
from studyez_contracts.roots.source_assessment import envelope
from studyez_contracts.bank.validate import validate_bank
from . import connection_batches as batches
from . import connection_visuals as visual
from .connection_batches import BATCH_MODE

POLICY = v3.POLICY
COVERAGE_CHUNK = 60      # goals per coverage call (plan U2)
REVIEW_BATCH = 40        # questions per item review (plan U2)
MEDICAL_BATCH = 40   # questions per medical call inside medical-0 (P6)
ADD_PER_GOAL = 2         # new IDs offered per gap goal
# A bank may prefix its question ids (261104_01 wrote ST-Q061); the error still belongs to that question.
_QID = re.compile(r'^((?:[A-Za-z][0-9A-Za-z]*-)?Q[0-9A-Za-z_-]+)\b')
# A resolved source conflict whose linked questions do not cite one of its sources (validate_bank's citation check).
# The linked questions can be right; only a citation is missing. On 261111_02 (picornavirus, 2026-11-11) CF02 cited
# S1 and S2 while its one question cited S1, and the whole run stopped before any stage (user: record as warning).
_CONFLICT_GAP = re.compile(r'^\S+: \S+ 기준 문항 누락$')


def _prompt_hash(folders=('v3',)):
    """Fingerprint of the stage prompts. /3 hashes v3/ alone (its identity is unchanged); /4 adds v4/."""
    root = Path(__file__).resolve().parents[1] / 'content/prompts/learning-links'
    rows = [{p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root / f).glob('*.md'))} for f in folders]
    return document_hash(rows[0] if len(rows) == 1 else rows)


def chunks(items, size):
    return [items[i:i + size] for i in range(0, len(items), size)] or [[]]


# early-call/1 (docs/changes/2026-11-11-pipeline-overlap): a stage whose input is already decided is called before
# its turn, beside the stages still running. Its answer waits in <out>/.early/<stage>.json with the input
# fingerprint; when the stage's turn comes, Stages.run takes it instead of calling the model if, and only if, the
# input it then builds has that fingerprint. Stage names, inputs, ledger entries and the result are the ones a
# call at its turn makes.
EARLY_POLICY = 'early-call/1'


def early_path(out, name):
    return Path(out) / '.early' / (name + '.json')


def write_early(out, name, input_hash, raw=None, info=None, error=None):
    """Keep an early call's answer, or the failure it ended with, for the stage's turn."""
    from . import connection_generate as g
    row = {'policy': EARLY_POLICY, 'stage': name, 'inputHash': input_hash}
    row.update({'error': str(error)[:4000], 'errorType': type(error).__name__} if error is not None else {'raw': raw, 'info': info})
    path = early_path(out, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    g.write(path, row)
    return row


def set_seat_aside(out, name, suffix):
    """Move <out>/.native/<stage> out of the stage's way (a call that will not be used) and return its new name."""
    seat = Path(out) / '.native' / name
    if not seat.exists():
        return None
    target = next(x for x in (seat.with_name(name + suffix + ('' if k == 0 else f'-{k}')) for k in range(1000)) if not x.exists())
    seat.replace(target)
    return '.native/' + target.name


class Stages:
    """Ledger of stage calls with archived evidence. Same rules as the /2 producer: no automatic rerun.

    `fresh`: keys only a new ledger gets (a policy of this code); a ledger made without them keeps running without."""

    def __init__(self, packet, out, model, invoke, resume=None, policy=POLICY, prompts=('v3',), fresh=None):
        from . import connection_generate as g
        self.g, self.out, self.model, self.invoke, self.policy = g, Path(out), model, invoke, policy
        self.path = self.out / 'ledger.json'
        # transport-retry/1: how a stage waits for the network before its one retry (tests replace it).
        self.wait_network = codex.wait_for_network
        self._early, self._early_pool = {}, None   # early-call/1: stage name -> (input fingerprint, future)
        # Batches and other independent judgments of one run call stages side by side (connection_batches);
        # every change to the ledger and its file happens under this lock.
        self.lock = threading.RLock()
        identity = document_hash({'base': g.identity(packet, model), 'v3': policy, 'prompts': _prompt_hash(prompts)})
        if self.path.exists():
            self.ledger = json.loads(self.path.read_text(encoding='utf-8'))
            v3.require(self.ledger.get('pipelineVersion') == policy, '기존 실행의 파이프라인 판이 다릅니다. 이력과 상한을 보존합니다.')
            v3.require(self.ledger.get('inputHash') == packet['inputHash'], '다른 packet으로는 이어 가지 않습니다.')
            if self.ledger.get('identity') != identity or any(s['status'] != 'completed' for s in self.ledger['stages'].values()):
                v3.require(type(resume) is str and resume.strip(),
                           '이전 실행이 실패·중단됐거나 코드가 달라졌습니다. 이력과 상한을 보존합니다. 이어 가려면 --resume <이유>.')
            self.resume_row = None
            if resume:
                self.resume_row = {'reason': resume, 'identityBefore': self.ledger.get('identity'), 'identity': identity, 'superseded': []}
                self.ledger.setdefault('stageResumes', []).append(self.resume_row)
                self.ledger['identity'] = identity
                self._retire_other_model()
        else:
            v3.require(not any(p.name != 'packet.json' for p in self.out.glob('*.json')), '기존 산출물의 ledger가 없습니다. 자동 재시작하지 않습니다.')
            self.out.mkdir(parents=True, exist_ok=True)
            self.ledger = {'pipelineVersion': policy, 'inputHash': packet['inputHash'], 'identity': identity, 'stages': {},
                           'addRounds': 0, 'fixAttempts': {}, 'verdictLedger': [],
                           # A new run reviews its batches side by side; a ledger without this key keeps the
                           # one-after-another order it was made with (docs/changes/2026-11-11-root-batch-parallel).
                           'batchMode': BATCH_MODE, **(fresh or {})}
            self.resume_row = None
        self.save()

    @property
    def parallel(self):
        return self.ledger.get('batchMode') == BATCH_MODE

    def save(self):
        with self.lock:
            self.g.write(self.path, self.ledger)

    def canonical(self, names):
        """Put the ledger records of `names` in this order, where the first of them stands, whatever order the
        calls finished in; review retries follow the stage order. The result then does not depend on timing."""
        with self.lock:
            stages = self.ledger['stages']
            names = [n for n in dict.fromkeys(names) if n in stages]
            if not names:
                return
            items = list(stages.items())
            at = min(i for i, (k, _) in enumerate(items) if k in set(names))
            rest = [(k, v) for k, v in items if k not in set(names)]
            ordered = rest[:at] + [(n, stages[n]) for n in names] + rest[at:]
            self.ledger['stages'] = dict(ordered)
            position = {k: i for i, (k, _) in enumerate(ordered)}
            if self.ledger.get('reviewRetries'):
                self.ledger['reviewRetries'].sort(key=lambda r: position.get(r['stage'], len(position)))
            self.save()

    def _retire_other_model(self):
        """On an operator resume with another model, a completed stage whose native receipt names a different model
        moves to the resume archive and runs again with this one: the ledger never mixes models it cannot verify
        (docs/changes/2026-11-14-root-claude-provider). A stage without a native receipt keeps the old rule."""
        current = codex.model_name(self.model)
        for name, entry in list(self.ledger['stages'].items()):
            if entry.get('status') != 'completed':
                continue
            usage = self.out / (name + '.usage.json')
            receipt = json.loads(usage.read_text(encoding='utf-8')).get('fileReceipt') if usage.exists() else None
            recorded = ((receipt or {}).get('proof') or {}).get('model')
            if recorded and recorded != current:
                self._archive(name)
                print('── 모델이 달라 다시 실행: ' + name + ' (' + recorded + ' → ' + current + ')', flush=True)
        self.save()

    def retire_legacy(self):
        """Stage names this code no longer produces (the lecture-wide `context-0`/`context-1` of the first /3
        version): on an operator resume they move to the resume archive like any superseded stage, so the manifest
        lists only stages whose output this result carries. A stage reused through the verdict ledger stays."""
        for name in [n for n in self.ledger['stages'] if re.fullmatch(r'context-\d+', n)]:
            v3.require(self.resume_row is not None, name + ': 이 실행이 쓰지 않는 이전 단계 기록이 있습니다. 이어 가려면 --resume <이유>.')
            self._archive(name)
        self.save()

    def judged(self, name, ctx, accept, material=None):
        """A coverage or review stage that judged nothing, or a context judgment left unknown, runs once more in a
        fresh session (review-retry/1, as /2: empty-judgment, final-context-unknown).

        The runner has already sent the error back once into the same session; the abandoned stage is archived
        under .retry-<stage>/ and recorded in ledger reviewRetries. A second empty judgment stops the lecture."""
        try:
            return self.run(name, ctx, accept, material=material)
        except ValueError as error:
            if str(error) not in (v3.UNPERFORMED_COVERAGE, v3.UNPERFORMED_REVIEW, v3.UNPERFORMED_CONTEXT, v3.UNPERFORMED_MAP) or \
                    any(r['stage'] == name for r in self.ledger.get('reviewRetries', [])):
                raise
            kind = 'empty-judgment'
        with self.lock:
            self._retire_for_retry(name, kind)
        print('── 검토 포기(' + kind + '): ' + name + ' 새 세션으로 한 번 다시 실행', flush=True)
        return self.run(name, ctx, accept, material=material)

    def _retire_for_retry(self, name, kind):
        archive = self.out / f'.retry-{name}'
        archive.mkdir()
        moved = []
        for suffix in ('.input.json', '.raw.json', '.usage.json', '.json'):
            path = self.out / (name + suffix)
            if path.exists():
                path.replace(archive / path.name)
                moved.append(path.name)
        seat = self.out / '.native' / name
        if seat.exists():
            (archive / '.native').mkdir()
            seat.replace(archive / '.native' / name)
            moved.append('.native/' + name)
        self.ledger.setdefault('reviewRetries', []).append({'policy': 'review-retry/1', 'stage': name, 'kind': kind,
                                                            'abandoned': self.ledger['stages'].pop(name), 'files': moved})
        self.save()

    def _archive(self, name):
        rows = self.ledger.setdefault('stageResumes', [])
        archive = self.out / f'.resume-{len(rows)}'
        archive.mkdir(exist_ok=True)
        for suffix in ('.input.json', '.raw.json', '.usage.json', '.json'):
            path = self.out / (name + suffix)
            if path.exists():
                path.replace(archive / path.name)
        seat = self.out / '.native' / name
        if seat.exists():
            (archive / '.native').mkdir(exist_ok=True)
            seat.replace(archive / '.native' / name)
        self.resume_row['superseded'].append({'name': name, 'entry': self.ledger['stages'].pop(name)})

    def _call(self, name, payload, material):
        """The model call of one stage. A call that ended because the network dropped (codex.network_failure: the
        CLI never brought an answer back) waits for the network and runs once more: transport-retry/1
        (docs/changes/2026-11-11-pipeline-resilience, user 2026-11-11 「오류가 나서 끊기고」).

        This is not a second opinion. Nothing was judged in the dropped call, the input is the same, and no review
        or fix count moves. Its diagnostics stay under .native/<stage>.net and the ledger's `transportRetries` names
        it. A provider refusal, a time limit, a check failure and a second drop of the same stage stop as before."""
        try:
            return self.invoke(name, payload, material, self.model)
        except Exception as error:
            with self.lock:
                again = any(r['stage'] == name for r in self.ledger.get('transportRetries', []))
            if again or not codex.network_failure(error):
                raise
            dropped = error
        with self.lock:
            seat, kept = self.out / '.native' / name, None
            if seat.exists():
                kept = '.native/' + name + '.net'
                seat.replace(self.out / '.native' / (name + '.net'))
            self.ledger.setdefault('transportRetries', []).append(
                {'policy': 'transport-retry/1', 'stage': name, 'error': str(dropped)[-600:], 'kept': kept})
            self.save()
        print('── 네트워크 끊김: ' + name + ' 연결을 기다린 뒤 한 번 다시 실행', flush=True)
        if not self.wait_network():
            raise dropped
        return self.invoke(name, payload, material, self.model)

    def start_early(self, name, ctx, state=None, material=None):
        """Call stage `name` now, in the background, with the input its turn is expected to build (early-call/1).

        Nothing is recorded in the ledger until the stage's turn. Returns False, and calls nothing, when the stage
        already has a ledger entry, an early answer or a seat: a resumed run never calls a stage twice this way."""
        ctx = {**ctx, '_pipeline_version': self.policy}
        input_hash = document_hash(ctx)
        payload = {**ctx, '_check': state} if state is not None else ctx
        folder = Path(material) if material is not None else self.out / 'material'
        with self.lock:
            if (name in self.ledger['stages'] or name in self._early or early_path(self.out, name).exists()
                    or (self.out / '.native' / name).exists()):
                return False
            if self._early_pool is None:
                from concurrent.futures import ThreadPoolExecutor
                self._early_pool = ThreadPoolExecutor(max_workers=batches.BATCH_WORKERS)

            def job():
                print('── 연결 자동출제 ' + self.policy[self.policy.index('/'):] + ' ' + name + ' (미리 시작)', flush=True)
                try:
                    raw, info = self._call(name, payload, folder)
                except Exception as error:
                    write_early(self.out, name, input_hash, error=error)
                    return error
                write_early(self.out, name, input_hash, raw, info)
                return None
            self._early[name] = (input_hash, self._early_pool.submit(job))
        return True

    def _take_early(self, name, input_hash):
        """The early answer of `name` for exactly this input: (raw, info), or None when there is none to use.

        An early call that failed fails the stage here, at its turn, as the same call would have (no second try by
        itself). An early answer for another input is not used: its seat moves to .native/<stage>.early and the
        stage is called normally."""
        with self.lock:
            held = self._early.pop(name, None)
        error = held[1].result() if held else None   # waits for a call still running
        path = early_path(self.out, name)
        if not path.exists():
            # A seat without a ledger entry or an answer is an early call the process did not live to finish.
            aside = set_seat_aside(self.out, name, '.early')
            if aside:
                self._record_early(name, False, aside)
            return None
        row = json.loads(path.read_text(encoding='utf-8'))
        path.unlink()
        if row.get('policy') != EARLY_POLICY or row.get('inputHash') != input_hash:
            self._record_early(name, False, set_seat_aside(self.out, name, '.early'))
            print('── 미리 시작한 ' + name + ': 입력이 달라져 쓰지 않고 다시 호출', flush=True)
            return None
        self._record_early(name, True, None)
        if 'error' in row:
            raise error if error is not None else ValueError(row['error'])
        return row['raw'], row['info']

    def _record_early(self, name, used, kept):
        with self.lock:
            rows = self.ledger.setdefault('earlyCalls', [])
            rows.append({'policy': EARLY_POLICY, 'stage': name, 'used': used, **({'kept': kept} if kept else {})})
            rows.sort(key=lambda r: r['stage'])   # batches take their answers in whatever order they finish
            self.save()

    def settle_early(self):
        """Before the result: wait for early calls nobody took and move them out of the way, so every seat under
        .native/ belongs to a stage of the ledger."""
        with self.lock:
            names = list(self._early)
        names += [p.stem for p in sorted((self.out / '.early').glob('*.json')) if p.stem not in names] if (self.out / '.early').is_dir() else []
        for name in names:
            with self.lock:
                held = self._early.pop(name, None)
            if held:
                held[1].result()
            early_path(self.out, name).unlink(missing_ok=True)
            if name not in self.ledger['stages']:
                self._record_early(name, False, set_seat_aside(self.out, name, '.early'))
        # The early calls' own copies of material/ (made so that a stage writing new images could not disturb them).
        import shutil
        for folder in sorted((self.out / '.early').glob('m[0-9]*')) if (self.out / '.early').is_dir() else []:
            shutil.rmtree(folder, ignore_errors=True)

    def run(self, name, ctx, accept, state=None, material=None):
        """One model stage. A completed stage with the same input is reused; anything else runs once.

        `state` (P6) is what the merge after this stage receives. It goes to the transport as `_check` so the
        runner's in-session check runs that same merge; it is not part of the stage input or its hash.
        `material` is the folder the stage reads; a review batch running beside others has its own copy."""
        ctx = {**ctx, '_pipeline_version': self.policy}
        input_hash = document_hash(ctx)
        with self.lock:
            prior = self.ledger['stages'].get(name)
            if prior and prior['status'] == 'completed' and prior['inputHash'] == input_hash:
                return json.loads((self.out / (name + '.json')).read_text(encoding='utf-8'))
            if prior:
                v3.require(self.resume_row is not None, name + ': 중단/실패/달라진 호출은 자동 재실행하지 않습니다.')
                self._archive(name)
            entry = {'status': 'started', 'inputHash': input_hash}
            self.ledger['stages'][name] = entry
            self.save()
        self.g.write(self.out / (name + '.input.json'), ctx)
        print('── 연결 자동출제 ' + self.policy[self.policy.index('/'):] + ' ' + name, flush=True)
        try:
            early = self._take_early(name, input_hash) if prior is None else None
            raw, info = early if early is not None else self._call(
                name, {**ctx, '_check': state} if state is not None else ctx,
                Path(material) if material is not None else self.out / 'material')
            self.g.write(self.out / (name + '.raw.json'), raw)
            self.g.write(self.out / (name + '.usage.json'), info)
            with self.lock:
                entry.update(rawOutputHash=document_hash(raw), usageHash=document_hash(info))
            value = accept(raw)
            self.g.write(self.out / (name + '.json'), value)
            with self.lock:
                entry.update(status='completed', outputHash=document_hash(value))
                self.save()
            return value
        except BaseException:
            with self.lock:
                entry['status'] = 'failed'
                self.save()
            raise


# ---------------------------------------------------------------- helpers
def _merge_row(old, new, replaced=()):
    """Coverage of one goal after a narrower judgment: evidence of replaced/new questions comes from `new`."""
    if old is None:
        return new
    keep = [e for e in old['evidence'] if e['question_id'] not in set(replaced) | {x['question_id'] for x in new['evidence']}]
    evidence = keep + copy.deepcopy(new['evidence'])
    probe = {**new, 'status': 'covered', 'evidence': keep}
    kept_cover = old['status'] == 'covered' and bool(v3.covering(probe))
    status = 'covered' if new['status'] == 'covered' or kept_cover else new['status']
    return {'direction_id': new['direction_id'], 'status': status, 'evidence': evidence,
            'reason': new['reason'] if new['status'] == 'covered' or not kept_cover else old['reason']}


def _question_of(text, question_ids=None):
    """The question a validate_bank error line belongs to, or None. The line starts with the question's id; a bank may
    number its questions any way (261104_01 ST-Q061, 261110_03 R049), so the bank's own ids decide when they are given."""
    label = text.split(':', 1)[0].strip()
    if question_ids is not None and label in question_ids:
        return label
    m = _QID.match(text)
    return m.group(1) if m else None


def _bank_findings(bank, sources, attempts=None):
    """Code checks per question (format errors and quality measures); never a model call.

    The quality measures only advise (bank/quality.py warnings). They go to a question's first fix; a question that
    was fixed once is not sent back for them again (`attempts`): on the 261113_01 run the model left such a question
    as it was and the same warning spent its second fix (docs/changes/2026-11-11-tier-from-importance)."""
    found = {}
    ids = {q['question_id'] for q in bank.get('questions', [])}
    done = {q for q, n in (attempts or {}).items() if n >= 1}
    advice = [r['text'] for r in v2.quality_reasons(bank) if not set(r['question_ids']) & done]
    for text in validate_bank(bank, sources)['errors'] + advice:
        qid = _question_of(text.replace('문항 품질: ', ''), ids)
        if qid:
            found.setdefault(qid, []).append(text)
    for qid in v3.history_marked(bank):
        found.setdefault(qid, []).append(qid + ': 문항·정답·해설에 검수·판정 이력 표현이 있다. 원본에 근거한 의학 설명으로만 쓴다.')
    return found


def intake_rejections(errors, quiet=False, question_ids=None):
    """Questions left out at intake, from validate_bank errors. A bank-level error stops the run, except a resolved
    conflict's missing source citation: it is printed and carried on, and stays in the final validation errors
    (shown to the administrator as an issue) unless a later fix adds the citation.

    The front bank stage runs this same function as its check (runner.root_front.bank, `quiet`), so a bank-level
    error goes back to the author's session instead of stopping the lecture here."""
    rejected, gaps = [], []
    for text in errors:
        if _CONFLICT_GAP.match(text):
            if text not in gaps:  # validate_bank repeats it once per locator of that source
                gaps.append(text)
                if not quiet:
                    print('접수 경고(출처 충돌 인용 누락, 진행): ' + text, flush=True)
            continue
        qid = _question_of(text, question_ids)
        v3.require(qid, '문제은행 형식 오류가 특정 문항에 속하지 않습니다. 결과를 만들지 않고 보존합니다: ' + text)
        rejected.append({'question_id': qid, 'error': text})
    return rejected


def _intake(packet, out):
    """The independently authored bank (1c or a web response). Questions with format errors are left out."""
    intake = copy.deepcopy(packet['intakeBank'])
    bank, projection = v3.intake_projection(intake['bank'])
    sources = [s['id'] for s in packet['sources']]
    report = validate_bank(bank, sources)
    rejected = intake_rejections(report['errors'], question_ids={q['question_id'] for q in bank['questions']})
    bad = {r['question_id'] for r in rejected}
    if bad:
        bank['questions'] = [q for q in bank['questions'] if q['question_id'] not in bad]
        for q in bank['questions']:
            q['prerequisites'] = [p for p in q.get('prerequisites', []) if p not in bad]
        intake['visual_stimuli'] = [s for s in intake['visual_stimuli'] if s['question_id'] not in bad]
    cloze = v3.cloze_units(bank)   # answer_units = the stem's blanks (not intake_projection: the server re-derives that)
    rendered = visual.render(bank, intake['visual_stimuli'], packet, out / 'material')
    return rendered, intake['visual_stimuli'], intake['clinical_conflicts'], rejected, projection, cloze


def _join_points(bank, brief, rows):
    """Code join: a question implements the points of the goals it was judged against (spec R0)."""
    owner = {d['direction_id']: t['target_id'] for t in brief['targets'] for d in t['directions']}
    points_of = {}
    for p in brief['points']:
        for tid in p['target_ids']:
            points_of.setdefault(tid, []).append(p['point_id'])
    found = {}
    for did, row in rows.items():
        for e in row['evidence']:
            found.setdefault(e['question_id'], set()).update(points_of.get(owner[did], []))
    value = copy.deepcopy(bank)
    for q in value['questions']:
        if q['question_id'] in found:
            q['point_ids'] = sorted(found[q['question_id']])
    return value


# ---------------------------------------------------------------- stage checks (P6)
def check_stage(kind, value, ctx, state, scratch):
    """Everything that runs after an add/fix/supplement-normalize stage, without changing anything: the contract
    check, the same merge (generation_v3), and for add/fix the same image render into `scratch`.

    The runner's in-session check (runner/root_native_json.check_file) and this orchestrator's acceptance call
    this one function, so whatever would stop the lecture after the stage is found while the model can still fix
    it (one follow-up in the same session). Before P6 the merge and render ran only afterwards (261102_02 stopped
    twice there)."""
    if kind == 'supplement-normalize':
        return v3.check_supplement_normalize(value, ctx, state)
    if kind == 'supplement':
        return v3.check_supplement(value, ctx, state)
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    if kind == 'add':
        v3.check_added(value, ctx, state)
        merged, _ = v3.merge_added(state['bank'], state['clinical_conflicts'], value, ctx['allowed_question_ids'])
        stimuli = [*state['stimuli'], *value['visual_stimuli']]
    else:
        v3.check_fixed(value, ctx, state)
        merged, _, changed = v3.merge_fixes(state['bank'], state['clinical_conflicts'], value, [q['question_id'] for q in ctx['questions']])
        stimuli = [s for s in state['stimuli'] if s['question_id'] not in set(changed)] + value['visual_stimuli']
    visual.render(merged, stimuli, {'sources': state['sources']}, scratch)
    return value


def _medical_batches(invoke, workers=1):
    """medical-0 as one stage of MEDICAL_BATCH-question calls (P6). One blind call over a whole 150-question bank
    risks omitted verdicts (the /2 recovery runner/root_medical_retry.py exists for that) and the 900 s call limit;
    each call here is a review-sized batch with only its questions, their facts and images. The stage input,
    its hash and the merged output are what validate_result proves; the medical review still runs once."""
    def call(stage, ctx, material, model):
        if not stage.startswith('medical-'):
            return invoke(stage, ctx, material, model)
        from .review import shape
        bank, conflicts = ctx['bank'], ctx['clinicalInput']['clinical_conflicts']
        sent = {q['question_id'] for q in ctx['clinicalInput']['questions']}
        rows, pool, summaries, infos, unreviewed = [], [], [], [], []
        unreviewed += [{'question_id': q['question_id'], 'reason': '검수·판정 이력 표현이 남아 의학 검토에 보내지 않았다'}
                       for q in bank['questions'] if q['question_id'] not in sent]

        def ask(part):
            sub = {**bank, 'questions': part}
            return invoke(stage, {**ctx, 'bank': sub, 'clinicalInput': v2.medical_input(sub, conflicts)}, material, model)

        def take(part, answer):
            value, info = answer
            got = {r['question_id'] for r in value['reviews']}
            rows.extend(r for r in value['reviews'] if r['question_id'] in {q['question_id'] for q in part})
            pool.extend(value.get('pool_checks', []))
            summaries.append(value['summary'])
            infos.append(info)
            return [q for q in part if q['question_id'] not in got]

        # A new run asks its batches side by side (docs/changes/2026-11-11-root-batch-parallel); the answers are
        # taken in batch order, each batch's second ask right after its first, as the one-after-another order did.
        parts = chunks([q for q in bank['questions'] if q['question_id'] in sent], MEDICAL_BATCH)
        firsts = batches.parallel_calls([lambda part=part: ask(part) for part in parts], workers)
        left = [[q for q in part if q['question_id'] not in {r['question_id'] for r in answer[0]['reviews']}]
                for part, answer in zip(parts, firsts)]
        seconds = iter(batches.parallel_calls([lambda part=part: ask(part) for part in left if part], workers))
        for part, answer, again in zip(parts, firsts, left):
            # A verdict the call left out is asked once more, alone; one still missing is recorded, not invented,
            # and never stops the lecture (the medical review is a note, not a gate: medical-final/1).
            missing = take(part, answer)
            if missing:
                missing = take(again, next(seconds))
            unreviewed += [{'question_id': q['question_id'], 'reason': '의학 검토가 두 번의 호출에서 이 문항의 판정을 내지 않았다'} for q in missing]
        rows += [v3.unreviewed_row(r['question_id'], r['reason']) for r in unreviewed]
        order = {q['question_id']: i for i, q in enumerate(bank['questions'])}
        rows.sort(key=lambda r: order[r['question_id']])
        merged = shape({'summary': ' / '.join(summaries), 'reviews': rows, 'pool_checks': pool}, bank)
        usage = {}
        for info in infos:
            for k, v in (info.get('usage') or {}).items():
                usage[k] = usage.get(k, 0) + v
        info = {'usage': usage, 'cost_usd': sum(i.get('cost_usd') or 0 for i in infos),
                'duration_ms': sum(i.get('duration_ms') or 0 for i in infos),
                'models': list(dict.fromkeys(m for i in infos for m in (i.get('models') or []))),
                'medicalBatches': [len(p) for p in chunks([q for q in bank['questions'] if q['question_id'] in sent], MEDICAL_BATCH)],
                'medicalCalls': len(infos), 'medicalUnreviewed': unreviewed}
        return merged, info
    return call


def _state(bank, conflicts, stimuli, packet):
    """The check state of an add/fix stage: what its merge and render receive."""
    return {'bank': visual.authored(bank), 'clinical_conflicts': copy.deepcopy(conflicts), 'stimuli': copy.deepcopy(stimuli),
            'sources': [{k: s[k] for k in ('id', 'localPath', 'sha256')} for s in packet['sources']]}


# ---------------------------------------------------------------- run
def run(packet, out, model, invoke, resume=None):
    from . import connection_generate as g
    out = Path(out)
    v3.require(packet.get('generationPolicy') == POLICY, 'root-generation/3 packet required')
    st = Stages(packet, out, model, invoke, resume)
    ledger = st.ledger
    sources = g.prepare(packet, out / 'material')
    page_counts = {s['source_id']: s['page_count'] for s in sources}
    base = {k: packet[k] for k in ('title', 'scope', 'conceptMap', 'points', 'examDate')}
    base.update(lecture_id=packet['subject'] + '/' + packet['runId'], sources=sources,
                preserved_scope=g.lecture_scope(packet['title'], packet['sources']))
    table = v2.importance_table(packet)
    points_doc = json.loads(packet['points']) if table is not None else None

    # 1c: intake bank -------------------------------------------------------
    bank, stimuli, conflicts, rejected, intake_changes, intake_cloze = _intake(packet, out)
    initial_bank = copy.deepcopy(bank)
    intake_conflict_ids = {c['conflict_id'] for c in [*bank.get('source_conflicts', []), *conflicts]}

    # normalize (+ one structural correction) -------------------------------
    def accept_brief(raw):
        v2.validate_shape(raw, v2.BRIEF, 'initial brief2')
        value = v2.blank_target_importance(raw) if table is not None else raw
        if value['scope']['label'] != packet['title']:
            value = {**value, 'scope': {**value['scope'], 'label': packet['title']}}
        v3.require(raw['sources'] == sources and raw['lecture_id'] == base['lecture_id'], 'Different initial source/lecture')
        return value
    brief = st.run('normalize', base, accept_brief)
    initial_brief = brief
    findings = v2.brief_findings(brief)
    if findings:
        fixed = st.run('v3-brief-fix', {'brief': brief, 'errors': findings, 'pages': []},
                       lambda raw: v3.check_brief_fix(raw, {'brief': brief}))
        brief = v2.blank_target_importance(fixed['brief']) if table is not None else fixed['brief']

    # 2: coverage, 2m: map check (independent judgments; side by side in a new run) ----------------------
    rows = {}
    dids = [d['direction_id'] for t in brief['targets'] for d in t['directions']]
    calls = [(f'v3-coverage-0-{k}', ctx, lambda raw, ctx=ctx: v3.check_coverage(raw, ctx['goals'], ctx['questions']))
             for k, ctx in enumerate(v3.coverage_input(brief, bank, part) for part in chunks(dids, COVERAGE_CHUNK))]
    ctx = v3.map_check_input(brief, table)
    calls.append(('v3-map-check-0', ctx, lambda raw, ctx=ctx: v3.check_map_input(raw, ctx)))
    values = batches.judgments(st, calls)
    for value in values[:-1]:
        rows.update({r['direction_id']: r for r in value['rows']})
    map_checks = [values[-1]]

    # 2a: off-goal questions → supplement points ----------------------------
    judged = {e['question_id'] for r in rows.values() for e in r['evidence']}
    off_goal = [q['question_id'] for q in bank['questions'] if q['question_id'] not in judged]
    supplement, out_of_scope = [], []
    if off_goal:
        v3.require(points_doc is not None, '목표 밖 문항의 포인트 보충에는 exam-point-extract/3 포인트가 필요합니다.')
        ctx = v3.supplement_input(bank, off_goal, points_doc, page_counts)
        state = {'points_doc': points_doc}
        value = st.run('v3-supplement', ctx, lambda raw: check_stage('supplement', raw, ctx, state, None), state)
        points_doc, table, supplement = v3.attach_points(points_doc, value, off_goal, page_counts,
                                                         [p['point_id'] for p in brief['points']])
        new_points = [p for p in points_doc['points'] if p['point_id'] in {d['point_id'] for d in supplement if d['decision'] == 'point'}]
        dup = [d for d in supplement if d['decision'] == 'duplicate_of']
        out_of_scope = [d for d in supplement if d['decision'] == 'out_of_scope']
        if new_points:
            allowed = v3.supplement_ids(brief, len(new_points))
            ctx = v3.supplement_normalize_input(brief, new_points, allowed)
            state = {'brief': brief, 'blank': table is not None}
            addition = st.run('v3-supplement-normalize', ctx, lambda raw: check_stage('supplement-normalize', raw, ctx, state, None), state)
            brief, new_tids = v3.extend_brief(brief, v3.supplement_addition(brief, addition, table is not None), [p['point_id'] for p in new_points])
            new_dids = [d['direction_id'] for t in brief['targets'] if t['target_id'] in new_tids for d in t['directions']]
            origins = [p['origin_question_id'] for p in new_points]
            ctx = v3.coverage_input(brief, bank, new_dids, origins)
            value = st.judged('v3-coverage-supplement', ctx, lambda raw: v3.check_coverage(raw, ctx['goals'], ctx['questions']))
            rows.update({r['direction_id']: r for r in value['rows']})
            ctx = v3.map_check_input(brief, table, new_tids)
            map_checks.append(st.judged('v3-map-check-1', ctx, lambda raw, ctx=ctx: v3.check_map_input(raw, ctx)))
        if dup:
            owner = {d['direction_id']: t for t in brief['targets'] for d in t['directions']}
            goal_ids = sorted({did for d in dup for did, t in owner.items()
                               if any(d['point_id'] in p['point_id'] and t['target_id'] in p['target_ids'] for p in brief['points'])})
            if goal_ids:
                ctx = v3.coverage_input(brief, bank, goal_ids, [d['question_id'] for d in dup])
                value = st.judged('v3-coverage-duplicate', ctx, lambda raw: v3.check_coverage(raw, ctx['goals'], ctx['questions']))
                for r in value['rows']:
                    rows[r['direction_id']] = _merge_row(rows.get(r['direction_id']), r)
        gone = {d['question_id'] for d in out_of_scope}
        off_questions = [q for q in bank['questions'] if q['question_id'] in gone]
        bank['questions'] = [q for q in bank['questions'] if q['question_id'] not in gone]
        for q in bank['questions']:
            if set(q.get('prerequisites', [])) & gone:
                q['prerequisites'] = [p for p in q['prerequisites'] if p not in gone]
        stimuli = [s for s in stimuli if s['question_id'] not in gone]
    else:
        off_questions = []
    bank = _join_points(bank, brief, rows)

    # 3: add only for gap goals (≤2) ----------------------------------------
    # Round numbers are fixed (v3-add-0, v3-add-1): a resumed run replays completed rounds from their records,
    # so the recorded count only grows and never exceeds ADD_LIMIT.
    restated = []   # existing items an add/fix stage wrote again (v3.restated); not taken, kept for the record (P6)
    for n in range(v3.ADD_LIMIT):
        gaps = [did for did in [d['direction_id'] for t in brief['targets'] for d in t['directions']] if rows[did]['status'] != 'covered']
        if not gaps:
            break
        allowed = v3.next_question_ids(bank, ADD_PER_GOAL * len(gaps))
        ctx = v3.add_input(brief, bank, gaps, allowed)
        if ledger['addRounds'] < n + 1:
            ledger['addRounds'] = n + 1
            st.save()
        state = _state(bank, conflicts, stimuli, packet)
        value = st.run(f'v3-add-{n}', ctx, lambda raw, ctx=ctx, state=state, n=n: check_stage('add', raw, ctx, state, out / '.check-render' / f'v3-add-{n}'), state)
        restated.extend({'stage': f'v3-add-{n}', **r} for r in v3.restated(visual.authored(bank), conflicts, value))
        bank, conflicts = v3.merge_added(visual.authored(bank), conflicts, value, allowed)
        stimuli = [*stimuli, *value['visual_stimuli']]
        bank = visual.render(bank, stimuli, packet, out / 'material')
        added = [q['question_id'] for q in value['questions']]
        for k, part in enumerate(chunks(gaps, COVERAGE_CHUNK)):
            ctx = v3.coverage_input(brief, bank, part, added)
            got = st.judged(f'v3-coverage-{n + 1}-{k}', ctx, lambda raw, ctx=ctx: v3.check_coverage(raw, ctx['goals'], ctx['questions']))
            for r in got['rows']:
                rows[r['direction_id']] = _merge_row(rows[r['direction_id']], r)

    # 4: item review and fixes by batch -------------------------------------
    # Batches start from one snapshot and run side by side unless a conflict record or a prerequisite link joins
    # two of them (connection_batches, docs/changes/2026-11-11-root-batch-parallel); otherwise one after another.
    source_ids = [s['id'] for s in packet['sources']]

    def covered_by(S):
        cov = {}
        for did, r in S.rows.items():
            for q in v3.covering(r):
                cov.setdefault(q, []).append(did)
        return cov

    def review_batch(S, stages, name, qids):
        """Reviews of `qids`: a recorded verdict for the same content is reused (P2); only the rest are asked."""
        got, todo = {}, []
        for q in S.bank['questions']:
            if q['question_id'] not in qids:
                continue
            again = v3.reusable(S.verdicts, 'item', q['question_id'], v3.item_hash(q, S.bank, S.conflicts))
            if again is not None:
                got[q['question_id']] = again
            else:
                todo.append(q['question_id'])
        if not todo:
            return got
        ctx = v3.review_input(S.bank, todo, S.conflicts)
        value = stages.judged(name, ctx, lambda raw: v3.check_review_input(raw, ctx))
        by_id = {q['question_id']: q for q in S.bank['questions']}
        for r in value['reviews']:
            got[r['question_id']] = r
            entry = v3.ledger_entry('item', r['question_id'], v3.item_hash(by_id[r['question_id']], S.bank, S.conflicts), r, name)
            if entry not in S.verdicts:   # a resumed run replays the same records
                S.verdicts.append(entry)
        st.save()
        return got

    def fix_round(S, stages, name, review_name, coverage_name, targets, findings):
        """One fix stage, the re-review of what it changed, reverts, and the narrowed coverage re-check.

        A revert takes back everything the reverted question brought: the bank is merged again from the state
        before the fix with only the kept questions, their images and the conflicts they cite. Restoring only
        the question left a conflict record no question cited (CF-POLIO-28, 261102_02) and images of a
        reverted version in the stimuli list (Q134)."""
        ctx = v3.fix_input(S.bank, findings, targets, S.conflicts, covered_by(S))
        if S.scope:
            ctx['conflict_scope'] = S.scope
        state = _state(S.bank, S.conflicts, S.stimuli, packet)
        value = stages.run(name, ctx, lambda raw, ctx=ctx, state=state: check_stage('fix', raw, ctx, state, out / '.check-render' / name), state)
        before = (copy.deepcopy(S.bank), copy.deepcopy(S.conflicts), copy.deepcopy(S.stimuli))
        before_reviews = {q: S.reviews[q] for q in targets}
        cited = {q.get('conflict_id') for q in value['questions'] if q.get('conflict_id')}
        S.restated.extend({'stage': name, **r} for r in v3.restated(visual.authored(S.bank), S.conflicts, value, cited))
        merged, S.conflicts, changed = v3.merge_fixes(visual.authored(S.bank), S.conflicts, value, targets)
        S.stimuli = [s for s in S.stimuli if s['question_id'] not in set(changed)] + value['visual_stimuli']
        S.bank = visual.render(merged, S.stimuli, packet, S.material)
        again = review_batch(S, stages, review_name, set(changed))
        reverted = [q for q in changed if q in again and v3.worse(before_reviews[q], again[q])]
        kept = [q for q in changed if q not in reverted]
        if reverted and not kept:
            S.bank, S.conflicts, S.stimuli = before
        elif reverted:
            part = v3.fixes_of(value, kept)
            merged, S.conflicts, _ = v3.merge_fixes(visual.authored(before[0]), before[1], part, targets)
            S.stimuli = [s for s in before[2] if s['question_id'] not in set(kept)] + part['visual_stimuli']
            S.bank = visual.render(merged, S.stimuli, packet, S.material)
        for q in changed:
            S.reviews[q] = before_reviews[q] if q in reverted else again.get(q, S.reviews[q])
            S.fixes.append({'question_id': q, 'attempt': S.attempts[q], 'stage': name, 'reverted': q in reverted})
        goals = sorted({did for q in kept for did, r in S.rows.items() if any(e['question_id'] == q for e in r['evidence'])})
        if goals:
            ctx = v3.coverage_input(brief, S.bank, goals, kept)
            got = stages.judged(coverage_name, ctx, lambda raw, ctx=ctx: v3.check_coverage(raw, ctx['goals'], ctx['questions']))
            for r in got['rows']:
                S.rows[r['direction_id']] = _merge_row(S.rows[r['direction_id']], r, kept)
            S.coverage.append((got['rows'], kept, goals))

    def count_attempts(S, targets):
        with st.lock:
            for q in targets:
                S.attempts[q] = S.attempts.get(q, 0) + 1
                ledger['fixAttempts'][q] = max(ledger['fixAttempts'].get(q, 0), S.attempts[q])
            st.save()

    def batch_body(b, batch, S, stages):
        S.reviews.update(review_batch(S, stages, f'v3-review-{b}-0', set(batch)))
        for k in range(v3.FIX_LIMIT):
            code = _bank_findings(S.bank, source_ids, S.attempts)
            targets = [q for q in batch if (v3.needs_fix(S.reviews[q]) or q in code) and S.attempts.get(q, 0) < v3.FIX_LIMIT]
            if not targets:
                break
            count_attempts(S, targets)
            findings = [{**S.reviews[q], 'code_findings': code.get(q, [])} for q in targets]
            fix_round(S, stages, f'v3-fix-{b}-{k}', f'v3-review-{b}-{k + 1}', f'v3-coverage-fix-{b}-{k}', targets, findings)

    def apply_coverage(rows_, got_rows, judged_ids):
        for r in got_rows:
            rows_[r['direction_id']] = _merge_row(rows_[r['direction_id']], r, judged_ids)

    order = [q['question_id'] for q in bank['questions']]
    # attempts are replayed from fixed stage names (v3-fix-<batch>-<k>); the ledger keeps the maximum seen
    S = batches.Batch(bank=bank, conflicts=conflicts, stimuli=stimuli, rows=rows, reviews={}, fixes=[], attempts={},
                      restated=restated, verdicts=ledger['verdictLedger'])
    S = batches.review_phase(st, out, chunks(order, REVIEW_BATCH), S, batch_body, apply_coverage)
    bank, conflicts, stimuli, rows = S.bank, S.conflicts, S.stimuli, S.rows
    reviews, fixes, attempts, restated = S.reviews, S.fixes, S.attempts, S.restated

    # context per conflict record (+ one repair) ------------------------------
    # A verdict reaches the conflict record or question it names: facts not judged consistent are not sent to the
    # medical review, the questions stay. The lecture-wide context gate stopped 134 questions over the wording of
    # three records, and the same records were judged 「확인됨」 and 「오염」 on two runs (261102_02, 2026-11-10).
    def context_judgment(name, conflict_ids=None, question_ids=None):
        nonlocal bank, conflicts
        # A fix may stop citing a conflict an earlier stage added. The record then belongs to no question: it is
        # taken out and recorded instead of stopping the lecture here (P7).
        bank, conflicts, orphans = v3.drop_orphans(bank, conflicts, intake_conflict_ids)
        restated.extend({'stage': name, 'kind': 'orphan_conflict', 'id': cid, 'changed': True} for cid in orphans
                        if not any(r['kind'] == 'orphan_conflict' and r['id'] == cid for r in restated))
        v3.check_integrity(bank, conflicts, stimuli, intake_conflict_ids)
        ctx = v3.context_input(bank, conflicts, conflict_ids, question_ids)
        return st.judged(name, ctx, lambda raw, ctx=ctx: v3.check_context(raw, ctx))
    context_judgments = [context_judgment('v3-context-0')]
    targets = v3.context_repair_targets(bank, context_judgments[0], attempts)
    if targets:
        ledger.setdefault('contextRepairs', [])
        if not ledger['contextRepairs']:
            ledger['contextRepairs'].append({'stage': 'v3-context-0', 'open': v3.context_open(context_judgments[0]), 'targets': targets})
        count_attempts(S, targets)
        notes = v3.context_findings(bank, context_judgments[0], targets)
        code = _bank_findings(bank, source_ids, attempts)
        findings = [{**reviews[q], 'code_findings': [*code.get(q, []), *notes.get(q, [])]} for q in targets]
        S.bank, S.conflicts, S.stimuli = bank, conflicts, stimuli
        fix_round(S, batches.BatchStages(st, S), 'v3-fix-context-0', 'v3-review-context-1', 'v3-coverage-fix-context-0', targets, findings)
        bank, conflicts, stimuli = S.bank, S.conflicts, S.stimuli
        present = {c['conflict_id'] for c in [*bank.get('source_conflicts', []), *conflicts]}
        cited = {q['conflict_id'] for q in bank['questions'] if q.get('conflict_id')} | set(intake_conflict_ids)
        again = sorted(({q['conflict_id'] for q in bank['questions'] if q['question_id'] in set(targets) and q.get('conflict_id')}
                        | (present - {r['conflict_id'] for r in context_judgments[0]['conflicts']})) & cited)
        context_judgments.append(context_judgment('v3-context-1', again, targets))
    context = v3.context_merge(context_judgments[0], context_judgments[1] if len(context_judgments) == 2 else None, bank, conflicts,
                               ledger['contextRepairs'][0]['targets'] if ledger.get('contextRepairs') else ())

    # assembly (before the medical review: whatever it refuses is found before that spend) -------------
    coverage_rows = [rows[d['direction_id']] for t in brief['targets'] for d in t['directions']]
    review_rows = [reviews[q['question_id']] for q in bank['questions']]
    map_check = {k: [x for m in map_checks for x in m[k]] for k in ('relation_checks', 'target_checks', 'direction_checks', 'issues')}
    relation_seen = {}
    for r in map_check['relation_checks']:
        relation_seen.setdefault(r['relation_id'], r)   # a relation judged again for a new goal keeps its first judgment
    map_check['relation_checks'] = list(relation_seen.values())
    summary = ('root-generation/3: coverage, map check, item review and per-conflict context judgments gathered by '
               'studyez_contracts.roots.generation_v3.assessment_raw; no judgment is filled in.')
    raw = v3.assessment_raw(brief, bank, coverage_rows, map_check, review_rows, v3.context_summary(context), summary)
    audit = v2.compile_assessment(brief, bank, envelope(brief, bank, raw))
    reviewed_bank = bank
    snapshot, projection = v2.project_container_concepts(bank)
    importance_proof = None
    if table is not None:
        snapshot, importance_proof = v2.project_importance(snapshot, brief, table)
    doc = v2.make_document(brief, reviewed_bank, audit, revision=packet['revision'], title=packet['title'], exam_date=packet['examDate'],
                           snapshot=snapshot if projection or importance_proof else None,
                           importance=v2.target_importance(brief, table) if importance_proof else None)
    ready_rows = v3.readiness(brief, bank, raw, doc)
    counts = v3.readiness_counts(ready_rows)
    print('── 조립 예행: 목표 ' + str(len(ready_rows)) + '개 중 과제 ' + str(counts.get('ready', 0)) + '개 · 안 된 이유 '
          + json.dumps({k: v for k, v in counts.items() if k != 'ready'}, ensure_ascii=False), flush=True)
    g.write(out / 'readiness.json', {'counts': counts, 'rows': ready_rows})
    v3.require(doc['tasks'], '학습 가능한 과제가 0개입니다. 의학 검토 전에 멈춥니다. 목표별 이유는 readiness.json: '
               + json.dumps({k: v for k, v in counts.items() if k != 'ready'}, ensure_ascii=False))

    # medical (once, medical-final/1) -----------------------------------------
    clinical_input, _ = v3.medical_parts(bank, v3.context_sent(conflicts, context))
    med_ctx = {'title': packet['title'], 'bank': bank, 'clinicalInput': clinical_input, 'medicalFinal': True}
    st.invoke = _medical_batches(invoke, workers=batches.BATCH_WORKERS if st.parallel else 1)
    medical = st.run('medical-0', med_ctx, lambda raw: validate_checks(raw, bank))
    medical_unreviewed = [{'question_id': r['question_id'], 'reason': r['note'][len(v3.UNREVIEWED_NOTE):]}
                          for r in medical['reviews'] if r['note'].startswith(v3.UNREVIEWED_NOTE)]
    st.retire_legacy()

    not_ready = v3.not_ready(brief, coverage_rows, review_rows)
    result = {'brief': brief, 'document': doc, 'sourceAudit': audit, 'medical': medical,
              'validation': validate_bank(snapshot, source_ids), 'manifest': {
                  'pipelineVersion': POLICY, 'inputHash': packet['inputHash'], 'briefHash': document_hash(brief),
                  'bankHash': document_hash(doc['bank_snapshot']), 'model': codex.model_name(model), 'runtimeHash': ledger['identity'],
                  'stages': [{'name': k, **v} for k, v in ledger['stages'].items()],
                  'verdictLedger': ledger['verdictLedger'], 'verdictLedgerHash': document_hash(ledger['verdictLedger']),
                  'addRounds': ledger['addRounds'], 'notReady': not_ready,
                  'offGoalQuestions': [{'question_id': q['question_id'], 'question': q,
                                        'reason': next(d['reason'] for d in out_of_scope if d['question_id'] == q['question_id'])}
                                       for q in off_questions],
                  'rejectedAtIntake': rejected, 'intakeProjection': intake_changes, 'restatedIgnored': restated,
                  **({'intakeClozeUnits': intake_cloze} if intake_cloze else {}),
                  'supplement': supplement, 'supplementPoints': points_doc if supplement else None,
                  'initialBrief': initial_brief, 'initialBank': initial_bank, 'coverage': coverage_rows, 'mapCheck': map_check,
                  'itemReviews': review_rows, 'clinicalContext': context, 'contextJudgments': context_judgments,
                  'medicalUnreviewed': medical_unreviewed, 'readiness': ready_rows, 'clinicalConflicts': conflicts,
                  'visualStimuli': stimuli, 'medicalFinal': True, 'sourceAssessment': raw, 'fixes': fixes,
                  **({'bankProjection': projection} if projection else {}),
                  **({'importanceProjection': importance_proof} if importance_proof else {}),
                  **({'stageResumes': ledger['stageResumes']} if ledger.get('stageResumes') else {}),
                  **({'reviewRetries': ledger['reviewRetries']} if ledger.get('reviewRetries') else {}),
                  **({'contextRepairs': ledger['contextRepairs']} if ledger.get('contextRepairs') else {}),
                  **({'batchPhases': ledger['batchPhases']} if ledger.get('batchPhases') else {}),
                  # map-tree/2: the server re-derives this packet from its request (studyez_contracts.roots.map_tree).
                  **({'derivedPacket': map_tree.public(packet), 'auditOpen': packet['frontStages']['openPoints']}
                     if 'derivedFrom' in packet else {})}}
    v3.validate_result(result, packet)
    g.write(out / 'result.json', result)
    return result
