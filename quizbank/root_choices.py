"""Main-Quiz(뿌리 학습) 판의 단답·나열 문항에 「선지 보기」용 선지를 만든다.

문항·판·학습 기록은 읽기만 한다. 판의 `bank_snapshot`에서 선지를 붙일 수 있는 문항을 40개씩 묶어
① 오답만 받아 오고(`content/prompts/learning-links/choices/write.md`, 강의 밖 일반 의학 지식·다른 강의 내용 허용)
② 그 오답을 독립된 호출로 의학 검토 한 번 받은 뒤(`review.md`, 2026-11-12 사용자 「의학 검수만 한번」)
③ 계약 검사(`studyez_contracts/roots/choices.py`)를 통과한 문항만 `root-choices/1` JSON 하나에 담는다.
의학 검토가 지적한 오답은 빼고, 남은 오답이 모자라면 그 문항은 선지 없이 둔다. 검토를 받지 못한 문항은 싣지 않는다.
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

PROMPTS = Path(__file__).resolve().parents[1] / "content/prompts/learning-links/choices"
PROMPT = PROMPTS / "write.md"
REVIEW_PROMPT = PROMPTS / "review.md"
REVIEW_POLICY = "choices-medical/1"
BATCH = 40
ATTEMPTS = 2
_STR = {"type": "string"}


def _rows(name: str, properties: dict) -> dict:
    return {"type": "object", "additionalProperties": False, "required": [name], "properties": {name: {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}}}}


def _pairs(first: str, second: str) -> dict:
    return {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": [first, second],
                                       "properties": {first: _STR, second: _STR}}}


PROPOSALS = _rows("proposals", {"question_id": _STR, "wrong": _pairs("text", "why_wrong"), "skip_reason": _STR})
REVIEWS = _rows("reviews", {"question_id": _STR, "invalid": _pairs("text", "reason")})


def _call(prompt: str, schema: dict, work: Path, model: str | None, label: str) -> tuple[dict, dict]:
    from .coverage import _call as call
    return call(prompt, schema, work, model, label)


def batch_input(document: dict, batch: list[dict]) -> dict:
    questions = document["bank_snapshot"]["questions"]
    return {"title": document.get("title", ""), "questions": [{
        "question_id": q["question_id"], "format": q["format"], "question": q["question"], "answer": q["answer"],
        "answer_units": q.get("answer_units", []), "explanation": q.get("explanation", ""),
        "candidate_pool": contract.distractor_pool(questions, q)} for q in batch]}


def review_input(document: dict, drafts: dict, questions: dict) -> dict:
    """검토자에게는 오답을 쓴 쪽의 이유를 주지 않는다."""
    return {"title": document.get("title", ""), "questions": [{
        "question_id": qid, "format": questions[qid]["format"], "question": questions[qid]["question"],
        "correct": contract.correct_texts(questions[qid]), "explanation": questions[qid].get("explanation", ""),
        "wrong": [row["text"] for row in wrong]} for qid, wrong in drafts.items()]}


def drafts_of(batch: list[dict], output: dict) -> tuple[dict, dict]:
    """묶음 결과를 문항마다 검사한다. (검토에 보낼 오답 초안, 건너뛴 이유)"""
    rows, drafts, skipped = {}, {}, {}
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
                drafts[qid] = row["wrong"]
    return drafts, skipped


def apply_review(questions: dict, drafts: dict, output: dict) -> tuple[dict, dict, dict]:
    """의학 검토가 지적한 오답을 뺀다. (통과한 칸, 건너뛴 이유, 문항별 검토 기록)"""
    reviews, entries, skipped, record = {}, {}, {}, {}
    for row in output.get("reviews", []):
        reviews.setdefault(row.get("question_id"), row)
    for qid, wrong in drafts.items():
        row = reviews.get(qid)
        if row is None:
            skipped[qid] = "의학 검토를 받지 못함"
            continue
        invalid = {contract.normalized(r["text"]): r["reason"].strip() for r in row["invalid"]}
        removed = [{"text": w["text"], "reason": invalid[contract.normalized(w["text"])]} for w in wrong
                   if contract.normalized(w["text"]) in invalid]
        kept = [w for w in wrong if contract.normalized(w["text"]) not in invalid]
        errors = contract.wrong_errors(questions[qid], kept)
        record[qid] = {"removed": removed, "kept": len(kept)}
        if errors:
            skipped[qid] = "의학 검토 뒤 오답 부족: " + "; ".join(f"{r['text']}({r['reason']})" for r in removed)
        else:
            entries[qid] = contract.entry(questions[qid], kept)
    return entries, skipped, record


def _stage(work: Path, name: str, prompt: str, schema: dict, data: dict, model: str | None, label: str, call, usage: list):
    """입력을 쓰고 한 번 부른다(실패하면 한 번 더). 같은 입력으로 이미 받은 답은 다시 부르지 않는다. 실패하면 (None, 오류)."""
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


def build(document: dict, out: Path, run_id: str, *, model: str | None = None, call=_call) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    by_id = {q["question_id"]: q for q in document["bank_snapshot"]["questions"]}
    targets = [q for q in by_id.values() if contract.eligible(q)]
    prompt, review_prompt = PROMPT.read_text(encoding="utf-8"), REVIEW_PROMPT.read_text(encoding="utf-8")
    questions, skipped, usage, reviewed, failed = {}, {}, [], {}, 0
    batches = [targets[i:i + BATCH] for i in range(0, len(targets), BATCH)]
    for index, batch in enumerate(batches):
        work = out / f"batch-{index}"
        output, error = _stage(work, f"choices-{index}", prompt, PROPOSALS, batch_input(document, batch), model,
                               f"Main-Quiz {run_id} 선지 작성 {index + 1}/{len(batches)}", call, usage)
        if output is None:
            failed += 1
            skipped.update({q["question_id"]: f"묶음 호출 실패: {error}" for q in batch})
            continue
        drafts, missed = drafts_of(batch, output)
        skipped.update(missed)
        if not drafts:
            continue
        verdicts, error = _stage(work / "review", f"choices-review-{index}", review_prompt, REVIEWS,
                                 review_input(document, drafts, by_id), model,
                                 f"Main-Quiz {run_id} 선지 의학 검토 {index + 1}/{len(batches)}", call, usage)
        if verdicts is None:  # 검토를 받지 못한 오답은 싣지 않는다
            failed += 1
            skipped.update({qid: f"의학 검토 호출 실패: {error}" for qid in drafts})
            continue
        entries, missed, record = apply_review(by_id, drafts, verdicts)
        questions.update(entries)
        skipped.update(missed)
        reviewed.update(record)
    asset = {"schema": contract.SCHEMA, "revision": document["revision"], "createdAt": datetime.now(UTC).isoformat(),
             "counts": {"eligible": len(targets), "written": len(questions), "skipped": len(skipped), "failedBatches": failed,
                        "removedByReview": sum(len(r["removed"]) for r in reviewed.values())},
             "medicalReview": {"policy": REVIEW_POLICY, "questions": reviewed},
             "questions": questions, "skipped": skipped}
    contract.validate(asset, document)
    (out / "choices.json").write_text(json.dumps(asset, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "usage.jsonl").open("a", encoding="utf-8") as log:
        for entry in usage:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return asset


def summary(asset: dict) -> str:
    c = asset["counts"]
    return (f"선지 대상 {c['eligible']}문항 · 작성 {c['written']} · 건너뜀 {c['skipped']} · "
            f"의학 검토가 뺀 오답 {c['removedByReview']} · 실패 묶음 {c['failedBatches']}")


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
