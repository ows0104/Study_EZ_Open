"""`runs/<편>/` 안에서 무엇이 어디 있는가. **묻는 자리를 하나로 둔다.**

`docs/runs-layout.md` 5단계다. 그 문서가 「왜 바꾸나」의 ③으로 적어 둔 것이 여기서
풀린다.

> **③ 강의 것과 시도 것이 한 폴더에 섞여 있다.** `runs/260812_02/`에 파일이
> 31개인데 성격이 둘이다. … **섞여 있어서 「다시 돌리기」가 위험하다.** 덮어쓰면
> 사람이 넣은 `preview.md`나 `HOLD`가 날아갈 수 있다.

## 두 성격을 코드가 구별하게 한다

    강의 것    시도가 바뀌어도 남아야 한다. 파이프라인이 **다시 만들 수 없다**
    시도 것    다시 만들면 새로 생긴다. 한 번의 실행이 낸 것 전부

**이 구별이 없어서 실제로 위험했다.** `runner import` 가 그 자리를 비우면서
남기는 것을 둘만 알고 있었다(`preview.md`·`pre_target.json`). 그래서 `HOLD` 가
지워질 수 있었는데, `.gitignore` 는 그 파일을 이렇게 적어 두고 있다 —
*"파이프라인이 다시 만들 수 없다 … 잃으면 막아 둔 이유를 아무도 모른 채 덱이
나간다."* 2026-09-15 에 `CHOSEN.json` 이 같은 자리에 하나 더 놓였다.

## 두 모양을 같이 읽는다

옛 모양은 시도 것이 강의 폴더에 그대로 널려 있다. 새 모양은 판마다 갈라 둔다.

    옛  runs/260812_01/prep.json                      ← 127편이 이 모양이다
    새  runs/260812_01/main/260827-2300/prep.json
        runs/260812_01/prequiz/260826-0410/prep.json

**둘을 같이 읽는 이유는 한 번에 안 갈아도 되게 하려는 것이다.** 반쯤 옮긴 나무에서도
파이프라인이 돈다 — `work_dir` 이 새 자리를 먼저 보고 없으면 옛 자리를 준다.
`docs/runs-layout.md` 의 이행 순서가 그렇게 적어 두었다(*"한 번에 안 갈아도 된다"*).

## 루트에 남는 것은 「지금 나가는 것」이다

`run.meta.json` 과 `.apkg` 가 강의 바로 밑에 있는 이유는 그 문서가 적어 두었다 —
**`publish` 와 `gate` 가 읽는 자리를 안 바꾸려는 것**이고 서버 계약
(`docs/artifact-contract.md`)도 그대로 산다. 서버는 `runs/` 를 아예 안 본다
(2026-09-15 확인 — `server/app` 에 `runs` 라는 글자가 없다).
"""

from __future__ import annotations

import re
from pathlib import Path

MAIN = "main"
PREQUIZ = "prequiz"

# **새 실행이 판 폴더에 쓴다.** 2026-09-15 에 켰다.
#
# 켜기 전까지 `deck.run_main` 이 `--out` 으로 강의 폴더를 그대로 넘겼고, 그래서
# **옮기면 안 되는 상태**였다 — 옮긴 편에 새 실행이 강의 폴더로 쓰면 `find` 가 판
# 폴더를 먼저 보므로 그 새 산출물이 **조용히 무시된다.** 그 함정을 열어 두지 않으려고
# `scripts/migrate_attempts.py` 가 이 값이 거짓인 동안 `--apply` 를 거부했다.
#
# 켜는 데 셋이 같이 왔다.
#
#   ① `deck.new_work_dir` 이 판 폴더를 정하고 `--out` 이 그것을 가리킨다.
#      **`--resume` 은 새 판을 안 연다** — 이어 돌리는 것은 그 시도를 계속하는 것이다
#   ② `deck.promote` 가 그 시도의 덱을 강의 폴더로 올린다. 나머지 계약은
#      `deck.contract` 가 원래 읽어서 다시 쓰던 것이라 옮길 것이 없었다
#   ③ `work_dir` 이 `CHOSEN.json` 이 고른 판을 먼저 보고 `chosen.verdict` 도 같은
#      자리를 본다 — 「고른 것」과 「올라간 것」이 어긋나면 문지기가 막는다
#
# **되돌리려면 이 값을 거짓으로 두면 된다.** 이미 옮긴 편은 `find` 가 판 폴더를 먼저
# 보므로 그대로 읽히고 새 실행만 강의 폴더로 돌아간다 — 다만 그때 그 편에 「가려진
# 산출물」이 생기므로, 되돌린 뒤 `migrate_attempts` 를 한 번 더 돌려 접어야 한다.
WRITES_ATTEMPT_DIRS = True

# 판. `cut_id` 와 같은 규칙이다 — 날짜만으로는 하루에 두 번 돌린 것이 겹친다
# (`quizgen/cutmark.new_cut_id`).
RE_VERSION = re.compile(r"^\d{6}-\d{4}(\.\d+)?$")

