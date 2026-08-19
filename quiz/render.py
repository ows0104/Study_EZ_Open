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

    다음 표시는 **`delete_annot`이 돌려주는 것**을 받는다. 지우기 전에 집어 둔
    `annot.next`를 쓰면 안 된다 — 앞엣것을 지울 때 뒤엣것이 페이지에서 풀리는
    자리가 있다. `250821_01`의 첫 쪽이 그랬고(FreeText를 지우자 바로 뒤 Text가
    죽었다), 그 한 편이 통째로 prep에서 막혀 있었다.

    그래도 남는 것이 있으면 그 쪽의 `/Annots`를 통째로 버린다. 이 파일이 사실
    채널이라 **덜 지운 채로 나가느니 다 버리는 편이 낫다.** 남기고 넘어가면
    강조 표시가 사실로 읽힌다.
    """
    doc = fitz.open(str(src_pdf_path))
    removed = 0
    for page in doc:
        annot = page.first_annot
        while annot:
            try:
                annot = page.delete_annot(annot)
                removed += 1
            except Exception:
                # 다음으로 넘어갈 손잡이가 없다. 아래 backstop에 맡긴다.
                break
        for widget in list(page.widgets() or []):
            try:
                page.delete_widget(widget)
                removed += 1
            except Exception:
                pass
        if page.first_annot is not None:
            print(f"[prep] 경고: {page.number + 1}쪽의 표시를 하나씩 못 지웠다 — "
                  f"그 쪽의 annotation을 통째로 버린다")
            doc.xref_set_key(page.xref, "Annots", "null")
    doc.save(str(out_pdf_path), garbage=4, deflate=True, clean=True)
    doc.close()
    return removed


# 각인을 놓을 하단 띠. 페이지 아래에 이만큼 빈 자리를 붙이고 **거기에만** 찍는다.
STAMP_BAND_PT = 30
STAMP_H = 24
STAMP_MARGIN = 6


def extend_bottom(doc, band: float = STAMP_BAND_PT) -> None:
    """모든 페이지 아래에 빈 띠를 붙인다. **내용은 움직이지 않는다.**

    mediabox의 아래 모서리(`y0`)를 내린다. PDF 좌표계는 y가 위로 증가하므로
    `y0`를 내리면 캔버스가 아래로 자라고 이미 그려진 것의 절대 좌표는 그대로다.

    `show_pdf_page`로 큰 페이지에 옮겨 붙이는 방법도 있지만 그건 **annotation을
    떨어뜨린다.** 족보 문항이 annotation으로만 있는 편에서 기출이 통째로 사라진다.

    실측(`260814_05` 49쪽, 띠 30pt): 텍스트 레이어 동일(667자), annotation 보존,
    첫 블록 bbox 불변, 확장본에서 다시 뽑은 라벨이 같은 절대 위치로 풀림
    (0.20115 x 540 = 0.19056 x 570 = 108.6pt).
    """
    band = float(band)
    for page in doc:
        mb = page.mediabox
        page.set_mediabox(fitz.Rect(mb.x0, mb.y0 - band, mb.x1, mb.y1))


def stamp_slide_labels(doc, slide_start: int = 1, band: float = STAMP_BAND_PT) -> None:
    """하단 띠에 'Slide N'을 찍는다. **내용을 덮지 않는다.**

    이게 없으면 모델은 첨부 PDF에서 페이지를 '세어' slide_no를 추정해야 하고,
    한 페이지만 잘못 세면 그 뒤 모든 문항에 엉뚱한 슬라이드 이미지가 붙는다.
    Read의 `pages` 경로는 쪽 번호를 돌려주지 않으므로 각인이 유일한 번호 신호다.

    **자리를 고르지 않는다.** 예전에는 빈 코너를 찾아 찍었는데(`choose_stamp_corners`)
    네 코너가 다 찬 쪽에서는 주력 코너로 되돌아가 덮었고, 그 쪽이 하필 **족보
    페이지**였다. 페이지 전체가 붙여넣은 스크린샷이라 코너가 다 차기 때문이다.
    `260814_05`에서 s48·s49의 **정답표**가 덮여 2019-94·2018-22·2018-23의 정답이
    사라졌다. 게다가 정답표 글자는 이미지 픽셀 안에 있어 PDF 구조로는 안 보이므로,
    "겹치는 면적이 가장 작은 코너"로도 못 피한다 - s48은 네 코너의 겹침이
    182.6%로 **똑같았고** s49는 최소값이 바로 그 덮은 자리였다.

    그래서 자리를 고르는 대신 **빈 자리를 만든다.** 띠는 항상 비어 있으므로
    제목도 정답표도 덮을 수 없고, 각인이 편 안에서 움직이지도 않는다.

    각인은 **annotation으로** 붙인다. 두 가지를 얻는다 - 필기가 살아 있는 판본에서
    각인이 필기 밑에 깔리지 않고(annotation은 배열 순서로 그려져 맨 뒤가 위에 온다),
    `get_text()`가 annotation을 안 읽으므로 **텍스트 레이어가 안 더러워진다**.
    페이지 내용으로 그리던 시절에는 s2가 `2026 Slide 2 년1학년 2학기`로 나왔다.
    """
    for index, page in enumerate(doc):
        label = f"Slide {int(slide_start) + index}"
        box_w = 11 * len(label) + 10
        bottom = page.rect.height - (float(band) - STAMP_H) / 2
        rect = fitz.Rect(STAMP_MARGIN, bottom - STAMP_H, STAMP_MARGIN + box_w, bottom)
        annot = page.add_freetext_annot(
            rect, label, fontsize=13, fontname="helv",
            text_color=(0, 0, 0), fill_color=(1, 1, 0.4), align=1)
        annot.update()


def make_labeled_pdf(src_pdf_path, out_pdf_path, slide_start: int = 1,
                     band: float = STAMP_BAND_PT) -> int:
    """하단에 띠를 붙이고 그 띠에 각인을 찍은 판본을 낸다.

    **`labels.json`은 이 결과물에서 뽑아야 한다.** 오클루전 렌더가 이 PDF를 쓰는데
    좌표가 정규화되어 있어서, 분모(페이지 높이)가 갈리면 상자가 통째로 어긋난다.
    띠 30pt면 페이지 중간의 상자가 13pt 아래로 밀려 라벨을 벗어난다.
    """
    doc = fitz.open(str(src_pdf_path))
    extend_bottom(doc, band)
    stamp_slide_labels(doc, slide_start, band)
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
