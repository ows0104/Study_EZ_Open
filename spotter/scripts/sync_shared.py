"""형제 앱과 나눠 쓰는 파일을 가져온다.

    uv run --python 3.13 python scripts/sync_shared.py

지금은 `session.js` 하나다. 원본은 이 저장소의 `packages/session/` 에 있고 여기
있는 것은 사본이다 — **여기서 고치면 다음 동기화에 덮인다.**

**저장소를 합친 뒤에도 사본이 남는 이유**는 이 앱에 빌드 도구가 없어서다.
정적 파일 넷을 그대로 내보내고 `index.html` 이 `<script src="session.js">` 로
부르므로, 그 이름의 파일이 실제로 그 자리에 있어야 한다. 같은 저장소 안이라
경로로 가리킬 수는 있지만 그건 번들러가 할 일이고, 여기엔 번들러가 없다.
대신 **사본이 원본과 다르면 이 스크립트가 그 자리에서 말한다** — 조용히
갈라지는 것만 막으면 된다.

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

# 원본이 사는 곳. **2026-09-14 에 저장소를 합치면서 형제 폴더에서 상위로 바뀌었다** —
# 그 전에는 `../Study_EZ_Open` 를 봤고, 합친 뒤 그 경로는 `Study_EZ_Open/Study_EZ_Open`
# 이 되어 「원본 저장소를 못 찾았습니다」로 죽었다. 환경 변수 우선은 그대로 둔다.
PLATFORM = os.getenv("STUDYEZ_REPO", "").strip() or os.path.dirname(ROOT)

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
