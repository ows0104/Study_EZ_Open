"""indicator 문항에 쓸 사진을 실제실습본에서 다시 잘라낸다.

    uv run --python 3.13 --with pymupdf python scripts/extract_indicators.py

출력: images/practical_ind/<쪽>_<번호>.png
      data/indicator_images.json

## 왜 따로 잘라내는가

땡시의 indicator는 사진에 그린 화살표가 아니라 **현미경 접안렌즈에 걸린 선분**이다
(2017년 족보 7번이 그렇게 설명한다 — "파란색 선분으로 보입니다"). 그래서 문제는
"이 선이 짚는 것이 무엇인가"이고, 선이 없는 사진에는 낼 수 없다.

실제실습본에는 정리한 사람이 **화살표를 그려 놨다.** 다만 화살표 옆에 구조물
이름도 같이 적어 놔서, 페이지를 그대로 그리면 답이 사진에 찍혀 나온다.

화살표와 글씨는 PDF 안에서 서로 다른 것이다 — 화살표는 벡터 도형, 이름은 텍스트다.
그래서 **글씨 자리에만 흰 사각형을 덮고 다시 그리면** 화살표는 남고 답은 사라진다.
덮은 글씨가 곧 그 화살표가 무엇을 짚는지 알려주므로, 정답도 여기서 나온다.

같은 김에 옆 사진이 겹쳐 들어오는 자리도 덮는다(`data/README.md`의 「잘라낸 자리에
남의 것이 딸려 온다」). 남의 사진 조각 대신 흰 여백이 남는다.

## 사진 한 장이 문항이 되는 조건

  1. 크롭 안에 **벡터 도형이 있다** — 화살표가 그려져 있다는 뜻이다.
  2. 크롭 안 글씨에서 마스터 테이블의 구조물 이름이 **정확히 하나** 나온다.
     둘이면 화살표가 어느 것을 짚는지 알 수 없다.

323장 중 40장이 통과한다. 나머지는 화살표가 없거나(210장) 이름이 없거나 여럿이다.
"""

import json
import os
import re
import sys

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_practical_pdf as E  # noqa: E402
from generate_exam import norm  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "images", "practical_ind")

# 벡터 도형이 이만큼은 돼야 화살표로 본다. 표 선이나 점 하나를 세지 않으려는 것이다.
MIN_DRAW = 20
# 잘라내는 해상도는 사진마다 다르다 — `extract_practical_pdf.render_dpi`가
# 그 사진이 실제로 가진 만큼을 돌려준다. 같은 값을 써야 원본과 크기가 맞는다.


def structures():
    specs = json.load(open(os.path.join(DATA, "specimens.json"), encoding="utf-8"))
    return sorted({s for x in specs for s in x.get("structures", [])},
                  key=len, reverse=True)


def named_in(text, terms):
    """글씨에서 구조물 이름을 찾는다. 상위어는 버린다.

    `ventral sucker`가 있으면 `sucker`는 같은 것을 가리키므로 세지 않는다 —
    안 그러면 이름이 둘로 세어져 멀쩡한 사진이 걸러진다.
    """
    blob = norm(text)
    got = [s for s in terms if norm(s) and norm(s) in blob]
    return [s for s in got if not any(s != o and norm(s) in norm(o) for o in got)]


def page_images(page):
    infos = [i for i in page.get_image_info()
             if (i["bbox"][2] - i["bbox"][0]) >= E.MIN_SIDE
             and (i["bbox"][3] - i["bbox"][1]) >= E.MIN_SIDE]
    # extract_practical_pdf.py와 **같은 순서여야 한다.** 파일 이름의 번호가
    # 이 순서에서 나오므로, 어긋나면 다른 사진을 가리키게 된다.
    infos.sort(key=lambda i: (round(i["bbox"][1] / 40), i["bbox"][0]))
    return infos


