"""Explicit recovery of one completed authoring call rejected only for oversized crop PNGs.

The model output, input and usage stay byte-identical. The original 2x crops are re-measured to
prove the failure; the current renderer (scale stepped down until the PNG fits) builds the
accepted bank. No model call, no content edit, no correction-budget change.

  python -m runner.root_render_recovery --packet <packet.json> --out <run> --stage generate \
      --expected-identity <ledger identity before the renderer fix> --reason "..."
"""
import argparse
import copy
import json
from pathlib import Path
import jsonschema
from quizbank import connection_generate as g, connection_visuals as visual
from studyez_contracts.roots import generation_v2 as c, document_hash
from studyez_contracts.roots.automation import packet_hash
from studyez_contracts.roots.media import MAX_IMAGE
from . import root_native_json as n

JOURNAL = 'render.recovery.json'


def oversized(raw, packet):
    """Crops whose original 2x render exceeds the PNG limit (the measured cause of the rejection)."""
    sources = {s['id']: s for s in packet['sources']}
    found = []
    for spec in raw['visual_stimuli']:
        if spec.get('image_id'):
            continue
        body, _w, _h = visual.page_crop(Path(sources[spec['source_id']]['localPath']), spec, scales=(2,))
        if len(body) > MAX_IMAGE:
            found.append({'question_id': spec['question_id'], 'page': spec['page'], 'bytes': len(body)})
    return found


def recover(packet, out, *, stage, expected_identity, reason, model=None):
    with g.exclusive({'connection-generation': str(Path(out).resolve())}):
        return _recover(packet, out, stage=stage, expected_identity=expected_identity, reason=reason, model=model)


def _recover(packet, out, *, stage, expected_identity, reason, model=None):
    out = Path(out)
    n.require_unblocked(out)
    old = n.read(out / 'ledger.json');from studyez_contracts.roots.generation_v2 import require_legacy_ledger;require_legacy_ledger(old)
    n.require(packet_hash(packet) == packet['inputHash'] and packet.get('sourceAssessmentFormat') == c.VERSION
              and old['identity'] == expected_identity and old.get('pipelineVersion') == c.POLICY,
              'Different render recovery input/runtime')
    n.require(stage in ('generate', 'repair-1', 'repair-2', 'repair-3') and stage in old['stages']
              and old['stages'][stage]['status'] == 'failed'
              and [k for k, v in old['stages'].items() if v['status'] == 'failed'] == [stage]
              and all(v['status'] in ('completed', 'failed', 'blocked') for v in old['stages'].values())
              and not any(old.get(k) for k in ('renderRecoveries', 'formatRecoveries', 'authoringRecoveries', 'runtimeRevalidations'))
              and not (out / JOURNAL).exists() and not (out / '.render-recovery').exists()
              and not (out / 'result.json').exists() and not (out / (stage + '.json')).exists(),
              'Only one failed authoring acceptance may be render-recovered')
    n.require(reason.strip() and type(old['repairRounds']) is int and 0 <= old['repairRounds'] <= 3, 'Missing reason or invalid budget')
    for source in packet['sources']:
        path = Path(source['localPath'])
        n.require(path.stat().st_size == source['sizeBytes'] and n.sha(path) == source['sha256'], 'Original PDF/source changed')
    entry = old['stages'][stage]
    ctx = n.read(out / (stage + '.input.json'))
    raw = n.read(out / (stage + '.raw.json'))
    info = n.read(out / (stage + '.usage.json'))
    n.require(document_hash(ctx) == entry['inputHash'] and document_hash(raw) == entry['rawOutputHash']
              and document_hash(info) == entry['usageHash'], 'Changed original call archive')
    # The original native call completed; its receipt/output still match the saved raw output.
    n.validate_stage(out, {'name': stage, **entry}, model=g.codex.model_name(model))
    # Same acceptance as the orchestrator, minus the renderer.
    jsonschema.validate(raw, c.author_schema(ctx.get('parallelAuthoring', False)))
    c.validate_authoring(raw, ctx.get('previousAuthoring'))
    sources = [{k: v for k, v in s.items() if k != 'localPath'} for s in n.read(out / 'normalize.input.json')['sources']]
    c.require(raw['brief']['sources'] == sources and raw['brief']['lecture_id'] == packet['subject'] + '/' + packet['runId'],
              'Different source/lecture')
    if stage == 'generate':
        if ctx['initialBriefErrors']:
            c.validate_initial_correction(ctx['brief'], raw['brief'], raw['map_change_reason'])
        else:
            c.require(raw['brief'] == ctx['brief'], 'Initial authoring must preserve the independent brief')
    measured = oversized(raw, packet)
    n.require(measured, 'No oversized 2x crop: this failure is not a render limit')
    for name, other in old['stages'].items():
        if name == stage or other['status'] == 'blocked':
            continue
        n.require(document_hash(n.read(out / (name + '.input.json'))) == other['inputHash']
                  and document_hash(n.read(out / (name + '.raw.json'))) == other['rawOutputHash']
                  and document_hash(n.read(out / (name + '.json'))) == other['outputHash'], 'Changed reused stage')
    accepted = copy.deepcopy(raw)
    accepted['bank'] = visual.render(accepted['bank'], raw['visual_stimuli'], packet, out / 'material')
    current = g.identity(packet, model)
    proof = {'priorLedger': old, 'priorLedgerHash': document_hash(old), 'packetHash': packet['inputHash'],
             'currentRuntimeHash': current, 'reason': reason, 'stage': stage, 'oversized': measured,
             'toolSha256': n.sha(__file__), 'modelReplay': False}
    row = {'proof': proof, 'proofHash': document_hash(proof)}
    updated = copy.deepcopy(old)
    updated.update(identity=current, renderRecoveries=[row])
    updated['stages'][stage].update(status='completed', outputHash=document_hash(accepted), briefHash=document_hash(raw['brief']))
    meta = {'renderRecoveries': [row], 'inputHash': packet['inputHash'], 'runtimeHash': current, 'repairRounds': old['repairRounds']}
    c.validate_render_recoveries(meta, {k: {'name': k, **v} for k, v in updated['stages'].items()})
    archive = out / '.render-recovery'
    archive.mkdir()
    (archive / 'ledger-before.json').write_bytes((out / 'ledger.json').read_bytes())
    (archive / 'recovery.py').write_bytes(Path(__file__).read_bytes())
    g.write(out / JOURNAL, row)
    g.write(out / (stage + '.json'), accepted)
    g.write(out / 'ledger.json', updated)
    images = [{'question_id': q['question_id'], 'width': s['width'], 'height': s['height']}
              for q in accepted['bank']['questions'] for s in q.get('stimuli', [])]
    return {'stage': stage, 'oversized': measured, 'images': images, 'repairRounds': old['repairRounds'],
            'modelCalls': 0, 'proofHash': row['proofHash'], 'identity': current}


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
