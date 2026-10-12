"""한 명령: ChatGPT 응답 + 필기 PDF → 정리 → 검증 → 외부지식 검토 → 인용 쪽 PNG.

    python -m quizbank.run raw.md --pdf 필기.pdf --title "콜린성 약리학(2)" --run-id 261002_02 \\
        --source "S1|notes_current|필기.pdf" --source "S2|jokbo|L12-13.md" --out runs/…/bank/<build>

나오는 것 (`--out` 안):

    bank.json        정리된 문제은행
    validation.json  {pass, errors, warnings}
    review.json      외부지식 검토 — 검증을 통과했을 때만
    pages.json       문항 ID → 인용 쪽들
    slides/          <run_id>_sNNN.png
    usage.jsonl      단계마다 시간·토큰
    result.json      위 것의 요약. **이 파일이 있어야 끝난 것이다**

검증에 떨어져도 0 으로 끝난다 — 떨어진 것도 결과다(관리자가 사이트에서 오류를 본다).
모델 세션이 죽으면 1 로 끝나고 마지막 줄에 `멈췄다 — 이유` 를 찍는다(러너가 그 줄을 읽는다).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from . import coverage, organize, review, slides
from .session import SessionError
from .validate import validate_dropping

OUTPUTS = ("bank.json", "bank.raw.json", "validation.json", "review.json", "coverage.json", "pages.json", "result.json", "usage.jsonl")


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


def run(raw_path: Path, pdf: Path | None, title: str, run_id: str, sources: list[dict], out: Path,
        *, pdf_source: str = "S1", do_review: bool = True, model: str | None = None,
        prompt_version: str = "", existing_bank: Path | None = None,
        do_coverage: bool = True, jokbo: Path | None = None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    # 지난 실행이 남긴 것을 이번 것으로 읽지 않는다 (루트 CLAUDE.md 함정 ②).
    for name in OUTPUTS:
        (out / name).unlink(missing_ok=True)
    shutil.rmtree(out / "slides", ignore_errors=True)

    raw = raw_path.read_text(encoding="utf-8")
    lecture = {"title": title, "sources": sources, "prompt_version": prompt_version}

    _stage("정리")
    if existing_bank is None:
        bank, info = organize.organize(raw, lecture, model=model)
        _usage(out, "정리", info)
    else:
        bank = json.loads(existing_bank.read_text(encoding="utf-8"))
    _write(out / "bank.json", bank)

    _stage("검증")
    # 걸린 문항만 빼고 다시 잰다 — 뺀 은행을 `bank.json` 에 다시 쓴다. 빼기 전 것은 `bank.raw.json`.
    full_count = len(bank.get("questions", []))
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
                bank, pdf, title, sources, out, model=model, pdf_source=pdf_source, jokbo=jokbo)
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

        _stage("슬라이드")
        pages = slides.cited_pages(bank, pdf_source)
        _write(out / "pages.json", pages)
        if pdf is not None:
            made, missing = slides.render(pdf, {p for ps in pages.values() for p in ps}, out / "slides", run_id)
            result["slides"], result["missing_pages"] = len(made), missing

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
    ap.add_argument("--existing-bank", type=Path, help="기존 문항을 재정리하지 않고 원본 대조·추가만 수행")
    ap.add_argument("--jokbo", type=Path, help="범위에 해당하는 족보 조각")
    ap.add_argument("--model")
    ap.add_argument("--prompt-version", default="")
    args = ap.parse_args(argv)
    sources = [parse_source(s) for s in args.source] or [{"id": "S1", "kind": "notes_current", "filename": ""}]
    try:
        result = run(args.raw, args.pdf, args.title, args.run_id, sources, args.out,
                     pdf_source=args.pdf_source, do_review=not args.no_review, model=args.model,
                     prompt_version=args.prompt_version, existing_bank=args.existing_bank,
                     do_coverage=not args.no_coverage, jokbo=args.jokbo)
    except SessionError as e:
        print(f"멈췄다 — {e}", flush=True)
        return 1
    # 산출물을 다 쓴 뒤의 요약도 실패할 수 있는 코드다 (루트 CLAUDE.md 함정 ①) — 종료 코드를 바꾸지 않는다.
    try:
        verdict = "통과" if result["pass"] else f"검증 오류 {result['errors']}건"
        if result.get("dropped"):
            verdict += f" (걸린 문항 {result['dropped']}개를 뺐다)"
        print(f"문항 {result['questions']} · {verdict} · 검토 {result['review']} · 슬라이드 {result['slides']}장"
              + (f" · PDF에 없는 쪽 {result['missing_pages']}" if result["missing_pages"] else ""), flush=True)
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
