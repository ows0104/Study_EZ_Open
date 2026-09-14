"""형제 앱과 나눠 쓰는 파일을 가져온다.

    uv run --python 3.13 python scripts/sync_shared.py

지금은 `session.js` 하나다. 원본은 Study_EZ_Open에 있고 여기 있는 것은 사본이다
— **여기서 고치면 다음 동기화에 덮인다.**

저장소를 합치지 않고 사본을 두는 이유는, 이 앱이 빌드 도구가 없는 정적 파일
넷이라 패키지 매니저로 끌어올 방법이 없어서다. 대신 **사본이 원본과 다르면
이 스크립트가 그 자리에서 말한다** — 조용히 갈라지는 것만 막으면 된다.

    --check   덮어쓰지 않고 다른지만 본다. 배포 전에 부른다.
"""

import hashlib
import os
import shutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")

# 원본이 사는 곳. 환경 변수로 바꿀 수 있다 — 옆에 나란히 두지 않은 사람도 있다.
PLATFORM = os.getenv("STUDYEZ_REPO", "").strip() or os.path.join(
    os.path.dirname(ROOT), "Study_EZ_Open"
)

SHARED = [("packages/session/session.js", "session.js")]


def digest(path):
    with open(path, "rb") as fh:
        # 줄끝이 갈리는 것으로 다르다고 하지 않는다. Windows에서 흔하다.
        return hashlib.sha1(fh.read().replace(b"\r\n", b"\n")).hexdigest()[:12]


def main():
    check = "--check" in sys.argv
    if not os.path.isdir(PLATFORM):
        raise SystemExit(
            f"원본 저장소를 못 찾았습니다: {PLATFORM}\n"
            "STUDYEZ_REPO 로 경로를 주세요."
        )

    differ = []
    for src_rel, dest_name in SHARED:
        src = os.path.join(PLATFORM, src_rel)
        dest = os.path.join(WEB, dest_name)
        if not os.path.isfile(src):
            raise SystemExit(f"원본이 없습니다: {src}")
        same = os.path.isfile(dest) and digest(src) == digest(dest)
        if same:
            print(f"  같음   {dest_name}  ({digest(src)})")
            continue
        differ.append(dest_name)
        if check:
            print(f"  다름   {dest_name}  원본 {digest(src)}")
            continue
        shutil.copyfile(src, dest)
        print(f"  가져옴 {dest_name}  ({digest(src)})")

    if check and differ:
        raise SystemExit(
            "사본이 원본과 다릅니다: " + ", ".join(differ) + "\n"
            "scripts/sync_shared.py 를 인자 없이 돌리세요."
        )


if __name__ == "__main__":
    main()
