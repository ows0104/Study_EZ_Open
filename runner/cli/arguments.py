"""`python -m runner`의 명령과 옵션. 실행은 main.py에서 분기한다."""

import argparse

from runner import agent, blocks, deck, publish, watch

from . import DEFAULT_ROOT, REPO_ROOT
from .materials import OLDER_JOKBO_YEARS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Study_EZ 로컬 러너")
    parser.add_argument("command", choices=["match", "watch", "done", "jokbo", "preview", "agent",
                                            "prequeue", "publish", "import", "release", "rebuild",
                                            "chosen", "promote", "bank"])
    parser.add_argument("subject", nargs="?", help="과목 폴더명. --all이면 생략")
    parser.add_argument("--all", action="store_true", help="필기/올해 폴더가 있는 과목 전부")
    parser.add_argument("--this", default="2026", help="올해 폴더명")
    parser.add_argument("--prev", default="2025", help="작년 폴더명")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="자료 최상위 폴더")
    parser.add_argument("--practical", default="",
                        help="jokbo: 실습 족보 PDF 또는 그 PDF들이 든 폴더. "
                             "주면 실습 조각(PRAC)을 이것으로만 만든다")
    parser.add_argument("--older", default=",".join(OLDER_JOKBO_YEARS),
                        help="jokbo: 덧붙일 옛 판 족보의 해 폴더 (쉼표 구분). 빈 값이면 안 붙인다")
    parser.add_argument("--runs", default=str(REPO_ROOT / "runs"), help="산출물 루트")
    parser.add_argument("--build", action="store_true",
                        help="watch·prequeue: 자리만 세우지 말고 덱까지 만든다")
    parser.add_argument("--model", default="",
                        help="생성 작업의 GPT 모델 (기본: STUDYEZ_MODEL 또는 gpt-6.1-sol)")
    parser.add_argument("--strategy", default="auto",
                        choices=("auto", "기본", "필기", "필기 중심", "족보", "족보 중심",
                                 "사진", "사진 중심",
                                 "base", "annotation", "jokbo", "image", "photo"),
                        help="watch --run-id: 복습 덱 전략. 실습 사진 중심은 '사진'")
    parser.add_argument("--slides", default="",
                        help="watch --run-id: 새 판에서 고쳐졌다고 **사람이 알려준** 슬라이드 "
                             "(쉼표 구분). 코드가 못 보는 갈림(그림 픽셀만 바뀐 것)이 여기로 들어온다")
    parser.add_argument("--timeout", type=int, default=deck.DEFAULT_TIMEOUT,
                        help=f"watch·prequeue: 한 편의 제한 시간(초). 기본 {deck.DEFAULT_TIMEOUT}")
    parser.add_argument("--max", type=int, default=watch.DEFAULT_MAX_ITEMS,
                        help="watch·prequeue: 한 번에 만들 상한")
    parser.add_argument("--within-days", type=int, default=0,
                        help="prequeue: 강의가 오늘부터 이 날짜 안에 있는 것만 만든다")
    parser.add_argument("--now", action="store_true",
                        help="watch: 방금 올라온 파일도 포함 (동기화 대기 생략)")
    parser.add_argument("--no-jokbo", action="store_true",
                        help="watch --run-id: 과목 족보가 안 잘려 있어도 그냥 만든다. "
                             "기본은 멈추고 `runner jokbo <과목>`을 안내한다")
    parser.add_argument("--since", default=None,
                        help="watch: 이 날짜부터의 강의만 (YYYY-MM-DD). 주면 시간표를 안 본다")
    parser.add_argument("--until", default=None, help="watch: 이 날짜까지의 강의만")
    parser.add_argument("--all-dates", action="store_true",
                        help="watch: 블럭으로 좁히지 않는다. 지난 학기까지 전부 잡힌다")
    parser.add_argument("--today", default=None,
                        help="watch: 오늘을 이 날짜로 친다 (블럭 판정 확인용)")
    parser.add_argument("--timetable", default=None,
                        help=f"watch/agent/publish: 시간표 (기본 {blocks.DEFAULT_SOURCE})")
    parser.add_argument("--version", default="",
                        help="promote: 올릴 판 (예: 260827-2300). 생략하면 CHOSEN 이 고른 것")
    parser.add_argument("--keep", action="store_true",
                        help="chosen: 지금 runs/<편>/ 에 있는 시도를 쓴다고 적는다")
    parser.add_argument("--pick", default="",
                        help="chosen: 다른 시도를 골랐다고 적는다 (예: out/redo_260812_01)")
    parser.add_argument("--why", default="",
                        help="chosen: 왜 그것을 골랐는가. **없으면 안 적는다**")
    parser.add_argument("--url", default=None,
                        help="preview: 공유된 예습 대화 주소")
    parser.add_argument("--api", default=None,
                        help=f"publish: API 주소 (기본 {publish.DEFAULT_API_BASE})")
    parser.add_argument("--token", default=None,
                        help="publish: 러너 토큰 (기본 server/.env의 RUNNER_TOKEN)")
    parser.add_argument("--dry-run", action="store_true",
                        help="publish: 무엇이 올라갈지만 적고 올리지 않는다. "
                             "prequeue: 어느 자리에 설지만 적고 내려받기·빌드를 안 한다. "
                             "import: 무엇을 옮길지만 본다")
    parser.add_argument("--force", action="store_true",
                        help="publish: 이미 올린 표시를 무시하고 다시 올린다. "
                             "prequeue·watch: 이미 만든 편도 버리고 다시 만든다 (--run-id 필요)")
    parser.add_argument("--points-only", action="store_true", help="bank: 원본 독립 출제포인트만 미리 추출·저장")
    parser.add_argument('--import-share', action='store_true', help='bank: 저장된 공유 링크에서 완성 응답을 가져와 검수 작업 등록')
    parser.add_argument("--notes-only", action="store_true",
                        help="publish: 강의록만 올리고 덱·run-meta·예습 링크는 미룬다")
    parser.add_argument("--no-gate", action="store_true",
                        help="publish: 검문을 끄고 막힌 편도 민다 (사람이 보고 판단했을 때)")
    parser.add_argument("--run-id", default=None,
                        help="publish: 이 run을 쓰는 강의 한 편만 민다 (작년 run이면 그 짝). "
                             "prequeue: 이 강의의 예습 링크 하나만 (올해 run_id). "
                             "watch: 이 강의 하나만 만든다 — 블럭 창·하루 상한·이미 만든 "
                             "표시를 지난다 (올해 run_id)")
    parser.add_argument("--no-ahead", action="store_true",
                        help="publish·prequeue: 아직 필기가 없는 강의는 세우지 않는다 "
                             "(예습용 작년 강의록도 안 붙는다)")
    parser.add_argument("--no-publish", action="store_true",
                        help="done: 표시만 하고 올리지 않는다")
    parser.add_argument("--once", action="store_true",
                        help="agent: 한 바퀴만 돌고 끝낸다 (붙는지 볼 때)")
    parser.add_argument("--poll", type=int, default=agent.POLL_SECONDS,
                        help=f"agent: 일감을 물어보는 간격(초). 기본 {agent.POLL_SECONDS}")
    parser.add_argument("--sweep-minutes", type=int, default=agent.SWEEP_SECONDS // 60,
                        help=f"agent: 일감이 없을 때 남은 것을 쓸어 올리는 간격(분). "
                             f"기본 {agent.SWEEP_SECONDS // 60}")
    parser.add_argument("--no-sweep", action="store_true",
                        help="agent: 쓸기를 하지 않는다. 일감만 받는다")
    parser.add_argument("--workers", type=int, default=agent.WORKERS,
                        help=f"agent: 겹쳐 만들 편 수. 기본 {agent.WORKERS} "
                             "(서버도 같은 상한을 든다 — 둘 중 작은 쪽이 실제 상한이다)")
    parser.add_argument("--no-prequeue", action="store_true",
                        help="publish·done: 올리기 전에 예습 링크를 서버와 맞추는 단계를 "
                             "건너뛴다 (그 사이 링크가 바뀌었으면 옛 주소로 덮어쓴다)")
    parser.add_argument("--reflag", action="store_true",
                        help="rebuild: 검사 규칙이 늘었을 때 소프트 표시를 다시 계산해 덧붙인다")
    parser.add_argument("--from", dest="source_dir", default=None,
                        help="import: 덱을 옮겨 올 quizgen 작업 폴더 (예: ../PDF2ANKI/out)")
    return parser
