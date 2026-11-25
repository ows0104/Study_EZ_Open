"""runs/marked-pages.json (docs/changes/2026-11-25-professor-marked-pages): the administrator's marked pages per lecture,
frozen for a new generation (front stages) and for a fill (with the fill record). Synthetic PDFs, no model."""
import copy
import json
import sys
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'quizbank'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner import fill_goals, marked_pages
from runner import root_front as rf
from studyez_contracts.roots import map_tree
from studyez_contracts.roots.automation import packet_hash
import test_root_front_v3 as t
import test_root_generation_v4 as t4

ROW = {'quote': '시험은 오른쪽 위에 햇살 그림이 있는 슬라이드만 열심히 보고 외워두면 된다', 'year': 2026,
       'marker': '슬라이드 오른쪽 위 해 그림', 'pages': [{'source_id': 'S1', 'pages': [2]}],
       'approval': '구현해', 'at': '2026-11-25T19:00:00+09:00'}
VALUE = {'instruction': {'quote': ROW['quote'], 'refs': [], 'year': 2026, 'source': 'admin'},
         'marker': ROW['marker'], 'pages': ROW['pages']}


def runs_with(root, rows, name=marked_pages.FILENAME):
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(json.dumps({'version': 1, 'lectures': rows}, ensure_ascii=False), encoding='utf-8')
    return root


def test_a_record_becomes_the_admins_marked_pages(tmp_path):
    runs = runs_with(tmp_path / 'runs', {'과목/261124_01': ROW})
    assert marked_pages.load(runs) == {'과목/261124_01': VALUE}
    assert marked_pages.load(tmp_path / 'none') == {}


@pytest.mark.parametrize('change', [
    {'quote': ' '}, {'approval': ''}, {'year': '2026'}, {'pages': []}, {'pages': [{'source_id': 'S1', 'pages': [0]}]},
])
def test_a_malformed_record_holds_the_job(tmp_path, change):
    runs = runs_with(tmp_path / 'runs', {'과목/261124_01': {**ROW, **change}})
    with pytest.raises(marked_pages.MarkedError):
        marked_pages.load(runs)


def test_the_record_is_frozen_once(tmp_path):
    runs = runs_with(tmp_path / 'runs', {'과목/261124_01': ROW})
    out = runs / '_root-generation' / 'gid' / 'front'
    assert marked_pages.frozen(out, runs, '과목', '261124_02') is None and not (out / marked_pages.FROZEN).exists()
    assert marked_pages.frozen(out, runs, '과목', '261124_01') == VALUE
    runs_with(runs, {})                                       # a later edit does not change a started run
    assert marked_pages.frozen(out, runs, '과목', '261124_01') == VALUE


def test_a_fill_takes_the_lectures_marked_pages_with_it(tmp_path):
    runs = tmp_path / 'runs'
    fill = {'previousRevision': 'auto-a', 'goals': ['D2'], 'rewrite': [], 'reason': 'r', 'approval': 'a', 'at': 'now'}
    runs_with(runs, {'과목/261124_01': fill}, fill_goals.FILENAME)
    runs_with(runs, {'과목/261124_01': ROW})
    out = runs / '_root-generation' / 'gid'
    out.mkdir(parents=True)
    frozen = json.loads(fill_goals.frozen(out, '과목', '261124_01').read_text(encoding='utf-8'))
    assert frozen == {**fill, 'markedPages': VALUE}


def front(tmp_path, rows):
    p = t.server_packet(tmp_path)
    p.update(pipeline=map_tree.PIPELINE3, sourceAssessmentFormat=map_tree.FORMAT3)
    p['inputHash'] = packet_hash(p)
    runs = tmp_path / 'runs'
    if rows is not None:
        runs_with(runs, {f"{p['subject']}/{p['runId']}": r for r in rows})
    out = runs / '_root-generation' / 'gid' / 'front'
    out.mkdir(parents=True)
    value = rf.Front(p, out, invoke=lambda *a, **k: None)
    value.prepare()
    return value, out


def written_points(out, profile_extra):
    work = out / 'point'
    work.mkdir()
    points = copy.deepcopy(t4.POINTS)
    points['notebook_profile'].update(profile_extra)
    points['points'][0]['point_id'] = 'P001'
    result = work / 'exam-points.json'
    result.write_text(json.dumps(points, ensure_ascii=False), encoding='utf-8')
    return work, result


def test_the_front_puts_the_admins_pages_in_the_point_input_and_over_the_models(tmp_path):
    f, out = front(tmp_path, [ROW])
    assert rf.read(out / 'input.json')['marked_pages'] == VALUE and (out / marked_pages.FROZEN).exists()
    model = {'instruction': {'quote': '다른 말', 'refs': [{'source_id': 'S1', 'pages': [1]}], 'year': 2026, 'source': 'notes'},
             'marker': '', 'pages': [{'source_id': 'S1', 'pages': [1]}]}
    work, result = written_points(out, {'marked_pages': model})
    value, extra = f.accept(work, result, 'point')
    assert value['notebook_profile']['marked_pages'] == VALUE and extra['modelMarkedPages'] == model
    assert rf.read(result)['notebook_profile']['marked_pages'] == VALUE
    assert json.loads((work / 'model-exam-points.json').read_text(encoding='utf-8'))['notebook_profile']['marked_pages'] == model


def test_without_a_record_the_front_is_unchanged(tmp_path):
    f, out = front(tmp_path, None)
    assert 'marked_pages' not in rf.read(out / 'input.json') and not (out / marked_pages.FROZEN).exists()
    work, result = written_points(out, {})
    value, extra = f.accept(work, result, 'point')
    assert 'marked_pages' not in value['notebook_profile'] and 'modelMarkedPages' not in extra


def test_the_models_marked_pages_must_name_pages_of_the_run(tmp_path):
    f, out = front(tmp_path, None)
    model = {'instruction': {'quote': '이 표시만', 'refs': [{'source_id': 'S1', 'pages': [1]}], 'year': 2026, 'source': 'notes'},
             'marker': '', 'pages': [{'source_id': 'S1', 'pages': [9]}]}
    work, result = written_points(out, {'marked_pages': model})
    with pytest.raises(ValueError, match='outside page'):
        f.accept(work, result, 'point')
