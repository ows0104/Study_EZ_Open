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


STAMP_H = 24
STAMP_MARGIN = 6


def _content_rects(page) -> list:
    """글자·이미지·annotation이 실제로 놓인 자리."""
    rects = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") == 1:
            rects.append(fitz.Rect(block["bbox"]))
            continue
        for line in block.get("lines", []):
            for span in line["spans"]:
                if span["text"].strip():
                    rects.append(fitz.Rect(span["bbox"]))
    try:
        for annot in page.annots():
            rects.append(fitz.Rect(annot.rect))
    except Exception:
        pass
    return rects


def _corner_origins(width: float, height: float, box_w: float, box_h: float):
    """좌상 → 우상 → 우하 → 좌하."""
    m = STAMP_MARGIN
    return ((m, m),
            (width - box_w - m, m),
            (width - box_w - m, height - box_h - m),
            (m, height - box_h - m))


# 우상 → 좌상 → 우하 → 좌하. 실측 434장(10편)의 점유율 순이다
# (우상 10.4% · 좌상 11.3% · 좌하 10.4% · 우하 15.0%). 좌하는 우상과 점유율이
# 같지만 **편 전체가 비는** 경우가 적어(2편 대 4편) 뒤로 뒀다.
CORNER_ORDER = (1, 0, 2, 3)


def _free_corners(page, box_w: float, box_h: float = STAMP_H) -> list[bool]:
    rects = _content_rects(page)
    return [
        not any(fitz.Rect(x, y, x + box_w, y + box_h).intersects(r) for r in rects)
        for x, y in _corner_origins(page.rect.width, page.rect.height, box_w, box_h)
    ]


def choose_stamp_corners(pages, slide_start: int = 1) -> list[int]:
    """편 전체를 보고 주력 코너를 하나 정하고, 그 자리가 찬 쪽만 따로 뺀다.

    좌상단 고정이던 시절 각인이 **제목을 먹었다.** `260812_02`는 33장 중 17장에서
    제목 글자가 상자 밑에 깔렸고, s8·s12는 제목이 `Cell death` 한 마디뿐이라
    **100% 사라졌다.** 그런데 `model_input.pdf`는 모델이 사실을 읽는 채널이다.

    자리를 쪽마다 따로 고르면 안 덮이기는 하지만 각인이 튄다. 각인의 존재 이유가
    "세지 말고 읽어라"이므로 **한 편 안에서 안 움직이는 것**이 값을 한다. 그래서
    편 단위로 가장 많이 비는 코너를 주력으로 잡고 예외만 옮긴다 - 실측에서 자리를
    옮기는 쪽이 41장에서 **17장으로** 줄었고(434장 중), 10편 중 4편은 예외가 0장이다.

    어느 코너가 비는지는 필기자의 템플릿마다 뒤집힌다. `260812_02`는 좌상단이
    52% 차 있고 우상단이 0%인데 `250820_01`은 정확히 그 반대다(4% / 41%).
    그래서 고정 위치로는 못 푼다.

    캔버스를 늘려 빈 띠를 만드는 방법은 쓰지 않는다. `labels.json`은 원본 PDF에서,
    오클루전 렌더는 `model_input.pdf`에서 좌표를 잡는데 **둘의 기하가 같아야
    맞물린다.** 한쪽만 늘리면 정규화 분모가 갈려 라벨 상자가 통째로 어긋나고,
    양쪽을 늘리면 이미 만든 run의 저장된 좌표가 무효가 된다. 코너만 옮기면
    기하는 그대로다.

    네 코너가 모두 찬 쪽은 434장 중 4장뿐이고, 그때는 주력으로 되돌아가 예전처럼
    덮는다. 덮지 않을 자리가 아예 없기 때문이다.
    """
    free = []
    for index, page in enumerate(pages):
        label = f"Slide {int(slide_start) + index}"
        free.append(_free_corners(page, 11 * len(label) + 10))
    if not free:
        return []
    primary = max(CORNER_ORDER,
                  key=lambda c: (sum(1 for f in free if f[c]), -CORNER_ORDER.index(c)))
    return [primary if f[primary] else next((c for c in CORNER_ORDER if f[c]), primary)
            for f in free]


def stamp_slide_labels(doc, slide_start: int = 1, corners=None) -> None:
    """모든 페이지에 'Slide N'을 노란 박스로 태워 넣는다. 자리는 비어 있는 코너.

    이게 없으면 모델은 첨부 PDF에서 페이지를 '세어' slide_no를 추정해야 하고,
    한 페이지만 잘못 세면 그 뒤 모든 문항에 엉뚱한 슬라이드 이미지가 붙는다.
    번호를 페이지에 구워 넣으면 추론이 읽기로 바뀐다.

    `corners`를 주면 그 판정을 그대로 쓴다. 평탄화한 페이지처럼 **자리를 고를
    근거가 페이지 안에 없을 때** 원본에서 골라 넘기는 용도다.

    각인은 **annotation으로** 붙인다. 페이지 내용으로 그리면 필기가 살아 있는
    판본에서 각인이 가려진다 - annotation이 페이지 내용보다 위에 그려지기
    때문이다. `260812_02`의 족보 구간에서 s26은 아래가 잘리고 s27은 `lide 27`만
    남았다. annotation은 배열 순서로 그려지므로 맨 뒤에 붙으면 필기 위에 온다.

    덕분에 필기 판본을 평탄화해 PNG로 굽는 우회로가 필요 없어졌다. 예전에는
    `render_flattened_labeled_pngs`가 그 일을 했다.
    """
    pages = list(doc)
    if corners is None:
        corners = choose_stamp_corners(pages, slide_start)
    for index, page in enumerate(pages):
        slide_no = int(slide_start) + index
        label = f"Slide {slide_no}"
        box_w = 11 * len(label) + 10
        x, y = _corner_origins(page.rect.width, page.rect.height, box_w, STAMP_H)[corners[index]]
        rect = fitz.Rect(x, y, x + box_w, y + STAMP_H)
        annot = page.add_freetext_annot(
            rect, label, fontsize=13, fontname="helv",
            text_color=(0, 0, 0), fill_color=(1, 1, 0.4), align=1)
        annot.update()


def make_labeled_pdf(src_pdf_path, out_pdf_path, slide_start: int = 1) -> int:
    doc = fitz.open(str(src_pdf_path))
    stamp_slide_labels(doc, slide_start)
    doc.save(str(out_pdf_path))
    n = len(doc)
    doc.close()
    return n


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
