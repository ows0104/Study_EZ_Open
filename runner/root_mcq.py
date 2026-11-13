"""게시된 Main-Quiz 판에 「객관식 모드」 선지를 만들어 붙인다(2026-11-14, docs/changes/2026-11-14-mcq-mode).

출제 파이프라인 밖의 수동 명령이다. 판을 게시한 PC(`runs/_root-generation/`)에서 돌린다.
같은 과목의 게시된 판 전부에서 블록 재료(강의별 짧은 정답, `block-pool/1`)를 만들고, 강의마다 생성기
(`quizbank.root_mcq`)를 하위 프로세스로 돌려 결과 JSON 하나를 asset 종류 `root_mcq`(`<revision>.json`)로 올린다.
문항·판·검수 상한·학습 기록을 바꾸지 않는다. 서버는 선지가 없으면 그 문항을 지금처럼 보여 준다.

    python -m runner.root_mcq --all-published --subject 감염과 면역 --no-upload        # 만들기만
    python -m runner.root_mcq --all-published --subject 감염과 면역 --upload-only      # 만든 것을 올리기만
    python -m runner.root_mcq --all-published --subject 감염과 면역 --missing          # 만들고 올리기(올린 판은 건너뜀)
    python -m runner.root_mcq --run-id 261110_03 --sheet block_sheet.json --no-upload

`--sheet`는 블록 병원체 사실·함정 표(`block-sheet/1`, 선택)다. 결과는 `<실행>/mcq/`에 두고,
올리면 `<실행>/mcq/uploaded.json`에 판을 적는다.
"""
from __future__ import annotations

import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from . import transport
from .root_choices import _published, published_run, published_run_ids
from .subprocesses import run_forwarded

KIND = "root_mcq"
MARKER = "uploaded.json"
FOLDER = "mcq"


def upload(client: transport.Client, subject: str, run_id: str, path: Path) -> None:
    base = transport.lecture_path(subject, run_id)
    item = transport.Upload(KIND, path)
    signed = client.call("POST", f"{base}/uploads", [item.payload()])
    url = next(e["uploadUrl"] for e in signed["files"] if e["filename"] == item.filename)
    transport._put_with_retry(client, url, item)
    missing = client.call("POST", f"{base}/uploads/complete", [item.payload()]).get("missing", [])
    if missing:
        raise transport.PublishError(f"올렸는데 서버가 못 찾는다: {', '.join(missing)}")


def block_pool(runs: Path, subject: str) -> dict:
    """같은 과목의 게시된 판마다(강의당 가장 최근 게시) 짧은 정답 목록. `block-pool/1`."""
    from studyez_contracts.roots import mcq
    latest: dict[str, tuple] = {}
    for row in _published(runs, subject):
        run_id = row[2].get("runId")
        if run_id and (run_id not in latest or row[0] > latest[run_id][0]):
            latest[run_id] = row
    return {"schema": "block-pool/1", "subject": subject, "lectures": [
        {"run_id": run_id, "title": row[3]["document"].get("title", ""), "facts": mcq.lecture_facts(row[3]["document"])}
        for run_id, row in sorted(latest.items())]}


def build(document: dict, out: Path, run_id: str, *, block: Path | None, sheet: Path | None,
          model: str | None = None, rounds: int | None = None, run=run_forwarded) -> Path | None:
    out.mkdir(parents=True, exist_ok=True)
    doc_path = out / "document.json"
    doc_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    args = [sys.executable, "-m", "quizbank.root_mcq", "--document", str(doc_path.resolve()),
            "--run-id", run_id, "--out", str(out.resolve())]
    if block:
        args += ["--block", str(block.resolve())]
    if sheet:
        args += ["--sheet", str(sheet.resolve())]
    if model:
        args += ["--model", model]
    if rounds:
        args += ["--rounds", str(rounds)]
    if run(args, cwd=Path(__file__).resolve().parents[1]).returncode:
        return None
    named = out / f"{document['revision']}.json"
    shutil.copyfile(out / "mcq.json", named)
    return named


def uploaded(folder: Path, revision: str) -> bool:
    try:
        return json.loads((folder / FOLDER / MARKER).read_text(encoding="utf-8")).get("revision") == revision
    except (OSError, ValueError, AttributeError):
        return False


