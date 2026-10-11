from server.app.bank_validation.pages import cited_pages


def test_pool_candidates_render_all_cited_pdf_pages_without_other_sources():
    question = {"question_id": "Q1", "source_refs": [{"source_id": "S1", "locator": "p2"}],
        "option_pools": [{"candidates": [
            {"source_refs": [{"source_id": "S1", "locator": "p4-p6"}]},
            {"source_refs": [{"source_id": "S1", "locator": "p2"}, {"source_id": "S2", "locator": "p99"}]}]}]}
    assert cited_pages({"questions": [question]}, "S1") == {"Q1": [2, 4, 5, 6]}
    assert cited_pages({"questions": [{"question_id": "old", "source_refs": question["source_refs"]}]}, "S1") == {"old": [2]}
