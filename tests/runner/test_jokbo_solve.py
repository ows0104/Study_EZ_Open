"""강의별 족보 풀이 자료 빌더(runner.jokbo_solve). 문항은 지어낸 것이다."""
import json
from pathlib import Path

import pytest

from runner import jokbo_solve as js
from studyez_contracts.jokbo import JokboSolveError, validate_lecture


def _w(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _item(iid, year, answers=(2,), **kw):
    return {"pastExamItemId": iid, "year": year, "number": 1, "stem": f"{iid} 발문",
            "choices": [f"{iid}-{c}" for c in "가나다라마"], "answer": answers[0] if answers else None,
            "answers": list(answers), "verification": "pending", **kw}


def _explain(n=5, **kw):
    return {"text": "해설", "choiceNotes": [f"선지{i}" for i in range(n)],
            "basis": {"kind": "notes", "pages": [3]}, "answerCheck": "agree", **kw}


@pytest.fixture
def env(tmp_path):
    amgi = tmp_path / "amgi"
    px = amgi / "data" / "pastexam"
    sets = [
        {"id": "pes_b_18", "ref": "18", "lectures": [18], "title": "헤모필루스",
         "groups": [{"professors": ["방예지"], "years": ["2025"], "from": 0, "count": 1},
                    {"professors": ["김동현"], "years": ["2022"], "from": 1, "count": 2}],
         "items": [_item("pe_2025_18_001", 2025), _item("pe_2022_18_002", 2022, answers=()),
                   _item("pe_2022_18_003", 2022, answerText="전원정답", answers=())]},
        {"id": "pes_b_25-26", "ref": "25-26", "lectures": [25, 26], "title": "묶음",
         "groups": [{"professors": ["김현제", "조남혁"], "years": ["2025"], "from": 0, "count": 2}],
         "items": [_item("pe_2025_25_001", 2025), _item("pe_2025_25_002", 2025)]},
        {"id": "pes_b_0a", "ref": "0a", "lectures": [], "title": "★ CBL 1. 세균감염",
         "groups": [{"professors": [], "years": ["2025"], "from": 0, "count": 1}],
         "items": [_item("pe_2025_0a_001", 2025)]},
    ]
    for s in sets:
        _w(px / f"{s['id']}.json", s)
    _w(px / "index.json", {"sets": [{"file": f"{s['id']}.json"} for s in sets]})
    _w(amgi / "data" / "lecture-map.json", {"lectures": []})
    figs = amgi / "webapp" / "public" / "pastexam-figures"
    _w(figs / "index.json", {"pe_2025_18_001": [{"file": "pe_2025_18_001.png", "w": 1, "h": 1}]})
    (figs / "pe_2025_18_001.png").write_bytes(b"png")
    tt = tmp_path / "tt.json"
    _w(tt, [
        {"id": "ev18", "date": "2026-11-09", "startTime": "09:00", "title": "감염과 면역 18",
         "details": "미생물학) 헤모필루스\n방예지", "professor": "방예지"},
        {"id": "ev25", "date": "2026-11-11", "startTime": "09:00", "title": "감염과 면역 25",
         "details": "파르보\n김현제", "professor": "김현제"},
        {"id": "ev26", "date": "2026-11-11", "startTime": "10:00", "title": "감염과 면역 26",
         "details": "피코르나\n조남혁", "professor": "조남혁"},
        {"id": "evc1", "date": "2026-11-09", "startTime": "14:00", "title": "감염과 면역 CBL 1",
         "details": "세균 감염", "professor": ""},
    ])
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "[261109_01]헤모필루스(방예지)_필기자v1.pdf").write_bytes(b"")
    root = tmp_path / "root"
    return amgi, root, tt, notes


def _lecture(root, event_id):
    return json.loads((root / js.EDITION / "lectures" / f"{event_id}.json").read_text(encoding="utf-8"))


def test_sections_same_professor_first_and_answers_untouched(env):
    amgi, root, tt, notes = env
    js.build(amgi, root, tt, notes)
    doc = _lecture(root, "ev18")
    validate_lecture(doc)
    assert doc["lecture"]["runId"] == "261109_01"
    assert doc["lecture"]["professorSource"] == "notes"
    assert [s["kind"] for s in doc["sections"]] == ["same", "other"]
    assert doc["sections"][0]["itemIds"] == ["pe_2025_18_001"]
    by_id = {it["id"]: it for it in doc["items"]}
    assert by_id["pe_2025_18_001"]["answers"] == [2]
    assert by_id["pe_2022_18_002"]["answerStatus"] == "missing"
    assert by_id["pe_2022_18_003"]["answerStatus"] == "all-correct"
    assert by_id["pe_2025_18_001"]["figures"][0]["file"] == "pe_2025_18_001.png"
    assert (root / js.EDITION / "figures" / "pe_2025_18_001.png").exists()


def test_explain_is_merged_and_survives_rebuild(env):
    amgi, root, tt, notes = env
    _w(root / "explain" / "pes_b_18.json", {
        "_meta": {"schema": "jokbo-explain/1"},
        "pe_2025_18_001": _explain(),
        "pe_2022_18_002": _explain(answerCheck="no-key", proposedAnswers=[3], caution="추정"),
    })
    js.build(amgi, root, tt, notes)
    js.build(amgi, root, tt, notes)
    by_id = {it["id"]: it for it in _lecture(root, "ev18")["items"]}
    assert by_id["pe_2025_18_001"]["explanation"]["source"] == "studyez"
    assert by_id["pe_2022_18_002"]["explanation"]["proposedAnswers"] == [3]
    assert by_id["pe_2022_18_002"]["answers"] == []  # 추정 답은 정답표가 되지 않는다
    assert (root / "explain" / "pes_b_18.json").exists()


