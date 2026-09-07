"""웹 앱용 문항 DB와 이미지를 만든다.

    uv run --python 3.13 --with pillow python scripts/build_web.py

출력: build/quiz_db.json  문항 전체 (보기·정답·해설·가중치 포함)
      build/images/*.jpg  문항이 쓰는 사진만 리사이즈해서 복사

**둘 다 배포물이 아니라 올릴 것의 원본이다.** 사진과 문항 DB는 R2 비공개
버킷으로 가고(`scripts/upload_web.py`) 로그인한 사람에게만 나간다. 배포되는
정적 파일은 `web/index.html`·`app.js`·`auth.js`·`config.js` 넷뿐이다.

문항 조립(어떤 40문항을 뽑을지)은 브라우저에서 한다. 여기서는 후보를 전부
완성된 문항으로 만들어 넘긴다 — 오답 생성은 마스터 테이블을 봐야 해서
서버에서 미리 해두는 편이 안전하다.
"""

import hashlib
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_exam import Generator, GROUP_MIX, QTYPE_MIX, GROUP_ORDER  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
# 생성물은 web/ 밖에 둔다. 안 그러면 배포 폴더를 통째로 올리는 순간
# 문항 DB와 사진이 로그인 없이 공개된다 — 그것이 이 전체 구조가 막는 일이다.
BUILD = os.path.join(ROOT, "build")
BUILD_IMG = os.path.join(BUILD, "images")
# **확대해서 보라고 있는 사진이다.** 900px는 화면에 맞춰 놓기에는 충분하지만
# 400x 시야에서 충란 하나를 찾는 데는 모자란다 — 눌러서 키우면 그때부터는
# 없는 픽셀을 늘리는 것이라 뿌옇게만 커졌다. 원본이 가진 만큼은 내보낸다.
# (`thumbnail`은 키우지 않으므로 작은 원본은 작은 그대로 나간다.)
MAX_SIDE = 1600
QUALITY = 82

# ── 시야 잘라내기
#
# 실습 사진 상당수는 **접안렌즈에 휴대폰을 대고 찍은 것**이다. 그래서 밝은
# 원(시야) 둘레에 렌즈 경통의 검은 테가 넓게 남고, 위쪽에는 천장이나 옆
# 사람이 같이 찍혀 있다. 606장 중 125장은 시야가 화면의 80%도 못 채웠고,
# 60장은 절반도 못 채웠다 — 화면에 맞춰 놓으면 정작 봐야 할 충란은 그
# 절반보다 더 작아진다. "저게 뭔지 모르겠다"는 말이 여기서 나온다.
#
# 그래서 시야만 남기고 테를 자른다. 자르면 같은 화면 크기에 시야가 꽉 차므로
# 배율을 올리지 않고도 표본이 두 배로 커진다.
SMALL = 200          # 판정은 축소본에서 한다. 원본을 훑으면 장당 몇 초씩 걸린다
MIN_SPAN = 0.35      # 짧은 변의 이만큼은 돼야 시야로 본다
# **되찾을 것이 많을 때만 자른다.** 시야가 이미 화면의 60% 넘게 차 있으면
# 잘라 봐야 조금 커질 뿐인데, 그런 사진에는 옆 칸에 다른 배율 사진이나 작은
# 확대 사진이 붙어 있는 것이 섞여 있어서 잘못 자르면 그 칸을 통째로 잃는다.
# 실제로 0.62·0.79짜리 두 장이 그렇게 아래 칸을 잃었다. 얻는 것이 적고 잃을
# 것이 있는 구간이라 손대지 않는다.
MAX_AREA = 0.60
DARK_RATIO = 0.55    # 바깥이 시야보다 이만큼은 어두워야 '테두리'다
MARGIN = 0.012       # 화면 끝에 이만큼 붙어 있으면 '닿았다'고 본다
EDGES_OK = 1         # 닿아도 되는 변의 수
FILL_MIN = 0.55      # 덩어리가 자기 bbox를 이만큼은 채워야 원반이다
ASPECT = 1.6         # 시야는 원이다. 이보다 길쭉하면 시야가 아니다
PAD = 0.015          # 잘라낸 자리에 조금 여유를 둔다


