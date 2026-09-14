"""만들어진 문항을 훑어 **풀 수 없는 문항**을 찾는다.

    uv run --python 3.13 python scripts/audit_questions.py
    uv run --python 3.13 --with pymupdf python scripts/audit_questions.py --pdf

`build/quiz_db.json`을 읽는다. 먼저 `scripts/build_web.py`를 돌려 둘 것.

여기서 보는 것은 "정답이 맞느냐"가 아니라 **"이 문항이 성립하느냐"**다. 문항은
자동 생성이라 정답이 맞아도 성립하지 않는 경우가 있고, 그건 푸는 사람 쪽에서는
자기 실력 부족과 구별이 안 된다. 그래서 기계가 볼 수 있는 것만 여기서 본다.

  1. **보기 포함관계** — 한 보기가 다른 보기의 부분집합이면 채점이 성립하지 않는다.
     (`사람` vs `사람·소`) `generate_exam.contains`가 막고 있으므로 0이어야 한다.
  2. **사진 결함** — 흐린 사진, 표본 매핑이 `high`가 아닌 사진.
  3. **indicator** — 표시가 실제로 찍힌 사진에서만 나와야 한다. 화살표가 없으면
     안 풀리고, 화살표 옆에 구조물 이름이 적혀 있으면 답이 새어 나온다. 쓸 수 있는
     자리는 `images/practical_ind/`(이름을 가린 것)와 `questions/`(족보) 둘뿐이다.
  4. **동정 문항의 정답↔오답 쌍** — 기계는 두 종이 사진으로 갈리는지 모른다.
     실제로 쓰인 쌍을 전부 뽑아 CSV로 내보내므로, 사람이 보고 "이건 사진으로는
     못 가른다" 싶은 줄에 표시해 `exclude_distractors`로 옮기면 된다.

`--pdf`를 주면 실제실습본 PDF를 다시 열어 잘라낸 자리를 검사한다.
`get_pixmap(clip=bbox)`는 **그 자리에 있는 것을 전부 그리므로**, 사진이 겹쳐
있으면 옆 사진 조각이 딸려 들어오고 사진 위에 적힌 글씨도 같이 구워진다.
"""

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_exam import contains, similar, norm  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
BUILD = os.path.join(ROOT, "build")

# 이 아래로는 초점이 나갔다고 보는 선명도. 생성기가 이미 하위 10%를 버리지만
# 그 기준선(9 남짓)이 "볼 만하다"는 뜻은 아니다.
BLURRY = 12.0


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def head(title):
    print(f"\n── {title}")


def check_options(qs):
    """보기 넷 중 둘이 같거나 상하위 관계인 문항."""
    bad = []
    for q in qs:
        o = q["options"]
        for i in range(len(o)):
            for j in range(i + 1, len(o)):
                if norm(o[i]) == norm(o[j]) or contains(o[i], o[j]) or similar(o[i], o[j]):
                    answered = q["answer"] in (i, j)
                    bad.append((q, o[i], o[j], answered))
    head("보기 포함관계")
    if not bad:
        print("    없음")
        return
    real = len({q["id"] for q, _, _, ans in bad if ans})
    print(f"    {len({q['id'] for q, *_ in bad})}문항 (정답이 낀 것 {real}문항)")
    for (q, a, b, ans) in bad[:20]:
        print(f"      [{q['qtype']}] {a}  ↔  {b}{'   ← 복수정답' if ans else ''}")


def check_images(qs, imeta, images):
    by_path = {r["path"]: r for r in images}
    used = {v["path"] for v in imeta.values()}

    head("사진 품질")
    blurry = {n for n, v in imeta.items() if v["sharp"] < BLURRY}
    nq = sum(1 for q in qs if q["image"] in blurry)
    print(f"    선명도 {BLURRY} 미만: 사진 {len(blurry)}장 / 문항 {nq}개")

    conf = Counter(by_path[p]["confidence"] for p in used if p in by_path)
    print(f"    사진→표본 매핑 신뢰도: {dict(conf)}")
    shaky = {n for n, v in imeta.items()
             if by_path.get(v["path"], {}).get("confidence") != "high"}
    print(f"      high가 아닌 사진이 쓰인 문항 {sum(1 for q in qs if q['image'] in shaky)}개")

    head("사진 출처별 문항 수")
    for k, v in Counter(imeta[q["image"]]["path"].split("/")[0] for q in qs).most_common():
        print(f"    {k:16s} {v:5d}")


# indicator 문항이 나와도 되는 사진의 자리. 여기 밖에서 나온 indicator는
# 화살표가 없거나(정리본·통합) 이름이 함께 적혀 있다(원본 실제실습본 크롭).
INDICATOR_OK = ("practical_ind/", "questions/")


