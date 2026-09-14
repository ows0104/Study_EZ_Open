"""배포 저장소(`ows0104/Spotter_Quiz`)를 이 저장소의 `web/`과 맞춘다.

    uv run --python 3.13 python scripts/deploy_pages.py <Pages 저장소>

Cloudflare Pages가 그 저장소의 **루트를 통째로** 내보내고 있어서, 거기 있는
파일이 곧 배포물이다. 이 스크립트가 하는 일은 셋이다.

    ① 공용 스크립트 넷을 루트에 둔다 (config·session·auth·gate)
    ② 기생충학 화면을 `parasitology/`에 둔다
    ③ 해부학 넷의 index.html에 로그인 문을 단다 (`gate_subject.py`)
    ④ 모든 `<script src>`에 내용 해시를 붙인다 (`?v=…`)

**④가 없으면 화면이 반만 갱신된다.** 2026-09-06에 실제로 그랬다 — 새 HTML은
`_headers`의 `no-store` 덕에 바로 갔는데 `app.js`는 그 헤더가 생기기 전에
`max-age=14400`으로 캐시된 것이 네 시간을 더 살아서, 새 HTML이 옛 코드를
불렀고 옛 코드가 찾던 자리가 없어 화면이 통째로 비었다. 헤더는 앞으로만
효력이 있고 이미 나간 캐시는 못 되돌린다 — 주소가 바뀌어야 다시 받는다.

해시는 **배포될 파일의 내용**에서 뽑는다. 안 바뀐 파일은 주소도 그대로라
쓸데없이 다시 받게 하지 않는다.

**해부학 넷의 index.html은 이 저장소에 원본이 없다.** 각자 완성된 한 파일짜리
앱이고 배포 저장소에만 있다 — 여기서는 문만 달아 준다. 그래서 과목 앱을 새로
구우면 이 스크립트를 다시 돌려야 한다.

`config.js`는 **배포본을 안 덮는다.** 이 저장소의 것은 보통 로컬 시험용으로
비워져 있고, 덮으면 배포에서 apiBase가 사라져 화면이 "설정이 없습니다"에서
멈춘다. 값이 다르면 그 사실만 알린다.

    --check   고치지 않고 무엇이 다른지만 본다
"""

import filecmp
import hashlib
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")

# 루트에 놓이는 공용 스크립트. 과목 다섯이 `../`로 부른다.
SHARED = ("session.js", "auth.js", "gate.js")
# 기생충학 화면. 이쪽은 자기 폴더를 쓴다.
PARA = ("index.html", "app.js")
SUBJECTS = ("exam1", "trunk", "head-neck", "neuro")


def rewrite(text):
    """공용 스크립트를 `../`에서 찾게 한다.

    이 저장소에서는 화면과 공용 스크립트가 `web/` 한 폴더에 같이 있지만,
    배포 저장소에서는 공용 스크립트가 **루트**에 있고 과목이 그 아래 폴더다.
    다섯 과목이 한 벌을 나눠 쓰기 때문이고, 그래서 옮길 때 한 칸 올린다.
    """
    for name in ("config.js", "session.js", "auth.js", "gate.js"):
        text = text.replace(f'<script src="{name}">', f'<script src="../{name}">')
    return text


# `<script src="…js">` 한 자리. 이미 붙은 `?v=…`는 다시 붙이지 않고 갈아 낀다.
SCRIPT = re.compile(r'<script src="([^"]+?\.js)(?:\?v=[0-9a-f]+)?"')


def digest(path):
    """파일 내용의 짧은 지문. 내용이 같으면 주소도 같다."""
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()[:8]


def source_of(repo, html_dir, src):
    """`src`가 배포되면 실제로 어느 파일이 되는가.

    해시는 **그 파일**에서 뽑아야 한다. 공용 넷은 이 저장소의 `web/`이 원본이고
    (이번 실행에서 그대로 복사된다), `config.js`만은 배포본이 사실이라
    저쪽 것을 본다 — 이 저장소의 것은 보통 로컬 시험용이라 값이 다르다.
    """
    name = os.path.basename(src)
    if name == "config.js":
        return os.path.join(repo, "config.js")
    if name in SHARED or name in PARA:
        return os.path.join(WEB, name)
    return os.path.normpath(os.path.join(html_dir, src))


