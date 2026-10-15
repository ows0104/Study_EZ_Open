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
from quizbank.schema import BANK, schema_errors, without_retired
from quizbank.validate import validate_bank, validate_dropping

FIX = Path(__file__).parent / "fixtures"
RAW = FIX / "response_261002_02.md"


@pytest.fixture
def bank():
    return json.loads((FIX / "bank_261002_02.json").read_text(encoding="utf-8"))


# ── 검증 ──────────────────────────────────────────────────────────

def test_그래프_요약은_선택적이고_전체_제목을_보존한다(bank):
    old_errors = validate_bank(bank, ["S1", "S2"])["errors"]
    original_title = bank["concepts"][0]["title"]
    compatible = without_retired(bank)
    assert compatible["concepts"][0]["graph_title"] == ""
    assert "graph_title" not in bank["concepts"][0]
    bank["concepts"][0]["graph_title"] = "콜린성 수용체"
    assert validate_bank(bank, ["S1", "S2"])["errors"] == old_errors
    assert without_retired(bank)["concepts"][0]["graph_title"] == "콜린성 수용체"
    assert bank["concepts"][0]["title"] == original_title
    bank["concepts"][0]["graph_title"] = 123
    assert "$.concepts[0].graph_title: string 형식이 필요합니다." in validate_bank(bank, ["S1", "S2"])["errors"]


def test_실물_은행은_list_채점단위_셋만_오류다(bank):
    """「목록 중 4개」처럼 후보를 한 줄로 적은 list 셋. 나머지 13건은 2026-10-04 에 경고로 내렸다."""
    v = validate_bank(bank, ["S1", "S2"])
    assert v["errors"] == ["Q009: list는 개별 채점 단위 2개 이상 필요", "Q015: list는 개별 채점 단위 2개 이상 필요",
                           "Q026: list는 개별 채점 단위 2개 이상 필요"]
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


@pytest.mark.parametrize("blank_count", [1, 4, 5, 8])
def test_cloze_고정_상한_없이_빈칸별_정답을_검증한다(bank, blank_count):
    q = next(x for x in bank["questions"] if x["format"] == "cloze")
    q["question"] = " ".join("{{c1}}" for _ in range(blank_count))
    q["answer_units"] = [f"정답{i}" for i in range(blank_count)]
    q["answer"] = " ".join(q["answer_units"])
    assert not any("cloze는" in e for e in validate_bank(bank, ["S1", "S2"])["errors"])
    q["answer_units"].append("빈칸이 없는 정답")
    assert any("cloze는" in e for e in validate_bank(bank, ["S1", "S2"])["errors"])


def test_cloze_빈칸이_없는_문장은_허용하지_않는다(bank):
    q = next(x for x in bank["questions"] if x["format"] == "cloze")
    q["question"] = "빈칸 없는 문장"
    q["answer_units"] = []
    assert any("cloze는" in e for e in validate_bank(bank, ["S1", "S2"])["errors"])


def _fix_lists(bank):
    for q in bank["questions"]:                     # 실물의 list 셋을 고쳐 다른 오류가 없게 한다
        if q["question_id"] in ("Q009", "Q015", "Q026"):
            q["answer_units"] = ["가", "나"]


def test_충돌은_한_문항으로_합쳐도_통과한다(bank):
    """프롬프트 v1.2(2026-10-05 관리자): 충돌은 출처별로 가르지 않고 합쳐 외부 의학지식으로 답을 정한다.
    「[출처 기준] 머리말」·「출처 하나」 규칙이 없어졌다 — 두 출처와 EXT 를 같이 적은 합친 문항이 통과한다."""
    _fix_lists(bank)
    conflict = bank["source_conflicts"][0]
    q = next(x for x in bank["questions"] if not x["conflict_id"] and "[" not in x["question"])
    q["conflict_id"] = conflict["conflict_id"]
    q["source_refs"] = [*conflict["source_refs"], {"source_id": "EXT", "locator": "외부 의학지식"}]
    assert validate_bank(bank, ["S1", "S2"])["errors"] == []


