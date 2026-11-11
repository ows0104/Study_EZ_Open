"""이미 게시된 Main-Quiz 판에 단답·나열 문항의 「선지 보기」용 선지를 만들어 붙인다(2026-11-12).

출제 파이프라인과 따로 도는 수동 명령이다(사용자 2026-11-12 「파이프라인에 영향을 안 주고」). 러너의 게시 경로는
이 모듈을 부르지 않는다. 강의 하나를 지정하면 그 강의의 게시된 실행(`runs/_root-generation/<gid>/`)에서
판 문서를 읽고, 생성기(`quizbank.root_choices`)를 하위 프로세스로 돌려 결과 JSON 하나를 asset 종류
`root_choices`(`<revision>.json`)로 기존 업로드 경로에 올린다. 문항·판·검수 상한·학습 기록을 바꾸지 않는다.
서버는 선지가 없으면 지금처럼 문제만 보여 준다.

    python -m runner.root_choices --run-id 261110_03 --no-upload   # 만들어 보기만(올리지 않음)
    python -m runner.root_choices --run-id 261110_03               # 만들어 올리기
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
    """선지를 만들어 올린다. 어떤 실패도 예외로 올리지 않고 로그만 남긴다."""
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


def published_run(runs: Path, run_id: str, subject: str | None = None, generation: str | None = None) -> tuple[Path, dict, dict]:
    """이 강의의 게시된 실행 폴더·packet·결과. 게시 응답의 판과 결과 문서의 판이 같은 것만, 여럿이면 가장 최근 게시."""
    found = []
    for folder in sorted((runs / "_root-generation").glob("*/")):
        if generation and folder.name != generation:
            continue
        try:
            packet = json.loads((folder / "packet.json").read_text(encoding="utf-8"))
            posted = json.loads((folder / "published.json").read_text(encoding="utf-8"))
            result_path = next(p for p in (folder / "generation" / "result.json", folder / "result.json") if p.exists())
        except (OSError, ValueError, StopIteration):
            continue
        if packet.get("runId") != run_id or (subject and packet.get("subject") != subject) or posted.get("status") != "ready":
            continue
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        if payload.get("document", {}).get("revision") != posted.get("revision"):
            continue
        found.append(((folder / "published.json").stat().st_mtime, folder, packet, payload))
    if not found:
        raise SystemExit(f"{run_id}: 게시된 Main-Quiz 실행을 runs/_root-generation에서 찾지 못했다")
    _, folder, packet, payload = max(found, key=lambda row: row[0])
    return folder, packet, payload


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="이미 게시된 Main-Quiz 판에 단답·나열 선지를 만들어 붙인다")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--subject", help="같은 run ID가 여러 과목에 있을 때")
    ap.add_argument("--generation", help="runs/_root-generation의 실행 ID를 직접 지정")
    ap.add_argument("--runs", type=Path, default=Path("runs"))
    ap.add_argument("--model")
    ap.add_argument("--no-upload", action="store_true", help="만들기만 하고 올리지 않는다")
    ap.add_argument("--api")
    ap.add_argument("--token")
    args = ap.parse_args(argv)
    folder, packet, payload = published_run(args.runs, args.run_id, args.subject, args.generation)
    document = payload["document"]
    print(f"Main-Quiz {args.run_id}: 판 {document['revision']} ({folder.name}) 선지 작성", flush=True)
    if args.no_upload:
        path = build(document, folder / "choices", args.run_id, model=args.model)
        print(f"만들기만 함: {path}" if path else "선지 작성 실패", flush=True)
        return 0 if path else 1
    import os
    from . import cycle, publish as publishing
    token = cycle.runner_token(args.token)
    if not token:
        print("러너 토큰이 없다. server/.env의 RUNNER_TOKEN이나 STUDYEZ_RUNNER_TOKEN 환경 변수, 또는 --token으로 준다")
        return 2
    api = (args.api or os.getenv("STUDYEZ_API_BASE_URL") or publishing.DEFAULT_API_BASE).rstrip("/")
    ok = publish(publishing.Client(api, token), packet["subject"], args.run_id, folder, payload, model=args.model)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
