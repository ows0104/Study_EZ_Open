"""선지(주관식 「선지 보기」·객관식 모드 공용, `root-mcq/2`): 출처 넷·표기 단서 검사·마지막 의학 검토·오답 풀 회전(모델은 가짜).

v1(`root-mcq/1`) 계약 함수는 이미 올라간 v1 asset을 읽기 위해 남아 있어 그 검사도 둔다.
"""
import json

import pytest

from quizbank import jokbo_pool, root_mcq
from studyez_contracts.roots import mcq as contract


def _q(qid, fmt="basic", answer="몸니", units=None, question=None, **extra):
    return {"question_id": qid, "format": fmt, "question": question or f"{qid} 매개체는?", "answer": answer,
            "answer_units": units if units is not None else [answer], "explanation": "해설", "options": [],
            "correct_option_ids": [], "source_refs": [], "sequence_items": [], "correct_order": [], **extra}


def _document():
    return {"revision": "rev-1", "title": "리케치아", "bank_snapshot": {"questions": [
        _q("B1", answer="Fe2+"),
        _q("L1", "list", "몸니, 벼룩", ["몸니", "벼룩"]),
        _q("C1", "cloze", "a", ["Fe2+", "산화"], question="{{c1}} 이온이 {{c2}}된다"),
        _q("C2", "cloze", "Fe2+", ["Fe2+"], question="{Fe2+} 이온"),
        _q("S1", "sequence", "", [], sequence_items=["흡착", "침입", "복제"], correct_order=["흡착", "침입", "복제"]),
        _q("O1", "ox", "O", ["O"]),
        {**_q("M1", "mcq", "A"), "options": [{"id": "A", "text": "x"}, {"id": "B", "text": "y"}], "correct_option_ids": ["A"]},
    ]}}


NO_JOKBO = {k: "" for k in contract.JOKBO_KEYS}


def _w(text="", parts=(), source="made", basis="Fe2+→Fe3+", jokbo=None):
    return {"text": text, "parts": list(parts), "source": source, "basis": basis, "why_tempting": "헷갈림",
            "why_wrong": "틀림", "jokbo": jokbo or NO_JOKBO}


def _good(qid):
    return {
        "B1": [_w("Fe3+"), _w("Cu2+", source="block", basis="Wilson"), _w("Zn2+", source="lecture", basis="다른 균"),
               _w("Mg2+"), _w("Ca2+"), _w("Mn2+", source="jokbo", basis="2022 족보 45번 ②",
                                           jokbo={**NO_JOKBO, "year": "2022", "number": "45", "professor": "김"})],
        "L1": [_w("털진드기", source="block", basis="쯔쯔가무시"), _w("모기", source="block", basis="말라리아"), _w("참진드기")],
        "C1": [_w(parts=["Fe3+", "산화"]), _w(parts=["Fe2+", "환원"]), _w(parts=["Fe3+", "환원"])],
        "C2": [_w("Fe3+"), _w("Cu2+"), _w("Zn2+")],
        "S1": [_w(parts=["침입", "흡착", "복제"]), _w(parts=["흡착", "복제", "침입"])],
    }[qid]


def _fake(write, review=None, seen=None):
    def call(prompt, schema, work, model, label):
        rows = json.loads((work / "input.json").read_text(encoding="utf-8"))
        if "reviews" in schema["properties"]:
            text = json.dumps(rows, ensure_ascii=False)
            for hidden in ("basis", "why_wrong", "why_tempting", "source", "jokbo"):
                assert hidden not in text   # 쓴 쪽의 출처·근거·이유는 검토자에게 주지 않는다
            qs = rows["questions"]
            return (review(qs) if review else {"reviews": [{"question_id": q["question_id"], "invalid": []} for q in qs]}), {}
        if seen is not None:
            seen.append(rows)
        return write(rows), {"seconds": 1.0}
    return call


def _all_good(rows):
    return {"proposals": [{"question_id": q["question_id"], "wrong": _good(q["question_id"]), "skip_reason": ""}
                          for q in rows["questions"]]}


# ── 대상·정답 선지 ──────────────────────────────────────────────────────────

