"""Main-Quiz 판의 모든 문항에 「객관식 모드」 선지를 만든다(2026-11-14, docs/changes/2026-11-14-mcq-mode).

문항·판·학습 기록은 읽기만 한다. 판의 `bank_snapshot`에서 basic·list·cloze·sequence 문항을 40개씩 묶어
① 오답만 받아 오고(`content/prompts/learning-links/mcq/write.md`) — 오답은 같은 블록 다른 병원체의 기전(block)이나
   정답의 사소한 부분을 바꾼 것(subtle)만 허용한다(사용자 2026-11-14)
② 그 오답을 독립된 호출로 의학 검토 한 번 받은 뒤(`review.md`)
③ 계약 검사(`studyez_contracts/roots/mcq.py`)를 통과한 문항만 `root-mcq/1` JSON 하나에 담는다.
검토 뒤 오답이 모자란 문항·모델이 건너뛴 문항·실패한 묶음은 뺀 오답과 이유를 주고 한 번 더 쓴다(둘째 회차).
ox·mcq·multi_select는 문항 자체가 선지라 대상이 아니다.
블록 재료: `--block`(같은 과목 다른 강의 판의 짧은 정답들, 러너가 만든다)과 `--sheet`(병원체별 사실·함정 표, 선택).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from studyez_contracts.roots import mcq as contract
from studyez_contracts.roots.choices import normalized

PROMPTS = Path(__file__).resolve().parents[1] / "content/prompts/learning-links/mcq"
PROMPT = PROMPTS / "write.md"
REVIEW_PROMPT = PROMPTS / "review.md"
REVIEW_POLICY = "mcq-medical/1"
BATCH = 40
ATTEMPTS = 2
ROUNDS = 2
WORKERS = 3
_STR = {"type": "string"}
_COUNT = re.compile(r"^(오답 \d|선지 \d)")

WRONG = {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                  "required": ["text", "parts", "kind", "basis", "why_wrong"],
                                  "properties": {"text": _STR, "parts": {"type": "array", "items": _STR},
                                                 "kind": {"type": "string", "enum": list(contract.KINDS)},
                                                 "basis": _STR, "why_wrong": _STR}}}
PROPOSALS = {"type": "object", "additionalProperties": False, "required": ["proposals"], "properties": {"proposals": {
    "type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["question_id", "wrong", "skip_reason"],
                               "properties": {"question_id": _STR, "wrong": WRONG, "skip_reason": _STR}}}}}
REVIEWS = {"type": "object", "additionalProperties": False, "required": ["reviews"], "properties": {"reviews": {
    "type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["question_id", "invalid"],
                               "properties": {"question_id": _STR, "invalid": {"type": "array", "items": {
                                   "type": "object", "additionalProperties": False, "required": ["text", "reason"],
                                   "properties": {"text": _STR, "reason": _STR}}}}}}}}


def _call(prompt: str, schema: dict, work: Path, model: str | None, label: str) -> tuple[dict, dict]:
    from .coverage import _call as call
    return call(prompt, schema, work, model, label)


def batch_input(document: dict, batch: list[dict], context: dict, rejected: dict) -> dict:
    questions = document["bank_snapshot"]["questions"]
    return {"title": document.get("title", ""), "block": context.get("block", ""), "questions": [{
        "question_id": q["question_id"], "format": q["format"], "question": q["question"], "answer": q["answer"],
        "correct": contract.correct_texts(q), "parts_needed": contract.parts_needed(q),
        **({"sequence_items": q.get("sequence_items", [])} if q["format"] == "sequence" else {}),
        "explanation": q.get("explanation", ""), "same_lecture": contract.same_lecture_pool(questions, q),
        "previous_rejected": rejected.get(q["question_id"], [])} for q in batch],
        "block_pool": context.get("lectures", []), "block_sheet": context.get("sheet") or {}}


def review_input(document: dict, drafts: dict, questions: dict) -> dict:
    """검토자에게는 오답을 쓴 쪽의 종류·근거·이유를 주지 않는다."""
    return {"title": document.get("title", ""), "questions": [{
        "question_id": qid, "format": questions[qid]["format"], "question": questions[qid]["question"],
        "correct": contract.correct_texts(questions[qid]), "explanation": questions[qid].get("explanation", ""),
        "wrong": [contract.wrong_text(questions[qid], row) for row in wrong]} for qid, wrong in drafts.items()]}


def _trim(question: dict, wrong: list[dict]) -> list[dict]:
    """빈 오답·중복을 빼고 형식 상한까지만. 넘친 오답 때문에 문항 전체를 버리지 않는다."""
    high = contract.WRONG_RANGE[question["format"]][1]
    seen ={normalized(t) for t in contract.correct_texts(question)}
    kept = []
    for row in wrong:
        key = normalized(contract.wrong_text(question, row))
        own = [e for e in contract.wrong_errors(question, [row]) if not _COUNT.match(e)]
        if key and key not in seen and not own:
            seen.add(key)
            kept.append(row)
    return kept[:high]


def drafts_of(batch: list[dict], output: dict) -> tuple[dict, dict]:
    """묶음 결과를 문항마다 검사한다. (검토에 보낼 오답 초안, 건너뛴 이유)"""
    rows, drafts, skipped = {}, {}, {}
    for row in output.get("proposals", []):
        rows.setdefault(row.get("question_id"), row)
    for q in batch:
        qid, row = q["question_id"], rows.get(q["question_id"])
        if row is None:
            skipped[qid] = "모델이 이 문항을 쓰지 않음"
        elif not row["wrong"]:
            skipped[qid] = row["skip_reason"].strip() or "모델이 오답을 쓰지 않음"
        else:
            wrong = _trim(q, row["wrong"])
            errors = contract.wrong_errors(q, wrong)
            if errors:
                skipped[qid] = "검사 탈락: " + "; ".join(errors)
            else:
                drafts[qid] = wrong
    return drafts, skipped


def apply_review(questions: dict, drafts: dict, output: dict) -> tuple[dict, dict, dict, dict]:
    """의학 검토가 지적한 오답을 뺀다. (통과한 칸, 건너뛴 이유, 문항별 검토 기록, 문항별 뺀 오답)"""
    reviews, entries, skipped, record, rejected = {}, {}, {}, {}, {}
    for row in output.get("reviews", []):
        reviews.setdefault(row.get("question_id"), row)
    for qid, wrong in drafts.items():
        q = questions[qid]
        row = reviews.get(qid)
        if row is None:
            skipped[qid] = "의학 검토를 받지 못함"
            continue
        invalid = {normalized(r["text"]): r["reason"].strip() for r in row["invalid"]}
        removed = [{"text": contract.wrong_text(q, w), "reason": invalid[normalized(contract.wrong_text(q, w))]}
                   for w in wrong if normalized(contract.wrong_text(q, w)) in invalid]
        kept = [w for w in wrong if normalized(contract.wrong_text(q, w)) not in invalid]
        errors = contract.wrong_errors(q, kept)
        record[qid] = {"removed": removed, "kept": len(kept)}
        if errors:
            skipped[qid] = "의학 검토 뒤 오답 부족: " + "; ".join(f"{r['text']}({r['reason']})" for r in removed)
            rejected[qid] = removed
        else:
            entries[qid] = contract.entry(q, kept)
    return entries, skipped, record, rejected


def _stage(work: Path, name: str, prompt: str, schema: dict, data: dict, model: str | None, label: str, call, usage: list):
    """입력을 쓰고 한 번 부른다(실패하면 한 번 더). 같은 입력으로 이미 받은 답은 다시 부르지 않는다."""
    work.mkdir(parents=True, exist_ok=True)
    body = json.dumps(data, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256((prompt + body).encode()).hexdigest()
    (work / "input.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    saved = work / "output.json"
    if saved.exists():
        try:
            kept = json.loads(saved.read_text(encoding="utf-8"))
            if kept.get("input_sha256") == digest:
                return kept["output"], None
        except (ValueError, KeyError, TypeError):
            pass
    error = None
    for _attempt in range(ATTEMPTS):
        try:
            output, info = call(prompt, schema, work, model, label)
            usage.append({"stage": name, **info})
            saved.write_text(json.dumps({"input_sha256": digest, "output": output}, ensure_ascii=False, indent=2), encoding="utf-8")
            return output, None
        except Exception as cause:  # noqa: BLE001 — 한 묶음의 실패가 다른 묶음을 막지 않는다
            error = cause
    return None, error


def _batch(document: dict, by_id: dict, batch: list[dict], work: Path, label: str, context: dict, rejected: dict,
           prompts: tuple[str, str], model: str | None, call) -> dict:
    """묶음 하나: 작성 → 의학 검토 → 반영."""
    prompt, review_prompt = prompts
    got = {"questions": {}, "skipped": {}, "reviewed": {}, "rejected": {}, "failed": 0, "usage": []}
    output, error = _stage(work, "mcq-write", prompt, PROPOSALS, batch_input(document, batch, context, rejected), model,
                           f"{label} 작성", call, got["usage"])
    if output is None:
        got["failed"] = 1
        got["skipped"].update({q["question_id"]: f"묶음 호출 실패: {error}" for q in batch})
        return got
    drafts, missed = drafts_of(batch, output)
    got["skipped"].update(missed)
    if not drafts:
        return got
    verdicts, error = _stage(work / "review", "mcq-review", review_prompt, REVIEWS, review_input(document, drafts, by_id),
                             model, f"{label} 의학 검토", call, got["usage"])
    if verdicts is None:
        got["failed"] = 1
        got["skipped"].update({qid: f"의학 검토 호출 실패: {error}" for qid in drafts})
        return got
    entries, missed, record, removed = apply_review(by_id, drafts, verdicts)
    got["questions"].update(entries)
    got["skipped"].update(missed)
    got["reviewed"].update(record)
    got["rejected"].update(removed)
    return got


def _round(document, by_id, targets, out: Path, run_id: str, number: int, context, rejected, prompts, model, call):
    batches = [targets[i:i + BATCH] for i in range(0, len(targets), BATCH)]
    if not batches:
        return []
    with ThreadPoolExecutor(max_workers=max(1, min(WORKERS, len(batches)))) as pool:
        futures = [pool.submit(_batch, document, by_id, batch, out / f"round-{number}" / f"batch-{index}",
                               f"Main-Quiz {run_id} 객관식 {number}회차 {index + 1}/{len(batches)}",
                               context, rejected, prompts, model, call) for index, batch in enumerate(batches)]
        return [f.result() for f in futures]


def build(document: dict, out: Path, run_id: str, *, context: dict | None = None, model: str | None = None,
          call=_call, rounds: int = ROUNDS) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    context = context or {}
    by_id = {q["question_id"]: q for q in document["bank_snapshot"]["questions"]}
    targets = [q for q in by_id.values() if contract.eligible(q)]
    prompts = (PROMPT.read_text(encoding="utf-8"), REVIEW_PROMPT.read_text(encoding="utf-8"))
    questions, skipped, usage, reviewed, failed, rejected = {}, {}, [], {}, 0, {}
    pending = targets
    for number in range(1, max(1, rounds) + 1):
        results = _round(document, by_id, pending, out, run_id, number, context, rejected, prompts, model, call)
        skipped = {}
        failed = 0
        for got in results:   # 묶음 순서로 모은다
            questions.update(got["questions"])
            skipped.update(got["skipped"])
            reviewed.update(got["reviewed"])
            usage.extend(got["usage"])
            failed += got["failed"]
            for qid, removed in got["rejected"].items():
                rejected[qid] = [*rejected.get(qid, []), *removed]
        pending = [by_id[qid] for qid in skipped if qid in by_id and qid not in questions]
        if not pending:
            break
    asset = {"schema": contract.SCHEMA, "revision": document["revision"], "createdAt": datetime.now(UTC).isoformat(),
             "counts": {"eligible": len(targets), "written": len(questions), "skipped": len(skipped), "failedBatches": failed,
                        "removedByReview": sum(len(r["removed"]) for r in reviewed.values())},
             "medicalReview": {"policy": REVIEW_POLICY, "questions": reviewed},
             "questions": questions, "skipped": skipped}
    contract.validate(asset, document)
    (out / "mcq.json").write_text(json.dumps(asset, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "usage.jsonl").open("a", encoding="utf-8") as log:
        for entry in usage:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return asset


def summary(asset: dict) -> str:
    c = asset["counts"]
    return (f"객관식 대상 {c['eligible']}문항 · 작성 {c['written']} · 건너뜀 {c['skipped']} · "
            f"의학 검토가 뺀 오답 {c['removedByReview']} · 실패 묶음 {c['failedBatches']}")


def load_context(block: Path | None, sheet: Path | None, own_run_id: str) -> dict:
    """블록 재료. 자기 강의는 뺀다."""
    context: dict = {}
    if block:
        data = json.loads(block.read_text(encoding="utf-8"))
        context["block"] = data.get("subject", "")
        context["lectures"] = [{"title": row.get("title", ""), "facts": row.get("facts", [])}
                               for row in data.get("lectures", []) if row.get("run_id") != own_run_id]
    if sheet and sheet.exists():
        context["sheet"] = json.loads(sheet.read_text(encoding="utf-8"))
    return context


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--document", type=Path, required=True, help="root_content 문서 JSON")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--block", type=Path, help="같은 블록 다른 강의의 짧은 정답들(block-pool/1)")
    ap.add_argument("--sheet", type=Path, help="블록 병원체 사실·함정 표(block-sheet/1)")
    ap.add_argument("--rounds", type=int, default=ROUNDS)
    ap.add_argument("--model")
    args = ap.parse_args(argv)
    asset = build(json.loads(args.document.read_text(encoding="utf-8")), args.out, args.run_id,
                  context=load_context(args.block, args.sheet, args.run_id), model=args.model, rounds=args.rounds)
    print(summary(asset), flush=True)
    return 0 if asset["questions"] or not asset["counts"]["eligible"] else 1


if __name__ == "__main__":
    sys.exit(main())
