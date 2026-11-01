"""Runner CLI의 실행 분기. 옵션은 arguments, 세부 구현은 materials/artifacts에 둔다."""

from __future__ import annotations

import os
from pathlib import Path

from runner import bank, cycle, filenames, publish

from .arguments import build_parser
from .artifacts import run_chosen, run_import, run_promote, run_rebuild, run_release
from .materials import report_subject, run_jokbo, run_preview


def run_bank(args, parser) -> int:
    """`bank <과목> --run-id …` — 관리자가 넣은 ChatGPT 응답을 정리·검토해 올린다(`runner/bank.py`)."""
    if not args.subject or not args.run_id:
        parser.error("bank 는 과목명과 --run-id 가 필요합니다")
    api = (args.api or os.getenv("STUDYEZ_API_BASE_URL") or publish.DEFAULT_API_BASE).rstrip("/")
    token = cycle.runner_token(args.token)
    if not token:
        print("러너 토큰이 없다. server/.env의 RUNNER_TOKEN이나 STUDYEZ_RUNNER_TOKEN 환경 변수, 또는 --token")
        return 2
    if getattr(args, 'import_share', False):
        from runner.shared_bank import recover
        client = publish.Client(api, token)
        base = publish.lecture_path(args.subject, args.run_id)
        got = client.call('GET', f'{base}/bank/shared-source')
        backup = Path(args.runs) / args.run_id / 'bank' / 'share-import-before.json'
        backup.parent.mkdir(parents=True, exist_ok=True)
        import json
        if not backup.exists():
            backup.write_text(json.dumps(got, ensure_ascii=False, indent=2), encoding='utf-8')
        recovered = recover(client, base, args.run_id, got, force=True)
        if recovered.get('shareUnchanged'):
            print(f"공유 응답이 기존 게시본과 같습니다: {args.subject}/{args.run_id} · 재검수 생략")
            return 0
        print(f"공유 응답 저장·러너 등록 완료: {args.subject}/{args.run_id} · {len(recovered['raw'])}자")
        return 0
    action = bank.prepare_points if args.points_only else bank.run
    return action(publish.Client(api, token), Path(args.root), args.subject, args.run_id,
                  args.this, args.prev, Path(args.runs), model=args.model)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # 이름을 직접 대도 막는다. 실수로 한 번 돌리면 재고에 섞여 들어가고,
    # 그 뒤로는 왜 거기 있는지 아무도 모른다.
    if args.subject and filenames.is_excluded(args.subject):
        print(f"[{args.subject}] 학생마다 듣는 것이 달라 파이프라인에서 뺀 과목이다.\n"
              "  강의록 연결·예습·복습 어느 것도 만들지 않는다.\n"
              "  정말 필요하면 runner/filenames.py의 EXCLUDED_SUBJECTS·"
              "EXCLUDED_PREFIXES를 고쳐라.")
        return 0

    if args.command == "watch":
        return cycle.report_watch(args)
    if args.command == "done":
        return cycle.run_done(args)
    if args.command == "jokbo":
        return run_jokbo(args)
    if args.command == "preview":
        return run_preview(args)
    if args.command == "prequeue":
        return cycle.report_prequeue(args)
    if args.command == "agent":
        return cycle.run_agent(args)
    if args.command == "import":
        return run_import(args)
    if args.command == "chosen":
        return run_chosen(args)
    if args.command == "promote":
        return run_promote(args)
    if args.command == "release":
        return run_release(args)
    if args.command == "rebuild":
        return run_rebuild(args)
    if args.command == "bank":
        return run_bank(args, parser)
    if args.command == "publish":
        if not args.subject and not args.all and not args.run_id:
            parser.error("과목명을 주거나 --all 또는 --run-id를 쓰세요")
        return cycle.report_publish(args)

    root = Path(args.root)
    if args.all:
        subjects = cycle.subjects_with_notes(root, args.this)
    elif args.subject:
        subjects = [args.subject]
    else:
        parser.error("과목명을 주거나 --all을 쓰세요")

    needs_review = 0
    for subject in subjects:
        needs_review += report_subject(root, subject, args.this, args.prev, Path(args.runs))

    print(f"\n손봐야 할 강의 {needs_review}편")
    return 0
