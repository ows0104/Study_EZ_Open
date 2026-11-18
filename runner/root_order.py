"""Main-Quiz 판에 순서 맞추기 판정(`root-order/1`)을 만들어 붙인다(docs/changes/2026-11-18-ordering-screen).

러너가 판을 게시하고 선지를 붙인 직후 `publish`를 기본으로 부르고(`runner/connection_generation.py`),
아래 수동 명령은 이미 게시된 판을 채울 때 쓴다. 판을 게시한 PC(`runs/_root-generation/`)에서 돈다.
강의마다 생성기(`quizbank.root_order`)를 하위 프로세스로 돌려 결과 JSON 하나를 asset 종류 `root_order`(`<revision>.json`)로 올린다.
문항·판·학습 기록·선지를 바꾸지 않는다. 서버는 판정이 없으면 그 문항을 지금처럼 보여 준다.

    python -m runner.root_order --all-published --subject 감염과 면역 --no-upload     # 만들기만
    python -m runner.root_order --all-published --subject 감염과 면역 --upload-only   # 만든 것을 올리기만
    python -m runner.root_order --all-published --subject 감염과 면역 --missing       # 만들고 올리기(올린 판은 건너뜀)
    python -m runner.root_order --run-id 261110_02 --no-upload

결과는 `<실행>/order/`에 두고, 올리면 `<실행>/order/uploaded.json`에 판과 schema를 적는다.
"""
from __future__ import annotations

import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from . import transport
from .root_choices import published_run, published_run_ids
from .root_mcq import upload as _upload
from .subprocesses import run_forwarded

KIND = "root_order"
MARKER = "uploaded.json"
FOLDER = "order"
SCHEMA = "root-order/1"


def upload(client: transport.Client, subject: str, run_id: str, path: Path) -> None:
    _upload(client, subject, run_id, path, kind=KIND)


def build(document: dict, out: Path, *, model: str | None = None, run=run_forwarded) -> Path | None:
    out.mkdir(parents=True, exist_ok=True)
    doc_path = out / "document.json"
    doc_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    args = [sys.executable, "-m", "quizbank.root_order", "--document", str(doc_path.resolve()), "--out", str(out.resolve())]
    if model:
        args += ["--model", model]
    if run(args, cwd=Path(__file__).resolve().parents[1]).returncode:
        return None
    named = out / f"{document['revision']}.json"
    shutil.copyfile(out / "order.json", named)
    return named


def uploaded(folder: Path, revision: str) -> bool:
    try:
        mark = json.loads((folder / FOLDER / MARKER).read_text(encoding="utf-8"))
        return mark.get("revision") == revision and mark.get("schema") == SCHEMA
    except (OSError, ValueError, AttributeError):
        return False


def _mark(path: Path, revision: str) -> None:
    (path.parent / MARKER).write_text(json.dumps({"revision": revision, "schema": SCHEMA,
                                                  "uploadedAt": datetime.now(UTC).isoformat()}), encoding="utf-8")


def publish(client: transport.Client, subject: str, run_id: str, folder: Path, payload: dict,
            *, model: str | None = None, run=run_forwarded) -> bool:
    """러너가 판을 게시한 직후 부른다. 어떤 실패도 예외로 올리지 않고 로그만 남긴다."""
    try:
        document = payload["document"]
        print(f"Quiz Bank {run_id}: 순서 맞추기 판정", flush=True)
        path = build(document, folder / FOLDER, model=model, run=run)
        if path is None:
            print(f"Quiz Bank {run_id}: 순서 맞추기 판정 실패 — 판은 게시됨, 나열 문항은 지금처럼 표시", flush=True)
            return False
        upload(client, subject, run_id, path)
        _mark(path, document["revision"])
        print(f"Quiz Bank {run_id}: 순서 맞추기 판정 업로드 완료 ({path.name})", flush=True)
        return True
    except Exception as error:  # noqa: BLE001 — 게시를 되돌리지 않는다
        print(f"Quiz Bank {run_id}: 순서 맞추기 판정 실패 — {error}", flush=True)
        return False


