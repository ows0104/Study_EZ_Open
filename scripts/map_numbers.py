"""현재 코드·검사·작업 안내의 크기를 측정한다.

    python scripts/map_numbers.py           현재 수치
    python scripts/map_numbers.py --check   문서 누락·빈 검사·잘못된 의존도 확인

수치는 여기서 계산하고 docs/map.md에는 파일 안내만 남긴다.
Git 추적 파일과 커밋 전 새 파일을 모두 세며 무시된 산출물은 뺀다.
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AREAS = (
    "quizgen", "quizbank", "runner", "server/app", "web/src",
    "spotter/scripts", "spotter/web", "bridge", "platform", "tests",
)
MODULE_TESTS = {
    "quizgen": "tests/quizgen", "quizbank": "tests/quizbank",
    "runner": "tests/runner", "spotter": "tests/spotter", "bridge": "tests/bridge",
    "web": None, "server": None,
}
CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".css", ".html", ".ps1"}
GENERATOR_PACKAGES = {"quizgen", "quizbank", "runner"}


def source_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", *AREAS],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return sorted({ROOT / name for name in result.stdout.split("\0")
                   if name and (ROOT / name).is_file()})


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8-sig").splitlines())


def test_counts() -> Counter[str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "--collect-only", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode:
        raise RuntimeError(
            f"검사 수집 실패 ({sys.executable})\n{result.stdout[-3000:]}\n{result.stderr[-1000:]}"
        )
    counts: Counter[str] = Counter()
    for line in result.stdout.splitlines():
        if line.startswith("tests/") and "::" in line:
            counts["/".join(line.split("/")[:2])] += 1
    if not counts:
        raise RuntimeError("pytest가 검사 목록을 반환하지 않았습니다.")
    return counts


def crossing_imports(files: list[Path]) -> list[str]:
    """서버·Spotter는 로컬 생성기를 import하지 않고 HTTP/파일로 연결한다."""
    found = []
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if path.suffix != ".py" or not relative.startswith(("server/app/", "spotter/")):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"), filename=relative)):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                if module.split(".")[0] in GENERATOR_PACKAGES:
                    found.append(f"{relative}:{node.lineno} → {module}")
    return sorted(found)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="안내·검사·의존 경계를 검사한다")
    args = parser.parse_args()
    try:
        files = source_files()
        counts = test_counts()
        crossings = crossing_imports(files)
    except (OSError, ValueError, SyntaxError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"측정 실패: {error}", file=sys.stderr)
        return 1

    print("영역                    코드 줄 수")
    for area in AREAS:
        lines = sum(line_count(path) for path in files
                    if path.suffix in CODE_SUFFIXES
                    and path.relative_to(ROOT).as_posix().startswith(f"{area}/"))
        print(f"  {area:<23}{lines:>7,}")
    print(f"\nPython 검사: {sum(counts.values()):,}")
    for area, count in sorted(counts.items()):
        print(f"  {area:<23}{count:>7,}")

    missing = []
    print("\n작업 안내 줄 수")
    for area in ("", *MODULE_TESTS):
        path = ROOT / area / "CLAUDE.md"
        count = line_count(path) if path.is_file() else 0
        label = f"{area}/CLAUDE.md" if area else "CLAUDE.md"
        print(f"  {label:<23}{count:>7,}")
        if not count:
            missing.append(label)
    empty = [area for area, tests in MODULE_TESTS.items() if tests and not counts[tests]]
    if crossings:
        print("\n서버·Spotter가 로컬 생성기를 import합니다:\n  " + "\n  ".join(crossings))
        return 2
    if missing:
        print("\n작업 안내 없음: " + ", ".join(missing))
    if empty:
        print("\n검사 없음: " + ", ".join(empty))
    if args.check and (missing or empty):
        return 1
    print("\n의존 경계 정상" + (" · 작업 안내와 검사 확인" if args.check else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
