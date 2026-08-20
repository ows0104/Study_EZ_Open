"""v2 기계 검증. **판정하지 않고 세어서 표시한다.**

    python -m quiz2.validate runs/260819_01

입력  items.raw.json     (merge.py가 합친 것)
      structure.json     구간과 조각 경계의 주인
      plan.json          조각이 낸 learning_plan (회수 목표·제외 기록)
출력  items.checked.json 빌드 가능한 카드만
      suspects.json      감사와 사람이 볼 것 전부

## v1 검증기를 그대로 못 쓰는 이유

`quiz/validate.py`를 v2 산출물에 대고 돌리면 **가짜 플래그가 348건** 나온다.
v2가 일부러 없앤 필드를 찾기 때문이다.

    weak_source_anchor 163   ⑱ source_anchor를 안 둔다
    no_retrieval_target 163  회수 목표는 카드가 아니라 learning_plan이 든다
    no_trap_note 22          trap_note를 안 둔다 (함정은 explanation에)

그 셋을 뺐고, v2에만 있는 것을 넣었다 — `card_format` 정합성(⑫㉕), 조각 경계
(assemble가 조각마다 범위를 못박는다), 예산 집계(⑴).

## quiz/에 무엇을 기대는가

`cloze`·`textutil`·`occlusion`·`timings`만 가져다 쓴다. v2 파이프라인이 0단계·
5단계에서 이미 쓰는 공용 유틸이다.

**출제 규칙을 담은 것은 안 가져온다.** 정규식도 중복 판정도 여기서 다시 쓴다.
`quiz/`는 언젠가 없어질 기준선이고, 규칙의 주인은 `quiz2/prompt.py`다.

## 수치의 출처

한도는 대부분 `INTERVIEW.md`에서 왔고 주석에 항목 번호를 달았다. **길이 한도만
예외로 v1에서 그대로 넘어왔다** — 인터뷰는 *"길이는 코드가 센다"*(⑵)까지만
정하고 숫자를 안 줬다. 이 자리를 제대로 대신할 것은 재현 검사(⓹)다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from quiz.cloze import (  # noqa: E402
    cloze_has_malformed_markup,
    cloze_matches,
    has_cloze_markup,
    normalize_cloze_to_c1,
    valid_cloze_text,
)
from quiz.occlusion import build_label_index, resolve_rects  # noqa: E402
from quiz.textutil import norm_for_compare, tokens  # noqa: E402
from quiz import timings  # noqa: E402
from quiz2.prompt import CARD_FORMATS, DECK_BUDGET_PER_SLIDE, IMPORTANCE_TIERS  # noqa: E402


# prompt.CARD_TYPES의 여섯. 거기 산문과 여기 집합이 어긋나면 프롬프트가 주인이다.
VALID_CARD_TYPES = {"fact", "comparison", "mechanism", "trap", "list", "sequence"}
VALID_IMPORTANCE = set(IMPORTANCE_TIERS)
VALID_CARD_FORMATS = set(CARD_FORMATS)
VALID_SOURCE_TYPES = {"lecture", "jokbo"}
VALID_REVIEW_FLAGS = {"answer_mismatch", "question_error", "uncertain"}
# ⑲ evidence_type. 족보는 question_text를, 강의록은 나머지를 쓴다.
VALID_EVIDENCE_TYPES = {
    "lecture": {"lecture_text", "table", "figure", "annotation"},
    "jokbo": {"question_text", "table", "figure"},
}

# ⑨⑩ 하나의 회상 단위. **일곱부터는 쪼갠다** — 관리자가 준 유일한 개수 한도다.
RECALL_UNIT_MAX = 6

# v1에서 넘어온 길이 한도. 인터뷰가 정한 것이 아니다 (위 docstring).
Q_MAX_CHARS = 110
Q_MAX_CHARS_JOKBO = 160          # 임상 vignette은 나이·증상·소견을 담아야 한다
A_MAX_CHARS = 110
A_MAX_CHARS_ATOMIC = 50          # fact와 cloze의 답은 명사구 하나다

# ㉕ ox는 선지 여럿을 한 카드에 모으라고 **일부러 만든 형식**이다. 1회차 13장이
# q 207~491자였다. basic용 한도를 그대로 대면 13장 전부가 가짜 플래그가 된다.
# ox에는 길이 대신 선지 개수(RECALL_UNIT_MAX)와 q·a 짝맞춤을 본다.
LENGTH_EXEMPT_FORMATS = {"ox"}

# 정보가 몰린 슬라이드는 대여섯 장이 맞다(VOLUME). 넘을 때만 쪼개기를 의심한다.
# CLAUDE.md 판정: 이건 문턱이 아니라 계수기다. 울려도 사람을 부르지 않는다.
SLIDE_CONCENTRATION_MAX = 8

CANONICAL_ITEMS = {"items.raw.json", "items.final.json"}

# QA ⑬ — 앞면에서 학습자는 슬라이드를 못 본다.
_SOURCE_REFERENCE_RE = re.compile(
    r"(위\s*(그림|표|도식|슬라이드|사진)|아래\s*(그림|표|도식)|다음\s*(그림|표|도식)"
    r"|이\s*(그림|표|도식|슬라이드|사진)|그림에서|표에서|도식(상|에서)|슬라이드에\s*(따르면|나온|제시)"
    # 좌측·우측은 뒤에 그림·사진이 올 때만. 임상 vignette의 "우측 하복부"가 더 흔하다.
    r"|제시된\s*(그림|표|도식)|(좌측|우측|왼쪽|오른쪽)\s*(그림|사진|표|도식|이미지))"
)
# GROUNDING — 자료의 내용이 아니라 수업 운영·출제 경향 자체를 묻는 카드.
_META_QUESTION_RE = re.compile(
    r"(교수(님|가|는)|강의에서\s*(강조|언급)|시험에\s*(나온|출제)|출제\s*(경향|빈도)|족보에\s*(따르면|나온))"
)
_YES_NO_RE = re.compile(r"^(예|아니오|아니요|맞다|틀리다|yes|no|true|false|o|x)[.!]?$", re.I)
# ⓷ "질문과 답이 직접적으로 연결이 안될때"의 한 갈래 — 회상 둘을 한 카드에 욱여넣기.
_COMPOUND_Q_RE = re.compile(r"(이며|이고|무엇이며|무엇이고|하며|각각\s*(어떤|무엇))")
# QA — a는 명사구여야 한다. 서술문이면 부연이 답에 섞였다.
_PREDICATE_END_RE = re.compile(r"(된다|한다|이다|있다|없다|진다|난다|시킨다|킨다)[.]?$")
# ⑫ cloze는 빈칸을 채우면 평서문이 되어야 한다. 물음표·"무엇인가"는 basic의 몫이다.
_CLOZE_QUESTION_RE = re.compile(r"(\?\s*$|무엇인가|무엇입니까|어떤 것인가)")
# ㉕ ox 선지 표식. 1회차 13장이 전부 원 숫자(①~⑳)를 썼다.
_CHOICE_RE = re.compile(r"[①-⑳]")
# ② 제외 기록에 적힌 슬라이드 번호. 프롬프트가 구조를 요구하지 않으므로 **최선 추정**이다.
_REJECTED_SLIDE_RE = re.compile(r"슬라이드\s*(\d+)")


def _text(value) -> str:
    return str(value or "").strip()


def _answer_leak(q: str, a: str) -> bool:
    """정답의 유의미 토큰이 질문에 거의 다 노출된 경우."""
    a_tokens = tokens(a)
    if len(a_tokens) < 2:
        return False
    q_tokens = tokens(q)
    return sum(1 for t in a_tokens if t in q_tokens) / len(a_tokens) >= 0.9


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _answer_lines(a: str) -> list[str]:
    return [ln for ln in (x.strip() for x in a.splitlines()) if ln]


def _recall_units(item: dict, q: str, a: str) -> tuple[int, str] | None:
    """이 카드가 한 번에 회수시키는 항목 수. 셀 수 있는 꼴에서만 센다 (⑨⑩)."""
    card_format = _text(item.get("card_format")).lower()
    card_type = _text(item.get("card_type")).lower()
    if card_format == "ox":
        return len(set(_CHOICE_RE.findall(q))), "선지"
    if card_format == "cloze":
        return len(cloze_matches(q)), "빈칸"
    if card_type in {"list", "sequence"}:
        return len(_answer_lines(a)), "항목"
    return None


def check_item(item: dict, max_slide: int, jokbo_range: list | None = None,
               chunk_ranges: dict | None = None,
               label_index: dict | None = None) -> tuple[list[str], list[str]]:
    """한 카드의 (hard, soft). hard가 있으면 빌드 불가.

    hard는 **기계적으로 명백한 것만** 한다. '자족적인가', '이 둘이 같은 걸 묻는가'
    같은 의미 판단은 여기서 하지 않는다.
    """
    hard: list[str] = []
    soft: list[str] = []
    source_type = _text(item.get("source_type")).lower() or "lecture"
    card_type = _text(item.get("card_type")).lower()
    card_format = _text(item.get("card_format")).lower()
    # 키가 있으면 검사한다. 빈 dict를 '오클루전 아님'으로 넘기면 그림 카드로
    # 만들려던 것이 조용히 텍스트 카드가 되어 나간다.
    occlusion = item["occlusion"] if item.get("occlusion") is not None else None

    q = _text(item.get("q"))
    a = _text(item.get("a"))
    if not q:
        hard.append("empty_question")
    if not a:
        hard.append("empty_answer")
    if q and a and norm_for_compare(q) == norm_for_compare(a):
        hard.append("question_equals_answer")

    # ── slide_no: 이미지가 붙는 유일한 근거 ─────────────────────────────
    try:
        slide_no = int(item.get("slide_no"))
    except (TypeError, ValueError):
        hard.append("slide_no_missing")
        slide_no = None
    # 경계는 자료의 범위(`total_slides`)다. 강의록 PDF 쪽수로 자르면 외부 족보를
    # 붙인 편에서 정상 카드가 hard 제거된다.
    if slide_no is not None and not (1 <= slide_no <= max_slide):
        hard.append(f"slide_no_out_of_range({slide_no}/1-{max_slide})")

    if jokbo_range and slide_no is not None and 1 <= slide_no <= max_slide:
        in_jokbo = int(jokbo_range[0]) <= slide_no <= int(jokbo_range[1])
        if in_jokbo and source_type != "jokbo":
            soft.append(f"source_type_range_mismatch(slide {slide_no}는 족보 구간)")
        elif not in_jokbo and source_type == "jokbo":
            soft.append(f"source_type_range_mismatch(slide {slide_no}는 강의록 구간)")

    # v2에만 있는 검사. assemble가 조각마다 "slide_no는 N 이상 M 이하"를 못박아
    # 보내므로, 벗어난 카드는 그 조각이 자기 구간 밖을 봤다는 뜻이다.
    # hard로 안 한다 — 경계에 걸친 내용을 옆 조각이 더 잘 아는 경우가 있다.
    chunk = _text(item.get("chunk"))
    if chunk_ranges and chunk in chunk_ranges and slide_no is not None:
        lo, hi = chunk_ranges[chunk]
        if not (lo <= slide_no <= hi):
            soft.append(f"chunk_range_mismatch(slide {slide_no} ∉ {chunk} {lo}-{hi})")

    # ── card_format 정합성 (⑫ ㉕) ──────────────────────────────────────
    if not card_format:
        soft.append("no_card_format")
    elif card_format not in VALID_CARD_FORMATS:
        soft.append(f"unknown_card_format({card_format})")

    if cloze_has_malformed_markup(q) and not valid_cloze_text(q):
        hard.append("cloze_malformed")
    if has_cloze_markup(a):
        soft.append("cloze_in_answer")
    if card_format == "cloze":
        if not has_cloze_markup(q):
            soft.append("cloze_format_without_markup")
        elif not valid_cloze_text(q):
            hard.append("cloze_empty")
        if _CLOZE_QUESTION_RE.search(q):
            soft.append("cloze_question_form")
    elif has_cloze_markup(q):
        soft.append(f"cloze_markup_without_format({card_format or '없음'})")

    if card_format == "ox":
        q_choices = set(_CHOICE_RE.findall(q))
        a_choices = set(_CHOICE_RE.findall(a))
        if not q_choices:
            soft.append("ox_no_choices")
        elif q_choices != a_choices:
            missing = "".join(sorted(q_choices - a_choices))
            extra = "".join(sorted(a_choices - q_choices))
            detail = f"q{len(q_choices)}/a{len(a_choices)}"
            if missing:
                detail += f" 판정없음{missing}"
            if extra:
                detail += f" 선지없음{extra}"
            soft.append(f"ox_choice_mismatch({detail})")

    units = _recall_units(item, q, a)
    if units and units[0] > RECALL_UNIT_MAX:
        soft.append(f"too_many_recall_units({units[1]} {units[0]}>{RECALL_UNIT_MAX})")

    # ── 자족성과 회상 방향 ─────────────────────────────────────────────
    # 오클루전 카드는 앞면에 그림이 뜨므로 자족성의 유일한 예외다.
    if not occlusion and _SOURCE_REFERENCE_RE.search(q):
        soft.append("source_reference")
    if _META_QUESTION_RE.search(q):
        soft.append("meta_question")
    # cloze는 빈칸이 곧 답이고 Anki가 가려 준다. ox는 선지를 보여주는 것이 형식이다.
    # 둘에 노출 검사를 대면 전량이 가짜로 걸린다.
    if q and a and card_format not in {"cloze", "ox"} and _answer_leak(q, a):
        soft.append("answer_leak")
    if card_format not in LENGTH_EXEMPT_FORMATS:
        q_limit = Q_MAX_CHARS_JOKBO if source_type == "jokbo" else Q_MAX_CHARS
        if len(q) > q_limit:
            soft.append(f"question_too_long({len(q)}>{q_limit})")
        atomic = card_type == "fact" or card_format == "cloze"
        a_limit = A_MAX_CHARS_ATOMIC if atomic else A_MAX_CHARS
        if len(a) > a_limit:
            soft.append(f"answer_too_long({len(a)}>{a_limit})")
        if atomic and _PREDICATE_END_RE.search(a):
            soft.append("answer_is_sentence")
    if card_format != "ox" and (_COMPOUND_Q_RE.search(q) or q.count("?") > 1):
        soft.append("compound_question")
    if _YES_NO_RE.match(a):
        soft.append("yes_no_answer")

    # QA ⑮ — 왜 그 답인지 한두 문장. 없으면 틀렸을 때 카드가 아무것도 안 알려준다.
    if not _text(item.get("explanation")):
        soft.append("no_explanation")

    # ── 메타데이터 ─────────────────────────────────────────────────────
    if not card_type:
        soft.append("no_card_type")
    elif card_type not in VALID_CARD_TYPES:
        soft.append(f"unknown_card_type({card_type})")
    importance = _text(item.get("importance")).lower()
    if not importance:
        soft.append("no_importance")
    elif importance not in VALID_IMPORTANCE:
        soft.append(f"unknown_importance({importance})")

    if source_type not in VALID_SOURCE_TYPES:
        soft.append(f"unknown_source_type({source_type})")
        source_type = "lecture"
    evidence_type = _text(item.get("evidence_type")).lower()
    if not evidence_type:
        soft.append("no_evidence_type")
    elif evidence_type not in VALID_EVIDENCE_TYPES[source_type]:
        soft.append(f"evidence_type_mismatch({evidence_type}/{source_type})")

    # ⑥ 필기가 유일한 근거인 카드는 **족보가 그 지점을 물었을 때만** 선다.
    # 조건 없이 열어 두면 필기 사담이 전부 근거로 둔갑한다.
    if evidence_type == "annotation" and not item.get("exam_hit"):
        soft.append("annotation_without_exam_hit")
    # ⑳ exam_hit은 강의록 카드에만. 족보 카드는 source_type이 이미 구분한다.
    # 1회차에 족보 44장 전부에 붙었던 자리다 (RUNS.md 「깨진 것 ②」).
    if item.get("exam_hit") and source_type == "jokbo":
        soft.append("exam_hit_on_jokbo")

    # ㉓ 정오 검토는 족보에만 해당한다. 강의록에 붙었다면 외부 지식이 새어든 신호다.
    # **review_note 단독은 막지 않는다** — 그건 ⑳‴의 자료 주의고 강의록도 쓴다.
    flags = item.get("review_flags") or []
    if flags and source_type != "jokbo":
        soft.append("review_flag_on_lecture")
    if any(f not in VALID_REVIEW_FLAGS for f in flags):
        soft.append("unknown_review_flag")
    if flags and not _text(item.get("review_note")):
        soft.append("review_flag_without_note")

    # ㉞ 오클루전 패스는 아직 없다. 나오면 여기서 좌표와 라벨을 본다.
    if occlusion is not None:
        if not isinstance(occlusion, dict):
            hard.append("occlusion_not_object")
        else:
            _, _masks, problems = resolve_rects(occlusion, slide_no or 0, label_index or {})
            if label_index is None:
                problems = [p for p in problems if not p.startswith("unknown_label_id")]
                if occlusion.get("label_ids"):
                    problems = [p for p in problems if p != "occlusion_empty"]
            hard.extend(problems)
            # 마스크는 세지 않는다. 회수 대상이 아니라 답이 딴 데 적힌 자리를 덮는 상자다.
            boxes = len(occlusion.get("label_ids") or []) + len(occlusion.get("rects") or [])
            if boxes > RECALL_UNIT_MAX:
                soft.append(f"too_many_recall_units(상자 {boxes}>{RECALL_UNIT_MAX})")
            if source_type == "jokbo":
                soft.append("occlusion_on_jokbo")
    return hard, soft


def find_exact_duplicates(items: list[dict]) -> list[int]:
    """완전 중복의 '뒤에 나온 쪽' 인덱스. 이것만 기계적으로 제거한다."""
    seen: set[str] = set()
    drop: list[int] = []
    for idx, item in enumerate(items):
        key = norm_for_compare(item.get("q", "")) + "||" + norm_for_compare(item.get("a", ""))
        if key in seen:
            drop.append(idx)
        else:
            seen.add(key)
    return drop


def find_near_duplicate_groups(items: list[dict], threshold: float = 0.70) -> list[dict]:
    """유사 후보만 묶어 넘긴다. **여기서 제거하지 않는다.**

    같은 개념을 다른 회상 방향으로 묻는 문항은 둘 다 살아남아야 하는데 그 판단은
    기계가 못 한다. 후보 blocking까지가 코드의 몫이다.

    v2에서 값이 올라간 자리다 — 조각이 서로를 못 보고 동시에 도므로 경계에서 같은
    카드가 두 번 날 수 있다. `chunk`를 함께 실어 어느 조각끼리인지 보인다.
    """
    groups: list[dict] = []
    used: set[int] = set()
    sigs = [tokens(f"{it.get('q', '')} {it.get('a', '')}") for it in items]
    answers = [norm_for_compare(it.get("a", "")) for it in items]
    for i in range(len(items)):
        if i in used:
            continue
        members = [i]
        for j in range(i + 1, len(items)):
            if j in used:
                continue
            score = _jaccard(sigs[i], sigs[j])
            same_answer = answers[i] and answers[i] == answers[j]
            if score >= threshold or (same_answer and score >= 0.40):
                members.append(j)
        if len(members) > 1:
            used.update(members)
            groups.append({
                "indices": members,
                "similarity": round(
                    max(_jaccard(sigs[members[0]], sigs[m]) for m in members[1:]), 3),
                "cross_chunk": len({items[m].get("chunk") for m in members}) > 1,
                "items": [{
                    "index": m, "id": items[m].get("id"), "chunk": items[m].get("chunk"),
                    "q": items[m].get("q"), "a": items[m].get("a"),
                    "slide_no": items[m].get("slide_no"),
                    "card_type": items[m].get("card_type"),
                    "card_format": items[m].get("card_format"),
                } for m in members],
            })
    return groups


def load_plan(run_dir: Path) -> list[dict]:
    """plan.json을 조각 구분 없이 objective 목록으로 편다."""
    path = run_dir / "plan.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    flat: list[dict] = []
    for entry in payload:
        for objective in entry.get("learning_plan") or []:
            flat.append({"chunk": entry.get("chunk"), **objective})
    return flat


def coverage_gaps(plan: list[dict], items: list[dict], threshold: float = 0.55) -> list[dict]:
    """조각이 스스로 세운 회수 목표 중 어떤 카드도 회수하지 않는 것.

    **v1과 입력이 다르다.** v1은 별도 청사진(`blueprint.json`)의 목표를 봤는데 v2에는
    그 단계가 없고, 조각이 카드와 같은 호출에서 낸 `learning_plan`을 본다. 같은
    모델이 같은 자리에서 낸 것이라 v1보다 느슨한 검사다 — 목표를 안 세운 자리는
    애초에 여기 안 잡힌다.

    문자열 완전 일치로 보면 안 된다. 표현을 바꿔 카드로 만들기 때문에 정규화 토큰
    겹침으로 본다. 애매하면 누락으로 보고하지 않는다 (검토 피로가 이 단계를 죽인다).
    """
    if not plan:
        return []
    covered = [
        tokens(" ".join([str(it.get("q", "")), str(it.get("a", "")),
                         str(it.get("explanation", ""))]))
        for it in items
    ]
    gaps = []
    for objective in plan:
        for target in objective.get("retrieval_targets") or []:
            target_tokens = tokens(str(target))
            if not target_tokens:
                continue
            best = max((len(target_tokens & c) / len(target_tokens) for c in covered),
                       default=0.0)
            if best < threshold:
                gaps.append({
                    "chunk": objective.get("chunk"),
                    "objective": objective.get("objective"),
                    "target": target,
                    "best_overlap": round(best, 2),
                })
    return gaps


def rejected_summary(plan: list[dict]) -> dict:
    """② 카드로 안 만든 것의 사유별 개수. 조용히 빠뜨렸는지 여기서 보인다."""
    counts: dict[str, int] = {}
    for objective in plan:
        for candidate in objective.get("rejected_candidates") or []:
            reason = _text(candidate.get("reason")) or "(사유없음)"
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def declared_rejected_slides(plan: list[dict]) -> set[int]:
    """제외 기록에 번호가 적힌 슬라이드. **최선 추정이다.**

    프롬프트는 `rejected_candidates`에 슬라이드 번호를 구조로 넣으라고 요구하지
    않는다. 1회차가 `"슬라이드 3 — ..."` 꼴로 적었기에 그것만 읽는다. 못 읽은 것은
    `untouched_undeclared`에 남으므로 이 추정이 틀려도 신호를 지우지 않는다.
    """
    found: set[int] = set()
    for objective in plan:
        for candidate in objective.get("rejected_candidates") or []:
            for m in _REJECTED_SLIDE_RE.finditer(_text(candidate.get("candidate"))):
                found.add(int(m.group(1)))
    return found


def validate_items(items: list[dict], max_slide: int, jokbo_range: list | None = None,
                   chunk_ranges: dict | None = None,
                   label_index: dict | None = None) -> tuple[list[dict], list[dict]]:
    """(빌드 가능한 카드, 제거된 카드). 제거된 카드는 원문을 통째로 보존한다.

    보존이 중요한 이유: 커버리지 검수에서 '이 목표를 회수하던 카드가 사라졌다'가
    확인되면 새로 만들지 않고 원문을 복원하는 게 안전하다.
    """
    kept: list[dict] = []
    removed: list[dict] = []
    for idx, raw in enumerate(items):
        item = dict(raw)
        item.setdefault("id", f"q{idx + 1:03d}")
        if item.get("q"):
            item["q"] = normalize_cloze_to_c1(str(item["q"]))
        hard, soft = check_item(item, max_slide, jokbo_range, chunk_ranges, label_index)
        item["flags"] = soft
        if hard:
            removed.append({"reason": hard, "item": item})
        else:
            kept.append(item)

    for idx in sorted(find_exact_duplicates(kept), reverse=True):
        removed.append({"reason": ["exact_duplicate"], "item": kept.pop(idx)})
    return kept, removed


def load_structure(run_dir: Path, prep: dict) -> dict:
    """구간의 주인은 `structure.json`이고 `prep.json`은 정규식이 낸 힌트다.

    이걸 안 지키면 검증기가 유령 불평을 낸다 — v1 `260812_01`에서 힌트가 `[32,35]`,
    모델 판정이 `[31,35]`였고 슬라이드 31의 족보 카드 3장이 range_mismatch로 걸렸다.
    카드가 옳고 힌트가 틀렸는데도.
    """
    path = run_dir / "structure.json"
    if path.exists():
        try:
            structure = json.loads(path.read_text(encoding="utf-8"))
            structure["_source"] = "structure.json"
            return structure
        except (ValueError, OSError):
            pass
    return {"lecture_range": prep.get("lecture_range"),
            "jokbo_range": prep.get("jokbo_range"),
            "chunks": [], "_source": "prep.json(힌트)"}


def validate_run(run_dir: Path, items_name: str = "items.raw.json") -> dict:
    run_dir = Path(run_dir)
    prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))
    # 자료의 범위와 강의록 PDF 쪽수는 다르다. 외부 족보를 붙이면 슬라이드 번호가
    # 필기 뒤로 이어져 `total_slides`가 커진다. 경계는 자료의 범위를 따른다.
    max_slide = int(prep.get("total_slides") or prep["num_pages"])

    structure = load_structure(run_dir, prep)
    lecture_range = structure.get("lecture_range")
    jokbo_range = structure.get("jokbo_range")
    chunk_ranges = {
        str(c["id"]): (int(c["slides"][0]), int(c["slides"][1]))
        for c in structure.get("chunks") or [] if c.get("slides")
    }
    if jokbo_range:
        chunk_ranges["jokbo"] = (int(jokbo_range[0]), int(jokbo_range[1]))

    payload = json.loads((run_dir / items_name).read_text(encoding="utf-8"))
    items = payload["items"] if isinstance(payload, dict) else payload

    labels_path = Path(prep.get("labels_path") or (run_dir / "labels.json"))
    label_index = build_label_index(
        json.loads(labels_path.read_text(encoding="utf-8")) if labels_path.exists() else None)

    kept, removed = validate_items(items, max_slide, jokbo_range, chunk_ranges, label_index)
    plan = load_plan(run_dir)

    slide_counts: dict[int, int] = {}
    for item in kept:
        slide_counts[int(item["slide_no"])] = slide_counts.get(int(item["slide_no"]), 0) + 1
    hot_slides = [{"slide_no": s, "count": c} for s, c in sorted(slide_counts.items())
                  if c > SLIDE_CONCENTRATION_MAX]

    declared = declared_rejected_slides(plan)
    untouched = [s for s in range(1, max_slide + 1) if s not in slide_counts]

    def counts(key: str, values) -> dict:
        return {v: sum(1 for i in kept if str(i.get(key, "")).lower() == v) for v in values}

    importance_counts = counts("importance", IMPORTANCE_TIERS)
    # build.py와 같은 기준으로 센다. 족보 카드의 exam_hit은 태그로 안 나간다.
    importance_counts["exam_hit"] = sum(
        1 for i in kept
        if i.get("exam_hit") and str(i.get("source_type", "lecture")).lower() != "jokbo")

    # ⑴ 숫자는 모델에 안 준다. 예산은 **여기서 사후에만** 센다.
    # 기준은 강의록 구간의 슬라이드 수다 — 족보 구간까지 세면 예산이 부풀어
    # 강의 내용이 얇은 편에서도 통과해 버린다.
    budget_slides = (int(lecture_range[1]) - int(lecture_range[0]) + 1
                     if lecture_range else max_slide)
    budget = budget_slides * DECK_BUDGET_PER_SLIDE

    suspects = {
        "lecture_id": prep["lecture_id"],
        "total_slides": max_slide,
        "lecture_range": lecture_range,
        "jokbo_range": jokbo_range,
        "range_source": structure.get("_source"),
        "item_count": len(kept),
        "budget": {"slides": budget_slides, "per_slide": DECK_BUDGET_PER_SLIDE,
                   "target": budget, "actual": len(kept),
                   "ratio": round(len(kept) / budget, 2) if budget else None},
        "importance": importance_counts,
        "sources": counts("source_type", VALID_SOURCE_TYPES),
        "card_types": counts("card_type", VALID_CARD_TYPES),
        "card_formats": counts("card_format", VALID_CARD_FORMATS),
        "removed": removed,
        "flagged": [
            {"index": i, "id": it["id"], "chunk": it.get("chunk"), "flags": it["flags"],
             "q": it["q"], "a": it["a"], "slide_no": it["slide_no"],
             "card_type": it.get("card_type"), "card_format": it.get("card_format"),
             "importance": it.get("importance"), "exam_hit": it.get("exam_hit"),
             "source_type": it.get("source_type")}
            for i, it in enumerate(kept) if it["flags"]
        ],
        "near_duplicate_groups": find_near_duplicate_groups(kept),
        # ①⃝ 우선순위는 내려갔지만 **계속 센다.** 메우느라 시간을 크게 쓰지 않을 뿐이다.
        "coverage_gaps": coverage_gaps(plan, kept),
        "rejected_reasons": rejected_summary(plan),
        "hot_slides": hot_slides,
        "untouched_slides": untouched,
        "untouched_undeclared": [s for s in untouched if s not in declared],
        "review_notes": sum(1 for i in kept if _text(i.get("review_note"))),
        "occlusion": sum(1 for i in kept if i.get("occlusion")),
    }

    # 조각 파일에 대고 돌리면 출력도 조각 이름으로 낸다. 정식 이름으로 쓰면 병합본이
    # 조용히 덮인다 — v1 `260814_05`에서 조각이 자기 14장으로 덮은 적이 있다.
    suffix = ("" if items_name in CANONICAL_ITEMS
              else "." + Path(items_name).stem.replace("items.raw.", ""))
    (run_dir / f"items.checked{suffix}.json").write_text(
        json.dumps({"lecture_id": prep["lecture_id"], "items": kept},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / f"suspects{suffix}.json").write_text(
        json.dumps(suspects, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"kept": len(kept), "suspects": suspects, "suffix": suffix}


def main() -> int:
    parser = argparse.ArgumentParser(description="v2 기계 검증")
    parser.add_argument("run_dir", help="runs/<lecture_id>")
    parser.add_argument("--items", default="items.raw.json", help="검증할 파일명")
    args = parser.parse_args()

    # 조각 파일에 대고 돌리는 것은 진단이지 단계가 아니므로 계측에 넣지 않는다.
    if args.items in CANONICAL_ITEMS:
        with timings.stage(Path(args.run_dir), "3-validate", label=args.items):
            result = validate_run(Path(args.run_dir), args.items)
    else:
        result = validate_run(Path(args.run_dir), args.items)

    s = result["suspects"]
    b = s["budget"]
    flag_counts: dict[str, int] = {}
    for entry in s["flagged"]:
        for flag in entry["flags"]:
            name = flag.split("(")[0]
            flag_counts[name] = flag_counts.get(name, 0) + 1

    print(f"[validate2] 통과 {result['kept']}장 "
          f"(강의록 {s['sources']['lecture']} / 족보 {s['sources']['jokbo']})")
    print(f"  예산: 슬라이드 {b['slides']}×{b['per_slide']} = {b['target']}장 "
          f"→ 실제 {b['actual']}장 ({b['ratio']}배)")
    print(f"  중요도: core {s['importance']['core']} / detail {s['importance']['detail']}"
          f"  |  exam_hit {s['importance']['exam_hit']}")
    print("  형식: " + ", ".join(f"{k}={v}" for k, v in s["card_formats"].items() if v))
    print(f"  hard 제거: {len(s['removed'])}  (사유: "
          f"{', '.join(sorted({r for x in s['removed'] for r in x['reason']})) or '없음'})")
    print(f"  soft 플래그: {len(s['flagged'])}문항 / {sum(flag_counts.values())}건")
    for flag, n in sorted(flag_counts.items(), key=lambda kv: -kv[1]):
        print(f"      {flag:<32}{n:>4}")
    print(f"  자료 주의 {s['review_notes']}장 / 오클루전 {s['occlusion']}장")
    print(f"  유사 후보군: {len(s['near_duplicate_groups'])}개 "
          f"(조각 경계 {sum(1 for g in s['near_duplicate_groups'] if g['cross_chunk'])}개)")
    print(f"  회수 목표 누락: {len(s['coverage_gaps'])}개")
    print("  제외 기록: "
          + (", ".join(f"{k} {v}" for k, v in s["rejected_reasons"].items()) or "없음"))
    if s["hot_slides"]:
        print(f"  과출제 의심 슬라이드: {[h['slide_no'] for h in s['hot_slides']]}")
    print(f"  문항이 없는 슬라이드 {len(s['untouched_slides'])}장 "
          f"(그중 제외 기록에 없는 것 {len(s['untouched_undeclared'])}장): "
          f"{s['untouched_undeclared']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
