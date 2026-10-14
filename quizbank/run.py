"""한 명령: ChatGPT 응답 + 필기 PDF → 정리 → 검증 → 외부지식 검토 → 인용 쪽 PNG.

    python -m quizbank.run raw.md --pdf 필기.pdf --title "콜린성 약리학(2)" --run-id 261002_02 \\
        --source "S1|notes_current|필기.pdf" --source "S2|jokbo|L12-13.md" --out runs/…/bank/<build>

나오는 것 (`--out` 안):

    bank.json        정리된 문제은행
    validation.json  {pass, errors, warnings}
    review.json      외부지식 검토 — 1.29 이상은 스키마를 읽을 수 있으면 의미 오류도 함께 검토
    repairs.json     CLI 수정·보완 기록 (프롬프트 1.29 이상)
    pages.json       문항 ID → 인용 쪽들
    slides/          <run_id>_sNNN.png
    usage.jsonl      단계마다 시간·토큰
    result.json      위 것의 요약. **이 파일이 있어야 끝난 것이다**

검증에 떨어져도 0 으로 끝난다 — 떨어진 것도 결과다(관리자가 사이트에서 오류를 본다).
모델 세션이 죽으면 1 로 끝나고 마지막 줄에 `멈췄다 — 이유` 를 찍는다(러너가 그 줄을 읽는다).
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import time
from pathlib import Path

from . import classify, coverage, explain, option_pools, organize, question_first, repair, review, slides, web_audit
from .schema import schema_errors
from .session import SessionError
from .validate import validate_bank, validate_dropping
from server.app.bank_validation.publication import stamp, usable

OUTPUTS = ("bank.json", "bank.raw.json", "bank.before-repair.json", "authored-points.json", "repairs.json", "checkpoint.json", "validation.json", "review.json", "coverage.json", "classification.json", "web-audit.json", "explanations.json", "pages.json", "result.json", "usage.jsonl")
OUTPUTS += ("content-validation.json", "learning-structure.json", "learning-structure.raw.json")
OUTPUTS += ("option-pools.json", "option-pools.raw.json")
MAX_REPAIR_ROUNDS = 3


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _usage(out: Path, step: str, info: dict) -> None:
    with (out / "usage.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"step": step, "t": int(time.time()), **info}, ensure_ascii=False) + "\n")


def _stage(name: str) -> None:
    print(f"── {name}", flush=True)  # runner/agent.py stage_of 가 읽는 꼴


def parse_source(text: str) -> dict:
    sid, kind, filename = (text.split("|", 2) + ["", ""])[:3]
    return {"id": sid.strip(), "kind": kind.strip(), "filename": filename.strip()}


def _review_with_notes(reviewed: dict, source: dict | None, explanations: dict | None) -> dict:
    """Display CLI doubts from every inspection without starting another repair."""
    result = copy.deepcopy(reviewed)
    rows = {row["question_id"]: row for row in result.get("reviews", [])}
    notes = [(row["question_id"], "원본 검수", row["reason"])
             for row in ((source or {}).get("webAudit") or {}).get("question_issues", [])
             if row["severity"] == "doubt"]
    notes += [(row["question_id"], "해설 검수", row["note"])
              for row in (explanations or {}).get("annotations", []) if row["verdict"] == "doubt"]
    notes += [(qid, "출제 포인트 검수", check["note"])
              for check in ((source or {}).get("webAudit") or {}).get("checks", [])
              if check["status"] == "uncertain" for qid in check["question_ids"]]
    for qid, origin, note in notes:
        if qid not in rows:
            continue  # Never fill a missing independent review with another stage's opinion.
        row = rows[qid]
        row["note"] = " · ".join(filter(None, [row["note"], f"{origin}: {note}"]))
        if row["verdict"] == "ok":
            row["verdict"] = "doubt"
            result["counts"]["ok"] -= 1
            result["counts"]["doubt"] = result["counts"].get("doubt", 0) + 1
    if any(qid in rows for qid, _, _ in notes):
        result["summary"] = result.get("summary", "") + " 원본·해설 검수의 주의사항은 문항별 주석에 함께 표시했습니다."
    return result


def _run_authored(bank: dict, raw: str, pdf: Path | None, title: str, run_id: str,
                  sources: list[dict], out: Path, *, pdf_source: str, do_review: bool,
                  do_coverage: bool, model: str | None, prompt_version: str,
                  jokbo: Path | None, point_plan: Path | None, max_repair_rounds: int,
                  question_first_mode: bool = False) -> dict:
    """Assess → repair locally → independently reassess, retaining every change."""
    initial_count = len(bank.get("questions", []))
    initial_ids = {q["question_id"] for q in bank.get("questions", [])}
    explanations_enabled = explain.enabled(prompt_version)
    points = json.loads(point_plan.read_text(encoding="utf-8")) if point_plan else None
    plan_error = None
    if question_first_mode and not points:
        plan_error = "문항 우선 처리에는 원본 독립 추출 포인트가 필요합니다."
    elif points is None:
        try:
            web_audit.parse_points(raw)
        except SessionError as cause:
            plan_error = str(cause)
    changes = []
    spent_repairs = 0
    for attempt in range(max_repair_rounds + 1):
        # Never publish a review of an earlier candidate as the final review.
        for name in ("review.json", "explanations.json", "coverage.json", "web-audit.json", "classification.json"):
            (out / name).unlink(missing_ok=True)
        explanation_check, source_check, answer_check = None, None, None
        if explanations_enabled and pdf is not None and not schema_errors(bank):
            _stage("정답 확인·해설 작성")
            bank, explanation_check, info = explain.write(bank, pdf, title, out,
                pdf_source=pdf_source, jokbo=jokbo, model=model)
            _usage(out, "정답 확인·해설 작성", info)
            _write(out / "explanations.json", explanation_check)
        _write(out / "bank.json", bank)
        _stage("검증")
        validation = validate_bank(bank, [s["id"] for s in sources],
            **({"learning_structure": False} if question_first_mode else {}))
        _write(out / "validation.json", validation)
        result = {"pass": validation["pass"], "questions": len(bank.get("questions", [])),
                  "dropped": 0, "errors": len(validation["errors"]), "warnings": len(validation["warnings"]),
                  "review": None, "slides": 0, "missing_pages": [],
                  "requiresRevision": not validation["pass"] or pdf is None or not do_coverage or not do_review}
        if explanations_enabled:
            validation["explanations"] = explanation_check
            result["explanations"] = {k: explanation_check[k] for k in ("annotatedCount", "requiresRevision")} if explanation_check else None
            result["requiresRevision"] |= not do_review or explanation_check is None or explanation_check["requiresRevision"]
        # Collect content findings before spending a bounded repair round on
        # semantic validation errors (for example, leaked answers or links).
        # Malformed JSON fields still cannot be inspected safely.
        if not schema_errors(bank):
            if pdf is not None and do_coverage:
                if plan_error:
                    source_check = {"requiresRevision": True, "error": plan_error}
                    result["requiresRevision"] = True
                else:
                    _stage("원본·출제 포인트·중복 검수")
                    kwargs = {"points": points} if points is not None else {}
                    if question_first_mode:
                        kwargs["defer_structure"] = True
                    source_check, usage = web_audit.inspect(bank, raw, pdf, title, sources, out,
                        model=model, jokbo=jokbo, **kwargs)
                    if (source_check.get("classification") or {}).get("status") == "partial":
                        _stage("객관식 유형 반영")
                        bank, classification = classify.apply_classifications(bank,
                            {"classifications": [{"question_id": row["question_id"],
                                "mcq_mode": row["recommended_mode"], "reason": row["reason"]}
                                for row in source_check["webAudit"]["classifications"]]})
                        rebuilt = web_audit.shape_report(source_check["webAudit"], bank,
                            points if points is not None else web_audit.parse_points(raw),
                            source_check["totalPages"], pdf_source=pdf_source)
                        source_check = {**source_check, **rebuilt}
                        _write(out / "classification.json", classification)
                        _write(out / "bank.json", bank)
                    added = [q for q in bank["questions"] if q["question_id"] not in initial_ids]
                    source_check.update(addedQuestions=len(added),
                        addedMcq=sum(q["format"] in ("mcq", "multi_select") for q in added))
                    validation["coverage"] = source_check
                    _write(out / "coverage.json", source_check)
                    result["requiresRevision"] |= source_check["requiresRevision"]
                    for entry in usage:
                        _usage(out, entry["step"], {k: v for k, v in entry.items() if k != "step"})
                    result["coverage"] = {k: source_check[k] for k in
                        ("status", "gapCount", "unreadablePages", "addedQuestions", "addedMcq")}
            if do_review:
                _stage("외부지식 검토")
                answer_check, info = review.review(bank, title, model=model)
                answer_check = _review_with_notes(answer_check, source_check, explanation_check)
                _write(out / "review.json", answer_check)
                _usage(out, "외부지식 검토", info)
                result["review"] = answer_check["counts"]
                result["requiresRevision"] |= bool(answer_check["counts"].get("wrong", 0)
                    or answer_check.get("missing") or answer_check.get('requiresRevision'))
        _write(out / "validation.json", validation)
        result["repairs"] = {"attempts": spent_repairs, "acceptedAttempts": len(changes), "maxAttempts": max_repair_rounds, "initialQuestions": initial_count,
                              "finalQuestions": len(bank.get("questions", []))}
        _write(out / "checkpoint.json", result)
        # Omitted required checks cannot be solved by editing a question.
        if not result["requiresRevision"] or attempt == max_repair_rounds or pdf is None or not do_coverage or not do_review:
            break
        if not changes:
            _write(out / "bank.before-repair.json", bank)
        _stage(f"CLI 문항 수정·누락 보완 {attempt + 1}/{max_repair_rounds}")
        findings = {"validation": validation, "audit": source_check,
                    "explanations": explanation_check, "review": answer_check}
        spent_repairs += 1
        result["repairs"]["attempts"] = spent_repairs
        _write(out / "checkpoint.json", result)
        try:
            bank, points, change, info = repair.repair(bank, raw, pdf, title, sources, findings,
                out, attempt + 1, points=points, jokbo=jokbo, model=model,
                **({"defer_structure": True} if question_first_mode else {}))
        except repair.RepairError as cause:
            result["repairError"] = str(cause)
            _write(out / "checkpoint.json", result)
            break
        changes.append(change)
        _write(out / "repairs.json", changes)
        _write(out / "bank.json", bank)
        _usage(out, "CLI 문항 수정·누락 보완", info)
        plan_error = None
    if question_first_mode:
        _write(out / "content-validation.json", validation)
        learning = {"status": "deferred", "reason": "내용 검수·보완이 완료되지 않았습니다."}
        if points and validate_bank(bank, [s['id'] for s in sources], learning_structure=False, check_quality=False)['pass']:
            _stage("검수 후 개념도·회상 계획 연결")
            try:
                bank, structure, info = question_first.connect(bank, points, title, out, model=model)
                _usage(out, "검수 후 개념도·회상 계획 연결", info)
                learning = {"status": "connected", "concepts": len(bank["concepts"]),
                            "assignments": len(structure["assignments"]), "summary": structure["summary"],
                            "contentHash": question_first.content_hash(bank)}
            except SessionError as cause:
                learning = {"status": "failed", "error": str(cause)}
                result["requiresRevision"] = True
        final_validation = validate_bank(bank, [s["id"] for s in sources])
        if not final_validation["pass"]:
            learning["errors"] = final_validation["errors"]
            if learning["status"] == "connected" and not validate_bank(bank, [s['id'] for s in sources], check_quality=False)['pass']:
                learning["status"] = "failed"
        result["pass"] = final_validation["pass"]
        result["errors"], result["warnings"] = len(final_validation["errors"]), len(final_validation["warnings"])
        result["requiresRevision"] |= learning["status"] != "connected" or not final_validation["pass"]
        result["learningStructure"], result["pipeline"] = learning, "question-first"
        final_validation["contentValidation"] = validation
        if "coverage" in validation:
            # Content is immutable across this step; only graph metadata changed.
            source_check = validation["coverage"]
            source_check["contentBankHash"] = source_check["bankHash"]
            source_check["contentHash"] = question_first.content_hash(bank)
            source_check["bankHash"] = coverage.bank_hash(bank)
            final_validation["coverage"] = source_check
            _write(out / "coverage.json", source_check)
        validation = final_validation
        _write(out / "bank.json", bank)
        _write(out / "learning-structure.json", learning)
        _write(out / "validation.json", validation)
    if result['requiresRevision']:
        validation['revision'] = {'audit': (source_check or {}).get('webAudit'), 'review': answer_check,
            'explanations': explanation_check, 'repairs': changes, 'repairError': result.get('repairError')}
    validation = stamp(bank, validation, [s['id'] for s in sources], allow_unresolved=True)
    result['publication'] = validation['publication']
    _write(out / 'validation.json', validation)
    if usable(bank, validation):
        _stage("슬라이드")
        pages = slides.cited_pages(bank, pdf_source)
        _write(out / "pages.json", pages)
        made, missing = slides.render(pdf, {p for ps in pages.values() for p in ps}, out / "slides", run_id)
        result["slides"], result["missing_pages"] = len(made), missing
        if missing:
            result["requiresRevision"] = True
            validation['publication']['hasUnresolved'] = True
            _write(out / 'validation.json', validation)
    _write(out / "result.json", result)
    return result


def run(raw_path: Path, pdf: Path | None, title: str, run_id: str, sources: list[dict], out: Path,
        *, pdf_source: str = "S1", do_review: bool = True, model: str | None = None,
        prompt_version: str = "", existing_bank: Path | None = None,
        do_coverage: bool = True, jokbo: Path | None = None, point_plan: Path | None = None,
        preserve_existing: bool = False, max_repair_rounds: int = MAX_REPAIR_ROUNDS,
        points_cache_root: Path | None = None) -> dict:
    if type(max_repair_rounds) is not int or not 0 <= max_repair_rounds <= MAX_REPAIR_ROUNDS:
        raise ValueError("CLI 수정 상한은 0~3회여야 합니다.")
    out.mkdir(parents=True, exist_ok=True)
    # 지난 실행이 남긴 것을 이번 것으로 읽지 않는다 (루트 CLAUDE.md 함정 ②).
    for name in OUTPUTS:
        (out / name).unlink(missing_ok=True)
    shutil.rmtree(out / "slides", ignore_errors=True)

    raw = raw_path.read_text(encoding="utf-8")
    lecture = {"title": title, "sources": sources, "prompt_version": prompt_version}
    question_first_mode = question_first.enabled(prompt_version) and not preserve_existing
    if question_first_mode and pdf is not None and do_coverage:
        if point_plan is None and points_cache_root is not None:
            point_plan = question_first.cached_points(points_cache_root, pdf, title, sources,
                                                       pdf_source=pdf_source, jokbo=jokbo)
        _stage("저장된 원본 독립 포인트 재사용" if point_plan else "원본 독립 출제포인트 추출")
        _, entries = question_first.extract_points(pdf, title, sources, out,
            pdf_source=pdf_source, jokbo=jokbo, reuse=point_plan, model=model)
        for entry in entries:
            _usage(out, entry["step"], {k: v for k, v in entry.items() if k != "step"})
        point_plan = out / "authored-points.json"

    _stage("정리")
    if existing_bank is None:
        bank, info = organize.organize(raw, lecture, model=model, out=out / "organize")
        _usage(out, "정리", info)
    else:
        bank = json.loads(existing_bank.read_text(encoding="utf-8"))
        if question_first_mode:
            bank = question_first.as_draft(bank)
    if question_first_mode:
        question_first.require_draft(bank)
        if option_pools.enabled(prompt_version) and existing_bank is None and pdf is not None and do_coverage and do_review:
            _write(out / "bank.json", bank)
            _stage("CLI 보기 풀 선택적 작성")
            points = json.loads(point_plan.read_text(encoding="utf-8"))
            bank, pool_report, info = option_pools.write(bank, points, pdf, title, sources, out, jokbo=jokbo, model=model)
            _write(out / "bank.json", bank)
            _write(out / "option-pools.json", pool_report)
            if info is not None:
                _usage(out, "CLI 보기 풀 선택적 작성", info)

    if web_audit.enabled(prompt_version) and not preserve_existing:
        return _run_authored(bank, raw, pdf, title, run_id, sources, out,
            pdf_source=pdf_source, do_review=do_review, do_coverage=do_coverage, model=model,
            prompt_version=prompt_version, jokbo=jokbo, point_plan=point_plan, max_repair_rounds=max_repair_rounds,
            question_first_mode=question_first_mode)

    _write(out / "bank.json", bank)

    _stage("검증")
    # 걸린 문항만 빼고 다시 잰다 — 뺀 은행을 `bank.json` 에 다시 쓴다. 빼기 전 것은 `bank.raw.json`.
    full_count = len(bank.get("questions", []))
    if preserve_existing:
        kept, validation = bank, validate_bank(bank, [s["id"] for s in sources])
    else:
        kept, validation = validate_dropping(bank, [s["id"] for s in sources])
    if kept is not bank:
        _write(out / "bank.raw.json", bank)
        bank = kept
        _write(out / "bank.json", bank)
    _write(out / "validation.json", validation)

    result: dict = {"pass": validation["pass"], "questions": len(bank.get("questions", [])),
                    "dropped": full_count - len(bank.get("questions", [])),
                    "errors": len(validation["errors"]), "warnings": len(validation["warnings"]),
                    "review": None, "slides": 0, "missing_pages": []}
    if validation["pass"]:
        if pdf is not None and do_coverage:
            _stage("원본 누락 검증·객관식 보강")
            bank, checked, usage = coverage.audit_and_supplement(
                bank, pdf, title, sources, out, model=model, pdf_source=pdf_source, jokbo=jokbo, point_plan=point_plan)
            # 보강은 validate_bank를 통과한 추가분만 합친다. 원본 대조 결과는 형식 통과와 별도다.
            validation["coverage"] = checked
            _write(out / "bank.json", bank)
            _write(out / "validation.json", validation)
            for entry in usage:
                _usage(out, entry["step"], {key: value for key, value in entry.items() if key != "step"})
            result["questions"] = len(bank["questions"])
            result["coverage"] = {key: checked[key] for key in ("status", "gapCount", "unreadablePages", "addedQuestions", "addedMcq")}
        if do_review:
            _stage("외부지식 검토")
            checked, info = review.review(bank, title, model=model)
            _write(out / "review.json", checked)
            _usage(out, "외부지식 검토", info)
            result["review"] = checked["counts"]
            if checked.get('requiresRevision'):
                result['requiresRevision'] = True

        _stage("슬라이드")
        pages = slides.cited_pages(bank, pdf_source)
        _write(out / "pages.json", pages)
        if pdf is not None:
            made, missing = slides.render(pdf, {p for ps in pages.values() for p in ps}, out / "slides", run_id)
            result["slides"], result["missing_pages"] = len(made), missing

    result['requiresRevision'] = bool(result.get('requiresRevision')
        or (result.get('review') or {}).get('wrong')
        or (result.get('coverage') or {}).get('status') == 'partial'
        or not validation['pass'])
    if result['requiresRevision']:
        validation['revision'] = {'coverage': validation.get('coverage'),
            'review': json.loads((out / 'review.json').read_text(encoding='utf-8')) if (out / 'review.json').exists() else None}
    validation = stamp(bank, validation, [s['id'] for s in sources], allow_unresolved=True)
    result['publication'] = validation['publication']
    _write(out / 'validation.json', validation)
    _write(out / "result.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m quizbank.run", description=__doc__.split("\n")[0])
    ap.add_argument("raw", type=Path, help="ChatGPT 응답 (markdown)")
    ap.add_argument("--pdf", type=Path, help="필기 PDF — 인용 쪽을 그린다")
    ap.add_argument("--title", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--source", action="append", default=[], help="'S1|notes_current|파일명' — 첨부한 순서대로")
    ap.add_argument("--pdf-source", default="S1")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--no-review", action="store_true")
    ap.add_argument("--no-coverage", action="store_true", help="원본 대조·보강 생략 (검증 완료로 표시하지 않음)")
    ap.add_argument("--existing-bank", type=Path, help="기존 JSON으로 정리를 생략하고 검수·CLI 수정·보완")
    ap.add_argument("--preserve-existing", action="store_true", help="보강 작업: 기존 질문·정답을 유지하고 추가분만 검증")
    ap.add_argument("--jokbo", type=Path, help="범위에 해당하는 족보 조각")
    ap.add_argument("--point-plan", type=Path, help="자료·범위가 같은 기존 고정 포인트 계획을 재사용")
    ap.add_argument("--points-cache-root", type=Path, help="웹 출제 중 미리 추출한 원본 독립 포인트 검색 위치")
    ap.add_argument("--model")
    ap.add_argument("--max-repair-rounds", type=int, choices=range(MAX_REPAIR_ROUNDS + 1), default=MAX_REPAIR_ROUNDS,
                    help="복구 시 남은 수정 횟수 (기본 3, 상한을 늘릴 수 없음)")
    ap.add_argument("--prompt-version", default="")
    args = ap.parse_args(argv)
    sources = [parse_source(s) for s in args.source] or [{"id": "S1", "kind": "notes_current", "filename": ""}]
    try:
        result = run(args.raw, args.pdf, args.title, args.run_id, sources, args.out,
                     pdf_source=args.pdf_source, do_review=not args.no_review, model=args.model,
                     prompt_version=args.prompt_version, existing_bank=args.existing_bank,
                     do_coverage=not args.no_coverage, jokbo=args.jokbo, point_plan=args.point_plan,
                     preserve_existing=args.preserve_existing, max_repair_rounds=args.max_repair_rounds,
                     points_cache_root=args.points_cache_root)
    except SessionError as e:
        print(f"멈췄다 — {e}", flush=True)
        return 1
    # 산출물을 다 쓴 뒤의 요약도 실패할 수 있는 코드다 (루트 CLAUDE.md 함정 ①) — 종료 코드를 바꾸지 않는다.
    try:
        verdict = "통과" if result["pass"] else f"검증 오류 {result['errors']}건"
        if result.get("requiresRevision"):
            verdict = "CLI 검수·보완 미완료"
        if result.get("dropped"):
            verdict += f" (걸린 문항 {result['dropped']}개를 뺐다)"
        print(f"문항 {result['questions']} · {verdict} · 검토 {result['review']} · 슬라이드 {result['slides']}장"
              + (f" · PDF에 없는 쪽 {result['missing_pages']}" if result["missing_pages"] else ""), flush=True)
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
