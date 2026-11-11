"""Main-Quiz(뿌리 학습) 판의 단답·나열 문항에 「선지 보기」용 선지를 만든다.

문항·판·학습 기록은 읽기만 한다. 판의 `bank_snapshot`에서 선지를 붙일 수 있는 문항을 40개씩 묶어
오답만 받아 오고(`content/prompts/learning-links/choices/write.md`), 계약 검사
(`studyez_contracts/roots/choices.py`)를 통과한 문항만 `root-choices/1` JSON 하나에 담는다.
강의 PDF·족보는 보내지 않는다. 묶음이 실패하면 그 묶음의 문항만 선지 없이 둔다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from studyez_contracts.roots import choices as contract

PROMPT = Path(__file__).resolve().parents[1] / "content/prompts/learning-links/choices/write.md"
BATCH = 40
ATTEMPTS = 2
_STR = {"type": "string"}
PROPOSALS = {
    "type": "object", "additionalProperties": False, "required": ["proposals"],
    "properties": {"proposals": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["question_id", "wrong", "skip_reason"],
        "properties": {"question_id": _STR, "skip_reason": _STR, "wrong": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["text", "why_wrong"],
            "properties": {"text": _STR, "why_wrong": _STR}}}}}}},
}


def _call(prompt: str, schema: dict, work: Path, model: str | None, label: str) -> tuple[dict, dict]:
    from .coverage import _call as call
    return call(prompt, schema, work, model, label)


def batch_input(document: dict, batch: list[dict]) -> dict:
    questions = document["bank_snapshot"]["questions"]
    return {"title": document.get("title", ""), "questions": [{
        "question_id": q["question_id"], "format": q["format"], "question": q["question"], "answer": q["answer"],
        "answer_units": q.get("answer_units", []), "explanation": q.get("explanation", ""),
        "candidate_pool": contract.distractor_pool(questions, q)} for q in batch]}


def accept(batch: list[dict], output: dict) -> tuple[dict, dict]:
    """묶음 결과를 문항마다 검사한다. (통과한 칸, 건너뛴 이유)"""
    rows, entries, skipped = {}, {}, {}
    for row in output.get("proposals", []):
        rows.setdefault(row.get("question_id"), row)  # 같은 문항을 두 번 쓰면 첫 줄만
    for q in batch:
        qid, row = q["question_id"], rows.get(q["question_id"])
        if row is None:
            skipped[qid] = "모델이 이 문항을 쓰지 않음"
        elif not row["wrong"]:
            skipped[qid] = row["skip_reason"].strip() or "모델이 오답을 쓰지 않음"
        else:
            errors = contract.wrong_errors(q, row["wrong"])
            if errors:
                skipped[qid] = "검사 탈락: " + "; ".join(errors)
            else:
                entries[qid] = contract.entry(q, row["wrong"])
    return entries, skipped


def build(document: dict, out: Path, run_id: str, *, model: str | None = None, call=_call) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    targets = [q for q in document["bank_snapshot"]["questions"] if contract.eligible(q)]
    prompt = PROMPT.read_text(encoding="utf-8")
    questions, skipped, usage, failed = {}, {}, [], 0
    batches = [targets[i:i + BATCH] for i in range(0, len(targets), BATCH)]
    for index, batch in enumerate(batches):
        work = out / f"batch-{index}"
        work.mkdir(exist_ok=True)
        data = batch_input(document, batch)
        body = json.dumps(data, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256((prompt + body).encode()).hexdigest()
        (work / "input.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        saved, output = work / "output.json", None
        if saved.exists():  # 같은 입력으로 이미 받은 묶음은 다시 부르지 않는다
            try:
                kept = json.loads(saved.read_text(encoding="utf-8"))
                output = kept["output"] if kept.get("input_sha256") == digest else None
            except (ValueError, KeyError, TypeError):
                output = None
        error = None
        for _attempt in range(ATTEMPTS if output is None else 0):
            try:
                output, info = call(prompt, PROPOSALS, work, model, f"Main-Quiz {run_id} 선지 작성 {index + 1}/{len(batches)}")
                usage.append({"stage": f"choices-{index}", **info})
                saved.write_text(json.dumps({"input_sha256": digest, "output": output}, ensure_ascii=False, indent=2), encoding="utf-8")
                break
            except Exception as cause:  # noqa: BLE001 — 한 묶음의 실패가 다른 묶음·게시를 막지 않는다
                error = cause
        if output is None:
            failed += 1
            skipped.update({q["question_id"]: f"묶음 호출 실패: {error}" for q in batch})
            continue
        entries, missed = accept(batch, output)
        questions.update(entries)
        skipped.update(missed)
    asset = {"schema": contract.SCHEMA, "revision": document["revision"], "createdAt": datetime.now(UTC).isoformat(),
             "counts": {"eligible": len(targets), "written": len(questions), "skipped": len(skipped), "failedBatches": failed},
             "questions": questions, "skipped": skipped}
    contract.validate(asset, document)
    (out / "choices.json").write_text(json.dumps(asset, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "usage.jsonl").open("a", encoding="utf-8") as log:
        for entry in usage:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return asset


def summary(asset: dict) -> str:
    c = asset["counts"]
    return f"선지 대상 {c['eligible']}문항 · 작성 {c['written']} · 건너뜀 {c['skipped']} · 실패 묶음 {c['failedBatches']}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--document", type=Path, required=True, help="root_content 문서 JSON")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model")
    args = ap.parse_args(argv)
    asset = build(json.loads(args.document.read_text(encoding="utf-8")), args.out, args.run_id, model=args.model)
    print(summary(asset), flush=True)
    return 0 if asset["questions"] or not asset["counts"]["eligible"] else 1


if __name__ == "__main__":
    sys.exit(main())