def test_형식별_대상과_정답_선지_cloze는_게시본의_중괄호_빈칸도_센다():
    doc = {q["question_id"]: q for q in _document()["bank_snapshot"]["questions"]}
    assert [qid for qid, q in doc.items() if contract.eligible(q)] == ["B1", "L1", "C1", "C2", "S1"]
    assert contract.blank_count(doc["C2"]) == 1   # 게시된 판의 `{답}` 꼴(2026-11-14 전에는 0으로 세어 cloze가 모두 빠졌다)
    assert contract.blank_count(_q("X", "cloze", question="{HSV-1} 와 {HSV-2}")) == 2
    assert contract.correct_texts(doc["C1"]) == ["Fe2+ / 산화"]
    assert contract.correct_texts(doc["S1"]) == ["흡착 → 침입 → 복제"]


@pytest.mark.parametrize("fmt", ["ox", "mcq"])
def test_자체_선지_형식은_대상이_아니다(fmt):
    doc = {q["question_id"]: q for q in _document()["bank_snapshot"]["questions"]}
    assert not contract.eligible(doc["O1" if fmt == "ox" else "M1"])


# ── 표기 단서(사용자 「4는 문체가 다른 경우 … 영어 vs 한국어」, 「1 적용」) ──────────────

def test_정답과_언어가_다른_오답은_뺀다():
    q = _q("Q", "list", "a", ["Necrotizing bronchitis", "Interstitial pneumonia"])
    assert contract.cue_errors(q, "간질 보존을 동반한 기관지 점액 과다") == ["표기 언어가 정답과 다름"]
    assert contract.cue_errors(q, "Diffuse alveolar damage") == []
    # 한국어 문장 속 영어 용어 하나, 짧은 한국어+약어는 언어가 다른 것이 아니다.
    assert contract.cue_errors(_q("K", answer="바이러스 변이가 많다"), "핵 내 cccDNA가 남는다") == []
    assert contract.cue_errors(_q("T", answer="TSST-1 독소"), "혈중으로 퍼진 균 자체") == []


def test_정답이_한글_영문_병기면_오답도_병기해야_한다():
    q = _q("Q", answer="폐렴사슬알균(S. pneumoniae)")
    assert contract.cue_errors(q, "S. dysgalactiae") == ["표기 방식이 정답과 다름(정답은 한글·영문 병기)"]
    assert contract.cue_errors(q, "고름사슬알균(S. pyogenes)") == []


def test_길이와_단정_표현_단서():
    q = _q("Q", answer="숙주세포에 대사적으로 의존한다")
    assert "길이가 정답과 크게 다름" in contract.cue_errors(q, "독립")
    assert contract.cue_errors(_q("S", answer="EBV"), "Cytomegalovirus") == []   # 짧은 정답은 길이를 보지 않는다
    assert contract.cue_errors(q, "숙주세포 없이 항상 독립적으로 증식한다") == ["오답에만 단정 표현"]
    assert contract.cue_errors(_q("B", answer="항상 숙주세포에 의존한다"), "항상 숙주세포 밖에서 증식한다") == []
    assert contract.cue_errors(_q("A", answer="미호기성 세균"), "절대혐기성 세균") == []   # 용어 속 「절대」는 단정 표현이 아니다


# ── 오답 줄 검사·칸 ─────────────────────────────────────────────────────────

def test_출처·이유·족보_연도번호가_없으면_거절():
    doc = {q["question_id"]: q for q in _document()["bank_snapshot"]["questions"]}
    assert contract.row_errors(doc["B1"], {**_w("Fe3+"), "source": "other"})
    assert contract.row_errors(doc["B1"], {**_w("Fe3+"), "why_tempting": ""})
    assert contract.row_errors(doc["B1"], _w("Fe3+", source="jokbo"))   # 연도·번호 없음
    assert contract.row_errors(doc["S1"], _w(parts=["흡착", "침입", "X"]))
    assert contract.row_errors(doc["C1"], _w(parts=["Fe3+"]))
    assert contract.row_errors(doc["B1"], _w("Fe2+")) == ["정답과 같은 오답"]


