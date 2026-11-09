"""Shared test defaults."""
import pytest


@pytest.fixture(autouse=True)
def per_round_medical_review(monkeypatch):
    """The fixtures and assertions written before medical-final/1 describe the per-round medical review,
    which ledgers created earlier still follow. Tests of the final-once review opt in
    (tests/quizbank/test_medical_final.py sets MEDICAL_FINAL back to True)."""
    try:
        import quizbank.connection_generate_v2 as g2
    except Exception:  # suites that never import the generator
        return
    monkeypatch.setattr(g2, 'MEDICAL_FINAL', False)