# ── 강의 것 ────────────────────────────────────────────────────────────
#
# **파이프라인이 다시 만들 수 없는 것**과 **지금 나가는 산출물**이다. 시도를 다시
# 돌려도 남아야 하고, 폴더를 비울 때 살아남아야 한다.
#
# 사람이 만든 것 / 남의 서비스에서 받아 온 것:
HUMAN_FILES = frozenset({
    "HOLD",             # 사람이 놓은 배포 보류. **안에 적힌 글이 그대로 사유다**
    "CHOSEN.json",      # 어느 시도를 왜 골랐나 (`chosen.py`). 2026-09-15
    "preview.md",       # 공유된 예습 대화. 다시 못 받는다
    "pre_target.json",  # 작년 것으로 만든 예습을 올해 어느 강의에 붙이나
    "note.md",          # 사람이 그 편에 적어 둔 지시
})

# 지금 나가는 산출물. `publish`·`gate`·서버 계약이 이 자리를 본다.
PUBLISHED_FILES = frozenset({
    "run.meta.json", "pre_run.meta.json",
    "main_items.final.json", "pre_items.final.json",
    "source.json",      # 어느 파일 몇 판으로 만들었나 (`fingerprint`)
})
PUBLISHED_DIRS = frozenset({"slides"})

# 러너가 지금 이 자리를 만들고 있다는 표시. 지우면 두 일꾼이 같은 편을 잡는다.
RUNTIME_FILES = frozenset({"BUILDING"})


def is_lecture_own(name: str) -> bool:
    """강의 것인가. **비울 때 남겨야 하는 것**이 정확히 이 집합이다.

    `.apkg` 는 이름이 강의마다 달라(`[260812_01] 병리학 소개(정경천).apkg`)
    집합으로 못 적는다. 확장자로 본다.
    """
    return (name in HUMAN_FILES or name in PUBLISHED_FILES
            or name in PUBLISHED_DIRS or name in RUNTIME_FILES
            or name.endswith(".apkg"))


# ── 시도가 사는 자리 ───────────────────────────────────────────────────
def new_version(when=None) -> str:
    """새 판 이름. `cutmark.new_cut_id` 와 같은 규칙이다 — 날짜+시각."""
    import datetime as dt
    return f"{when or dt.datetime.now():%y%m%d-%H%M}"


def attempt_root(run_dir: Path, kind: str = MAIN) -> Path:
    """그 갈래의 시도들이 들어가는 폴더. 있는지는 안 본다."""
    return Path(run_dir) / kind


def versions(run_dir: Path, kind: str = MAIN) -> list[str]:
    """그 갈래의 판, 이름순(= 시간순). 없으면 빈 목록 — **옛 모양이다.**"""
    root = attempt_root(run_dir, kind)
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir()
                  if p.is_dir() and RE_VERSION.match(p.name))


def work_dir(run_dir: Path, kind: str = MAIN, version: str | None = None) -> Path:
    """그 갈래의 작업 폴더 — **지금 나가는 덱을 만든 시도**의 자리.

    `version` 을 안 주면 이 순서로 고른다.

        ① `CHOSEN.json` 이 고른 시도       사람이 적어 둔 것이 제일 세다
        ② `run.meta.json` 의 `attempt`     지금 나가는 덱을 만든 판
        ③ 제일 새 판 (이름순의 끝)         둘 다 없으면
        ④ 강의 폴더 자신                   판이 하나도 없으면 — 옛 모양이다

    **②가 없으면 미완성 실험이 정본이 된다.** 2026-09-15 에 실제 트리를 접자마자
    나왔다 — `260901_01` 은 cloze 프롬프트를 아홉 번 돌린 편이라 판이 11개인데, 그중
    **이름이 제일 새 것(`260906-1619`)에 `prep.json` 도 `run.config.json` 도 없다.**
    카드만 남은 실험 폴더다. ③만 있으면 그 판이 작업 폴더가 되어 `deck.source_pdf` 가
    빈 값을 돌려주고, 그러면 `publish._owns` 가 **주인을 확인할 수 없다**고 본다.

    **①이 없으면 틀린다.** 2026-09-14 에 실컷 시험에서 잡았다 — `out/` 의 시도를
    접어 넣으면 그중 제일 새것이 「제일 새 판」이 되고, 그러면 `deck.contract` 가
    **배포 중인 덱과 다른 시도의 카드로** 계약을 다시 쓴다. 그 편은 83장으로
    나가 있는데 58장짜리 시도가 들어오면서 `item_count` 가 58이 됐다.
    `docs/runs-layout.md` 가 4단계(`CHOSEN`)를 5단계(폴더 이동)보다 앞에 둔 이유가
    이것이다 — 판이 여럿이 되는 순간 「어느 것이 정본인가」에 답이 있어야 한다.

    **「제일 새 판」은 이름순의 끝이다.** mtime 으로 고르지 않는다 — 파일을 옮기거나
    복사하면 mtime 이 뒤집힌다(`runner/fingerprint.py` 가 실측으로 적어 둔 자리).
    """
    run_dir = Path(run_dir)
    if version:
        return attempt_root(run_dir, kind) / version
    found = versions(run_dir, kind)
    if not found:
        return run_dir
    picked = (_chosen_version(run_dir, kind, found)
              or _published_version(run_dir, kind, found)
              or _newest_whole(run_dir, kind, found))
    return attempt_root(run_dir, kind) / picked


