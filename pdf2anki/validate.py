"""생성 결과를 기계 검증한다.

hard  — 의미 판단이 필요 없는 명백한 결함. 카드를 빼고 원문과 사유를 남긴다.
soft  — 의미 판단이 필요한 의심. 카드는 남기고 표시만 한다. 판정은 뒤 단계 몫이다.

validator 는 의미적 결론을 대신하지 않는다. 유사 중복·자족성·중요도는 표시만 하고
유지/수정/경고유지/삭제는 disposition 이 정한다.

사용:
    python -m pdf2anki.validate out/lec03/items.raw.json \
        --prep out/lec03/prep.json --jokbo "out/jokbo/L16-18_소아질환의-병태생리-1-3.json"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from jsonschema import Draft202012Validator

from .schema import (CARD_SCHEMA, IMAGE_FORMATS, MAX_Q_CHARS, MAX_RECALL_ITEMS)
from .textutil import char_ngrams, containment, jaccard, norm_key

RE_CLOZE = re.compile(r"\{\{c(\d+)::(.*?)(?:::(.*?))?\}\}")
RE_POINTS_AT_SOURCE = re.compile(
    r"이\s*그림|위\s*그림|아래\s*그림|위\s*표|이\s*표|해당\s*물질|이\s*물질|"
    r"슬라이드에\s*따르면|표에\s*제시된|강의록|본문에\s*따르면|필기(된|에)|"
    r"강조된|도장이|위\s*내용")
OX_TRUE = {"o", "○", "맞다", "true", "예", "참"}
OX_FALSE = {"x", "×", "틀리다", "false", "아니오", "거짓"}
SPLIT_ITEMS = re.compile(r"[,;·/\n]|\s→\s|\s-\s")
RE_BULLET_LINE = re.compile(r"^\s*[-•*]\s+\S", re.M)

# 질문 길이 상한(`MAX_Q_CHARS`)은 `schema.py` 에 있다 — 계약에 실려야 모델이 안다.
# 여기서 이름을 다시 내보내는 것은 `prequiz/schema.py` 가 그렇게 가져다 쓰기 때문이다.


def count_items(a: str) -> int:
    """답의 회수 항목 수.

    불릿으로 정리된 답은 **줄이 항목**이다. 줄 안의 쉼표까지 세면
    `- 동맥: 관상동맥, 대뇌동맥, 대퇴동맥` 세 줄짜리 답이 항목 일곱으로 잡혀
    멀쩡한 카드에 깃발이 선다.
    """
    bullets = RE_BULLET_LINE.findall(a)
    if len(bullets) >= 2:
        return len(bullets)
    return len([x for x in SPLIT_ITEMS.split(a) if x.strip()])

# 같은 슬라이드끼리는 회수 방향이 겹칠 가능성이 높아 문턱을 낮춘다.
SIMILAR_SAME_SLIDE = 0.35
SIMILAR_CROSS_SLIDE = 0.60
LEAK_THRESHOLD = 0.80


def _fail(card, code, detail=""):
    return {"code": code, "detail": detail, "card": card}


def _figure_index(prep: dict) -> tuple[dict, dict]:
    """figure_id -> slide, occlusion_id -> (slide, figure_id, label)"""
    figs, occs = {}, {}
    for s in prep["pages"]:
        for f in s["lecture_figures"]:
            figs[f["id"]] = s["slide"]
        for o in s["occlusion_candidates"]:
            occs[o["id"]] = (s["slide"], o["figure_id"], o.get("label"))
    return figs, occs


def _ref_status(ref: dict, keys: set, years: set) -> str:
    """기출 ref 를 조각과 맞춰 본다. `ok` / `missing` / `outside`.

    갈래가 둘인 이유는 **모르는 것과 틀린 것이 다르기 때문**이다.

        missing   조각이 그 연도를 들고 있는데 그 번호가 없다 → 지어낸 것에 가깝다
        outside   조각이 그 연도를 아예 안 들고 있다 → 조각으로는 판정할 수 없다

    `outside` 가 실제로 나온다. 필기자가 강의록 뒤에 조각보다 오래된 기출을 직접
    붙여 놓는 일이 있고(260821_02 Slide 41: *"2019년 이전 족보 문제들은 … 정리를
    하지 않고 추가로 첨부하였습니다"*), 모델은 그것을 읽고 카드를 만든다.

    이 갈래를 두기 전까지 `jokbo_ref_not_found` 는 하드 삭제 하나뿐이었다. 28편
    실측에서 삭제된 기출 카드 17장이 **전부** `outside` 였다 — 인용 연도는 2017·
    2018·2019 인데 조각은 2020·21·22·23·25 만 든다. 그중에는 교수 이의제기 답변을
    근거로 삼은 카드도 있었다. 조각이 못 보는 자리를 근거 없음으로 셌던 것이다.
    """
    if not keys:
        return "ok"                              # 조각이 없으면 맞출 것도 없다
    if (ref["year"], ref["no"]) in keys:
        return "ok"
    return "missing" if ref["year"] in years else "outside"


def validate(raw: dict, prep: dict, jokbo: dict | None,
             annotation_evidence: bool = False) -> tuple[list, dict]:
    """annotation_evidence: 올해 필기를 질문·정답의 근거로 인정한다.

    기본은 불가다 — 필기에는 교수 잡담과 필기자 사담이 섞여 있고, 강의록이 정본이기
    때문이다. **담당 교수가 바뀐 강의는 사정이 다르다.** 강의록이 작년 것 그대로여도
    올해 교수가 말한 의학적 내용은 필기에만 남는다. 그때는 필기가 유일한 기록이므로
    근거로 인정한다(사담·잡담은 여전히 아니다 — 그 판단은 모델이 한다).
    """
    cards = list(raw.get("cards", []))
    plan = raw.get("learning_plan") or {}
    n_slides = prep["slides"]
    figs, occs = _figure_index(prep)
    jokbo_qs = (jokbo or {}).get("questions", [])
    jokbo_keys = {(q["year"], q["no"]) for q in jokbo_qs}
    jokbo_years = {q["year"] for q in jokbo_qs}

    schema_check = Draft202012Validator(CARD_SCHEMA)
    kept, dropped, flags = [], [], defaultdict(list)
    seen_exact: dict[str, int] = {}
    autofix = Counter()

    for idx, c in enumerate(cards):
        errs = sorted(schema_check.iter_errors(c), key=lambda e: e.path)
        if errs:
            dropped.append(_fail(c, "schema", "; ".join(
                f"{'/'.join(str(p) for p in e.path) or '(root)'}: {e.message}" for e in errs[:3])))
            continue

        q, a = c["q"].strip(), c["a"].strip()
        fmt, src = c["card_format"], c["source_type"]

        if not q or not a:
            dropped.append(_fail(c, "empty_q_or_a"))
            continue
        if norm_key(q) == norm_key(a):
            dropped.append(_fail(c, "q_equals_a"))
            continue

        # 범위
        if src == "lecture":
            if c.get("slide_no") is None:
                dropped.append(_fail(c, "missing_slide_no"))
                continue
            if not 1 <= c["slide_no"] <= n_slides:
                dropped.append(_fail(c, "slide_out_of_range",
                                     f"slide_no={c['slide_no']} / 1..{n_slides}"))
                continue
            # `exam_hit` 의 근거 ref 는 오래 검사 밖에 있었다. 28편 실측에서 강의록
            # 카드에 달린 ref 649개 중 52개가 조각에 없었고 아무도 몰랐다. 이 카드의
            # 근거는 슬라이드이지 기출이 아니므로 **떨어뜨리지 않는다** — 표시만 한다.
            ref = c.get("jokbo_ref")
            if ref:
                st = _ref_status(ref, jokbo_keys, jokbo_years)
                if st != "ok":
                    flags[idx].append("jokbo_ref_outside_slice" if st == "outside"
                                      else "jokbo_ref_not_found")
            # 외부 의학지식은 기출 파트에만 열려 있다. 강의록은 정본이라
            # 밖에서 메울 것이 없고, 메우기 시작하면 근거 위계가 무너진다.
            if c.get("evidence_type") == "medical_knowledge":
                dropped.append(_fail(c, "medical_knowledge_on_lecture"))
                continue
        else:
            ref = c.get("jokbo_ref")
            if not ref:
                dropped.append(_fail(c, "missing_jokbo_ref"))
                continue
            st = _ref_status(ref, jokbo_keys, jokbo_years)
            if st == "missing":
                dropped.append(_fail(c, "jokbo_ref_not_found", f"{ref['year']}-{ref['no']}"))
                continue
            if st == "outside":
                # 원문을 붙일 수 없다는 것은 카드 뒷면에 뜬다(`FLAG_LABEL`).
                flags[idx].append("jokbo_ref_outside_slice")

        # 형식별 계약
        clozes = RE_CLOZE.findall(q)
        if fmt == "cloze" and not clozes:
            dropped.append(_fail(c, "cloze_syntax_broken"))
            continue
        if fmt != "cloze" and clozes:
            dropped.append(_fail(c, "cloze_in_non_cloze"))
            continue

        if fmt == "ox":
            key = a.lower().strip(". ")
            if key in OX_TRUE:
                c["a"] = "O"
            elif key in OX_FALSE:
                c["a"] = "X"
            else:
                dropped.append(_fail(c, "ox_answer_not_binary", a))
                continue

        media = c.get("media")
        if fmt in IMAGE_FORMATS:
            if not media:
                dropped.append(_fail(c, "image_card_without_media"))
                continue
            fid = media["figure_id"]
            if fid not in figs:
                dropped.append(_fail(c, "figure_id_not_found", fid))
                continue
            if c.get("slide_no") is not None and figs[fid] != c["slide_no"]:
                dropped.append(_fail(c, "figure_slide_mismatch",
                                     f"{fid} 는 Slide {figs[fid]}, 카드는 {c['slide_no']}"))
                continue
            if fmt == "image_occlusion":
                ids = media.get("occlusion_ids") or []
                if not ids:
                    dropped.append(_fail(c, "occlusion_without_ids"))
                    continue
                bad = [i for i in ids if i not in occs]
                if bad:
                    dropped.append(_fail(c, "occlusion_id_not_found", ", ".join(bad)))
                    continue
                wrong = [i for i in ids if occs[i][1] != fid]
                if wrong:
                    dropped.append(_fail(c, "occlusion_figure_mismatch", ", ".join(wrong)))
                    continue
        elif media:
            c["media"] = None                      # 기계적 교정
            autofix["media_on_text_card"] += 1
            flags[idx].append("media_on_text_card")

        if src == "jokbo" and c.get("exam_hit"):
            c["exam_hit"] = False                  # 기출 카드에 중복 부여 금지
            autofix["exam_hit_on_jokbo"] += 1
            flags[idx].append("exam_hit_on_jokbo")

        key = norm_key(q) + "␟" + norm_key(c["a"])
        if key in seen_exact:
            dropped.append(_fail(c, "exact_duplicate", f"#{seen_exact[key]} 와 동일"))
            continue
        seen_exact[key] = idx

        c["_idx"] = idx
        kept.append(c)

    # ── soft flag ────────────────────────────────────────────────────
    for c in kept:
        i = c["_idx"]
        q, a, fmt = c["q"], c["a"], c["card_format"]

        if fmt not in IMAGE_FORMATS and RE_POINTS_AT_SOURCE.search(q):
            flags[i].append("points_at_source")
        if not (c.get("explanation") or "").strip():
            flags[i].append("missing_explanation")
        if (c.get("evidence_type") == "annotation" and not c.get("exam_hit")
                and not annotation_evidence):
            flags[i].append("annotation_evidence_without_exam_hit")
        # 고친 것을 적어 두지 않으면 사람이 그것을 볼 길이 없다. 카드는 살린다 —
        # 무엇이 고쳐졌는지는 기계가 모르고, 판정은 뒷면을 보는 사람 몫이다.
        if (c.get("evidence_type") == "medical_knowledge"
                and not (c.get("review_note") or "").strip()):
            flags[i].append("corrected_without_note")

        # cloze 는 정답이 질문 안에 있는 것이 정의이므로 노출 검사 대상이 아니다
        if fmt != "cloze" and containment(char_ngrams(a), char_ngrams(q)) >= LEAK_THRESHOLD:
            flags[i].append("answer_leaked_in_question")

        if len(RE_CLOZE.findall(q)) > MAX_RECALL_ITEMS:
            flags[i].append("too_many_clozes")
        # 불릿으로 정리된 답은 card_type 이 무엇이든 사실상 목록이다. 함께 센다.
        if c["card_type"] in ("list", "sequence") or len(RE_BULLET_LINE.findall(a)) >= 2:
            if count_items(a) > MAX_RECALL_ITEMS:
                flags[i].append("too_many_items")

        # 긴 질문은 대개 축을 여럿 문 결과다. 카드를 떨어뜨리지는 않는다 —
        # 나누는 판단은 모델이 해야 하고, 여기서는 사람이 볼 수 있게 표시만 한다.
        if fmt != "cloze" and len(q) > MAX_Q_CHARS:
            flags[i].append("question_too_long")
        # 빈칸 카드는 한동안 이 검사에서 면제였다. 문장이 길어야 여러 항목을 나란히
        # 물을 수 있다는 이유였는데, **면제가 정의문 통째로 싣기를 열어 줬다.**
        #
        #   Inflammation is a complex reaction to {{c1::injurious agents}} such as
        #   microbes and damaged, usually {{c2::necrotic}}, cells that consists of
        #   … (249자, 빈칸 5개, 플래그 0개)
        #
        # 관리자 판정 — *"저 문장이 그렇게 중요한지 모르겠어. 길이도 긴데."* 29편
        # 2,396장 실측에서 빈칸 카드 75장 중 35장이 이 상한을 넘고 있었다.
        # 개수는 안 건드린다. 같은 관리자가 c2~c5 는 *"이런거면 몰라도"* 라고 했다 —
        # 걸리는 것은 빈칸이 몇 개냐가 아니라 문장을 통째로 옮겼느냐다.
        if fmt == "cloze" and len(q) > MAX_Q_CHARS:
            flags[i].append("cloze_sentence_too_long")
        if fmt == "ox" and q.rstrip().endswith("?"):
            flags[i].append("ox_is_question_not_statement")

        if fmt == "image_occlusion":
            for oid in c["media"].get("occlusion_ids", []):
                label = occs[oid][2]
                if label and norm_key(label) and norm_key(label) in norm_key(q):
                    flags[i].append("occlusion_answer_leaked_in_question")
                    break

    # 유사 중복 (같은 회수 방향인지는 disposition 이 판단한다)
    sigs = [(c["_idx"], c.get("slide_no"), char_ngrams(c["q"] + " " + c["a"]),
             (c.get("media") or {}).get("figure_id"),
             c["card_format"], c["a"]) for c in kept]
    similar = []
    for x in range(len(sigs)):
        for y in range(x + 1, len(sigs)):
            # 붙는 그림이 다르면 문구가 같아도 별개 자극이다.
            # ("이 조직 소견의 발생 단계는?" 이 18주·23주·신생아에 각각 붙는 경우)
            fx, fy = sigs[x][3], sigs[y][3]
            if fx and fy and fx != fy:
                continue
            # 답이 갈리는 O/X 짝은 의도된 것이다. 함의의 두 방향을 각각 묻는 카드로,
            # "A는 B다(O)" / "B는 A다(X)" 처럼 문구가 겹칠수록 오히려 제 역할을 한다.
            if sigs[x][4] == sigs[y][4] == "ox" and sigs[x][5] != sigs[y][5]:
                continue
            same_slide = sigs[x][1] is not None and sigs[x][1] == sigs[y][1]
            j = jaccard(sigs[x][2], sigs[y][2])
            if j >= (SIMILAR_SAME_SLIDE if same_slide else SIMILAR_CROSS_SLIDE):
                similar.append({"a": sigs[x][0], "b": sigs[y][0], "jaccard": round(j, 2),
                                "same_slide": same_slide})
                flags[sigs[x][0]].append("similar_duplicate")
                flags[sigs[y][0]].append("similar_duplicate")

    # ── 커버리지 ─────────────────────────────────────────────────────
    carded = {c["slide_no"] for c in kept if c.get("slide_no")}
    declared = {s for r in plan.get("rejected_candidates", []) for s in r.get("slides", [])}
    # 족보 부록은 "안 낸 것" 이 아니라 "기출 파트 소관" 이다. 따로 세어 둔다 —
    # 기출 계획이 재료로 쓸 구간이고, 제외 기록에 섞어 두면 그 자리를 잃는다.
    appendix = sorted({s for r in plan.get("rejected_candidates", [])
                       if r.get("reason") == "jokbo_appendix"
                       for s in r.get("slides", [])})
    planned = {s for o in plan.get("objectives", []) for s in o.get("slides", [])}
    untouched = sorted(set(range(1, n_slides + 1)) - carded - declared - planned)

    obj_hit, obj_miss = [], []
    for o in plan.get("objectives", []):
        tok = char_ngrams(o["objective"] + " " + " ".join(o.get("retrieval_targets", [])))
        hit = any(jaccard(tok, char_ngrams(c["q"] + " " + c["a"])) >= 0.2
                  or c.get("slide_no") in set(o.get("slides", [])) for c in kept)
        (obj_hit if hit else obj_miss).append(o["objective"])

    # 기출 목표는 슬라이드로 못 맞춘다. 인용 문항이 겹치는지로 본다.
    jobj_miss = []
    for o in plan.get("jokbo_objectives", []):
        refs = set(o.get("jokbo_refs") or [])
        tok = char_ngrams(o["objective"] + " " + " ".join(o.get("retrieval_targets", [])))
        hit = any(jaccard(tok, char_ngrams(c["q"] + " " + c["a"])) >= 0.2
                  or (c.get("jokbo_ref")
                      and f"{c['jokbo_ref']['year']}-{c['jokbo_ref']['no']}" in refs)
                  for c in kept)
        if not hit:
            jobj_miss.append(o["objective"])

    for c in kept:
        c["review_flags"] = sorted(set(flags[c.pop("_idx")]))

    suspects = {
        "n_input": len(cards), "n_kept": len(kept), "n_dropped": len(dropped),
        "dropped": dropped,
        "autofixed": dict(autofix),
        "flag_counts": dict(Counter(f for c in kept for f in c["review_flags"])),
        "similar_pairs": similar,
        "coverage": {
            "slides_total": n_slides,
            "slides_with_cards": len(carded),
            "untouched_undeclared": untouched,
            "objectives_total": len(plan.get("objectives", [])),
            "objectives_without_card": obj_miss,
            "jokbo_objectives_total": len(plan.get("jokbo_objectives", [])),
            "jokbo_objectives_without_card": jobj_miss,
            "rejected_candidates": len(plan.get("rejected_candidates", [])),
            "jokbo_appendix_slides": appendix,
        },
        "format_mix": dict(Counter(c["card_format"] for c in kept)),
        "source_mix": dict(Counter(c["source_type"] for c in kept)),
        "importance_mix": dict(Counter(c["importance"] for c in kept)),
        # O/X 정답 쏠림. 오답 선지만 캐면 답이 죄 X 가 되고, 그러면 푸는 사람이
        # 문항 대신 「O/X 면 X」를 배운다. 세어서 보이기만 한다 — 판정은 사람 몫이다.
        "ox_mix": {st: dict(Counter(c["a"].strip() for c in kept
                                    if c["card_format"] == "ox" and c["source_type"] == st))
                   for st in sorted({c["source_type"] for c in kept
                                     if c["card_format"] == "ox"})},
        "exam_hit": sum(1 for c in kept if c.get("exam_hit")),
    }
    return kept, suspects


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="생성 결과를 기계 검증한다")
    ap.add_argument("raw")
    ap.add_argument("--prep", required=True)
    ap.add_argument("--jokbo")
    ap.add_argument("--plan", help="승인된 학습계획. 커버리지 계산에 쓴다")
    ap.add_argument("-o", "--out")
    ap.add_argument("--annotation-evidence", action="store_true",
                    help="올해 필기를 질문·정답의 근거로 인정한다 (담당 교수가 바뀐 강의)")
    args = ap.parse_args(argv)

    raw = json.loads(Path(args.raw).read_text(encoding="utf-8"))
    prep = json.loads(Path(args.prep).read_text(encoding="utf-8"))
    jokbo = json.loads(Path(args.jokbo).read_text(encoding="utf-8")) if args.jokbo else None
    plan_path = Path(args.plan) if args.plan else Path(args.raw).parent / "plan.approved.json"
    if "learning_plan" not in raw and plan_path.exists():
        pl = json.loads(plan_path.read_text(encoding="utf-8"))
        raw["learning_plan"] = pl.get("learning_plan", pl)

    kept, suspects = validate(raw, prep, jokbo, args.annotation_evidence)
    outdir = Path(args.out or Path(args.raw).parent)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "items.checked.json").write_text(
        json.dumps({"cards": kept}, ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "suspects.json").write_text(
        json.dumps(suspects, ensure_ascii=False, indent=2), encoding="utf-8")

    s = suspects
    print(f"입력 {s['n_input']}장 → 통과 {s['n_kept']}장 · hard 제거 {s['n_dropped']}장")
    if s["dropped"]:
        print("\nhard 제거:")
        for d in s["dropped"]:
            print(f"   {d['code']:<28}{d['detail'][:60]}")
            print(f"      q: {d['card'].get('q','')[:70]!r}")
    if s["autofixed"]:
        print(f"\n기계 교정: {s['autofixed']}")
    if s["flag_counts"]:
        print("\nsoft flag:")
        for k, v in sorted(s["flag_counts"].items(), key=lambda x: -x[1]):
            print(f"   {k:<40}{v:>4}장")
    if s["similar_pairs"]:
        print(f"\n유사 중복 후보 {len(s['similar_pairs'])}쌍: "
              f"{[(p['a'], p['b'], p['jaccard']) for p in s['similar_pairs'][:8]]}")
    c = s["coverage"]
    print(f"\n형식 {s['format_mix']} · 출처 {s['source_mix']} · 중요도 {s['importance_mix']} "
          f"· exam_hit {s['exam_hit']}장")
    # 여덟 장 밑에서는 쏠림이라 부를 것이 없다. 8 과 3/4 는 12편 실측(O/X 119장 중
    # X 113장)을 보고 잠정으로 세운 값이다 — 편이 쌓이면 실제 분포를 보고 다시 정한다.
    for st, mix in s["ox_mix"].items():
        o, x = mix.get("O", 0), mix.get("X", 0)
        note = "  ← 한쪽이 3/4를 넘는다" if o + x >= 8 and max(o, x) / (o + x) > 0.75 else ""
        print(f"O/X 정답 ({st}): O {o} · X {x}{note}")
    print(f"커버리지: 카드 있는 슬라이드 {c['slides_with_cards']}/{c['slides_total']} · "
          f"학습목표 {c['objectives_total']}개 중 카드 없는 것 {len(c['objectives_without_card'])}개 · "
          f"제외 기록 {c['rejected_candidates']}건")
    if c["untouched_undeclared"]:
        print(f"⚠ 카드도 없고 제외 기록에도 없는 슬라이드: {c['untouched_undeclared']}")
    print(f"\n→ {outdir}/items.checked.json, suspects.json")
    print(f"   다음: python -m pdf2anki.reproduce check {outdir.as_posix()}")
    print("      앞면만 보고 다시 풀어 재현 가능성을 잰다. build 는 그 결과를 입력으로 받는다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
