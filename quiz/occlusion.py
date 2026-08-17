"""이미지 오클루전: 슬라이드의 라벨을 가린 앞면과 드러낸 뒷면을 만든다.

Brodmann area 번호, 조직 슬라이드의 구조명, 도식의 화살표 라벨처럼 **위치와
이름의 대응 자체가 시험 대상**인 내용은 텍스트 카드로 옮기는 순간 죽는다.
"Brodmann area 4는?"는 번호만 외우게 하지만, 그림에서 그 자리를 가리고 물으면
위치를 회수하게 된다.

좌표를 모델에게 눈대중으로 찍게 하지 않는다. PDF의 텍스트 span에는 정확한
bbox가 이미 들어 있으므로, 코드가 라벨 후보를 뽑아 ID를 붙이고 모델은 그중
무엇을 가릴지만 고른다. 파이프라인의 다른 곳과 같은 분업이다 - 좌표는 코드,
의미는 모델.

라벨이 벡터 텍스트가 아니라 그림에 구워져 있으면 후보가 안 잡힌다. 그때만
정규화 좌표(0~1)를 직접 쓰는 우회로를 연다.
"""

from __future__ import annotations

import re
import string
from pathlib import Path

import fitz

# 불릿, 화살표, 괘선 같은 기호만 있는 줄. 가려봐야 아무것도 회수되지 않는다.
_HAS_WORD_RE = re.compile(r"[0-9A-Za-z가-힣]")

# 가림 상자 테두리 색. 슬라이드 본문에 잘 안 쓰이는 마젠타를 골라 학습자가
# "이건 원래 슬라이드에 없던 표시"임을 즉시 알게 한다.
ACCENT = (0.85, 0.0, 0.55)

# 상자를 라벨보다 살짝 크게 잡는다. 글자 끝이 삐져나오면 정답이 새어 보인다.
BOX_MARGIN_PT = 1.8

# 라벨 후보로 볼 최대 글자 수. 이보다 길면 본문 문장이지 라벨이 아니다.
MAX_LABEL_CHARS = 40
MAX_LABELS_PER_SLIDE = 80

# 오클루전 이미지는 카드 앞면에 뜨는 주인공이므로 미디어와 같은 배율로 크게 뽑는다.
OCCLUSION_RENDER_SCALE = 2.0

# 상자가 여럿일 때 붙이는 표식. 모델이 "A와 B에 해당하는 구조는?"으로 물을 수 있다.
MARKERS = string.ascii_uppercase


def _norm_rect(rect, page_rect) -> list[float]:
    """PDF 좌표 → 페이지 크기에 대한 0~1 비율. 배율이 바뀌어도 살아남는다."""
    w = float(page_rect.width) or 1.0
    h = float(page_rect.height) or 1.0
    return [
        round(max(0.0, rect[0] / w), 5),
        round(max(0.0, rect[1] / h), 5),
        round(min(1.0, rect[2] / w), 5),
        round(min(1.0, rect[3] / h), 5),
    ]


def label_id(slide_no: int, index: int) -> str:
    return f"s{int(slide_no):03d}_l{int(index):02d}"


def extract_slide_labels(page, slide_no: int) -> list[dict]:
    """한 슬라이드의 라벨 후보. 줄 단위로 자르고 짧은 것만 남긴다.

    `kind`는 힌트다. 한 블록이 몇 줄 안 되고 글자 수도 적으면 그림에 얹힌
    라벨일 가능성이 높고(`label`), 여러 줄짜리 블록의 한 줄이면 본문(`text`)이다.
    모델은 `label` 쪽을 우선 고르면 된다.
    """
    try:
        data = page.get_text("dict")
    except Exception:
        return []

    page_rect = page.rect
    candidates: list[dict] = []
    seen: set[tuple] = set()

    for block in data.get("blocks", []):
        if block.get("type") != 0:  # 0 = 텍스트, 1 = 이미지
            continue
        lines = block.get("lines", [])
        block_chars = sum(
            len("".join(s.get("text", "") for s in ln.get("spans", [])).strip())
            for ln in lines
        )
        # 짧은 독립 블록 = 그림 위 라벨. 긴 블록의 한 줄 = 본문.
        block_kind = "label" if (len(lines) <= 3 and block_chars <= 60) else "text"

        for line in lines:
            text = "".join(s.get("text", "") for s in line.get("spans", [])).strip()
            if not text or len(text) > MAX_LABEL_CHARS:
                continue
            if not _HAS_WORD_RE.search(text):
                continue
            rect = _norm_rect(line.get("bbox", (0, 0, 0, 0)), page_rect)
            if rect[2] - rect[0] <= 0.002 or rect[3] - rect[1] <= 0.002:
                continue
            key = (text, round(rect[0], 3), round(rect[1], 3))
            if key in seen:
                continue
            seen.add(key)
            candidates.append({"text": text, "rect": rect, "kind": block_kind})

    # 라벨스러운 것을 먼저, 그다음 위→아래. 잘릴 때 그림 라벨이 살아남게.
    candidates.sort(key=lambda c: (c["kind"] != "label", c["rect"][1], c["rect"][0]))
    candidates = candidates[:MAX_LABELS_PER_SLIDE]
    for index, candidate in enumerate(candidates, start=1):
        candidate["id"] = label_id(slide_no, index)
    return candidates