def test_오답_하나만_통과해도_칸을_만들고_ID로는_정답을_알_수_없다():
    doc = {q["question_id"]: q for q in _document()["bank_snapshot"]["questions"]}
    entry = contract.entry_v2(doc["B1"], [_w("Fe3+"), _w("Fe3+"), _w("x", source="other")])
    assert [w["text"] for w in entry["wrong"]] == ["Fe3+"]
    assert contract.entry_errors_v2(doc["B1"], entry) == []
    picked = contract.select(doc["B1"], entry, "seed")
    assert len(picked["choices"]) == 2 and all(c["id"].startswith("k") and len(c["id"]) == 9 for c in picked["choices"])
    with pytest.raises(ValueError):
        contract.entry_v2(doc["B1"], [_w("Fe2+")])


# ── 회전(사용자 「5 4-5개 정도 … 괜찮은 오답이 나오는 만큼」) ─────────────────────

def test_같은_씨앗이면_같은_선지_다른_씨앗이면_다른_조합_정답은_늘_전부():
    doc = {q["question_id"]: q for q in _document()["bank_snapshot"]["questions"]}
    entry = contract.entry_v2(doc["B1"], _good("B1"))
    assert len(entry["wrong"]) == 6
    first = contract.select(doc["B1"], entry, "u1|B1|2026-11-14")
    assert first == contract.select(doc["B1"], entry, "u1|B1|2026-11-14")
    assert len(first["choices"]) == 1 + contract.SHOW["basic"]
    combos = {frozenset(c["id"] for c in contract.select(doc["B1"], entry, f"u1|B1|day{d}")["choices"]) for d in range(20)}
    assert len(combos) > 1
    correct = contract.choice_id("B1", "Fe2+")
    assert all(correct in combo for combo in combos)
    assert set(first["notes"]) == {c["id"] for c in first["choices"]} - {correct}
    jokbo = next(w for w in entry["wrong"] if w["source"] == "jokbo")
    assert contract.source_label(jokbo) == "2022 족보 45번"


def test_list는_정답_단위_전부와_오답_4개까지():
    doc = {q["question_id"]: q for q in _document()["bank_snapshot"]["questions"]}
    entry = contract.entry_v2(doc["L1"], _good("L1"))
    picked = contract.select(doc["L1"], entry, "s")
    assert len(picked["correct_ids"]) == 2 and len(picked["choices"]) == 5


# ── 생성기 ──────────────────────────────────────────────────────────────────

def test_모두_통과하면_전부_싣고_v2로_검증된다(tmp_path):
    document, seen = _document(), []
    context = {"block": "감염과 면역", "lectures": [{"title": "포도알균", "facts": ["coagulase"]}]}
    asset = root_mcq.build(document, tmp_path, "261110_03", context=context, call=_fake(_all_good, seen=seen))
    assert asset["schema"] == "root-mcq/2"
    assert sorted(asset["questions"]) == ["B1", "C1", "C2", "L1", "S1"]
    assert asset["counts"]["written"] == 5 and asset["skipped"] == {}
    assert asset["counts"]["sources"]["jokbo"] == 1
    assert seen[0]["block_pool"] == context["lectures"]
    contract.validate_v2(json.loads((tmp_path / "mcq.json").read_text(encoding="utf-8")), document)


def test_표기_단서로_빠진_오답은_기록되고_남은_오답이_없으면_이유를_주고_다시_쓴다(tmp_path):
    document, seen = _document(), []

    def write(rows):
        second = len(seen) > 1
        out = []
        for q in rows["questions"]:
            wrong = _good(q["question_id"])
            if q["question_id"] == "L1" and not second:
                wrong = [_w("Mosquito"), _w("Flea")]   # 정답은 한국어인데 영어 → 모두 빠진다
            out.append({"question_id": q["question_id"], "wrong": wrong, "skip_reason": ""})
        return {"proposals": out}

    asset = root_mcq.build(document, tmp_path, "r", call=_fake(write, seen=seen))
    assert [q["question_id"] for q in seen[1]["questions"]] == ["L1"]
    assert {r["reason"] for r in seen[1]["questions"][0]["previous_rejected"]} == {"표기 언어가 정답과 다름"}
    assert "L1" in asset["questions"] and asset["counts"]["removedByStyle"] == 2


