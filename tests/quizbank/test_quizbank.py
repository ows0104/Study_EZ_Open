"""quizbank — 모델을 부르지 않고 잰다. 세션은 전부 가짜로 바꾼다.

픽스처는 261002_02 콜린성 약리학(2)의 실물이다(2026-10-04).

    response_261002_02.md   ChatGPT 응답 (첫 판, 프롬프트가 망가져 있던 때) — 대화창 복사본이라
                            인용 표식은 빠져 있다
    bank_261002_02.json     그것을 Claude 가 정리한 것 — 36문항
"""

import json
from pathlib import Path

import pytest

from quizbank import organize, review, run, session, slides
from quizbank.schema import BANK, schema_errors
from quizbank.validate import validate_bank

FIX = Path(__file__).parent / "fixtures"
RAW = FIX / "response_261002_02.md"


@pytest.fixture
def bank():
    return json.loads((FIX / "bank_261002_02.json").read_text(encoding="utf-8"))


# ── 검증 ──────────────────────────────────────────────────────────

def test_실물_은행은_list_채점단위_셋만_오류다(bank):
    """「목록 중 4개」처럼 후보를 한 줄로 적은 list 셋. 나머지 13건은 2026-10-04 에 경고로 내렸다."""
    v = validate_bank(bank, ["S1", "S2"])
    assert v["errors"] == ["Q009: list는 채점 단위 2–5개", "Q015: list는 채점 단위 2–5개",
                           "Q026: list는 채점 단위 2–5개"]
    assert "C01/mechanism: 계획에 대응하는 문항 누락" in v["warnings"]
    assert "CF-04: 한 자료 안의 충돌" in v["warnings"]
    assert "Q024: 회상 계획에 없는 방향" in v["warnings"]


def test_스키마에_어긋나면_자리를_말한다(bank):
    bank["questions"][0]["format"] = "essay"
    del bank["questions"][1]["answer"]
    errors = schema_errors(bank, BANK)
    assert "$.questions[0].format: 허용 값 basic, cloze, list, ox, mcq, multi_select, matching, sequence" in errors
    assert "$.questions[1].answer: 필수 필드 누락" in errors
    assert validate_bank(bank, ["S1", "S2"])["pass"] is False


def test_선행_문항_순환을_잡는다(bank):
    q = {x["question_id"]: x for x in bank["questions"]}
    q["Q001"]["prerequisites"] = ["Q022"]   # Q022 는 이미 Q001 을 선행으로 둔다
    assert "prerequisite 순환 참조가 있습니다." in validate_bank(bank, ["S1", "S2"])["errors"]


def test_cloze_빈칸과_채점단위_수가_같아야_한다(bank):
    q = next(x for x in bank["questions"] if x["format"] == "cloze")
    q["answer_units"] = q["answer_units"][:1]
    assert any("cloze는" in e for e in validate_bank(bank, ["S1", "S2"])["errors"])


# ── 정리 ──────────────────────────────────────────────────────────

def test_인용_표식과_완료_표시를_걷는다():
    raw = "정답은 X다.fileciteturn0file0L6-L13 끝\n\n**STUDYEZ_BANK_COMPLETE**"
    assert organize.clean_response(raw) == "정답은 X다. 끝"


def test_정리_프롬프트는_응답을_데이터로_싣는다():
    raw = RAW.read_text(encoding="utf-8")
    p = organize.organizer_prompt(raw, {"title": "콜린성", "sources": [{"id": "S1", "kind": "notes_current", "filename": "a.pdf"}]})
    assert "CHATGPT_RESPONSE_DATA" in p and '"S1"' in p
    assert "{{" + "raw}}" not in p and "{{c1}}" in p      # cloze 표기는 그대로, 자리표시는 채워짐
    assert "STUDYEZ_BANK_COMPLETE" not in p.split("CHATGPT_RESPONSE_DATA")[1]


def test_정리는_스키마를_넘겨_세션을_부른다(monkeypatch, bank):
    seen = {}

    def fake(prompt, schema, *, system, label, timeout, model):
        seen.update(schema=schema, label=label)
        return bank, {"seconds": 1}

    monkeypatch.setattr(session, "run_structured", fake)
    out, _ = organize.organize("응답", {"title": "t", "sources": []})
    assert out is bank and seen["schema"] is BANK and seen["label"] == "정리"


# ── 외부지식 검토 ──────────────────────────────────────────────────

def test_검토는_모르는_ID를_버리고_빠진_ID를_남긴다(bank):
    output = {"summary": "s", "reviews": [
        {"question_id": "Q033", "verdict": "wrong", "note": "길항제다", "suggested_answer": "muscarinic antagonist"},
        {"question_id": "Q033", "verdict": "ok", "note": "", "suggested_answer": ""},      # 두 번째는 버린다
        {"question_id": "Q999", "verdict": "ok", "note": "", "suggested_answer": ""},
    ]}
    shaped = review.shape(output, bank)
    assert [r["question_id"] for r in shaped["reviews"]] == ["Q033"]
    assert shaped["counts"] == {"ok": 0, "doubt": 0, "wrong": 1}
    assert len(shaped["missing"]) == 35


def test_검토_프롬프트는_정오만_보게_필드를_줄인다(bank):
    p = review.review_prompt(bank, "콜린성")
    assert '"importance"' not in p.split("QUESTIONS:")[1]
    assert '"conflict_id": "CF-01"' in p


# ── 슬라이드 ──────────────────────────────────────────────────────