def _mark(path: Path, revision: str) -> None:
    (path.parent / MARKER).write_text(json.dumps({"revision": revision, "uploadedAt": datetime.now(UTC).isoformat()}),
                                      encoding="utf-8")


def one(run_id: str, args, client, block: Path | None) -> str:
    """강의 하나: "done"·"skipped"·"failed". 실패는 다른 강의를 멈추지 않는다."""
    try:
        folder, packet, payload = published_run(args.runs, run_id, args.subject, args.generation)
    except SystemExit as missing:
        print(missing, flush=True)
        return "failed"
    document = payload["document"]
    revision = document["revision"]
    if client is not None and uploaded(folder, revision) and (args.missing or args.upload_only):
        print(f"Main-Quiz {run_id}: 판 {revision} 객관식 선지 이미 올림 — 건너뜀", flush=True)
        return "skipped"
    out = folder / FOLDER
    try:
        if args.upload_only:
            path = out / f"{revision}.json"
            if not path.exists():
                print(f"Main-Quiz {run_id}: 만든 객관식 선지가 없다({path})", flush=True)
                return "failed"
        else:
            print(f"Main-Quiz {run_id}: 판 {revision} ({folder.name}) 객관식 선지 작성", flush=True)
            path = build(document, out, run_id, block=block, sheet=args.sheet, model=args.model, rounds=args.rounds)
            if path is None:
                print(f"Main-Quiz {run_id}: 객관식 선지 작성 실패", flush=True)
                return "failed"
        if client is None:
            print(f"{run_id} 만들기만 함: {path}", flush=True)
            return "done"
        upload(client, packet["subject"], run_id, path)
        _mark(path, revision)
        print(f"Main-Quiz {run_id}: 객관식 선지 업로드 완료 ({path.name})", flush=True)
        return "done"
    except Exception as error:  # noqa: BLE001 — 한 강의의 실패가 다른 강의를 멈추지 않는다
        print(f"Main-Quiz {run_id}: 객관식 선지 실패 — {error}", flush=True)
        return "failed"


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="게시된 Main-Quiz 판에 객관식 모드 선지를 만들어 붙인다")
    ap.add_argument("--run-id", action="append", default=[], help="여러 번 줄 수 있다")
    ap.add_argument("--all-published", action="store_true", help="--subject 과목에서 이 PC가 게시한 강의 전부")
    ap.add_argument("--subject", help="블록 재료를 모을 과목. --all-published에는 필수")
    ap.add_argument("--generation", help="runs/_root-generation의 실행 ID를 직접 지정(강의 하나일 때)")
    ap.add_argument("--runs", type=Path, default=Path("runs"))
    ap.add_argument("--sheet", type=Path, help="블록 병원체 사실·함정 표(block-sheet/1)")
    ap.add_argument("--workers", type=int, default=3, help="함께 도는 강의 수")
    ap.add_argument("--rounds", type=int, help="작성 회차(기본 2: 모자란 문항을 한 번 더)")
    ap.add_argument("--model")
    ap.add_argument("--no-upload", action="store_true", help="만들기만 하고 올리지 않는다")
    ap.add_argument("--upload-only", action="store_true", help="이미 만든 선지를 올리기만 한다")
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
    block = None
    if args.subject and not args.upload_only:
        block = args.runs / "_root-generation" / f"block-pool-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}.json"
        pool = block_pool(args.runs, args.subject)
        block.write_text(json.dumps(pool, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"블록 재료: {len(pool['lectures'])}강의 ({block})", flush=True)
    print(f"객관식 선지 {len(run_ids)}강의 · 함께 {max(1, args.workers)}: {', '.join(run_ids)}", flush=True)
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, len(run_ids)))) as pool:
        done = list(pool.map(lambda run_id: one(run_id, args, client, block), run_ids))
    failed = [r for r, state in zip(run_ids, done) if state == "failed"]
    skipped = done.count("skipped")
    print(f"객관식 선지 끝: 성공 {done.count('done')} · 실패 {len(failed)}" + (f" ({', '.join(failed)})" if failed else "")
          + (f" · 이미 있음 {skipped}" if skipped else ""), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