def _newest_whole(run_dir: Path, kind: str, found: list[str]) -> str:
    """제일 새 판. 단 **설정 파일이 있는 판만** 센다.

    `run.config.json` 이 없는 판은 카드만 남은 실험 폴더다 — 그것이 작업 폴더가 되면
    `deck.source_pdf` 가 빈 값을 내고 `publish` 가 주인을 확인할 수 없게 된다
    (`work_dir` 머리의 `260901_01` 사례).

    **온전한 판이 하나도 없으면 그냥 제일 새것을 준다.** 모르는 자리에서 골라 주지
    않는 것보다 무엇이든 주고 위의 계수기가 울게 두는 편이 낫다 — 조용히 빈 값을
    돌려주면 그 편만 이유 없이 안 나간다.
    """
    cfg = "prequiz.config.json" if kind == PREQUIZ else "run.config.json"
    whole = [v for v in found if (attempt_root(run_dir, kind) / v / cfg).is_file()]
    return (whole or found)[-1]


def _published_version(run_dir: Path, kind: str, found: list[str]) -> str | None:
    """계약이 「이 덱은 이 판으로 만들었다」고 적어 둔 판. 없으면 None.

    `deck.contract` 가 `run.meta.json` 의 `attempt` 에 적는다(2026-09-15부터).
    그 전에 쓰인 계약에는 없으므로 `None` 이 정상이다.
    """
    import json

    name = "pre_run.meta.json" if kind == PREQUIZ else "run.meta.json"
    try:
        meta = json.loads((Path(run_dir) / name).read_text(encoding="utf-8"))
        mark = meta.get("attempt") or {}
        v = str(mark.get("version") or "")
    except (OSError, ValueError, AttributeError):
        return None
    return v if v in found else None


def _chosen_version(run_dir: Path, kind: str, found: list[str]) -> str | None:
    """`CHOSEN.json` 이 고른 시도가 이 판들 중 어느 것인가. 없으면 None.

    **경로가 아니라 카드 해시로 맞춘다.** 기록에 적힌 경로는 고를 때의 자리
    (`out/redo_260812_01`)이고 옮긴 뒤에는 그 경로가 없다 — `chosen.py` 가 판정을
    해시로 하는 것과 같은 이유다.
    """
    import hashlib
    import json

    p = Path(run_dir) / "CHOSEN.json"
    if not p.is_file():
        return None
    try:
        rec = json.loads(p.read_text(encoding="utf-8"))
        want = ((rec.get("publish") or {}).get(kind) or {}).get("cards_sha256")
    except (OSError, ValueError, AttributeError):
        return None
    if not want:
        return None
    for v in found:
        cards = attempt_root(run_dir, kind) / v / "items.raw.json"
        try:
            if hashlib.sha256(cards.read_bytes()).hexdigest() == want:
                return v
        except OSError:
            continue
    return None


def is_migrated(run_dir: Path, kind: str = MAIN) -> bool:
    """그 갈래가 새 모양으로 옮겨졌나."""
    return bool(versions(run_dir, kind))


def find(run_dir: Path, name: str, kind: str = MAIN) -> Path | None:
    """시도 것 하나를 찾는다. 새 자리 → 옛 자리 순. 없으면 None.

    **강의 것을 여기로 묻지 마라** — 그것은 늘 `run_dir / name` 이다. 섞어 묻게
    두면 「어느 판의 HOLD 인가」 같은 없는 질문이 생긴다.
    """
    if is_lecture_own(name):
        p = Path(run_dir) / name
        return p if p.exists() else None
    for base in (work_dir(Path(run_dir), kind), Path(run_dir)):
        p = base / name
        if p.exists():
            return p
    return None


def attempt_dirs(run_dir: Path) -> list[tuple[str, str, Path]]:
    """그 편의 시도 전부. `(갈래, 판, 폴더)`. 옛 모양이면 빈 목록."""
    found = []
    for kind in (MAIN, PREQUIZ):
        for v in versions(run_dir, kind):
            found.append((kind, v, attempt_root(run_dir, kind) / v))
    return found


def kind_of(work: Path) -> str:
    """그 작업 폴더가 복습이냐 예습이냐. 폴더 안의 설정 파일이 말한다."""
    work = Path(work)
    if (work / "prequiz.config.json").is_file():
        return PREQUIZ
    return MAIN
