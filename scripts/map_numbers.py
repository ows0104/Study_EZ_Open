"""지도(`docs/map.md`)가 적는 숫자를 다시 뜬다.

    python scripts/map_numbers.py            사람이 읽는 표
    python scripts/map_numbers.py --check    지도와 다른 줄만 찍고 1로 끝난다

**이 도구가 있는 이유는 지도가 두 곳에 있기 때문이다.** 저장소의 `docs/map.md` 와
관리자가 보는 Artifact 페이지가 같은 숫자를 적는데, 2026-09-14 에 벌써 갈라졌다
(검사 604 대 606). 손으로 맞추면 또 갈라진다.

**줄수는 낡으라고 두는 값이다.** 지도 §5 가 그렇게 적고 있다 — 낡았는지가 중요한
것은 줄수가 아니라 **경계**(§3)다. 그래서 `--check` 는 숫자가 다르면 알려만 주고,
막지 않는다. 고칠지는 사람이 정한다.

**2026-09-14 에 두 가지를 더 센다.** 문맥을 덩이별로 가른 날이라 그것이 다시
모이는지를 봐야 한다.

    검사를 덩이별로       tests/<덩이> 가 몇 개인가. 비면 옮기다 흘린 것이다
    덩이 문서            <덩이>/CLAUDE.md 가 있는가. 없으면 루트를 통째로 읽게 된다

루트 CLAUDE.md 줄수도 같이 찍는다 — **덩이 하나의 것을 루트에 적으면 그 숫자만
늘고 덩이 것은 그대로다.** 다시 자라는 것은 그 자리에서 보인다.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "docs" / "map.md"

# 지도 §1 이 적는 덩이. 이름은 지도에 쓰인 그대로다.
AREAS = [
    "quizgen", "runner", "server/app", "web/src",
    "spotter/scripts", "spotter/web", "spotter-dist",
    "bridge", "platform", "tests",
]
# `docs` 는 일부러 뺐다. **그 숫자를 적는 파일이 `docs/` 안에 있어서** 적는 순간
# 틀린다 — 2026-09-14 에 실제로 그랬다. 수렴하지 않는 값은 지도에 안 적는다.
SUB = ["web/src/calendar", "web/src/admin", "web/src/lecture", "web/src/styles"]

# 덩이마다 자기 `CLAUDE.md` 를 든다. **없으면 그 덩이를 고치는 세션이 루트를 통째로
# 읽게 되고, 그것이 나누기 전 상태다** — 2026-09-14 에 루트가 587줄이었고 그 89%가
# `quizgen`·`runner` 이야기였다. 값은 그 덩이의 검사 폴더이고, 없는 것은 pytest 가
# 아니라 자기 명령으로 돈다(`web` 은 `npm run typecheck`, `server` 는 `-m tests`).
DOCS = {
    "quizgen": "tests/quizgen", "runner": "tests/runner",
    "spotter": "tests/spotter", "bridge": "tests/bridge",
    "web": None, "server": None,
}
CODE = re.compile(r"\.(py|ts|tsx|js|css|html|md|ps1)$")


def lines_in(area: str) -> int:
    out = subprocess.run(["git", "ls-files", area], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8").stdout
    total = 0
    for name in out.split("\n"):
        if not name.strip() or not CODE.search(name):
            continue
        # 덩이의 `CLAUDE.md` 는 `module_docs()` 가 따로 센다. 여기서도 세면 같은 줄이
        # 두 번 들어가고 **「덩이 줄수」가 코드 크기를 뜻하지 않게 된다.**
        if name.endswith("/CLAUDE.md"):
            continue
        p = ROOT / name
        if p.is_file():
            total += len(p.read_bytes().split(b"\n")) - 1
    return total


def test_counts() -> dict[str, int]:
    """검사를 덩이별로 센다. **한 번만 수집하고 경로 앞머리로 가른다.**

    덩이별 폴더를 만든 이유가 이 숫자다 — 땡시 문항을 고치면 `pytest tests/spotter`
    22개(7초)만 돌면 된다. 전부는 606개 27초다.
    """
    out = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "--collect-only"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    got: dict[str, int] = {}
    for line in out.split("\n"):
        if "::" not in line:
            continue
        parts = line.split("/")
        if len(parts) > 2 and parts[0] == "tests":
            key = f"tests/{parts[1]}"
            got[key] = got.get(key, 0) + 1
    m = re.search(r"(\d+) tests? collected", out)
    got["__all__"] = int(m.group(1)) if m else -1
    return got


def module_docs() -> dict[str, int]:
    """덩이별 `CLAUDE.md` 의 줄수. 빈 문자열 칸이 루트다. **없으면 0 이다.**"""
    got = {"": len((ROOT / "CLAUDE.md").read_text(encoding="utf-8").split("\n")) - 1}
    for area in DOCS:
        p = ROOT / area / "CLAUDE.md"
        got[area] = len(p.read_text(encoding="utf-8").split("\n")) - 1 if p.is_file() else 0
    return got


def route_count() -> int:
    p = ROOT / "server" / "tests" / "test_routes_golden.py"
    m = re.search(r'GOLDEN = """(.*?)"""', p.read_text(encoding="utf-8"), re.S)
    return len([ln for ln in m.group(1).split("\n") if ln.strip()]) if m else -1


def crossing_imports() -> int:
    """경계를 넘는 파이썬 import. **0 이 아니면 지도가 아니라 구조가 틀린 것이다.**"""
    out = subprocess.run(
        ["git", "grep", "-cE", r"^\s*(from|import)\s+(quizgen|runner)\b",
         "--", "server/app", "spotter"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    return sum(int(ln.rsplit(":", 1)[1]) for ln in out.split("\n") if ":" in ln)


def measured() -> dict[str, int]:
    got = {a: lines_in(a) for a in AREAS}
    got |= {s: lines_in(s) for s in SUB}
    got |= test_counts()
    got["__routes__"] = route_count()
    got["__crossing__"] = crossing_imports()
    return got


def in_map(text: str, area: str) -> int | None:
    """지도에서 그 덩이 옆에 적힌 숫자. 못 찾으면 None."""
    m = re.search(re.escape(area) + r"/?\s*\|?[^|\n]*?([\d,]{3,})", text)
    return int(m.group(1).replace(",", "")) if m else None


def main() -> None:
    check = "--check" in sys.argv
    got = measured()
    text = MAP.read_text(encoding="utf-8")

    print(f"{'덩이':<20}{'실측':>9}{'지도':>9}")
    drift = []
    for area in AREAS + SUB:
        want = in_map(text, area)
        mark = ""
        if want is not None and want != got[area]:
            mark = "  ← 다르다"
            drift.append((area, got[area], want))
        print(f"  {area:<18}{got[area]:>9,}{(f'{want:,}' if want else '—'):>9}{mark}")

    counts = {k: v for k, v in got.items() if k.startswith("tests/")}
    print(f"\n  {'검사':<18}{got['__all__']:>9,}")
    for area, n in sorted(counts.items()):
        print(f"    {area:<16}{n:>9,}")
    print(f"  {'서버 경로':<17}{got['__routes__']:>9,}")
    print(f"  {'경계 넘는 import':<15}{got['__crossing__']:>9,}"
          + ("   ← **0 이어야 한다**" if got["__crossing__"] else ""))

    # 덩이 문서. **루트가 다시 자라는 것이 여기서 보인다** — 덩이 하나의 것을 루트에
    # 적으면 루트 줄수만 늘고 덩이 것은 그대로다.
    docs = module_docs()
    print(f"\n  {'CLAUDE.md 루트':<17}{docs['']:>9,}")
    for area, n in docs.items():
        if area:
            print(f"    {area + '/':<16}{n:>9,}" + ("   ← 없다" if not n else ""))
    missing = [a for a, n in docs.items() if a and n == 0]
    hollow = [a for a, t in DOCS.items() if t and counts.get(t, 0) == 0]

    if got["__crossing__"]:
        print("\n경계가 늘었다. 지도가 아니라 구조를 본다 — docs/map.md §7.")
        raise SystemExit(2)
    if missing:
        print(f"\n덩이 {len(missing)}개에 CLAUDE.md 가 없다 — {' · '.join(missing)}")
        print("그 덩이를 고치는 세션은 루트를 통째로 읽게 된다. 그게 나누기 전 상태다.")
        drift.append(("CLAUDE.md", 0, len(missing)))
    if hollow:
        print(f"\n검사가 빈 덩이 — {' · '.join(hollow)}. 옮기다 흘린 것이 아닌지 본다.")
        drift.append(("tests", 0, len(hollow)))
    if check and drift:
        print(f"\n지도의 숫자 {len(drift)}개가 낡았다. "
              "줄수는 낡으라고 둔 값이니 고칠지는 사람이 정한다.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
