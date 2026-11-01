"""Coordinate stored-response processing, checkpoints, and publication.

The generator is a child process; source selection, state, and HTTP upload have
separate owners. No first-generation CLI fallback is introduced here.
"""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
from pathlib import Path

from .. import transport
from ..subprocesses import run_forwarded
from . import REPO_ROOT, sources, state, upload


def _stage(name: str) -> None:
    print(f"── {name}", flush=True)  # agent.stage_of 가 읽는 꼴


def prepare_points(client: transport.Client, root: Path, subject: str, run_id: str,
                   this_year: str, prev_year: str, runs_dir: Path, *, model: str = "") -> int:
    # Legacy web clients still enqueue this preparatory job. Do not independently
    # re-author objectives while WEB is already doing that work.
    print(f"Quiz Bank points {run_id}: 별도 포인트 생성 생략 · 웹 문항과 저장된 원본 포인트를 본 검수에서 재사용", flush=True)
    return 0


def run(client: transport.Client, root: Path, subject: str, run_id: str, this_year: str, prev_year: str,
        runs_dir: Path, *, model: str = "") -> int:
    base = transport.lecture_path(subject, run_id)
    _stage("응답 받기")
    got = client.call("GET", f"{base}/bank-response")
    if got.get('importShare'):
        from ..shared_bank import recover
        _stage('저장된 공유 링크에서 완성 응답 가져오기')
        try:
            got = recover(client, base, run_id, got)
            if got.get('shareUnchanged'):
                print(f'Quiz Bank {run_id}: ready · 공유 응답이 기존 게시본과 같아 재검수 생략', flush=True)
                return 0
        except (ValueError, SystemExit, transport.PublishError) as error:
            # Do not mark the published bank failed or process its stale raw text.
            print(f'멈췄다 — 공유 응답 가져오기: {error}', flush=True)
            return 1
    # Preserve the original early rejection of a response without its revision.
    got["respondedAt"]
    maintenance = got.get("existingBank") is not None

    def fail(why: str, *, revision: dict | None = None) -> int:
        return upload.report_failure(client, base, got, why, revision=revision)

    pdf = sources._attached_pdf(root, subject, this_year, prev_year, runs_dir, run_id, got.get("sources", []))
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
    resume = state._resume(runs_dir, run_id, got, pdf) if maintenance else None
    if resume:
        _stage("저장된 보강본·출제 포인트로 재검증")
        (out / "maintenance-base.json").write_text(json.dumps(got["existingBank"], ensure_ascii=False), encoding="utf-8")
        existing.write_text(Path(resume["bankPath"]).read_text(encoding="utf-8"), encoding="utf-8")
    if not got.get("raw") and not maintenance:
        return fail("저장된 웹 응답이 없습니다. CLI에서 대신 출제하지 않습니다. 웹 출제를 완료하고 응답을 저장하세요.")
    legacy = bool(re.fullmatch(r"v?1\.(?:[0-9]|1[0-2])", got.get("promptVersion", "")))
    if got.get("raw") and not legacy and not got["raw"].rstrip().endswith("STUDYEZ_BANK_COMPLETE"):
        return fail("저장된 웹 응답의 완료 표식이 없습니다. 완성된 응답을 먼저 확인하세요.")
    if got.get('responseFile') or 'STUDYEZ_BANK_FILE' in (got.get('raw') or ''):
        from studyez_contracts.bank.markdown_file import validate as validate_markdown_file
        info = got.get('responseFile')
        if not info:
            return fail('파일 문제은행의 원본 검증 정보가 없습니다. 실제 .md 파일을 다시 전달하세요.')
        try:
            checked_file = validate_markdown_file(got['raw'], info['filename'], subject, run_id, info)
        except (ValueError, KeyError) as error:
            return fail(f'문제은행 파일 확인: {error}')
        (out / 'response-file.json').write_text(json.dumps(checked_file, ensure_ascii=False, indent=2), encoding='utf-8')
    raw.write_bytes((got.get("raw") or "").encode("utf-8"))
    argv = [sys.executable, "-m", "quizbank.run", str(raw), "--pdf", str(pdf), "--title", got["title"],
            "--run-id", run_id, "--out", str(out), "--points-cache-root", str(runs_dir / run_id / "bank")]
    if not maintenance:
        argv += ["--web-postprocess"]
    if got.get("promptVersion"):
        argv += ["--prompt-version", got["promptVersion"]]
    if maintenance:
        argv += ["--existing-bank", str(existing), "--preserve-existing"]
    if resume:
        argv += ["--point-plan", resume["pointPlanPath"]]
    if any(s["kind"] == "jokbo" for s in got.get("sources", [])):
        slices = sources.jokbo_slices(runs_dir, subject, {run_id: pdf})
        if run_id not in slices:
            return fail("등록된 족보 조각을 노트북에서 못 찾았다")
        argv += ["--jokbo", str(slices[run_id])]
    for s in got.get("sources") or [{"id": "S1", "kind": "notes_current", "filename": pdf.name}]:
        argv += ["--source", f"{s['id']}|{s['kind']}|{s['filename']}"]
    if model:
        argv += ["--model", model]
    jokbo_path = Path(argv[argv.index("--jokbo") + 1]) if "--jokbo" in argv else None
    response_resume = state._response_resume(runs_dir, run_id, got, pdf, jokbo_path) if not maintenance else None
    if response_resume:
        _stage("저장된 CLI 수정본·출제 포인트로 재검수")
        argv += ["--existing-bank", response_resume["bankPath"], "--point-plan", response_resume["pointPlanPath"]]
        if "remainingRepairRounds" in response_resume:
            argv += ["--max-repair-rounds", str(response_resume["remainingRepairRounds"])]
    response_identity = state._response_identity(got, pdf, jokbo_path) if not maintenance else None
    # 표준 출력을 물려준다 — `── 정리` 같은 단계 줄이 러너 로그로 바로 간다.
    code = run_forwarded(argv, cwd=REPO_ROOT).returncode
    result = state._read(out / "result.json")
    if not maintenance:
        allowed = response_resume.get("remainingRepairRounds", 2) if response_resume else 3
        checkpoint = result or state._read(out / "checkpoint.json") or {}
        consumed = (checkpoint.get("repairs") or {}).get("attempts", len(state._read(out / "repairs.json") or []))
        state._record_response_resume(runs_dir, run_id, got, pdf, out, jokbo_path, identity=response_identity,
                                remaining_repair_rounds=max(0, allowed - consumed))
    if code != 0 or result is None:
        return fail(f"quizbank 가 {code} 로 끝났다 (로그: {out})")
    revision = None
    if result.get("requiresRevision"):
        reason = f" {result['repairError'][:1000]}" if result.get("repairError") else ""
        summary = state._revision_summary(out, result)
        if summary:
            reason += f" 남은 지적: {summary}."
        revision = {"validation": state._read(out / "validation.json"),
                              "audit": state._read(out / "web-audit.json"),
                              "review": state._read(out / "review.json"),
                              "explanations": state._read(out / "explanations.json"),
                              "repairs": state._read(out / "repairs.json"),
                              "repairError": result.get("repairError")}
        if not (result.get('publication') or {}).get('allowed'):
            return fail(f"학습 가능한 구조를 만들지 못했습니다.{reason} 검수 기록: {out}", revision=revision)
        print(f'검수 지적을 보존하고 게시합니다.{reason}', flush=True)
    if maintenance:
        state._record_additions(out, got["existingBank"])

    _stage("업로드")
    return upload.publish_result(client, subject, run_id, got, out, result, revision=revision)
