"""3단계: 모델이 만든 카드를 기계적으로 검증한다.

    python quiz/validate.py runs/250813_02

입력  items.raw.json      (②카드 작성자의 출력)
출력  items.checked.json  빌드 가능한 카드만
      suspects.json       감사(③)가 판정해야 할 것 전부

원칙: 여기서 하는 일은 전부 결정론적이다. '이 카드가 자족적인가', '이 둘이
같은 걸 묻는가' 같은 의미 판단은 하지 않는다. 의심스러운 것을 모아 감사에게
넘길 뿐이므로, hard 제거는 기계적으로 명백한 것만 한다.

규칙 근거는 `.claude/skills/quiz/references/item-rules.md`다. 절 번호를 인용한
주석은 그 문서를 고칠 때 함께 확인할 것.
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

VALID_CARD_TYPES = {"fact", "comparison", "mechanism", "trap", "list", "sequence", "cloze"}
VALID_IMPORTANCE = {"core", "detail"}
VALID_SOURCE_TYPES = {"lecture", "jokbo"}
VALID_REVIEW_FLAGS = {"answer_mismatch", "question_error", "uncertain"}
# 족보 문항은 question_text를, 강의록은 나머지를 쓴다.
VALID_EVIDENCE_TYPES = {
    "lecture": {"lecture_text", "table", "figure"},
    "jokbo": {"question_text", "table", "figure"},
}

# 길이 한도는 감사로 보내는 소프트 신호다 (item-rules §10 질문, §11 정답).
# 한도가 실제 분포보다 헐거우면 아무것도 걸리지 않으므로 규칙에 맞춰 조인다.
Q_MAX_CHARS = 110
# 족보 임상 vignette은 나이·증상·검사소견을 담아야 해서 강의록 카드보다 길다.
# 압축하라는 요구(§4.2)는 유지하되 한도는 따로 둔다.
Q_MAX_CHARS_JOKBO = 160
A_MAX_CHARS = 110
# fact/cloze는 명사구 하나가 답이므로 더 짧아야 한다.
A_MAX_CHARS_ATOMIC = 50
ATOMIC_TYPES = {"fact", "cloze"}
CLOZE_MAX_BLANKS = 2
# 정보량이 많은 슬라이드는 5~6장, 그 이상도 내는 것이 맞다(§2). 몰림 자체는 문제가
# 아니므로 한도를 넉넉히 두고, 넘을 때만 쪼개기가 잘못됐는지 감사에게 알린다.
SLIDE_CONCENTRATION_MAX = 8

# 원본을 눈앞에 두고 있어야만 풀리는 카드. Anki에서는 앞면만 보인다 (§6 자족성).
_SOURCE_REFERENCE_RE = re.compile(
    r"(위\s*(그림|표|도식|슬라이드|사진)|아래\s*(그림|표|도식)|다음\s*(그림|표|도식)"
    r"|이\s*(그림|표|도식|슬라이드|사진)|그림에서|표에서|도식(상|에서)|슬라이드에\s*(따르면|나온|제시)"
    # 좌측·우측은 뒤에 그림·사진이 올 때만 잡는다. 임상 vignette의 "우측 하복부"처럼
    # 해부학적 방향을 가리키는 쪽이 훨씬 흔하다.
    r"|제시된\s*(그림|표|도식)|(좌측|우측|왼쪽|오른쪽)\s*(그림|사진|표|도식|이미지))"
)
# 자료의 내용이 아니라 수업 운영·출제 경향 자체를 묻는 카드. 어느 슬라이드에서도
# 확인되지 않으므로 §1의 unsupported에 해당한다.
_META_QUESTION_RE = re.compile(
    r"(교수(님|가|는)|강의에서\s*(강조|언급)|시험에\s*(나온|출제)|출제\s*(경향|빈도)|족보에\s*(따르면|나온))"
)
_YES_NO_RE = re.compile(r"^(예|아니오|아니요|맞다|틀리다|yes|no|true|false|o|x)[.!]?$", re.I)
# "A 세 가지는 무엇이며, 그중 B는 무엇인가" - 두 개의 회상을 한 카드에 욱여넣은 형태.
# §7이 금지하는 대표 패턴이고, 답이 길어지는 가장 흔한 경로다.
_COMPOUND_Q_RE = re.compile(r"(이며|이고|무엇이며|무엇이고|하며|각각\s*(어떤|무엇))")
# 답이 완결된 서술문으로 끝나는 경우. 명사구여야 할 자리에 문장이 들어왔다는 신호(§11).
_PREDICATE_END_RE = re.compile(r"(된다|한다|이다|있다|없다|진다|난다|시킨다|킨다)[.]?$")


def _text(value) -> str:
    return str(value or "").strip()


def _answer_leak(q: str, a: str) -> bool:
    """정답의 유의미 토큰이 질문에 거의 다 노출된 경우."""
    a_tokens = tokens(a)
    if len(a_tokens) < 2:
        return False
    q_tokens = tokens(q)
    exposed = sum(1 for t in a_tokens if t in q_tokens)
    return exposed / len(a_tokens) >= 0.9


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def check_item(item: dict, num_pages: int, jokbo_range: list | None = None,
               label_index: dict | None = None) -> tuple[list[str], list[str]]:
    """한 카드의 (hard, soft) 문제 목록. hard가 있으면 빌드 불가.

    jokbo_range를 주면 source_type과 slide_no가 서로 맞는지도 본다.
    label_index를 주면 오클루전 카드가 가리키는 라벨이 실재하는지도 본다.
    """
    hard: list[str] = []
    soft: list[str] = []
    source_type = _text(item.get("source_type")).lower() or "lecture"
    # 키가 있으면 검사한다. 빈 dict를 "오클루전 아님"으로 넘기면 모델이 그림
    # 카드로 만들려던 것이 조용히 텍스트 카드가 되어 나간다.
    occlusion = item["occlusion"] if item.get("occlusion") is not None else None

    q = _text(item.get("q"))
    a = _text(item.get("a"))
    if not q:
        hard.append("empty_question")
    if not a:
        hard.append("empty_answer")
    if q and a and norm_for_compare(q) == norm_for_compare(a):
        hard.append("question_equals_answer")

    # slide_no: 이미지가 붙는 유일한 근거. 틀리면 엉뚱한 슬라이드가 카드에 박힌다.
    raw_slide = item.get("slide_no")
    try:
        slide_no = int(raw_slide)
    except (TypeError, ValueError):
        hard.append("slide_no_missing")
        slide_no = None
    if slide_no is not None and not (1 <= slide_no <= num_pages):
        hard.append(f"slide_no_out_of_range({slide_no}/1-{num_pages})")

    # 족보 구간 슬라이드를 근거로 삼았는데 lecture라고 적혔거나 그 반대인 경우.
    # 구간을 잘못 읽었다는 뜻이고, 그러면 grounding 채널 자체가 어긋난다.
    if jokbo_range and slide_no is not None and 1 <= slide_no <= num_pages:
        in_jokbo = int(jokbo_range[0]) <= slide_no <= int(jokbo_range[1])
        if in_jokbo and source_type != "jokbo":
            soft.append(f"source_type_range_mismatch(slide {slide_no}는 족보 구간)")
        elif not in_jokbo and source_type == "jokbo":
            soft.append(f"source_type_range_mismatch(slide {slide_no}는 강의록 구간)")

    # cloze
    if cloze_has_malformed_markup(q) and not valid_cloze_text(q):
        hard.append("cloze_malformed")
    if has_cloze_markup(a):
        soft.append("cloze_in_answer")
    if has_cloze_markup(q):
        if q.rstrip().endswith("?"):
            soft.append("cloze_question_form")
        if not valid_cloze_text(q):
            hard.append("cloze_empty")
        # 빈칸이 셋 이상이면 문장 대부분이 가려져 회상이 아니라 재구성 과제가 된다.
        # c1으로 통일돼 있으므로 Anki에서도 한 번에 전부 가려진다.
        blanks = len(cloze_matches(q))
        if blanks > CLOZE_MAX_BLANKS:
            soft.append(f"cloze_too_many_blanks({blanks})")

    # 오클루전 카드는 앞면에 그림이 뜨므로 §6 자족성의 유일한 예외다.
    # "가려진 A는?"처럼 그림을 가리키는 표현이 정상이라 소스 참조를 잡지 않는다.
    if not occlusion and _SOURCE_REFERENCE_RE.search(q):
        soft.append("source_reference")
    if _META_QUESTION_RE.search(q):
        soft.append("meta_question")
    if q and a and _answer_leak(q, a):
        soft.append("answer_leak")
    q_limit = Q_MAX_CHARS_JOKBO if source_type == "jokbo" else Q_MAX_CHARS
    if len(q) > q_limit:
        soft.append(f"question_too_long({len(q)}>{q_limit})")
    if _COMPOUND_Q_RE.search(q) or q.count("?") > 1:
        soft.append("compound_question")

    card_type_raw = _text(item.get("card_type")).lower()
    atomic = card_type_raw in ATOMIC_TYPES
    limit = A_MAX_CHARS_ATOMIC if atomic else A_MAX_CHARS
    if len(a) > limit:
        soft.append(f"answer_too_long({len(a)}>{limit})")
    if atomic and _PREDICATE_END_RE.search(a):
        # fact/cloze의 답은 명사구여야 한다. 서술문이면 부연이 답에 섞여 있다.
        soft.append("answer_is_sentence")
    if _YES_NO_RE.match(a):
        soft.append("yes_no_answer")

    # §12: 왜 그 답인지 한두 문장. 없으면 틀렸을 때 카드가 아무것도 알려주지 않는다.
    if not _text(item.get("explanation")):
        soft.append("no_explanation")
    if len(_text(item.get("source_anchor"))) < 6:
        soft.append("weak_source_anchor")

    if card_type_raw and card_type_raw not in VALID_CARD_TYPES:
        soft.append(f"unknown_card_type({card_type_raw})")
    importance = _text(item.get("importance")).lower()
    if not importance:
        soft.append("no_importance")
    elif importance not in VALID_IMPORTANCE:
        soft.append(f"unknown_importance({importance})")

    if source_type not in VALID_SOURCE_TYPES:
        soft.append(f"unknown_source_type({source_type})")
        source_type = "lecture"
    evidence_type = _text(item.get("evidence_type")).lower()
    if evidence_type and evidence_type not in VALID_EVIDENCE_TYPES[source_type]:
        soft.append(f"evidence_type_mismatch({evidence_type}/{source_type})")

    # exam_hit은 '강의록 내용인데 족보가 물었다'는 표시다. 족보 구간 카드는
    # source_type으로 이미 구분되므로 붙이지 않는다.
    if item.get("exam_hit") and source_type == "jokbo":
        soft.append("exam_hit_on_jokbo")

    flags = item.get("review_flags") or []
    if flags and source_type != "jokbo":
        # 정오 검토는 족보에만 해당한다. 강의록에 붙었다면 외부 지식이 새어든 신호다.
        soft.append("review_flag_on_lecture")
    if any(f not in VALID_REVIEW_FLAGS for f in flags):
        soft.append("unknown_review_flag")
    if flags and not _text(item.get("review_note")):
        soft.append("review_flag_without_note")

    if not _text(item.get("retrieval_target")):
        soft.append("no_retrieval_target")

    # 함정: 족보 오답 선지는 다음 시험의 정답 후보다(§4.2). trap 카드에 이게
    # 없으면 무엇과 헷갈리는지가 카드에 안 남는다.
    if _text(item.get("trap_note")) and len(_text(item.get("trap_note"))) > 200:
        soft.append("trap_note_too_long")
    if card_type_raw == "trap" and not _text(item.get("trap_note")):
        soft.append("no_trap_note")

    if occlusion is not None:
        if not isinstance(occlusion, dict):
            hard.append("occlusion_not_object")
        else:
            _, problems = resolve_rects(occlusion, slide_no or 0, label_index or {})
            if label_index is None:
                # 라벨 목록 없이 부를 때(build의 재검사 등)는 id 실재 여부를 알 수
                # 없으므로 좌표 형식만 본다. 실제 확인은 render_occlusion_media가 한다.
                problems = [p for p in problems if not p.startswith("unknown_label_id")]
                if occlusion.get("label_ids"):
                    problems = [p for p in problems if p != "occlusion_empty"]
            hard.extend(problems)
            if len(occlusion.get("label_ids") or []) + len(occlusion.get("rects") or []) > 6:
                # 상자가 일곱 개면 한 카드에서 일곱 개를 회상해야 한다(§7 위반).
                soft.append("occlusion_too_many_boxes")
            if source_type == "jokbo":
                soft.append("occlusion_on_jokbo")
    return hard, soft


def find_exact_duplicates(items: list[dict]) -> list[int]:
    """완전 중복의 '뒤에 나온 쪽' 인덱스. 이것만 기계적으로 제거한다."""
    seen: dict[str, int] = {}
    drop: list[int] = []
    for idx, item in enumerate(items):
        key = norm_for_compare(item.get("q", "")) + "||" + norm_for_compare(item.get("a", ""))
        if key in seen:
            drop.append(idx)
        else:
            seen[key] = idx
    return drop


def find_near_duplicate_groups(items: list[dict], threshold: float = 0.70) -> list[dict]:
    """유사 후보만 묶어서 감사에게 넘긴다. 여기서 제거하지 않는다.

    같은 개념을 다른 회상 방향으로 묻는 문항은 둘 다 살아남아야 하는데, 그
    판단은 기계가 못 한다. 후보 blocking까지가 코드의 몫이다.
    """
    groups: list[dict] = []
    used: set[int] = set()
    sigs = [tokens(f"{it.get('q','')} {it.get('a','')}") for it in items]
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
                "similarity": round(max(_jaccard(sigs[members[0]], sigs[m]) for m in members[1:]), 3),
                "items": [{
                    "index": m,
                    "id": items[m].get("id"),
                    "q": items[m].get("q"),
                    "a": items[m].get("a"),
                    "slide_no": items[m].get("slide_no"),
                    "card_type": items[m].get("card_type"),
                    "retrieval_target": items[m].get("retrieval_target"),
                } for m in members],
            })
    return groups


def coverage_gaps(blueprint: dict | None, items: list[dict], threshold: float = 0.55) -> list[dict]:
    """청사진의 retrieval target 중 어떤 문항도 회수하지 않는 것.

    문자열 완전 일치로 보면 안 된다. 모델은 target을 합치거나 표현을 바꿔서
    문항을 만들기 때문에, 정규화 토큰 겹침으로 본다. 애매하면 누락으로
    보고하지 않는다 (검토 피로가 이 단계를 무력화시킨다).
    """
    if not blueprint:
        return []
    covered_texts = [
        tokens(" ".join([
            str(it.get("retrieval_target", "")), str(it.get("q", "")),
            str(it.get("a", "")), str(it.get("explanation", "")),
        ]))
        for it in items
    ]
    gaps = []
    for objective in blueprint.get("objectives", []):
        for entry in objective.get("retrieval_targets", []):
            # 스키마상 {target, importance, exam_hit} 객체지만, 문자열로 온 것도 받아준다.
            if isinstance(entry, dict):
                target = entry.get("target")
                meta = {"importance": entry.get("importance"), "exam_hit": entry.get("exam_hit")}
            else:
                target, meta = entry, {}
            target_tokens = tokens(str(target))
            if not target_tokens:
                continue
            best = max(
                (len(target_tokens & c) / len(target_tokens) for c in covered_texts),
                default=0.0,
            )
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


def validate_items(items: list[dict], num_pages: int, jokbo_range: list | None = None,
                   label_index: dict | None = None) -> tuple[list[dict], list[dict]]:
    """(빌드 가능한 카드, 제거된 카드). 제거된 카드는 원문을 통째로 보존한다.

    보존이 중요한 이유: 커버리지 검수에서 '이 target을 회수하던 카드가
    사라졌다'가 확인되면 새로 만들지 않고 원문을 복원하는 게 안전하다.
    """
    kept: list[dict] = []
    removed: list[dict] = []
    for idx, raw in enumerate(items):
        item = dict(raw)
        item.setdefault("id", f"q{idx + 1:03d}")
        if item.get("q"):
            item["q"] = normalize_cloze_to_c1(str(item["q"]))
        hard, soft = check_item(item, num_pages, jokbo_range, label_index)
        item["flags"] = soft
        if hard:
            removed.append({"reason": hard, "item": item})
        else:
            kept.append(item)

    for idx in sorted(find_exact_duplicates(kept), reverse=True):
        removed.append({"reason": ["exact_duplicate"], "item": kept.pop(idx)})
    return kept, removed


def authoritative_ranges(run_dir: Path, prep: dict) -> tuple[list | None, list | None, str]:
    """구간의 주인은 `structure.json`(모델)이고, `prep.json`은 정규식이 낸 힌트다.

    이걸 안 지키면 검증기가 유령 불평을 낸다 - 실제로 `260812_01`에서 힌트가
    `[32,35]`, 모델 판정이 `[31,35]`였고, 슬라이드 31의 족보 카드 3장이
    `source_type_range_mismatch`로 걸렸다. 카드가 옳고 힌트가 틀렸는데도.
    """
    structure_path = run_dir / "structure.json"
    if structure_path.exists():
        try:
            structure = json.loads(structure_path.read_text(encoding="utf-8"))
            return (structure.get("lecture_range"), structure.get("jokbo_range"),
                    "structure.json")
        except (ValueError, OSError):
            pass
    return prep.get("lecture_range"), prep.get("jokbo_range"), "prep.json(힌트)"


def validate_run(run_dir: Path, items_name: str = "items.raw.json") -> dict:
    run_dir = Path(run_dir)
    prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))
    num_pages = int(prep["num_pages"])
    lecture_range, jokbo_range, range_source = authoritative_ranges(run_dir, prep)

    payload = json.loads((run_dir / items_name).read_text(encoding="utf-8"))
    items = payload["items"] if isinstance(payload, dict) else payload

    blueprint_path = run_dir / "blueprint.json"
    blueprint = json.loads(blueprint_path.read_text(encoding="utf-8")) if blueprint_path.exists() else None

    labels_path = Path(prep.get("labels_path") or (run_dir / "labels.json"))
    labels = json.loads(labels_path.read_text(encoding="utf-8")) if labels_path.exists() else None
    label_index = build_label_index(labels)

    kept, removed = validate_items(items, num_pages, jokbo_range, label_index)

    slide_counts: dict[int, int] = {}
    for item in kept:
        slide_counts[int(item["slide_no"])] = slide_counts.get(int(item["slide_no"]), 0) + 1
    # 정보량이 많은 슬라이드는 많이 내는 것이 맞으므로 과출제는 삭제 사유가 아니다.
    # 다만 한 슬라이드에 지나치게 몰리면 쪼개기가 잘못됐을 수 있어 감사에 알린다.
    hot_slides = [
        {"slide_no": s, "count": c}
        for s, c in sorted(slide_counts.items()) if c > SLIDE_CONCENTRATION_MAX
    ]
    skip = set(blueprint.get("skip_slides", []) if blueprint else [])
    untouched = [s for s in range(1, num_pages + 1) if s not in slide_counts and s not in skip]

    importance_counts = {
        key: sum(1 for i in kept if str(i.get("importance", "")).lower() == key)
        for key in ("core", "detail")
    }
    # build.py와 같은 기준으로 센다. 족보 카드의 exam_hit은 태그로 나가지 않는다.
    importance_counts["exam_hit"] = sum(
        1 for i in kept
        if i.get("exam_hit") and str(i.get("source_type", "lecture")).lower() != "jokbo"
    )
    sources = {
        s: sum(1 for i in kept if str(i.get("source_type", "lecture")).lower() == s)
        for s in ("lecture", "jokbo")
    }

    suspects = {
        "lecture_id": prep["lecture_id"],
        "num_pages": num_pages,
        "lecture_range": lecture_range,
        "jokbo_range": jokbo_range,
        "range_source": range_source,
        "item_count": len(kept),
        "importance": importance_counts,
        "sources": sources,
        "removed": removed,
        "flagged": [
            {"index": i, "id": it["id"], "flags": it["flags"], "q": it["q"],
             "a": it["a"], "slide_no": it["slide_no"], "card_type": it.get("card_type"),
             "importance": it.get("importance"), "exam_hit": it.get("exam_hit"),
             "source_type": it.get("source_type")}
            for i, it in enumerate(kept) if it["flags"]
        ],
        "near_duplicate_groups": find_near_duplicate_groups(kept),
        "coverage_gaps": coverage_gaps(blueprint, kept),
        "hot_slides": hot_slides,
        "untouched_slides": untouched,
        "occlusion": sum(1 for i in kept if i.get("occlusion")),
        "trap_notes": sum(1 for i in kept if str(i.get("trap_note") or "").strip()),
    }

    (run_dir / "items.checked.json").write_text(
        json.dumps({"lecture_id": prep["lecture_id"], "items": kept}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    (run_dir / "suspects.json").write_text(
        json.dumps(suspects, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"kept": len(kept), "suspects": suspects}


def main() -> int:
    parser = argparse.ArgumentParser(description="퀴즈 파이프라인 3단계: 기계 검증")
    parser.add_argument("run_dir", help="runs/<lecture_id>")
    parser.add_argument("--items", default="items.raw.json", help="검증할 파일명")
    args = parser.parse_args()

    result = validate_run(Path(args.run_dir), args.items)
    s = result["suspects"]
    print(f"[validate] 통과 {result['kept']}장 "
          f"(강의록 {s['sources']['lecture']} / 족보 {s['sources']['jokbo']})")
    print(f"  중요도: core {s['importance']['core']} / detail {s['importance']['detail']}"
          f"  |  족보 출제(exam_hit) {s['importance']['exam_hit']}")
    print(f"  hard 제거: {len(s['removed'])}  (사유별: "
          f"{', '.join(sorted({r for x in s['removed'] for r in x['reason']})) or '없음'})")
    print(f"  soft 플래그: {len(s['flagged'])}문항")
    print(f"  이미지 오클루전 {s['occlusion']}장 / 함정 메모 {s['trap_notes']}장")
    print(f"  유사 후보군: {len(s['near_duplicate_groups'])}개")
    print(f"  커버리지 누락: {len(s['coverage_gaps'])}개")
    if s["hot_slides"]:
        print(f"  과출제 의심 슬라이드: {[h['slide_no'] for h in s['hot_slides']]}")
    print(f"  문항이 없는 슬라이드 {len(s['untouched_slides'])}장: {s['untouched_slides']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