@pytest.mark.parametrize("locator,pages", [
    ("p13", [13]), ("p13–14", [13, 14]), ("p11, p18", [11, 18]), ("S1 p4", [4]),
    ("p 7", [7]), ("13쪽", [13]), ("2023 Q11", []), ("p2-p3", [2, 3]), ("p3–40", [3, 40]),
])
def test_쪽_번호를_읽는다(locator, pages):
    assert slides.pages_of(locator) == pages


def test_인용_쪽은_필기_PDF_출처만(bank):
    pages = slides.cited_pages(bank, "S1")
    assert pages["Q002"] == [8, 9]            # p8–9 → 두 장
    assert "Q017" not in pages                # S2(족보)만 인용
    assert pages["Q019"] == [4, 18]           # S1 p18; S1 p4


def test_PDF_쪽을_그리고_없는_쪽을_알린다(tmp_path):
    fitz = pytest.importorskip("fitz")
    pdf = tmp_path / "n.pdf"
    doc = fitz.open()
    for _ in range(3):
        doc.new_page(width=200, height=150)
    doc.save(pdf)
    made, missing = slides.render(pdf, {1, 3, 9}, tmp_path / "s", "261002_02")
    assert [p.name for p in made] == ["261002_02_s001.png", "261002_02_s003.png"]
    assert missing == [9]


# ── 한 명령 ───────────────────────────────────────────────────────

def _fake_sessions(monkeypatch, bank):
    def fake(prompt, schema, *, system, label, timeout, model):
        if label == "정리":
            return bank, {"seconds": 1, "input_tokens": 10, "output_tokens": 5}
        return {"summary": "s", "reviews": [{"question_id": q["question_id"], "verdict": "ok", "note": "",
                                             "suggested_answer": ""} for q in bank["questions"]]}, {"seconds": 1}
    monkeypatch.setattr(session, "run_structured", fake)


def test_검증에_떨어지면_검토와_슬라이드를_건너뛰고_0으로_끝난다(monkeypatch, tmp_path, bank, capsys):
    _fake_sessions(monkeypatch, bank)
    out = tmp_path / "build"
    code = run.main([str(RAW), "--title", "콜린성", "--run-id", "261002_02", "--out", str(out),
                     "--source", "S1|notes_current|a.pdf", "--source", "S2|jokbo|b.md"])
    assert code == 0
    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    assert result["pass"] is False and result["errors"] == 3
    assert not (out / "review.json").exists()
    assert "── 정리\n── 검증\n" in capsys.readouterr().out


def test_통과하면_검토하고_쪽을_모은다(monkeypatch, tmp_path, bank):
    for q in bank["questions"]:                     # list 셋을 고쳐 통과시킨다
        if q["question_id"] in ("Q009", "Q015", "Q026"):
            q["answer_units"] = ["가", "나"]
    _fake_sessions(monkeypatch, bank)
    out = tmp_path / "build"
    (out / "slides").mkdir(parents=True)
    (out / "slides" / "stale.png").write_bytes(b"x")    # 지난 실행의 것 — 지워져야 한다
    result = run.run(RAW, None, "콜린성", "261002_02", [{"id": "S1"}, {"id": "S2"}], out)
    assert result["pass"] is True and result["review"] == {"ok": 36, "doubt": 0, "wrong": 0}
    assert json.loads((out / "pages.json").read_text(encoding="utf-8"))["Q002"] == [8, 9]
    assert not (out / "slides" / "stale.png").exists()
    assert len((out / "usage.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_세션이_죽으면_멈췄다를_찍고_1로_끝난다(monkeypatch, tmp_path, capsys):
    def boom(*a, **k):
        raise session.SessionError("정리: claude 가 1 로 끝났다")
    monkeypatch.setattr(session, "run_structured", boom)
    code = run.main([str(RAW), "--title", "t", "--run-id", "r", "--out", str(tmp_path / "o")])
    assert code == 1
    assert capsys.readouterr().out.strip().splitlines()[-1].startswith("멈췄다 — 정리:")


def test_라벨만_가리키는_정답을_본문으로_맞춘다():
    """261002_02 두 번째 정리에서 matching 4 · sequence 2 문항이 이 모양으로 떨어졌다(2026-10-04)."""
    m = {"question_id": "Q002", "format": "matching", "matching_left": ["L1:M1", "L2:M2"],
         "matching_right": ["R1:PLC 활성화", "R2:Adenylyl cyclase 억제"],
         "answer_pairs": [{"left": "L1", "right": "R1"}, {"left": "L2", "right": "R2"}]}
    s = {"question_id": "Q012", "format": "sequence", "sequence_items": ["A:cAMP 감소", "B:M2 결합"],
         "correct_order": ["B", "A"]}
    ok = {"question_id": "Q003", "format": "matching", "matching_left": ["가", "나"], "matching_right": ["1", "2"],
          "answer_pairs": [{"left": "가", "right": "1"}, {"left": "나", "right": "2"}]}
    bank = {"questions": [m, s, ok]}
    assert organize.tidy_labels(bank) == ["Q002", "Q012"]
    assert m["matching_left"] == ["M1", "M2"] and m["answer_pairs"][1] == {"left": "M2", "right": "Adenylyl cyclase 억제"}
    assert s["sequence_items"] == ["cAMP 감소", "M2 결합"] and s["correct_order"] == ["M2 결합", "cAMP 감소"]
    assert ok["matching_left"] == ["가", "나"]            # 라벨이 없으면 건드리지 않는다
