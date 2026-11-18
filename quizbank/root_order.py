"""Main-Quiz 판의 나열 문항 중 순서가 곧 내용인 문항을 판정한다(`root-order/1`, docs/changes/2026-11-18-ordering-screen).

순서형으로 판정된 문항은 선지 대신 「단계를 순서대로 놓기」 화면으로 푼다. 문항·판·학습 기록·선지 asset은 읽기만 한다.
판의 `bank_snapshot`에서 대상 나열 문항(`studyez_contracts/roots/order.py` `eligible`)만 묶어 Codex에 판정을 받고
(`content/prompts/learning-links/order/judge.md`), 코드가 순열·문항 지문을 검사한 줄만 asset에 담는다.
키워드 규칙은 쓰지 않는다 — 「경로 두 가지」처럼 순서가 없는 나열이 많다(spec R1).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from studyez_contracts.roots import order as contract

from .root_mcq import _call, _stage

PROMPT = Path(__file__).resolve().parents[1] / "content/prompts/learning-links/order/judge.md"
POLICY = "order-judge/2"
BATCH = 60
_STR = {"type": "string"}
JUDGMENTS = {"type": "object", "additionalProperties": False, "required": ["judgments"], "properties": {"judgments": {
    "type": "array", "items": {"type": "object", "additionalProperties": False,
                               "required": ["question_id", "ordered", "order", "basis"],
                               "properties": {"question_id": _STR, "ordered": {"type": "boolean"},
                                              "order": {"type": "array", "items": {"type": "integer"}}, "basis": _STR}}}}}


def batch_input(batch: list[dict]) -> dict:
    return {"questions": [{"question_id": q["question_id"], "question": q.get("question", ""), "answer": q.get("answer", ""),
                           "units": [{"index": i, "text": u} for i, u in enumerate(contract.units(q))],
                           "explanation": q.get("explanation") or ""} for q in batch]}


def apply(batch: list[dict], output: dict) -> tuple[dict, dict, dict]:
    """판정을 문항에 대조한다. 반환: (순서형 칸, 순서형 아님 이유, 코드가 버린 판정 이유)."""
    by_id = {q["question_id"]: q for q in batch}
    rows, rest, dropped = {}, {}, {}
    for got in output.get("judgments") or []:
        qid = got.get("question_id")
        if qid not in by_id or qid in rows or qid in rest:
            continue
        if not got.get("ordered"):
            rest[qid] = str(got.get("basis") or "").strip()
            continue
        try:
            rows[qid] = contract.entry(by_id[qid], got.get("order") or [], got.get("basis") or "")
        except ValueError as cause:
            dropped[qid] = str(cause)
    for qid in by_id:
        if qid not in rows and qid not in rest and qid not in dropped:
            dropped[qid] = "판정 없음"
    return rows, rest, dropped


def build(document: dict, out: Path, *, model: str | None = None, call=_call) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    targets = [q for q in document["bank_snapshot"]["questions"] if contract.eligible(q)]
    prompt = PROMPT.read_text(encoding="utf-8")
    rows, rest, dropped, usage, failed = {}, {}, {}, [], 0
    for start in range(0, len(targets), BATCH):
        batch = targets[start:start + BATCH]
        output, error = _stage(out / f"judge-{start // BATCH}", "judge", prompt, JUDGMENTS, batch_input(batch), model,
                               "순서 맞추기 판정", call, usage)
        if output is None:
            failed += 1
            dropped.update({q["question_id"]: f"판정 호출 실패: {error}" for q in batch})
            continue
        got, other, bad = apply(batch, output)
        rows.update(got)
        rest.update(other)
        dropped.update(bad)
    asset = {"schema": contract.SCHEMA, "revision": document["revision"], "createdAt": datetime.now(UTC).isoformat(),
             "policy": POLICY,
             "counts": {"eligible": len(targets), "ordered": len(rows), "notOrdered": len(rest), "dropped": len(dropped),
                        "failedBatches": failed},
             "questions": rows, "not_ordered": rest, "dropped": dropped}
    contract.validate(asset, document)
    (out / "order.json").write_text(json.dumps(asset, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "usage.jsonl").open("a", encoding="utf-8") as log:
        for entry in usage:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return asset


def summary(asset: dict) -> str:
    c = asset["counts"]
    return (f"순서 판정 대상 {c['eligible']}문항 · 순서형 {c['ordered']} · 아님 {c['notOrdered']} · "
            f"버림 {c['dropped']} · 실패 묶음 {c['failedBatches']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--document", type=Path, required=True, help="root_content 문서 JSON")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model")
    args = ap.parse_args(argv)
    asset = build(json.loads(args.document.read_text(encoding="utf-8")), args.out, model=args.model)
    print(summary(asset), flush=True)
    return 1 if asset["counts"]["failedBatches"] else 0


if __name__ == "__main__":
    sys.exit(main())
