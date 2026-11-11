"""CI가 이번 실행에서 무엇을 돌릴지 정한다(GitHub Actions 분 줄이기).

    python scripts/ci_scope.py        GITHUB_* 환경에서 tests=/windows= 를 GITHUB_OUTPUT에 쓴다

- tests:   Linux 전체 검사(Python 회귀·서버·웹 빌드·bridge). 문서·기록만 바뀌면 false.
- windows: Windows runner checks. 러너·생성기·계약·스크립트 쪽이 안 바뀌면 false.

master push는 PR에서 이미 같은 트리(병합 결과 트리 == PR 머리 트리)를 통과했으면 다시 돌리지 않는다.
판단할 수 없으면(수동 실행·새 브랜치·파일 300개 이상·API 오류) 전부 돌린다.
배포 후보 준비와 배포는 이 판단과 무관하게 master에서 늘 돈다(Pages가 같은 SHA의 health를 기다린다).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from fnmatch import fnmatchcase

# 검사가 읽지 않는 문서·기록. 검사가 읽는 문서는 아래 DOC_EXCEPTIONS로 다시 코드 취급한다.
DOC_ONLY = (
    "docs/*", "runs/*", "etc/*",
    "*.md", "*/CLAUDE.md", "*/AGENTS.md", "*/README.md",
)
DOC_EXCEPTIONS = (
    "docs/samples/*",                 # server/tests/test_samples.py
    "docs/prompt-architecture.md",    # tests/quizgen/test_prompt_modules.py
    "docs/development/templates/*",   # 개발 루프 도구의 틀
)
ROOT_MD_ONLY = "*.md"  # 루트의 *.md만. web/src/bank/bankPrompt.md 같은 프롬프트는 코드다.

# Windows runner checks가 보지 않는 영역. 여기 밖이 하나라도 바뀌면 Windows 검사를 돌린다.
NOT_WINDOWS = (
    "web/*", "server/app/*", "server/tests/*", "spotter/*", "spotter-dist/*",
)

TESTS_JOB = "Tests and build"
WINDOWS_JOB = "Windows runner checks"


def is_doc(path: str) -> bool:
    if any(fnmatchcase(path, p) for p in DOC_EXCEPTIONS):
        return False
    if fnmatchcase(path, ROOT_MD_ONLY) and "/" not in path:
        return True
    return any(fnmatchcase(path, p) for p in DOC_ONLY if p != ROOT_MD_ONLY)


def classify(paths: list[str]) -> dict[str, bool]:
    code = [p for p in paths if not is_doc(p)]
    return {
        "tests": bool(code),
        "windows": any(not any(fnmatchcase(p, n) for n in NOT_WINDOWS) for p in code),
    }


ALL = {"tests": True, "windows": True}


def _gh(*args: str):
    out = subprocess.run(["gh", "api", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout
    return json.loads(out)


def _passed(repo: str, sha: str) -> set[str]:
    runs = _gh(f"repos/{repo}/commits/{sha}/check-runs?per_page=100")["check_runs"]
    return {r["name"] for r in runs if r.get("conclusion") == "success"}


def decide(env: dict[str, str]) -> tuple[dict[str, bool], str]:
    repo, event = env["GITHUB_REPOSITORY"], env["GITHUB_EVENT_NAME"]
    with open(env["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
        payload = json.load(f)
    if event == "pull_request":
        number = payload["pull_request"]["number"]
        files = subprocess.run(
            ["gh", "api", "--paginate", f"repos/{repo}/pulls/{number}/files?per_page=100", "--jq", ".[].filename"],
            check=True, capture_output=True, text=True, encoding="utf-8",
        ).stdout.splitlines()
        if len(files) >= 3000:
            return ALL, "PR 파일 3000개 이상 — 전부"
        return classify(files), f"PR #{number} 파일 {len(files)}개"
    if event != "push":
        return ALL, f"{event} — 전부"
    before, after = payload.get("before", ""), env["GITHUB_SHA"]
    if not before or set(before) == {"0"}:
        return ALL, "새 브랜치 — 전부"
    files = [f["filename"] for f in _gh(f"repos/{repo}/compare/{before}...{after}")["files"]]
    if len(files) >= 300:
        return ALL, "push 파일 300개 이상 — 전부"
    scope = classify(files)
    note = f"push 파일 {len(files)}개"
    commit = _gh(f"repos/{repo}/commits/{after}")
    parents = commit["parents"]
    if len(parents) == 2:
        head = _gh(f"repos/{repo}/commits/{parents[1]['sha']}")
        if head["commit"]["tree"]["sha"] == commit["commit"]["tree"]["sha"]:
            passed = _passed(repo, parents[1]["sha"])
            if TESTS_JOB in passed:
                scope["tests"] = False
                note += f"; PR 머리 {parents[1]['sha'][:8]}가 같은 트리로 검사 통과"
            if WINDOWS_JOB in passed:
                scope["windows"] = False
    return scope, note


def main() -> int:
    try:
        scope, note = decide(dict(os.environ))
    except Exception as exc:  # 판단 실패는 전부 돌리는 쪽으로
        scope, note = ALL, f"판단 실패({exc.__class__.__name__}: {exc}) — 전부"
    print(note)
    print(json.dumps(scope))
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            for key, value in scope.items():
                f.write(f"{key}={'true' if value else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
