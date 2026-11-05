from quizbank.connection_report import render_report
from tests.contracts.test_learning_links import synthetic_inputs


def test_report_exposes_provided_tested_gaps_unknown_and_separate_priority_bases():
    review, bank, _ = synthetic_inputs()
    text = render_report(review, bank)
    for value in ("실제 시험: R2", "발문 제공: R1", "부족한 질문: D1", "미확인: D3",
                  "강의 이해: supported", "임상: supported", "시험: insufficient", "세부 목표: T2, T3",
                  "독립 포인트 근거: unverified", "학습률이 아닙니다", "원문 부가 필드"):
        assert value in text
    assert "목표 T1" in text and "목표 T2" in text
    assert "원본 전체 검토를 대체하지 않는 합성 사례" in text
    assert "기존 은행의 검수·충돌 기록" in text and "&quot;pass&quot;: false" in text


def test_authored_markdown_and_html_are_inert_data():
    review, bank, _ = synthetic_inputs()
    bank["questions"][0]["question"] = '[click](https://example.com) <script>bad()</script> | `code`\n# forged heading'
    review["targets"][0]["title"] = "**fake**"
    text = render_report(review, bank)
    assert "<script>" not in text
    assert "[click](https://example.com)" not in text
    assert "&lt;script&gt;" in text
    assert "\\|" in text and "<br>\\# forged heading" in text
    assert "\\*\\*fake\\*\\*" in text


def test_shared_positions_show_one_detailed_target_and_keep_unmapped_relations():
    review, bank, _ = synthetic_inputs()
    review["targets"][0]["concept_ids"].append("D")
    review["relations"].append({**review["relations"][2], "relation_id": "R4"})
    text = render_report(review, bank)
    assert text.count("## 목표 T1:") == 1
    assert "목표 연결 없음 — 검토 필요" in text