def one(run_id: str, args, client) -> str:
    """강의 하나: "done"·"skipped"·"failed". 실패는 다른 강의를 멈추지 않는다."""
    try:
        folder, packet, payload = published_run(args.runs, run_id, args.subject, args.generation)
    except SystemExit as missing:
        print(missing, flush=True)
        return "failed"
    document = payload["document"]
    revision = document["revision"]
    if client is not None and uploaded(folder, revision) and (args.missing or args.upload_only):
        print(f"Main-Quiz {run_id}: 판 {revision} 순서 판정 이미 올림 — 건너뜀", flush=True)
        return "skipped"
    out = folder / FOLDER
    try:
        if args.upload_only:
            path = out / f"{revision}.json"
            if not path.exists():
                print(f"Main-Quiz {run_id}: 만든 순서 판정이 없다({path})", flush=True)
                return "failed"
        else:
            print(f"Main-Quiz {run_id}: 판 {revision} ({folder.name}) 순서 판정", flush=True)
            path = build(document, out, model=args.model)
            if path is None:
                print(f"Main-Quiz {run_id}: 순서 판정 실패", flush=True)
                return "failed"
        if client is None:
            print(f"{run_id} 만들기만 함: {path}", flush=True)
            return "done"
        upload(client, packet["subject"], run_id, path)
        _mark(path, revision)
        print(f"Main-Quiz {run_id}: 순서 판정 업로드 완료 ({path.name})", flush=True)
        return "done"
    except Exception as error:  # noqa: BLE001 — 한 강의의 실패가 다른 강의를 멈추지 않는다
        print(f"Main-Quiz {run_id}: 순서 판정 실패 — {error}", flush=True)
        return "failed"


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="게시된 Main-Quiz 판에 순서 맞추기 판정을 만들어 붙인다")
    ap.add_argument("--run-id", action="append", default=[], help="여러 번 줄 수 있다")
    ap.add_argument("--all-published", action="store_true", help="--subject 과목에서 이 PC가 게시한 강의 전부")
    ap.add_argument("--subject", help="--all-published에는 필수")
    ap.add_argument("--generation", help="runs/_root-generation의 실행 ID를 직접 지정(강의 하나일 때)")
    ap.add_argument("--runs", type=Path, default=Path("runs"))
    ap.add_argument("--workers", type=int, default=3, help="함께 도는 강의 수")
    ap.add_argument("--model")
    ap.add_argument("--no-upload", action="store_true", help="만들기만 하고 올리지 않는다")
    ap.add_argument("--upload-only", action="store_true", help="이미 만든 판정을 올리기만 한다")
    ap.add_argument("--missing", action="store_true", help="현재 판에 올린 기록이 있는 강의는 건너뛴다")
    ap.add_argument("--api")
    ap.add_argument("--token")
    args = ap.parse_args(argv)
    if args.all_published and not args.subject:
        ap.error("--all-published에는 --subject가 필요하다")
    if args.no_upload and args.upload_only:
        ap.error("--no-upload와 --upload-only는 함께 쓰지 않는다")
    run_ids = list(dict.fromkeys([*args.run_id, *(published_run_ids(args.runs, args.subject) if args.all_published else [])]))
    if not run_ids:
        ap.error("--run-id나 --all-published가 필요하다")
    if args.generation and len(run_ids) != 1:
        ap.error("--generation은 강의 하나일 때만 쓴다")
    client = None
    if not args.no_upload:
        import os
        from . import cycle, publish as publishing
        token = cycle.runner_token(args.token)
        if not token:
            print("러너 토큰이 없다. server/.env의 RUNNER_TOKEN이나 STUDYEZ_RUNNER_TOKEN 환경 변수, 또는 --token으로 준다")
            return 2
        api = (args.api or os.getenv("STUDYEZ_API_BASE_URL") or publishing.DEFAULT_API_BASE).rstrip("/")
        client = publishing.Client(api, token)
    print(f"순서 판정 {len(run_ids)}강의 · 함께 {max(1, args.workers)}: {', '.join(run_ids)}", flush=True)
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, len(run_ids)))) as pool:
        done = list(pool.map(lambda run_id: one(run_id, args, client), run_ids))
    failed = [r for r, state in zip(run_ids, done) if state == "failed"]
    skipped = done.count("skipped")
    print(f"순서 판정 끝: 성공 {done.count('done')} · 실패 {len(failed)}" + (f" ({', '.join(failed)})" if failed else "")
          + (f" · 이미 있음 {skipped}" if skipped else ""), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