def field_box(im):
    """가장 큰 '밝은 덩어리'와 그 안팎의 밝기.

    임계값을 최댓값이 아니라 **98퍼센타일**에서 잡는다 — 경통 가장자리의
    반사나 화면에 비친 형광등 한 점이 최댓값을 끌어올리면 시야 전체가 임계
    아래로 떨어져 아무것도 못 찾는다.

    덩어리를 이어 붙여서 세는 것도 이유가 있다. 밝은 픽셀의 bbox를 그냥
    쓰면 위쪽에 같이 찍힌 실험실 천장이 bbox를 화면 전체로 벌려 놓는다.
    """
    from PIL import Image  # noqa: F401  (호출부에서 이미 들여왔다)
    from collections import deque

    g = im.convert("L").copy()
    g.thumbnail((SMALL, SMALL))
    w, h = g.size
    px = g.load()
    vals = sorted(g.getdata())
    thr = vals[int(len(vals) * 0.98)] * 0.62

    seen = [[False] * w for _ in range(h)]
    best = None
    for sy in range(h):
        for sx in range(w):
            if seen[sy][sx] or px[sx, sy] < thr:
                continue
            q = deque([(sx, sy)])
            seen[sy][sx] = True
            x0 = x1 = sx
            y0 = y1 = sy
            n = 0
            while q:
                x, y = q.popleft()
                n += 1
                x0 = min(x0, x); x1 = max(x1, x)
                y0 = min(y0, y); y1 = max(y1, y)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and px[nx, ny] >= thr:
                        seen[ny][nx] = True
                        q.append((nx, ny))
            if best is None or n > best[0]:
                best = (n, x0, y0, x1, y1)
    if not best:
        return None
    n, x0, y0, x1, y1 = best
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    inside = ni = outside = no = 0
    for y in range(h):
        for x in range(w):
            v = px[x, y]
            if x0 <= x <= x1 and y0 <= y <= y1:
                inside += v; ni += 1
            else:
                outside += v; no += 1
    return {
        "box": (x0 / w, y0 / h, (x1 + 1) / w, (y1 + 1) / h),
        "span": min(bw / w, bh / h),
        "area": (bw / w) * (bh / h),
        "fill": n / (bw * bh),
        "aspect": max(bw / bh, bh / bw),
        "inside": inside / max(ni, 1),
        "outside": outside / max(no, 1),
    }


def crop_field(im):
    """시야만 남긴 이미지. 자를 만하지 않으면 원본을 그대로 돌려준다.

    걸러내는 조건이 넷인데 전부 **자르면 안 되는 사진**을 지키려고 있다.
    특히 `EDGES_OK` — 덩어리가 화면 끝에 닿아 있으면 어두운 쪽은 시야 밖이
    아니라 표본의 배경일 수 있다. 이 조건이 없을 때 족보의 육안 표본(초록
    천 위에 놓인 충체) 하나가 세로로 반토막이 났다.

    다만 **한 변까지는 봐준다.** 실제 시야가 사진 밖으로 조금 밀려 나간
    경우가 그렇게 걸리는데, 30장을 세어 보니 한 변만 닿은 19장은 전부
    멀쩡한 시야였고 반대로 위험한 것(육안 표본·족보 스캔)은 세 변에
    닿아 있었다.
    """
    f = field_box(im)
    if not f:
        return im, False
    x0, y0, x1, y1 = f["box"]
    edges = sum((x0 < MARGIN, y0 < MARGIN, x1 > 1 - MARGIN, y1 > 1 - MARGIN))
    if (f["area"] > MAX_AREA
            or f["span"] < MIN_SPAN
            or f["outside"] > f["inside"] * DARK_RATIO
            or edges > EDGES_OK
            or f["fill"] < FILL_MIN or f["aspect"] > ASPECT):
        return im, False
    w, h = im.size
    return im.crop((max(0, int((x0 - PAD) * w)), max(0, int((y0 - PAD) * h)),
                    min(w, int((x1 + PAD) * w)), min(h, int((y1 + PAD) * h)))), True


def nkey(s):
    return re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())


def flat(path):
    return re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", path).rsplit(".", 1)[0] + ".jpg"


# 사진마다 어디서 온 것인지. 흐리거나 잘못 잘린 사진을 만났을 때 원본을 찾아갈
# 자리가 없으면 신고가 "3번 사진이 이상함"에서 멈춘다.
SOURCE_KO = {
    "practical": "실제실습본",
    "tonghap": "2026 실습사진통합",
    "jiseok": "실습 정리본(이지석)",
    "eunju": "실습 정리본(신은주)",
    "note": "2026 실습 필기본",
}
JMS = "실습 정리본(전민서)"
# PDF에서 뽑은 것들. 엑셀과 달리 시트·셀이 아니라 **몇 번째 쪽**이 자리다.
FROM_PDF = ("practical", "jiseok", "eunju", "note")


