"""Quiz Bank 의 러너 쪽 — 족보 조각을 미리 올리고, 받은 ChatGPT 응답을 정리해 올린다.

    ① 족보 조각 업로드   쓸기(publish)가 올해 필기 옆에 `jokbo` 로 올린다. 관리자가
                         캘린더에서 「Quiz Bank 만들기」를 누를 때 확장이 이것을 ChatGPT 에 붙인다.
    ② `runner bank`      일감(kind=bank)을 받은 러너가 부른다. 응답을 받아
                         `python -m quizbank.run` → 인용 쪽 PNG 올리기 → 결과 올리기.

quizgen 도 quizbank 도 import 하지 않는다 — 둘 다 하위 프로세스다(루트 CLAUDE.md 경계 ①).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
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
    found: dict[str, Path] = {}
    pending: dict[str, Path] = {}
    for run_id, pdf in sources.items():
        try:
            cached = json.loads(_cache_path(runs_dir, run_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cached = None
        if cached and cached.get("cut") == str(cut) and cached.get("source") == pdf.name:
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

    pdf = _notes_pdf(root, subject, this_year, prev_year, runs_dir, run_id)
    if pdf is None:
        return fail(f"{run_id} 의 올해 필기 PDF 를 노트북에서 못 찾았다")
    current_source = next((s for s in got.get("sources", []) if s["kind"] == "notes_current"), None)
    if current_source and current_source["filename"] != pdf.name:
        return fail("서버의 올해 필기와 로컬 PDF 파일명이 다릅니다. 자료 동기화 후 다시 요청하세요.")

    out = runs_dir / run_id / "bank" / time.strftime("%y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    raw = out / "raw.md"
    existing = out / "existing-bank.json"
    if maintenance:
        existing.write_text(json.dumps(got["existingBank"], ensure_ascii=False), encoding="utf-8")
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
            "--run-id", run_id, "--out", str(out)]
    if got.get("promptVersion"):
        argv += ["--prompt-version", got["promptVersion"]]
    if maintenance:
        argv += ["--existing-bank", str(existing)]
    if any(s["kind"] == "jokbo" for s in got.get("sources", [])):
        slices = jokbo_slices(runs_dir, subject, {run_id: pdf})
        if run_id not in slices:
            return fail("등록된 족보 조각을 노트북에서 못 찾았다")
        argv += ["--jokbo", str(slices[run_id])]
    for s in got.get("sources") or [{"id": "S1", "kind": "notes_current", "filename": pdf.name}]:
        argv += ["--source", f"{s['id']}|{s['kind']}|{s['filename']}"]
    if model:
        argv += ["--model", model]
    # 표준 출력을 물려준다 — `── 정리` 같은 단계 줄이 러너 로그로 바로 간다.
    code = subprocess.run(argv, cwd=REPO_ROOT).returncode
    result = _read(out / "result.json")
    if code != 0 or result is None:
        return fail(f"quizbank 가 {code} 로 끝났다 (로그: {out})")
    if result.get("requiresRevision"):
        return fail(f"CLI 검수에서 ChatGPT 응답 수정이 필요합니다. 검수 기록: {out}",
                    revision={"validation": _read(out / "validation.json"),
                              "audit": _read(out / "web-audit.json"),
                              "review": _read(out / "review.json"),
                              "explanations": _read(out / "explanations.json")})

    _stage("업로드")
    slides = sorted((out / "slides").glob("*.png")) if (out / "slides").is_dir() else []
    sent = _upload_slides(client, subject, run_id, slides)
    usage = [json.loads(line) for line in (out / "usage.jsonl").read_text(encoding="utf-8").splitlines()
             if line.strip()] if (out / "usage.jsonl").is_file() else []
    answer = client.call("PUT", f"{base}/bank", {
        "respondedAt": responded, "bank": _read(out / "bank.json"), "validation": _read(out / "validation.json"),
        **({"baseBuildId": got["baseBuildId"]} if maintenance else {}),
        "review": _read(out / "review.json"), "pages": _read(out / "pages.json") or {}, "usage": generation_usage + usage,
        "message": "" if result["pass"] else f"검증 오류 {result['errors']}건"})
    print(f"Quiz Bank {run_id}: {answer.get('status')} · 문항 {result['questions']} · 검토 {result['review']}"
          f" · 슬라이드 {len(slides)}장(새로 {sent})", flush=True)
    return 0
