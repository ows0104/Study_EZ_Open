"""Quiz Bank 의 러너 쪽 — 족보 조각을 미리 올리고, 받은 ChatGPT 응답을 정리해 올린다.

    ① 족보 조각 업로드   쓸기(publish)가 올해 필기 옆에 `jokbo` 로 올린다. 관리자가
                         캘린더에서 「Quiz Bank 만들기」를 누를 때 확장이 이것을 ChatGPT 에 붙인다.
    ② `runner bank`      일감(kind=bank)을 받은 러너가 부른다. 응답을 받아
                         `python -m quizbank.run` → 인용 쪽 PNG 올리기 → 결과 올리기.

quizgen 도 quizbank 도 import 하지 않는다 — 둘 다 하위 프로세스다(루트 CLAUDE.md 경계 ①).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

from . import deck, publish, watch

REPO_ROOT = Path(__file__).resolve().parents[1]
SLICE_CACHE = "jokbo.json"


# ---------------------------------------------------------------- ① 족보 조각


def _cache_path(runs_dir: Path, run_id: str) -> Path:
    return runs_dir / run_id / "bank" / SLICE_CACHE


def jokbo_slices(runs_dir: Path, subject: str, sources: dict[str, Path]) -> dict[str, Path]:
    """run_id → 그 편의 족보 조각(.md). 조각이 없거나 문턱 아래인 편은 빠진다.

    판정은 하위 프로세스(`python -m quizgen.slicefor`)라 느리다 — 쓸기가 10분마다 도므로
    편마다 `runs/<id>/bank/jokbo.json` 에 적어 두고, **컷이나 필기 파일이 바뀔 때만** 다시 잰다.
    """
    cut = deck.jokbo_dir(runs_dir, subject)
    if not (cut / "index.json").is_file():
        return {}
    revision = json.loads((cut / "index.json").read_text(encoding="utf-8")).get("professor_table_revision", "")
    found: dict[str, Path] = {}
    pending: dict[str, Path] = {}
    for run_id, pdf in sources.items():
        try:
            cached = json.loads(_cache_path(runs_dir, run_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cached = None
        if (cached and cached.get("cut") == str(cut) and cached.get("source") == pdf.name
                and cached.get("professorRevision", "") == revision):
            if cached.get("slice") and Path(cached["slice"]).is_file():
                found[run_id] = Path(cached["slice"])
            continue
        pending[run_id] = pdf
    if not pending:
        return found
    with tempfile.TemporaryDirectory(prefix="slicefor-") as tmp:
        out = Path(tmp) / "out.json"
        proc = subprocess.run([sys.executable, "-m", "quizgen.slicefor", "--jokbo-dir", str(cut), "--out", str(out),
                               *map(str, pending.values())], cwd=REPO_ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode != 0 or not out.is_file():
            print(f"  ⚠ {subject}: 족보 조각을 못 쟀다 — {(proc.stderr or proc.stdout).strip()[-200:]}", flush=True)
            return found
        rows = json.loads(out.read_text(encoding="utf-8"))
    by_source = {Path(r["source"]).name: r for r in rows}
    for run_id, pdf in pending.items():
        row = by_source.get(pdf.name) or {}
        slice_md = str((REPO_ROOT / row["slice"]).resolve()) if row.get("slice") else ""
        path = _cache_path(runs_dir, run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"cut": str(cut), "source": pdf.name, "slice": slice_md,
                                    "professorRevision": revision,
                                    "score": row.get("score"), "why": row.get("why", "")},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
        if slice_md:
            found[run_id] = Path(slice_md)
    return found


# ---------------------------------------------------------------- ② runner bank


def _stage(name: str) -> None:
    print(f"── {name}", flush=True)  # agent.stage_of 가 읽는 꼴


def _notes_pdf(root: Path, subject: str, this_year: str, prev_year: str, runs_dir: Path, run_id: str) -> Path | None:
    plans, _ = publish.plan_subject(root, subject, this_year, prev_year, runs_dir)
    return next((p.item.path for p in plans if p.run_id == run_id), None)


def _attached_pdf(root: Path, subject: str, this_year: str, prev_year: str, runs_dir: Path,
                  run_id: str, sources: list[dict]) -> Path | None:
    """Keep the WEB-attached source version even if a newer local PDF arrives."""
    source = next((s for s in sources if s["kind"] == "notes_current"), None)
    if source:
        name = source["filename"]
        folder = root / subject / "필기" / this_year
        if Path(name).name == name:
            direct = folder / name
            if direct.is_file():
                return direct
            matches = [p for p in folder.rglob("*.pdf")
                       if unicodedata.normalize("NFC", p.name) == unicodedata.normalize("NFC", name)]
            if len(matches) == 1:
                return matches[0]
    return _notes_pdf(root, subject, this_year, prev_year, runs_dir, run_id)


def _upload_slides(client: publish.Client, subject: str, run_id: str, slides: list[Path]) -> int:
    if not slides:
        return 0
    base = publish.lecture_path(subject, run_id)
    uploads = [publish.Upload("bank_media", p) for p in slides]
    payloads = [u.payload() for u in uploads]
    signed = client.call("POST", f"{base}/uploads", payloads)
    urls = {e["filename"]: e["uploadUrl"] for e in signed["files"]}
    missing = set(client.call("POST", f"{base}/uploads/complete", payloads).get("missing", []))
    todo = [u for u in uploads if u.filename in missing]
    for upload in todo:
        publish._put_with_retry(client, urls[upload.filename], upload)
    if todo:
        left = client.call("POST", f"{base}/uploads/complete", [u.payload() for u in todo]).get("missing", [])
        if left:
            raise publish.PublishError(f"올렸는데 서버가 못 찾는다: {', '.join(left[:5])}")
    return len(todo)


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _resume(runs_dir: Path, run_id: str, got: dict, pdf: Path) -> dict | None:
    record = _read(runs_dir / run_id / "bank" / "resume.json")
    if not record or got.get("existingBank") is None:
        return None
    expected = hashlib.sha256(json.dumps(got["existingBank"], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    if (record.get("expectedBankHash") != expected or record.get("baseBuildId") != got.get("baseBuildId")
            or record.get("sourceSha256") != hashlib.sha256(pdf.read_bytes()).hexdigest()):
        return None
    if not all(Path(record.get(key, "")).is_file() for key in ("bankPath", "pointPlanPath")):
        return None
    return record


def _response_identity(got: dict, pdf: Path, jokbo: Path | None = None) -> dict:
    return {"responseHash": hashlib.sha256(got.get("raw", "").encode("utf-8")).hexdigest(),
            "respondedAt": got["respondedAt"], "promptVersion": got.get("promptVersion", ""),
            "title": got["title"], "sources": got.get("sources", []),
            "sourceSha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "jokboSha256": hashlib.sha256(jokbo.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
            if jokbo is not None and jokbo.is_file() else None}


def _response_resume(runs_dir: Path, run_id: str, got: dict, pdf: Path,
                     jokbo: Path | None = None) -> dict | None:
    """Continue CLI edits only when the response and every source identity still match."""
    root = (runs_dir / run_id / "bank").resolve()
    try:
        record = _read(root / "response-resume.json")
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("identity") != _response_identity(got, pdf, jokbo):
        return None
    remaining = record.get("remainingRepairRounds", 2)  # Legacy records retain the old allowance.
    if type(remaining) is not int or not 0 <= remaining <= 3:
        return None
    for key in ("bankPath", "pointPlanPath"):
        value = record.get(key)
        if not isinstance(value, str) or not value.strip():
            return None
        path = Path(value).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            return None
    return record


def _record_response_resume(runs_dir: Path, run_id: str, got: dict, pdf: Path, out: Path,
                            jokbo: Path | None = None, *, identity: dict | None = None,
                            remaining_repair_rounds: int | None = None) -> None:
    point_path = next((path for path in (out / "authored-points.json", out / "web-audit/point-plan.json")
                       if path.is_file()), None)
    if not (out / "bank.json").is_file() or point_path is None:
        return
    try:
        if not isinstance(_read(out / "bank.json"), dict) or not isinstance(_read(point_path), list):
            return
    except (OSError, ValueError):
        return  # Interrupted writes are never a resumable candidate.
    current_identity = _response_identity(got, pdf, jokbo)
    if identity is not None and identity != current_identity:
        return
    record = {"identity": current_identity, "bankPath": str((out / "bank.json").resolve()),
              "pointPlanPath": str(point_path.resolve())}
    if remaining_repair_rounds is not None:
        if type(remaining_repair_rounds) is not int or not 0 <= remaining_repair_rounds <= 3:
            raise ValueError("CLI 수정 상한은 0~3회여야 합니다.")
        record["remainingRepairRounds"] = remaining_repair_rounds
    path = runs_dir / run_id / "bank/response-resume.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def _record_additions(out: Path, original: dict) -> None:
    validation = _read(out / "validation.json")
    if not isinstance((validation or {}).get("coverage"), dict):
        return
    current = _read(out / "bank.json")
    def mcqs(bank):
        return sum(q.get("format") in ("mcq", "multi_select") for q in bank["questions"])
    counts = {"addedQuestions": len(current["questions"]) - len(original["questions"]), "addedMcq": mcqs(current) - mcqs(original)}
    validation["coverage"].update(counts)
    (out / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    if (out / "coverage.json").is_file():
        (out / "coverage.json").write_text(json.dumps(validation["coverage"], ensure_ascii=False, indent=2), encoding="utf-8")
    result = _read(out / "result.json")
    if result and result.get("coverage"):
        result["coverage"].update(counts)
        (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def _revision_summary(out: Path, result: dict) -> str:
    """Summarize blocking CLI findings without counting nonblocking doubts."""
    audit = _read(out / "web-audit.json") or {}
    review = _read(out / "review.json") or {}
    explanations = _read(out / "explanations.json") or {}
    wrong = {row["question_id"] for row in audit.get("question_issues", []) if row.get("severity") == "error"}
    wrong.update(row["question_id"] for row in review.get("reviews", []) if row.get("verdict") == "wrong")
    wrong.update(row["question_id"] for row in explanations.get("annotations", []) if row.get("verdict") == "wrong")
    parts = []
    if wrong:
        parts.append(f"문항 오류 {len(wrong)}건({', '.join(sorted(wrong)[:5])})")
    for label, count in (("구조·의미 검증 오류", result.get("errors", 0)),
                         ("미충족 포인트", (result.get("coverage") or {}).get("gapCount", 0)),
                         ("누락된 출제 목표", sum(row.get("kind") == "missing_point" for row in audit.get("plan_issues", []))),
                         ("중복 묶음", len(audit.get("duplicates", []))),
                         ("정답 검토 누락", len(review.get("missing", []))),
                         ("읽지 못한 원본 쪽", (result.get("coverage") or {}).get("unreadablePages", 0))):
        if count:
            parts.append(f"{label} {count}건")
    return " · ".join(parts)


def prepare_points(client: publish.Client, root: Path, subject: str, run_id: str,
                   this_year: str, prev_year: str, runs_dir: Path, *, model: str = "") -> int:
    base = publish.lecture_path(subject, run_id)
    context = client.call("GET", f"{base}/bank/source-context")
    pdf = _attached_pdf(root, subject, this_year, prev_year, runs_dir, run_id, context["sources"])
    if pdf is None:
        print(f"멈췄다 — {run_id} 의 올해 필기 PDF를 노트북에서 못 찾았다", flush=True)
        return 1
    source = next((s for s in context["sources"] if s["kind"] == "notes_current"), None)
    if source is None or unicodedata.normalize("NFC", source["filename"]) != unicodedata.normalize("NFC", pdf.name):
        print("멈췄다 — 서버와 로컬의 올해 필기가 다릅니다. 자료 동기화가 필요합니다.", flush=True)
        return 1
    cache = runs_dir / run_id / "bank"
    out = cache / "points" / str(time.time_ns())
    out.mkdir(parents=True, exist_ok=True)
    context_path = out / "context.json"
    context_path.write_text(json.dumps({"title": context["title"], "sources": context["sources"]},
                                        ensure_ascii=False), encoding="utf-8")
    argv = [sys.executable, "-m", "quizbank.independent", "--pdf", str(pdf),
            "--context", str(context_path), "--out", str(out), "--cache-root", str(cache),
            "--min-source-age", str(watch.MIN_AGE_SECONDS)]
    if any(s["kind"] == "jokbo" for s in context["sources"]):
        slices = jokbo_slices(runs_dir, subject, {run_id: pdf})
        if run_id not in slices:
            print("멈췄다 — 등록된 족보 조각을 노트북에서 못 찾았다", flush=True)
            return 1
        argv += ["--jokbo", str(slices[run_id])]
    if model:
        argv += ["--model", model]
    code = subprocess.run(argv, cwd=REPO_ROOT).returncode
    result = _read(out / "points-result.json")
    point_file = out / "authored-points.json"
    points = _read(point_file)
    if (code or not result or result.get("completed") is not True or not isinstance(points, list)
            or not points or result.get("points") != len(points)
            or result.get("pointPlanPath") != str(point_file.resolve())):
        print(f"멈췄다 — 원본 독립 포인트 준비 미완료 (로그: {out})", flush=True)
        return 1
    action = "저장된 결과 재사용" if result["reused"] else "원본 독립 추출 완료"
    print(f"Quiz Bank points {run_id}: {action} · 포인트 {result['points']}개", flush=True)
    return 0


def run(client: publish.Client, root: Path, subject: str, run_id: str, this_year: str, prev_year: str,
        runs_dir: Path, *, model: str = "") -> int:
    base = publish.lecture_path(subject, run_id)
    _stage("응답 받기")
    got = client.call("GET", f"{base}/bank-response")
    responded = got["respondedAt"]
    maintenance = got.get("existingBank") is not None

    def fail(why: str, *, revision: dict | None = None) -> int:
        try:
            client.call("PUT", f"{base}/bank", {"respondedAt": responded, "message": why,
                        **({"revision": revision} if revision is not None else {}),
                        **({"baseBuildId": got["baseBuildId"]} if maintenance else {})})
        except publish.PublishError as e:
            print(f"  (실패를 서버에 적지 못했다: {e})", flush=True)
        print(f"멈췄다 — {why}", flush=True)
        return 1

    pdf = _attached_pdf(root, subject, this_year, prev_year, runs_dir, run_id, got.get("sources", []))
    if pdf is None:
        return fail(f"{run_id} 의 올해 필기 PDF 를 노트북에서 못 찾았다")
    current_source = next((s for s in got.get("sources", []) if s["kind"] == "notes_current"), None)
    if current_source and unicodedata.normalize("NFC", current_source["filename"]) != unicodedata.normalize("NFC", pdf.name):
        return fail("서버의 올해 필기와 로컬 PDF 파일명이 다릅니다. 자료 동기화 후 다시 요청하세요.")

    out = runs_dir / run_id / "bank" / time.strftime("%y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    raw = out / "raw.md"
    existing = out / "existing-bank.json"
    if maintenance:
        existing.write_text(json.dumps(got["existingBank"], ensure_ascii=False), encoding="utf-8")
    resume = _resume(runs_dir, run_id, got, pdf) if maintenance else None
    if resume:
        _stage("저장된 보강본·출제 포인트로 재검증")
        (out / "maintenance-base.json").write_text(json.dumps(got["existingBank"], ensure_ascii=False), encoding="utf-8")
        existing.write_text(Path(resume["bankPath"]).read_text(encoding="utf-8"), encoding="utf-8")
    generation_usage = []
    if not got.get("raw") and not maintenance:
        # 동기화 중인 PDF로 출제하지 않는다. 부모 러너가 대기 중에도 취소를 받는다.
        left = watch.MIN_AGE_SECONDS - (time.time() - pdf.stat().st_mtime)
        if left > 0:
            _stage("동기화 대기")
        while left > 0:
            time.sleep(min(30, left))
            left = watch.MIN_AGE_SECONDS - (time.time() - pdf.stat().st_mtime)
        _stage("출제")
        context = out / "context.json"
        context.write_text(json.dumps(got, ensure_ascii=False), encoding="utf-8")
        argv = [sys.executable, "-m", "quizbank.generate", "--pdf", str(pdf),
                "--context", str(context), "--out", str(out)]
        if any(s["kind"] == "jokbo" for s in got.get("sources", [])):
            slices = jokbo_slices(runs_dir, subject, {run_id: pdf})
            if run_id not in slices:
                return fail("등록된 족보 조각을 노트북에서 못 찾았다")
            argv += ["--jokbo", str(slices[run_id])]
        if model:
            argv += ["--model", model]
        code = subprocess.run(argv, cwd=REPO_ROOT).returncode
        generated = _read(out / "generation.json")
        if code != 0 or generated is None or not raw.is_file():
            return fail(f"자동 출제가 {code} 로 끝났다 (로그: {out})")
        got["raw"] = raw.read_text(encoding="utf-8")
        got["promptVersion"] = generated["promptVersion"]
        client.call("PUT", f"{base}/bank-generated-response", {
            "raw": got["raw"], "respondedAt": responded,
            "promptVersion": generated["promptVersion"]})
        generation_usage = generated.get("usage", [])
    raw.write_text(got.get("raw") or "", encoding="utf-8")
    argv = [sys.executable, "-m", "quizbank.run", str(raw), "--pdf", str(pdf), "--title", got["title"],
            "--run-id", run_id, "--out", str(out), "--points-cache-root", str(runs_dir / run_id / "bank")]
    if got.get("promptVersion"):
        argv += ["--prompt-version", got["promptVersion"]]
    if maintenance:
        argv += ["--existing-bank", str(existing), "--preserve-existing"]
    if resume:
        argv += ["--point-plan", resume["pointPlanPath"]]
    if any(s["kind"] == "jokbo" for s in got.get("sources", [])):
        slices = jokbo_slices(runs_dir, subject, {run_id: pdf})
        if run_id not in slices:
            return fail("등록된 족보 조각을 노트북에서 못 찾았다")
        argv += ["--jokbo", str(slices[run_id])]
    for s in got.get("sources") or [{"id": "S1", "kind": "notes_current", "filename": pdf.name}]:
        argv += ["--source", f"{s['id']}|{s['kind']}|{s['filename']}"]
    if model:
        argv += ["--model", model]
    jokbo_path = Path(argv[argv.index("--jokbo") + 1]) if "--jokbo" in argv else None
    response_resume = _response_resume(runs_dir, run_id, got, pdf, jokbo_path) if not maintenance else None
    if response_resume:
        _stage("저장된 CLI 수정본·출제 포인트로 재검수")
        argv += ["--existing-bank", response_resume["bankPath"], "--point-plan", response_resume["pointPlanPath"]]
        if "remainingRepairRounds" in response_resume:
            argv += ["--max-repair-rounds", str(response_resume["remainingRepairRounds"])]
    response_identity = _response_identity(got, pdf, jokbo_path) if not maintenance else None
    # 표준 출력을 물려준다 — `── 정리` 같은 단계 줄이 러너 로그로 바로 간다.
    code = subprocess.run(argv, cwd=REPO_ROOT).returncode
    result = _read(out / "result.json")
    if not maintenance:
        allowed = response_resume.get("remainingRepairRounds", 2) if response_resume else 3
        checkpoint = result or _read(out / "checkpoint.json") or {}
        consumed = (checkpoint.get("repairs") or {}).get("attempts", len(_read(out / "repairs.json") or []))
        _record_response_resume(runs_dir, run_id, got, pdf, out, jokbo_path, identity=response_identity,
                                remaining_repair_rounds=max(0, allowed - consumed))
    if code != 0 or result is None:
        return fail(f"quizbank 가 {code} 로 끝났다 (로그: {out})")
    revision = None
    if result.get("requiresRevision"):
        reason = f" {result['repairError'][:1000]}" if result.get("repairError") else ""
        summary = _revision_summary(out, result)
        if summary:
            reason += f" 남은 지적: {summary}."
        revision = {"validation": _read(out / "validation.json"),
                              "audit": _read(out / "web-audit.json"),
                              "review": _read(out / "review.json"),
                              "explanations": _read(out / "explanations.json"),
                              "repairs": _read(out / "repairs.json"),
                              "repairError": result.get("repairError")}
        if not (result.get('publication') or {}).get('allowed'):
            return fail(f"학습 가능한 구조를 만들지 못했습니다.{reason} 검수 기록: {out}", revision=revision)
        print(f'검수 지적을 보존하고 게시합니다.{reason}', flush=True)
    if maintenance:
        _record_additions(out, got["existingBank"])

    _stage("업로드")
    slides = sorted((out / "slides").glob("*.png")) if (out / "slides").is_dir() else []
    sent = _upload_slides(client, subject, run_id, slides)
    usage = [json.loads(line) for line in (out / "usage.jsonl").read_text(encoding="utf-8").splitlines()
             if line.strip()] if (out / "usage.jsonl").is_file() else []
    answer = client.call("PUT", f"{base}/bank", {
        "respondedAt": responded, "bank": _read(out / "bank.json"), "validation": _read(out / "validation.json"),
        'allowUnresolved': True,
        **({'revision': revision} if revision is not None else {}),
        **({"baseBuildId": got["baseBuildId"]} if maintenance else {}),
        "review": _read(out / "review.json"), "pages": _read(out / "pages.json") or {}, "usage": generation_usage + usage,
        "message": ('미해결 검수 지적을 보존하고 게시했습니다.' if revision else '')
            if result.get('publication', {}).get('allowed') else ("" if result["pass"] else f"검증 오류 {result['errors']}건")})
    print(f"Quiz Bank {run_id}: {answer.get('status')} · 문항 {result['questions']} · 검토 {result['review']}"
          f" · 슬라이드 {len(slides)}장(새로 {sent})", flush=True)
    return 0
