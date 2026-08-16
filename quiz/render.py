"""PDF 자르기, annotation 제거, 슬라이드 번호 각인, PNG 렌더.

meddeck-local-app/pdf_to_anki/pdf_render.py 기반. 이 파이프라인의 급소인
'슬라이드 번호 계약'을 물리적으로 보증하는 코드가 여기 있다.
"""

from __future__ import annotations

from pathlib import Path

import fitz

# Anki 카드에 들어가는 이미지 배율. 2.0이면 720x540 슬라이드가 1440x1080이 된다.
MEDIA_RENDER_SCALE = 2.0


def make_annotation_clean_pdf(src_pdf_path, out_pdf_path) -> int:
    """PDF annotation(필기·형광펜·도장)을 제거한 복사본. 페이지 본문과 이미지는 유지.

    모델이 '사실'을 읽는 채널은 반드시 이쪽이어야 한다. 필기가 섞인 자료를 근거로
    쓰면 강조 표시를 사실로 착각한 문항이 나온다.
    """
    doc = fitz.open(str(src_pdf_path))
    removed = 0
    for page in doc:
        annot = page.first_annot
        while annot:
            nxt = annot.next
            try:
                page.delete_annot(annot)
                removed += 1
            except Exception:
                pass
            annot = nxt
        try:
            widgets = list(page.widgets() or [])
        except Exception:
            widgets = []
        for widget in widgets:
            try:
                page.delete_widget(widget)
                removed += 1
            except Exception:
                pass
    doc.save(str(out_pdf_path), garbage=4, deflate=True, clean=True)
    doc.close()
    return removed


def stamp_slide_labels(doc, slide_start: int = 1) -> None:
    """모든 페이지 좌상단에 'Slide N'을 노란 박스로 태워 넣는다.

    이게 없으면 모델은 첨부 PDF에서 페이지를 '세어' slide_no를 추정해야 하고,
    한 페이지만 잘못 세면 그 뒤 모든 문항에 엉뚱한 슬라이드 이미지가 붙는다.
    번호를 페이지에 구워 넣으면 추론이 읽기로 바뀐다.
    """
    for index, page in enumerate(doc):
        slide_no = int(slide_start) + index
        label = f"Slide {slide_no}"
        rect = fitz.Rect(6, 6, 6 + 11 * len(label) + 10, 30)
        page.draw_rect(rect, color=(0, 0, 0), fill=(1, 1, 0.4), overlay=True)
        page.insert_textbox(rect, label, fontsize=13, color=(0, 0, 0), align=1, overlay=True)


def make_labeled_pdf(src_pdf_path, out_pdf_path, slide_start: int = 1) -> int:
    doc = fitz.open(str(src_pdf_path))
    stamp_slide_labels(doc, slide_start)
    doc.save(str(out_pdf_path))
    n = len(doc)
    doc.close()
    return n


def make_page_range_pdf(src_pdf_path, out_pdf_path, slide_start: int, slide_end: int) -> int:
    """원본의 1-indexed slide_start~slide_end를 새 PDF로 저장한다."""
    src = fitz.open(str(src_pdf_path))
    total = len(src)
    start = min(max(1, int(slide_start)), total)
    end = min(max(start, int(slide_end)), total)
    out = fitz.open()
    out.insert_pdf(src, from_page=start - 1, to_page=end - 1)
    out.save(str(out_pdf_path))
    out.close()
    src.close()
    return end - start + 1


def render_slide_pngs(pdf_path, media_dir: Path, prefix: str, scale: float = MEDIA_RENDER_SCALE,
                      slide_start: int = 1):
    """슬라이드마다 PNG 한 장. Anki 미디어로 들어간다.

    반환: (media_files, slide_image_map) - map은 {슬라이드번호: 파일명}.
    파일명에 슬라이드 번호가 제로패딩으로 박혀 있어서 나중에 눈으로도 검증된다.

    `slide_start`는 외부 족보 PDF를 필기 뒤에 이어 붙일 때 쓴다. 필기가 N장이면
    족보는 N+1부터 번호를 받는다. map만 옮기면 파일명과 번호가 어긋나 뒤의
    `validate_slide_image_map`이 막으므로, 번호는 여기 한 곳에서 정한다.
    """
    doc = fitz.open(str(pdf_path))
    media_dir = Path(media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    media_files: list[str] = []
    slide_image_map: dict[int, str] = {}
    matrix = fitz.Matrix(scale, scale)
    for i in range(len(doc)):
        slide_no = i + slide_start
        img_name = f"{prefix}_s{slide_no:03d}.png"
        img_path = media_dir / img_name
        pix = doc.load_page(i).get_pixmap(matrix=matrix, alpha=False)
        pix.save(str(img_path))
        media_files.append(str(img_path.resolve()))
        slide_image_map[slide_no] = img_name
    doc.close()
    return media_files, slide_image_map


def render_flattened_labeled_pngs(
    pdf_path, out_dir: Path, prefix: str, slide_start: int = 1, scale: float = MEDIA_RENDER_SCALE
):
    """annotation을 먼저 래스터로 굽고 그 위에 'Slide N'을 각인해 PNG로 저장한다.

    족보 페이지에는 문항이 이미지 annotation으로 붙어 있는데, annotation은 페이지
    내용보다 위에 그려진다. 그래서 PDF에 각인한 라벨이 족보 이미지에 가려져 보이지
    않는다. 페이지를 먼저 픽스맵으로 평탄화한 뒤 라벨을 얹으면 항상 맨 위에 남는다.

    반환: {원본 슬라이드 번호: 파일명}
    """
    src = fitz.open(str(pdf_path))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    page_map: dict[int, str] = {}
    for index in range(len(src)):
        slide_no = int(slide_start) + index
        pix = src.load_page(index).get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)

        flat = fitz.open()
        page = flat.new_page(width=pix.width, height=pix.height)
        page.insert_image(fitz.Rect(0, 0, pix.width, pix.height), pixmap=pix)
        stamp_slide_labels(flat, slide_no)

        img_name = f"{prefix}_s{slide_no:03d}.png"
        page.get_pixmap(alpha=False).save(str(out_dir / img_name))
        flat.close()
        page_map[slide_no] = img_name
    src.close()
    return page_map


def validate_slide_image_map(slide_image_map: dict, media_dir: Path, num_pages: int) -> None:
    """모든 슬라이드에 이미지가 정확히 하나씩, 번호와 파일명이 일치하는지 확인."""
    problems = []
    seen = set()
    media_dir = Path(media_dir)
    for slide_no in range(1, int(num_pages) + 1):
        name = slide_image_map.get(slide_no) or slide_image_map.get(str(slide_no))
        if not name:
            problems.append(f"Slide {slide_no}: 이미지 파일명 없음")
            continue
        if name in seen:
            problems.append(f"Slide {slide_no}: 파일명 중복 {name}")
        seen.add(name)
        if not (media_dir / name).exists():
            problems.append(f"Slide {slide_no}: 파일 없음 ({name})")
        if not name.endswith(f"_s{slide_no:03d}.png"):
            problems.append(f"Slide {slide_no}: 파일명이 슬라이드 번호와 불일치 ({name})")
    if problems:
        raise RuntimeError("슬라이드 이미지 맵 검증 실패:\n" + "\n".join(problems[:20]))
