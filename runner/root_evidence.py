"""Main-Quiz 판 게시 뒤 Quiz Bank 수준 근거를 만들어 올린다(2026-11-08).

생성기(`quizbank.root_evidence`)는 하위 프로세스로 실행하고, 결과 JSON 하나를 asset 종류
`root_evidence`(`<revision>.json`)로 기존 업로드 경로에 올린다. 실패해도 게시된 판·학습에는 영향이 없다 —
서버는 근거가 없으면 인용 쪽만 보여 준다. 문항·판·검수 상한을 바꾸지 않는다.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from . import transport
from .subprocesses import run_forwarded

KIND = "root_evidence"


def upload(client: transport.Client, subject: str, run_id: str, path: Path) -> None:
    base = transport.lecture_path(subject, run_id)
    item = transport.Upload(KIND, path)
    signed = client.call("POST", f"{base}/uploads", [item.payload()])
    url = next(e["uploadUrl"] for e in signed["files"] if e["filename"] == item.filename)
    transport._put_with_retry(client, url, item)
    missing = client.call("POST", f"{base}/uploads/complete", [item.payload()]).get("missing", [])
    if missing:
        raise transport.PublishError(f"올렸는데 서버가 못 찾는다: {', '.join(missing)}")


def build(document: dict, sources: dict[str, Path], out: Path, run_id: str, *, model: str | None = None,
          run=run_forwarded, reviews: list[dict] | None = None, review_source: str | None = None) -> Path | None:
    """하위 프로세스로 근거를 만든다. 성공하면 `<revision>.json` 경로.

    `reviews`·`review_source`: review-evidence/1 판의 문항 검토. 검토가 증명한 쪽은 다시 고르지 않는다."""
    out.mkdir(parents=True, exist_ok=True)
    doc_path = out / "document.json"
    doc_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    args = [sys.executable, "-m", "quizbank.root_evidence", "--document", str(doc_path.resolve()),
            "--run-id", run_id, "--out", str(out.resolve())]
    if reviews and review_source:
        reviews_path = out / "item-reviews.json"
        reviews_path.write_text(json.dumps(reviews, ensure_ascii=False), encoding="utf-8")
        args += ["--reviews", str(reviews_path.resolve()), "--review-source", review_source]
    for sid, path in sources.items():
        args += ["--source", f"{sid}={path.resolve()}"]
    if model:
        args += ["--model", model]
    if run(args, cwd=Path(__file__).resolve().parents[1]).returncode:
        return None
    named = out / f"{document['revision']}.json"
    shutil.copyfile(out / "evidence.json", named)
    return named


def publish(client: transport.Client, subject: str, run_id: str, out: Path, packet: dict, payload: dict,
            *, model: str | None = None, run=run_forwarded) -> bool:
    """게시 직후 한 번. 어떤 실패도 예외로 올리지 않고 로그만 남긴다. `run`: 호출한 쪽의 하위 프로세스 실행기."""
    try:
        document = payload["document"]
        known = {s["source_id"] for s in document["review"]["sources"]}
        sources = {s["id"]: Path(s["localPath"]) for s in packet["sources"]
                   if s.get("localPath", "").lower().endswith(".pdf") and s["id"] in known}
        print(f"Quiz Bank {run_id}: 핵심 근거·족보 지면 연결", flush=True)
        manifest = payload.get("manifest") or {}
        path = build(document, sources, out / "evidence", run_id, model=model, run=run,
                     reviews=manifest.get("itemReviews"), review_source=(manifest.get("reviewEvidence") or {}).get("sourceId"))
        if path is None:
            print(f"Quiz Bank {run_id}: 근거 보강 실패 — 판은 게시됨, 인용 쪽만 표시", flush=True)
            return False
        upload(client, subject, run_id, path)
        print(f"Quiz Bank {run_id}: 근거 보강 업로드 완료 ({path.name})", flush=True)
        return True
    except Exception as error:  # noqa: BLE001 — 게시를 되돌리지 않는다
        print(f"Quiz Bank {run_id}: 근거 보강 실패 — {error}", flush=True)
        return False
