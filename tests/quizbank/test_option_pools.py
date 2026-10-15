"""V1 generation preserves authored pools and binds their medical review."""
from quizbank import organize, review
from server.app.bank_validation.choices import pool_review_identity
from server.app.bank_validation.pool_checks import candidates


def test_v1_contract_is_bound_to_prompt_metadata(monkeypatch):
    lecture = {"title": "강의", "sources": [], "prompt_version": "1.26"}
    assert organize.expected_schema("표 누락", lecture) == "3.2"
    assert organize.expected_schema("", {**lecture, "prompt_version": "1.25"}) == "3.0"
    assert organize.expected_schema("## Option Pools", {"title": "강의", "sources": []}) == "3.2"
    prompt = organize.organizer_prompt("## Option Pools\n## Option Pool Candidates", lecture)
    assert "`3.2`" in prompt and "false_explanation" in prompt and "option_pools=[]" in prompt
    monkeypatch.setattr(organize.session, "run_structured", lambda *a, **k: (
        {"build_meta": {"schema_version": "3.0"}, "questions": [], "concepts": []}, {}))
    bank, _ = organize.organize("表 누락", lecture)
    assert bank["build_meta"]["schema_version"] == "3.2"


def test_review_covers_every_truth_pair_and_is_bound_to_content():
    question = {"question_id": "Q1", "question": "옳은 것은?", "format": "mcq", "correct_option_ids": ["A"],
        "option_pools": [{"pool_id": "P1", "correct_when": "true", "select_count": 2, "candidates": [
            {"candidate_id": "C1", "true_text": "원문의 참 문장", "false_text": "검토할 거짓 문장",
             "true_explanation": "참 근거", "false_explanation": "정정 근거", "source_refs": []}]}]}
    bank = {"source_conflicts": [], "questions": [question]}
    prompt = review.review_prompt(bank, "강의")
    assert "검토할 거짓 문장" in prompt and "정정 근거" in prompt and "모든 풀의 모든 후보" in prompt
    checks = [{**{k: c[k] for k in ('question_id', 'pool_id', 'candidate_id', 'content_hash')},
               'true_verdict': 'ok', 'false_verdict': 'ok', 'criterion_verdict': 'ok',
               'note': '참·거짓의 근거 확인'} for c in candidates(bank)]
    shaped = review.shape({"summary": "", "reviews": [{"question_id": "Q1", "verdict": "ok", "note": "", "suggested_answer": ""}], 'pool_checks': checks}, bank)
    proof = shaped["reviews"][0]["option_pool_hash"]
    assert proof == pool_review_identity(question)
    question["option_pools"][0]["candidates"][0]["false_text"] = "미검토 변경"
    assert proof != pool_review_identity(question)
