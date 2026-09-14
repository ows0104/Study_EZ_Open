"""어느 시도를 왜 골랐는지 적는다 — `runs/<편>/CHOSEN.json`.

`docs/runs-layout.md` 4단계이고, 그 문서가 「왜 바꾸나」의 **④**로 적어 둔 자리다.

> **어느 시도가 왜 이겼는지 적는 자리가 없다.** 지금 「정본」은 *어쩌다
> `runs/<id>/`에 놓여 있는 것*이다.

## 두 질문에 답한다. 섞으면 나중에 갈린다

    publish   무엇을 올릴 것인가          시도 하나를 가리킨다 + **사람이 적은 why**
    current   다음에 돌릴 때 무엇을 쓸까    지금은 족보 컷 하나다

## 경로가 아니라 카드 해시로 가리킨다

고른 시도를 `path` 로만 적으면, 그 카드를 `runs/<편>/` 으로 옮겨 놓은 뒤에도
「고른 것과 다른 것이 나간다」고 말한다. 시도의 신원은 `items.raw.json` 의 내용
해시다(`attempts.py` 머리). 그래서 **경로는 사람이 읽는 값이고 판정은 해시로 한다** —
카드를 옮기면 그 자리에서 저절로 맞는다.

## 문지기가 본다. 없으면 지금과 똑같이 돈다

그 문서의 4단계가 이렇게 적었다 — *"`publish`가 CHOSEN을 보되 없으면 지금처럼
동작하게 두면 한 번에 안 갈아도 된다."* 그대로다.

    CHOSEN 이 없다              지금과 같다. 아무 말도 안 한다
    고른 것이 그 자리에 있다      지난다
    고른 것이 다른 자리에 있다    **덱을 미룬다** (강의록은 나간다)

**마지막 줄을 적기만 하는 것으로 두지 않은 이유**는 이 저장소가 같은 실패를 세 번
했기 때문이다 — 편마다 경고가 떴고 아무도 안 봤다(`runner/CLAUDE.md`). 2026-08-27
에 다시 구운 25편이 **한 번도 안 나간 것**을 09-14 에야 찾았는데, 그때도 화면에는
아무 말이 없었다. 사람이 「이걸 내라」고 적어 둔 것과 나가는 것이 다르면 그것은
**산출물이 자기 주장과 다른 경우**와 같은 급이다.

## `why` 는 코드가 쓰지 않는다

그 문서가 그렇게 정해 두었고 이유도 적어 두었다 — 무엇이 좋은 시도인지가 아직 안
정해졌고, 지표 하나를 임의로 고르면 근거 없는 규칙이 된다. 그래서 `why` 없이는
기록을 안 만든다. 재어 둔 값은 `considered` 에 **원값으로만** 같이 적힌다.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from . import attempts as att
from . import runlayout

CHOSEN_FILE = "CHOSEN.json"

MAIN = "main"
PREQUIZ = "prequiz"


def path_of(run_dir: Path) -> Path:
    return Path(run_dir) / CHOSEN_FILE


def read(run_dir: Path) -> dict | None:
    """그 편의 기록. 없거나 못 읽으면 None — **없는 것이 정상이다.**"""
    p = path_of(run_dir)
    if not p.is_file():
        return None
    try:
        got = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) else None


def _brief(a: att.Attempt, repo_root: Path) -> dict:
    """시도 하나를 기록에 적을 모양으로. **원값만 적고 점수는 안 낸다.**"""
    try:
        where = a.path.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except ValueError:
        where = a.path.as_posix()          # 저장소 밖이다. 있는 그대로 적는다
    got = {"path": where, "cards": a.cards, "cards_sha256": a.cards_sha256,
           "exam_hit": a.exam_hit, "jokbo_ref": a.jokbo_ref,
           "same": a.same, "partial": a.partial, "different": a.different}
    if a.minutes is not None:
        got["minutes"] = a.minutes
    if a.cost is not None:
        got["cost_usd"] = a.cost
    if a.cut_id:
        got["cut_id"] = a.cut_id
    if a.jokbo_why_not:
        got["jokbo_why_not"] = a.jokbo_why_not
    return got


def build(run_id: str, chosen: att.Attempt, *, why: str, repo_root: Path,
          considered: list[att.Attempt] | None = None,
          kind: str = MAIN, previous: dict | None = None) -> dict:
    """기록 한 장을 만든다. `why` 가 비어 있으면 만들지 않는다.

    `previous` 를 주면 그 위에 얹는다 — 복습과 예습을 따로 적을 수 있어야 하고,
    한쪽을 적으면서 다른 쪽을 지우면 안 된다.
    """
    if not (why or "").strip():
        raise ValueError("why 가 없다. 왜 골랐는지는 코드가 쓰지 않는다 (모듈 머리)")
    got = dict(previous or {})
    got["run_id"] = run_id
    pub = dict(got.get("publish") or {})
    pub[kind] = _brief(chosen, repo_root)
    pub[f"{kind}_why"] = why.strip()
    pub[f"{kind}_chosen_at"] = dt.datetime.now().isoformat(timespec="seconds")
    got["publish"] = pub

    # `current` — 다음에 돌릴 때 무엇을 쓸까. 지금 적을 값은 족보 컷 하나다.
    # **고른 시도가 본 컷**을 적는다. 그 컷을 다시 자르면 `cut_id` 가 달라지므로,
    # 이 값이 「이 덱은 어느 컷으로 만들었나」의 답으로 남는다.
    if chosen.cut_id:
        cur = dict(got.get("current") or {})
        cur["jokbo"] = {"cut_id": chosen.cut_id, "slice": chosen.jokbo_slice}
        got["current"] = cur

    # 무엇과 비교했는가. **비어 있으면 「비교 안 했다」로 읽어야 한다** —
    # 나중에 이 판단이 정보에 근거한 것이었는지 사람이 알 수 있어야 한다.
    others = [a for a in (considered or [])
              if a.fresh and a.cards_sha256 != chosen.cards_sha256]
    got["considered"] = [_brief(a, repo_root) for a in others]
    return got


def write(run_dir: Path, record: dict) -> Path:
    p = path_of(run_dir)
    p.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def published_cards(run_dir: Path, kind: str = MAIN) -> str:
    """**지금 나가는 덱을 만든** 시도의 카드 해시. 모르면 빈 문자열.

    옛 모양에서는 강의 폴더 자신이 그 시도다. 새 모양에서는 `run.meta.json` 의
    `attempt` 가 말한다 — 계약을 쓸 때 `deck.contract` 가 적어 둔 값이다.

    **`runlayout.work_dir` 을 쓰면 안 된다.** 그것은 「고른 판」을 주므로, 고른 것과
    맞대 보면 늘 같다고 나온다 — 검사가 꺼진 것과 같다. 2026-09-15 에 올리기를
    붙이면서 실제로 그렇게 한 번 꺼졌고, 그 자리를 이 함수가 대신한다.
    """
    meta_name = "pre_run.meta.json" if kind == PREQUIZ else "run.meta.json"
    try:
        meta = json.loads((Path(run_dir) / meta_name).read_text(encoding="utf-8"))
        mark = meta.get("attempt")
    except (OSError, ValueError, AttributeError):
        mark = None
    if isinstance(mark, dict) and mark.get("cards_sha256"):
        return str(mark["cards_sha256"])
    if isinstance(mark, dict) and mark.get("version"):
        # 해시를 안 적은 옛 계약. 판 이름으로 그 폴더를 찾아 직접 뜬다.
        return att.cards_sha256(
            runlayout.attempt_root(run_dir, kind) / str(mark["version"]))
    # 계약이 판을 말하지 않는다. 옛 모양이면 강의 폴더 자신이 그 시도다.
    if not runlayout.is_migrated(Path(run_dir), kind):
        return att.cards_sha256(run_dir)

    # 옮겨졌는데 계약이 판을 안 말한다 — 2026-09-15 이전에 쓰인 계약이다.
    # **덱으로 되짚는다.** 강의 폴더에 올라간 덱과 크기가 같은 판이 하나면 그것이다.
    # 짐작이 아니라 증거이고, 하나로 안 좁혀지면 **모른다고 한다.**
    return _by_deck(Path(run_dir), kind)


def _by_deck(run_dir: Path, kind: str) -> str:
    """올라간 덱과 같은 덱을 가진 판을 찾아 그 카드 해시를. 못 좁히면 빈 문자열."""
    decks = sorted(run_dir.glob("*.apkg"))
    if len(decks) != 1:
        return ""                      # 덱이 둘이면 어느 것이 이 갈래인지 모른다
    size = decks[0].stat().st_size
    hits = []
    for v in runlayout.versions(run_dir, kind):
        work = runlayout.attempt_root(run_dir, kind) / v
        for cand in work.glob("*.apkg"):
            if cand.stat().st_size == size:
                hits.append(work)
                break
    return att.cards_sha256(hits[0]) if len(hits) == 1 else ""


def verdict(run_dir: Path, kind: str = MAIN) -> str:
    """지금 그 자리에 있는 것이 사람이 고른 시도인가. 어긋나면 사람이 읽을 한 줄.

    **없으면 빈 문자열이다** — 기록이 없는 편은 지금과 똑같이 돈다.
    """
    record = read(run_dir)
    if not record:
        return ""
    pick = (record.get("publish") or {}).get(kind) or {}
    want = pick.get("cards_sha256")
    if not want:
        return ""                          # 신원을 안 적은 기록이다. 판정하지 않는다
    now = published_cards(run_dir, kind)
    if not now:
        # 카드 파일이 없다. 옆 저장소에서 옮겨 온 편이 이 자리에 온다 —
        # 기록이 가리키는 것과 맞는지 **알 수 없다.** 모르는 것을 틀렸다고 하지 않는다.
        return ""
    if now == want:
        return ""
    return (f"사람이 고른 시도가 이 자리에 없다 — {pick.get('path', '?')} "
            f"({pick.get('cards', '?')}장, 카드 {want[:12]}) 를 골랐는데 "
            f"여기 있는 것은 {now[:12]} 다. "
            f"고른 것을 이 자리로 옮기거나, 마음이 바뀌었으면 "
            f"`python -m runner chosen {record.get('run_id', '<run_id>')}` 로 다시 적어라")


def summary(run_dir: Path, kind: str = MAIN) -> str:
    """사람이 읽는 한 줄. 기록이 없으면 그렇다고 말한다."""
    record = read(run_dir)
    if not record:
        return "고른 기록이 없다 — 지금 이 자리에 있는 것이 그냥 정본이다"
    pub = record.get("publish") or {}
    pick = pub.get(kind) or {}
    if not pick:
        return f"{kind} 쪽은 아직 안 골랐다"
    when = (pub.get(f"{kind}_chosen_at") or "")[:16]
    n = len(record.get("considered") or [])
    against = f"{n}개와 비교" if n else "**비교한 시도 없음**"
    return (f"{pick.get('path')} ({pick.get('cards')}장) · {when} · {against}\n"
            f"    왜: {pub.get(f'{kind}_why', '(안 적혀 있다)')}")