def test_conflict_question_can_cite_additional_nonconflicting_evidence(bank):
    _fix_lists(bank)
    conflict = bank["source_conflicts"][0]
    q = next(x for x in bank["questions"] if x["conflict_id"] == conflict["conflict_id"])
    q["source_refs"].append({"source_id": "S3", "locator": "2023 Q29"})
    assert validate_bank(bank, ["S1", "S2", "S3"])["pass"]
    q["source_refs"] = [{"source_id": "S3", "locator": "2023 Q29"}]
    assert any("충돌 기록과 출처 불일치" in e for e in validate_bank(bank, ["S1", "S2", "S3"])["errors"])
    q["source_refs"].append({"source_id": "missing", "locator": "p.1"})
    assert any("유효한 source_id" in e for e in validate_bank(bank, ["S1", "S2", "S3"])["errors"])


def test_unused_conflict_history_is_preserved_as_a_warning(bank):
    _fix_lists(bank)
    cid = bank["source_conflicts"][0]["conflict_id"]
    for q in bank["questions"]:
        if q["conflict_id"] == cid:
            q["conflict_id"] = ""
    validation = validate_bank(bank, ["S1", "S2"])
    assert validation["pass"], validation
    assert f"{cid}: 연결된 문항이 없는 출처 충돌 기록" in validation["warnings"]
    bank["questions"][0]["conflict_id"] = "missing-conflict"
    assert any("Conflict ID 없음" in e for e in validate_bank(bank, ["S1", "S2"])["errors"])


def test_EXT_출처는_허용하되_출처_요약은_요구하지_않는다(bank):
    _fix_lists(bank)
    bank["questions"][0]["source_refs"].append({"source_id": "EXT", "locator": "외부 의학지식"})
    v = validate_bank(bank, ["S1", "S2"])
    assert v["errors"] == []
    bank["questions"][0]["source_refs"].append({"source_id": "S9", "locator": "p1"})   # 모르는 출처는 여전히 걸린다
    assert any("유효한 source_id" in e for e in validate_bank(bank, ["S1", "S2"])["errors"])


def test_external_refs_need_no_pdf_locator_but_uploaded_sources_do(bank):
    _fix_lists(bank)
    for section in ("concepts", "questions", "source_conflicts"):
        bank[section][0]["source_refs"].append({"source_id": "EXT", "locator": ""})
    assert validate_bank(bank, ["S1", "S2"])["pass"]
    bank["questions"][0]["source_refs"].append({"source_id": "S1", "locator": ""})
    assert any("유효한 source_id" in e for e in validate_bank(bank, ["S1", "S2"])["errors"])


def test_걸린_문항만_빼고_다시_잰다(bank):
    """2026-10-05 관리자 — 「걸린 문항만 빼고 연다」. 실물의 list 셋이 빠지고 나머지 33이 통과한다."""
    kept, v = validate_dropping(bank, ["S1", "S2"])
    assert v["pass"] is True and len(kept["questions"]) == 33
    assert [d["question_id"] for d in v["dropped"]] == ["Q009", "Q015", "Q026"]
    assert v["dropped"][0]["errors"] == ["Q009: list는 개별 채점 단위 2개 이상 필요"]
    assert v["dropped"][0]["question"]["question_id"] == "Q009"   # 관리자가 원문을 본다
    assert v["warnings"][0] == "검증에 걸려 뺀 문항 3개: Q009, Q015, Q026"
    gone = {"Q009", "Q015", "Q026"}
    assert not any(gone & set(q["prerequisites"]) for q in kept["questions"])
    assert len(bank["questions"]) == 36                              # 받은 은행은 그대로


def test_문항_탓이_아닌_오류가_있으면_통째로_막는다(bank):
    bank["concepts"][0]["related_concepts"] = ["C99"]
    kept, v = validate_dropping(bank, ["S1", "S2"])
    assert kept is bank and v["pass"] is False and v["dropped"] == []
    assert "C01: related_concepts 오류" in v["errors"] and "Q009: list는 개별 채점 단위 2개 이상 필요" in v["errors"]


def test_자료_요약과_점검_보고는_없어도_된다(bank):
    """프롬프트 v1.5(2026-10-05): 자료 요약·Quality Audit 보고를 안 받는다. 앱이 읽지 않던 출력이다."""
    _fix_lists(bank)
    bank["source_summary"] = []
    bank["audit_summary"] = {"summary": "", "rejected_candidate_count": 0, "changes": []}
    assert validate_bank(bank, ["S1", "S2"])["errors"] == []


