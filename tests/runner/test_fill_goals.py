"""runs/fill-goals.json (docs/changes/2026-11-17-fill-recovery): the operator's fill record per lecture."""
import json

import pytest

from runner import fill_goals

ROW = {'previousRevision': 'auto-a', 'goals': ['D2'], 'rewrite': [], 'reason': 'r', 'approval': 'a', 'at': '2026-11-17T09:30:00+09:00'}


def runs(tmp_path, value=None):
    root = tmp_path / 'runs'
    (root / '_root-generation' / 'gid').mkdir(parents=True)
    if value is not None:
        (root / fill_goals.FILENAME).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    return root / '_root-generation' / 'gid'


def test_no_file_or_no_row_gives_nothing(tmp_path):
    assert fill_goals.frozen(runs(tmp_path), '과목', '261116_02') is None
    out = runs(tmp_path / 'b', {'version': 1, 'lectures': {'과목/261116_03': ROW}})
    assert fill_goals.frozen(out, '과목', '261116_02') is None and not (out / fill_goals.FROZEN).exists()


def test_the_row_is_frozen_in_the_run_folder_and_kept(tmp_path):
    out = runs(tmp_path, {'version': 1, 'lectures': {'과목/261116_02': ROW}})
    path = fill_goals.frozen(out, '과목', '261116_02')
    assert json.loads(path.read_text(encoding='utf-8')) == ROW
    # a later edit of the file does not change a run that has started
    (out.parent.parent / fill_goals.FILENAME).write_text(json.dumps({'version': 1, 'lectures': {}}), encoding='utf-8')
    assert json.loads(fill_goals.frozen(out, '과목', '261116_02').read_text(encoding='utf-8')) == ROW


def test_a_malformed_file_holds_the_job(tmp_path):
    for value in ({'version': 2, 'lectures': {}}, {'version': 1, 'lectures': {'과목/261116_02': {**ROW, 'goals': 'D2'}}},
                  {'version': 1, 'lectures': {'과목/261116_02': {k: v for k, v in ROW.items() if k != 'approval'}}}):
        out = runs(tmp_path / str(abs(hash(json.dumps(value)))), value)
        with pytest.raises(fill_goals.FillError):
            fill_goals.frozen(out, '과목', '261116_02')
