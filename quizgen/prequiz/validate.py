"""예습 카드의 기계 검증.

복습 쪽(`quizgen.validate`)과 **기계적 검사는 같다** — 스키마, cloze 문법, 그림 id,
중복, 정답 노출. 그 부분은 그대로 가져다 쓴다.

다른 것은 예습에만 있는 계약 넷이다.
  · **개수 상한(`schema.MAX_CARDS`).** 이것이 이 덱의 품질 장치다.
  · **`reason=repeated` 는 교수 유임일 때만.** 바뀌었으면 과거 반복은 이전 교수의 습관이다.
  · **`ox` 는 1/5 이하.** 예습은 알게 하는 것이 목적이라 O/X 는 회수량이 적다.
  · **도전 문제는 `schema.MAX_CHALLENGE` 장 이하**(2026-10-04).

「왜 냈나」(`why_asked`)는 표시만 단다 — 비었는가 · 긴가 · 답이 들었는가 · 기출을
말하는데 문항이 없는가.

그리고 **커버리지의 뜻이 복습과 다르다.** 예습은 슬라이드를 다 훑는 덱이 아니다 —
중요한 것만 가져간다. 그래서 여기서는 슬라이드를 세지 않고, 사람이 승인한 must-know
항목만 센다. 승인한 항목에 카드가 안 갔으면 그것은 빠뜨린 것이지만,
카드가 안 닿은 슬라이드가 있는 것은 이 덱에서 결함이 아니다.

사용:
    python -m quizgen.prequiz.validate out/pre_xxx/items.raw.json \\
        --prep out/pre_xxx/prep.json --jokbo out/jokbo/<조각>.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from jsonschema import Draft202012Validator

from ..textutil import char_ngrams, containment, jaccard, norm_key
from ..validate import (
    LEAK_THRESHOLD,
    MAX_Q_CHARS,
    OX_FALSE,
    OX_TRUE,
    RE_BULLET_LINE,
    RE_CLOZE,
    RE_POINTS_AT_SOURCE,
    SIMILAR_CROSS_SLIDE,
    SIMILAR_SAME_SLIDE,
    _ref_status,
    count_items,
    occlusion_answer_matches,
)
from .schema import (
    CARD_SCHEMA,
    DIFFICULTY_LABELS,
    IMAGE_FORMATS,
    MAX_CARDS,
    MAX_CHALLENGE,
    MAX_RECALL_ITEMS,
    MAX_WHY_TAGS,
    MAX_WHY_CHARS,
    MIN_CARDS,
    MIN_CHALLENGE,
    MIN_CORE,
    MAX_CORE,
    OX_SHARE_MAX,
    WHY_CITES_EXAM,
    WHY_TAGS,
)


# 「필기 강조」보다 앞서는 근거. 하나라도 있으면 `annotation` 배지를 뗀다.
STRONGER_THAN_ANNOTATION = ("exam", "clinical", "later")


def prune_annotation(tags: list) -> list:
    """다른 근거가 있으면 「필기 강조」 배지를 뗀다(2026-10-05 관리자 — 「필기 강조는 다른
    근거 있으면 빼줘」). 그날 수업 전 6편 90장 중 69장이 필기 강조를 다른 배지와 같이
    달고 있었다 — 덱마다 15장 중 8~13장이라 배지가 아무것도 가르지 못했다."""
    if "annotation" in tags and any(t in STRONGER_THAN_ANNOTATION for t in tags):
        return [t for t in tags if t != "annotation"]
    return list(tags)


# 근거의 기출 문항 표기 — `2025-28` · `2025-28번` · `2025년 28`.
RE_EXAM_REF = re.compile(r"^\s*(\d{4})\D+(\d+)")


def _fail(card, code, detail=""):
    return {"code": code, "detail": detail, "card": card}


def _figure_index(prep: dict) -> tuple[dict, dict]:
    figs, occs = {}, {}
    for s in prep["pages"]:
        for f in s["lecture_figures"]:
            figs[f["id"]] = s["slide"]
        for o in s["occlusion_candidates"]:
            occs[o["id"]] = (s["slide"], o["figure_id"], o.get("label"))
    return figs, occs


def validate(raw: dict, prep: dict, jokbo: dict | None,
             professor_stayed: bool = True, preview_text: str | None = None) -> tuple[list, dict]:
    cards = list(raw.get("cards", []))
    must = raw.get("must_know") or {}
    n_slides = prep["slides"]
    figs, occs = _figure_index(prep)
    jokbo_qs = (jokbo or {}).get("questions", [])
    jokbo_keys = {(q["year"], q["no"]) for q in jokbo_qs}
    jokbo_years = {q["year"] for q in jokbo_qs}
    must_reason = {norm_key(i["item"]): i["reason"] for i in must.get("items", [])}

    schema_check = Draft202012Validator(CARD_SCHEMA)
    kept, dropped, flags = [], [], defaultdict(list)
    seen_exact: dict[str, int] = {}
    autofix = Counter()

    for idx, c in enumerate(cards):
        errs = sorted(schema_check.iter_errors(c), key=lambda e: e.path)
        if errs:
            dropped.append(_fail(c, "schema", "; ".join(
                f"{'/'.join(str(p) for p in e.path) or '(root)'}: {e.message}"
                for e in errs[:3])))
            continue

        q, a = c["q"].strip(), c["a"].strip()
        fmt, src = c["card_format"], c["source_type"]

        if not q or not a:
            dropped.append(_fail(c, "empty_q_or_a"))
            continue
        if norm_key(q) == norm_key(a):
            dropped.append(_fail(c, "q_equals_a"))
            continue

        # 범위. 작년 강의록·필기에서 온 카드는 슬라이드를 가리켜야 한다.
        # 예습 설명본에서 온 카드는 슬라이드가 없을 수 있다.
        if src in ("lecture", "annotation"):
            if c.get("slide_no") is None:
                dropped.append(_fail(c, "missing_slide_no"))
                continue
            if not 1 <= c["slide_no"] <= n_slides:
                dropped.append(_fail(c, "slide_out_of_range",
                                     f"slide_no={c['slide_no']} / 1..{n_slides}"))
                continue
            ref = c.get("jokbo_ref")
            if ref:
                st = _ref_status(ref, jokbo_keys, jokbo_years)
                if st != "ok":
                    flags[idx].append("jokbo_ref_outside_slice" if st == "outside"
                                      else "jokbo_ref_not_found")
        elif src == "jokbo":
            ref = c.get("jokbo_ref")
            if not ref:
                dropped.append(_fail(c, "missing_jokbo_ref"))
                continue
            # 갈래의 뜻은 `quizgen.validate._ref_status` 에 있다. 측정은 복습 쪽에서
            # 나왔고(28편 · 삭제 17장), 여기는 같은 검사라 같이 고친다.
            st = _ref_status(ref, jokbo_keys, jokbo_years)
            if st == "missing":
                dropped.append(_fail(c, "jokbo_ref_not_found", f"{ref['year']}-{ref['no']}"))
                continue
            if st == "outside":
                flags[idx].append("jokbo_ref_outside_slice")

        # 교수가 바뀌었으면 과거 반복은 이 단원의 중심이 아니다. 이유를 강등한다.
        if c["reason"] == "repeated" and not professor_stayed:
            dropped.append(_fail(c, "repeated_but_professor_changed",
                                 "교수가 바뀐 강의에서는 reason=repeated 를 쓸 수 없다"))
            continue
        if c["reason"] == "repeated" and not c.get("jokbo_ref"):
            flags[idx].append("repeated_without_jokbo_ref")

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
                unlabeled = [i for i in ids if not (occs[i][2] or "").strip()]
                if unlabeled:
                    dropped.append(_fail(c, "occlusion_unlabeled_region", ", ".join(unlabeled)))
                    continue
                labels = [occs[i][2] for i in ids]
                if not occlusion_answer_matches(labels, a):
                    dropped.append(_fail(c, "occlusion_answer_mismatch",
                                         f"가린 라벨: {', '.join(labels)} / a: {a}"))
                    continue
        elif media:
            c["media"] = None
            autofix["media_on_text_card"] += 1
            flags[idx].append("media_on_text_card")

        key = norm_key(q) + "␟" + norm_key(c["a"])
        if key in seen_exact:
            dropped.append(_fail(c, "exact_duplicate", f"#{seen_exact[key]} 와 동일"))
            continue
        seen_exact[key] = idx

        c["_idx"] = idx
        kept.append(c)

    # ── soft flag ────────────────────────────────────────────────────
    has_difficulty = any("difficulty" in (c.get("learning_support") or {}) for c in kept)
    for c in kept:
        i = c["_idx"]
        q, a, fmt = c["q"], c["a"], c["card_format"]

        if fmt not in IMAGE_FORMATS and RE_POINTS_AT_SOURCE.search(q):
            flags[i].append("points_at_source")

        # 예습 카드의 explanation 은 '수업에서 어디에 쓰이는지'를 잇는 다리다.
        # 복습에서는 있으면 좋은 것이지만 여기서는 목적의 절반이라 더 세게 본다.
        if not (c.get("explanation") or "").strip():
            flags[i].append("missing_bridge_to_lecture")

        support = c.get("learning_support") or {}
        difficulty = support.get("difficulty")
        if has_difficulty and not difficulty:
            flags[i].append("missing_difficulty")
        if difficulty and bool(c.get("challenge")) != (difficulty == "challenge"):
            flags[i].append("difficulty_challenge_mismatch")
        # 옛 카드의 재검토에는 새 칸을 강제하지 않는다. 새 생성은 note 입력을 전달한다.
        if "learning_support" in c or preview_text is not None:
            if any(not (support.get(k) or "").strip() for k in ("hint", "scope", "lecture_focus")):
                flags[i].append("missing_learning_support")
        excerpt = (support.get("preview_excerpt") or "").strip()
        hint = norm_key(support.get("hint") or "")
        answer = norm_key(a)
        if len(answer) >= 2 and answer in hint:
            flags[i].append("answer_leaked_in_hint")
        if preview_text is not None:
            if preview_text.strip() and not c.get("challenge") and not excerpt:
                flags[i].append("missing_preview_evidence")
            if excerpt and re.sub(r"\s+", "", excerpt) not in re.sub(r"\s+", "", preview_text):
                flags[i].append("preview_excerpt_not_found")

        if fmt != "cloze" and containment(char_ngrams(a), char_ngrams(q)) >= LEAK_THRESHOLD:
            flags[i].append("answer_leaked_in_question")

        # 「왜 냈나」(2026-10-04). 비면 학생이 「이것까지?」를 그대로 겪는다. 답 뒤에 보이므로
        # 답이 들어 있어도 된다 — 앞면에 서던 동안 재던 노출은 같은 날 걷어 냈다.
        why = (c.get("why_asked") or "").strip()
        if not why:
            flags[i].append("missing_why_asked")
        else:
            if len(why) > MAX_WHY_CHARS:
                flags[i].append("why_asked_too_long")
            tags = c.get("why_tags") or []
            cites = any(w in why for w in WHY_CITES_EXAM) or "exam" in tags
            if cites and not c.get("jokbo_ref"):
                flags[i].append("why_cites_exam_without_ref")
            if not tags:
                flags[i].append("missing_why_tags")
        if len(RE_CLOZE.findall(q)) > MAX_RECALL_ITEMS:
            flags[i].append("too_many_clozes")
        if c["card_type"] == "sequence" or len(RE_BULLET_LINE.findall(a)) >= 2:
            if count_items(a) > MAX_RECALL_ITEMS:
                flags[i].append("too_many_items")
        if fmt != "cloze" and len(q) > MAX_Q_CHARS:
            flags[i].append("question_too_long")
        if fmt == "ox" and q.rstrip().endswith("?"):
            flags[i].append("ox_is_question_not_statement")
        if fmt == "image_occlusion":
            for oid in c["media"].get("occlusion_ids", []):
                label = occs[oid][2]
                if label and norm_key(label) and norm_key(label) in norm_key(q):
                    flags[i].append("occlusion_answer_leaked_in_question")
                    break

    # 유사 중복
    sigs = [(c["_idx"], c.get("slide_no"), char_ngrams(c["q"] + " " + c["a"]),
             (c.get("media") or {}).get("figure_id"), c["card_format"], c["a"]) for c in kept]
    similar = []
    for x in range(len(sigs)):
        for y in range(x + 1, len(sigs)):
            fx, fy = sigs[x][3], sigs[y][3]
            if fx and fy and fx != fy:
                continue
            if sigs[x][4] == sigs[y][4] == "ox" and sigs[x][5] != sigs[y][5]:
                continue
            same_slide = sigs[x][1] is not None and sigs[x][1] == sigs[y][1]
            j = jaccard(sigs[x][2], sigs[y][2])
            if j >= (SIMILAR_SAME_SLIDE if same_slide else SIMILAR_CROSS_SLIDE):
                similar.append({"a": sigs[x][0], "b": sigs[y][0], "jaccard": round(j, 2),
                                "same_slide": same_slide})
                flags[sigs[x][0]].append("similar_duplicate")
                flags[sigs[y][0]].append("similar_duplicate")

    # ── 예습 고유의 계약 ─────────────────────────────────────────────
    n = len(kept)
    ox = sum(1 for c in kept if c["card_format"] == "ox")
    contract = []
    if n < MIN_CARDS:
        contract.append(f"카드가 {n}장이다. 최소 {MIN_CARDS}장 — 강의를 덜 훑었을 수 있다")
    if n > MAX_CARDS:
        contract.append(f"카드가 {n}장이다. 상한 {MAX_CARDS}장 — "
                        f"넘치는 것은 '꼭 반드시'가 아니었다는 뜻이다")
    if n and ox / n > OX_SHARE_MAX:
        contract.append(f"O/X 가 {ox}/{n} ({ox / n:.0%}) 이다. 상한 {OX_SHARE_MAX:.0%}")
    challenge = sum(1 for c in kept if c.get("challenge"))
    if not MIN_CORE <= n - challenge <= MAX_CORE:
        contract.append(f"핵심 문항은 {MIN_CORE}~{MAX_CORE}장이어야 한다. 현재 {n - challenge}장")
    if not MIN_CHALLENGE <= challenge <= MAX_CHALLENGE:
        contract.append(f"도전 문제가 {challenge}장이다. 총 8~12장 안에 "
                        f"{MIN_CHALLENGE}~{MAX_CHALLENGE}장이어야 한다")
    difficulty_mix = Counter((c.get("learning_support") or {}).get("difficulty") for c in kept)
    if has_difficulty:
        for level, label in DIFFICULTY_LABELS.items():
            if not difficulty_mix[level]:
                contract.append(f"{label} 난도 문항이 없다. 기본·심화·도전을 모두 포함한다")

    # ── 승인된 목록과 카드를 잇는 끈 ────────────────────────────────
    #
    # 카드가 `must_id` 를 적어 왔으면 그것으로 잇는다 — 추측할 것이 없다.
    # **없으면 아무 값도 내지 않는다.** 글자 유사도로 대신 재 봤더니 문턱 0.05~0.20
    # 사이에서 안 닿은 항목이 8%~72% 로 흔들렸다(예습 10편 · must 항목 185개).
    # 그 폭이면 문턱을 고르는 것이 곧 답을 고르는 것이라, 재지 않고 **안 쟀다고 적는다.**
    #
    # 갈래가 셋이다. **가운데 것을 따로 두는 이유**는 그것이 조용한 실패이기 때문이다 —
    # 승인본에 id 가 있는데 카드가 하나도 안 적었으면 계약을 어긴 것이지, 잴 것이 없는
    # 것이 아니다. 하나로 뭉치면 「안 쟀다」로 읽히고 그대로 지나간다.
    items = must.get("items") or []
    by_id = {it["id"]: it for it in items if it.get("id")}
    linked = Counter(c.get("must_id") for c in kept if c.get("must_id"))
    if by_id and linked:
        method = "must_id"          # 끈이 있다. 사실로 센다
    elif by_id:
        method = "not_written"      # 승인본에는 id 가 있는데 카드가 아무도 안 적었다
    else:
        method = "unlinked"         # 2026-08-30 이전에 만든 편이다. 잴 것이 없다

    # 기출 배지는 근거에서 채운다(2026-10-04 관리자 — 「기출 배지가 생각보다 적다」).
    # 모델에게 맡겼더니 글이 기출 아닌 이유를 쓰면 기출 배지도 같이 빠졌다 — 6편에서
    # 기출 근거가 있는 항목의 카드 16장. 배지는 「이 주제가 기출에 나왔다」는 사실이고
    # 그 사실은 승인본에 있으니 코드가 붙인다. 근거 문항(`jokbo_ref`)도 같이 채운다.
    for c in kept:
        it = by_id.get(c.get("must_id") or "")
        exam = [s for s in (it or {}).get("signals") or [] if s.get("kind") == "exam"]
        if not exam:
            continue
        tags = list(c.get("why_tags") or [])
        if "exam" not in tags:
            c["why_tags"] = ["exam", *tags][:MAX_WHY_TAGS]
            autofix["exam_tag_from_signals"] += 1
        if not c.get("jokbo_ref"):
            for s in exam:
                m = RE_EXAM_REF.match(str(s.get("ref") or ""))
                if m:
                    c["jokbo_ref"] = {"year": m.group(1), "no": m.group(2)}
                    autofix["jokbo_ref_from_signals"] += 1
                    break
        # 위의 「기출을 말하는데 문항이 없다」 표시는 채우기 전에 섰다. 채웠으면 걷는다.
        if c.get("jokbo_ref"):
            flags[c["_idx"]] = [f for f in flags[c["_idx"]] if f != "why_cites_exam_without_ref"]

    for c in kept:
        tags = list(c.get("why_tags") or [])
        pruned = prune_annotation(tags)
        if pruned != tags:
            c["why_tags"] = pruned
            autofix["annotation_tag_dropped"] += 1

    # 배지가 근거에서 왔는가(2026-10-04). 항목이 `signals` 칸을 갖고 있을 때만 잰다 —
    # 그 전에 만든 승인본은 칸이 없어서, 재면 모든 배지가 「근거 밖」으로 찍힌다.
    for c in kept:
        it = by_id.get(c.get("must_id") or "")
        if not it or "signals" not in it:
            continue
        have = {s.get("kind") for s in it.get("signals") or []} | {"basis"}
        if any(t in WHY_TAGS and t not in have for t in c.get("why_tags") or []):
            flags[c["_idx"]].append("why_tag_not_in_signals")

    orphan_objectives, card_budget = [], []
    if method == "must_id":
        for c in kept:
            mid = c.get("must_id")
            if not mid or mid not in by_id:
                flags[c["_idx"]].append("off_must")
        for mid, it in by_id.items():
            if not linked.get(mid):
                orphan_objectives.append(it["item"])
            elif it.get("cards") and linked[mid] != it["cards"]:
                card_budget.append({"id": mid, "item": it["item"][:40],
                                    "assigned": it["cards"], "made": linked[mid]})

    if method == "not_written":
        contract.append(f"카드 {len(kept)}장 중 `must_id` 를 적은 것이 하나도 없다. "
                        f"승인된 항목 {len(by_id)}개와 이을 길이 없다")

    coverage = {
        # 이 이름으로 `runner/deck.py` 가 읽어 간다 (복습과 같은 칸).
        "objectives_without_card": orphan_objectives,
        "cards_per_item_mismatch": card_budget,
        # **슬라이드 커버리지는 내지 않는다.** 예습은 그것을 목표로 하지 않는다.
        # 그래서 `untouched_undeclared` 가 여기 없다 — 0 이 아니라 아예 안 잰 것이다.
        "method": method,
        "must_items": len(items),
    }

    # must_know 와 카드의 `reason` 이 어긋나는지.
    #
    # **끈이 있으면 끈으로 본다.** 예전에는 항목 이름이 카드 글자에 그대로 남아 있을
    # 때만 볼 수 있었고, 그래서 예습 10편 · must 항목 185개에서 **한 건도 안 걸렸다.**
    # 0 이 「어긋난 것이 없다」는 뜻이 아니라 「볼 수 있는 것이 없었다」는 뜻이었다.
    reason_mismatch = []
    if method == "must_id":
        for c in kept:
            it = by_id.get(c.get("must_id") or "")
            if it and c["reason"] != it["reason"]:
                reason_mismatch.append({"q": c["q"][:40], "must_id": c["must_id"],
                                        "card": c["reason"], "must": it["reason"]})
    else:
        for c in kept:
            for item, r in must_reason.items():
                if item and item in norm_key(c["q"] + " " + c["a"]) and c["reason"] != r:
                    reason_mismatch.append({"q": c["q"][:40], "card": c["reason"], "must": r})
                    break

    for c in kept:
        c["review_flags"] = sorted(set(flags[c.pop("_idx")]))

    suspects = {
        "n_input": len(cards), "n_kept": n, "n_dropped": len(dropped),
        "dropped": dropped,
        "autofixed": dict(autofix),
        "flag_counts": dict(Counter(f for c in kept for f in c["review_flags"])),
        "similar_pairs": similar,
        "coverage": coverage,
        "contract_violations": contract,
        "reason_mismatch": reason_mismatch,
        "format_mix": dict(Counter(c["card_format"] for c in kept)),
        "type_mix": dict(Counter(c["card_type"] for c in kept)),
        "reason_mix": dict(Counter(c["reason"] for c in kept)),
        "challenge": challenge,
        "difficulty_mix": {level: difficulty_mix[level] for level in DIFFICULTY_LABELS},
        "source_mix": dict(Counter(c["source_type"] for c in kept)),
        "must_know_items": len(must.get("items", [])),
        "rejected_candidates": len(must.get("rejected_candidates", [])),
    }
    return kept, suspects


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="예습 카드를 기계 검증한다")
    ap.add_argument("raw", help="items.raw.json")
    ap.add_argument("--prep", required=True)
    ap.add_argument("--jokbo")
    ap.add_argument("--must", help="must_know.approved.json (reason 대조용)")
    ap.add_argument("--note", help="예습 설명본. 핵심 문항의 발췌 근거를 대조한다")
    ap.add_argument("--professor-changed", action="store_true",
                    help="담당 교수가 바뀌었다 — reason=repeated 를 금지한다")
    ap.add_argument("-o", "--out", help="기본은 raw 옆의 items.checked.json")
    args = ap.parse_args(argv)

    raw_path = Path(args.raw)
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    prep = json.loads(Path(args.prep).read_text(encoding="utf-8"))
    jokbo = json.loads(Path(args.jokbo).read_text(encoding="utf-8")) if args.jokbo else None
    if args.must and Path(args.must).exists() and "must_know" not in raw:
        raw["must_know"] = json.loads(Path(args.must).read_text(encoding="utf-8"))

    note = Path(args.note) if args.note else raw_path.with_name("note.md")
    preview_text = note.read_text(encoding="utf-8") if note.exists() else None
    kept, suspects = validate(raw, prep, jokbo, professor_stayed=not args.professor_changed,
                              preview_text=preview_text)

    out = Path(args.out) if args.out else raw_path.with_name("items.checked.json")
    out.write_text(json.dumps({"cards": kept}, ensure_ascii=False, indent=2), encoding="utf-8")
    raw_path.with_name("suspects.json").write_text(
        json.dumps(suspects, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"입력 {suspects['n_input']}장 → 유지 {suspects['n_kept']} · "
          f"탈락 {suspects['n_dropped']}")
    if suspects["dropped"]:
        for d in suspects["dropped"][:10]:
            print(f"   [{d['code']}] {d['card'].get('q', '')[:50]}  {d['detail']}")
    print(f"형식 {suspects['format_mix']}")
    print(f"유형 {suspects['type_mix']}")
    print(f"이유 {suspects['reason_mix']}")
    if suspects["flag_counts"]:
        print(f"깃발 {suspects['flag_counts']}")
    if suspects["reason_mismatch"]:
        print(f"⚠ must_know 와 이유가 어긋난 카드 {len(suspects['reason_mismatch'])}장")
    cov = suspects["coverage"]
    if cov["method"] == "must_id":
        print(f"승인 항목 {cov['must_items']}개 중 카드가 안 간 것 "
              f"{len(cov['objectives_without_card'])}개"
              + (f" · 배정 수와 다른 항목 {len(cov['cards_per_item_mismatch'])}개"
                 if cov["cards_per_item_mismatch"] else ""))
        for o in cov["objectives_without_card"][:5]:
            print(f"   [카드 없음] {o[:60]}")
        for b in cov["cards_per_item_mismatch"][:5]:
            print(f"   [배정 {b['assigned']} → {b['made']}] {b['item']}")
    elif cov["method"] == "not_written":
        print(f"⚠ 카드가 must_id 를 하나도 안 적었다 — 승인 항목 {cov['must_items']}개와 "
              f"이을 길이 없다")
    else:
        print("커버리지: 카드에 must_id 가 없어 **재지 않았다** "
              "(0 이 아니라 잰 적이 없다는 뜻이다)")
    if suspects["contract_violations"]:
        print()
        for v in suspects["contract_violations"]:
            print(f"⚠ 계약 위반 — {v}")
        return 2
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