def test_뺀_문항_때문에_기초를_잃은_통합_문항도_뺀다(bank):
    q = {x["question_id"]: x for x in bank["questions"]}
    base = next(x for x in bank["questions"] if x["retrieval_direction"] == "direct" and not x["conflict_id"]
                and "[" not in x["question"])
    top = next(x for x in bank["questions"] if x["retrieval_direction"] == "integration")
    top["prerequisites"] = [base["question_id"]]
    base["conflict_id"] = "CF-없음"                                   # 없는 충돌 ID → 그 문항이 걸린다
    kept, v = validate_dropping(bank, ["S1", "S2"])
    gone = [d["question_id"] for d in v["dropped"]]
    assert v["pass"] is True and base["question_id"] in gone and top["question_id"] in gone
    assert any("integration의 기초 문항 필요" in e for d in v["dropped"] for e in d["errors"])
    assert top["question_id"] not in {x["question_id"] for x in kept["questions"]}
    assert q  # 픽스처가 그대로 읽혔다


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
    assert seen["schema"] is BANK and seen["label"] == "정리"
    # 프롬프트 v1.6 에서 뺀 칸은 옛 응답을 정리해도 남기지 않는다(받은 은행은 그대로).
    assert len(out["questions"]) == len(bank["questions"])
    assert not any(k in q for q in out["questions"] for k in ("concept_difficulty", "cognitive_type", "source_strength"))
    assert not any("rationale" in p for p in out["retrieval_plan"])
    assert "cognitive_type" in bank["questions"][0]


def test_합쳐진_선행_ID_때문에_정상_통합_문항이_빠지지_않는다(monkeypatch, bank):
    _fix_lists(bank)
    top = next(q for q in bank["questions"] if q["retrieval_direction"] == "integration")
    bases = [q["question_id"] for q in bank["questions"] if q["retrieval_direction"] == "direct"][:2]
    top["prerequisites"] = ["; ".join(bases)]
    assert any("잘못된 prerequisite" in e for e in validate_bank(bank, ["S1", "S2"])["errors"])

    monkeypatch.setattr(session, "run_structured", lambda *args, **kwargs: (bank, {}))
    organized, _ = organize.organize("응답", {"title": "t", "sources": []})
    kept, validation = validate_dropping(organized, ["S1", "S2"])
    assert validation["pass"] and validation["dropped"] == []
    assert next(q for q in kept["questions"] if q["question_id"] == top["question_id"])["prerequisites"] == bases
    assert top["prerequisites"] == ["; ".join(bases)]  # 입력 원본은 보존


def test_선행_ID는_전부_확인된_경우에만_분리한다():
    bank = {"questions": [
        {"question_id": "A", "prerequisites": []},
        {"question_id": "B", "prerequisites": []},
        {"question_id": "C", "prerequisites": ["A<br />B", "A"]},
        {"question_id": "D", "prerequisites": ["A; UNKNOWN"]},
        {"question_id": "E", "prerequisites": ["A;B;"]},
        {"question_id": "A;B", "prerequisites": []},
        {"question_id": "F", "prerequisites": ["A;B"]},
    ]}
    assert len(organize.tidy_prerequisites(bank)) == 1
    assert bank["questions"][2]["prerequisites"] == ["A", "B"]
    assert bank["questions"][3]["prerequisites"] == ["A; UNKNOWN"]
    assert bank["questions"][4]["prerequisites"] == ["A;B;"]
    assert bank["questions"][6]["prerequisites"] == ["A;B"]


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
    """문항 하나의 탓이 아닌 오류(회상 계획의 목표 숙련도 범위)가 있으면 걸린 문항을 빼지 않고 통째로 막는다.
    (관련 개념 오류는 정리가 코드로 고치므로 예로 못 쓴다 — organize.tidy_related)"""
    bank["retrieval_plan"][0]["target_mastery"] = 5
    _fake_sessions(monkeypatch, bank)
    out = tmp_path / "build"
    code = run.main([str(RAW), "--title", "콜린성", "--run-id", "261002_02", "--out", str(out),
                     "--source", "S1|notes_current|a.pdf", "--source", "S2|jokbo|b.md"])
    assert code == 0
    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    assert result["pass"] is False and result["errors"] == 4 and result["dropped"] == 0
    assert not (out / "review.json").exists() and not (out / "bank.raw.json").exists()
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