def source_line(rec):
    """사람이 읽는 출처 한 줄.

    `실제실습본 p.8`, `2026 실습사진통합 충란 D2`,
    `실습 정리본(이지석) 실습 2 p2-3`.
    """
    src = rec.get("source") or ""
    who = SOURCE_KO.get(src) or (JMS if src.startswith("jms_") else src)
    if src == "practical":
        return f"{who} p.{rec.get('page')}"
    if src in FROM_PDF:
        # 이 셋은 PDF가 여러 개라 쪽 번호만으로는 어느 파일인지 알 수 없다.
        # `cell`이 「실습 2 p2-3」처럼 파일과 쪽을 같이 들고 있다.
        return f"{who} {rec.get('cell') or 'p.' + str(rec.get('page'))}".strip()
    where = " ".join(x for x in [rec.get("sheet"), rec.get("cell")] if x)
    return f"{who} {where}".strip()


def past_indicator(gen):
    """족보의 indicator 문항을 그대로 가져온다.

    **여기에는 진짜 indicator가 있다.** 땡시의 indicator는 사진에 그린 화살표가
    아니라 현미경 접안렌즈에 걸린 파란 선분이고, 족보 사진에는 그 선이 찍혀 있다
    (2017년 7번 지문이 그렇게 설명한다).

    지문·보기·정답이 전부 실제 시험의 것이므로 만들지 않고 그대로 쓴다. 다만
    표본 연결은 없다 — 구조물 이름으로 되짚는다. `ovary`처럼 여러 종에 걸치는
    구조물은 사진을 봐야 갈리므로 **연결하지 않고 비워 둔다**(분류군 비율 계산에서
    빠질 뿐, 문항 자체는 멀쩡하다).

    **사진은 딸린 것을 전부 가져온다.** 실제 땡시는 한 문항에 현미경 둘, 또는
    현미경 하나와 데모 하나를 같이 놓고 묻는 자리가 있고, 족보도 그대로 두 장을
    싣는다. 첫 장만 쓰면 2019년 16번처럼 **indicator가 둘째 장에만 찍힌 문항이
    화살표 없는 사진만 남아** 무엇을 묻는지 알 수 없게 된다.
    """
    path = os.path.join(ROOT, "data", "past_questions_linked.json")
    if not os.path.exists(path):
        return []
    rows = json.load(open(path, encoding="utf-8"))
    if isinstance(rows, dict):
        rows = rows.get("questions", rows)

    by_struct = {}
    for x in gen.specimens:
        for st in x.get("structures", []):
            by_struct.setdefault(nkey(st), []).append(x)

    out = []
    for q in rows:
        if q.get("qtype") != "indicator" or q.get("answer_kind") != "structure":
            continue
        if not (q.get("answer_structure") and q.get("image_paths")
                and q.get("options") and len(q["options"]) >= 4
                and q.get("answer_index") is not None):
            continue
        imgs = [os.path.join(ROOT, "questions", p) for p in q["image_paths"]]
        imgs = [p for p in imgs if os.path.exists(p)]
        if not imgs:
            continue
        # 족보에 "복원 안됨"으로 남은 보기가 섞인 문항이 있다. 보기가 서로 같으면
        # 채점이 성립하지 않으므로 낸다는 것 자체가 말이 안 된다.
        opts = [str(o).strip() for o in q["options"]]
        if len({nkey(o) for o in opts}) != len(opts) or any(
                "복원" in o or not nkey(o) for o in opts):
            continue
        cands = by_struct.get(nkey(q["answer_structure"]), [])
        sids = {c["species_id"] for c in cands}
        spec = cands[0] if len(sids) == 1 else None
        sp = gen.sp[spec["species_id"]] if spec else None
        out.append({
            "year": q["year"], "no": q["no"], "imgs": imgs,
            "stem": q["stem"], "options": q["options"],
            "answer": q["answer_index"], "structure": q["answer_structure"],
            "spec": spec, "sp": sp,
        })
    return out


