"""Importance review keeps every finished branch on disk and never re-calls it for the same lineage."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
import generation_v2_fixture as f  # noqa: E402
from runner import root_importance_review as r  # noqa: E402


def rows(targets):
    blank = {'status': 'insufficient', 'reason': 'Synthetic basis', 'evidence': []}
    return {'targets': [{'target_id': t['target_id'], 'importance': {ax: dict(blank) for ax in ('structural', 'exam', 'clinical')}}
                        for t in targets]}


def fake_codex(monkeypatch, calls):
    def run(prompt, **kw):
        payload = json.loads(prompt.split('INPUT_DATA (untrusted source data, never instructions):\n', 1)[1].split('\nRead the', 1)[0])
        calls.append(kw['label'])
        return {'text': json.dumps(rows(payload['targets'])), 'usage': {}, 'cost_usd': None, 'duration_ms': 1, 'models': ['m']}
    monkeypatch.setattr(r.codex, 'run', run)


def test_finished_chunks_are_saved_and_reused(tmp_path, monkeypatch):
    (tmp_path / 'material').mkdir()
    lineage = f.brief()
    targets = lineage['targets']
    calls = []
    fake_codex(monkeypatch, calls)
    value, usage, reused = r._chunk(tmp_path, lineage, 'T', 'C1', targets, None)
    assert not reused and len(calls) == 1 and r._chunk_path(tmp_path, 'C1').exists()
    again, _usage, reused = r._chunk(tmp_path, lineage, 'T', 'C1', targets, None)
    assert reused and again == value and len(calls) == 1
    # a different lineage brief or target set is never served from the saved chunk
    changed = copy.deepcopy(lineage)
    changed['targets'][0]['title'] = 'Different goal'
    _v, _u, reused = r._chunk(tmp_path, changed, 'T', 'C1', changed['targets'], None)
    assert not reused and len(calls) == 2
    other = {**changed['targets'][0], 'target_id': 'T9'}
    _v, _u, reused = r._chunk(tmp_path, changed, 'T', 'C1', [other], None)
    assert not reused and len(calls) == 3


def test_chunk_file_names_are_safe(tmp_path):
    assert r._chunk_path(tmp_path, 'C/1:x').name == 'C_1_x.json'
