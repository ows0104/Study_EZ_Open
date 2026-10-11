"""외부지식 검토 — 검증을 통과한 문제은행의 정답을 모델의 의학 지식으로 본다.

만들기와 정리는 강의자료에 묶여 있고 고치지 않는다. 이 단계는 일부러 그 반대다:
별도의 눈먼 세션이 모든 정답을 자기 지식으로 보고, 충돌 문항은 어느 쪽이 맞는지 판정한다.
**표시만 한다** — 은행을 고치지 않고 학습도 막지 않는다. 학생은 답을 볼 때 그 아래서 본다.

왜: 261002_02(2026-10-04)의 은행에 망가진 족보 정답표를 사실로 가르치는 카드가 둘 있었다
(Atropine = adrenergic agonist · phase 1 block 은 탈분극이 아니다). 이 검토가 둘 다 wrong 으로
잡았고, 같은 은행에서 둘을 더 잡았다(36문항 · 36초).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from . import session
from .schema import REVIEW, VERDICTS
from server.app.bank_validation.choices import pool_review_identity

PROMPT = Path(__file__).parent / "prompts" / "review.md"
SYSTEM = "You are a meticulous medical fact checker for Korean medical-school exam questions. Answer only with the requested JSON."

# 검토에 보이는 필드. 난이도·중요도는 뺀다 — 정오만 보게 한다.
FIELDS = ("question_id", "concept_id", "format", "question", "answer", "answer_units", "options",
          "correct_option_ids", "matching_left", "matching_right", "answer_pairs", "sequence_items",
          "correct_order", "source_refs", "exam_rationale", "conflict_id", "option_explanations", "option_pools")


def review_prompt(bank: dict, title: str) -> str:
    questions = [{k: q[k] for k in FIELDS if k in q} for q in bank["questions"]]
    fill = {"lecture": json.dumps({"title": title}, ensure_ascii=False),
            "conflicts": json.dumps(bank["source_conflicts"], ensure_ascii=False),
            "questions": json.dumps(questions, ensure_ascii=False)}
    return re.sub(r"\{\{(lecture|conflicts|questions)\}\}", lambda m: fill[m.group(1)],
                  PROMPT.read_text(encoding="utf-8"))


def shape(output: dict, bank: dict) -> dict:
    """모델 출력 → 저장할 꼴. 모르는 ID 는 버리고, 빠진 ID 는 missing 에 남긴다."""
    known = [q["question_id"] for q in bank["questions"]]
    reviews, seen = [], set()
    for r in output["reviews"]:
        if r["question_id"] in known and r["question_id"] not in seen:
            seen.add(r["question_id"])
            question = next(q for q in bank["questions"] if q["question_id"] == r["question_id"])
            reviews.append({**r, **({"option_pool_hash": pool_review_identity(question)} if question.get("option_pools") else {})})
    counts = Counter(r["verdict"] for r in reviews)
    return {"summary": output["summary"], "reviews": reviews,
            "missing": [qid for qid in known if qid not in seen],
            "counts": {v: counts.get(v, 0) for v in VERDICTS},
            "reviewed_at": datetime.now(UTC).isoformat()}


def review(bank: dict, title: str, *, model: str | None = None) -> tuple[dict, dict]:
    output, info = session.run_structured(review_prompt(bank, title), REVIEW, system=SYSTEM,
                                          label="외부지식 검토", timeout=900, model=model)
    return shape(output, bank), info
