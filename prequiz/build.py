"""4단계: 확정된 예습 문항 + 슬라이드 이미지 → .apkg

    python prequiz/build.py runs/250813_02

입력  pre_items.final.json  (감사 ③이 확정한 문항)
      prep.json             (slide_image_map)
출력  <lecture_id>_예습.apkg, pre_run.meta.json

선지 번호(①②③④⑤)와 정답 표시는 전부 여기서 붙인다. 모델은 선지 본문과
정답 인덱스까지만 책임진다. 번호를 모델이 적게 하면 선지 순서를 바꿀 때마다
번호와 정답이 어긋난다.

`quiz/build.py`와 마찬가지로, slide_no에 해당하는 이미지가 없을 때 '가장 가까운
슬라이드'로 대체하지 않는다. 문항은 맞는데 그림만 다른 카드를 조용히 만들어
잘못된 연결을 학습시키기 때문이다. 실패로 처리하고 어느 문항인지 이름을 댄다.
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

from prequiz.notetype import get_anki_model  # noqa: E402
from prequiz.validate import check_item  # noqa: E402
from quiz.notetype import deck_component  # noqa: E402
from quiz.textutil import (  # noqa: E402
    escape_field,
    normalize_display_newlines,
    safe_filename,
    stable_int_id,
)
from quiz.verify import verify_apkg  # noqa: E402

DEFAULT_PROJECT = "병리학"
DECK_LEAF = "예습확인"

CHOICE_NUMERALS = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧"]
# OX도 선지가 보이는 편이 낫다. 무엇에 O/X를 하는 건지가 앞면에서 분명해진다.
OX_CHOICES = ["맞다 (O)", "틀리다 (X)"]

QTYPE_LABELS = {"mcq": "객관식", "short": "단답", "ox": "OX"}
FOCUS_LABELS = {"must_know": "필수", "core": "핵심", "context": "맥락"}


def _numeral(index: int) -> str:
    """1-based 선지 번호 → ①②③… 범위를 넘으면 그냥 숫자로."""
    return CHOICE_NUMERALS[index - 1] if 1 <= index <= len(CHOICE_NUMERALS) else f"{index}."


def display_choices(item: dict) -> tuple[list[str], int | None]:
    """(화면에 뿌릴 선지 목록, 정답의 1-based 위치). 단답이면 ([], None)."""
    qtype = str(item.get("qtype") or "").strip().lower()
    if qtype == "mcq":
        choices = [str(c).strip() for c in (item.get("choices") or [])]
        return choices, int(item["answer"])
    if qtype == "ox":
        return list(OX_CHOICES), 1 if str(item["answer"]).strip().upper() == "O" else 2
    return [], None


def render_choice_list(choices: list[str], correct: int | None, mark: bool) -> str:
    """선지 <ol>. mark=True면 정답 <li>에 correct 클래스를 붙인다."""
    if not choices:
        return ""
    rows = []
    for i, choice in enumerate(choices, start=1):
        cls = ' class="correct"' if mark and i == correct else ""
        rows.append(f'<li{cls}><span class="num">{_numeral(i)}</span>{escape_field(choice)}</li>')
    return '<ol class="choices">' + "".join(rows) + "</ol>"


def answer_text(item: dict) -> str:
    """뒷면 정답 줄. 객관식·OX는 번호와 본문을 함께 보여준다."""
    choices, correct = display_choices(item)
    if choices and correct and 1 <= correct <= len(choices):
        return f"{_numeral(correct)} {choices[correct - 1]}"
    return normalize_display_newlines(item.get("answer", ""))


def _explanation_field(item: dict) -> str:
    """해설 + 근거 한 줄. 근거는 예습 때 어느 슬라이드로 돌아갈지의 좌표다."""
    parts = []
    explanation = normalize_display_newlines(item.get("explanation", ""))
    if explanation:
        parts.append(explanation)
    anchor = str(item.get("source_anchor") or "").strip()
    if anchor:
        parts.append(f"근거: Slide {item.get('slide_no')} {anchor}")
    return normalize_display_newlines("\n\n".join(parts))


def build_notes(items: list[dict], slide_image_map: dict[int, str], lecture_id: str):
    model = get_anki_model()
    notes, used_slides = [], set()
    stats = {q: 0 for q in QTYPE_LABELS}
    for item in items:
        slide_no = int(item["slide_no"])
        img_name = slide_image_map[slide_no]
        used_slides.add(slide_no)

        qtype = str(item.get("qtype") or "short").strip().lower()
        stats[qtype] = stats.get(qtype, 0) + 1
        focus = str(item.get("focus") or "core").strip().lower()

        stem = normalize_display_newlines(item["stem"])
        choices, correct = display_choices(item)

        source_type = str(item.get("source_type") or "lecture").strip().lower()
        tags = [
            f"focus_{safe_filename(focus)}",
            f"qtype_{safe_filename(qtype)}",
            f"source_{safe_filename(source_type)}",
            f"lecture_{safe_filename(lecture_id)}",
            f"slide_{slide_no:03d}",
            "prequiz",
        ]
        if item.get("exam_hit"):
            tags.append("exam_hit")

        notes.append(genanki.Note(
            model=model,
            fields=[
                escape_field(stem),
                render_choice_list(choices, correct, mark=False),
                render_choice_list(choices, correct, mark=True),
                escape_field(answer_text(item)),
                escape_field(_explanation_field(item)),
                str(slide_no),
                f'<img src="{img_name}">',
                QTYPE_LABELS.get(qtype, qtype),
                FOCUS_LABELS.get(focus, focus),
            ],
            tags=tags,
        ))
    return notes, used_slides, stats


def build_run(run_dir: Path, items_name: str, project: str, output: Path | None) -> dict:
    from quiz.validate import authoritative_ranges

    run_dir = Path(run_dir)
    prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))
    num_pages = int(prep["num_pages"])
    # 구간의 주인은 structure.json이다. prep.json은 힌트다.
    lecture_range, jokbo_range, _ = authoritative_ranges(run_dir, prep)
    slide_image_map = {int(k): v for k, v in prep["slide_image_map"].items()}
    media_dir = Path(prep["media_dir"])

    payload = json.loads((run_dir / items_name).read_text(encoding="utf-8"))
    items = payload["items"] if isinstance(payload, dict) else payload

    # 감사가 문항을 고쳤을 수 있으므로 같은 규칙으로 한 번 더 본다.
    # "모델이 무언가 반환했다"를 "문제가 해결됐다"로 간주하지 않는다.
    blocked = []
    for item in items:
        hard, _ = check_item(item, num_pages, jokbo_range)
        if int(item.get("slide_no") or 0) not in slide_image_map:
            hard.append("slide_image_missing")
        if hard:
            blocked.append({"id": item.get("id"), "stem": item.get("stem"), "reason": hard})
    if blocked:
        lines = [f"  - {b['id']}: {', '.join(b['reason'])} | {str(b['stem'])[:60]}" for b in blocked]
        raise SystemExit(
            f"빌드 중단: {len(blocked)}문항이 하드 규칙을 통과하지 못했습니다.\n"
            + "\n".join(lines)
            + "\n감사 단계로 되돌려 고치거나 해당 문항을 삭제하세요."
        )

    lecture_id = prep["lecture_id"]
    deck_title = f"[{lecture_id}] {prep['lecture_title']}"
    # 시험 대비 덱과 같은 강의 아래에 붙되 하위 덱으로 갈라 둔다. 예습은 강의 전에
    # 한 번 돌리고 끝이라 시험 덱과 학습 스케줄이 섞이면 곤란하다.
    deck_name = "::".join([
        deck_component(project, "프로젝트"),
        deck_component(deck_title, "강의"),
        DECK_LEAF,
    ])
    deck = genanki.Deck(stable_int_id(f"deck:prequiz:{project}:{lecture_id}"), deck_name)

    notes, used_slides, stats = build_notes(items, slide_image_map, lecture_id)
    for note in notes:
        deck.add_note(note)

    # 실제로 쓰인 슬라이드만 넣는다. 전체를 넣으면 안 쓰는 이미지가 쌓인다.
    media_files = [str((media_dir / slide_image_map[s]).resolve()) for s in sorted(used_slides)]
    output = Path(output) if output else run_dir / f"{safe_filename(deck_title)}_예습.apkg"
    package = genanki.Package([deck])
    package.media_files = media_files
    package.write_to_file(str(output))

    # 쓴 파일을 도로 열어 실제 내용물을 센다. genanki의 성공 반환은 덱이
    # 온전하다는 뜻이 아니다 - 미디어가 빠져도 write_to_file은 성공한다.
    verified = verify_apkg(output, len(notes), [Path(p).name for p in media_files])

    lecture_lo, lecture_hi = lecture_range or [1, num_pages]
    meta = {
        "lecture_id": lecture_id,
        "deck_name": deck_name,
        "verified": verified,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "apkg": str(output.resolve()),
        "item_count": len(items),
        "qtypes": stats,
        "focus": {
            key: sum(1 for i in items if str(i.get("focus", "core")).lower() == key)
            for key in ("must_know", "core", "context")
        },
        "sources": {
            key: sum(1 for i in items if str(i.get("source_type", "lecture")).lower() == key)
            for key in ("lecture", "jokbo")
        },
        "exam_hit": sum(1 for i in items if i.get("exam_hit")),
        "lecture_range": [int(lecture_lo), int(lecture_hi)],
        "slides_used": sorted(used_slides),
        # 커버리지는 강의록 구간 기준이다. 족보 슬라이드는 중심 흐름과 겹칠 때만
        # 쓰므로 안 쓴 것이 누락이 아니다.
        "slides_uncovered": [s for s in range(int(lecture_lo), int(lecture_hi) + 1)
                             if s not in used_slides],
        "media_count": len(media_files),
    }
    (run_dir / "pre_run.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description="예습퀴즈 파이프라인 4단계: Anki 덱 빌드")
    parser.add_argument("run_dir", help="runs/<lecture_id>")
    parser.add_argument("--items", default="pre_items.final.json", help="빌드할 파일명")
    parser.add_argument("--project", default=DEFAULT_PROJECT, help="상위 덱 이름")
    parser.add_argument("--out", default=None, help="출력 apkg 경로")
    args = parser.parse_args()

    meta = build_run(Path(args.run_dir), args.items, args.project, args.out)
    q, f, src = meta["qtypes"], meta["focus"], meta["sources"]
    print(f"[pre-build] {meta['deck_name']}")
    print(f"  {meta['item_count']}문항 (객관식 {q.get('mcq', 0)} / 단답 {q.get('short', 0)}"
          f" / OX {q.get('ox', 0)})")
    print(f"  예습 비중: 필수 {f['must_know']} / 핵심 {f['core']} / 맥락 {f['context']}"
          f"  |  출처: 강의록 {src['lecture']} / 족보 {src['jokbo']}"
          f"  |  족보가 물었던 지점 {meta['exam_hit']}")
    print(f"  강의록 {meta['lecture_range'][0]}-{meta['lecture_range'][1]} 중"
          f" {len(meta['slides_used'])}장 사용")
    print(f"  문항이 없는 슬라이드: {meta['slides_uncovered']}")
    v = meta["verified"]
    print(f"  apkg 검증: 노트 {v['notes']} / 카드 {v['cards']} / 미디어 {v['media']}"
          f" ({v['collection']})")
    print(f"  → {meta['apkg']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
