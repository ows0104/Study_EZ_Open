"""문항 DB와 사진을 R2로 올린다.

    uv run --python 3.13 --with requests python scripts/upload_web.py

`build_web.py`가 만든 `build/quiz_db.json`과 `build/images/*.jpg`를 R2의
`spotter/` 아래로 밀어 넣는다. 버킷은 비공개고, 로그인한 사람에게만 서버가
서명 URL을 내준다.

**R2 자격증명을 여기 두지 않는다.** 서버의 `POST /api/spotter/admin/uploads`가
서명된 PUT 주소를 내주고 이 스크립트는 거기에 바이트만 붓는다. 키를 노트북에
한 벌 더 두면 그만큼 새어 나갈 자리가 는다 — 서버가 이미 들고 있는 것을
다시 복사할 이유가 없다.

인증은 두 갈래다. **`RUNNER_TOKEN`이 있으면 그것을 쓰고**, 없으면 관리자
계정으로 Supabase에 로그인한다. 토큰 쪽이 있는 것은 사람이 비밀번호를 치지
않고도 배포가 돌아야 하기 때문이고, 서버의 `require_runner`가 둘 다 받는다.
토큰은 `Study_EZ_Open/server/.env`의 `RUNNER_TOKEN`과 같은 값이다.

    SPOTTER_API_BASE     https://studyez-api-....run.app   (기본: web/config.js에서 읽음)
    SPOTTER_SUPABASE_URL https://xxxx.supabase.co          (기본: 위와 같음)
    SPOTTER_SUPABASE_ANON_KEY                              (기본: 위와 같음)
    RUNNER_TOKEN         서버와 같은 공유 토큰. 있으면 로그인을 건너뛴다
    SPOTTER_EMAIL        관리자 이메일  (토큰이 없을 때만)
    SPOTTER_PASSWORD     비밀번호       (없으면 물어본다)

    --env-file <경로>    RUNNER_TOKEN 을 여기서 읽는다. 기본은 옆 저장소의
                         Study_EZ_Open/server/.env 이고, 없으면 그냥 넘어간다.
"""

import getpass
import hashlib
import json
import os
import re
import sys

import requests

from jsonio import read_bytes, read_text

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
BUILD = os.path.join(ROOT, "build")
DB_PATH = os.path.join(BUILD, "quiz_db.json")
IMG_DIR = os.path.join(BUILD, "images")

# 한 번에 서명받을 사진 수. 서명은 싸지만 응답이 커지므로 나눠 받는다.
BATCH = 100


def from_config(name: str) -> str:
    """`web/config.js`의 값 하나. 배포되는 파일이 곧 설정의 사실이다.

    스크립트가 따로 `.env`를 들면 화면이 보는 서버와 올리는 서버가 갈라질 수
    있다. 실제로 갈라지면 "올렸는데 안 보인다"가 되고, 그건 원인을 찾기
    어려운 종류의 고장이다.
    """
    try:
        text = read_text(os.path.join(WEB, "config.js"))
    except OSError:
        return ""
    m = re.search(rf"{name}\s*:\s*[\"']([^\"']*)[\"']", text)
    return m.group(1).strip() if m else ""


def setting(env_name: str, config_name: str) -> str:
    return os.getenv(env_name, "").strip() or from_config(config_name)


