"""Pages an administrator withheld from one lecture's model input (docs/changes/2026-11-18-root-exclude-pages).

Synthetic PDFs and fake model calls only. No model, server or DB."""
import hashlib
import json
import sys
from pathlib import Path

import fitz
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from quizbank import connection_generate as g
from quizbank import evidence_sources, withheld_pages
from runner import connection_generation as worker
from runner import page_exclusions as px
from runner import root_front as rf
from studyez_contracts.roots.automation import validate_result
from map_tree_fixture import pdf
from test_root_front import GID, Client, fake_codex, server_packet, wire

KEY = 'Synthetic subject/261109_01'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(runs, packet, pages, **over):
    s1 = packet['sources'][0]
    row = {'sources': [{'assetId': str(s1['assetId']), 'sha256': s1['sha256'], 'pages': pages}],
           'reason': 'test', 'approval': '「36~48쪽만 빼자」', 'at': '2026-11-18T19:00:00+09:00', **over}
    runs.mkdir(parents=True, exist_ok=True)
    (runs / px.FILENAME).write_text(json.dumps({'version': 1, 'lectures': {KEY: row}}, ensure_ascii=False), encoding='utf-8')


def texts(path):
    with fitz.open(path) as doc:
        return [page.get_text() for page in doc]


# ------------------------------------------------------------------ the masked view

def test_withheld_pages_are_blank_notice_pages_with_the_original_numbering(tmp_path):
    source = pdf(tmp_path / 'notes.pdf', 4)
    before = source.read_bytes()
    withheld_pages.sidecar(source).write_text(json.dumps({'policy': withheld_pages.POLICY, 'sourceSha256': sha(source), 'pages': [2, 3]}))
    with withheld_pages.document(source) as doc:
        shown = [page.get_text() for page in doc]
    assert len(shown) == 4
    assert 'notes page 1' in shown[0] and 'notes page 4' in shown[3]
    assert all('withheld by the operator' in shown[i] and 'notes page' not in shown[i] for i in (1, 2))
    assert source.read_bytes() == before   # the original copy is never changed
    copy = tmp_path / 'copy.pdf'
    withheld_pages.save_model_copy(source, copy)
    assert len(texts(copy)) == 4 and not any('notes page 2' in t or 'notes page 3' in t for t in texts(copy))


def test_a_source_without_a_sidecar_opens_as_before_and_a_sidecar_for_other_bytes_stops(tmp_path):
    source = pdf(tmp_path / 'notes.pdf', 2)
    assert withheld_pages.pages(source) == frozenset()
    withheld_pages.sidecar(source).write_text(json.dumps({'policy': withheld_pages.POLICY, 'sourceSha256': '0' * 64, 'pages': [1]}))
    with pytest.raises(ValueError, match='other bytes'):
        withheld_pages.pages(source)


def test_generator_and_evidence_material_read_the_withheld_pages_blank(tmp_path):
    source = pdf(tmp_path / 'notes.pdf', 3)
    withheld_pages.sidecar(source).write_text(json.dumps({'policy': withheld_pages.POLICY, 'sourceSha256': sha(source), 'pages': [3]}))
    packet = {'sources': [{'id': 'S1', 'localPath': str(source), 'sizeBytes': source.stat().st_size, 'sha256': sha(source),
                           'filename': 'notes.pdf', 'kind': 'notes_current'}]}
    inventory = g.prepare(packet, tmp_path / 'material')
    text = (tmp_path / 'material' / 'S1.md').read_text(encoding='utf-8')
    assert inventory[0]['page_count'] == 3 and inventory[0]['sha256'] == sha(source)
    assert '## S1 physical PDF page 3\n[Page 3 withheld' in text and 'notes page 3' not in text and 'notes page 2' in text
    assert len(list((tmp_path / 'material').glob('S1-*.png'))) == 3
    own = evidence_sources.prepare(source, tmp_path / 'evidence')
    assert 'notes page 3' not in Path(own['text']).read_text(encoding='utf-8') and len(own['images']) == 3
    assert Path(own['pdf']) != source and not any('notes page 3' in t for t in texts(own['pdf']))
    assert evidence_sources.describe(source)['sourceSha256'] == sha(source)   # evidence still names the original


# ------------------------------------------------------------------ the administrator's record