def test_걸린_문항을_빼면_뺀_은행으로_검토하고_원본을_남긴다(monkeypatch, tmp_path, bank):
    _fake_sessions(monkeypatch, bank)
    out = tmp_path / "build"
    result = run.run(RAW, None, "콜린성", "261002_02", [{"id": "S1"}, {"id": "S2"}], out)
    assert result["pass"] is True and result["questions"] == 33 and result["dropped"] == 3
    assert len(json.loads((out / "bank.json").read_text(encoding="utf-8"))["questions"]) == 33
    assert len(json.loads((out / "bank.raw.json").read_text(encoding="utf-8"))["questions"]) == 36
    assert result["review"]["ok"] == 33                             # 뺀 문항은 검토하지 않는다


def test_세션이_죽으면_멈췄다를_찍고_1로_끝난다(monkeypatch, tmp_path, capsys):
    def boom(*a, **k):
        raise session.SessionError("정리: claude 가 1 로 끝났다")
    monkeypatch.setattr(session, "run_structured", boom)
    code = run.main([str(RAW), "--title", "t", "--run-id", "r", "--out", str(tmp_path / "o")])
    assert code == 1
    assert capsys.readouterr().out.strip().splitlines()[-1].startswith("멈췄다 — 정리:")


def test_짝은_꼬리표로_찾는다_글을_줄여_써도():
    """프롬프트 v1.3(2026-10-05): 왼쪽 1·2·3, 오른쪽 A·B·C, 정답 `1. … - A. …`. 261002_03 Q046 처럼 정답 쪽 글을
    줄여 써도 꼬리표로 찾아 보기 글로 맞춘다."""
    q = {"question_id": "Q046", "format": "matching",
         "matching_left": ["1. Amphetamine", "2. Ephedrine"],
         "matching_right": ["A. 과거 식욕저하 효과로 비만에 사용됐으나 중독 문제", "B. 과거 천식에 사용됐으나 대체"],
         "answer_pairs": [{"left": "1. Amphetamine", "right": "A. 과거 비만 사용/중독"},
                          {"left": "2", "right": "B"}]}
    assert organize.tidy_labels({"questions": [q]}) == ["Q046"]
    assert q["matching_left"] == ["Amphetamine", "Ephedrine"]
    assert q["answer_pairs"] == [{"left": "Amphetamine", "right": "과거 식욕저하 효과로 비만에 사용됐으나 중독 문제"},
                                 {"left": "Ephedrine", "right": "과거 천식에 사용됐으나 대체"}]
    bad = {"question_id": "Q9", "format": "matching", "matching_left": ["1. 가"], "matching_right": ["A. 나"],
           "answer_pairs": [{"left": "1. 가", "right": "C. 없는 보기"}]}
    assert organize.tidy_labels({"questions": [bad]}) == [] and bad["matching_left"] == ["1. 가"]   # 못 찾으면 그대로


def test_관련_개념의_범위를_풀고_없는_연결은_뺀다():
    """261002_03 6-sol 응답(2026-10-05): `AD10–AD14` 를 그대로 둔 정리가 은행 전체를 막았다."""
    bank = {"concepts": [{"concept_id": f"AD{n:02d}", "related_concepts": []} for n in range(1, 15)]}
    bank["concepts"][4]["related_concepts"] = ["AD03", "AD10–AD14", "AD99", "AD05", "AD03"]
    bank["concepts"][0]["related_concepts"] = ["AD02-AD03"]
    notes = organize.tidy_related(bank)
    assert bank["concepts"][4]["related_concepts"] == ["AD03", "AD10", "AD11", "AD12", "AD13", "AD14"]
    assert bank["concepts"][0]["related_concepts"] == ["AD02", "AD03"]
    assert any("AD99" in n for n in notes) and any("AD10–AD14" in n for n in notes)


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
