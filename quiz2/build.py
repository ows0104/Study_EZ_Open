"""v2 5단계: 검증된 문항 + 슬라이드 이미지 → .apkg

    python -m quiz2.build runs/260819_01 --items items.reproduced.json

입력  items.reproduced.json  (재현 검사까지 붙은 것. 없으면 items.checked.json)
      prep.json              (slide_image_map, labels_path)
      structure.json         (구간의 주인)
출력  <lecture_id>.apkg, run.meta.json, media_occlusion/

## 왜 `quiz/build.py`를 그대로 못 쓰는가

v2 산출물에 v1 빌드를 대면 세 자리에서 조용히 어긋난다. 셋 다 **에러가 아니라
손실**이라 돌려보면 성공한 것처럼 보인다.

    card_type == "cloze"   v2는 cloze가 `card_format`이다. card_type의 여섯에
                           cloze가 없으므로 빈칸 카드 6장이 통째로 basic이 된다
    source_anchor          ⑱에서 없앴다. v1은 이게 없으면 `근거:` 줄을 통째로
                           안 낸다 — 145장 전부에서 evidence_type이 사라진다
    trap_note              v2는 함정을 explanation에 녹인다. v1은 `함정:` 줄과
                           `trap_note` 태그를 찾다가 못 찾고 넘어간다

## 뒷면 빨간 박스가 이 파일의 본론이다

인터뷰 ③⃝의 결론이 *"표시는 카드 뒷면에 떠야 한다"*였다. `suspects.json`이나 빌드
요약에만 있으면 관리자가 볼 일이 없다 — 덱이 나오면 *"풀면서 걸러낸다"*고 했다.

그래서 신호 셋이 **한 박스에 서되 각자 제 머리글을 쓴다.** `_review_field` 참조.

## `runs/INDEX.md`를 건드리지 않는다

`quiz/deck_index.update_index`는 같은 `lecture_id`의 줄을 **덮어쓴다.** v2가 v1이
이미 빌드한 강의를 다시 빌드하면(비교하려면 그래야 한다) 기준선 줄이 지워진다.
그래서 기본은 안 쓴다. v2가 생산 라인이 될 때 `--index`로 켠다.

같은 이유로 덱 이름도 겹친다. v1 덱과 v2 덱을 한 Anki에 같이 넣어 견주려면
`--project 병리학-v2`처럼 상위 덱을 갈라라. 안 가르면 같은 덱에 두 벌이 쌓인다.
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

from quiz.cloze import (  # noqa: E402
    blank_cloze_markup,
    normalize_cloze_to_c1,
    strip_cloze_markup,
    valid_cloze_text,
)
from quiz.deck_index import update_index  # noqa: E402
from quiz.notetype import get_anki_model, hierarchical_deck_name  # noqa: E402
from quiz.occlusion import build_label_index, render_occlusion_pair, resolve_rects  # noqa: E402
from quiz2.occlusion import render_figure_crop, resolve_crop  # noqa: E402
from quiz.textutil import (  # noqa: E402
    escape_field,
    normalize_display_newlines,
    safe_filename,
    safe_media_prefix,
    stable_int_id,
)
from quiz.verify import verify_apkg  # noqa: E402
from quiz import timings  # noqa: E402
from quiz2.prompt import CARD_FORMATS, IMPORTANCE_TIERS  # noqa: E402
from quiz2.validate import VALID_CARD_TYPES, check_item, load_structure  # noqa: E402


DEFAULT_PROJECT = "병리학"

# ㉓ 족보 정오 검토. 라벨은 카드 뒷면에 그대로 뜬다.
REVIEW_FLAG_LABELS = {
    "answer_mismatch": "정답 불일치",
    "question_error": "문항 오류 의심",
    "uncertain": "검토 필요",
}

# ⓹ 재현 검사가 실패로 치는 판정. `same`은 박스를 안 낸다.
REPRODUCE_FAILED = ("different", "partial")
REPRODUCE_HEADS = {
    "different": "질문만 주고 다시 풀었을 때 다른 답이 나왔다",
    "partial": "질문만 주고 다시 풀었을 때 일부만 나왔다",
}
# 자족성(⑬) 실패는 판정보다 이쪽이 먼저다 — 답이 갈린 게 아니라 질문이 안 선 것이다.
REPRODUCE_UNANSWERABLE = "질문만으로는 무엇을 묻는지 알 수 없다고 했다"

# 박스 한 줄의 길이. 재현 답을 통째로 싣다가 박스가 그림을 밀어내지 않게 자른다.
REVIEW_LINE_MAX = 240
REVIEW_FIELD_MAX = 800

DECK_LEAVES = {"lecture": "강의록", "jokbo": "족보"}


def _text(value) -> str:
    return str(value or "").strip()


def _reproduce_line(item: dict) -> str:
    """재현 검사 실패 한 줄. **판정이 아니라 사실을 적는다.**

    `reproduce`는 `reproduce.py score --apply`가 카드에 박아 둔 객체다. 문자열을
    이어붙인 `review_note`를 다시 읽지 않는다 — 그 자리는 자료 주의와 족보 검토
    근거가 이미 나눠 쓰고 있어서, 셋째가 끼면 코드가 부분 문자열로만 갈라낼 수 있다.
    """
    record = item.get("reproduce") or {}
    verdict = _text(record.get("verdict")).lower()
    if verdict not in REPRODUCE_FAILED:
        return ""
    head = (REPRODUCE_UNANSWERABLE if record.get("answerable") is False
            else REPRODUCE_HEADS[verdict])
    body = f"재현 주의: {head}"
    why = _text(record.get("why"))
    if why:
        body += f" — {why}"
    reproduced = _text(record.get("reproduced"))
    if reproduced:
        body += f" (재현 답: {reproduced})"
    return body[:REVIEW_LINE_MAX]


def _review_field(item: dict) -> str:
    """뒷면 빨간 박스. **신호 셋이 한 박스에 서고 각자 제 머리글을 쓴다.**

        족보 검토: …   ㉓ 족보 문항의 정답을 의심한 것. `review_flags`
        검토 근거: …   그 판정의 근거. 플래그가 있을 때의 `review_note`
        재현 주의: …   ⓹ 이 카드가 질문만으로 답을 못 끌어냈다. `reproduce`
        자료 주의: …   ⑳‴ 자료 자체에 결함이 있다. 플래그 없는 `review_note`

    **셋은 다른 것이다.** 앞은 족보를 의심하고, 가운데는 카드를 의심하고, 뒤는
    자료를 의심한다. 관리자가 할 일도 다르다 — 자료 주의는 "그림을 의심하며
    읽어라"이고 재현 주의는 "이 카드가 안 선다"이다.

    v1은 앞뒤 둘만 알았고 그마저 `review_note` 한 필드에 겹쳐 담았다. 플래그가
    있으면 note 전체가 `검토 근거:` 아래로 들어가므로(`quiz/build.py`의
    `_review_field`), 거기에 재현 실패를 이어붙이면 **그 줄이 머리글 없이 족보
    검토 블록에 딸려 붙어 누구의 근거인지가 사라진다.** 실제로 그려 봤다 —

        족보 검토: 정답 불일치
        검토 근거: 족보 표기: ③ → 검토 결론: ②를 채택했다
        재현 검사: 질문만 주고 다시 풀었을 때 다른 답이 나왔다 — …

    셋째 줄은 카드를 의심하는 말인데 위 두 줄에 매달린다. 1회차에 안 터진 것은
    `review_flags`가 0/145였기 때문이지 설계가 막은 게 아니다.

    순서는 자료 주의가 맨 아래다 — 셋 중 그 줄만 바로 아래 붙는 그림을 가리킨다.
    """
    flags = [f for f in (item.get("review_flags") or []) if f in REVIEW_FLAG_LABELS]
    note = normalize_display_newlines(_text(item.get("review_note")))
    parts: list[str] = []

    if flags:
        parts.append("족보 검토: " + ", ".join(REVIEW_FLAG_LABELS[f] for f in flags))
        if note:
            parts.append("검토 근거: " + note)

    reproduce = _reproduce_line(item)
    if reproduce:
        parts.append(reproduce)

    if note and not flags:
        parts.append("자료 주의: " + note)

    if not parts:
        return ""
    return normalize_display_newlines("\n".join(parts))[:REVIEW_FIELD_MAX]


def _explanation_field(item: dict, lead: str = "") -> str:
    """해설 + 근거. 접힌 칩 안에 들어간다.

    v1의 `함정:` 줄이 없다 — v2는 함정을 따로 두지 않고 해설에 녹인다.

    `근거:`도 반쪽이다. v1은 `Slide 12 (table) 표 3행`처럼 슬라이드 안의 좌표까지
    적었는데 그 뒷부분은 `source_anchor`이고 ⑱에서 없앴다. 남은 `evidence_type`은
    그래도 낸다 — 슬라이드의 어디를 볼지(본문이냐 표냐 그림이냐 필기냐)는 뒷면
    meta-box의 `출처: Slide N`이 말해주지 않는 유일한 것이다.
    """
    parts = []
    if lead:
        parts.append(normalize_display_newlines(lead))
    explanation = normalize_display_newlines(_text(item.get("explanation")))
    if explanation:
        parts.append(explanation)
    evidence_type = _text(item.get("evidence_type")) or "lecture_text"
    parts.append(f"근거: Slide {item.get('slide_no')} ({evidence_type})")
    return normalize_display_newlines("\n\n".join(parts))


def stamped_slides(run_dir: Path) -> set[int]:
    """족보 도장이 찍힌 슬라이드 번호. annotations.json에 이미 결정론적으로 있다."""
    path = Path(run_dir) / "annotations.json"
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {a["slide_no"] for a in data if "stamp" in (a.get("signals") or {})}


def render_occlusion_media(items: list[dict], prep: dict, out_dir: Path) -> dict[str, tuple[str, str]]:
    """오클루전 카드마다 (가린 앞면, 드러낸 뒷면) PNG 두 장.

    ㉞ 오클루전 패스는 아직 없어서 1회차에 한 장도 안 왔다. 좌표가 안 풀리면
    여기서 멈춘다 — 상자가 어긋난 카드는 답이 새어 보이거나 엉뚱한 데를 가린다.
    """
    targets = [it for it in items if it.get("occlusion")]
    if not targets:
        return {}

    labels_path = Path(prep.get("labels_path") or "")
    labels = json.loads(labels_path.read_text(encoding="utf-8")) if labels_path.exists() else None
    label_index = build_label_index(labels)
    prefix = safe_media_prefix(prep["source_stem"])

    # 오려내는 카드는 **clean**에서 뽑는다 — 답이 그림의 이름이라 필기가 답을
    # 적어 두면 그대로 샌다 (`quiz2/occlusion.render_figure_crop`).
    clean = prep.get("model_input_pdf") or prep["source_pdf"]

    media: dict[str, tuple[str, str | None]] = {}
    failures: list[str] = []
    for item in targets:
        slide_no = int(item["slide_no"])

        crop_rect, crop_problem = resolve_crop(item, clean)
        if crop_problem:
            failures.append(f"  - {item.get('id')} (slide {slide_no}): {crop_problem}")
            continue
        if crop_rect:
            basename = f"{prefix}_occl_s{slide_no:03d}_{safe_filename(item.get('id') or 'x')}"
            name = render_figure_crop(
                clean, slide_no, crop_rect, out_dir, basename,
                band_pt=float(prep.get("stamp_band_pt") or 0.0))
            # 뒷면이 없다 = **슬라이드 전체를 쓴다.** 오려낸 카드의 답은 그림의
            # 이름이므로 뒷면에서 제목과 본문을 읽을 수 있어야 한다.
            media[str(item["id"])] = (name, None)
            continue

        rects, masks, problems = resolve_rects(item["occlusion"], slide_no, label_index)
        if problems:
            failures.append(f"  - {item.get('id')} (slide {slide_no}): {', '.join(problems)}")
            continue
        basename = f"{prefix}_occl_s{slide_no:03d}_{safe_filename(item.get('id') or 'x')}"
        # ㉞ 채널은 필기본이다. clean으로 렌더하면 가려야 할 답이 필기로 옆에 남는다.
        source = prep.get("annotated_pdf") or prep.get("model_input_pdf") or prep["source_pdf"]
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
    stats = {fmt: 0 for fmt in CARD_FORMATS}
    stats["occlusion"] = 0
    for item in items:
        slide_no = int(item["slide_no"])
        pair = occlusion_media.get(str(item.get("id")))
        cropped = False
        if pair:
            front_img, back_img = pair
            stats["occlusion"] += 1
            if back_img is None:
                # 오려낸 카드. 뒷면은 슬라이드 전체이고 **답 텍스트를 살린다.**
                cropped = True
                img_name = slide_image_map[slide_no]
                used_slides.add(slide_no)
            else:
                # 마스킹 카드. 뒷면은 가림 상자만 걷어낸 같은 슬라이드다.
                img_name = back_img
        else:
            front_img, img_name = None, slide_image_map[slide_no]
            used_slides.add(slide_no)

        question = normalize_display_newlines(normalize_cloze_to_c1(item["q"]))
        answer = normalize_display_newlines(_text(item.get("a")))
        # **v2는 cloze가 card_format이다.** card_type의 여섯(fact·comparison·
        # mechanism·trap·list·sequence)에 cloze가 없다. v1처럼 card_type을 보면
        # 빈칸 카드가 통째로 basic이 되어 답이 앞면에 그대로 나간다.
        card_format = _text(item.get("card_format")).lower() or "basic"
        card_type = _text(item.get("card_type")).lower() or "fact"

        if card_format == "cloze" and valid_cloze_text(question):
            # escape_field가 {, }, : 를 안 건드리므로 먼저 이스케이프한 뒤 빈칸을
            # 넣어야 <span>이 진짜 HTML로 남는다.
            anki_question = blank_cloze_markup(escape_field(question))
        else:
            if card_format == "cloze":
                # 마크업이 깨진 cloze. 답을 살려 basic으로 낸다.
                question = strip_cloze_markup(question, keep_answer=True)
                card_format = "basic"
            anki_question = escape_field(question)
        stats[card_format] = stats.get(card_format, 0) + 1

        if front_img:
            # 오클루전은 앞면에 그림이 있어야 성립하는 유일한 예외다.
            anki_question = (
                f'<div class="occlusion-box"><img src="{front_img}"></div>' + anki_question)
            # 뒷면의 정답도 그림이다. 큰 글씨 자리를 비우면 눈이 바로 그림으로 간다.
            # 텍스트는 접힌 해설 맨 앞에 남긴다 — 상자가 라벨을 덜 덮었을 때 확인할
            # 자리가 필요하다.
            if cropped:
                # 답이 그림의 이름이다. 큰 글씨 자리를 비우면 안 된다.
                answer_field = answer
                explanation = _explanation_field(item)
            else:
                answer_field = ""
                explanation = _explanation_field(item, lead=f"정답: {answer}" if answer else "")
        else:
            answer_field = answer
            explanation = _explanation_field(item)

        source_type = _text(item.get("source_type")).lower() or "lecture"
        importance = _text(item.get("importance")).lower() or "detail"
        tags = [
            importance,
            f"type_{safe_filename(card_type)}",
            f"format_{safe_filename(card_format)}",
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
        if source_type == "jokbo":
            year = _text(item.get("exam_year"))
            if year:
                tags.append(f"exam_{safe_filename(year)}")
        for flag in item.get("review_flags") or []:
            tags.append(f"review_{safe_filename(flag)}")
        # 뒷면 박스에 뜬 것을 Anki에서도 추릴 수 있게 태그로 남긴다. 박스가 본론이고
        # 태그는 그 뒤를 따른다 — 관리자가 "재현 주의 붙은 것만" 걸러 보게 하는 자리.
        verdict = _text((item.get("reproduce") or {}).get("verdict")).lower()
        if verdict in REPRODUCE_FAILED:
            tags.append(f"reproduce_{verdict}")

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


def build_run(run_dir: Path, items_name: str, project: str, output: Path | None,
              write_index: bool = False) -> dict:
    run_dir = Path(run_dir)
    prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))
    # 경계는 자료의 범위다. `num_pages`(강의록 PDF 쪽수)로 자르면 외부 족보를 붙인
    # 편에서 정상 카드가 hard 제거된다 — `260814_05`에서 4장이 그랬다.
    max_slide = int(prep.get("total_slides") or prep["num_pages"])
    # 구간의 주인은 structure.json이고 prep.json은 정규식이 낸 힌트다.
    structure = load_structure(run_dir, prep)
    jokbo_range = structure.get("jokbo_range")
    slide_image_map = {int(k): v for k, v in prep["slide_image_map"].items()}
    media_dir = Path(prep["media_dir"])

    payload = json.loads((run_dir / items_name).read_text(encoding="utf-8"))
    items = payload["items"] if isinstance(payload, dict) else payload

    # 감사가 문항을 고쳤을 수 있으므로 같은 규칙으로 한 번 더 본다. "모델이 무언가
    # 반환했다"를 "문제가 해결됐다"로 간주하지 않는다.
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

    # 강의록과 족보를 하위 덱으로 가른다 — `과목::강의::강의록` / `::족보`.
    # `build_notes`는 items 순서대로 append하므로 인덱스가 그대로 짝이 된다.
    decks: list = []
    for key, leaf in DECK_LEAVES.items():
        picked = [n for n, item in zip(notes, items)
                  if _text(item.get("source_type")).lower() == key
                  or (key == "lecture" and not _text(item.get("source_type")))]
        if not picked:
            continue
        sub = genanki.Deck(stable_int_id(f"deck:quiz2:{project}:{lecture_id}:{key}"),
                           f"{deck_name}::{leaf}")
        for note in picked:
            sub.add_note(note)
        decks.append(sub)
    if not decks:
        raise SystemExit("빌드 중단: 덱에 넣을 카드가 없습니다.")

    # 미디어는 실제로 쓰인 슬라이드만 넣는다.
    media_files = [str((media_dir / slide_image_map[s]).resolve()) for s in sorted(used_slides)]
    for front, back in occlusion_media.values():
        media_files.append(str((occlusion_dir / front).resolve()))
        if back:
            media_files.append(str((occlusion_dir / back).resolve()))

    output = Path(output) if output else run_dir / f"{safe_filename(deck_title)}.apkg"
    package = genanki.Package(decks)
    package.media_files = media_files
    package.write_to_file(str(output))

    # 쓴 파일을 도로 열어 실제 내용물을 센다. genanki가 성공을 반환했다는 사실은
    # 덱이 온전하다는 뜻이 아니다.
    verified = verify_apkg(output, len(notes), [Path(p).name for p in media_files])
    covered_slides = {int(i["slide_no"]) for i in items}

    def _verdict(item: dict) -> str:
        return _text((item.get("reproduce") or {}).get("verdict")).lower()

    reproduce_counts = {key: sum(1 for i in items if _verdict(i) == key)
                        for key in ("same", "partial", "different")}
    # 오클루전은 `reproduce.py split`이 일부러 뺀다 — 앞면에 그림이 떠야 서는
    # 카드라 글자만으로는 못 잰다. 안 거친 것과 못 거친 것을 갈라 센다.
    reproduce_counts["occlusion_exempt"] = sum(
        1 for i in items if i.get("occlusion") and not _verdict(i))
    reproduce_counts["unscored"] = sum(
        1 for i in items if not _verdict(i) and not i.get("occlusion"))
    reproduce_counts["unanswerable"] = sum(
        1 for i in items if (i.get("reproduce") or {}).get("answerable") is False)

    meta = {
        "pipeline": "quiz2",
        "lecture_id": lecture_id,
        "lecture_title": prep.get("lecture_title", ""),
        "deck_name": deck_name,
        "decks": {d.name: len(d.notes) for d in decks},
        "verified": verified,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "apkg": str(output.resolve()),
        "items_file": items_name,
        "item_count": len(items),
        "card_formats": {k: v for k, v in stats.items() if k != "occlusion"},
        "occlusion": stats["occlusion"],
        "slides_used": sorted(covered_slides),
        "slides_unused": [s for s in range(1, max_slide + 1) if s not in covered_slides],
        "media_count": len(media_files),
        "importance": {key: sum(1 for i in items
                                if _text(i.get("importance")).lower() == key)
                       for key in IMPORTANCE_TIERS},
        "exam_hit": sum(1 for i in items if i.get("exam_hit")
                        and _text(i.get("source_type")).lower() != "jokbo"),
        "stamped": sum(1 for i in items if int(i["slide_no"]) in stamps),
        "sources": {key: sum(1 for i in items
                             if _text(i.get("source_type")).lower() == key)
                    for key in DECK_LEAVES},
        "card_types": {key: sum(1 for i in items
                                if _text(i.get("card_type")).lower() == key)
                       for key in sorted(VALID_CARD_TYPES)},
        # ── 뒷면 빨간 박스에 실제로 뜬 것 ────────────────────────────────
        # 셋을 따로 센다. 신호는 개수가 아니라 종류에 있다 — 셋이 의심하는 대상이
        # 각각 족보·카드·자료로 다르다.
        "review_flagged": sum(1 for i in items if i.get("review_flags")),
        "review_flags": {key: sum(1 for i in items if key in (i.get("review_flags") or []))
                         for key in REVIEW_FLAG_LABELS},
        "source_warned": sum(1 for i in items
                             if _text(i.get("review_note")) and not i.get("review_flags")),
        "reproduce": reproduce_counts,
        "review_boxed": sum(1 for i in items if _review_field(i)),
    }
    (run_dir / "run.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    if write_index:
        meta["index_path"] = str(update_index(run_dir.parent, meta))
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description="v2 5단계: Anki 덱 빌드")
    parser.add_argument("run_dir", help="runs/<lecture_id>")
    parser.add_argument("--items", default="items.reproduced.json", help="빌드할 파일명")
    parser.add_argument("--project", default=DEFAULT_PROJECT,
                        help="상위 덱 이름. v1 덱과 같이 견주려면 갈라라")
    parser.add_argument("--out", default=None, help="출력 apkg 경로")
    parser.add_argument("--index", action="store_true",
                        help="runs/INDEX.md에도 쓴다. 같은 lecture_id의 v1 줄을 덮어쓴다")
    args = parser.parse_args()

    with timings.stage(Path(args.run_dir), "5-build", label=args.items):
        meta = build_run(Path(args.run_dir), args.items, args.project, args.out, args.index)

    print(f"[build] {meta['deck_name']}")
    for name, count in meta.get("decks", {}).items():
        print(f"    └ {name.split('::')[-1]:<8} {count}장")
    fmt = " / ".join(f"{k} {v}" for k, v in meta["card_formats"].items() if v)
    print(f"  {meta['item_count']}장 ({fmt})")
    print(f"  출처: 강의록 {meta['sources']['lecture']} / 족보 {meta['sources']['jokbo']}")
    print(f"  중요도: core {meta['importance']['core']} / detail {meta['importance']['detail']}")
    print(f"  출제 이력: exam_hit {meta['exam_hit']} / stamp {meta['stamped']}")
    print(f"  유형: { {k: v for k, v in meta['card_types'].items() if v} }")

    rep = meta["reproduce"]
    print(f"\n  뒷면 빨간 박스 {meta['review_boxed']}장 — 셋이 다른 것을 의심한다")
    flags = " · ".join(f"{k} {v}" for k, v in meta["review_flags"].items() if v) or "없음"
    print(f"    족보 검토  {meta['review_flagged']:>3}장  ({flags})")
    print(f"    재현 주의  {rep['partial'] + rep['different']:>3}장  "
          f"(일부 {rep['partial']} · 다름 {rep['different']} · "
          f"자족성 실패 {rep['unanswerable']})")
    print(f"    자료 주의  {meta['source_warned']:>3}장")
    if rep.get("occlusion_exempt"):
        print(f"    (오클루전 {rep['occlusion_exempt']}장은 재현 검사에서 뺐다 — "
              f"앞면에 그림이 떠야 서는 카드다)")
    if rep["unscored"]:
        print(f"    ! 재현 검사를 안 거친 카드 {rep['unscored']}장 — "
              f"reproduce score --apply 를 먼저 돌렸는지 보라")

    print(f"\n  이미지 오클루전 {meta['occlusion']}장")
    print(f"  슬라이드 {len(meta['slides_used'])}장 사용, 미사용 {meta['slides_unused']}")
    v = meta["verified"]
    print(f"  apkg 검증: 노트 {v['notes']} / 카드 {v['cards']} / 미디어 {v['media']}"
          f" ({v['collection']})")
    print(f"  → {meta['apkg']}")
    if meta.get("index_path"):
        print(f"  대장: {meta['index_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
