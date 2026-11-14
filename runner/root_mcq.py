"""Main-Quiz 판에 선지(주관식 「선지 보기」·객관식 모드 공용)를 만들어 붙인다.

2026-11-14 객관식 모드(docs/changes/2026-11-14-mcq-mode)로 시작해 같은 날 두 선지 기능을 합쳤다
(docs/changes/2026-11-14-choices-merge, `root-mcq/2`). 러너가 판을 게시한 직후 `publish`를 기본으로 부르고
(`runner/connection_generation.py`), 아래 수동 명령은 이미 게시된 판에 다시 붙이거나 빠진 강의를 채울 때 쓴다.
판을 게시한 PC(`runs/_root-generation/`)에서 돈다. 같은 과목의 게시된 판 전부에서 블록 재료(강의별 짧은 정답, `block-pool/1`)와
족보 PDF 목록(`jokbo-sources/1`)을 만들고, 강의마다 생성기(`quizbank.root_mcq`)를 하위 프로세스로 돌려
결과 JSON 하나를 asset 종류 `root_mcq`(`<revision>.json`)로 올린다.
문항·판·검수 상한·학습 기록을 바꾸지 않는다. 서버는 선지가 없으면 그 문항을 지금처럼 보여 준다.
v1 파일이 있던 자리에 v2를 만들면 v1은 `mcq/v1-<revision>.json`으로 남긴다(되올리기용).

    python -m runner.root_mcq --all-published --subject 감염과 면역 --no-upload        # 만들기만
    python -m runner.root_mcq --all-published --subject 감염과 면역 --upload-only      # 만든 것을 올리기만
    python -m runner.root_mcq --all-published --subject 감염과 면역 --missing          # 만들고 올리기(올린 판은 건너뜀)
    python -m runner.root_mcq --run-id 261110_03 --sheet block_sheet.json --no-upload

`--sheet`는 블록 병원체 사실·함정 표(`block-sheet/1`, 선택)다. 결과는 `<실행>/mcq/`에 두고,
올리면 `<실행>/mcq/uploaded.json`에 판과 schema를 적는다. `--missing`은 현재 판에 v2를 올린 기록이 있을 때만 건너뛴다.
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
SCHEMA = "root-mcq/2"


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
    return {"schema": "block-pool/1", "subject": subject, "lectures": [
        {"run_id": run_id, "title": row[3]["document"].get("title", ""), "facts": mcq.lecture_facts(row[3]["document"])}
        for run_id, row in sorted(_latest(runs, subject).items())]}


def _latest(runs: Path, subject: str) -> dict[str, tuple]:
    latest: dict[str, tuple] = {}
    for row in _published(runs, subject):
        run_id = row[2].get("runId")
        if run_id and (run_id not in latest or row[0] > latest[run_id][0]):
            latest[run_id] = row
    return latest


def jokbo_sources(runs: Path, subject: str) -> dict:
    """같은 과목의 게시된 판마다(강의당 가장 최근 게시) 실행 packet의 족보 PDF. `jokbo-sources/1`."""
    lectures = []
    for run_id, row in sorted(_latest(runs, subject).items()):
        pdfs = [{"path": s["localPath"], "sha256": s.get("sha256", ""), "filename": s.get("filename", "")}
                for s in row[2].get("sources", [])
                if s.get("kind") == "jokbo" and s.get("localPath") and Path(s["localPath"]).is_file()]
        lectures.append({"run_id": run_id, "title": row[3]["document"].get("title", ""), "pdfs": pdfs})
    return {"schema": "jokbo-sources/1", "subject": subject, "lectures": lectures}


def evidence_path(folder: Path) -> Path | None:
    """이 실행의 근거 asset(문항별 족보 연결). 중복 재판정 판처럼 근거를 앞 판에서 가져온 실행에는 없다."""
    return next((p for p in (folder / "generation" / "evidence" / "evidence.json", folder / "evidence" / "evidence.json")
                 if p.is_file()), None)


def materials(runs: Path, subject: str) -> tuple[Path, Path]:
    """블록 재료와 족보 목록을 파일로 쓴다(생성기 하위 프로세스가 읽는다)."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    folder = runs / "_root-generation"
    block, jokbo = folder / f"block-pool-{stamp}.json", folder / f"jokbo-sources-{stamp}.json"
    block.write_text(json.dumps(block_pool(runs, subject), ensure_ascii=False, indent=1), encoding="utf-8")
    jokbo.write_text(json.dumps(jokbo_sources(runs, subject), ensure_ascii=False, indent=1), encoding="utf-8")
    return block, jokbo