def check_indicator(qs, imeta):
    """indicator는 표시가 실제로 찍힌 사진에서만 나와야 한다.

    쓸 수 있는 자리는 둘뿐이다 — 이름을 가리고 다시 자른 실제실습본
    (`scripts/extract_indicators.py`)과, 진짜 indicator가 찍힌 족보 사진.
    """
    ind = [q for q in qs if q["qtype"] == "indicator"]
    head("indicator 문항")
    if not ind:
        print("    없음")
        return
    src = Counter(imeta[q["image"]]["path"].rsplit("/", 1)[0] + "/" for q in ind)
    print(f"    {len(ind)}문항 / 사진 {len({q['image'] for q in ind})}장")
    bad = 0
    for k, v in src.most_common():
        ok = k.startswith(INDICATOR_OK)
        print(f"      {'  ' if ok else '✗ '}{k:28s} {v:4d}" + ("" if ok else "  ← 표시가 없는 사진"))
        if not ok:
            bad += v
    if bad:
        print(f"    {bad}문항이 표시 없는 사진에서 나왔다. scripts/extract_indicators.py를 보라.")


def dump_pairs(qs, path):
    """동정 문항에 실제로 쓰인 정답↔오답 쌍. 사람이 검토할 목록이다."""
    rows = defaultdict(int)
    for q in qs:
        if q["qtype"] not in ("충란 동정", "종 동정"):
            continue
        ans = q["options"][q["answer"]]
        for i, o in enumerate(q["options"]):
            if i != q["answer"]:
                rows[(q["specimen_id"], q["label"], ans, o)] += 1
    # **사람이 표시해 둔 것을 덮지 않는다.** 이 표는 손으로 채우라고 있는 것이라,
    # 감사를 다시 돌린다고 지워지면 표시할 이유가 없어진다.
    marked = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for row in list(csv.reader(fh))[1:]:      # 머리글의 열 이름은 표시가 아니다
                if len(row) >= 6 and row[5].strip():
                    marked[(row[0], row[2], row[3])] = row[5].strip()
    if marked:
        path = path.replace(".csv", ".new.csv")

    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["specimen_id", "표본", "정답", "오답으로 쓰인 종", "문항수",
                    "사진으로_구별불가(체크)"])
        for (spec, label, ans, other), n in sorted(rows.items(), key=lambda x: -x[1]):
            w.writerow([spec, label, ans, other, n, marked.get((spec, ans, other), "")])
    head("동정 문항의 정답↔오답 쌍")
    print(f"    {len(rows)}쌍 → {os.path.relpath(path, ROOT)}")
    if marked:
        print(f"    표시해 둔 {len(marked)}줄이 있어 원본은 그대로 두고 옆에 새로 썼다.")
    print("    사진만으로 못 가르는 줄에 표시해서 표본의 exclude_distractors로 옮길 것.")


def check_pdf(imeta):
    """실제실습본에서 잘라낸 자리에 남의 것이 섞여 들어왔는지."""
    import pymupdf
    import extract_practical_pdf as E

    head("실제실습본 크롭 (--pdf)")
    if not os.path.exists(E.PDF):
        print("    PDF를 못 찾았습니다:", E.PDF)
        return
    used = {v["path"] for v in imeta.values()}
    doc = pymupdf.open(E.PDF)
    overlap = text = 0
    hit = set()
    for pno in range(doc.page_count):
        page = doc[pno]
        infos = [i for i in page.get_image_info()
                 if (i["bbox"][2] - i["bbox"][0]) >= E.MIN_SIDE
                 and (i["bbox"][3] - i["bbox"][1]) >= E.MIN_SIDE]
        boxes = [pymupdf.Rect(i["bbox"]) for i in infos]
        words = page.get_text("words")
        for k, box in enumerate(boxes):
            rel = f"practical/{pno + 1:03d}_{k + 1}.png"
            ov = any(j != k and (box & boxes[j]).get_area() > 0.02 * box.get_area()
                     for j in range(len(boxes)))
            tx = any(pymupdf.Rect(w[:4]).intersects(box) for w in words)
            overlap += ov
            text += tx
            if ov or tx:
                hit.add(rel)
    mine = {p for p in used if p.startswith("practical/")}
    print(f"    잘라낸 사진 {sum(1 for _ in hit) and len(hit) or 0}장이 결함 "
          f"(겹침 {overlap}, 크롭 안 텍스트 {text})")
    print(f"    문제로 쓰는 실제실습본 사진 {len(mine)}장 중 {len(hit & mine)}장이 해당")
    print("    원인은 get_pixmap(clip=bbox)가 '그 자리에 있는 것을 전부' 그리는 것이다.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", action="store_true", help="실제실습본 PDF까지 다시 검사")
    args = ap.parse_args()

    db_path = os.path.join(BUILD, "quiz_db.json")
    if not os.path.exists(db_path):
        raise SystemExit("build/quiz_db.json이 없습니다. scripts/build_web.py를 먼저 돌리세요.")
    db = load(db_path)
    qs, imeta = db["questions"], db["meta"]["images"]
    images = load(os.path.join(DATA, "images.json"))

    print(f"문항 {len(qs)}개 · 사진 {len(imeta)}장")
    check_options(qs)
    check_images(qs, imeta, images)
    check_indicator(qs, imeta)
    dump_pairs(qs, os.path.join(DATA, "identification_pairs.csv"))
    if args.pdf:
        check_pdf(imeta)


if __name__ == "__main__":
    main()
