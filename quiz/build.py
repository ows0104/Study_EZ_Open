"""4단계: 검증된 문항 + 슬라이드 이미지 → .apkg

    python quiz/build.py runs/250813_02

입력  items.final.json  (감사 ③Auditor가 확정한 문항)
      prep.json         (slide_image_map, labels_path)
출력  <lecture_id>.apkg, run.meta.json, media_occlusion/, ../INDEX.md

원본 파이프라인과 다른 점 하나: slide_no에 해당하는 이미지가 없을 때
'가장 가까운 슬라이드'로 대체하지 않는다. 그건 문항은 맞는데 그림만 다른
카드를 조용히 만들어내고, 복습할 때 오히려 잘못된 연결을 학습시킨다.
여기서는 실패로 처리하고 어느 문항인지 이름을 대서 보고한다. 오클루전
좌표가 풀리지 않을 때도 같다.

마지막에 쓴 .apkg를 도로 열어 노트·카드·미디어 수를 실제로 센다(quiz/verify.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import genanki

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from quiz.cloze import blank_cloze_markup, normalize_cloze_to_c1, strip_cloze_markup, valid_cloze_text  # noqa: E402
from quiz.deck_index import update_index  # noqa: E402
from quiz.notetype import get_anki_model, hierarchical_deck_name  # noqa: E402
from quiz.occlusion import build_label_index, render_occlusion_pair, resolve_rects  # noqa: E402
from quiz.textutil import (  # noqa: E402
    escape_field,
    normalize_display_newlines,
    safe_filename,
    safe_media_prefix,
    stable_int_id,
)
from quiz.validate import authoritative_ranges, check_item  # noqa: E402
from quiz import timings  # noqa: E402
from quiz.verify import verify_apkg  # noqa: E402


DEFAULT_PROJECT = "병리학"

REVIEW_FLAG_LABELS = {
    "answer_mismatch": "정답 불일치",
    "question_error": "문항 오류 의심",
    "uncertain": "검토 필요",
}

# 하위 덱 이름. `source_type` → 잎 이름이고, 순서가 Anki에서 보이는 순서다.
# PreQuiz가 같은 강의 아래 `::예습확인`으로 붙으므로 한 강의 밑에 셋이 나란히 선다.
DECK_LEAVES = {"lecture": "강의록", "jokbo": "족보"}


def _review_field(item: dict) -> str:
    """뒷면의 빨간 경고 박스. 두 가지가 들어온다.

    - `review_flags` — 족보 문항의 정오 분류. 족보 카드에만 붙는다
    - `review_note` — 이 카드에서 조심할 **자료 쪽 사정**. 강의록 카드도 쓴다

    `review_note`만 있어도 박스를 낸다. 자료 자체에 결함이 있는 카드가 그 자리다 -
    `260814_05` s20이 M2 유도 자극을 `IL-13, IL-14`로 인쇄했는데 IL-14는 IL-4의
    오기이고(같은 강의 s19가 IL-4·IL-13을 적어 교차 확인된다), s31은 표의 줄 순서를
    일대일 인과로 읽으면 표준 지식과 어긋난다.

    **경고가 그림 바로 위에 서야 값을 한다.** 템플릿에서 이 박스가 `SlideImage`
    직전이다. 뒷면에 그 그림이 붙으므로 해설의 회색 글씨로는 늦는다.
    """
    flags = [f for f in (item.get("review_flags") or []) if f in REVIEW_FLAG_LABELS]
    note = normalize_display_newlines(str(item.get("review_note") or "").strip())
    if not flags and not note:
        return ""
    parts = []
    if flags:
        parts.append("족보 검토: " + ", ".join(REVIEW_FLAG_LABELS[f] for f in flags))
        if note:
            parts.append("검토 근거: " + note)
    else:
        parts.append("자료 주의: " + note)
    return normalize_display_newlines("\n".join(parts))[:800]


def _explanation_field(item: dict, lead: str = "") -> str:
    """해설 + 함정 + 근거. 근거는 나중에 원본을 다시 찾아갈 때의 좌표다.

    `lead`는 맨 앞에 세울 한 덩이다. 오클루전 카드의 정답 텍스트가 이리로 온다 -
    그 카드는 드러난 슬라이드가 정답이라 뒷면 큰 글씨 자리를 비우지만, 텍스트를
    버리지는 않는다. 상자가 라벨을 덜 덮었거나 그림이 작아 안 읽힐 때 확인할
    자리가 필요하다.
    """
    parts = []
    if lead:
        parts.append(normalize_display_newlines(lead))
    explanation = normalize_display_newlines(item.get("explanation", ""))
    if explanation:
        parts.append(explanation)
    # 교수가 선지를 돌려 쓰는 경향이 있어 오답 선지가 좋은 함정 재료다(item-rules §4.2).
    # 해설에 묻어두면 눈에 안 들어오므로 한 줄로 따로 세운다.
    trap = normalize_display_newlines(item.get("trap_note", ""))
    if trap:
        parts.append(f"함정: {trap}")
    anchor = str(item.get("source_anchor") or "").strip()
    if anchor:
        evidence_type = str(item.get("evidence_type") or "lecture_text").strip()
        parts.append(f"근거: Slide {item.get('slide_no')} ({evidence_type}) {anchor}")
    return normalize_display_newlines("\n\n".join(parts))


def stamped_slides(run_dir: Path) -> set[int]:
    """족보 도장이 찍힌 슬라이드 번호.

    도장은 슬라이드에 찍혀 있고 annotations.json에 이미 결정론적으로 잡혀 있다.
    모델이 옮겨 적을 이유가 없으므로 여기서 붙인다.
    """
    path = Path(run_dir) / "annotations.json"
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {a["slide_no"] for a in data if "stamp" in (a.get("signals") or {})}


def render_occlusion_media(items: list[dict], prep: dict, out_dir: Path) -> dict[str, tuple[str, str]]:
    """오클루전 카드마다 (가린 앞면, 드러낸 뒷면) PNG 두 장.

    좌표는 labels.json의 bbox이거나 모델이 직접 적은 정규화 좌표다. 어느 쪽도
    풀리지 않으면 여기서 멈춘다 - 상자가 어긋난 카드는 정답이 새어 보이거나
    엉뚱한 데를 가려서, 조용히 통과시키면 복습할 때 오히려 방해가 된다.
    """
    targets = [it for it in items if it.get("occlusion")]
    if not targets:
        return {}

    labels_path = Path(prep.get("labels_path") or "")
    labels = json.loads(labels_path.read_text(encoding="utf-8")) if labels_path.exists() else None
    label_index = build_label_index(labels)
    prefix = safe_media_prefix(prep["source_stem"])

    media: dict[str, tuple[str, str]] = {}
    failures: list[str] = []
    for item in targets:
        slide_no = int(item["slide_no"])
        rects, masks, problems = resolve_rects(item["occlusion"], slide_no, label_index)
        if problems:
            failures.append(f"  - {item.get('id')} (slide {slide_no}): {', '.join(problems)}")
            continue
        basename = f"{prefix}_occl_s{slide_no:03d}_{safe_filename(item.get('id') or 'x')}"
        # 필기를 지운 채널에서 렌더한다. 원본으로 렌더하면 가려야 할 답이 필기로
        # 옆에 적혀 있어 카드가 무의미해진다 - 실제로 260812_01 슬라이드 8에서
        # 6개 분야 설명이 격자와 같은 순서로 적혀 있어 오클루전 3장이 전멸했다.
        source = prep.get("model_input_pdf") or prep["source_pdf"]
        # 각인용 하단 띠는 카드 이미지에서 잘라낸다. 예전 run은 이 값이 없어 0이 된다.
        media[str(item["id"])] = render_occlusion_pair(
            source, slide_no, rects, out_dir, basename,
            band_pt=float(prep.get("stamp_band_pt") or 0.0), masks=masks)

    if failures:
        raise SystemExit(
            f"빌드 중단: 오클루전 좌표를 풀 수 없는 카드 {len(failures)}장.\n"
            + "\n".join(failures)
            + "\n감사 단계로 되돌려 label_ids를 labels.json에서 다시 확인하세요."
        )
    return media


def build_notes(items: list[dict], slide_image_map: dict[int, str], lecture_id: str,
                stamps: set[int], occlusion_media: dict[str, tuple[str, str]] | None = None):
    model = get_anki_model()
    occlusion_media = occlusion_media or {}
    notes, used_slides = [], set()
    stats = {"basic": 0, "cloze": 0, "jokbo": 0, "occlusion": 0}
    for item in items:
        slide_no = int(item["slide_no"])
        pair = occlusion_media.get(str(item.get("id")))
        if pair:
            # 뒷면 이미지는 가림 상자만 걷어낸 같은 슬라이드다. 원본 미디어를
            # 따로 붙이면 같은 그림이 두 번 나와 답이 두 번 보인다.
            front_img, img_name = pair
            stats["occlusion"] += 1
        else:
            front_img, img_name = None, slide_image_map[slide_no]
            used_slides.add(slide_no)

        question = normalize_display_newlines(normalize_cloze_to_c1(item["q"]))
        answer = normalize_display_newlines(item["a"])
        card_type = str(item.get("card_type") or "fact").strip().lower()

        if card_type == "cloze" and valid_cloze_text(question):
            # escape_field가 {, }, : 를 건드리지 않으므로 먼저 이스케이프한 뒤
            # 빈칸을 넣어야 <span>이 진짜 HTML로 남는다.
            anki_question = blank_cloze_markup(escape_field(question))
            stats["cloze"] += 1
        else:
            if card_type == "cloze":
                question = strip_cloze_markup(question, keep_answer=True)
                card_type = "fact"
            anki_question = escape_field(question)
            stats["basic"] += 1

        if front_img:
            # 오클루전은 앞면에 그림이 있어야 성립하는 유일한 예외다(item-rules §16).
            anki_question = (
                f'<div class="occlusion-box"><img src="{front_img}"></div>' + anki_question)
            # 뒷면의 정답도 그림이다. 가려진 자리를 보고 답하는 카드이므로, 그 자리에
            # 무엇이 있었는지는 **제자리에서 드러난 그림**이 옮겨 적은 텍스트보다
            # 읽기 쉽다. 큰 글씨 자리를 비우면(템플릿이 빈 Answer를 지운다) 뒷면에서
            # 눈이 바로 그림으로 간다. 텍스트는 접힌 해설 맨 앞에 남긴다 - 상자가
            # 라벨을 덜 덮었거나 글자가 작아 안 읽히는 카드에서 확인할 자리가 필요하다.
            answer_field = ""
            explanation = _explanation_field(item, lead=f"정답: {answer}" if answer else "")
        else:
            answer_field = answer
            explanation = _explanation_field(item)

        source_type = str(item.get("source_type") or "lecture").strip().lower()
        # 중요도·출제 이력 태그는 나중에 붙일 풀이 시스템이 학습 순서를 짜는 데 쓴다.
        # 덱은 나누지 않고 태그만 붙인다.
        importance = str(item.get("importance") or "detail").strip().lower()
        tags = [
            importance,
            f"type_{safe_filename(card_type)}",
            f"source_{safe_filename(source_type)}",
            f"lecture_{safe_filename(lecture_id)}",
            f"slide_{slide_no:03d}",
        ]
        if item.get("exam_hit") and source_type != "jokbo":
            tags.append("exam_hit")
        if slide_no in stamps:
            tags.append("stamp")
        if front_img:
            tags.append("occlusion")
        if str(item.get("trap_note") or "").strip():
            tags.append("trap_note")
        if source_type == "jokbo":
            stats["jokbo"] += 1
            year = str(item.get("exam_year") or "").strip()
            if year:
                tags.append(f"exam_{safe_filename(year)}")
        for flag in item.get("review_flags") or []:
            tags.append(f"review_{safe_filename(flag)}")

        notes.append(genanki.Note(
            model=model,
            fields=[
                anki_question,
                escape_field(answer_field),
                escape_field(explanation),
                str(slide_no),
                f'<img src="{img_name}">',
                escape_field(source_type),
                escape_field(card_type),
                escape_field(_review_field(item)),
            ],
            tags=tags,
        ))
    return notes, used_slides, stats


def build_run(run_dir: Path, items_name: str, project: str, output: Path | None) -> dict:
    run_dir = Path(run_dir)
    prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))
    num_pages = int(prep["num_pages"])
    # 경계는 자료의 범위다. `num_pages`(강의록 PDF 쪽수)로 자르면 외부 족보를 붙인
    # 편에서 정상 카드가 막힌다. 아래 `slide_image_map` 검사가 진짜 빌드 가능성이다.
    max_slide = int(prep.get("total_slides") or num_pages)
    # 구간의 주인은 structure.json이다. prep.json은 힌트라 여기서 쓰면
    # 빌드가 잘못된 범위로 커버리지를 보고하고, 족보 문항을 범위 밖으로 친다.
    lecture_range, jokbo_range, _ = authoritative_ranges(run_dir, prep)
    slide_image_map = {int(k): v for k, v in prep["slide_image_map"].items()}
    media_dir = Path(prep["media_dir"])

    payload = json.loads((run_dir / items_name).read_text(encoding="utf-8"))
    items = payload["items"] if isinstance(payload, dict) else payload

    # 감사가 문항을 고쳤을 수 있으므로 같은 규칙으로 한 번 더 본다.
    # "모델이 무언가 반환했다"를 "문제가 해결됐다"로 간주하지 않는다.
    blocked = []
    for item in items:
        hard, _ = check_item(item, max_slide, jokbo_range)
        if int(item.get("slide_no") or 0) not in slide_image_map:
            hard.append("slide_image_missing")
        if hard:
            blocked.append({"id": item.get("id"), "q": item.get("q"), "reason": hard})
    if blocked:
        lines = [f"  - {b['id']}: {', '.join(b['reason'])} | {str(b['q'])[:60]}" for b in blocked]
        raise SystemExit(
            f"빌드 중단: {len(blocked)}문항이 하드 규칙을 통과하지 못했습니다.\n"
            + "\n".join(lines)
            + "\n감사 단계로 되돌려 slide_no를 고치거나 해당 문항을 삭제하세요."
        )

    lecture_id = prep["lecture_id"]
    deck_title = f"[{lecture_id}] {prep['lecture_title']}"
    deck_name = hierarchical_deck_name(project, deck_title)

    stamps = stamped_slides(run_dir)
    occlusion_dir = run_dir / "media_occlusion"
    occlusion_media = render_occlusion_media(items, prep, occlusion_dir)
    notes, used_slides, stats = build_notes(
        items, slide_image_map, lecture_id, stamps, occlusion_media)

    # 강의록과 족보를 하위 덱으로 가른다 - `과목::강의::강의록` / `::족보`.
    # PreQuiz가 이미 같은 강의 아래 `::예습확인`으로 붙고 있어 셋이 한 강의 밑에
    # 나란히 선다. 학습 스케줄을 따로 잡을 수 있게 하려는 것이다 - 족보는 시험 직전에
    # 몰아 보고 강의록은 꾸준히 도는 식으로 쓸 수 있다.
    # `build_notes`는 `items` 순서대로 append하므로 인덱스가 그대로 짝이 된다.
    decks: list = []
    for key, leaf in DECK_LEAVES.items():
        picked = [n for n, item in zip(notes, items)
                  if str(item.get("source_type", "lecture")).lower() == key]
        if not picked:
            continue
        sub = genanki.Deck(stable_int_id(f"deck:quiz:{project}:{lecture_id}:{key}"),
                           f"{deck_name}::{leaf}")
        for note in picked:
            sub.add_note(note)
        decks.append(sub)
    if not decks:
        raise SystemExit("빌드 중단: 덱에 넣을 카드가 없습니다.")

    # 미디어는 실제로 쓰인 슬라이드만 넣는다. 33장 전체를 넣으면 안 쓰는 이미지가
    # collection.media에 쌓인다.
    media_files = [str((media_dir / slide_image_map[s]).resolve()) for s in sorted(used_slides)]
    for front, back in occlusion_media.values():
        media_files.append(str((occlusion_dir / front).resolve()))
        media_files.append(str((occlusion_dir / back).resolve()))

    output = Path(output) if output else run_dir / f"{safe_filename(deck_title)}.apkg"
    package = genanki.Package(decks)
    package.media_files = media_files
    package.write_to_file(str(output))

    # 쓴 파일을 도로 열어 실제 내용물을 센다. genanki가 성공을 반환했다는 사실은
    # 덱이 온전하다는 뜻이 아니다.
    verified = verify_apkg(output, len(notes), [Path(p).name for p in media_files])
    covered_slides = {int(i["slide_no"]) for i in items}

    meta = {
        "lecture_id": lecture_id,
        "lecture_title": prep.get("lecture_title", ""),
        # `deck_name`은 강의 덱(부모)이다. 실제 카드는 그 아래 하위 덱에 들어간다.
        "deck_name": deck_name,
        "decks": {d.name: len(d.notes) for d in decks},
        "verified": verified,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "apkg": str(output.resolve()),
        "item_count": len(items),
        "format": stats,
        "occlusion": stats["occlusion"],
        "trap_notes": sum(1 for i in items if str(i.get("trap_note") or "").strip()),
        # 오클루전 카드는 원본 슬라이드 미디어를 쓰지 않지만 그 슬라이드는 분명히
        # 다뤄졌다. 커버리지는 미디어가 아니라 문항 기준으로 센다.
        "slides_used": sorted(covered_slides),
        "slides_unused": [s for s in range(1, max_slide + 1) if s not in covered_slides],
        "media_count": len(media_files),
        "importance": {
            key: sum(1 for i in items if str(i.get("importance", "detail")).lower() == key)
            for key in ("core", "detail")
        },
        "exam_hit": sum(1 for i in items if i.get("exam_hit")
                        and str(i.get("source_type", "lecture")).lower() != "jokbo"),
        "stamped": sum(1 for i in items if int(i["slide_no"]) in stamps),
        "sources": {
            key: sum(1 for i in items if str(i.get("source_type", "lecture")).lower() == key)
            for key in ("lecture", "jokbo")
        },
        "review_flagged": sum(1 for i in items if i.get("review_flags")),
        # 종류별로도 남긴다. 신호는 개수가 아니라 종류에 있다 — `answer_mismatch`만
        # "정답이 틀렸다"는 뜻이고 나머지 둘은 실측에서 스스로 풀렸다(CLAUDE.md
        # "계수기는 아직 사람을 부를 줄 모른다"). `studyez.gate`가 이걸로 배포를 막는다.
        "review_flags": {
            key: sum(1 for i in items if key in (i.get("review_flags") or []))
            for key in REVIEW_FLAG_LABELS
        },
        # `review_note`만 있고 플래그가 없는 카드 — 자료 자체가 의심스러운 자리다
        # (item-rules §4.5). 위 `review_flagged`가 플래그만 세므로 따로 센다. 안 세던
        # 동안 `260814_05`의 빨간 박스 두 장이 요약에 "없음"으로 나왔다.
        "source_warned": sum(1 for i in items
                             if str(i.get("review_note") or "").strip()
                             and not i.get("review_flags")),
        "card_types": {
            key: sum(1 for i in items if str(i.get("card_type", "fact")).lower() == key)
            for key in ("fact", "comparison", "mechanism", "trap", "list", "sequence", "cloze")
        },
    }
    (run_dir / "run.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    meta["index_path"] = str(update_index(run_dir.parent, meta))
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description="퀴즈 파이프라인 4단계: Anki 덱 빌드")
    parser.add_argument("run_dir", help="runs/<lecture_id>")
    parser.add_argument("--items", default="items.final.json", help="빌드할 파일명")
    parser.add_argument("--project", default=DEFAULT_PROJECT, help="상위 덱 이름")
    parser.add_argument("--out", default=None, help="출력 apkg 경로")
    args = parser.parse_args()

    with timings.stage(Path(args.run_dir), "5-build"):
        meta = build_run(Path(args.run_dir), args.items, args.project, args.out)
    print(f"[build] {meta['deck_name']}")
    for name, count in meta.get("decks", {}).items():
        print(f"    └ {name.split('::')[-1]:<8} {count}장")
    print(f"  {meta['item_count']}장 (basic {meta['format']['basic']} / cloze {meta['format']['cloze']})")
    flags = " · ".join(f"{k} {v}" for k, v in meta["review_flags"].items() if v) or "없음"
    print(f"  출처: 강의록 {meta['sources']['lecture']} / 족보 {meta['sources']['jokbo']}"
          f" (정오 검토 플래그 {meta['review_flagged']}장 — {flags})")
    if meta.get("source_warned"):
        print(f"  자료 주의 경고 {meta['source_warned']}장 — 뒷면 그림 위에 빨간 박스가 뜬다")
    print(f"  중요도: core {meta['importance']['core']} / detail {meta['importance']['detail']}")
    print(f"  출제 이력: exam_hit {meta['exam_hit']} / stamp {meta['stamped']}")
    print(f"  유형: { {k: v for k, v in meta['card_types'].items() if v} }")
    print(f"  이미지 오클루전 {meta['occlusion']}장 / 함정 메모 {meta['trap_notes']}장")
    print(f"  슬라이드 {len(meta['slides_used'])}장 사용, 미사용 {meta['slides_unused']}")
    v = meta["verified"]
    print(f"  apkg 검증: 노트 {v['notes']} / 카드 {v['cards']} / 미디어 {v['media']}"
          f" ({v['collection']})")
    print(f"  → {meta['apkg']}")
    print(f"  대장: {meta['index_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