def test_record_needs_reason_approval_time_and_expands_ranges(tmp_path):
    p = server_packet(tmp_path)
    record(tmp_path / 'runs', p, [1, '3-5'])
    assert px.load(tmp_path / 'runs')[KEY]['sources'][0]['pages'] == [1, 3, 4, 5]
    record(tmp_path / 'runs', p, [1], approval='')
    with pytest.raises(px.PageExclusionError, match='approval'):
        px.load(tmp_path / 'runs')
    record(tmp_path / 'runs', p, ['5-3'])
    with pytest.raises(px.PageExclusionError):
        px.load(tmp_path / 'runs')


def test_freeze_writes_the_sidecar_once_and_keeps_it(tmp_path):
    p = server_packet(tmp_path)   # S1 has 2 pages
    runs, out = tmp_path / 'runs', tmp_path / 'out'
    assert px.freeze(out, p, runs) == {}   # no record: nothing changes
    record(runs, p, [2])
    assert px.freeze(out, p, runs) == {'S1': [2]}
    side = json.loads(withheld_pages.sidecar(Path(p['sources'][0]['localPath'])).read_text(encoding='utf-8'))
    assert side['pages'] == [2] and side['approval'] == '「36~48쪽만 빼자」' and side['sourceSha256'] == p['sources'][0]['sha256']
    record(runs, p, [1])   # a later edit does not move a frozen run
    assert px.freeze(out, p, runs) == {'S1': [2]}


def test_freeze_holds_the_job_when_the_record_does_not_fit_the_request(tmp_path):
    p = server_packet(tmp_path)
    runs, out = tmp_path / 'runs', tmp_path / 'out'
    record(runs, p, [3])
    with pytest.raises(px.PageExclusionError, match='2쪽인데'):
        px.freeze(out, p, runs)
    record(runs, {**p, 'sources': [{**p['sources'][0], 'sha256': 'f' * 64}]}, [1])
    with pytest.raises(px.PageExclusionError, match='요청에 없다'):
        px.freeze(out, p, runs)
    record(runs, p, [1])
    (out / 'front' / 'material').mkdir(parents=True)   # a run that already built its material unmasked
    with pytest.raises(px.PageExclusionError, match='이미 자료를 만든'):
        px.freeze(out, p, runs)


# ------------------------------------------------------------------ front host checks

def test_front_refuses_a_reference_to_a_withheld_page():
    with pytest.raises(ValueError, match='withheld'):
        rf.refs_ok({'source_id': 'S1', 'pages': [1, 3], 'locator': None}, {'S1': 3}, {'S1': [3]})
    rf.refs_ok({'source_id': 'S1', 'pages': [1, 2], 'locator': None}, {'S1': 3}, {'S1': [3]})


# ------------------------------------------------------------------ runner: request → front → generation → publication

def test_a_recorded_lecture_runs_end_to_end_on_the_masked_copies_and_the_server_re_derives_it(tmp_path, monkeypatch):
    (tmp_path / 'src').mkdir()
    p = server_packet(tmp_path / 'src')
    runs = tmp_path / 'runs'
    record(runs, p, [2])
    client = Client(p); commands = []; front_calls = []
    wire(monkeypatch, client, commands, front_calls)
    assert worker.run_generation(client, p['subject'], p['runId'], runs, GID) == 0
    out = runs / '_root-generation' / GID
    source = out / 'source-0.pdf'
    assert sha(source) == p['sources'][0]['sha256']            # the downloaded copy is the original
    assert withheld_pages.sidecar(source).is_file()
    front = json.loads((out / 'front' / 'input.json').read_text(encoding='utf-8'))
    assert front['sources'][0]['withheld_pages'] == [2] and front['sources'][0]['page_count'] == 2
    assert front['sources'][0]['sha256'] == p['sources'][0]['sha256'] and 'withheld_pages' not in front['sources'][1]
    for md in (out / 'front' / 'material' / 'S1.md', out / 'generation' / 'material' / 'S1.md'):
        text = md.read_text(encoding='utf-8')
        assert 'notes page 1' in text and 'notes page 2' not in text and '[Page 2 withheld' in text
    assert not any('notes page 2' in t for t in texts(out / 'front' / 'material' / 'S1.pdf'))
    payload = next(c for c in client.calls if c[0] == 'PUT')[2]
    validate_result(json.loads(json.dumps(payload)), client.packet)   # the server's packet is unchanged
    assert json.loads((out / 'withheld-citations.json').read_text(encoding='utf-8')) == []
