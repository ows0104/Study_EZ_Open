"""지도(`docs/map.md`)가 적는 숫자를 다시 뜬다.

    python scripts/map_numbers.py            사람이 읽는 표
    python scripts/map_numbers.py --check    지도와 다른 줄만 찍고 1로 끝난다

**이 도구가 있는 이유는 지도가 두 곳에 있기 때문이다.** 저장소의 `docs/map.md` 와
관리자가 보는 Artifact 페이지가 같은 숫자를 적는데, 2026-09-14 에 벌써 갈라졌다
(검사 604 대 606). 손으로 맞추면 또 갈라진다.

**줄수는 낡으라고 두는 값이다.** 지도 §5 가 그렇게 적고 있다 — 낡았는지가 중요한
것은 줄수가 아니라 **경계**(§3)다. 그래서 `--check` 는 숫자가 다르면 알려만 주고,
막지 않는다. 고칠지는 사람이 정한다.
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
CODE = re.compile(r"\.(py|ts|tsx|js|css|html|md|ps1)$")


def lines_in(area: str) -> int:
    out = subprocess.run(["git", "ls-files", area], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8").stdout
    total = 0
    for name in out.split("\n"):
        if not name.strip() or not CODE.search(name):
            continue
        p = ROOT / name
        if p.is_file():
            total += len(p.read_bytes().split(b"\n")) - 1
    return total


def test_count() -> int:
    out = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "--collect-only"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    m = re.search(r"(\d+) tests? collected", out)
    return int(m.group(1)) if m else -1


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
    got["__tests__"] = test_count()
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

    print(f"\n  {'검사':<18}{got['__tests__']:>9,}")
    print(f"  {'서버 경로':<17}{got['__routes__']:>9,}")
    print(f"  {'경계 넘는 import':<15}{got['__crossing__']:>9,}"
          + ("   ← **0 이어야 한다**" if got["__crossing__"] else ""))

    if got["__crossing__"]:
        print("\n경계가 늘었다. 지도가 아니라 구조를 본다 — docs/map.md §7.")
        raise SystemExit(2)
    if check and drift:
        print(f"\n지도의 숫자 {len(drift)}개가 낡았다. "
              "줄수는 낡으라고 둔 값이니 고칠지는 사람이 정한다.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
