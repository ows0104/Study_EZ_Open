"""과목 하나의 문항 DB와 사진을 R2로 올린다.

    uv run --python 3.13 --with requests python scripts/upload_subject.py <과목 폴더> [--subject 이름]

`upload_web.py`가 기생충학 하나만 올리던 것을 **어느 과목이든** 올릴 수 있게
넓힌 것이다. 해부학 넷은 문항 DB가 `quiz_db.js`(`const QUIZ_DB = [...]`)이고
사진이 과목마다 다른 폴더에 있어서, 폴더를 훑어 그 둘을 찾아낸다.

    <과목 폴더>/
      quiz_db.js        또는 quiz_db.json
      <사진 폴더>/       Spotter_Questions_All · Spotter_Labeling_Images …

**문항이 안 쓰는 사진은 안 올린다.** 해부학 넷의 폴더에는 703장이 남아 있는데
문항이 가리키지 않는 것들이다. 올려도 서명이 안 나가므로 대역폭만 든다.

과목 이름은 폴더 이름에서 뽑는다(`--subject`로 덮어쓸 수 있다). 서버의
`SUBJECTS`에 없는 이름이면 서버가 404로 막는다.
"""

import hashlib
import json
import os

import sys

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from upload_web import BATCH, runner_token, setting


def load_db(folder):
    """`quiz_db.json`이면 그대로, `quiz_db.js`면 배열만 떼어 낸다.

    해부학 넷은 `const QUIZ_DB = [ … ];` 형태의 스크립트다. 파일이 `<script src>`로
    읽히던 시절의 모양이고, 지금은 로그인한 사람에게만 JSON으로 나간다.
    """
    as_json = os.path.join(folder, "quiz_db.json")
    if os.path.isfile(as_json):
        return json.load(open(as_json, encoding="utf-8"))
    as_js = os.path.join(folder, "quiz_db.js")
    if not os.path.isfile(as_js):
        raise SystemExit(f"{folder}에 quiz_db.json도 quiz_db.js도 없습니다.")
    text = open(as_js, encoding="utf-8").read()
    start, end = text.index("["), text.rindex("]")
    return json.loads(text[start : end + 1])


def image_name(item):
    """문항 하나가 가리키는 사진의 **파일명**. 경로는 버린다.

    과목마다 어느 칸에 경로가 있는지가 다르다 — 해부학 셋은 `image_path`,
    neuro는 `image_filename`에 폴더까지 들어 있다. R2에서는 과목이 이미 키에
    있으므로 폴더 이름은 필요 없고, 파일명만 쓰면 셋이 같은 규칙이 된다.
    """
    for key in ("image_path", "image_filename", "image"):
        value = str(item.get(key) or "").replace("\\", "/").strip()
        if value:
            return value.rsplit("/", 1)[-1]
    return ""


def find_images(folder, wanted):
    """사진이 실제로 어느 폴더에 있는지 찾는다. 이름 → 경로."""
    found = {}
    for root, _dirs, files in os.walk(folder):
        for name in files:
            if name in wanted and name not in found:
                found[name] = os.path.join(root, name)
    return found


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__.strip().splitlines()[2].strip())
    folder = os.path.abspath(args[0])
    if not os.path.isdir(folder):
        raise SystemExit(f"폴더가 없습니다: {folder}")
    subject = (
        sys.argv[sys.argv.index("--subject") + 1]
        if "--subject" in sys.argv
        else os.path.basename(folder.rstrip("/\\"))
    )

    api = setting("SPOTTER_API_BASE", "apiBase").rstrip("/")
    if not api:
        raise SystemExit("web/config.js의 apiBase가 비어 있습니다.")
    token = runner_token()
    if not token:
        raise SystemExit("RUNNER_TOKEN을 못 찾았습니다. Study_EZ_Open/server/.env를 보세요.")
    auth = {"Authorization": f"Bearer {token}"}
    base = f"{api}/api/spotter/admin/subjects/{subject}"

    items = load_db(folder)
    # 두 모양이 있다. 해부학은 문항 배열 그대로고, 기생충학은 `{meta, questions}`다
    # (`build_web.py`가 유형 비율과 개수를 같이 싣는다). 사진을 세는 것은
    # 문항 쪽이고, 올리는 것은 받은 모양 그대로다 — 화면이 그 모양을 안다.
    questions = items["questions"] if isinstance(items, dict) else items
    wanted = {image_name(it) for it in questions} - {""}
    local = find_images(folder, wanted)
    missing = sorted(wanted - set(local))
    print(f"[{subject}] 문항 {len(questions)}개 · 사진 {len(wanted)}장")
    if missing:
        # 올리기는 하되 말한다. 없는 사진은 화면에서 빈 칸이 되고, 그 사실을
        # 여기서 안 알리면 나중에 한 문항씩 발견하게 된다.
        print(f"  못 찾은 사진 {len(missing)}장: {missing[:3]}")

    r = requests.get(f"{base}/manifest", headers=auth, timeout=120)
    if r.status_code == 404:
        raise SystemExit(f"서버가 모르는 과목입니다: {subject} (routes/spotter.py의 SUBJECTS)")
    r.raise_for_status()
    remote = r.json()["images"]

    todo = [
        name
        for name, path in sorted(local.items())
        if remote.get(name) != hashlib.md5(open(path, "rb").read()).hexdigest()
    ]
    size = sum(os.path.getsize(local[n]) for n in todo)
    print(f"  올릴 것 {len(todo)}장  {size / 1e6:.1f}MB")

    sent = 0
    for i in range(0, len(todo), BATCH):
        chunk = todo[i : i + BATCH]
        r = requests.post(f"{base}/uploads", headers=auth, json={"names": chunk}, timeout=180)
        r.raise_for_status()
        urls = r.json()["images"]
        for name in chunk:
            ext = name.rsplit(".", 1)[-1].lower()
            ctype = {"png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
            with open(local[name], "rb") as fh:
                put = requests.put(urls[name], data=fh, headers={"Content-Type": ctype}, timeout=600)
            put.raise_for_status()
            sent += 1
            if sent % 50 == 0 or sent == len(todo):
                print(f"    {sent}/{len(todo)}")

    # ── 문항 DB
    #
    # **JSON으로 통일해서 올린다.** 과목마다 quiz_db.js와 quiz_db.json이 섞여
    # 있었는데, 서버가 내보내는 것은 어차피 JSON이고 화면도 fetch로 읽는다.
    raw = json.dumps(items, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    r = requests.post(f"{base}/uploads", headers=auth, json={"names": [], "db": True}, timeout=60)
    r.raise_for_status()
    put = requests.put(
        r.json()["db"], data=raw, headers={"Content-Type": "application/json"}, timeout=600
    )
    put.raise_for_status()
    requests.post(f"{base}/db/refresh", headers=auth, timeout=30)
    print(f"  quiz_db.json {len(raw) / 1e6:.2f}MB · 끝")


if __name__ == "__main__":
    main()
