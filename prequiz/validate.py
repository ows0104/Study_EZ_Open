"""3단계: 모델이 만든 예습 문항을 기계적으로 검증한다.

    python prequiz/validate.py runs/250813_02

입력  pre_items.raw.json      (②문항 작성자의 출력)
출력  pre_items.checked.json  빌드 가능한 문항만
      pre_suspects.json       감사(③)가 판정해야 할 것 전부

원칙은 `quiz/validate.py`와 같다. 여기서 하는 일은 전부 결정론적이다.
'이 선지가 그럴듯한가', '이게 정말 핵심인가' 같은 의미 판단은 하지 않는다.
의심스러운 것을 모아 감사에게 넘길 뿐이므로 hard 제거는 기계적으로 명백한
것만 한다.

규칙 근거는 `.claude/skills/prequiz/references/preview-rules.md`다.
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

from quiz import timings  # noqa: E402
from quiz.textutil import norm_for_compare, tokens  # noqa: E402

# 3단계가 정식으로 도는 입력. 다른 파일에 대고 돌리는 것은 진단이지 단계가
# 아니므로 계측에 넣지 않는다 — 넣으면 벽시계가 호출 간격이 되어 버린다
# (`quiz/validate.py`가 그 사고를 한 번 겪었다).
CANONICAL_ITEMS = {"pre_items.raw.json", "pre_items.final.json"}

VALID_QTYPES = {"mcq", "short", "ox"}
VALID_FOCUS = {"must_know", "core", "context"}
VALID_SOURCE_TYPES = {"lecture", "jokbo"}
MCQ_CHOICE_COUNT = 5

# 길이 한도는 감사로 보내는 소프트 신호다 (preview-rules §5).
STEM_MAX_CHARS = {"mcq": 140, "short": 110, "ox": 120}
CHOICE_MAX_CHARS = 60
# 정답 선지가 나머지 평균보다 이 배수 이상이고, 동시에 이 글자 수 이상 길면
# 길이만 보고 찍힌다 (§7.3). 둘 다 요구해야 짧은 선지에서 오탐하지 않는다.
CHOICE_LENGTH_RATIO = 1.6
CHOICE_LENGTH_MIN_GAP = 12
SHORT_ANSWER_MAX_CHARS = 40
# 예습 문항은 틀렸을 때 '무엇을 다시 봐야 하는지'가 전부다. 해설이 한 줄이면
# 그 역할을 못 한다 (§8).
EXPLANATION_MIN_CHARS = 40
# 한 슬라이드에서 예습 문항을 여러 개 뽑는 건 정상이지만, 지나치면 예습
# 점검이 아니라 그 슬라이드 정독 시험이 된다 (§3).
SLIDE_CONCENTRATION_MAX = 3

# 원본을 눈앞에 두고 있어야만 풀리는 문항 (§6 자족성).
_SOURCE_REFERENCE_RE = re.compile(
    r"(위\s*(그림|표|도식|슬라이드|사진)|아래\s*(그림|표|도식)|다음\s*(그림|표|도식)"
    r"|이\s*(그림|표|도식|슬라이드|사진)|그림에서|표에서|도식(상|에서)"
    r"|슬라이드에\s*(따르면|나온|제시)|제시된\s*(그림|표|도식)"
    r"|(좌측|우측|왼쪽|오른쪽)\s*(그림|사진|표|도식|이미지))"
)
# 자료의 내용이 아니라 수업 운영·출제 경향 자체를 묻는 문항.
_META_QUESTION_RE = re.compile(
    r"(교수(님|가|는)|강의에서\s*(강조|언급)|시험에\s*(나온|출제)|출제\s*(경향|빈도)|족보에\s*(따르면|나온))"
)
# 부정형 발문. 예습 단계에서 특히 실수를 유발하므로 강조 표시를 요구한다 (§5.3).
_NEGATIVE_STEM_RE = re.compile(r"(아닌\s*것|옳지\s*않은|틀린\s*것|해당하지\s*않는|거리가\s*먼)")
# 강조 수단은 무엇이든 좋다. 부정어 주변이 아니라 발문 어딘가에 있으면 통과시킨다 -
# 위치까지 따지면 표기 습관마다 다르게 걸려 신호가 못 된다.
_EMPHASIS_RE = re.compile(r"(<b>|<strong>|\*\*|__|【|「|『|\[)")
# 소거법으로 풀리는 무성의 선지 (§7.2).
_LAZY_CHOICE_RE = re.compile(
    r"^(위의?\s*(모든|전부)|모두\s*(정답|해당)|정답\s*없음|해당\s*없음|모두\s*맞다|answer|all of)")
# OX는 판단할 진술문이어야 한다. 의문형이면 무엇에 O/X를 하라는 건지 모호하다.
_QUESTION_FORM_RE = re.compile(r"(무엇|어느|어떤|왜|몇|것은|인가\s*\?|\?)\s*$")


def _text(value) -> str:
    return str(value or "").strip()


def _choices(item: dict) -> list[str]:
    raw = item.get("choices") or []
    return [_text(c) for c in raw] if isinstance(raw, list) else []


def _answer_leak(stem: str, answer: str) -> bool:
    """정답의 유의미 토큰이 발문에 거의 다 노출된 경우."""
    a_tokens = tokens(answer)
    if len(a_tokens) < 2:
        return False
    q_tokens = tokens(stem)
    exposed = sum(1 for t in a_tokens if t in q_tokens)
    return exposed / len(a_tokens) >= 0.9


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def item_text(item: dict) -> str:
    """중복·커버리지 비교에 쓰는 문항 전체 텍스트."""
    return " ".join([_text(item.get("stem")), " ".join(_choices(item)),
                     _text(item.get("answer"))])


def check_item(item: dict, max_slide: int, jokbo_range: list | None = None) -> tuple[list[str], list[str]]:
    """한 문항의 (hard, soft) 문제 목록. hard가 있으면 빌드 불가."""
    hard: list[str] = []
    soft: list[str] = []

    qtype = _text(item.get("qtype")).lower()
    if qtype not in VALID_QTYPES:
        hard.append(f"unknown_qtype({qtype or '없음'})")
        qtype = "short"

    stem = _text(item.get("stem"))
    answer = _text(item.get("answer"))
    choices = _choices(item)
    if not stem:
        hard.append("empty_stem")
    if not answer:
        hard.append("empty_answer")

    # slide_no: 이미지가 붙는 유일한 근거. 틀리면 엉뚱한 슬라이드가 카드에 박힌다.
    try:
        slide_no = int(item.get("slide_no"))
    except (TypeError, ValueError):
        hard.append("slide_no_missing")
        slide_no = None
    # 경계는 **자료의 범위**(`total_slides`)다. `num_pages`(강의록 PDF 쪽수)로 자르면
    # 외부 족보를 붙인 편에서 정상 카드가 hard 제거된다. quiz 쪽에서 실제로 났다 -
    # `260814_05`는 `num_pages` 49에 외부 족보가 슬라이드 50-51이라 카드 4장이 걸렸다.
    # prequiz는 자기 prep이 없고 `quiz/prep.py`가 만든 `prep.json`을 읽으므로 같은 조건을
    # 그대로 만난다.
    if slide_no is not None and not (1 <= slide_no <= max_slide):
        hard.append(f"slide_no_out_of_range({slide_no}/1-{max_slide})")
    # 족보 구간에서도 출제한다. 다만 '강의의 중심 흐름에 있는가'는 의미 판단이라
    # 코드가 못 한다 (§2). 여기서는 출처가 실제 구간과 맞는지만 보고, 중심 흐름
    # 여부는 감사로 넘긴다.
    source_type = _text(item.get("source_type")).lower() or "lecture"
    if source_type not in VALID_SOURCE_TYPES:
        soft.append(f"unknown_source_type({source_type})")
        source_type = "lecture"
    if jokbo_range and slide_no is not None and 1 <= slide_no <= max_slide:
        in_jokbo = int(jokbo_range[0]) <= slide_no <= int(jokbo_range[1])
        if in_jokbo and source_type != "jokbo":
            soft.append(f"source_type_range_mismatch(slide {slide_no}는 족보 구간)")
        elif not in_jokbo and source_type == "jokbo":
            soft.append(f"source_type_range_mismatch(slide {slide_no}는 강의록 구간)")
        # 족보 문항은 중심 흐름일 때만 낸다. context는 '알면 매끄러운' 수준이라
        # 그 조건과 정면으로 어긋나므로 감사가 직접 보게 한다.
        if in_jokbo and _text(item.get("focus")).lower() == "context":
            soft.append("jokbo_item_is_context")

    # 유형별 형식. 여기가 틀리면 카드가 아예 풀 수 없는 형태로 나간다.
    if qtype == "mcq":
        if len(choices) != MCQ_CHOICE_COUNT:
            hard.append(f"mcq_choice_count({len(choices)}/{MCQ_CHOICE_COUNT})")
        if any(not c for c in choices):
            hard.append("mcq_empty_choice")
        normalized = [norm_for_compare(c) for c in choices if c]
        if len(set(normalized)) != len(normalized):
            hard.append("mcq_duplicate_choice")
        try:
            index = int(answer)
        except (TypeError, ValueError):
            hard.append(f"mcq_answer_not_index({answer!r})")
            index = None
        if index is not None and not (1 <= index <= len(choices)):
            hard.append(f"mcq_answer_out_of_range({index}/1-{len(choices)})")

        for choice in choices:
            if _LAZY_CHOICE_RE.match(norm_for_compare(choice) or choice):
                soft.append("lazy_distractor")
                break
        if any(len(c) > CHOICE_MAX_CHARS for c in choices):
            soft.append(f"choice_too_long(>{CHOICE_MAX_CHARS})")
        # 정답 선지만 유독 길면 내용을 몰라도 길이로 찍힌다 (§7.3).
        # 비율만 보면 한글 단답형 선지에서 두세 글자 차이로 걸린다. 눈에 띌 만한
        # 절대 격차(CHOICE_LENGTH_MIN_GAP)를 함께 요구한다.
        if index is not None and 1 <= index <= len(choices) and len(choices) > 1:
            lengths = [len(c) for c in choices]
            correct_len = lengths[index - 1]
            others = [n for i, n in enumerate(lengths) if i != index - 1]
            average = sum(others) / len(others)
            if (correct_len == max(lengths)
                    and correct_len >= CHOICE_LENGTH_RATIO * average
                    and correct_len - average >= CHOICE_LENGTH_MIN_GAP):
                soft.append("longest_choice_is_answer")
    elif qtype == "ox":
        if answer.upper() not in {"O", "X"}:
            hard.append(f"ox_answer_not_o_or_x({answer!r})")
        if choices:
            soft.append("ox_has_choices")
        if _QUESTION_FORM_RE.search(stem):
            # OX는 참·거짓을 판정할 진술문이어야 한다 (§5.4).
            soft.append("ox_not_statement")
    else:  # short
        if choices:
            soft.append("short_has_choices")
        if len(answer) > SHORT_ANSWER_MAX_CHARS:
            soft.append(f"short_answer_too_long({len(answer)}>{SHORT_ANSWER_MAX_CHARS})")
        if stem and answer and _answer_leak(stem, answer):
            soft.append("answer_leak")

    limit = STEM_MAX_CHARS.get(qtype, 120)
    if len(stem) > limit:
        soft.append(f"stem_too_long({len(stem)}>{limit})")
    if _SOURCE_REFERENCE_RE.search(stem):
        soft.append("source_reference")
    if _META_QUESTION_RE.search(stem):
        soft.append("meta_question")
    if _NEGATIVE_STEM_RE.search(stem) and not _EMPHASIS_RE.search(stem):
        soft.append("negative_stem_unmarked")

    explanation = _text(item.get("explanation"))
    if not explanation:
        soft.append("no_explanation")
    elif len(explanation) < EXPLANATION_MIN_CHARS:
        # 예습 문항은 틀렸을 때 어디를 다시 보라고 알려주는 게 본체다.
        soft.append(f"thin_explanation({len(explanation)}<{EXPLANATION_MIN_CHARS})")

    if len(_text(item.get("source_anchor"))) < 6:
        soft.append("weak_source_anchor")

    focus = _text(item.get("focus")).lower()
    if not focus:
        soft.append("no_focus")
    elif focus not in VALID_FOCUS:
        soft.append(f"unknown_focus({focus})")

    if not _text(item.get("retrieval_target")):
        soft.append("no_retrieval_target")
    return hard, soft


def find_exact_duplicates(items: list[dict]) -> list[int]:
    """완전 중복의 '뒤에 나온 쪽' 인덱스. 이것만 기계적으로 제거한다."""
    seen: dict[str, int] = {}
    drop: list[int] = []
    for idx, item in enumerate(items):
        key = norm_for_compare(item.get("stem", "")) + "||" + norm_for_compare(str(item.get("answer", "")))
        if key in seen:
            drop.append(idx)
        else:
            seen[key] = idx
    return drop


def find_near_duplicate_groups(items: list[dict], threshold: float = 0.70) -> list[dict]:
    """유사 후보만 묶어 감사에게 넘긴다. 여기서 제거하지 않는다.

    예습 문항 수는 적으므로(§3) 같은 지점을 두 번 묻는 것이 시험 대비 덱보다
    훨씬 비싸다. 그래도 '같은 개념의 다른 각도'인지는 기계가 못 가리므로
    후보 묶기까지만 한다.
    """
    groups: list[dict] = []
    used: set[int] = set()
    sigs = [tokens(item_text(it)) for it in items]
    for i in range(len(items)):
        if i in used:
            continue
        members = [i]
        for j in range(i + 1, len(items)):
            if j in used:
                continue
            if _jaccard(sigs[i], sigs[j]) >= threshold:
                members.append(j)
        if len(members) > 1:
            used.update(members)
            groups.append({
                "indices": members,
                "similarity": round(max(_jaccard(sigs[members[0]], sigs[m]) for m in members[1:]), 3),
                "items": [{
                    "index": m, "id": items[m].get("id"), "qtype": items[m].get("qtype"),
                    "stem": items[m].get("stem"), "answer": items[m].get("answer"),
                    "slide_no": items[m].get("slide_no"),
                    "retrieval_target": items[m].get("retrieval_target"),
                } for m in members],
            })
    return groups


def coverage_gaps(blueprint: dict | None, items: list[dict], threshold: float = 0.55) -> list[dict]:
    """청사진의 예습 확인 지점 중 어떤 문항도 회수하지 않는 것.

    문자열 완전 일치로 보면 안 된다. 모델은 target을 합치거나 표현을 바꿔서
    문항을 만들기 때문에 정규화 토큰 겹침으로 본다. 애매하면 누락으로
    보고하지 않는다 (검토 피로가 이 단계를 무력화시킨다).
    """
    if not blueprint:
        return []
    covered = [
        tokens(" ".join([_text(it.get("retrieval_target")), item_text(it),
                         _text(it.get("explanation"))]))
        for it in items
    ]
    gaps = []
    for objective in blueprint.get("objectives", []):
        for entry in objective.get("check_points", []):
            if isinstance(entry, dict):
                target = entry.get("target")
                meta = {"focus": entry.get("focus"), "exam_hit": entry.get("exam_hit")}
            else:
                target, meta = entry, {}
            target_tokens = tokens(str(target))
            if not target_tokens:
                continue
            best = max((len(target_tokens & c) / len(target_tokens) for c in covered), default=0.0)
            if best < threshold:
                gaps.append({
                    "objective_id": objective.get("id"),
                    "objective": objective.get("objective"),
                    "target": target,
                    **meta,
                    "best_overlap": round(best, 2),
                    "slides": objective.get("slides"),
                })
    return gaps


def answer_position_bias(items: list[dict]) -> dict | None:
    """객관식 정답 번호가 한쪽에 몰렸는가.

    사람이 만들면 ③에 몰리고 모델이 만들면 ①·②에 몰린다. 내용을 몰라도
    찍히므로 예습 점검으로서 무의미해진다 (§7.4).
    """
    positions: dict[int, int] = {}
    for item in items:
        if _text(item.get("qtype")).lower() != "mcq":
            continue
        try:
            positions[int(item["answer"])] = positions.get(int(item["answer"]), 0) + 1
        except (KeyError, TypeError, ValueError):
            continue
    total = sum(positions.values())
    if total < 8:
        return None
    top, count = max(positions.items(), key=lambda kv: kv[1])
    if count / total <= 0.40:
        return None
    return {"total_mcq": total, "distribution": dict(sorted(positions.items())),
            "dominant": top, "share": round(count / total, 2)}


def ox_balance(items: list[dict]) -> dict | None:
    """OX의 참·거짓이 한쪽으로 몰렸는가.

    `answer_position_bias`의 형제다. 저쪽이 "다 ③으로 찍으면 몇 개 맞나"를 재고
    이쪽은 "다 X로 찍으면 몇 개 맞나"를 잰다. 몰려 있으면 내용을 몰라도 찍히므로
    예습 점검으로서 무의미해진다 (§5.4가 "참·거짓을 반반 가깝게"라고 적은 자리다).

    **세 편에서 재현돼서 넣었다.** 감사가 매번 손으로 맞추고 있었는데 기계가
    가리켜 주지 않아 감사의 눈에 걸리는지에 달려 있었다.

        250820_02   X 6 : O 2 (75%)  → 감사가 4:4로
        250820_03   X 4 : O 1 (80%)  → 감사가 3:2로
        250820_05   쏠림           → 감사가 4:4로

    문턱은 `answer_position_bias`와 다르다. 선지가 다섯인 객관식은 0.40이 기준이
    되지만 OX는 둘뿐이라 0.50이 우연의 자리다. **0.70을 넘을 때만 부른다** —
    4문항에서 3:1(0.75)이면 부르고 2:1(0.67)이면 안 부른다.

    최소 개수도 다르다. 객관식은 8개를 요구하는데 OX는 한 편에 4~8개라 그 문턱을
    쓰면 영영 안 울린다. **4개부터 본다.**
    """
    counts: dict[str, int] = {}
    for item in items:
        if _text(item.get("qtype")).lower() != "ox":
            continue
        answer = _text(item.get("answer")).strip().upper()
        # O/X 말고 다른 표기로 적혀 온 것은 세지 않는다. 그건 스키마 문제라
        # 다른 검사가 잡는다 — 여기서 같이 세면 쏠림이 흐려진다.
        if answer in ("O", "X"):
            counts[answer] = counts.get(answer, 0) + 1
    total = sum(counts.values())
    if total < 4:
        return None
    top, count = max(counts.items(), key=lambda kv: kv[1])
    if count / total <= 0.70:
        return None
    return {"total_ox": total, "distribution": {"O": counts.get("O", 0), "X": counts.get("X", 0)},
            "dominant": top, "share": round(count / total, 2)}


def validate_items(items: list[dict], max_slide: int,
                   jokbo_range: list | None = None) -> tuple[list[dict], list[dict]]:
    """(빌드 가능한 문항, 제거된 문항). 제거된 문항은 원문을 통째로 보존한다."""
    kept: list[dict] = []
    removed: list[dict] = []
    for idx, raw in enumerate(items):
        item = dict(raw)
        item.setdefault("id", f"p{idx + 1:03d}")
        if item.get("answer") is not None:
            item["answer"] = str(item["answer"]).strip()
        hard, soft = check_item(item, max_slide, jokbo_range)
        item["flags"] = soft
        if hard:
            removed.append({"reason": hard, "item": item})
        else:
            kept.append(item)

    for idx in sorted(find_exact_duplicates(kept), reverse=True):
        removed.append({"reason": ["exact_duplicate"], "item": kept.pop(idx)})
    return kept, removed


def validate_run(run_dir: Path, items_name: str = "pre_items.raw.json") -> dict:
    from quiz.validate import authoritative_ranges

    run_dir = Path(run_dir)
    prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))
    num_pages = int(prep["num_pages"])
    # 자료의 범위와 강의록 PDF 쪽수는 다르다. 외부 족보를 붙이면 슬라이드 번호가
    # 필기 뒤로 이어져 `total_slides`가 커진다.
    max_slide = int(prep.get("total_slides") or num_pages)
    # 구간의 주인은 structure.json(모델)이고 prep.json은 힌트다. 이걸 안 지키면
    # 멀쩡한 족보 문항이 source_type_range_mismatch로 걸린다.
    lecture_range, jokbo_range, range_source = authoritative_ranges(run_dir, prep)

    payload = json.loads((run_dir / items_name).read_text(encoding="utf-8"))
    items = payload["items"] if isinstance(payload, dict) else payload

    blueprint_path = run_dir / "pre_blueprint.json"
    blueprint = json.loads(blueprint_path.read_text(encoding="utf-8")) if blueprint_path.exists() else None

    kept, removed = validate_items(items, max_slide, jokbo_range)

    slide_counts: dict[int, int] = {}
    for item in kept:
        slide_counts[int(item["slide_no"])] = slide_counts.get(int(item["slide_no"]), 0) + 1
    hot_slides = [{"slide_no": s, "count": c} for s, c in sorted(slide_counts.items())
                  if c > SLIDE_CONCENTRATION_MAX]

    # 커버리지는 강의록 구간에서만 본다. 족보 구간은 강의의 중심 흐름과 겹칠 때만
    # 출제하므로 '안 다룬 족보 슬라이드'는 누락이 아니다 (§2).
    lecture_lo, lecture_hi = lecture_range or [1, num_pages]
    skip = set(blueprint.get("skip_slides", []) if blueprint else [])
    untouched = [s for s in range(int(lecture_lo), int(lecture_hi) + 1)
                 if s not in slide_counts and s not in skip]

    qtypes = {q: sum(1 for i in kept if _text(i.get("qtype")).lower() == q)
              for q in sorted(VALID_QTYPES)}
    focus_counts = {f: sum(1 for i in kept if _text(i.get("focus")).lower() == f)
                    for f in ("must_know", "core", "context")}
    sources = {s: sum(1 for i in kept if (_text(i.get("source_type")).lower() or "lecture") == s)
               for s in ("lecture", "jokbo")}

    suspects = {
        "lecture_id": prep["lecture_id"],
        "num_pages": num_pages,
        "lecture_range": lecture_range,
        "jokbo_range": jokbo_range,
        "range_source": range_source,
        "item_count": len(kept),
        "qtypes": qtypes,
        "focus": focus_counts,
        "sources": sources,
        "exam_hit": sum(1 for i in kept if i.get("exam_hit")),
        "removed": removed,
        "flagged": [
            {"index": i, "id": it["id"], "flags": it["flags"], "qtype": it.get("qtype"),
             "stem": it["stem"], "choices": it.get("choices"), "answer": it.get("answer"),
             "slide_no": it["slide_no"], "focus": it.get("focus"),
             "source_type": it.get("source_type")}
            for i, it in enumerate(kept) if it["flags"]
        ],
        "near_duplicate_groups": find_near_duplicate_groups(kept),
        "coverage_gaps": coverage_gaps(blueprint, kept),
        "answer_position_bias": answer_position_bias(kept),
        "ox_balance": ox_balance(kept),
        "hot_slides": hot_slides,
        "untouched_slides": untouched,
    }

    # `pre_items.checked.json`은 **2단계 결과를 거른 것**이다. 확정본을 검증할 때는
    # 쓰지 않는다 — 그러면 `prequiz/apply_audit.py`가 패치를 얹을 base가 감사
    # **이후** 내용으로 덮인다. 실제로 그렇게 덮인 파일을 한 번 봤고, 그 상태로
    # apply를 다시 부르면 `add`가 두 번 들어간다.
    #
    # `pre_suspects.json`은 반대로 **언제나 갱신한다.** `studyez.gate`가 "확정본
    # 검증에서 hard 제거가 났나"를 그 파일로 보기 때문이다.
    if items_name != "pre_items.final.json":
        (run_dir / "pre_items.checked.json").write_text(
            json.dumps({"lecture_id": prep["lecture_id"], "items": kept},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")
    (run_dir / "pre_suspects.json").write_text(
        json.dumps(suspects, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"kept": len(kept), "suspects": suspects}


def main() -> int:
    parser = argparse.ArgumentParser(description="예습퀴즈 파이프라인 3단계: 기계 검증")
    parser.add_argument("run_dir", help="runs/<lecture_id>")
    parser.add_argument("--items", default="pre_items.raw.json", help="검증할 파일명")
    args = parser.parse_args()

    if args.items in CANONICAL_ITEMS:
        with timings.stage(Path(args.run_dir), "3-validate", label=args.items):
            result = validate_run(Path(args.run_dir), args.items)
    else:
        result = validate_run(Path(args.run_dir), args.items)
    s = result["suspects"]
    q, f, src = s["qtypes"], s["focus"], s["sources"]
    print(f"[pre-validate] 통과 {result['kept']}문항 "
          f"(객관식 {q['mcq']} / 단답 {q['short']} / OX {q['ox']})")
    print(f"  예습 비중: must_know {f['must_know']} / core {f['core']} / context {f['context']}"
          f"  |  출처: 강의록 {src['lecture']} / 족보 {src['jokbo']}"
          f"  |  족보가 물었던 지점 {s['exam_hit']}")
    print(f"  hard 제거: {len(s['removed'])}  (사유별: "
          f"{', '.join(sorted({r.split('(')[0] for x in s['removed'] for r in x['reason']})) or '없음'})")
    mismatch = sum(1 for x in s["flagged"]
                   if any(r.startswith("source_type_range_mismatch") for r in x["flags"]))
    if mismatch:
        print(f"  ! source_type이 실제 구간과 어긋난 문항 {mismatch}개. 대량이면 문항이 아니라"
              " 족보 경계가 틀린 것이니 quiz/prep.py --jokbo-start 부터 다시 잡으세요.")
    print(f"  soft 플래그: {len(s['flagged'])}문항")
    print(f"  유사 후보군: {len(s['near_duplicate_groups'])}개")
    print(f"  커버리지 누락: {len(s['coverage_gaps'])}개")
    if s["answer_position_bias"]:
        b = s["answer_position_bias"]
        print(f"  ! 정답 번호 편중: {b['dominant']}번이 {int(b['share'] * 100)}% ({b['distribution']})")
    if s["ox_balance"]:
        b = s["ox_balance"]
        print(f"  ! OX 쏠림: {b['dominant']}가 {int(b['share'] * 100)}% "
              f"(O {b['distribution']['O']} : X {b['distribution']['X']}) — "
              f"다 {b['dominant']}로 찍으면 {b['distribution'][b['dominant']]}개를 맞는다")
    if s["hot_slides"]:
        print(f"  과출제 의심 슬라이드: {[h['slide_no'] for h in s['hot_slides']]}")
    print(f"  문항이 없는 강의록 슬라이드 {len(s['untouched_slides'])}장: {s['untouched_slides']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