def question_id(specimen_id, qtype, correct, image_path):
    """문항 고유번호. 내용에서 뽑으므로 표본이나 사진이 늘어도 바뀌지 않는다.

    순번(q0001, q0002 …)을 쓰면 앞쪽에 사진 한 장만 추가돼도 그 뒤가 전부 밀려
    localStorage에 저장된 오답노트가 엉뚱한 문제를 가리키게 된다.
    """
    key = "|".join([specimen_id, qtype, correct, image_path])
    return "q" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def main():
    gen = Generator(seed=20260906)
    cands = gen.candidates()
    print(f"후보 {len(cands)}개")

    by_path = {r["path"]: r for r in gen.images}
    questions, used, seen_ids, img_meta = [], {}, {}, {}
    for i, cand in enumerate(cands):
        q = gen.build(cand, i + 1, 0)
        if not q:
            continue
        # 문항 하나에 사진 하나. 사진이 다르면 이미 별개 문항이다.
        name = flat(cand["image"]["path"])
        used[name] = os.path.join(ROOT, "images", cand["image"]["path"])
        rec = by_path.get(cand["image"]["path"], cand["image"])
        img_meta[name] = {
            "src": source_line(rec),
            "path": rec["path"],
            "sharp": round(rec.get("sharpness") or 0, 1),
        }
        spec = gen.spec[q["specimen_id"]]
        qid = question_id(q["specimen_id"], q["qtype"], q["answer"],
                          cand["image"]["path"])
        if qid in seen_ids:
            raise SystemExit(f"문항 id 충돌 {qid}: {seen_ids[qid]} / {q['stem']}")
        seen_ids[qid] = q["stem"]
        questions.append({
            "id": qid,
            "qtype": q["qtype"],
            "stem": q["stem"],
            "image": name,
            "options": q["options"],
            "answer": q["answer_index"],
            "explanation": q["explanation"],
            "species_id": q["species_id"],
            "specimen_id": q["specimen_id"],
            "label": spec["label_ko"],
            "group": q["group"],
            "specimen_type": spec["specimen_type"],
            "stain": spec.get("stain") or "",
            "magnification": spec.get("magnification") or "",
            "weight": q["exam_weight"],
            "years": q["past_years"],
        })

    # ── 족보 indicator 문항
    #
    # 생성한 indicator는 정리본에 그려진 표시를 쓰지만, 족보 사진에는 실제 시험의
    # indicator(파란 선분)가 그대로 찍혀 있다. 지문·보기·정답도 실제 것이다.
    past = past_indicator(gen)
    for q in past:
        # 사진이 둘인 문항이 있다 — 현미경 + 데모, 또는 현미경 둘. 전부 내보내고
        # 문항에는 순서대로 달아 준다. 첫 장은 `image`에도 그대로 두어서 사진
        # 하나를 기대하는 쪽(다시보기 섬네일·신고·audit)이 그대로 돈다.
        names = []
        for i, path in enumerate(q["imgs"]):
            rel = os.path.relpath(path, os.path.join(ROOT, "questions"))
            name = "jokbo_" + flat(rel)
            used[name] = path
            n = f"{q['year']}년 족보 {q['no']}번"
            if len(q["imgs"]) > 1:
                n += f" (사진 {i + 1}/{len(q['imgs'])})"
            img_meta[name] = {"src": n, "path": "questions/" + rel.replace("\\", "/"),
                              "sharp": 0}
            names.append(name)
        name = names[0]
        spec, sp = q["spec"], q["sp"]
        qid = "j" + hashlib.sha1(f'{q["year"]}|{q["no"]}'.encode()).hexdigest()[:9]
        if qid in seen_ids:
            raise SystemExit(f"문항 id 충돌 {qid}")
        seen_ids[qid] = q["stem"]
        expl = f"{q['year']}년 족보 {q['no']}번. 정답 {q['structure']}."
        if spec:
            why = " / ".join(spec.get("key_features", [])[:2])
            expl += chr(10) + spec["label_ko"] + (f" — {why}" if why else "")
        questions.append({
            "id": qid,
            "qtype": "indicator",
            "stem": q["stem"],
            "image": name,
            # 한 장짜리에는 달지 않는다. 5,300문항이 같은 값을 한 번 더
            # 들고 가면 DB만 커지고 읽는 쪽은 `q.images || [q.image]`로 같다.
            **({"images": names} if len(names) > 1 else {}),
            "options": q["options"],
            "answer": q["answer"],
            "explanation": expl,
            # 표본을 못 짚은 문항은 자기 자신을 표본으로 삼는다. 세트 안에서
            # 중복 회피만 하면 되고, 없는 표본을 있다고 하지 않는다.
            "species_id": (sp or {}).get("id") or f"jokbo_{q['year']}_{q['no']}",
            "specimen_id": (spec or {}).get("id") or f"jokbo_{q['year']}_{q['no']}",
            "label": (spec or {}).get("label_ko") or f"{q['year']}년 족보 {q['no']}번",
            "group": (sp or {}).get("group"),
            "specimen_type": (spec or {}).get("specimen_type") or "",
            "stain": (spec or {}).get("stain") or "",
            "magnification": (spec or {}).get("magnification") or "",
            "weight": 3.0,          # 실제 출제된 문항이다. 자주 나오게 둔다
            "years": [str(q["year"])],
            "jokbo": True,
        })
    print(f"족보 indicator {len(past)}문항 (표본 연결 {sum(1 for q in past if q['spec'])}건"
          f" / 사진 여러 장 {sum(1 for q in past if len(q['imgs']) > 1)}문항)")

    # ── 이미지 리사이즈
    if os.path.isdir(BUILD_IMG):
        shutil.rmtree(BUILD_IMG)
    os.makedirs(BUILD_IMG, exist_ok=True)
    from PIL import Image, ImageFilter
    total = cut = 0
    for name, src in sorted(used.items()):
        im = Image.open(src).convert("RGB")
        im, did = crop_field(im)
        cut += did
        im.thumbnail((MAX_SIDE, MAX_SIDE))
        dest = os.path.join(BUILD_IMG, name)
        im.save(dest, "JPEG", quality=QUALITY, optimize=True)
        total += os.path.getsize(dest)
        # **선명도는 내보낸 사진에서 다시 잰다.** `images.json`의 값은 자르기
        # 전 원본에서 잰 것이라, 화면의 절반이 경통의 검은 테였던 사진은
        # 실제로는 멀쩡한데도 낮게 나온다 — 그대로 쓰면 잘 찍힌 사진에
        # "흐린 사진"이라고 붙여 놓게 된다.
        if name in img_meta:
            g = im.convert("L")
            g.thumbnail((256, 256))
            px = list(g.filter(ImageFilter.FIND_EDGES).getdata())
            img_meta[name]["sharp"] = round(sum(px) / len(px), 1)
    print(f"시야만 남기고 자른 사진 {cut}장 / {len(used)}장")

    meta = {
        "generated": "scripts/build_web.py",
        "qtype_mix": QTYPE_MIX,
        "group_mix": GROUP_MIX,
        "group_order": GROUP_ORDER,
        # 사진 → 출처. 문항마다 넣으면 6,461번 되풀이되므로 사진 쪽에 한 번만 둔다.
        "images": img_meta,
        "counts": {
            "questions": len(questions),
            "images": len(used),
            "specimens": len({q["specimen_id"] for q in questions}),
            "species": len({q["species_id"] for q in questions}),
        },
    }
    # ── quiz_db.json
    #
    # **JS가 아니라 JSON이다.** 예전에는 `<script src="quiz_db.js">`로 읽혔지만
    # 지금은 사진과 함께 R2 비공개 버킷에 올라가고 로그인한 사람에게만
    # `GET /api/spotter/db`로 나간다. 서버가 gzip하고 ETag를 붙이므로 여기서
    # 캐시 버전을 index.html에 박던 일도 없어졌다 — 내용이 곧 ETag다.
    #
    # `build/`에 남는 것은 **올릴 것의 원본이지 배포물이 아니다.**
    # 배포되는 것은 `web/`의 index.html·app.js·auth.js·config.js 넷뿐이다.
    os.makedirs(BUILD, exist_ok=True)
    db_path = os.path.join(BUILD, "quiz_db.json")
    with open(db_path, "w", encoding="utf-8") as fh:
        json.dump({"meta": meta, "questions": questions}, fh,
                  ensure_ascii=False, separators=(",", ":"))

    legacy = os.path.join(WEB, "quiz_db.js")
    if os.path.exists(legacy):
        os.remove(legacy)
        print("옛 quiz_db.js 지움 (이제 R2로 올린다)")

    size = os.path.getsize(db_path)
    digest = hashlib.sha1(open(db_path, "rb").read()).hexdigest()[:8]
    print(f"문항 {len(questions)}개  (표본 {meta['counts']['specimens']}건 / "
          f"종 {meta['counts']['species']}종)")
    print(f"이미지 {len(used)}장  {total / 1e6:.1f}MB")
    print(f"quiz_db.json  {size / 1e6:.2f}MB  ({digest})")
    # `upload_web.py`는 서버가 과목별 주소로 옮기기 전에 쓰던 것이라
    # `/api/spotter/admin/manifest`에서 404가 난다. 과목을 받는 쪽을 쓴다.
    print("\n올리기:  uv run --python 3.13 --with requests python"
          " scripts/upload_subject.py build --subject parasitology")
    from collections import Counter
    print("\n─ 유형별")
    for k, v in Counter(q["qtype"] for q in questions).most_common():
        print(f"    {k:12s} {v:4d}")


if __name__ == "__main__":
    main()
