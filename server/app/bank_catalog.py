"""Read-only slide ordering, independent of the study queue and its spacing rules."""
from app.bank_validation.pages import pages_of


def question_pages(question: dict, stored: dict) -> list[int]:
    pages = stored.get(question["question_id"]) or [
        page for ref in question.get("source_refs", []) if ref.get("source_id") == "S1"
        for page in pages_of(ref.get("locator", ""))
    ]
    return sorted({page for page in pages if type(page) is int and page > 0})


def ordered_questions(bank: dict, stored: dict) -> list[tuple[dict, list[int]]]:
    items = [(q, question_pages(q, stored)) for q in bank.get("questions", [])]
    # Python's stable sort retains authored order within a slide. Neither tier,
    # review status, prerequisites nor another source's page can move a card.
    return sorted(items, key=lambda item: item[1][0] if item[1] else float("inf"))