def extract_labels(pdf_path, slide_range: tuple[int, int] | None = None) -> dict:
    """전 슬라이드의 라벨 후보. prep 단계에서 labels.json으로 저장된다."""
    doc = fitz.open(str(pdf_path))
    lo = 1
    hi = len(doc)
    if slide_range:
        lo = max(1, int(slide_range[0]))
        hi = min(hi, int(slide_range[1]))

    slides: dict[str, list[dict]] = {}
    total = 0
    for slide_no in range(lo, hi + 1):
        labels = extract_slide_labels(doc.load_page(slide_no - 1), slide_no)
        if labels:
            slides[str(slide_no)] = labels
            total += len(labels)
    doc.close()
    return {"slide_range": [lo, hi], "label_count": total, "slides": slides}


def build_label_index(labels: dict | None) -> dict[int, dict[str, list[float]]]:
    """labels.json → {슬라이드번호: {label_id: rect}}. 검증과 렌더가 함께 쓴다."""
    index: dict[int, dict[str, list[float]]] = {}
    for slide_key, entries in ((labels or {}).get("slides") or {}).items():
        try:
            slide_no = int(slide_key)
        except (TypeError, ValueError):
            continue
        index[slide_no] = {e["id"]: e["rect"] for e in entries if e.get("id")}
    return index


def valid_rect(value) -> bool:
    """모델이 직접 적은 정규화 좌표가 그릴 수 있는 형태인지."""
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return False
    try:
        x0, y0, x1, y1 = (float(v) for v in value)
    except (TypeError, ValueError):
        return False
    if not all(0.0 <= v <= 1.0 for v in (x0, y0, x1, y1)):
        return False
    return x1 - x0 > 0.001 and y1 - y0 > 0.001


def resolve_rects(occlusion: dict, slide_no: int,
                  label_index: dict[int, dict[str, list[float]]]) -> tuple[list[list[float]], list[str]]:
    """카드의 occlusion 지정 → 실제 좌표 목록. (좌표, 문제 목록)."""
    rects: list[list[float]] = []
    problems: list[str] = []
    known = label_index.get(int(slide_no), {})

    for lid in occlusion.get("label_ids") or []:
        rect = known.get(str(lid))
        if rect is None:
            problems.append(f"unknown_label_id({lid})")
        else:
            rects.append(list(rect))

    for raw in occlusion.get("rects") or []:
        if valid_rect(raw):
            rects.append([float(v) for v in raw])
        else:
            problems.append(f"invalid_rect({raw})")

    if not rects and not problems:
        problems.append("occlusion_empty")
    return rects, problems


def _draw_marker(page, rect: fitz.Rect, text: str, fontsize: float, filled: bool) -> None:
    """상자 안(앞면) 또는 모서리(뒷면)에 표식을 찍는다."""
    try:
        width = fitz.get_text_length(text, fontname="helv", fontsize=fontsize)
    except Exception:
        width = fontsize * 0.6 * len(text)
    if filled:
        x = rect.x0 + (rect.width - width) / 2
        y = rect.y0 + (rect.height + fontsize * 0.72) / 2
    else:
        # 뒷면: 상자 왼쪽 위에 작은 흰 칩. 상자 안은 원래 라벨이 보여야 한다.
        chip = fitz.Rect(rect.x0 - 2, rect.y0 - fontsize - 4, rect.x0 + width + 6, rect.y0 - 1)
        page.draw_rect(chip, color=ACCENT, fill=(1, 1, 1), width=0.8, overlay=True)
        x = chip.x0 + 3
        y = chip.y1 - 3
    page.insert_text((x, y), text, fontname="helv", fontsize=fontsize,
                     color=ACCENT, overlay=True)


def render_occlusion_pair(pdf_path, slide_no: int, rects: list[list[float]],
                          out_dir: Path, basename: str,
                          scale: float = OCCLUSION_RENDER_SCALE) -> tuple[str, str]:
    """가린 앞면 / 드러낸 뒷면 PNG 두 장. 반환은 파일명 두 개.

    페이지를 먼저 픽스맵으로 평탄화한 뒤 그 위에 그린다. annotation은 페이지
    내용보다 위에 그려지므로, 평탄화하지 않으면 필기가 가림 상자를 뚫고 올라온다.
    render.py의 `stamp_slide_labels`는 같은 사실을 반대로 이용한다 - 각인을
    annotation으로 붙여 필기 위에 올린다.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    src = fitz.open(str(pdf_path))
    pix = src.load_page(int(slide_no) - 1).get_pixmap(
        matrix=fitz.Matrix(scale, scale), alpha=False)
    src.close()

    names: list[str] = []
    for hide in (True, False):
        doc = fitz.open()
        page = doc.new_page(width=pix.width, height=pix.height)
        page.insert_image(fitz.Rect(0, 0, pix.width, pix.height), pixmap=pix)

        for index, raw in enumerate(rects):
            rect = fitz.Rect(
                raw[0] * pix.width - BOX_MARGIN_PT * scale,
                raw[1] * pix.height - BOX_MARGIN_PT * scale,
                raw[2] * pix.width + BOX_MARGIN_PT * scale,
                raw[3] * pix.height + BOX_MARGIN_PT * scale,
            )
            marker = MARKERS[index] if len(rects) > 1 and index < len(MARKERS) else "?"
            if hide:
                page.draw_rect(rect, color=ACCENT, fill=(1, 1, 1),
                               width=1.6 * scale, overlay=True)
                size = max(9.0, min(rect.height * 0.72, 26.0 * scale))
                _draw_marker(page, rect, marker, size, filled=True)
            else:
                page.draw_rect(rect, color=ACCENT, width=1.6 * scale, overlay=True)
                if len(rects) > 1:
                    _draw_marker(page, rect, marker, 8.0 * scale, filled=False)

        name = f"{basename}_{'q' if hide else 'a'}.png"
        page.get_pixmap(alpha=False).save(str(out_dir / name))
        doc.close()
        names.append(name)

    return names[0], names[1]