def test_검토가_전부_뺀_문항만_다시_쓰고_일부만_뺀_문항은_남은_오답으로_싣는다(tmp_path):
    document, seen = _document(), []

    def review(qs):
        first = len(seen) == 1
        return {"reviews": [{"question_id": q["question_id"], "invalid": (
            [{"text": t, "reason": "정답일 수 있음"} for t in q["wrong"]] if first and q["question_id"] == "C2"
            else [{"text": "Fe3+", "reason": "불확실"}] if q["question_id"] == "B1" else [])} for q in qs]}

    asset = root_mcq.build(document, tmp_path, "r", call=_fake(_all_good, review, seen))
    assert [q["question_id"] for q in seen[1]["questions"]] == ["C2"]
    assert "Fe3+" not in [w["text"] for w in asset["questions"]["B1"]["wrong"]] and len(asset["questions"]["B1"]["wrong"]) == 5


def test_실패한_묶음은_빠지고_나머지는_싣는다(tmp_path):
    def write(rows):
        raise RuntimeError("끊김")
    asset = root_mcq.build(_document(), tmp_path, "r", call=_fake(write), rounds=1)
    assert asset["questions"] == {} and asset["counts"]["failedBatches"] == 1


def test_족보는_직접_연결_이_강의_다른_강의_순으로_입력에_들어간다():
    item = {"year": "2022", "professor": "김", "number": "45", "answer": "②", "stem": "Fe2+ 이온 매개체는?",
            "options": [{"mark": "①", "text": "Fe3+"}, {"mark": "②", "text": "Fe2+"}]}
    other = {"run_id": "261113_01", "title": "헤르페스", "items": [{**item, "number": "7", "stem": "Fe2+ 매개체는 무엇인가"}]}
    context = {"jokbo": [item], "other_jokbo": [other], "links": {"B1": [("2022", "45")]}}
    document = _document()
    data = root_mcq.batch_input(document, document["bank_snapshot"]["questions"][:1], context, {})
    q = data["questions"][0]
    assert q["linked_jokbo"][0]["number"] == "45" and q["linked_jokbo"][0]["options"] == ["① Fe3+", "② Fe2+"]
    assert q["other_jokbo"][0]["run_id"] == "261113_01" and data["jokbo"][0]["year"] == "2022"


def test_근거_asset의_족보_연결을_연도_번호로_읽는다():
    evidence = {"jokboPages": {"questions": {"H060": {"locators": {"physical PDF p.5": [
        {"year": "2022", "number": "45", "page": 5}, {"year": "2022", "number": "45", "page": 6}]}}}}}
    assert root_mcq.jokbo_links(evidence) == {"H060": [("2022", "45")]}


def test_족보_쪽_글에서_머리_정답_발문_보기를_읽는다():
    text = ("감염과 면역 | 헤르페스바이러스과\n2022 | 김동현 | 45번\n참고 기출 | 원본 p.39\n정답: 원본 표기 기준 | 우선순위: 올해\n5\n정답 2\n"
            "45. 병원체에 감염된 환자의 혈액에서 Atypical lymphocyte 가 관찰되는 병원체는? \n"
            "① Cytomegalovirus \n② Epstein-Barr virus \n③ Varicella-zoster virus")
    item = jokbo_pool.page_item(text)
    assert (item["year"], item["professor"], item["number"], item["answer"]) == ("2022", "김동현", "45", "②")
    assert item["stem"].startswith("병원체에 감염된") and [o["text"] for o in item["options"]] == [
        "Cytomegalovirus", "Epstein-Barr virus", "Varicella-zoster virus"]
    assert jokbo_pool.page_item("머리 없는 쪽") is None


# ── v1(이미 올라간 asset 읽기) ────────────────────────────────────────────────

def _w1(text="", parts=(), kind="subtle"):
    return {"text": text, "parts": list(parts), "kind": kind, "basis": "b", "why_wrong": "틀림"}


def test_v1_칸은_그대로_읽힌다():
    doc = {q["question_id"]: q for q in _document()["bank_snapshot"]["questions"]}
    entry = contract.entry(doc["B1"], [_w1("Fe3+"), _w1("Cu2+", kind="block"), _w1("Zn2+")])
    asset = {"schema": contract.SCHEMA, "revision": "rev-1", "questions": {"B1": entry}, "skipped": {}}
    assert contract.attachable(asset, "rev-1", doc["B1"]) is not None
    assert contract.attachable(asset, "rev-2", doc["B1"]) is None
    assert contract.attachable(asset, "rev-1", {**doc["B1"], "question": "바뀜"}) is None
    assert contract.attachable_v2(asset, "rev-1", doc["B1"]) is None
