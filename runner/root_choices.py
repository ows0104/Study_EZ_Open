"""Main-Quiz 판 게시 뒤 단답·나열 문항의 「선지 보기」용 선지를 만들어 올린다(2026-11-12).

생성기(`quizbank.root_choices`)는 하위 프로세스로 실행하고, 결과 JSON 하나를 asset 종류
`root_choices`(`<revision>.json`)로 기존 업로드 경로에 올린다. 실패해도 게시된 판·학습에는 영향이 없다 —
서버는 선지가 없으면 지금처럼 문제만 보여 준다. 문항·판·검수 상한을 바꾸지 않는다.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from . import transport
from .subprocesses import run_forwarded

KIND = "root_choices"


def upload(client: transport.Client, subject: str, run_id: str, path: Path) -> None:
    base = transport.lecture_path(subject, run_id)
    item = transport.Upload(KIND, path)
    signed = client.call("POST", f"{base}/uploads", [item.payload()])
    url = next(e["uploadUrl"] for e in signed["files"] if e["filename"] == item.filename)
    transport._put_with_retry(client, url, item)
    missing = client.call("POST", f"{base}/uploads/complete", [item.payload()]).get("missing", [])
    if missing:
        raise transport.PublishError(f"올렸는데 서버가 못 찾는다: {', '.join(missing)}")


def build(document: dict, out: Path, run_id: str, *, model: str | None = None, run=run_forwarded) -> Path | None:
    """하위 프로세스로 선지를 만든다. 성공하면 `<revision>.json` 경로."""
    out.mkdir(parents=True, exist_ok=True)
    doc_path = out / "document.json"
    doc_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    args = [sys.executable, "-m", "quizbank.root_choices", "--document", str(doc_path.resolve()),
            "--run-id", run_id, "--out", str(out.resolve())]
    if model:
        args += ["--model", model]
    if run(args, cwd=Path(__file__).resolve().parents[1]).returncode:
        return None
    named = out / f"{document['revision']}.json"
    shutil.copyfile(out / "choices.json", named)
    return named


def publish(client: transport.Client, subject: str, run_id: str, out: Path, payload: dict,
            *, model: str | None = None, run=run_forwarded) -> bool:
    """게시·근거 보강 뒤 한 번. 어떤 실패도 예외로 올리지 않고 로그만 남긴다."""
    try:
        document = payload["document"]
        print(f"Quiz Bank {run_id}: 단답·나열 선지 작성", flush=True)
        path = build(document, out / "choices", run_id, model=model, run=run)
        if path is None:
            print(f"Quiz Bank {run_id}: 선지 작성 실패 — 판은 게시됨, 선지 없이 표시", flush=True)
            return False
        upload(client, subject, run_id, path)
        print(f"Quiz Bank {run_id}: 선지 업로드 완료 ({path.name})", flush=True)
        return True
    except Exception as error:  # noqa: BLE001 — 게시를 되돌리지 않는다
        print(f"Quiz Bank {run_id}: 선지 작성 실패 — {error}", flush=True)
        return False
