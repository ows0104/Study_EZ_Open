"""같은 강의의 두 필기본을 한 덱으로 합친다.

`[260820_01]` 과 `[260820_02]` 처럼 제목이 같은 두 파일이 아카이브에 있을 때 쓴다.
교시가 다르면 내용이 갈리므로 두 덱을 따로 두면 회독이 두 번 갈리고,
같은 대목을 다룬 카드는 두 장이 된다.

**중복 제거의 절반은 guid 가 이미 한다.** `build.py` 의 guid 씨앗은
`(강의 ID, 정규화한 질문)` 이라, 합친 덱을 **강의 ID 하나**로 구우면 질문이 같은
카드는 Anki 가 임포트할 때 한 장으로 본다. 이 모듈이 하는 일은 그 위에서
*질문이 다르지만 같은 것을 묻는* 카드를 골라내는 것이다.

**두 강의를 이어 붙여 한 강의로 만든다.** Media 를 카드마다 갈라 태우는 대신
annotated/clean PDF 를 물리적으로 잇고 B 의 쪽번호·그림 ID 를 A 의 쪽수만큼 민다.
그러면 `build.build()` 를 손대지 않아도 접촉 시트·기출 원문·오클루전이 그대로 산다.

    python -m quizgen.merge report out/p260820_01 out/p260820_02
    python -m quizgen.merge make   out/p260820_01 out/p260820_02 --id p260820_0102

`report` 는 아무것도 쓰지 않는다. 겹침이 실제로 몇 장인지 재서 임계값을 정하는 데 쓴다.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import unicodedata
from pathlib import Path

import fitz

from .textutil import char_ngrams, containment, jaccard, norm_key

# 판정은 두 신호로 한다 — 질문 포함도와 **답 포함도**.
#
# 처음에는 질문 2-gram 자카드 하나로 재려 했는데 실측이 그걸 반증했다.
# 순환장애 1×2 에서 눈으로 확인한 진짜 중복 6쌍의 질문 자카드는 0.41~0.88 로 흩어져
# 임계값을 어디에 두어도 절반을 놓쳤다. 한쪽 질문이 길면 자카드가 무너지기 때문이다
# (핸드오프: "자카드만으로는 길이 차이에 진다. 포함도를 양방향으로 함께 본다").
#
# 반면 **답 포함도가 깨끗하게 갈랐다** — 진짜 중복 6쌍은 0.86~1.00, 가짜 2쌍은 0.00.
# 가짜 두 쌍은 O/X 카드와 열거 카드였다. 같은 용어를 쓰지만 묻는 것이 다르고,
# 그 차이가 질문이 아니라 답에 나타난다.
#
# 답만으로 판정하지 않는 이유는 답이 짧을 때다 — 서로 다른 질문 둘이 똑같이 "혈전"을
# 답으로 가질 수 있다. 질문 포함도를 함께 걸어 그것을 막는다.
#
# 실측 표본이 8쌍뿐이다. 실제 합칠 두 강의에서 다시 재고 조정할 것.
Q_MIN = 0.60          # 질문 양방향 포함도
A_MIN = 0.80          # 답 양방향 포함도

VERDICT_RANK = {"same": 0, "partial": 1, "different": 2}
IMPORTANCE_RANK = {"core": 0, "detail": 1}


# ── 읽기 ──────────────────────────────────────────────────────────
def load(d: Path) -> tuple[dict, list, dict]:
    prep = json.loads((d / "prep.json").read_text(encoding="utf-8"))
    src = d / "items.reproduced.json"
    if not src.exists():
        src = d / "items.checked.json"
    if not src.exists():
        raise FileNotFoundError(f"{d} 에 items.reproduced.json 도 items.checked.json 도 없다")
    cards = json.loads(src.read_text(encoding="utf-8"))["cards"]
    cfg = {}
    p = d / "run.config.json"
    if p.exists():
        cfg = json.loads(p.read_text(encoding="utf-8"))
    return prep, cards, cfg


# ── 유사도 ────────────────────────────────────────────────────────
def _both(x: set, y: set) -> float:
    """양방향 포함도 중 큰 쪽. 한쪽이 더 길게 물어도 같은 것을 묻는 경우를 잡는다."""
    return max(containment(x, y), containment(y, x))


def is_dup(p: dict, q_min: float = Q_MIN, a_min: float = A_MIN) -> bool:
    return p["exact"] or (p["qc"] >= q_min and p["ac"] >= a_min)


def pairs(ca: list, cb: list, floor: float = 0.40) -> list[dict]:
    """두 강의를 가로지르는 쌍만 본다. 한 강의 안의 중복은 이 모듈의 일이 아니다.

    쌍마다 네 수를 낸다 — `qc`·`ac` 는 양방향 포함도(판정에 쓴다),
    `sq`·`sa` 는 자카드(사람이 곁들여 볼 참고값).
    """
    ga = [(c, char_ngrams(c["q"]), char_ngrams(c["a"])) for c in ca]
    gb = [(c, char_ngrams(c["q"]), char_ngrams(c["a"])) for c in cb]
    out = []
    for a, qa, aa in ga:
        for b, qb, ab in gb:
            qc = _both(qa, qb)
            exact = norm_key(a["q"]) == norm_key(b["q"])
            if qc < floor and not exact:
                continue
            out.append({"a": a, "b": b, "exact": exact,
                        "qc": qc, "ac": _both(aa, ab),
                        "sq": jaccard(qa, qb), "sa": jaccard(aa, ab)})
    out.sort(key=lambda p: (-p["qc"], -p["ac"]))
    return out


def better(a: dict, b: dict) -> dict:
    """겹친 두 장 중 남길 쪽. 재현 검사를 통과한 것 · 기출에 걸린 것 · 중요한 것 순."""
    def key(c):
        r = c.get("reproduce") or {}
        return (VERDICT_RANK.get(r.get("verdict"), 3),
                0 if c.get("jokbo_ref") else 1,
                0 if c.get("exam_hit") else 1,
                IMPORTANCE_RANK.get(c.get("importance"), 2),
                -len(c.get("explanation") or ""))
    return a if key(a) <= key(b) else b


# ── 이어 붙이기 ───────────────────────────────────────────────────
def _shift_id(s: str, off: int) -> str:
    """`fig_p09_01` · `occ_p09_05` 의 쪽번호를 민다."""
    return re.sub(r"_p(\d+)_", lambda m: f"_p{int(m.group(1)) + off:02d}_", s)


def shift_prep(prep: dict, off: int) -> dict:
    """B 의 prep 을 A 의 쪽수만큼 민다."""
    p = json.loads(json.dumps(prep))          # 원본을 건드리지 않는다
    for pg in p["pages"]:
        pg["slide"] += off
        for f in pg["lecture_figures"]:
            f["id"] = _shift_id(f["id"], off)
        for o in pg["occlusion_candidates"]:
            o["id"] = _shift_id(o["id"], off)
            o["figure_id"] = _shift_id(o["figure_id"], off)
    for k in ("badge_failed_slides", "slides_with_covered_lecture_content"):
        p[k] = [n + off for n in p.get(k, [])]
    return p


def shift_cards(cards: list, off: int) -> list:
    c2 = json.loads(json.dumps(cards))
    for c in c2:
        if c.get("slide_no"):
            c["slide_no"] += off
        m = c.get("media") or {}
        if m.get("figure_id"):
            m["figure_id"] = _shift_id(m["figure_id"], off)
        if m.get("occlusion_ids"):
            m["occlusion_ids"] = [_shift_id(i, off) for i in m["occlusion_ids"]]
    return c2


def concat_pdf(a: Path, b: Path, dest: Path) -> int:
    doc = fitz.open(a)
    with fitz.open(b) as second:
        doc.insert_pdf(second)
    n = doc.page_count
    doc.save(dest)
    doc.close()
    return n


# ── 리포트 ────────────────────────────────────────────────────────
def report(da: Path, db: Path, q_min: float, a_min: float, top: int = 60) -> str:
    pa, ca, _ = load(da)
    pb, cb, _ = load(db)
    ps = pairs(ca, cb)
    hit = [p for p in ps if is_dup(p, q_min, a_min)]
    exact = [p for p in ps if p["exact"]]
    L = []
    L.append(f"# 겹침 실측 — {da.name} × {db.name}\n")
    L.append(f"- {da.name}: 카드 {len(ca)}장 (슬라이드 {pa['slides']})")
    L.append(f"- {db.name}: 카드 {len(cb)}장 (슬라이드 {pb['slides']})")
    L.append(f"- 질문이 완전히 같은 쌍: **{len(exact)}** (guid 가 알아서 합친다)")
    L.append(f"- 중복으로 판정된 쌍 (qc≥{q_min} 이고 ac≥{a_min}): **{len(hit)}**")
    L.append(f"- 합치면 {len(ca) + len(cb)}장 → 약 **{len(ca) + len(cb) - len(hit)}장**\n")

    # 기출직결 카드에 중복이 몰리는지 — 두 강의가 같은 족보 조각을 덮으므로 그럴 것이다
    ex = [p for p in hit if p["a"].get("exam_hit") or p["b"].get("exam_hit")]
    na = sum(1 for c in ca if c.get("exam_hit"))
    nb = sum(1 for c in cb if c.get("exam_hit"))
    L.append(f"- 겹친 {len(hit)}쌍 중 **{len(ex)}쌍이 기출직결** "
             f"(기출직결 카드는 {da.name} {na}장 · {db.name} {nb}장)\n")

    L.append("## 답 포함도가 실제로 가르는가 (qc≥0.40 인 쌍의 ac 분포)\n")
    L.append("판정을 두 신호로 하는 근거다. 진짜 중복은 ac 가 높고 가짜는 0 에 몰려야 한다.\n")
    for lo, hi, name in [(0.80, 1.01, "ac 0.80~"), (0.50, 0.80, "ac 0.50~0.80"),
                         (0.20, 0.50, "ac 0.20~0.50"), (0.0, 0.20, "ac 0.00~0.20")]:
        n = sum(1 for p in ps if lo <= p["ac"] < hi)
        L.append(f"  {name:14} {n:4}쌍  {'#' * min(n, 60)}")
    L.append("")

    L.append("## 질문 포함도 분포 (0.40 이상인 쌍만)\n")
    prev = 1.01
    for lo in (0.95, 0.85, 0.75, 0.60, 0.40):
        n = sum(1 for p in ps if lo <= p["qc"] < prev)
        L.append(f"  qc {lo:.2f}~{prev if prev <= 1 else 1.0:.2f}  {n:4}쌍  "
                 f"{'#' * min(n, 60)}")
        prev = lo
    L.append("")

    L.append(f"## 쌍 목록 (질문 포함도 높은 순, 상위 {top})\n")
    L.append("`qc`·`ac` 양방향 포함도 — **판정은 이 둘로 한다**. "
             "`sq`·`sa` 는 자카드(참고값).\n")
    for p in ps[:top]:
        mark = "합침" if is_dup(p, q_min, a_min) else " ·  "
        L.append(f"- [{mark}] qc={p['qc']:.2f} ac={p['ac']:.2f} "
                 f"(sq={p['sq']:.2f} sa={p['sa']:.2f})"
                 f"{' **완전동일**' if p['exact'] else ''}")
        L.append(f"    A. {p['a']['q']}")
        L.append(f"       → {p['a']['a'][:90]}")
        L.append(f"    B. {p['b']['q']}")
        L.append(f"       → {p['b']['a'][:90]}")
    if len(ps) > top:
        L.append(f"\n… qc 0.40 이상인 쌍 {len(ps)}개 중 {top}개만 보였다.")
    return "\n".join(L)


# ── 합치기 ────────────────────────────────────────────────────────
def make(da: Path, db: Path, out: Path, lecture_id: str, deck: str,
         q_min: float, a_min: float) -> dict:
    pa, ca, cfa = load(da)
    pb, cb, cfb = load(db)
    off = pa["slides"]

    out.mkdir(parents=True, exist_ok=True)
    n_ann = concat_pdf(da / pa["annotated_pdf"], db / pb["annotated_pdf"],
                       out / "annotated.pdf")
    n_cln = concat_pdf(da / pa["clean_pdf"], db / pb["clean_pdf"], out / "clean.pdf")
    if n_ann != n_cln:
        raise RuntimeError(f"이어 붙인 쪽수가 다르다: annotated {n_ann} · clean {n_cln}")

    pbs = shift_prep(pb, off)
    prep = json.loads(json.dumps(pa))
    prep["source"] = f"{pa['source']}  +  {pb['source']}"
    prep["slides"] = n_ann
    prep["annotated_pdf"], prep["clean_pdf"] = "annotated.pdf", "clean.pdf"
    prep["pages"] = pa["pages"] + pbs["pages"]
    prep["merged_from"] = [{"dir": da.name, "slides": pa["slides"], "offset": 0},
                           {"dir": db.name, "slides": pb["slides"], "offset": off}]
    for k in ("badge_failed_slides", "slides_with_covered_lecture_content"):
        prep[k] = list(pa.get(k, [])) + pbs.get(k, [])
    # 팔레트는 편마다 따로 잰 것이라 한쪽만 남기면 뒤쪽 색이 사이드카에서 사라진다.
    # 쪽별 `lecture_emphasis` 는 이미 각자 계산돼 있으니 설명만 합치면 된다.
    pa_pal, pb_pal = pa.get("lecture_palette") or {}, pb.get("lecture_palette") or {}
    if pa_pal or pb_pal:
        cols = dict(pa_pal.get("colors") or {})
        for c, v in (pb_pal.get("colors") or {}).items():
            if c in cols:
                cols[c] = {**cols[c], "chars": cols[c]["chars"] + v["chars"],
                           "pages": cols[c]["pages"] + v["pages"]}
            else:
                cols[c] = v
        body_a, body_b = pa_pal.get("body_color"), pb_pal.get("body_color")
        prep["lecture_palette"] = {
            "body_color": body_a if body_a == body_b else None,
            "merged_body_colors": None if body_a == body_b else [body_a, body_b],
            "colors": dict(sorted(cols.items(), key=lambda kv: -kv[1]["chars"])),
            "template_slots": sorted(set((pa_pal.get("template_slots") or [])
                                         + (pb_pal.get("template_slots") or []))),
        }
    prep.setdefault("annotation_years", {})
    for y, n in (pb.get("annotation_years") or {}).items():
        prep["annotation_years"][y] = prep["annotation_years"].get(y, 0) + n
    (out / "prep.json").write_text(json.dumps(prep, ensure_ascii=False, indent=1),
                                   encoding="utf-8")

    # 중복 판정은 쪽번호를 미는 것과 무관하므로 원본 질문으로 한다
    ps = pairs(ca, cb)
    drop_ids, log = set(), []
    for p in ps:
        if not is_dup(p, q_min, a_min):
            continue
        if f"{da.name}:{p['a']['id']}" in drop_ids or f"{db.name}:{p['b']['id']}" in drop_ids:
            continue                      # 이미 한쪽이 빠진 쌍은 건너뛴다
        keep = better(p["a"], p["b"])
        gone = p["b"] if keep is p["a"] else p["a"]
        tag = f"{db.name}:{gone['id']}" if gone is p["b"] else f"{da.name}:{gone['id']}"
        drop_ids.add(tag)
        log.append({"qc": p["qc"], "ac": p["ac"], "exact": p["exact"],
                    "kept": keep["q"], "dropped": gone["q"], "tag": tag})

    cbs = shift_cards(cb, off)
    merged = []
    for c in ca:
        if f"{da.name}:{c['id']}" not in drop_ids:
            merged.append(dict(c, _src=da.name))
    for c in cbs:
        if f"{db.name}:{c['id']}" not in drop_ids:
            merged.append(dict(c, _src=db.name))
    merged.sort(key=lambda c: (c.get("slide_no") or 0))
    for i, c in enumerate(merged, 1):
        c["id"] = f"c{i:03d}"
    (out / "items.merged.json").write_text(
        json.dumps({"cards": merged}, ensure_ascii=False, indent=1), encoding="utf-8")

    R = [f"# 합침 — {da.name} + {db.name}\n",
         f"- 원본 {len(ca)} + {len(cb)} = {len(ca) + len(cb)}장",
         f"- 중복으로 뺀 것 **{len(drop_ids)}장** (qc≥{q_min} 이고 ac≥{a_min})",
         f"- 남은 것 **{len(merged)}장**",
         f"- 슬라이드 {pa['slides']} + {pb['slides']} = {n_ann} "
         f"(B 의 쪽번호·그림 ID 를 +{off} 밀었다)\n",
         "## 뺀 카드 — 눈으로 훑을 것\n"]
    for e in sorted(log, key=lambda x: -x["qc"]):
        R.append(f"- qc={e['qc']:.2f} ac={e['ac']:.2f}"
                 f"{' **완전동일**' if e['exact'] else ''}  ({e['tag']})")
        R.append(f"    남김: {e['kept']}")
        R.append(f"    뺌  : {e['dropped']}")
    (out / "merge.report.md").write_text("\n".join(R), encoding="utf-8")

    (out / "run.config.json").write_text(json.dumps(
        {"deck": deck, "id": lecture_id, "merged_from": [str(da), str(db)],
         "q_min": q_min, "a_min": a_min,
         "strategy": cfa.get("strategy"), "strategy_why": cfa.get("strategy_why")},
        ensure_ascii=False, indent=1), encoding="utf-8")

    return {"n_a": len(ca), "n_b": len(cb), "dropped": len(drop_ids),
            "kept": len(merged), "slides": n_ann, "report": out / "merge.report.md"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="같은 강의의 두 필기본을 한 덱으로 합친다")
    ap.add_argument("cmd", choices=["report", "make"])
    ap.add_argument("dir_a")
    ap.add_argument("dir_b")
    ap.add_argument("-o", "--out", help="합친 작업 폴더. 기본 out/<id>")
    ap.add_argument("--id", help="합친 덱의 강의 ID. guid 씨앗이다")
    ap.add_argument("--deck", help="덱 이름. 기본은 A 의 덱 이름에 +B 를 단다")
    ap.add_argument("--subject", default="과목")
    ap.add_argument("--q-min", type=float, default=Q_MIN,
                    help=f"질문 양방향 포함도 임계값 (기본 {Q_MIN})")
    ap.add_argument("--a-min", type=float, default=A_MIN,
                    help=f"답 양방향 포함도 임계값 (기본 {A_MIN}). 둘 다 넘어야 중복이다")
    ap.add_argument("--top", type=int, default=60, help="report 가 보일 쌍의 수")
    ap.add_argument("--jokbo-dir", default="out/jokbo")
    ap.add_argument("--jokbo", help="족보 조각 json. 생략하면 A 와 같은 규칙으로 찾는다")
    ap.add_argument("--no-build", action="store_true", help="합치기만 하고 덱은 굽지 않는다")
    args = ap.parse_args(argv)

    da, db = Path(args.dir_a), Path(args.dir_b)
    if args.cmd == "report":
        print(report(da, db, args.q_min, args.a_min, args.top))
        return 0

    _, _, cfa = load(da)
    _, _, cfb = load(db)
    tail = (cfb.get("id") or db.name)[-2:]
    lecture_id = args.id or f"{cfa.get('id', da.name)}{tail}"
    lecture_id = unicodedata.normalize("NFC", lecture_id)
    deck = args.deck
    if not deck:
        base = (cfa.get("deck") or f"{args.subject}::{da.name}").split("::")[-1]
        deck = f"{args.subject}::{base} +{tail}"
    out = Path(args.out) if args.out else Path("out") / lecture_id

    res = make(da, db, out, lecture_id, deck, args.q_min, args.a_min)
    print(f"합침: {res['n_a']} + {res['n_b']} → {res['kept']}장 "
          f"(중복 {res['dropped']}장 뺌) · 슬라이드 {res['slides']}")
    print(f"뺀 목록: {res['report']}")

    if args.no_build:
        print("덱은 굽지 않았다 (--no-build).")
        return 0

    from .build import build, find_jokbo_source, verify
    jslice, jpdf = find_jokbo_source(da, Path(args.jokbo_dir), args.jokbo, None)
    jb, _ = find_jokbo_source(db, Path(args.jokbo_dir), None, None)
    if jslice and jb and jslice != jb:
        print(f"⚠ 두 강의가 다른 족보 조각을 쓴다 — A 것을 쓴다\n"
              f"    A {jslice.name}\n    B {jb.name}")
    print(f"기출 원본: {jslice.name if jslice else '조각 없음'}")

    r = build(out, deck, lecture_id, src=out / "items.merged.json",
              jokbo_slice=jslice, jokbo_pdf=jpdf)
    verify(r["apkg"], r["n_notes"], r["n_media"])
    print(f"덱: {deck}   (강의 ID {lecture_id})")
    print(f"노트 {r['n_notes']}장 · 미디어 {r['n_media']}개 → {r['apkg']}")
    if r.get("contact"):
        dest = Path("out/_image_check")
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(r["contact"], dest / Path(r["contact"]).name)
        print(f"이미지 접촉 시트 → {dest / Path(r['contact']).name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
