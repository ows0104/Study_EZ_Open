"""1단계: PDF → 모델 입력 자료 + Anki 미디어.

    python quiz/prep.py "2025 필기/[250813_02]세포의 손상 및 적응(1)(고지원)_장원영v1.pdf"

만들어지는 것 (runs/<lecture_id>/):
    model_pages/*.png 강의록 구간. annotation 제거 + Slide N 각인. 사실을 읽는 채널
    jokbo_pages/*.png 족보 구간. annotation 포함 + Slide N 각인
    model_input.pdf   강의록 clean 판본의 PDF (PDF 페이지 렌더가 되는 환경용)
    annotated.pdf     원본 그대로 + Slide N 각인
    media/*.png       원본(필기 포함) 슬라이드 렌더. Anki 카드 뒷면에 들어간다
    outline.json      슬라이드별 제목·본문 앞부분·글자 수
    annotations.json  슬라이드별 필기/형광펜/도장 신호 (중요도 힌트, 근거 아님)
    labels.json       슬라이드별 라벨 후보와 정확한 bbox. 이미지 오클루전 카드용
    prep.json         위 전부의 인덱스. 이후 단계가 읽는 계약 파일

족보 문항은 PDF annotation(이미지)으로만 존재하는 경우가 있다. 그 구간을 clean
채널로 읽으면 백지가 되어 기출이 통째로 사라진다. 그래서 족보 구간은 annotated
렌더를 따로 만든다.

LLM 호출 없음.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows 콘솔 기본 cp949로는 한글 로그가 깨지거나 UnicodeEncodeError로 죽는다.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from quiz.occlusion import extract_labels  # noqa: E402
from quiz.structure import page_features, suggest_jokbo_start  # noqa: E402
from quiz.render import (  # noqa: E402
    make_annotation_clean_pdf,
    make_labeled_pdf,
    make_page_range_pdf,
    render_flattened_labeled_pngs,
    render_slide_pngs,
    validate_slide_image_map,
)
from quiz.textutil import (  # noqa: E402
    lecture_id_from_stem,
    lecture_title_from_stem,
    safe_media_prefix,
)

# Read 툴이 PDF에서 한 번에 가져올 수 있는 최대 페이지 수. 모델 입력을 이 크기로
# 나눠 읽도록 prep.json에 창(window)을 미리 계산해 둔다.
READ_WINDOW = 20

# 모델이 읽을 clean 슬라이드 PNG 배율. Anki 미디어(2.0)보다 낮게 잡는다 - 모델은
# 본문·표·그림 라벨을 읽기만 하면 되고, 인쇄 품질은 카드에 들어가는 쪽만 필요하다.
MODEL_PAGE_SCALE = 1.6

# annotation 종류 → 우선순위 신호. 원본 파이프라인의 분류를 따른다.
# 이건 '무엇이 중요한가'의 힌트일 뿐, 절대 정답의 근거가 아니다.
_ANNOT_SIGNAL = {
    "Highlight": "highlight",
    "Square": "red_box",
    "Circle": "red_box",
    "Underline": "underline",
    "Squiggly": "underline",
    "StrikeOut": "strikeout",
    "FreeText": "student_note",
    "Text": "student_note",
    "Ink": "student_note",
    "Stamp": "stamp",
    "Line": "student_note",
}

# 색은 수집하지 않는다.
#
# 필기자마다 도구도 규약도 달라서 같은 색이 정반대를 뜻한다. 병리학 2026 15편에서만
# 서로 다른 색이 31종 나왔고, 1페이지에 "중요한 내용은 빨간색" 같은 규약을 적어 두는
# 사람도 있지만 그것도 그 사람 것이다. 회색이 사담일 때도, "이 부분은 시험에 안 낸다고
# 하셨습니다" 같은 결정적인 말일 때도 있다.
#
# 뜻은 색이 아니라 **글에 있다.** 그래서 FreeText의 본문(`notes`)은 그대로 싣고
# 색은 버린다. 남겨 두면 쓰이고, 쓰이면 근거로 둔갑한다.


def extract_outline(doc) -> list[dict]:
    """슬라이드별 제목과 본문 앞부분. 청사진 단계에서 전체 구조를 잡는 데 쓴다."""
    outline = []
    for i in range(len(doc)):
        text = doc.load_page(i).get_text("text") or ""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        outline.append({
            "slide_no": i + 1,
            "title": lines[0][:120] if lines else "",
            "head": " / ".join(lines[1:4])[:300],
            "chars": len(text.strip()),
        })
    return outline


def extract_annotations(doc) -> list[dict]:
    """슬라이드별 필기 신호. 종류와 본문(FreeText)을 수집한다.

    색은 싣지 않는다 - 위의 주석을 보라. 뜻은 색이 아니라 `notes`의 글에 있다.
    """
    result = []
    for i in range(len(doc)):
        page = doc.load_page(i)
        signals: dict[str, int] = {}
        notes: list[str] = []
        try:
            annots = list(page.annots() or [])
        except Exception:
            annots = []
        for annot in annots:
            try:
                type_name = annot.type[1]
            except Exception:
                continue
            signal = _ANNOT_SIGNAL.get(type_name, "annotation")
            # 붙여넣은 이미지도 Stamp다. 그걸 출제 이력 도장으로 세면 신호가
            # 오염된다 - 260813_03에서 Stamp 69개 중 35개가 클립보드였다.
            # stamp는 "교수가 강조했다"는 뜻이어야 하고, 스킬이 그걸 frequent의
            # 근거로 쓴다.
            if signal == "stamp":
                name = str((annot.info or {}).get("name", "")).lower()
                if name.startswith("clipboard.image"):
                    signal = "pasted_image"
            signals[signal] = signals.get(signal, 0) + 1
            try:
                content = (annot.info or {}).get("content", "").strip()
            except Exception:
                content = ""
            if content:
                notes.append(content[:200])
        if signals or notes:
            result.append({
                "slide_no": i + 1,
                "signals": signals,
                # 필기자의 말은 그대로 싣는다. "이 부분은 시험에 안 낸다고 하셨습니다"
                # 같은 문장이 여기 있고, 그건 어떤 색보다 확실한 신호다.
                "notes": notes[:12],
            })
    return result


def read_windows(num_pages: int, size: int = READ_WINDOW) -> list[str]:
    return [f"{s}-{min(s + size - 1, num_pages)}" for s in range(1, num_pages + 1, size)]


# 앞에서 훑으며 족보 시작 문구를 찾던 `detect_jokbo_start`는 지웠다.
# 족보는 꼬리에 붙은 연속 블록이라 뒤에서부터 세는 편이 경계의 정의에 맞고,
# 실측에서도 그쪽이 이겼다(정답 아는 2건: 뒤에서 2/2, 앞에서 0/2).
# 힌트는 quiz/structure.py의 suggest_jokbo_start가 낸다.


def prep_external_jokbo(jokbo_pdf: Path, run_dir: Path, media_dir: Path, prefix: str,
                        first_slide: int, scale: float) -> dict:
    """과목 족보 폴더에서 잘라온 원본 PDF를 족보 채널로 붙인다.

    필기 뒤에 붙은 캡처본보다 이쪽이 낫다 - 원본이라 화질이 고르고 텍스트 레이어가
    살아 있다. 다만 원본 족보가 없는 과목·연도가 있어서 **옵션**이다.

    번호는 필기에 이어서 준다. 필기가 N장이면 족보는 N+1부터다. 그래야
    `slide_no` 하나로 두 채널을 다 가리킬 수 있고, 검증·빌드가 손댈 것 없이 돈다.
    """
    jokbo_pdf = Path(jokbo_pdf).resolve()
    if not jokbo_pdf.exists():
        raise FileNotFoundError(f"족보 PDF를 찾을 수 없습니다: {jokbo_pdf}")

    # 원본 족보의 진짜 값어치는 **텍스트 레이어**다. 필기에 붙은 캡처본은 문항이
    # 이미지뿐이라 모델이 그림을 읽어야 했지만, 교실이 공개한 원본은 평균
    # 1,600자/쪽의 텍스트를 들고 있다. 문항·선지·정답을 글로 읽으면 훨씬 싸고
    # 정확하다.
    #
    # 이미지도 함께 남긴다 - "아래 왼쪽은 정상 전립선 사진이고" 같은 그림 문항이
    # 있어서 텍스트만으로는 죽는다. 글이 주고 그림이 보조다.
    lines: list[str] = []
    with fitz.open(str(jokbo_pdf)) as doc:
        pages = len(doc)
        for index, page in enumerate(doc):
            text = (page.get_text() or "").strip()
            lines.append(f"## Slide {first_slide + index}\n")
            lines.append(text if text else "(텍스트 없음 — jokbo_pages 이미지를 읽어라)")
            lines.append("")
    if pages < 1:
        raise ValueError(f"족보 PDF가 비어 있습니다: {jokbo_pdf}")

    text_path = run_dir / "jokbo_text.md"
    text_path.write_text(
        f"# 족보 원문 — {jokbo_pdf.name}\n\n"
        "슬라이드 번호는 필기 뒤에 이어 붙인 가상 번호다. 그림이 필요한 문항은\n"
        "`jokbo_pages/jokbo_sNNN.png`를 함께 보라.\n\n" + "\n".join(lines),
        encoding="utf-8")

    last_slide = first_slide + pages - 1
    jokbo_pages_dir = run_dir / "jokbo_pages"
    page_map = render_flattened_labeled_pngs(
        jokbo_pdf, jokbo_pages_dir, "jokbo", slide_start=first_slide, scale=MODEL_PAGE_SCALE)
    media_files, image_map = render_slide_pngs(
        jokbo_pdf, media_dir, f"{prefix}_jokbo", scale=scale, slide_start=first_slide)

    return {
        "source": str(jokbo_pdf),
        "pages": pages,
        "range": [first_slide, last_slide],
        "pages_dir": jokbo_pages_dir,
        "page_map": page_map,
        "media_files": media_files,
        "image_map": image_map,
        "text_path": text_path,
        "chars": sum(len(line) for line in lines),
    }


def prep(pdf_path: Path, out_root: Path, scale: float, jokbo_start_override: int | None = None,
         run_id: str | None = None, jokbo_pdf: Path | None = None) -> dict:
    """`run_id`를 주면 그 이름으로 디렉터리를 만든다.

    파일명만으로는 부족할 때가 있다. 선택형 과목은 한 교시에 여러 강의가 열려
    `260303_02`에 서로 다른 강의 세 편이 들어오는데, 그대로 두면 한 디렉터리를
    나눠 쓰면서 뒤 강의가 앞 강의를 덮어쓴다. 겹치는지 아는 건 폴더 전체를 본
    워처뿐이라, 이름을 정하는 일은 그쪽에 맡긴다.
    """
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF를 찾을 수 없습니다: {pdf_path}")

    lecture_id = run_id or lecture_id_from_stem(pdf_path.stem)
    lecture_title = lecture_title_from_stem(pdf_path.stem)
    run_dir = Path(out_root) / lecture_id
    media_dir = run_dir / "media"
    run_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    num_pages = len(doc)
    outline = extract_outline(doc)
    annotations = extract_annotations(doc)
    doc.close()
    if num_pages == 0:
        raise ValueError("페이지가 없는 PDF입니다.")

    # 사실 채널: annotation 제거 → Slide N 각인
    clean_tmp = run_dir / "_clean_tmp.pdf"
    removed = make_annotation_clean_pdf(pdf_path, clean_tmp)
    model_input = run_dir / "model_input.pdf"
    make_labeled_pdf(clean_tmp, model_input, slide_start=1)
    clean_tmp.unlink(missing_ok=True)

    # PDF를 페이지 이미지로 렌더하지 못하는 환경(poppler 미설치 등)에서는 모델이
    # model_input.pdf를 못 읽고 필기가 살아 있는 media/를 대신 읽어버린다. 그러면
    # 이 파이프라인의 핵심인 사실/신호 채널 분리가 조용히 무너진다. clean PNG를
    # 미리 뽑아두어 그 우회로를 없앤다.
    model_pages_dir = run_dir / "model_pages"
    _, model_page_map = render_slide_pngs(
        model_input, model_pages_dir, "clean", scale=MODEL_PAGE_SCALE)
    validate_slide_image_map(model_page_map, model_pages_dir, num_pages)

    # 신호 채널: 원본 그대로 + 각인.
    annotated = run_dir / "annotated.pdf"
    make_labeled_pdf(pdf_path, annotated, slide_start=1)

    # 족보 구간: 문항이 annotation 안에만 있을 수 있으므로 annotated 렌더를 쓴다.
    # clean 채널만 쓰면 이 페이지들이 백지가 되어 기출이 통째로 사라진다.
    #
    # 여기서 나오는 값은 **힌트**다. 경계를 실제로 정하는 건 structure.json(모델)이고,
    # 코드는 quiz/structure.py의 verify()로 그 판정을 따진다.
    #
    # 족보는 꼬리에 붙은 연속 블록이므로 **뒤에서부터** 거슬러 올라간다. 앞에서
    # 훑으며 "여기서부터 족보인가"를 묻던 방식은 본문의 숫자·낱말에 걸려 번번이
    # 늦게 멈췄다 - 정답을 아는 두 건에서 둘 다 한 쪽씩 밀렸다.
    features = page_features(pdf_path)

    # 외부 족보를 쓰더라도 **필기 자신의 족보 꼬리는 그대로 있다.** 필기자가
    # 기출을 캡처해 뒤에 붙여 두기 때문이다. 실측(260812_02)에서 필기 26-33의
    # 캡처와 외부 족보의 문항이 상당수 겹쳤다. 필기를 통째로 강의록으로 치면
    # 기출 8쪽이 강의록 근거로 둔갑한다.
    if jokbo_start_override:
        jokbo_hint, jokbo_reason = int(jokbo_start_override), "수동 지정"
    else:
        jokbo_hint = suggest_jokbo_start(features)
        jokbo_reason = (f"뒤에서부터 훑어 슬라이드 {jokbo_hint}까지 기출 근거가 이어짐"
                        if jokbo_hint else "기출 근거를 찾지 못함")

    # 뒤 절반은 힌트와 무관하게 항상 렌더한다. 그래야 모델이 경계를 옮겨도 다시
    # 렌더하지 않는다 - model_pages는 이미 전 페이지를 덮고 있으므로, 이걸로
    # 경계가 순수한 포인터가 된다.
    render_from = max(2, min(jokbo_hint or num_pages, (num_pages // 2) + 1))
    jokbo_pages_dir = run_dir / "jokbo_pages"
    jokbo_page_map: dict[int, str] = {}
    if num_pages >= 6:
        tmp_pdf = run_dir / "_jokbo_tmp.pdf"
        # 원본에서 잘라낸다. annotated.pdf를 쓰면 각인이 두 번 들어간다.
        make_page_range_pdf(pdf_path, tmp_pdf, render_from, num_pages)
        # 평탄화 후 각인. 그러지 않으면 라벨이 족보 이미지 annotation에 가려진다.
        jokbo_page_map = render_flattened_labeled_pngs(
            tmp_pdf, jokbo_pages_dir, "jokbo", slide_start=render_from, scale=MODEL_PAGE_SCALE)
        tmp_pdf.unlink(missing_ok=True)

    external = None
    if jokbo_pdf:
        external = prep_external_jokbo(
            jokbo_pdf, run_dir, media_dir, safe_media_prefix(pdf_path.stem),
            first_slide=num_pages + 1, scale=scale)
        jokbo_reason += f" · 외부 족보 덧붙임: {Path(jokbo_pdf).name}"
        jokbo_page_map = {**jokbo_page_map, **external["page_map"]}

    # Anki 미디어는 원본(필기 포함)에서 렌더한다. 복습 카드 뒷면에서 교수 강조가
    # 보이는 편이 낫고, 이 이미지는 모델 입력이 아니라 사람이 보는 확인용이다.
    prefix = safe_media_prefix(pdf_path.stem)
    media_files, slide_image_map = render_slide_pngs(pdf_path, media_dir, prefix, scale=scale)
    # 여기서는 아직 검증하지 않는다. 외부 족보를 붙이면 번호가 필기 뒤로
    # 이어져서, 합친 뒤에 한 번만 본다(아래).

    # 이미지 오클루전용 라벨 후보. 원본 PDF에서 뽑아야 미디어 렌더와 좌표가 맞는다.
    # 강의록 구간만 본다 - 족보 구간은 문항 이미지라 가릴 라벨이 없다.
    labels = extract_labels(pdf_path, tuple(
        [1, (jokbo_hint - 1) if jokbo_hint else num_pages]))

    lecture_range = [1, (jokbo_hint - 1) if jokbo_hint else num_pages]
    if external:
        # 필기의 족보 꼬리와 외부 족보는 가상 번호에서 맞닿는다(꼬리가 N에서
        # 끝나고 외부가 N+1에서 시작). 그래서 둘을 한 구간으로 이어 붙일 수 있고,
        # 검증·빌드의 단일 범위 검사가 그대로 돈다.
        jokbo_range = [jokbo_hint or (num_pages + 1), external["range"][1]]
        total_slides = external["range"][1]
        media_files = media_files + external["media_files"]
        slide_image_map = {**slide_image_map, **external["image_map"]}
    else:
        jokbo_range = [jokbo_hint, num_pages] if jokbo_hint else None
        total_slides = num_pages

    validate_slide_image_map(slide_image_map, media_dir, total_slides)

    manifest = {
        "lecture_id": lecture_id,
        "lecture_title": lecture_title,
        "source_pdf": str(pdf_path),
        "source_stem": pdf_path.stem,
        "num_pages": num_pages,
        "prepared_at": datetime.now().isoformat(timespec="seconds"),
        "annotations_removed": removed,
        "model_input_pdf": str(model_input),
        "model_pages_dir": str(model_pages_dir),
        "model_pages": [str(model_pages_dir / model_page_map[s]) for s in sorted(model_page_map)],
        "annotated_pdf": str(annotated),
        # 외부 족보를 쓰면 경계가 확정이고, 아니면 힌트다.
        # 어느 쪽이든 최종 주인은 structure.json이다.
        "jokbo_source": "external" if external else "embedded",
        "jokbo_pdf": external["source"] if external else None,
        # 원본 족보의 원문. 글이 주고 이미지가 보조다.
        "jokbo_text_path": str(external["text_path"]) if external else None,
        "jokbo_hint": jokbo_hint,
        "jokbo_detection": jokbo_reason,
        "lecture_range": lecture_range,
        "jokbo_range": jokbo_range,
        "total_slides": total_slides,
        "jokbo_pages_dir": str(jokbo_pages_dir) if jokbo_page_map else None,
        "jokbo_rendered_from": render_from if jokbo_page_map else None,
        "jokbo_pages": [str(jokbo_pages_dir / jokbo_page_map[s]) for s in sorted(jokbo_page_map)],
        "page_features_path": str(run_dir / "page_features.json"),
        "media_dir": str(media_dir),
        "media_files": media_files,
        "slide_image_map": {str(k): v for k, v in slide_image_map.items()},
        "read_windows": read_windows(total_slides),
        "outline_path": str(run_dir / "outline.json"),
        "annotations_path": str(run_dir / "annotations.json"),
        "labels_path": str(run_dir / "labels.json"),
        "label_count": labels["label_count"],
    }

    (run_dir / "outline.json").write_text(
        json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "annotations.json").write_text(
        json.dumps(annotations, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "labels.json").write_text(
        json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "page_features.json").write_text(
        json.dumps([asdict(f) for f in features], ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "prep.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="퀴즈 파이프라인 1단계: PDF 준비")
    parser.add_argument("pdf", help="강의 PDF 경로")
    parser.add_argument("--out", default="runs", help="출력 루트 (기본: runs)")
    parser.add_argument("--scale", type=float, default=2.0, help="슬라이드 PNG 배율 (기본: 2.0)")
    parser.add_argument("--jokbo-start", type=int, default=None,
                        help="족보 시작 슬라이드 번호를 직접 지정 (힌트를 덮어씀)")
    parser.add_argument("--run-id", default=None,
                        help="출력 디렉터리 이름 (기본: 파일명의 강의 코드)")
    parser.add_argument("--jokbo-pdf", default=None,
                        help="과목 족보에서 잘라온 원본 PDF. 주면 필기 뒤의 캡처본 대신 "
                             "이걸 족보 채널로 쓰고, 경계 판정이 필요 없어진다")
    args = parser.parse_args()

    manifest = prep(Path(args.pdf), Path(args.out), args.scale, args.jokbo_start, args.run_id,
                    Path(args.jokbo_pdf) if args.jokbo_pdf else None)
    annots = json.loads(Path(manifest["annotations_path"]).read_text(encoding="utf-8"))
    stamped = [a["slide_no"] for a in annots if "stamp" in a["signals"]]
    print(f"[prep] {manifest['lecture_id']} : {manifest['lecture_title']}")
    print(f"  슬라이드 {manifest['num_pages']}장, annotation {manifest['annotations_removed']}개 제거")
    print(f"  필기 신호 {len(annots)}장 / 족보 도장(stamp) {len(stamped)}장: {stamped}")
    print(f"  전 페이지 clean → {manifest['model_pages_dir']} ({len(manifest['model_pages'])}장)")
    if manifest["jokbo_pages"] and manifest["jokbo_rendered_from"]:
        print(f"  뒤쪽 annotated → {manifest['jokbo_pages_dir']} "
              f"({manifest['jokbo_rendered_from']}쪽부터 {len(manifest['jokbo_pages'])}장)")
    elif manifest["jokbo_pages"]:
        print(f"  족보 annotated → {manifest['jokbo_pages_dir']} "
              f"({len(manifest['jokbo_pages'])}장)")
    if manifest["jokbo_source"] == "external":
        lo, hi = manifest["jokbo_range"]
        pages = manifest["num_pages"]
        print(f"  족보: 필기 꼬리 {lo}-{pages} + 원본 {pages + 1}-{hi}"
              f" ({Path(manifest['jokbo_pdf']).name})")
        text_path = Path(manifest["jokbo_text_path"])
        print(f"        원본 원문 {len(text_path.read_text(encoding='utf-8')):,}자 → {text_path.name}")
        print(f"  ※ 필기 꼬리의 시작({lo})은 여전히 힌트다 — 필기자가 기출을 캡처해 "
              "붙여 두므로 0.5단계가 확정해야 한다")
    else:
        hint = manifest["jokbo_hint"]
        print(f"  족보 힌트: {hint if hint else '없음'} — {manifest['jokbo_detection']}")
        print("  ※ 힌트일 뿐이다. 경계는 0.5단계가 structure.json으로 정하고 "
              "quiz/structure.py가 검증한다")
    labels = json.loads(Path(manifest["labels_path"]).read_text(encoding="utf-8"))
    figure_slides = sorted(
        int(s) for s, v in labels["slides"].items()
        if sum(1 for e in v if e["kind"] == "label") >= 4
    )
    print(f"  오클루전 라벨 후보 {manifest['label_count']}개 / 라벨 많은 슬라이드: {figure_slides}")
    print(f"  미디어: {manifest['media_dir']} ({len(manifest['media_files'])}장)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
