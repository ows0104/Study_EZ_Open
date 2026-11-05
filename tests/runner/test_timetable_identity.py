import json
import sqlite3
from pathlib import Path

import pytest

from runner import ahead, blocks, filenames

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/timetable/2026_본1_2학기_시간표.json"


def test_moved_topics_keep_existing_ids_in_json_and_sqlite(tmp_path):
    rows = json.loads(SOURCE.read_text(encoding="utf-8"))
    identities = json.loads((ROOT / "data/timetable/identities/2026-2.json").read_text(encoding="utf-8"))
    path = tmp_path / "schedule.db"
    with sqlite3.connect(path) as db:
        db.execute("create table timetable_event (id text, date text, start_time text, slot integer, title text, details text, professor text, category text, course text)")
        db.executemany("insert into timetable_event values (?,?,?,?,?,?,?,?,?)", [
            (r['id'], r['date'], r['startTime'], ahead._slot_from_time(r['startTime']), r['title'],
             r['details'], r['professor'], r['category'], blocks.base_name(r['title'])) for r in rows])
    cells = ahead.read_cells(SOURCE)
    assert cells == ahead.read_cells(path)
    by_title = {c.title: c for c in cells if c.title.startswith('감염과 면역 ')}
    expectations = {
        12: ('261110_01', '2026-11-05', 5, '콜레라'),
        13: ('261106_06', '2026-11-05', 6, '미코플라스마'),
        17: ('261105_06', '2026-11-06', 6, '무산소성세균'),
        22: ('261105_05', '2026-11-10', 1, '렙토스피라'),
        23: ('261113_01', '2026-11-10', 2, '아데노바이러스'),
        30: ('261110_02', '2026-11-13', 1, '헤르페스바이러스'),
        40: ('261119_06', '2026-11-18', 1, '의료관련감염'),
        46: ('261119_07', '2026-11-19', 5, '형성평가'),
        47: ('261118_01', '2026-11-19', 6, '신종 감염병'),
        48: ('261119_05', '2026-11-19', 7, '환경 관리'),
        65: ('261126_05', '2026-11-26', 3, '다양한 알레르기'),
        66: ('261126_03', '2026-11-26', 5, '호산구성'),
    }
    for number, (key, day, slot, topic) in expectations.items():
        c = by_title[f'감염과 면역 {number}']
        assert (c.key, c.date, c.slot) == (key, day, slot)
        assert topic in ' '.join(c.body)
        assert c.as_lecture().key == key
        assert c.as_lecture().date == day
    assert len(identities) == 12
    assert by_title['감염과 면역 59'].professors == ('장윤석',)
    assert by_title['감염과 면역 5'].professors == ()
    keys = [c.key for c in by_title.values()]
    assert len(keys) == len(set(keys))


def test_existing_confirmed_previous_year_pairs_follow_topic():
    cells = {c.title: c for c in ahead.read_cells(SOURCE)}
    pairs = {'261105_05': '251110_02', '261110_01': '251111_01',
             '261110_02': '251111_02', '261119_05': '251120_05'}
    assert pairs[cells['감염과 면역 22'].key] == '251110_02'
    assert pairs[cells['감염과 면역 12'].key] == '251111_01'
    assert pairs[cells['감염과 면역 30'].key] == '251111_02'
    assert pairs[cells['감염과 면역 48'].key] == '251120_05'


def test_unrelated_event_uses_date_key(tmp_path):
    path = tmp_path / 'schedule.json'
    path.write_text(json.dumps([{'id': 'other', 'date': '2026-11-05', 'startTime': '13:00',
                                'title': '다른 과목', 'category': 'lecture'}]), encoding='utf-8')
    assert ahead.read_cells(path)[0].key == '261105_05'


def test_invalid_identity_registry_fails_closed(tmp_path, monkeypatch):
    (tmp_path / 'data/timetable/identities').mkdir(parents=True)
    (tmp_path / 'data/timetable/identities/2026-2.json').write_text('{"event": "bad"}', encoding='utf-8')
    monkeypatch.setattr(blocks, 'REPO_ROOT', tmp_path)
    with pytest.raises(ValueError, match='identities'):
        ahead.read_cells(SOURCE)


@pytest.mark.parametrize('name,expected', [
    ('[261105_05]콜레라, 캄필로박터, 수도모나스(방예지)_학생v1.pdf', '261110_01'),
    ('[261110_01]렙토스피라, 매독균, 보렐리아(김현제)_학생v1.pdf', '261105_05'),
    ('[261105_06]미코플라스마, 클라미디아(김동현)_학생v1.pdf', '261106_06'),
    ('[261106_06]무산소성세균(염진기)_학생v1.pdf', '261105_06'),
    ('[261118_01]의료관련감염(김의석)_학생v1.pdf', '261119_06'),
    ('[261119_06]신종 감염병에 대한 대처와 전망(박상원)_학생v1.pdf', '261118_01'),
    ('[261126_03]호산구성 질환(김세훈)_학생v1.pdf', '261126_03'),
    ('[261126_05]호산구성 질환(김세훈)_학생v1.pdf', '261126_03'),
    ('[261105_05]다른 과목(교수)_학생v1.pdf', '261105_05'),
    ('[251105_05]콜레라, 캄필로박터, 수도모나스(방예지)_학생v1.pdf', '251105_05'),
])
def test_current_notes_keep_topic_identity(name, expected):
    item = filenames.parse(Path(name))
    assert item.key == expected
    assert item.date == f'20{name[1:3]}-{name[3:5]}-{name[5:7]}'