def stamp(text, repo, html_dir):
    """이 HTML이 부르는 스크립트마다 `?v=<내용 해시>`를 붙인다."""

    def one(m):
        src = m.group(1)
        path = source_of(repo, html_dir, src)
        if not os.path.isfile(path):
            # 우리가 모르는 스크립트다. 건드리지 않는다.
            return m.group(0)
        return f'<script src="{src}?v={digest(path)}"'

    return SCRIPT.sub(one, text)


def copy(src, dest, check, repo=None):
    body = open(src, encoding="utf-8").read()
    if dest.endswith(".html"):
        body = stamp(rewrite(body), repo, os.path.dirname(dest))
    same = os.path.isfile(dest) and open(dest, encoding="utf-8").read() == body
    name = os.path.relpath(dest, os.path.dirname(os.path.dirname(dest)))
    if same:
        print(f"  같음     {name}")
        return False
    if check:
        print(f"  다름     {name}")
        return True
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, "w", encoding="utf-8", newline="").write(body)
    print(f"  넣었음   {name}")
    return True


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit("Pages 저장소 경로를 주세요.")
    repo = os.path.abspath(args[0])
    check = "--check" in sys.argv
    if not os.path.isdir(os.path.join(repo, "parasitology")):
        raise SystemExit(f"Pages 저장소가 아닌 것 같습니다: {repo}")

    # 공용 파일 중 session.js는 Study_EZ가 원본이다. 먼저 가져온다.
    print("공용 세션 파일")
    subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "sync_shared.py")]
        + (["--check"] if check else []),
        check=True,
    )

    print("\n공용 스크립트")
    changed = False
    for name in SHARED:
        changed |= copy(os.path.join(WEB, name), os.path.join(repo, name), check)

    # config.js는 값이 배포마다 달라서 덮지 않는다. 다르면 말만 한다.
    here, there = os.path.join(WEB, "config.js"), os.path.join(repo, "config.js")
    if not os.path.isfile(there):
        print("  없음!    config.js — 배포 저장소에 손으로 채워 넣어야 합니다")
    elif not filecmp.cmp(here, there, shallow=False):
        print("  다름     config.js (안 덮습니다. 배포본이 사실입니다)")

    print("\n기생충학")
    for name in PARA:
        changed |= copy(
            os.path.join(WEB, name), os.path.join(repo, "parasitology", name), check, repo
        )

    print("\n해부학 — 로그인 문")
    subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "gate_subject.py"), repo, *SUBJECTS],
        check=True,
    )

    # 해부학 넷은 한 번 문을 달면 다시 안 건드리므로(`gate_subject.py`가
    # 건너뛴다) 도장은 여기서 따로 찍는다. 안 찍으면 공용 스크립트를 고쳐도
    # 네 과목은 옛 주소를 계속 불러서 캐시가 그대로 산다.
    print("\n스크립트 버전 도장")
    for subject in SUBJECTS:
        path = os.path.join(repo, subject, "index.html")
        text = open(path, encoding="utf-8").read()
        body = stamp(text, repo, os.path.dirname(path))
        if body == text:
            print(f"  같음     {subject}/index.html")
            continue
        if check:
            print(f"  다름     {subject}/index.html")
            changed = True
            continue
        open(path, "w", encoding="utf-8", newline="").write(body)
        print(f"  찍었음   {subject}/index.html")

    if check and changed:
        raise SystemExit("\n배포 저장소가 뒤처져 있습니다. 인자 없이 다시 돌리세요.")
    print("\n끝. 배포 저장소에서 커밋하고 push 하면 Cloudflare Pages가 빌드합니다.")


if __name__ == "__main__":
    main()