def main():
    if not os.path.exists(E.PDF):
        raise SystemExit(f"PDF를 못 찾았습니다: {E.PDF}")
    terms = structures()
    images = {r["path"]: r for r in
              json.load(open(os.path.join(DATA, "images.json"), encoding="utf-8"))}

    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))

    doc = pymupdf.open(E.PDF)
    picked, skipped = [], {"화살표 없음": 0, "구조물 이름이 없음": 0,
                           "구조물 이름이 여럿": 0, "표본 매핑 없음": 0,
                           "화살표가 가려지는 자리로 향함": 0}

    for pno in range(doc.page_count):
        page = doc[pno]
        infos = page_images(page)
        boxes = [pymupdf.Rect(i["bbox"]) for i in infos]
        words = page.get_text("words")
        draws = page.get_drawings()

        for k, box in enumerate(boxes):
            rel = f"practical/{pno + 1:03d}_{k + 1}.png"
            inside_w = [w for w in words if pymupdf.Rect(w[:4]).intersects(box)]
            arrows = [d for d in draws
                      if pymupdf.Rect(d["rect"]).intersects(box)
                      and (d["rect"][2] - d["rect"][0]) + (d["rect"][3] - d["rect"][1]) > MIN_DRAW]
            if not arrows:
                skipped["화살표 없음"] += 1
                continue
            got = named_in(" ".join(w[4] for w in inside_w), terms)
            if not got:
                skipped["구조물 이름이 없음"] += 1
                continue
            if len({norm(g) for g in got}) > 1:
                skipped["구조물 이름이 여럿"] += 1
                continue
            src = images.get(rel)
            if not src or not src.get("specimen_id"):
                skipped["표본 매핑 없음"] += 1
                continue
            # 겹친 자리를 덮으면 그 자리는 흰 여백이 된다. **화살표가 그리로
            # 향하고 있으면 짚는 것을 같이 덮는 것이므로** 이 사진은 못 쓴다.
            covered = [box & other for j, other in enumerate(boxes)
                       if j != k and (box & other).get_area() > 0]
            if any(pymupdf.Rect(a["rect"]).intersects(c)
                   for a in arrows for c in covered):
                skipped["화살표가 가려지는 자리로 향함"] += 1
                continue

            # ── 덮고 다시 그린다. 크롭마다 PDF를 새로 열고 그 사본에만 덮는다.
            #
            # **`draw_rect`는 이 PDF에서 아무것도 그리지 않는다.** 페이지 내용
            # 스트림이 `q`를 닫지 않고 끝나서, 뒤에 붙인 것이 그 그래픽 상태에
            # 딸려 들어가 화면 밖으로 나간다. 리댁션은 내용 스트림을 다시 쓰므로
            # 그 영향을 안 받는다 — 그래서 리댁션으로 덮는다.
            one = pymupdf.open(E.PDF)
            p2 = one[pno]
            for w in inside_w:                       # 글씨 = 답
                p2.add_redact_annot(pymupdf.Rect(w[:4]), fill=(1, 1, 1))
            for j, other in enumerate(boxes):        # 겹쳐 들어오는 옆 사진
                if j == k:
                    continue
                hit = box & other
                if hit.get_area() > 0:
                    p2.add_redact_annot(hit, fill=(1, 1, 1))
            # 사진은 건드리지 않는다. 지우는 것은 글씨와 그 자리의 벡터뿐이다.
            p2.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
            name = f"{pno + 1:03d}_{k + 1}.png"
            p2.get_pixmap(clip=box, dpi=E.render_dpi(infos[k])).save(
                os.path.join(OUT, name))
            one.close()

            rec = dict(src)
            rec["path"] = f"practical_ind/{name}"
            rec["from"] = rel
            rec["structure"] = got[0]
            rec["masked_words"] = [w[4] for w in inside_w]
            rec["arrows"] = len(arrows)
            # 라벨을 가린 사진이라는 표시. 앱의 출처 줄이 이걸 읽는다.
            rec["masked"] = True
            picked.append(rec)

    with open(os.path.join(DATA, "indicator_images.json"), "w", encoding="utf-8") as fh:
        json.dump(picked, fh, ensure_ascii=False, indent=2)

    print(f"indicator 사진 {len(picked)}장  → images/practical_ind/")
    print(f"제외: {skipped}")
    from collections import Counter
    print("\n─ 구조물별")
    for k, v in Counter(r["structure"] for r in picked).most_common():
        print(f"    {k:24s} {v}")


if __name__ == "__main__":
    main()