def runner_token() -> str:
    """서버와 나눠 가진 공유 토큰. 환경 변수가 먼저고, 없으면 `.env`를 본다.

    기본 경로가 옆 저장소를 가리키는 것은 서버 코드가 거기 살기 때문이다.
    없으면 조용히 빈 값을 돌려주고 관리자 로그인으로 넘어간다 — 서버를 안 든
    사람도 이 스크립트를 쓸 수 있어야 한다.
    """
    token = os.getenv("RUNNER_TOKEN", "").strip()
    if token:
        return token
    # **2026-09-14 에 저장소를 합치면서 한 칸 바뀌었다.** 그 전에는 형제 폴더
    # (`../Study_EZ_Open/server/.env`)였고, 합친 뒤 그 경로는
    # `Study_EZ_Open/Study_EZ_Open/server/.env` 가 되어 조용히 못 찾는다 —
    # 못 찾으면 빈 토큰으로 떨어져서 「인증 실패」로만 보인다.
    path = os.getenv("SPOTTER_ENV_FILE", "").strip() or os.path.join(
        os.path.dirname(ROOT), "server", ".env"
    )
    if "--env-file" in sys.argv:
        path = sys.argv[sys.argv.index("--env-file") + 1]
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("RUNNER_TOKEN=") and not line.startswith("#"):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def login(supabase_url: str, anon_key: str, email: str, password: str) -> str:
    r = requests.post(
        f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
        headers={"apikey": anon_key, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=30,
    )
    if not r.ok:
        raise SystemExit(f"로그인 실패: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]


def main() -> None:
    if not os.path.isfile(DB_PATH):
        raise SystemExit("build/quiz_db.json이 없습니다. 먼저 scripts/build_web.py를 돌리세요.")

    api = setting("SPOTTER_API_BASE", "apiBase").rstrip("/")
    if not api:
        raise SystemExit("web/config.js의 apiBase가 비어 있습니다.")

    token = runner_token()
    if token:
        print("러너 토큰으로 붙는다")
    else:
        supabase_url = setting("SPOTTER_SUPABASE_URL", "supabaseUrl")
        anon_key = setting("SPOTTER_SUPABASE_ANON_KEY", "supabaseAnonKey")
        if not (supabase_url and anon_key):
            raise SystemExit(
                "RUNNER_TOKEN도 없고 Supabase 설정도 비어 있습니다. "
                "web/config.js를 채우거나 RUNNER_TOKEN을 주세요."
            )
        email = os.getenv("SPOTTER_EMAIL", "").strip() or input("관리자 이메일: ").strip()
        password = os.getenv("SPOTTER_PASSWORD", "") or getpass.getpass("비밀번호: ")
        token = login(supabase_url, anon_key, email, password)
        print(f"로그인 완료 — {email}")
    auth = {"Authorization": f"Bearer {token}"}

    # ── 무엇이 이미 올라가 있나
    r = requests.get(f"{api}/api/spotter/admin/manifest", headers=auth, timeout=60)
    if r.status_code == 403:
        raise SystemExit("관리자 계정이 아닙니다. STUDYEZ_ADMIN_EMAILS를 보세요.")
    r.raise_for_status()
    remote = r.json()["images"]

    local = sorted(f for f in os.listdir(IMG_DIR) if f.lower().endswith(".jpg"))
    todo = []
    for name in local:
        path = os.path.join(IMG_DIR, name)
        # R2의 ETag는 한 번에 올린 객체에 한해 내용의 MD5다. 같으면 건너뛴다 —
        # 555장 중 두 장을 고쳤을 때 30MB를 다시 붓지 않기 위해서다.
        md5 = hashlib.md5(read_bytes(path)).hexdigest()
        if remote.get(name) != md5:
            todo.append(name)

    gone = sorted(set(remote) - set(local))
    print(f"사진 {len(local)}장 중 {len(todo)}장 올림"
          + (f", R2에만 남은 것 {len(gone)}장" if gone else ""))
    if gone:
        # 지우지 않는다. 문항 DB를 되돌릴 때 그 사진이 다시 필요해지고, 남아
        # 있어도 서명은 지금 문항이 쓰는 이름에만 나간다.
        print("  (안 지운다. 문항을 되돌릴 때 다시 쓰인다)")

    # ── 사진
    sent = 0
    for i in range(0, len(todo), BATCH):
        chunk = todo[i : i + BATCH]
        r = requests.post(
            f"{api}/api/spotter/admin/uploads", headers=auth, json={"names": chunk}, timeout=120
        )
        r.raise_for_status()
        urls = r.json()["images"]
        for name in chunk:
            with open(os.path.join(IMG_DIR, name), "rb") as fh:
                put = requests.put(urls[name], data=fh, headers={"Content-Type": "image/jpeg"},
                                   timeout=300)
            put.raise_for_status()
            sent += 1
            if sent % 25 == 0 or sent == len(todo):
                print(f"  {sent}/{len(todo)}")

    # ── 문항 DB
    raw = read_bytes(DB_PATH)
    r = requests.post(
        f"{api}/api/spotter/admin/uploads", headers=auth, json={"names": [], "db": True}, timeout=60
    )
    r.raise_for_status()
    put = requests.put(r.json()["db"], data=raw,
                       headers={"Content-Type": "application/json"}, timeout=300)
    put.raise_for_status()
    counts = json.loads(raw)["meta"]["counts"]
    print(f"quiz_db.json {len(raw) / 1e6:.2f}MB  문항 {counts['questions']}개")

    # 서버가 들고 있던 옛 DB를 버리게 한다. 인스턴스가 여럿이면 그중 하나만
    # 비워지고 나머지는 다음 콜드 스타트에 맞춰진다 — 라우터의 설명을 보라.
    requests.post(f"{api}/api/spotter/admin/db/refresh", headers=auth, timeout=30)
    print("끝.")


if __name__ == "__main__":
    main()
