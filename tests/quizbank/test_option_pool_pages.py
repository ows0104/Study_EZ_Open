from server.app.bank_validation.pages import cited_pages


def test_pool_candidate_evidence_pages_are_not_lost():
    bank = {"questions": [{"question_id": "Q1", "source_refs": [{"source_id": "S1", "locator": "p1"}],
                          "option_pools": [{"candidates": [{"source_refs": [{"source_id": "S1", "locator": "p3–4"}]}]}]}]}
    assert cited_pages(bank, "S1") == {"Q1": [1, 3, 4]}
