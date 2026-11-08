"""Explicit single retry of an independent medical review that omitted question verdicts.

The completed-but-incomplete response is archived with its input and usage; the review input
(the final bank) is unchanged; the stage is then run once more by the normal orchestrator.
No content edit and no correction-budget change. Approved per run by the user.

  python -m runner.root_medical_retry --packet <packet.json> --out <run> --stage medical-2 \
      --expected-identity <ledger identity before the prompt fix> --reason "..."
"""
import argparse
import copy
import json
import shutil
from pathlib import Path
from quizbank import connection_generate as g
from studyez_contracts.roots import generation_v2 as c, document_hash
from studyez_contracts.roots.automation import packet_hash
from . import root_native_json as n

JOURNAL = 'medical.retry.json'
ARCHIVE = '.medical-retry'


def recover(packet, out, *, stage, expected_identity, reason, model=None):
    with g.exclusive({'connection-generation': str(Path(out).resolve())}):
        return _recover(packet, out, stage=stage, expected_identity=expected_identity, reason=reason, model=model)


def _recover(packet, out, *, stage, expected_identity, reason, model=None):
    out = Path(out)
    n.require_unblocked(out)
    old = n.read(out / 'ledger.json')
    n.require(packet_hash(packet) == packet['inputHash'] and old['identity'] == expected_identity
              and old.get('pipelineVersion') == c.POLICY, 'Different medical retry input/runtime')
    n.require(stage.startswith('medical-') and stage in old['stages'] and old['stages'][stage]['status'] == 'failed'
              and [k for k, v in old['stages'].items() if v['status'] == 'failed'] == [stage]
              and not old.get('medicalRetries') and not (out / JOURNAL).exists() and not (out / ARCHIVE).exists()
              and not (out / 'result.json').exists() and reason.strip(), 'Only one failed medical review may be retried')
    entry = old['stages'][stage]
    files = {suffix: out / (stage + suffix) for suffix in ('.input.json', '.raw.json', '.usage.json')}
    n.require(all(p.exists() for p in files.values()) and not (out / (stage + '.json')).exists(), 'Missing failed review archive')
    ctx, raw, usage = (n.read(files[s]) for s in ('.input.json', '.raw.json', '.usage.json'))
    n.require(document_hash(ctx) == entry['inputHash'] and document_hash(raw) == entry['rawOutputHash']
              and document_hash(usage) == entry['usageHash'], 'Changed failed review archive')
    expected = [q['question_id'] for q in ctx['bank']['questions']]
    reviewed = [r['question_id'] for r in raw['reviews']]
    missing = [q for q in expected if q not in set(reviewed)]
    n.require(missing and set(reviewed) <= set(expected) and len(reviewed) == len(set(reviewed)),
              'The rejected review is not an omission of question verdicts')
    for name, other in old['stages'].items():
        if name == stage or other['status'] == 'blocked':
            continue
        n.require(document_hash(n.read(out / (name + '.input.json'))) == other['inputHash']
                  and document_hash(n.read(out / (name + '.json'))) == other['outputHash'], 'Changed reused stage')
        n.validate_stage(out, {'name': name, **other}, model=g.codex.model_name(model))
    current = g.identity(packet, model)
    proof = {'priorLedger': old, 'priorLedgerHash': document_hash(old), 'packetHash': packet['inputHash'],
             'currentRuntimeHash': current, 'reason': reason, 'stage': stage, 'rejectedRawHash': entry['rawOutputHash'],
             'reviewed': reviewed, 'missing': missing, 'toolSha256': n.sha(__file__), 'modelReplay': True}
    row = {'proof': proof, 'proofHash': document_hash(proof)}
    updated = copy.deepcopy(old)
    del updated['stages'][stage]
    updated.update(identity=current, medicalRetries=[row])
    meta = {k: updated.get(k, []) for k in ('renderRecoveries', 'formatRecoveries', 'authoringRecoveries')}
    meta.update(medicalRetries=[row], inputHash=packet['inputHash'], runtimeHash=current, repairRounds=old['repairRounds'])
    c.validate_medical_retries(meta, {k: {'name': k, **v} for k, v in updated['stages'].items()}, pending=True)
    archive = out / ARCHIVE
    archive.mkdir()
    (archive / 'ledger-before.json').write_bytes((out / 'ledger.json').read_bytes())
    (archive / 'recovery.py').write_bytes(Path(__file__).read_bytes())
    for path in files.values():
        shutil.move(str(path), str(archive / path.name))
    g.write(out / JOURNAL, row)
    g.write(out / 'ledger.json', updated)
    return {'stage': stage, 'reviewed': len(reviewed), 'missing': len(missing), 'repairRounds': old['repairRounds'],
            'proofHash': row['proofHash'], 'identity': current, 'next': 'python -m runner.root_native_json (one new review call)'}


def validate_archive(out, row):
    out = Path(out)
    p = row['proof']
    archive = out / ARCHIVE
    n.require(n.read(out / JOURNAL) == row and n.read(archive / 'ledger-before.json') == p['priorLedger']
              and n.sha(archive / 'recovery.py') == p['toolSha256']
              and document_hash(n.read(archive / (p['stage'] + '.raw.json'))) == p['rejectedRawHash'],
              'Changed medical retry archive')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--packet', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--stage', required=True)
    p.add_argument('--expected-identity', required=True)
    p.add_argument('--reason', required=True)
    p.add_argument('--model')
    a = p.parse_args()
    print(json.dumps(recover(n.read(a.packet), a.out, stage=a.stage, expected_identity=a.expected_identity,
                             reason=a.reason, model=a.model), ensure_ascii=False))


if __name__ == '__main__':
    main()
