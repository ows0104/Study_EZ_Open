"""Explicit recovery of one completed source review rejected only for a mixed required_gap
or a relation claimed twice in one question review (generation_v2.normalize_source_review).

The reviewer listed optional directions inside a required_gap (2026-11-08, 261104_02 source-0).
The model's raw review, input and usage stay byte-identical. The original rejection is reproduced
to prove the cause; `generation_v2.split_required_gaps` (required directions stay the gap, optional
ones become an optional_extension) builds the accepted review. No model call, no content edit,
no correction-budget change.

  python -m runner.root_source_gap_recovery --packet <packet.json> --out <run> --stage source-0 \
      --expected-identity <ledger identity> --reason "..."
"""
import argparse
import copy
import json
from pathlib import Path
import jsonschema
from quizbank import connection_generate as g
from studyez_contracts.roots import generation_v2 as c, document_hash
from studyez_contracts.roots.automation import packet_hash
from . import root_native_json as n

JOURNAL = 'source-gap.recovery.json'
ARCHIVE = '.source-gap-recovery'
CAUSES = ('required gaps must reference required directions', 'relation_id: duplicate')


def recover(packet, out, *, stage, expected_identity, reason, model=None):
    with g.exclusive({'connection-generation': str(Path(out).resolve())}):
        return _recover(packet, out, stage=stage, expected_identity=expected_identity, reason=reason, model=model)


def _recover(packet, out, *, stage, expected_identity, reason, model=None):
    out = Path(out)
    n.require_unblocked(out)
    old = n.read(out / 'ledger.json')
    n.require(packet_hash(packet) == packet['inputHash'] and packet.get('sourceAssessmentFormat') == c.VERSION
              and old['identity'] == expected_identity and old.get('pipelineVersion') == c.POLICY,
              'Different source gap recovery input/runtime')
    historical = ({'generate'} if old.get('authoringRecoveries')
                  and old['authoringRecoveries'][0]['proof'].get('mode') == 'brief-repair' else set())
    n.require(stage in ('source-0', 'source-1', 'source-2', 'source-3') and stage in old['stages']
              and old['stages'][stage]['status'] == 'failed'
              and [k for k, v in old['stages'].items() if v['status'] == 'failed' and k not in historical] == [stage]
              and all(v['status'] in ('completed', 'failed', 'blocked') for v in old['stages'].values())
              and not old.get('sourceGapRecoveries')
              and not (out / JOURNAL).exists() and not (out / ARCHIVE).exists()
              and not (out / 'result.json').exists() and not (out / (stage + '.json')).exists(),
              'Only one failed source review may be gap-recovered')
    n.require(reason.strip() and type(old['repairRounds']) is int and 0 <= old['repairRounds'] <= 3, 'Missing reason or invalid budget')
    entry = old['stages'][stage]
    n.require(all(k in entry for k in ('inputHash', 'rawOutputHash', 'usageHash')), 'The source call did not finish')
    ctx = n.read(out / (stage + '.input.json'))
    raw = n.read(out / (stage + '.raw.json'))
    info = n.read(out / (stage + '.usage.json'))
    n.require(document_hash(ctx) == entry['inputHash'] and document_hash(raw) == entry['rawOutputHash']
              and document_hash(info) == entry['usageHash'], 'Changed original call archive')
    n.validate_stage(out, {'name': stage, **entry}, model=g.codex.model_name(model))
    brief, bank = ctx['brief'], ctx['bank']
    n.require(entry.get('clinicalContextHash') == document_hash(ctx['clinical_conflicts']), 'Changed clinical context')
    # Same acceptance as the orchestrator: the schema passes and the compile fails for exactly this cause.
    jsonschema.validate(raw['assessment'], c.source_schema(brief, bank))
    try:
        c.compile_assessment(brief, bank, raw)
        rejection = None
    except Exception as error:  # the reproduced original rejection
        rejection = str(error)
    n.require(rejection is not None and any(cause in rejection for cause in CAUSES),
              'The original review is not rejected for a mixed required_gap or a duplicate relation claim')
    fixed, splits, merges = c.normalize_source_review(brief, raw)
    n.require(splits or merges, 'Nothing to normalise')
    jsonschema.validate(fixed['assessment'], c.source_schema(brief, bank))
    accepted = c.compile_assessment(brief, bank, fixed)
    for name, other in old['stages'].items():
        if name == stage or other['status'] == 'blocked' or name in historical:
            continue
        n.require(document_hash(n.read(out / (name + '.input.json'))) == other['inputHash']
                  and document_hash(n.read(out / (name + '.raw.json'))) == other['rawOutputHash']
                  and document_hash(n.read(out / (name + '.json'))) == other['outputHash'], 'Changed reused stage')
    current = g.identity(packet, model)
    proof = {'priorLedger': old, 'priorLedgerHash': document_hash(old), 'packetHash': packet['inputHash'],
             'currentRuntimeHash': current, 'reason': reason, 'stage': stage, 'rejection': rejection,
             'brief': brief, 'originalRaw': raw, 'splits': splits, 'merges': merges, 'toolSha256': n.sha(__file__), 'modelReplay': False}
    row = {'proof': proof, 'proofHash': document_hash(proof)}
    updated = copy.deepcopy(old)
    updated.update(identity=current, sourceGapRecoveries=[row])
    updated['stages'][stage].update(status='completed', outputHash=document_hash(accepted))
    meta = {'sourceGapRecoveries': [row], 'inputHash': packet['inputHash'], 'runtimeHash': current, 'repairRounds': old['repairRounds']}
    c.validate_source_gap_recoveries(meta, {k: {'name': k, **v} for k, v in updated['stages'].items()})
    archive = out / ARCHIVE
    archive.mkdir()
    (archive / 'ledger-before.json').write_bytes((out / 'ledger.json').read_bytes())
    (archive / 'recovery.py').write_bytes(Path(__file__).read_bytes())
    g.write(archive / 'accepted.raw.json', fixed)
    g.write(out / JOURNAL, row)
    g.write(out / (stage + '.json'), accepted)
    g.write(out / 'ledger.json', updated)
    return {'stage': stage, 'rejection': rejection, 'splits': splits, 'merges': merges, 'repairRounds': old['repairRounds'],
            'modelCalls': 0, 'proofHash': row['proofHash'], 'identity': current}


def validate_archive(out, row):
    """The orchestrator's re-check: the journal, prior ledger and tool bytes are the recorded ones."""
    out = Path(out)
    proof = row['proof']
    archive = out / ARCHIVE
    n.require(n.read(out / JOURNAL) == row and n.read(archive / 'ledger-before.json') == proof['priorLedger']
              and n.sha(archive / 'recovery.py') == proof['toolSha256'], 'Changed source gap recovery archive')


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
