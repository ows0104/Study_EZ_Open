"""Generation cannot silently discard or bypass reviewed option truth pairs."""
from quizbank import organize, review
from server.app.bank_validation.choices import pool_review_identity


def test_old_contracts_remain_old_and_pool_contract_is_bound_to_metadata(monkeypatch):
    lecture = {"title": "강의", "sources": [], "prompt_version": "2.3"}
    assert organize.expected_schema("필수 표 누락", lecture) == "4.2"
    assert organize.expected_schema("", {**lecture, "prompt_version": "2.2"}) == "4.1"
    assert organize.expected_schema("", {**lecture, "prompt_version": "2.0"}) == "4.0"
    prompt = organize.organizer_prompt("## Option Pools\n## Option Pool Candidates", lecture)
    assert "`4.2`" in prompt and "false_explanation" in prompt and "option_pools=[]" in prompt
    monkeypatch.setattr(organize.session, "run_structured", lambda *a, **k: (
        {"build_meta": {"schema_version": "3.0"}, "questions": [], "concepts": []}, {}))
    bank, _ = organize.organize("필수 표 누락", lecture)
    assert bank["build_meta"]["schema_version"] == "4.2"


def test_every_truth_pair_is_reviewed_and_review_is_bound_to_content():
    question = {"question_id": "Q1", "question": "옳은 것은?", "format": "mcq", "correct_option_ids": ["A"],
        "option_pools": [{"pool_id": "P1", "correct_when": "true", "select_count": 2, "candidates": [
            {"candidate_id": "C1", "true_text": "원문의 참 문장", "false_text": "검토할 거짓 문장",
             "true_explanation": "참 근거", "false_explanation": "정정 근거", "source_refs": []}]}]}
    bank = {"source_conflicts": [], "questions": [question]}
    prompt = review.review_prompt(bank, "강의")
    assert "검토할 거짓 문장" in prompt and "정정 근거" in prompt and "모든 풀의 모든 후보" in prompt
    shaped = review.shape({"summary": "", "reviews": [{"question_id": "Q1", "verdict": "ok", "note": "", "suggested_answer": ""}]}, bank)
    proof = shaped["reviews"][0]["option_pool_hash"]
    assert proof == pool_review_identity(question)
    question["option_pools"][0]["candidates"][0]["false_text"] = "변경된 미검토 문장"
    assert proof != pool_review_identity(question)
