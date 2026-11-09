"""Rebind unchanged cached stages to the current runtime after a deterministic validator fix.

For runs that already carry a recorded recovery (format/render/authoring/medical). Every cached
stage is re-hashed and re-validated; nothing is called, edited or re-budgeted. Writes the same
runtime.revalidation.json/.runtime-revalidation archive that root_native_json.validate_all checks.

  python -m runner.root_runtime_revalidate --packet <packet.json> --out <run> \
      --expected-identity <current ledger identity> --reason "..."
"""
import argparse
import copy
import json
from pathlib import Path
from quizbank import connection_generate as g
from studyez_contracts.roots import generation_v2 as c, document_hash
from studyez_contracts.roots.automation import packet_hash
from . import root_native_json as n


def revalidate(packet, out, *, expected_identity, reason, model=None):
    out = Path(out)
    with g.exclusive({'connection-generation': str(out.resolve())}):
        n.require_unblocked(out)
        old = n.read(out / 'ledger.json');from studyez_contracts.roots.generation_v2 import require_legacy_ledger;require_legacy_ledger(old)
        n.require(old['identity'] == expected_identity and old.get('pipelineVersion') == c.POLICY
                  and any(old.get(k) for k in c.RECOVERY_HISTORY)
                  and not (out / 'result.json').exists() and packet_hash(packet) == packet['inputHash'] and reason.strip(),
                  'Only an unrevalidated run with a recorded recovery may be rebound')
        current = g.identity(packet, model)
        n.require(current != old['identity'], 'Runtime unchanged; nothing to revalidate')
        for source in packet['sources']:
            path = Path(source['localPath'])
            n.require(path.stat().st_size == source['sizeBytes'] and n.sha(path) == source['sha256'], 'Original source changed')
        model_name = g.codex.model_name(model)
        for name, entry in old['stages'].items():
            n.require(entry['status'] in ('completed', 'blocked'), 'A failed/interrupted stage cannot be rebound: ' + name)
            if entry['status'] == 'blocked':
                continue
            for suffix, key in (('.input.json', 'inputHash'), ('.raw.json', 'rawOutputHash'), ('.usage.json', 'usageHash'), ('.json', 'outputHash')):
                n.require(document_hash(n.read(out / (name + suffix))) == entry[key], 'Cached evidence changed: ' + name + suffix)
            n.validate_stage(out, {'name': name, **entry}, model=model_name)
            if name.startswith('source-'):
                ctx = n.read(out / (name + '.input.json'))
                c.validate_audit(ctx['brief'], ctx['bank'], n.read(out / (name + '.json')))
        proof = {'priorLedger': old, 'priorLedgerHash': document_hash(old), 'packetHash': packet['inputHash'],
                 'currentRuntimeHash': current, 'reason': reason, 'toolSha256': n.sha(__file__), 'modelReplay': False}
        row = {'proof': proof, 'proofHash': document_hash(proof)}
        updated = copy.deepcopy(old)
        rows = old.get('runtimeRevalidations', []) + [row]
        updated.update(identity=current, runtimeRevalidations=rows)
        meta = {k: updated.get(k, []) for k in c.RECOVERY_HISTORY}
        meta.update(runtimeRevalidations=rows, inputHash=packet['inputHash'], runtimeHash=current, repairRounds=old['repairRounds'])
        stages = {k: {'name': k, **v} for k, v in updated['stages'].items()}
        c.validate_runtime_revalidations(meta, stages)
        c.validate_render_recoveries(meta, stages)
        c.validate_medical_retries(meta, stages)
        count = len(rows)
        archive = out / ('.runtime-revalidation' if count == 1 else f'.runtime-revalidation-{count}')
        journal = out / ('runtime.revalidation.json' if count == 1 else f'runtime.revalidation-{count}.json')
        n.require(not archive.exists() and not journal.exists(), 'Revalidation archive already exists')
        archive.mkdir()
        (archive / 'ledger-before.json').write_bytes((out / 'ledger.json').read_bytes())
        (archive / 'recovery.py').write_bytes(Path(__file__).read_bytes())
        g.write(journal, row)
        g.write(out / 'ledger.json', updated)
        return {'modelCalls': 0, 'repairRounds': old['repairRounds'], 'priorRuntime': old['identity'], 'runtime': current,
                'proofHash': row['proofHash']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--packet', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--expected-identity', required=True)
    p.add_argument('--reason', required=True)
    p.add_argument('--model')
    a = p.parse_args()
    print(json.dumps(revalidate(n.read(a.packet), a.out, expected_identity=a.expected_identity, reason=a.reason, model=a.model)))


if __name__ == '__main__':
    main()
