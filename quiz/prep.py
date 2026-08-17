"""1단계: PDF → 모델 입력 자료 + Anki 미디어.

    python quiz/prep.py "2025 필기/[250813_02]세포의 손상 및 적응(1)(고지원)_장원영v1.pdf"

만들어지는 것 (runs/<lecture_id>/):
    model_input.pdf   필기를 지운 판본 + Slide N 각인. **사실을 읽는 채널**
    annotated.pdf     원본 그대로 + Slide N 각인. **족보를 읽는 채널**
    jokbo_input.pdf   외부 족보 PDF + 각인(번호는 필기 뒤에 이어서). 줬을 때만
    jokbo_text.md     외부 족보의 원문 텍스트. 줬을 때만
    media/*.png       원본(필기 포함) 슬라이드 렌더. Anki 카드 뒷면에 들어간다
    outline.json      슬라이드별 제목·본문 앞부분·글자 수
    annotations.json  슬라이드별 필기/형광펜/도장 신호 (중요도 힌트, 근거 아님)
    labels.json       슬라이드별 라벨 후보와 정확한 bbox. 이미지 오클루전 카드용
    prep.json         위 전부의 인덱스. 이후 단계가 읽는 계약 파일

족보 문항은 PDF annotation(이미지)으로만 존재하는 경우가 있다. 그 구간을 clean
채널로 읽으면 백지가 되어 기출이 통째로 사라진다. 그래서 원본 그대로인
`annotated.pdf`를 함께 낸다. 두 판본은 쪽 수가 같고 offset도 없다 - 슬라이드 N이
양쪽에서 N쪽이다.

**모델은 이 PDF들을 Read의 `pages`로 직접 읽는다.** 예전에는 슬라이드마다 PNG를
미리 뽑아 뒀는데(`model_pages/`·`jokbo_pages/`, 편당 19MB) 그럴 필요가 없어졌다.
`pages` 경로는 쪽 번호를 돌려주지 않으므로 슬라이드 번호는 각인이 나른다.

LLM 호출 없음.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
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
from quiz.structure import page_features  # noqa: E402
from quiz.render import (  # noqa: E402
    make_annotation_clean_pdf,
    make_labeled_pdf,
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


def poppler_available() -> bool:
    """Read의 `pages` 경로가 쓸 수 있는 상태인가.

    2·4단계는 PDF의 쪽 범위를 `pages`로 읽고, 그 경로는 `pdftoppm`(poppler)으로
    래스터화한다. **prep 자체는 PyMuPDF만 쓰므로 poppler가 없어도 성공한다** -
    그래서 없다는 사실이 한참 뒤 조각 에이전트에서야 드러난다. 여기서 표시해 둔다.

    **막지는 않는다.** `pages`를 생략한 통째 읽기는 poppler가 필요 없어서 0.5·1단계는
    그대로 돌고, 무엇을 포기할지는 사람이 정할 일이다. 코드는 세어서 표시만 한다.
    """
    return shutil.which("pdftoppm") is not None


def read_windows(num_pages: int, total_slides: int, size: int = READ_WINDOW) -> list[str]:
    """`pages`로 나눠 읽을 창. **파일 경계를 넘지 않는다.**

    슬라이드 번호로 적지만 읽는 대상은 PDF다. 외부 족보는 별도 파일이라
    `num_pages`에서 끊어야 한다 - 안 끊으면 `21-39` 같은 창이 나오고, 33쪽짜리
    `annotated.pdf`에 39쪽을 요청하게 된다.
    """
    total = int(total_slides)
    windows = [f"{s}-{min(s + size - 1, num_pages)}"
               for s in range(1, num_pages + 1, size)]
    windows += [f"{s}-{min(s + size - 1, total)}"
                for s in range(num_pages + 1, total + 1, size)]
    return windows


# 경계를 짐작하던 코드는 전부 지웠다.
#
# 처음엔 앞에서 훑으며 문구를 찾았고(정답 아는 2건 중 0건), 다음엔 뒤에서부터
# 세었다(2건 중 2건). 뒤쪽이 확실히 나았지만 그래도 **힌트로 넘기지 않는다** -
# 네 강의 연속으로 모델이 뒤집었고 방향이 일정하지 않았다.
#
# 뒤에서부터 세는 논리는 `quiz/structure.py`의 `scan_jokbo_start`로 옮겨
# **검증에만** 쓴다. 코드는 재고 모델이 정한다.


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
            lines.append(text if text else "(텍스트 없음 — jokbo_input.pdf에서 이 쪽을 읽어라)")
            lines.append("")
    if pages < 1:
        raise ValueError(f"족보 PDF가 비어 있습니다: {jokbo_pdf}")

    last_slide = first_slide + pages - 1
    text_path = run_dir / "jokbo_text.md"
    text_path.write_text(
        f"# 족보 원문 — {jokbo_pdf.name}\n\n"
        "슬라이드 번호는 필기 뒤에 이어 붙인 가상 번호다. 그림이 필요한 문항은\n"
        f"`jokbo_input.pdf`를 함께 보라 - 슬라이드 N은 그 PDF의 N-{first_slide - 1}쪽이다.\n\n"
        + "\n".join(lines),
        encoding="utf-8")

    # 여기만 offset이 붙는다. 외부 족보는 별도 파일이라 1쪽부터 시작하는데 슬라이드
    # 번호는 필기 뒤에 이어지므로, 슬라이드 N = (N - first_slide + 1)쪽이다.
    # 각인에는 슬라이드 번호가 찍히니 **읽고 나면** 헷갈릴 일이 없다. 헷갈리는 건
    # 요청할 때뿐이라, offset을 prep.json이 나른다.
    jokbo_input = run_dir / "jokbo_input.pdf"
    make_labeled_pdf(jokbo_pdf, jokbo_input, slide_start=first_slide)

    media_files, image_map = render_slide_pngs(
        jokbo_pdf, media_dir, f"{prefix}_jokbo", scale=scale, slide_start=first_slide)

    return {
        "source": str(jokbo_pdf),
        "pages": pages,
        "range": [first_slide, last_slide],
        "input_pdf": jokbo_input,
        "slide_offset": first_slide - 1,
        "media_files": media_files,
        "image_map": image_map,
        "text_path": text_path,
        "chars": sum(len(line) for line in lines),
    }


def prep(pdf_path: Path, out_root: Path, scale: float,
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

    # 신호 채널: 원본 그대로 + 각인. 족보 구간을 읽는 곳이기도 하다.
    annotated = run_dir / "annotated.pdf"
    make_labeled_pdf(pdf_path, annotated, slide_start=1)

    # 족보 구간을 따로 렌더하지 않는다. 문항이 annotation 안에만 있을 수 있어서
    # clean 채널로 읽으면 백지가 되는데, `annotated.pdf`가 원본 그대로이고 쪽 번호도
    # 같으므로 그 구간만 `pages`로 읽으면 된다. 각인이 annotation이라 필기 위에
    # 남는다 - 예전에 평탄화 PNG를 굽던 이유가 그것이었다.
    #
    # 여기서 나오는 값은 **힌트**다. 경계를 실제로 정하는 건 structure.json(모델)이고,
    # 코드는 quiz/structure.py의 verify()로 그 판정을 따진다.
    #
    # 족보는 꼬리에 붙은 연속 블록이므로 **뒤에서부터** 거슬러 올라간다. 앞에서
    # 훑으며 "여기서부터 족보인가"를 묻던 방식은 본문의 숫자·낱말에 걸려 번번이
    # 늦게 멈췄다 - 정답을 아는 두 건에서 둘 다 한 쪽씩 밀렸다.
    features = page_features(pdf_path)

    # **경계를 여기서 짐작하지 않는다.**
    #
    # 예전에는 정규식으로, 그다음엔 뒤에서부터 세는 방식으로 힌트를 냈다. 네 강의
    # 연속으로 모델이 그 힌트를 뒤집었고(한 장 늦음·한 장 이름·세 장 이름) 방향이
    # 일정하지 않아 보정할 수도 없었다.
    #
    # 그리고 힌트는 공짜가 아니었다. 계산 자체는 0.018ms지만 라벨 추출 범위를
    # `[1, 힌트-1]`로 잘라서, 힌트가 이르면 **오클루전 후보를 조용히 잃었다.**
    # 전 페이지에서 뽑아도 263ms 더 걸릴 뿐이다(prep 전체는 수십 초다).
    #
    # 그러니 코드는 재기만 하고(`page_features.json`), 판정은 0.5단계가 한다.
    # 뒤에서부터 세는 논리는 버리지 않고 `structure.py`의 검증으로 옮겼다.
    external = None
    if jokbo_pdf:
        external = prep_external_jokbo(
            jokbo_pdf, run_dir, media_dir, safe_media_prefix(pdf_path.stem),
            first_slide=num_pages + 1, scale=scale)

    # Anki 미디어는 원본(필기 포함)에서 렌더한다. 복습 카드 뒷면에서 교수 강조가
    # 보이는 편이 낫고, 이 이미지는 모델 입력이 아니라 사람이 보는 확인용이다.
    prefix = safe_media_prefix(pdf_path.stem)
    media_files, slide_image_map = render_slide_pngs(pdf_path, media_dir, prefix, scale=scale)
    # 여기서는 아직 검증하지 않는다. 외부 족보를 붙이면 번호가 필기 뒤로
    # 이어져서, 합친 뒤에 한 번만 본다(아래).

    # 이미지 오클루전용 라벨 후보. 원본 PDF에서 뽑아야 미디어 렌더와 좌표가 맞는다.
    # **전 페이지에서 뽑는다.** 경계를 모르는 상태이므로 범위를 좁히면 강의록
    # 슬라이드의 라벨을 잃는다. 족보 구간의 라벨은 어차피 아무도 안 쓴다.
    labels = extract_labels(pdf_path, (1, num_pages))

    # 구간은 비워 둔다. 0.5단계가 `structure.json`에 쓰기 전까지는 **모르는 게 맞다.**
    # 여기에 짐작을 적어 두면 검증기가 그걸 근거로 삼아 멀쩡한 카드에 유령 불평을
    # 낸다(실제로 그랬다).
    total_slides = external["range"][1] if external else num_pages
    if external:
        media_files = media_files + external["media_files"]
        slide_image_map = {**slide_image_map, **external["image_map"]}

    validate_slide_image_map(slide_image_map, media_dir, total_slides)

    manifest = {
        "lecture_id": lecture_id,
        "lecture_title": lecture_title,
        "source_pdf": str(pdf_path),
        "source_stem": pdf_path.stem,
        "num_pages": num_pages,
        "prepared_at": datetime.now().isoformat(timespec="seconds"),
        "annotations_removed": removed,
        # 모델이 Read의 `pages`로 직접 읽는 두 채널. 슬라이드 N = 양쪽 다 N쪽이다.
        "model_input_pdf": str(model_input),
        "annotated_pdf": str(annotated),
        "jokbo_source": "external" if external else "embedded",
        "jokbo_pdf": external["source"] if external else None,
        # 외부 족보만 별도 파일이라 offset이 붙는다. 슬라이드 N = (N - offset)쪽.
        "jokbo_input_pdf": str(external["input_pdf"]) if external else None,
        "jokbo_slide_offset": external["slide_offset"] if external else None,
        # 원본 족보의 원문. 글이 주고 이미지가 보조다.
        "jokbo_text_path": str(external["text_path"]) if external else None,
        # 외부 족보를 붙였으면 그 구간만은 파일 경계라 확실하다. 필기 안의 경계는
        # 0.5단계가 정한다.
        "external_jokbo_range": external["range"] if external else None,
        "num_lecture_pdf_pages": num_pages,
        "total_slides": total_slides,
        "page_features_path": str(run_dir / "page_features.json"),
        "media_dir": str(media_dir),
        "media_files": media_files,
        "slide_image_map": {str(k): v for k, v in slide_image_map.items()},
        "read_windows": read_windows(num_pages, total_slides),
        # false면 `pages` 읽기가 안 된다. 통째 읽기는 되므로 0.5·1단계는 산다.
        "poppler_available": poppler_available(),
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
    parser.add_argument("--run-id", default=None,
                        help="출력 디렉터리 이름 (기본: 파일명의 강의 코드)")
    parser.add_argument("--jokbo-pdf", default=None,
                        help="과목 족보에서 잘라온 원본 PDF. 주면 필기 뒤의 캡처본 대신 "
                             "이걸 족보 채널로 쓰고, 경계 판정이 필요 없어진다")
    args = parser.parse_args()

    manifest = prep(Path(args.pdf), Path(args.out), args.scale, args.run_id,
                    Path(args.jokbo_pdf) if args.jokbo_pdf else None)
    annots = json.loads(Path(manifest["annotations_path"]).read_text(encoding="utf-8"))
    stamped = [a["slide_no"] for a in annots if "stamp" in a["signals"]]
    print(f"[prep] {manifest['lecture_id']} : {manifest['lecture_title']}")
    print(f"  슬라이드 {manifest['num_pages']}장, annotation {manifest['annotations_removed']}개 제거")
    print(f"  필기 신호 {len(annots)}장 / 족보 도장(stamp) {len(stamped)}장: {stamped}")
    print(f"  사실 채널 → {Path(manifest['model_input_pdf']).name} "
          f"(필기 제거, {manifest['num_pages']}쪽, 슬라이드 N = N쪽)")
    print(f"  족보 채널 → {Path(manifest['annotated_pdf']).name} "
          f"(원본 그대로, {manifest['num_pages']}쪽, 슬라이드 N = N쪽)")
    if manifest["jokbo_source"] == "external":
        lo, hi = manifest["external_jokbo_range"]
        text_path = Path(manifest["jokbo_text_path"])
        offset = manifest["jokbo_slide_offset"]
        print(f"  원본 족보 {lo}-{hi} ({Path(manifest['jokbo_pdf']).name})")
        print(f"        → {Path(manifest['jokbo_input_pdf']).name} "
              f"(슬라이드 N = N-{offset}쪽)")
        print(f"        원문 {len(text_path.read_text(encoding='utf-8')):,}자 → {text_path.name}")
    print("  ※ 경계는 짐작하지 않는다. 0.5단계가 structure.json으로 정하고 "
          "quiz/structure.py가 뒤에서부터 세어 따진다")
    if not manifest["poppler_available"]:
        print("  ⚠ pdftoppm(poppler)이 PATH에 없다. prep은 끝났지만 **2·4단계가 못 읽는다** -")
        print("    그 단계는 Read의 `pages`로 쪽 범위를 받고, 그 경로가 poppler를 쓴다.")
        print("    `pages`를 생략한 통째 읽기는 되므로 0.5·1단계는 돈다.")
        print("    깔려 있는데 이 경고가 뜨면 **앱을 완전히 종료했다 켜라** - PATH는")
        print("    프로세스가 시작할 때 한 번 잡힌다 (새 세션이나 새 창만으로는 안 된다).")
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
