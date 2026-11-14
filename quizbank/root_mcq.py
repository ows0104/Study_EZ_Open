"""Main-Quiz 판의 문항에 선지(오답 풀)를 만든다 — 주관식 「선지 보기」와 객관식 모드가 같이 쓴다.

2026-11-14 객관식 모드(docs/changes/2026-11-14-mcq-mode)로 시작해, 같은 날 두 선지 기능을 합쳤다
(docs/changes/2026-11-14-choices-merge, `root-mcq/2`).
문항·판·학습 기록은 읽기만 한다. 판의 `bank_snapshot`에서 basic·list·cloze·sequence 문항을 40개씩 묶어
① 오답만 받아 오고(`content/prompts/learning-links/mcq/write.md`) — 출처는 같은 강의·다른 강의·족보·직접 작성(사용자 2026-11-14)
② 표기 언어·병기·길이·단정 표현으로 티 나는 오답을 코드가 빼고(`studyez_contracts/roots/mcq.py` `row_errors`)
③ 남은 오답을 독립된 호출로 마지막 의학 검토 한 번 받은 뒤(`review.md`)
④ 통과한 오답이 하나라도 있는 문항을 `root-mcq/2` JSON 하나에 담는다. 오답 수는 맞추지 않는다(「괜찮은 오답이 나오는 만큼」).
통과한 오답이 하나도 없는 문항·건너뛴 문항·실패한 묶음은 빠진 오답과 이유를 주고 한 번 더 쓴다(둘째 회차).
족보 재료: `--jokbo-sources`(강의별 족보 PDF, 러너가 만든다)를 코드로 읽는다(`quizbank/jokbo_pool.py`, 모델 호출 없음).
`--evidence`(근거 asset)가 있으면 문항에 직접 연결된 족보 문항을 먼저 준다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from studyez_contracts.roots import mcq as contract
from studyez_contracts.roots.choices import normalized

from . import jokbo_pool

PROMPTS = Path(__file__).resolve().parents[1] / "content/prompts/learning-links/mcq"
PROMPT = PROMPTS / "write.md"
REVIEW_PROMPT = PROMPTS / "review.md"
REVIEW_POLICY = "mcq-medical/2"
BATCH = 40
ATTEMPTS = 2
ROUNDS = 2
WORKERS = 3
_STR = {"type": "string"}

JOKBO = {"type": "object", "additionalProperties": False, "required": list(contract.JOKBO_KEYS),
         "properties": {k: _STR for k in contract.JOKBO_KEYS}}
WRONG = {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                  "required": ["group", "text", "parts", "source", "basis", "why_tempting", "why_wrong", "jokbo"],
                                  "properties": {"group": {"type": "integer"}, "text": _STR, "parts": {"type": "array", "items": _STR},
                                                 "source": {"type": "string", "enum": list(contract.SOURCES)},
                                                 "basis": _STR, "why_tempting": _STR, "why_wrong": _STR, "jokbo": JOKBO}}}
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


def _item(item: dict) -> dict:
    """족보 문항을 입력 모양으로(쪽 번호 등은 뺀다)."""
    return {k: item.get(k, "") for k in ("year", "professor", "number", "answer", "stem")} | {
        "options": [f"{o['mark']} {o['text']}" for o in item.get("options", [])]}


def batch_input(document: dict, batch: list[dict], context: dict, rejected: dict) -> dict:
    questions = document["bank_snapshot"]["questions"]
    own = context.get("jokbo", [])
    by_number = {(i["year"], i["number"]): i for i in own}
    others = context.get("other_jokbo", [])

    def other(q):
        rows = []
        for lecture in others:
            for item in jokbo_pool.related(lecture["items"], f"{q['question']} {q['answer']}", limit=3):
                rows.append({"run_id": lecture["run_id"], "title": lecture["title"], **_item(item)})
        return rows[:6]

    def parts(q):
        found = contract.groups(q)
        return {"groups": [{"group": i, "label": g["label"], "correct": g["correct"]} for i, g in enumerate(found)],
                "correct": [g["correct"] for g in found], "parts_needed": 0} if found else {
            "groups": [], "correct": contract.correct_texts(q), "parts_needed": contract.parts_needed(q)}

    return {"title": document.get("title", ""), "block": context.get("block", ""), "questions": [{
        "question_id": q["question_id"], "format": q["format"], "question": q["question"], "answer": q["answer"],
        **parts(q),
        **({"sequence_items": q.get("sequence_items", [])} if q["format"] == "sequence" else {}),
        "explanation": q.get("explanation", ""), "same_lecture": contract.same_lecture_pool(questions, q),
        "linked_jokbo": [_item(by_number[k]) for k in context.get("links", {}).get(q["question_id"], []) if k in by_number],
        "other_jokbo": other(q),
        "previous_rejected": rejected.get(q["question_id"], [])} for q in batch],
        "jokbo": [_item(i) for i in own], "block_pool": context.get("lectures", []), "block_sheet": context.get("sheet") or {}}


def shown(question: dict, row: dict) -> str:
    """검토·기록에 쓰는 오답 글. 나눠 묻는 문항은 묶음 이름을 앞에 붙인다(「[서울대병원] 10^5 CFU/mL」)."""
    found = contract.groups(question)
    text = contract.text_v2(question, row)
    group = row.get("group")
    return f"[{found[group]['label']}] {text}" if found and isinstance(group, int) and 0 <= group < len(found) else text


def _correct_shown(question: dict) -> list[str]:
    found = contract.groups(question)
    return [f"[{g['label']}] {g['correct']}" for g in found] if found else contract.correct_texts(question)


def review_input(document: dict, drafts: dict, questions: dict) -> dict:
    """검토자에게는 오답을 쓴 쪽의 출처·근거·이유를 주지 않는다."""
    return {"title": document.get("title", ""), "questions": [{
        "question_id": qid, "format": questions[qid]["format"], "question": questions[qid]["question"],
        "correct": _correct_shown(questions[qid]), "explanation": questions[qid].get("explanation", ""),
        "wrong": [shown(questions[qid], row) for row in wrong]} for qid, wrong in drafts.items()]}


def keep(question: dict, wrong: list[dict]) -> tuple[list[dict], list[dict]]:
    """코드 검사(형식·출처·표기 단서)를 통과한 오답과, 빠진 오답·이유. 중복은 앞의 것만, 풀 상한까지."""
    grouped = bool(contract.groups(question))
    seen = {normalized(t) for t in _correct_shown(question)}
    kept, dropped, per = [], [], {}
    for row in wrong:
        if not grouped:
            row = {**row, "group": -1}
        text = shown(question, row)
        errors = contract.row_errors(question, row)
        if not errors and normalized(text) in seen:
            errors = ["다른 오답과 같음"]
        if errors:
            dropped.append({"text": text, "reason": "; ".join(errors)})
            continue
        group = row["group"]
        if per.get(group, 0) >= contract.MAX_POOL:
            continue
        per[group] = per.get(group, 0) + 1
        seen.add(normalized(text))
        kept.append(row)
    return kept, dropped


def drafts_of(batch: list[dict], output: dict) -> tuple[dict, dict, dict]:
    """묶음 결과를 문항마다 검사한다. (검토에 보낼 오답 초안, 건너뛴 이유, 코드가 뺀 오답)"""
    rows, drafts, skipped, dropped = {}, {}, {}, {}
    for row in output.get("proposals", []):
        rows.setdefault(row.get("question_id"), row)
    for q in batch:
        qid, row = q["question_id"], rows.get(q["question_id"])
        if row is None:
            skipped[qid] = "모델이 이 문항을 쓰지 않음"
            continue
        if not row["wrong"]:
            skipped[qid] = row["skip_reason"].strip() or "모델이 오답을 쓰지 않음"
            continue
        kept, removed = keep(q, row["wrong"])
        if removed:
            dropped[qid] = removed
        if kept:
            drafts[qid] = kept
        else:
            skipped[qid] = "검사 탈락: " + "; ".join(f"{r['text']}({r['reason']})" for r in removed)
    return drafts, skipped, dropped


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
        removed = [{"text": shown(q, w), "reason": invalid[normalized(shown(q, w))]}
                   for w in wrong if normalized(shown(q, w)) in invalid]
        kept = [w for w in wrong if normalized(shown(q, w)) not in invalid]
        record[qid] = {"removed": removed, "kept": len(kept)}
        if kept:
            entries[qid] = contract.entry_v2(q, kept)
        else:
            skipped[qid] = "의학 검토 뒤 남은 오답 없음: " + "; ".join(f"{r['text']}({r['reason']})" for r in removed)
            rejected[qid] = removed
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
    """묶음 하나: 작성 → 코드 검사 → 의학 검토 → 반영."""
    prompt, review_prompt = prompts
    got = {"questions": {}, "skipped": {}, "reviewed": {}, "rejected": {}, "styled": {}, "failed": 0, "usage": []}
    output, error = _stage(work, "mcq-write", prompt, PROPOSALS, batch_input(document, batch, context, rejected), model,
                           f"{label} 작성", call, got["usage"])
    if output is None:
        got["failed"] = 1
        got["skipped"].update({q["question_id"]: f"묶음 호출 실패: {error}" for q in batch})
        return got
    drafts, missed, styled = drafts_of(batch, output)
    got["skipped"].update(missed)
    got["styled"].update(styled)
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
                               f"Main-Quiz {run_id} 선지 {number}회차 {index + 1}/{len(batches)}",
                               context, rejected, prompts, model, call) for index, batch in enumerate(batches)]
        return [f.result() for f in futures]


def build(document: dict, out: Path, run_id: str, *, context: dict | None = None, model: str | None = None,
          call=_call, rounds: int = ROUNDS) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    context = context or {}
    by_id = {q["question_id"]: q for q in document["bank_snapshot"]["questions"]}
    targets = [q for q in by_id.values() if contract.eligible(q)]
    prompts = (PROMPT.read_text(encoding="utf-8"), REVIEW_PROMPT.read_text(encoding="utf-8"))
    questions, skipped, usage, reviewed, failed, rejected, styled = {}, {}, [], {}, 0, {}, {}
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
            for qid, removed in [*got["rejected"].items(), *got["styled"].items()]:
                rejected[qid] = [*rejected.get(qid, []), *removed]
            for qid, removed in got["styled"].items():
                styled[qid] = [*styled.get(qid, []), *removed]
        pending = [by_id[qid] for qid in skipped if qid in by_id and qid not in questions]
        if not pending:
            break
    sources: dict[str, int] = {}
    for row in questions.values():
        for w in row["wrong"]:
            sources[w["source"]] = sources.get(w["source"], 0) + 1
    asset = {"schema": contract.SCHEMA_V2, "revision": document["revision"], "createdAt": datetime.now(UTC).isoformat(),
             "counts": {"eligible": len(targets), "written": len(questions), "skipped": len(skipped), "failedBatches": failed,
                        "removedByReview": sum(len(r["removed"]) for r in reviewed.values()),
                        "removedByStyle": sum(len(v) for v in styled.values()),
                        "wrong": sum(len(r["wrong"]) for r in questions.values()), "sources": sources},
             "jokbo": {"own": len(context.get("jokbo", [])),
                       "linkedQuestions": sum(1 for v in context.get("links", {}).values() if v)},
             "medicalReview": {"policy": REVIEW_POLICY, "questions": reviewed},
             "codeChecks": styled, "questions": questions, "skipped": skipped}
    contract.validate_v2(asset, document)
    (out / "mcq.json").write_text(json.dumps(asset, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "usage.jsonl").open("a", encoding="utf-8") as log:
        for entry in usage:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return asset


def summary(asset: dict) -> str:
    c = asset["counts"]
    src = " ".join(f"{k} {v}" for k, v in sorted(c.get("sources", {}).items()))
    return (f"선지 대상 {c['eligible']}문항 · 작성 {c['written']} · 건너뜀 {c['skipped']} · 오답 {c.get('wrong', 0)}({src}) · "
            f"표기 검사가 뺀 오답 {c.get('removedByStyle', 0)} · 의학 검토가 뺀 오답 {c['removedByReview']} · 실패 묶음 {c['failedBatches']}")


def jokbo_links(evidence: dict) -> dict[str, list[tuple[str, str]]]:
    """근거 asset의 `jokboPages`에서 문항별로 직접 연결된 족보 문항(연도, 번호)."""
    out: dict[str, list[tuple[str, str]]] = {}
    questions = ((evidence or {}).get("jokboPages") or {}).get("questions") or {}
    for qid, row in questions.items():
        keys = []
        for refs in (row.get("locators") or {}).values():
            for ref in refs if isinstance(refs, list) else []:
                key = (str(ref.get("year") or ""), str(ref.get("number") or ""))
                if all(key) and key not in keys:
                    keys.append(key)
        out[qid] = keys
    return out


def load_context(block: Path | None, sheet: Path | None, own_run_id: str, *,
                 jokbo_sources: Path | None = None, evidence: Path | None = None, cache: Path | None = None) -> dict:
    """블록·족보 재료. 블록 재료와 다른 강의 족보에서 자기 강의는 뺀다."""
    context: dict = {}
    if block:
        data = json.loads(block.read_text(encoding="utf-8"))
        context["block"] = data.get("subject", "")
        context["lectures"] = [{"title": row.get("title", ""), "facts": row.get("facts", [])}
                               for row in data.get("lectures", []) if row.get("run_id") != own_run_id]
    if sheet and sheet.exists():
        context["sheet"] = json.loads(sheet.read_text(encoding="utf-8"))
    if jokbo_sources and jokbo_sources.exists():
        sources = json.loads(jokbo_sources.read_text(encoding="utf-8")).get("lectures", [])
        lectures = jokbo_pool.subject_items(sources, cache or jokbo_sources.parent / "jokbo-items")
        context["jokbo"] = next((lec["items"] for lec in lectures if lec["run_id"] == own_run_id), [])
        context["other_jokbo"] = [lec for lec in lectures if lec["run_id"] != own_run_id and lec["items"]]
    if evidence and evidence.exists():
        try:
            context["links"] = jokbo_links(json.loads(evidence.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return context


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--document", type=Path, required=True, help="root_content 문서 JSON")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--block", type=Path, help="같은 과목 다른 강의의 짧은 정답들(block-pool/1)")
    ap.add_argument("--sheet", type=Path, help="과목 병원체 사실·함정 표(block-sheet/1)")
    ap.add_argument("--jokbo-sources", type=Path, help="강의별 족보 PDF 목록(jokbo-sources/1, 러너가 만든다)")
    ap.add_argument("--evidence", type=Path, help="이 판의 근거 asset(문항별 족보 연결)")
    ap.add_argument("--rounds", type=int, default=ROUNDS)
    ap.add_argument("--model")
    args = ap.parse_args(argv)
    context = load_context(args.block, args.sheet, args.run_id, jokbo_sources=args.jokbo_sources, evidence=args.evidence)
    asset = build(json.loads(args.document.read_text(encoding="utf-8")), args.out, args.run_id,
                  context=context, model=args.model, rounds=args.rounds)
    print(summary(asset), flush=True)
    return 0 if asset["questions"] or not asset["counts"]["eligible"] else 1


if __name__ == "__main__":
    sys.exit(main())