def test_bad_explain_is_dropped_and_reported(env):
    amgi, root, tt, notes = env
    _w(root / "explain" / "pes_b_18.json", {"pe_2025_18_001": _explain(n=3)})
    summary = js.build(amgi, root, tt, notes)
    assert _lecture(root, "ev18")["items"][0]["explanation"] is None
    assert any("해설 무시" in p for p in summary["problems"])


def test_combined_set_split_by_assign(env):
    amgi, root, tt, notes = env
    js.build(amgi, root, tt, notes)
    assert len(_lecture(root, "ev25")["items"]) == 2 == len(_lecture(root, "ev26")["items"])
    _w(root / "assign" / "pes_b_25-26.json", {"pe_2025_25_001": "25", "pe_2025_25_002": ["25", "26"]})
    js.build(amgi, root, tt, notes)
    assert [it["id"] for it in _lecture(root, "ev25")["items"]] == ["pe_2025_25_001", "pe_2025_25_002"]
    assert [it["id"] for it in _lecture(root, "ev26")["items"]] == ["pe_2025_25_002"]
    # 공동 담당은 올해 교수와 한 명만 겹쳐도 같은 교수 구획이다
    assert _lecture(root, "ev26")["sections"][0]["kind"] == "same"


def test_cbl_attaches_by_title_with_unknown_professor(env):
    amgi, root, tt, notes = env
    summary = js.build(amgi, root, tt, notes)
    doc = _lecture(root, "evc1")
    assert doc["lecture"]["professorSource"] == "none"
    assert [s["kind"] for s in doc["sections"]] == ["unknown"]
    assert summary["unattachedSets"] == []


def test_check_reports_missing_and_unassigned(env):
    amgi, root, tt, _ = env
    r = js.check(amgi, root, "pes_b_25-26")
    assert r["missingExplain"] == ["pe_2025_25_001", "pe_2025_25_002"]
    assert r["unassigned"] == ["pe_2025_25_001", "pe_2025_25_002"]


def test_fixes_correct_answer_choices_figures_and_move(env):
    amgi, root, tt, notes = env
    _w(root / "fixes" / "pes_b_18.json", {
        "pe_2025_18_001": {"note": "답안지 오기", "evidence": "족보 p.1", "answers": [3],
                           "figures": [], "choices": ["가", "나", "다", "라"]},
        "pe_2022_18_003": {"note": "다른 강의 문항", "evidence": "족보 p.2", "moveTo": ["25"]},
        "pe_2022_18_002": {"note": "근거 없음"},  # evidence 없음 → 무시
    })
    summary = js.build(amgi, root, tt, notes)
    assert any("교정 무시 pe_2022_18_002" in p for p in summary["problems"])
    doc18 = _lecture(root, "ev18")
    validate_lecture(doc18)
    fixed = {it["id"]: it for it in doc18["items"]}["pe_2025_18_001"]
    assert fixed["answers"] == [3] and fixed["originalAnswers"] == [2]
    assert fixed["verification"] == "corrected" and fixed["correctionEvidence"] == "족보 p.1"
    assert fixed["choices"] == ["가", "나", "다", "라"] and fixed["figures"] == []
    assert "pe_2022_18_003" not in {it["id"] for it in doc18["items"]}
    moved = {it["id"]: it for it in _lecture(root, "ev25")["items"]}["pe_2022_18_003"]
    assert moved["movedFrom"] == "pes_b_18"


def test_duplicates_merge_and_variants_group():
    def it(i, year, stem, choices, answers=(1,), status="key"):
        return {"id": i, "setId": "s", "yearLabel": year, "number": 1, "stem": stem, "choices": list(choices),
                "answers": list(answers), "answerStatus": status}
    base = ["가나다", "라마바", "사아자", "차카타", "파하"]
    entries = [
        (it("a25", "2025", "다음 중 옳은 것은?", base, (2,)), ["갑"]),
        (it("a23", "2023", "다음 중  옳은 것은 ?", list(reversed(base)), (4,)), ["을"]),  # 같은 문제, 선지 순서만 다름
        (it("a21", "2021", "다음 중 옳은 것은?", base[:4] + ["새 선지"], (2,)), ["을"]),   # 선지 하나만 바뀐 변형
        (it("b", "2022", "전혀 다른 발문이다", base), ["을"]),
    ]
    out, review = js.merge_duplicates(entries, ["을"])
    ids = [e[0]["id"] for e in out]
    assert ids == ["a25", "a21", "b"]
    merged = out[0][0]
    assert merged["years"] == ["2025", "2023"] and merged["mergedFrom"][0]["answers"] == [2]
    assert "keyConflict" not in merged
    assert out[0][1] == ["을"]  # 같은 교수가 낸 해가 있으면 같은 교수 구획
    assert merged["variantGroup"] == out[1][0]["variantGroup"]
    assert "variantGroup" not in out[2][0]
    # 사람이 「다른 문제」로 정하면 합치지 않는다
    out2, _ = js.merge_duplicates(entries, ["을"], {frozenset(("a25", "a23")): "distinct"})
    assert [e[0]["id"] for e in out2][:2] == ["a25", "a23"]


def test_duplicate_key_conflict_is_flagged():
    base = ["가나다", "라마바", "사아자", "차카타", "파하"]
    a = {"id": "x1", "setId": "s", "yearLabel": "2025", "number": 1, "stem": "같은 발문", "choices": base, "answers": [1], "answerStatus": "key"}
    b = {**a, "id": "x2", "yearLabel": "2023", "answers": [3]}
    out, review = js.merge_duplicates([(a, ["갑"]), (b, ["갑"])], ["갑"])
    assert out[0][0]["keyConflict"] is True and review[0]["kind"] == "key-conflict"