def _keep_v1(named: Path) -> None:
    """v1 선지 파일을 v2로 덮기 전에 `v1-<revision>.json`으로 남긴다(되올리기용)."""
    try:
        if json.loads(named.read_text(encoding="utf-8")).get("schema") == "root-mcq/1":
            backup = named.with_name(f"v1-{named.name}")
            if not backup.exists():
                shutil.copyfile(named, backup)
    except (OSError, ValueError):
        pass


def build(document: dict, out: Path, run_id: str, *, block: Path | None, sheet: Path | None,
          jokbo: Path | None = None, evidence: Path | None = None,
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
    if jokbo:
        args += ["--jokbo-sources", str(jokbo.resolve())]
    if evidence:
        args += ["--evidence", str(evidence.resolve())]
    if model:
        args += ["--model", model]
    if rounds:
        args += ["--rounds", str(rounds)]
    if run(args, cwd=Path(__file__).resolve().parents[1]).returncode:
        return None
    named = out / f"{document['revision']}.json"
    _keep_v1(named)
    shutil.copyfile(out / "mcq.json", named)
    return named


def uploaded(folder: Path, revision: str) -> bool:
    """현재 판에 v2 선지를 올린 기록이 있나. schema가 없는 표시는 v1 때 것이다."""
    try:
        mark = json.loads((folder / FOLDER / MARKER).read_text(encoding="utf-8"))
        return mark.get("revision") == revision and mark.get("schema") == SCHEMA
    except (OSError, ValueError, AttributeError):
        return False


def _mark(path: Path, revision: str) -> None:
    try:
        schema = json.loads(path.read_text(encoding="utf-8")).get("schema")
    except (OSError, ValueError):
        schema = None
    (path.parent / MARKER).write_text(json.dumps({"revision": revision, "schema": schema,
                                                  "uploadedAt": datetime.now(UTC).isoformat()}), encoding="utf-8")


def publish(client: transport.Client, subject: str, run_id: str, folder: Path, payload: dict,
            *, model: str | None = None, run=run_forwarded) -> bool:
    """러너가 판을 게시한 직후 부른다(선지 기본 실행, 2026-11-14). 어떤 실패도 예외로 올리지 않고 로그만 남긴다."""
    try:
        document = payload["document"]
        print(f"Quiz Bank {run_id}: 선지(주관식·객관식 공용) 작성", flush=True)
        block, jokbo = materials(folder.parents[1], subject)
        path = build(document, folder / FOLDER, run_id, block=block, sheet=None, jokbo=jokbo,
                     evidence=evidence_path(folder), model=model, run=run)
        if path is None:
            print(f"Quiz Bank {run_id}: 선지 작성 실패 — 판은 게시됨, 선지 없이 표시", flush=True)
            return False
        upload(client, subject, run_id, path)
        _mark(path, document["revision"])
        print(f"Quiz Bank {run_id}: 선지 업로드 완료 ({path.name})", flush=True)
        return True
    except Exception as error:  # noqa: BLE001 — 게시를 되돌리지 않는다
        print(f"Quiz Bank {run_id}: 선지 작성 실패 — {error}", flush=True)
        return False


def one(run_id: str, args, client, block: Path | None, jokbo: Path | None = None) -> str:
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
            path = build(document, out, run_id, block=block, sheet=args.sheet, jokbo=jokbo,
                         evidence=evidence_path(folder), model=args.model, rounds=args.rounds)
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
    block = jokbo = None
    if args.subject and not args.upload_only:
        block, jokbo = materials(args.runs, args.subject)
        lectures = json.loads(jokbo.read_text(encoding="utf-8"))["lectures"]
        print(f"블록 재료: {len(lectures)}강의 ({block}) · 족보 PDF {sum(len(x['pdfs']) for x in lectures)}개", flush=True)
    print(f"객관식 선지 {len(run_ids)}강의 · 함께 {max(1, args.workers)}: {', '.join(run_ids)}", flush=True)
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, len(run_ids)))) as pool:
        done = list(pool.map(lambda run_id: one(run_id, args, client, block, jokbo), run_ids))
    failed = [r for r, state in zip(run_ids, done) if state == "failed"]
    skipped = done.count("skipped")
    print(f"객관식 선지 끝: 성공 {done.count('done')} · 실패 {len(failed)}" + (f" ({', '.join(failed)})" if failed else "")
          + (f" · 이미 있음 {skipped}" if skipped else ""), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
