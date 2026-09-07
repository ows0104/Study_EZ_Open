"""배포되는 사진에 글자가 남았는지 읽어 본다.

    uv run --python 3.13 --with pillow --with rapidocr-onnxruntime \
        python scripts/audit_baked_text.py

**PDF 텍스트를 지우는 것과 배포본이 깨끗한 것은 다른 얘기다.** 지우는 것은
원본 쪽에서 하고, 배포되는 것은 거기서 잘라 낸 뒤 시야만 남기고 다시 자른
사진이다. 그 사이에 글자가 들어올 자리도, 나갈 자리도 있다 —
`build_web.crop_field()`가 테두리를 잘라 내면서 캡션을 같이 버리기도 하고,
시야 **안**에 적힌 글자는 그대로 남기도 한다.

그래서 **마지막에 나가는 파일**을 읽는다. 원본이 아니라 `build/images/`다.

숫자만인 것(배율 `400x`, 미터자 눈금, SEM 촬영정보)은 글자로 치지 않는다.
답이 아니라 크기 정보고, 오히려 있어야 푸는 문항이 있다.
"""

import hashlib
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_IMG = os.path.join(ROOT, "build", "images")
DB = os.path.join(ROOT, "build", "quiz_db.json")
CACHE_PATH = os.path.join(ROOT, "data", "_ocr_cache.json")
OUT = os.path.join(ROOT, "data", "baked_text.csv")

NUMERIC_RE = re.compile(r"^[\d.,\s]*[xX×]?$")
WORDY_RE = re.compile(r"[A-Za-z]{4,}|[가-힣]{2,}")
MIN_SCORE, MAX_SIDE = 0.5, 1000


def main():
    from PIL import Image
    from rapidocr_onnxruntime import RapidOCR

    if not os.path.isdir(BUILD_IMG):
        raise SystemExit("build/images 가 없습니다. scripts/build_web.py 를 먼저 돌리세요.")
    label = {}
    if os.path.isfile(DB):
        db = json.load(open(DB, encoding="utf-8"))
        for q in db["questions"]:
            label.setdefault(q["image"], (q.get("label") or "", db["meta"]["images"]
                                          .get(q["image"], {}).get("src", "")))

    cache = {}
    if os.path.isfile(CACHE_PATH):
        try:
            cache = json.load(open(CACHE_PATH, encoding="utf-8"))
        except (OSError, ValueError):
            cache = {}

    ocr = RapidOCR()
    names = sorted(os.listdir(BUILD_IMG))
    hits, read = [], 0
    for i, name in enumerate(names, 1):
        im = Image.open(os.path.join(BUILD_IMG, name)).convert("RGB")
        im.thumbnail((MAX_SIDE, MAX_SIDE))
        key = hashlib.sha1(im.tobytes()).hexdigest()
        if key in cache:
            words = cache[key]
        else:
            import numpy as np
            result, _ = ocr(np.asarray(im))
            words = [str(x[1]).strip() for x in (result or [])
                     if float(x[2]) >= MIN_SCORE and len(str(x[1]).strip()) >= 3
                     and not NUMERIC_RE.match(str(x[1]).strip())]
            cache[key] = words
            read += 1
        wordy = [t for t in words if WORDY_RE.search(t)]
        if wordy:
            lab, src = label.get(name, ("", ""))
            hits.append((name, lab, src, " | ".join(wordy)))
        if i % 100 == 0:
            print(f"  {i}/{len(names)}")

    with open(CACHE_PATH, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        import csv
        w = csv.writer(fh)
        w.writerow(["파일", "라벨", "출처", "읽힌 글자"])
        w.writerows(hits)

    print(f"\n배포본 {len(names)}장 · 새로 읽은 것 {read}장")
    print(f"글자가 남은 사진 {len(hits)}장 ({len(hits) / max(1, len(names)) * 100:.1f}%)")
    for name, lab, src, txt in hits[:25]:
        print(f"  {lab[:18]:20s} {txt[:46]:48s} {src[:30]}")
    print(f"\n전체 목록: {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
