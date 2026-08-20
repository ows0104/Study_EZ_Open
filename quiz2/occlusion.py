"""오클루전 패스 — 그림의 라벨을 가린 카드를 만든다 (인터뷰 ㉙~㉟).

    python -m quiz2.occlusion plan runs/260819_01      # → spawn/occl.bNN.md
    #  배치마다 서브에이전트를 하나씩. 각자 아래 render를 돌려 가며 고친다
    python -m quiz2.occlusion render runs/260819_01 --items items.raw.occl_b01.json

## 왜 별도 패스인가

**단발 호출로 안 되는 유일한 작업이다.** 상자를 그려 렌더하고 라벨을 덜 덮었는지
눈으로 봐야 하므로 한 번에 안 끝난다. 인터뷰에서 그걸 알고 골랐다(⑳″).

1회차에서 **한 장도 안 나왔다.** `prompt.py`에 `OCCLUSION` 규칙 문자열이 있는데
`make_prompt`가 그걸 어디에도 안 넣는다 — 규칙만 있고 부르는 자리가 없었다.

## 코드가 잡아 주는 것 두 가지

`CLAUDE.md`가 감사의 한계를 이렇게 적어 두었다 — 오클루전 결함 셋 중 *"상자가
라벨을 덜 덮은 것은 셋 중 하나만, 가린 답이 아래 행에 그대로 있던 것은 아무도
온전히 못 잡았다."* 둘 다 **좌표와 문자열로 셀 수 있다.**

    answer_text_elsewhere      가린 라벨의 글자가 슬라이드의 **안 가린 다른 라벨**에
                               그대로 또 있다. ㉝의 자리다 — 카드를 버리지 말고
                               그 자리를 `mask_label_ids`로 같이 덮으면 된다
    answer_text_in_annotation  가린 라벨의 글자가 그 슬라이드 **필기**에 또 있다 (㉞)
    rect_clips_label           직접 적은 좌표가 라벨을 **걸치기만 하고 다 못 덮었다.**
                               글자 끝이 삐져나오면 정답이 새어 보인다

세는 것까지가 코드다. 지울지 고칠지는 언제나 사람과 모델이 정한다(CLAUDE.md).

## 채널은 필기본이다 (㉞)

v1은 필기를 지운 `model_input.pdf`에 그렸다. 관리자가 필기본으로 바꿨다.
**알고 있는 위험**은 필기에 답이 적혀 있으면 가려도 그 필기가 답을 보여 준다는
것이었다. 첫 렌더에서 바로 나왔다 — s13에서 인쇄된 `(beta globin)`을 덮었는데
하단 필기가 `beta-globin allele 건드리는 혈액질환`이라고 적고 있었다.

그래서 `annotations.json`의 `notes`를 같은 잣대로 함께 센다. `260819_01`의 후보
슬라이드에서 라벨 267개 중 **7개**가 그 슬라이드 필기에 글자로 또 있었다.

**못 세는 것이 남는다** — 필기가 답을 바꿔 말하거나(`같은 유전자의 결과이다`),
글자가 아니라 그림으로 그려져 있으면 이 검사가 못 본다. 그건 눈이 유일한 장치다.
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

from quiz.occlusion import (  # noqa: E402
    ACCENT,
    valid_rect,
    build_label_index,
    render_occlusion_pair,
    resolve_rects,
)
from quiz.textutil import safe_filename, safe_media_prefix  # noqa: E402
import fitz  # noqa: E402
from quiz import timings  # noqa: E402
from quiz2 import prompt as prompt_mod  # noqa: E402


# 후보를 좁히는 조건. **한도가 아니라 추림이다** — 목록에 있어도 안 만들어도 된다
# (㉚ "회수 목표가 있는 것만").
#
# **그림이 있는 슬라이드만 본다.** 목표가 "텍스트로 표현할 수 없는 것을 내는 것"이라
# 그림이 없으면 이 패스의 일이 아니다(2026-08-20 관리자). 라벨 수는 안 본다 —
# 제목만 달린 조직학 사진이 그 관문에서 탈락하고 있었다.
#
# 둘 중 하나면 후보다. **벡터를 따로 세는 이유가 실측에 있다** — 도형으로 그린
# 도식은 래스터 블록이 없다. `260819_02` s12(유전자 구조도)가 래스터 3%인데
# 벡터 경로 29개였고, 그림이 진짜 없는 s13은 1개였다.
MIN_FIGURE_AREA = 0.10      # 가장 큰 래스터 그림이 쪽 면적에서 차지하는 비율
MIN_VECTOR_COVER = 0.25     # 벡터 경로들이 덮는 넓이. **개수보다 이게 깨끗하다**
#
# 개수로 재면 안 갈린다 — 문턱 5로 잡으니 `260819_01`이 67장 중 48장을 통과시켰다.
# 넓이로 재면 `260819_02`가 `0.37 → 0.00`으로 낭떠러지가 생긴다(19장이 정확히 0).
# **다만 두 편으로 잡은 값이다.** 넉넉히 통과시키고 모델이 넘기는 쪽을 골랐다.

# 오려낼 후보로 목록에 올릴 그림의 최소 면적. 마스코트·배지 따위를 뺀다.
FIGURE_LIST_MIN_AREA = 0.03

# 배치 하나가 맡는 후보 슬라이드 수. 렌더-확인-수정을 슬라이드마다 도는 자리라
# 한 배치를 크게 잡으면 문맥이 길어진다. `reproduce.py`와 같은 이유의 값이다.
BATCH_SIZE = 5

# 각인 라벨. 모든 슬라이드에 하나씩 있고 가릴 이유가 없다.
_STAMP_RE = re.compile(r"^Slide\s+\d+$")

# 누출 비교용. **낱말 배열로 잰다.** 뭉갠 문자열로 재면 오탐이 섞인다 —
# `260819_01`에서 실제로 `Male` ⊂ `Female`, `1 in 250` ⊂ `1 in 25,000`이 걸렸다.
# 낱말로 끊으면 둘 다 안 걸리고, v1에서 실제로 샌 것(캡션 `Disuse atrophy`가 바로
# 아래 URL `.../disuse-atrophy`에 그대로 있던 것)은 그대로 걸린다.
_TOKEN_RE = re.compile(r"[0-9]+|[a-z]+|[가-힣]+")

# 이보다 짧은 라벨은 누출 검사에서 뺀다. `Yes`·`No` 같은 것이 슬라이드 곳곳에 있어
# 전부 걸리면 신호가 죽는다.
LEAK_MIN_CHARS = 4


def _text(value) -> str:
    return str(value or "").strip()


def _tokens(value: str) -> list[str]:
    return _TOKEN_RE.findall(str(value or "").lower())


def _contains_tokens(haystack: list[str], needle: list[str]) -> bool:
    """`needle`이 `haystack`에 **낱말 단위로 이어서** 들어 있나."""
    if not needle or len(needle) > len(haystack):
        return False
    return any(haystack[i:i + len(needle)] == needle
               for i in range(len(haystack) - len(needle) + 1))


def load_labels(run_dir: Path, prep: dict) -> dict[str, list[dict]]:
    path = run_dir / "labels.json"
    if not path.exists():
        path = Path(_text(prep.get("labels_path")))
    if not path.exists():
        raise SystemExit(f"labels.json이 없다: {run_dir}. prep.py를 먼저 돌려라")
    return json.loads(path.read_text(encoding="utf-8")).get("slides") or {}


def page_shapes(source, slide_no: int) -> tuple[float, float, list[dict]]:
    """한 쪽의 (가장 큰 래스터 그림 면적, 벡터가 덮는 넓이, 오려낼 만한 그림들).

    **래스터만 자를 좌표를 준다.** 벡터 도식은 경로 bbox의 합집합이 본문까지
    삼킨다 — `260819_02` s12에서 67%, s7에서 76%였다. 그래서 벡터는 **후보인지
    가르는 데만** 쓰고, 자를 자리는 모델이 지도를 보고 정한다.
    """
    doc = fitz.open(str(source))
    page = doc.load_page(int(slide_no) - 1)
    width, height = page.rect.width, page.rect.height
    area = (width * height) or 1.0

    figures: list[dict] = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 1:
            continue
        x0, y0, x1, y1 = block["bbox"]
        size = ((x1 - x0) * (y1 - y0)) / area
        if size < FIGURE_LIST_MIN_AREA:
            continue
        figures.append({"rect": [round(x0 / width, 5), round(y0 / height, 5),
                                 round(x1 / width, 5), round(y1 / height, 5)],
                        "area": round(size, 3)})
    figures.sort(key=lambda f: -f["area"])
    for index, figure in enumerate(figures, start=1):
        figure["id"] = f"s{int(slide_no):03d}_f{index:02d}"

    union = None
    for path in page.get_drawings():
        rect = path.get("rect")
        if not rect:
            continue
        # 배경 사각형(거의 전면)은 빼고 나머지를 다 합친다.
        if (rect.width * rect.height) / area > 0.6:
            continue
        union = rect if union is None else (union | rect)
    cover = ((union.width * union.height) / area) if union else 0.0
    doc.close()
    biggest = figures[0]["area"] if figures else 0.0
    return biggest, round(cover, 3), figures


def slide_labels(labels: dict, slide_no: int) -> list[dict]:
    """각인 라벨을 뺀 그 슬라이드의 라벨 후보."""
    return [e for e in labels.get(str(int(slide_no)), [])
            if not _STAMP_RE.match(_text(e.get("text")))]


def existing_items(run_dir: Path) -> list[dict]:
    """1단계가 낸 카드. 합치기 전이라 조각 파일에서 직접 읽는다.

    이 패스는 **1단계 뒤, merge 앞**에 선다 — 어느 슬라이드에 회수 목표가 있었는지는
    이미 나온 카드가 말해 주고(㉚), 결과는 `items.raw.occl_bNN.json`으로 떨어져
    merge가 나머지와 함께 주워 간다.
    """
    items: list[dict] = []
    for path in sorted(run_dir.glob("items.raw.*.json")):
        if path.name == "items.raw.json" or ".occl" in path.name:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        items.extend(payload.get("cards") or payload.get("items") or [])
    return items


def candidates(run_dir: str | Path) -> list[dict]:
    """오클루전을 시도해 볼 만한 슬라이드. **추림이지 한도가 아니다.**

    올리는 길이 둘이다.

    - **래스터 그림이 넓다** (`raster >= MIN_FIGURE_AREA`). 자를 좌표도 함께 나온다
    - **벡터가 넓게 덮었고**(`cover >= MIN_VECTOR_COVER`) **1단계가 그 슬라이드의
      그림·표를 근거로 카드를 냈다**(`figure_card`). 둘 다여야 한다

    벡터 팔이 필요한 이유가 실측에 있다 — `260819_01`에서 `image_ratio`가 0인
    슬라이드가 67장 중 45장인데, 그중에도 `figure` 근거 카드가 있는 슬라이드가
    있었다(s9의 Mutation 도식). 벡터로 그린 도식은 래스터가 아니라 비율이 0이다.

    **`figure_card`를 곱하는 이유도 실측에 있다** (2026-08-21). 그 전에는 벡터
    덮임만으로 올렸는데, 표 괘선·밑줄·글상자가 전부 벡터 경로라 **그림이 없는
    텍스트 슬라이드가 그대로 통과**했다.

        260819_03  후보 29장 → 벡터만으로 올라온 13장 중 카드가 된 것 1장 (8%)
                              래스터로 올라온 16장 중            14장 (88%)

    벡터 팔에 `figure_card`를 곱하면 세 편 모두 **채택된 슬라이드를 하나도 안
    잃고** 후보가 준다 — `260819_03` 29→19, `260819_02` 14→10, `260819_01` 31→26.
    벡터로만 올라와 채택된 유일한 장(`260819_03` s26)이 `figure_card`가 참이다.

    배치는 후보 5장씩 끊으므로 이 관문이 곧 배치 수다(29장이면 6, 19장이면 4).
    """
    run_dir = Path(run_dir)
    prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))
    structure = json.loads((run_dir / "structure.json").read_text(encoding="utf-8"))
    labels = load_labels(run_dir, prep)
    features = {f["slide_no"]: f for f in json.loads(
        (run_dir / "page_features.json").read_text(encoding="utf-8"))}
    items = existing_items(run_dir)

    figure_slides = {int(i["slide_no"]) for i in items
                     if _text(i.get("evidence_type")) in ("figure", "table")
                     and _text(i.get("slide_no"))}
    carded = {int(i["slide_no"]) for i in items if _text(i.get("slide_no"))}

    source = prep.get("annotated_pdf") or prep.get("source_pdf")
    lo, hi = (int(structure["lecture_range"][0]), int(structure["lecture_range"][1]))
    rows: list[dict] = []
    for slide_no in range(lo, hi + 1):
        raster, cover, figures = page_shapes(source, slide_no)
        figure_card = slide_no in figure_slides
        if raster < MIN_FIGURE_AREA and not (cover >= MIN_VECTOR_COVER and figure_card):
            continue
        rows.append({
            "slide_no": slide_no,
            "raster": raster,
            "vector_cover": cover,
            "figures": figures,
            "figure_card": figure_card,
            "carded": slide_no in carded,
            "labels": slide_labels(labels, slide_no),
        })
    return rows


# ── 그림으로 주는 것 두 가지 ────────────────────────────────────────────
#
# 도구 호출을 줄이려고 넣었다. `260819_02` 1회차가 29회였고, 그중 상당수가
# **좌표를 지어내고 틀린 것을 렌더로 확인하는 데** 들었다.

LABELMAP_SCALE = 2.0
SHEET_GAP = 12

# 지도에 그리는 눈금. **페이지 기준으로 매긴다** — 지도는 각인 띠를 잘라낸 슬라이드
# 비율인데 좌표는 페이지 분모를 쓰므로, 눈금이 없으면 모델이 `y/1.0556`을 손으로
# 곱해야 한다. `260819_03`에서 배치 하나가 그 계산을 하느라 Bash 19회 중 13회를
# 즉석 PIL 스크립트에 썼다. 눈금을 그리면 읽어서 그대로 적으면 된다.
GRID_STEP = 0.05            # 선 간격 (페이지 정규화)
GRID_LABEL_EVERY = 2        # 이 선마다 숫자를 적는다 (0.1마다)
GRID_COLOR = (0.55, 0.55, 0.58)


def render_label_map(source, slide_no: int, entries: list[dict], out_dir: Path,
                     basename: str, band_pt: float = 0.0,
                     figures: list[dict] | None = None) -> str:
    """라벨 상자를 다 그리고 id를 찍은 한 장. **좌표를 지어낼 일을 없앤다.**

    `labels.json`에 좌표가 이미 다 있으므로 코드가 공짜로 만든다. 이걸 주면 고를 때
    `label_ids`만 쓰면 되고, 그러면 분모 문제도 `rect_clips_label`도 안 생긴다.

    상자는 **테두리만** 그린다 — 안이 보여야 무엇을 가릴지 고를 수 있다.

    **눈금도 함께 그린다**(2026-08-21). 라벨로 안 잡히는 자리를 가리거나 오릴 때는
    좌표를 직접 적어야 하는데, 지도는 각인 띠를 잘라낸 슬라이드 비율이고 좌표는
    페이지 분모라 그 값이 어긋난다. 눈금을 **페이지 기준**으로 매겨 두면 읽은 값을
    그대로 적으면 된다.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    src = fitz.open(str(source))
    pix = src.load_page(int(slide_no) - 1).get_pixmap(
        matrix=fitz.Matrix(LABELMAP_SCALE, LABELMAP_SCALE), alpha=False)
    src.close()

    doc = fitz.open()
    page = doc.new_page(width=pix.width, height=pix.height)
    page.insert_image(fitz.Rect(0, 0, pix.width, pix.height), pixmap=pix)

    # 눈금 먼저. 라벨 상자보다 아래에 깔려야 상자가 안 가려진다.
    keep_h = pix.height - float(band_pt) * LABELMAP_SCALE if band_pt else pix.height
    ticks = int(round(1.0 / GRID_STEP))
    tick_size = 7.0 * LABELMAP_SCALE
    for i in range(1, ticks):
        value = i * GRID_STEP
        labelled = (i % GRID_LABEL_EVERY == 0)
        x = value * pix.width
        page.draw_line(fitz.Point(x, 0), fitz.Point(x, keep_h), color=GRID_COLOR,
                       width=(0.9 if labelled else 0.4), dashes="[3 6] 0", overlay=True)
        y = value * pix.height          # ← 페이지 분모. 지도가 잘려도 값은 그대로다
        if y < keep_h:
            page.draw_line(fitz.Point(0, y), fitz.Point(pix.width, y), color=GRID_COLOR,
                           width=(0.9 if labelled else 0.4), dashes="[3 6] 0", overlay=True)
        if not labelled:
            continue
        text = f"{value:.1f}"
        chip = fitz.Rect(x + 1, 1, x + tick_size * 2.4, tick_size + 4)
        page.draw_rect(chip, color=None, fill=(1, 1, 1), overlay=True)
        page.insert_text((chip.x0 + 1, chip.y1 - 3), text, fontsize=tick_size,
                         color=GRID_COLOR, fontname="helv")
        if y < keep_h:
            chip = fitz.Rect(1, y + 1, tick_size * 2.4, y + tick_size + 4)
            page.draw_rect(chip, color=None, fill=(1, 1, 1), overlay=True)
            page.insert_text((chip.x0 + 1, chip.y1 - 3), text, fontsize=tick_size,
                             color=GRID_COLOR, fontname="helv")

    for entry in entries:
        raw = entry.get("rect")
        if not raw:
            continue
        rect = fitz.Rect(raw[0] * pix.width, raw[1] * pix.height,
                         raw[2] * pix.width, raw[3] * pix.height)
        page.draw_rect(rect, color=ACCENT, width=1.2 * LABELMAP_SCALE, overlay=True)
        # id는 상자 **왼쪽 위 바깥**에 흰 칩으로. 안에 찍으면 라벨을 가린다.
        tag = str(entry.get("id", ""))[-3:]
        size = 8.0 * LABELMAP_SCALE
        chip = fitz.Rect(rect.x0 - 1, max(0, rect.y0 - size - 3),
                         rect.x0 + size * 2.2, max(size, rect.y0 - 1))
        page.draw_rect(chip, color=ACCENT, fill=(1, 1, 1), width=0.8, overlay=True)
        page.insert_text((chip.x0 + 2, chip.y1 - 3), tag, fontsize=size,
                         color=ACCENT, fontname="helv")

    # 오려낼 그림은 굵은 파란 테두리로. 라벨(마젠타)과 눈으로 갈리게 한다.
    for figure in (figures or []):
        raw = figure["rect"]
        rect = fitz.Rect(raw[0] * pix.width, raw[1] * pix.height,
                         raw[2] * pix.width, raw[3] * pix.height)
        page.draw_rect(rect, color=(0.0, 0.35, 0.9), width=2.4 * LABELMAP_SCALE,
                       overlay=True)
        tag = str(figure.get("id", ""))[-3:]
        size = 10.0 * LABELMAP_SCALE
        chip = fitz.Rect(rect.x0 - 1, rect.y0 - 1, rect.x0 + size * 2.6,
                         rect.y0 + size + 3)
        page.draw_rect(chip, color=(0.0, 0.35, 0.9), fill=(1, 1, 1), width=0.8,
                       overlay=True)
        page.insert_text((chip.x0 + 3, chip.y1 - 4), tag, fontsize=size,
                         color=(0.0, 0.35, 0.9), fontname="helv")

    name = f"{basename}_map.png"
    clip = fitz.Rect(0, 0, pix.width, keep_h) if band_pt else None
    page.get_pixmap(alpha=False, clip=clip).save(str(out_dir / name))
    doc.close()
    return name


def render_figure_crop(source, slide_no: int, rect: list[float], out_dir: Path,
                       basename: str, band_pt: float = 0.0) -> str:
    """그림만 오려낸 한 장. **앞면에 이것만 선다.**

    채널은 **clean**이다(㉞의 예외). 마스킹 카드는 필기본에 그리지만, 오려내는
    카드는 답이 그림의 이름이라 **필기가 답을 적어 두면 그대로 샌다** — 관리자가
    든 예시 슬라이드에서도 사진 옆 필기가 `심하면 kernicterus`라고 적고 있었다.
    오려내면 그 필기는 사각형 밖이라 안 들어오지만, 채널까지 clean으로 두면
    사진 위에 얹힌 필기도 안 들어온다.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(source))
    page = doc.load_page(int(slide_no) - 1)
    width, height = page.rect.width, page.rect.height
    clip = fitz.Rect(rect[0] * width, rect[1] * height,
                     rect[2] * width, rect[3] * height)
    name = f"{basename}_crop.png"
    page.get_pixmap(matrix=fitz.Matrix(LABELMAP_SCALE, LABELMAP_SCALE),
                    alpha=False, clip=clip).save(str(out_dir / name))
    doc.close()
    return name


def render_contact_sheet(paths: list[Path], out_path: Path) -> str:
    """앞면들을 한 장으로 이어 붙인다. **한 바퀴에 한 번만 읽으면 된다.**

    카드마다 따로 읽으면 바퀴마다 카드 수만큼 호출이 든다.
    """
    pixmaps = [fitz.Pixmap(str(path)) for path in paths if Path(path).exists()]
    if not pixmaps:
        return ""
    width = max(p.width for p in pixmaps)
    height = sum(p.height for p in pixmaps) + SHEET_GAP * (len(pixmaps) - 1)
    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    page.draw_rect(fitz.Rect(0, 0, width, height), fill=(1, 1, 1), width=0)
    y = 0.0
    for pix in pixmaps:
        page.insert_image(fitz.Rect(0, y, pix.width, y + pix.height), pixmap=pix)
        y += pix.height + SHEET_GAP
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    page.get_pixmap(alpha=False).save(str(out_path))
    doc.close()
    return str(out_path)


def resolve_crop(item: dict, source) -> tuple[list[float] | None, str]:
    """카드의 `crop`/`crop_rect` → 정규화 좌표. (좌표, 문제)를 낸다.

    `crop`은 지도에 찍힌 그림 id(`s013_f01`)다. 벡터 도식은 그 id가 없으므로
    `crop_rect`로 직접 적는다.
    """
    occlusion = item.get("occlusion") or {}
    raw = occlusion.get("crop_rect")
    if raw:
        if valid_rect(raw):
            return [float(v) for v in raw], ""
        return None, f"invalid_crop_rect({raw})"

    crop_id = _text(occlusion.get("crop"))
    if not crop_id:
        return None, ""
    slide_no = int(item.get("slide_no") or 0)
    _, _, figures = page_shapes(source, slide_no)
    for figure in figures:
        if figure["id"] == crop_id:
            return figure["rect"], ""
    known = ", ".join(f["id"] for f in figures) or "없음"
    return None, f"unknown_crop_id({crop_id}; 이 슬라이드의 그림: {known})"


# ── 코드가 잡아 주는 결함 ──────────────────────────────────────────────

def _overlaps(a: list[float], b: list[float]) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _contains(outer: list[float], inner: list[float]) -> bool:
    return (outer[0] <= inner[0] and outer[1] <= inner[1]
            and outer[2] >= inner[2] and outer[3] >= inner[3])


def check_card(item: dict, labels: dict, notes: dict | None = None) -> list[str]:
    """가린 뒤에도 답이 보이는가. **좌표와 문자열로 셀 수 있는 것만 본다.**

    감사가 못 잡았다고 기록된 것들이다(`CLAUDE.md`). 세기만 하고 판정하지 않는다.

    `notes`는 `{슬라이드번호: [필기 문자열]}`. ㉞이 경고한 자리를 여기서 센다.
    """
    occlusion = item.get("occlusion") or {}
    slide_no = int(item.get("slide_no") or 0)
    entries = slide_labels(labels, slide_no)
    by_id = {e["id"]: e for e in entries if e.get("id")}
    problems: list[str] = []

    answer_ids = [str(i) for i in (occlusion.get("label_ids") or [])]
    mask_ids = [str(i) for i in (occlusion.get("mask_label_ids") or [])]
    covered = set(answer_ids) | set(mask_ids)

    # ① ㉝ — 가린 답이 슬라이드 다른 자리에 글자로 그대로 있다.
    for lid in answer_ids:
        entry = by_id.get(lid)
        if not entry:
            continue
        needle = _tokens(entry.get("text"))
        if sum(len(t) for t in needle) < LEAK_MIN_CHARS:
            continue
        for other in entries:
            if other.get("id") in covered or other.get("id") == lid:
                continue
            hay = _tokens(other.get("text"))
            if _contains_tokens(hay, needle) or _contains_tokens(needle, hay):
                problems.append(
                    f"answer_text_elsewhere({lid} '{_text(entry.get('text'))[:24]}'"
                    f" → {other.get('id')} '{_text(other.get('text'))[:24]}')")
                break

    # ② ㉞ — 가린 답이 그 슬라이드 필기에 글자로 또 있다.
    note_tokens = _tokens(" ".join((notes or {}).get(slide_no) or []))
    if note_tokens:
        for lid in answer_ids:
            entry = by_id.get(lid)
            if not entry:
                continue
            needle = _tokens(entry.get("text"))
            if sum(len(t) for t in needle) < LEAK_MIN_CHARS:
                continue
            if _contains_tokens(note_tokens, needle):
                problems.append(
                    f"answer_text_in_annotation({lid} "
                    f"'{_text(entry.get('text'))[:24]}')")

    # ③ 직접 적은 좌표가 라벨을 걸치기만 하고 다 못 덮었다.
    for key in ("rects", "mask_rects"):
        for raw in occlusion.get(key) or []:
            try:
                rect = [float(v) for v in raw]
            except (TypeError, ValueError):
                continue
            for entry in entries:
                label_rect = entry.get("rect")
                if not label_rect:
                    continue
                if _overlaps(rect, label_rect) and not _contains(rect, label_rect):
                    problems.append(
                        f"rect_clips_label({key} {rect} ⊅ {entry.get('id')}"
                        f" '{_text(entry.get('text'))[:24]}')")
    return problems


# ── 렌더 ───────────────────────────────────────────────────────────────

def render(run_dir: str | Path, items_name: str) -> dict:
    """오클루전 카드마다 앞/뒤 PNG를 뽑고, 기계가 볼 수 있는 것을 함께 센다."""
    run_dir = Path(run_dir)
    prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))
    labels = load_labels(run_dir, prep)
    label_index = build_label_index({"slides": labels})

    notes_file = run_dir / "annotations.json"
    notes: dict[int, list[str]] = {}
    if notes_file.exists():
        for entry in json.loads(notes_file.read_text(encoding="utf-8")):
            notes[int(entry.get("slide_no") or 0)] = entry.get("notes") or []

    payload = json.loads((run_dir / items_name).read_text(encoding="utf-8"))
    items = payload.get("cards") or payload.get("items") or []
    targets = [i for i in items if i.get("occlusion")]

    # ㉞ 필기본에 그린다. v1은 필기를 지운 채널이었다.
    source = prep.get("annotated_pdf") or prep.get("source_pdf")
    out_dir = run_dir / "occl_preview"
    prefix = safe_media_prefix(prep["source_stem"])

    # 오려내는 카드는 **clean**에서 뽑는다 — 답이 그림의 이름이라 필기가 답을
    # 적어 두면 그대로 샌다.
    clean = prep.get("model_input_pdf") or prep.get("source_pdf")

    rows: list[dict] = []
    for index, item in enumerate(targets):
        slide_no = int(item.get("slide_no") or 0)
        crop_rect, crop_problem = resolve_crop(item, clean)
        if crop_rect or crop_problem:
            row = {"id": _text(item.get("id")) or f"n{index + 1:02d}",
                   "slide_no": slide_no, "boxes": 0, "masks": 0, "kind": "crop",
                   "problems": [crop_problem] if crop_problem else []}
            if crop_rect:
                basename = f"{prefix}_occl_s{slide_no:03d}_{safe_filename(str(row['id']))}"
                name = render_figure_crop(clean, slide_no, crop_rect, out_dir,
                                          basename,
                                          band_pt=float(prep.get("stamp_band_pt") or 0.0))
                row["front"] = str(out_dir / name)
            rows.append(row)
            continue

        rects, masks, problems = resolve_rects(
            item.get("occlusion") or {}, slide_no, label_index)
        # merge가 붙이기 전이라 `id`가 없다. 파일 이름이 질문 앞머리가 되면
        # 길고 편마다 달라지므로 자리 번호로 대신한다.
        row = {
            "id": _text(item.get("id")) or f"n{index + 1:02d}",
            "slide_no": slide_no,
            "kind": "mask",
            "boxes": len(rects),
            "masks": len(masks),
            "problems": problems + check_card(item, labels, notes),
        }
        if rects:
            basename = f"{prefix}_occl_s{slide_no:03d}_{safe_filename(str(row['id']))}"
            front, back = render_occlusion_pair(
                source, slide_no, rects, out_dir, basename,
                band_pt=float(prep.get("stamp_band_pt") or 0.0), masks=masks)
            row["front"] = str(out_dir / front)
            row["back"] = str(out_dir / back)
        rows.append(row)

    sheet = ""
    fronts = [Path(r["front"]) for r in rows if r.get("front")]
    if len(fronts) > 1:
        sheet = render_contact_sheet(
            fronts, out_dir / f"{Path(items_name).stem}_sheet.png")

    return {"items": len(items), "occlusion": len(targets), "out_dir": str(out_dir),
            "source": str(source), "cards": rows, "sheet": sheet,
            "flagged": sum(1 for r in rows if r["problems"])}


# ── 스폰 문구 ──────────────────────────────────────────────────────────

DO_NOT = """\
## 하지 말 것

- **1단계가 만든 카드 파일을 열지 마라.** 겹치는지는 아래 「이미 나온 카드」를 보면 된다
- **`labels.json`을 열지 마라.** 네 후보 슬라이드의 라벨은 전부 아래 표에 있다
- **`quiz/occlusion.py`나 `validate.py`를 읽거나 돌리지 마라.**
  좌표를 푸는 것도 그리는 것도 아래 `render` 한 줄이 한다
- **후보를 다 쓰려고 하지 마라.** 회수 목표가 없는 그림은 그냥 넘긴다 (㉚)
"""


def _label_table(row: dict) -> str:
    if row.get("map"):
        lines = [f"### 슬라이드 {row['slide_no']} — 지도: `{row['map']}`", ""]
        if row.get("figures"):
            lines.append("**오려낼 수 있는 그림** (지도의 파란 상자)")
            lines.append("")
            for f in row["figures"]:
                lines.append(f"- `{f['id']}` — 쪽 면적의 {f['area']:.0%}")
            lines.append("")
        else:
            lines.append("이 슬라이드는 **벡터로 그린 도식**이라 오려낼 그림이 "
                         "자동으로 안 잡힌다. 오리려면 `crop_rect`로 직접 적어라.")
            lines.append("")
        lines += [
                 "**이 지도를 읽어라.** 라벨마다 상자와 끝 세 글자(`l02` 꼴)가 찍혀 "
                 "있다. 무엇을 가릴지는 그림을 봐야 정해진다.", "",
                 "| label_id | 글자 |", "|---|---|"]
        for e in row["labels"]:
            lines.append(f"| `{e['id']}` | {_text(e.get('text')).replace('|', '/')} |")
        return "\n".join(lines)
    lines = [f"### 슬라이드 {row['slide_no']}"
             f"  (그림 비율 {row['image_ratio']}"
             + (", 1단계가 그림·표를 근거로 카드를 냈다" if row["figure_card"] else "")
             + ")",
             "",
             "| label_id | 글자 |", "|---|---|"]
    for e in row["labels"]:
        lines.append(f"| `{e['id']}` | {_text(e.get('text')).replace('|', '/')} |")
    return "\n".join(lines)


def coord_note(prep: dict) -> str:
    """직접 적는 좌표의 **분모가 슬라이드가 아니라 페이지**라는 것.

    각인을 놓으려고 페이지 아래에 빈 띠를 붙여 뒀다(`prep.json`의 `stamp_band_pt`).
    `labels.json`의 정규화 분모가 그 띠를 포함한 높이이고, 직접 적는 좌표도 같은
    분모를 써야 라벨과 섞일 수 있다.

    **안 적어 뒀더니 첫 실행에서 바로 걸렸다** — `260819_02`에서 어떤 실행이 슬라이드
    기준으로 y를 적어 상자 셋이 한 행 아래를 덮었고, 렌더를 두 번 더 돌려 눈으로
    잡아냈다. 그때 실측으로 찾은 배율 1.0503이 아래 계산과 같다.
    """
    source = prep.get("annotated_pdf") or prep.get("source_pdf")
    band = float(prep.get("stamp_band_pt") or 0.0)
    if not source or not band:
        return ""
    try:
        doc = fitz.open(str(source))
        height = float(doc.load_page(0).rect.height)
        doc.close()
    except Exception:
        return ""
    if height <= band:
        return ""
    factor = height / (height - band)
    return (
        "## 직접 좌표를 적을 때 — **지도의 눈금을 읽어라**\n\n"
        "지도에 점선 눈금이 0.05마다 그어져 있고 위·왼쪽 가장자리에 0.1마다 숫자가"
        " 찍혀 있다. **그 숫자가 곧 여기 적을 값이다.** 계산하지 마라.\n\n"
        "    x0, y0 = 상자 왼쪽 위 눈금        x1, y1 = 오른쪽 아래 눈금\n\n"
        f"눈금은 **페이지 기준**으로 매겨져 있다. 각인을 놓으려고 페이지 아래에 빈"
        f" 띠가 {band:.0f}pt 붙어 있어서(페이지 {height:.0f}pt · 슬라이드"
        f" {height - band:.0f}pt) 지도 이미지의 픽셀로 재면 y가 어긋나는데, 눈금이"
        f" 그 어긋남을 이미 먹었다 — 예전에는 잰 y를 {factor:.4f}로 나눠 적어야"
        f" 했다.\n\n"
        "**픽셀을 재는 스크립트를 쓰지 마라.** 위 표의 라벨 좌표와 눈금이 같은 자다."
    )


def spawn_prompt(run_dir: Path, rows: list[dict], batch: str, out_path: Path,
                 nearby: list[dict], prep: dict | None = None) -> str:
    parts = [
        f"# 오클루전 패스 `{batch}` — 슬라이드 "
        + ", ".join(str(r["slide_no"]) for r in rows),
        ("그림의 라벨을 가린 앞면과 드러낸 뒷면이 붙는 카드를 만든다.\n\n"
         "**이 작업만 한 번에 안 끝난다.** 상자를 고르고, 렌더해서, 라벨을 덜 덮었는지 "
         "눈으로 보고, 고친다. 아래 「돌리는 법」이 그 고리다."),
        prompt_mod.OCCLUSION,
        '## 카드 두 꼴\n\n**목표는 "라벨을 가리는 것"이 아니라 텍스트로 표현할 수 없는 것을 내는 것이다.**\n사진·조직학 슬라이드·그래프·모식도가 그렇다. 꼴이 둘이고, 그림에 맞는 쪽을 고른다.\n\n### ⓐ 오려서 묻는다 — **이 그림이 무엇인가**\n\n그림만 오려 앞면에 세우고, 답은 그 그림의 이름이다. 뒷면은 슬라이드 전체라 제목과\n본문으로 답을 확인한다.\n\n    "occlusion": {"crop": "s013_f01"}\n\n지도에서 **파란 상자**가 오려낼 수 있는 그림이고 `f01` 꼴로 찍혀 있다. 벡터로 그린\n도식은 파란 상자가 없다 — 그때만 `"crop_rect": [x0, y0, x1, y1]`로 직접 적는다.\n\n    ○ 이 조직 소견의 진단명은?              → 조직학 사진\n    ○ 이 육안 소견에서 노랗게 착색된 부위가 뜻하는 병태는?\n    ✗ Kernicterus는 무엇 때문에 생기는가?    ← 그림이 없어도 되는 질문이다\n\n**앞면에 이름이 남으면 안 된다.** 오려낸 사각형 안에 제목이나 캡션이 들어오면\n`crop_rect`로 그 부분을 잘라 내라.\n\n### ⓑ 라벨을 가린다 — **어느 부분이 무엇인가**\n\n위치와 이름의 대응이 지식일 때다. 지도에서 **마젠타 상자**(`l02` 꼴)를 고른다.\n\n    "occlusion": {"label_ids": ["s013_l01", "s013_l04"],\n                  "mask_label_ids": ["s013_l07"]}\n\n    ○ A~C로 표시된 세 성분의 이름은?         → Stromal / Blastemal / Epithelial\n    ○ A~E로 표시된 다섯 곡선이 각각 뜻하는 것은?\n\n',
        "## 네가 맡은 후보\n\n"
        "1단계가 그림·표를 근거로 카드를 냈거나 그림 비율이 높은 슬라이드다. "
        "**추림이지 한도가 아니다** — 회수 목표가 없으면 넘기고 된다.\n\n"
        "**고르는 것은 `label_ids`다.** 슬라이드마다 라벨 지도 PNG가 있으니 그것만 "
        "읽고 id를 고르면 된다. **좌표를 손으로 지어내지 마라** — 지도에 없는 자리를 "
        "꼭 가려야 할 때만 아래 「직접 좌표」로 간다.\n\n"
        + "\n\n".join(_label_table(r) for r in rows),
    ]

    note = coord_note(prep or {})
    if note:
        parts.append(note)

    if nearby:
        lines = ["## 이미 나온 카드 (겹치지 마라)", "",
                 "1단계가 이 슬라이드들에서 낸 카드다. 같은 것을 그림으로 다시 묻는 것은 "
                 "중복이 아니지만(회수 방향이 다르다), **같은 회수 방향을 두 번 내지는 "
                 "마라.**", ""]
        for i in nearby:
            lines.append(f"- s{i.get('slide_no')} · {_text(i.get('q'))[:70]}")
        parts.append("\n".join(lines))

    parts.append(f"""\
## 돌리는 법

1. 상자를 고르고 아래 꼴로 `{out_path}`에 쓴다
2. 렌더한다

       python -m quiz2.occlusion render {run_dir} --items {out_path.name}

3. 나온 **접촉 시트 한 장**을 `Read`로 본다 (카드가 둘 이상이면 렌더가 앞면을
   한 장으로 이어 붙여 준다). 확인할 것은 셋이다
   - 가려야 할 글자가 상자 밖으로 삐져나오지 않았나
   - 가리지 말아야 할 것까지 덮지 않았나
   - 답이 슬라이드 다른 자리에 그대로 보이지 않나 (필기도 포함이다)
4. 어긋났으면 고쳐 쓰고 2로 돌아간다. **여기서는 고쳐 쓰는 것이 정상이다** —
   다른 패스와 다른 점이다

렌더가 두 가지를 대신 세어 준다. 감사가 못 잡던 자리다.

    answer_text_elsewhere      가린 답이 안 가린 다른 라벨에 글자로 또 있다
                               → 버리지 말고 그 자리를 `mask_label_ids`로 덮어라
    answer_text_in_annotation  가린 답이 그 슬라이드 **필기**에 글자로 또 있다
    rect_clips_label           직접 적은 좌표가 라벨을 걸치기만 하고 다 못 덮었다

**세어 주는 것은 여기까지다.** 필기가 답을 **바꿔 말하거나**(`같은 유전자의
결과이다`) 글자가 아니라 **그림으로** 그려져 있으면 코드가 못 본다.
그건 3번에서 네 눈이 유일한 장치다.

**상자는 필기도 덮는다.** 렌더가 페이지를 먼저 평탄화한 뒤 그리므로 인쇄 글자든
필기든 상자 아래는 다 가려진다. `label_ids`·`rects`·`mask_rects`가 전부 같다 —
그리는 코드가 하나다. 그러니 **필기가 답을 적어 놨다는 이유로 카드를 버리지 마라.**
그 자리를 `mask_rects`로 덮으면 된다 (㉝).

한 번 틀린 자리라 적어 둔다 — `260819_02`에서 어떤 실행이 "마스크는 필기를 못
가린다"고 판단해 멀쩡한 카드를 버렸다. 재 보니 덮였다. 의심되면 덮어서 렌더하고
**눈으로 확인해라.**""")

    parts.append(DO_NOT)
    parts.append(f"""\
## 출력

`{out_path}`에 JSON 하나로 쓴다.

```json
{{
  "cards": [
    {{"q": "A로 표시된 구조의 이름은?", "a": "...", "explanation": "...",
     "slide_no": 13, "card_type": "fact", "card_format": "basic",
     "importance": "core", "exam_hit": false,
     "evidence_type": "figure", "source_type": "lecture",
     "occlusion": {{"label_ids": ["s013_l01"],
                   "mask_label_ids": ["s013_l07"],
                   "rects": [], "mask_rects": []}}}}
  ]
}}
```

- `card_type`은 `fact` `comparison` `mechanism` `trap` `list` `sequence` 여섯 중 하나,
  `importance`는 **`core` / `detail` 둘뿐**, `card_format`은 `basic` `cloze` `ox`,
  `evidence_type`은 `figure` `table` `lecture_text` `annotation`, `source_type`은
  `lecture`. **여기 없는 값을 지어내지 마라** — `260819_02`에서 `importance`에
  `support`가 나왔고, 그건 이 문구가 허용값을 안 적어 둬서였다
- `label_ids`가 **답 상자**다. 앞면에 `A`·`B`… 표식이 붙고 학습자가 그 수만큼 회수한다
- `mask_label_ids`는 **표식이 안 붙는 덮개**다. 답이 딴 데 적힌 자리를 덮는 데 쓴다.
  회수 대상이 아니므로 개수에 안 센다 (㉝)
- 라벨이 안 잡힌 그림은 `rects`/`mask_rects`에 `[x0, y0, x1, y1]`을 0~1로 적는다
- 답 상자가 하나도 없으면 물을 것이 없다. 그런 카드는 쓰지 마라""")
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def plan(run_dir: str | Path, batch_size: int = BATCH_SIZE) -> dict:
    run_dir = Path(run_dir)
    rows = candidates(run_dir)
    items = existing_items(run_dir)
    prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))

    # 후보마다 라벨 지도 한 장. 코드가 공짜로 만들 수 있는 것을 모델이 좌표를
    # 지어내며 대신하고 있었다 (`260819_02` 1회차 도구 29회).
    source = prep.get("annotated_pdf") or prep.get("source_pdf")
    band = float(prep.get("stamp_band_pt") or 0.0)
    prefix = safe_media_prefix(prep["source_stem"])
    map_dir = run_dir / "occl_labelmap"
    for row in rows:
        name = render_label_map(source, row["slide_no"], row["labels"], map_dir,
                                f"{prefix}_s{row['slide_no']:03d}", band_pt=band,
                                figures=row.get("figures"))
        row["map"] = str(map_dir / name)
    out_dir = run_dir / "spawn"
    out_dir.mkdir(parents=True, exist_ok=True)

    made: list[dict] = []
    for index in range(0, len(rows), batch_size):
        group = rows[index:index + batch_size]
        batch = f"b{index // batch_size + 1:02d}"
        out_path = run_dir / f"items.raw.occl_{batch}.json"
        slides = {r["slide_no"] for r in group}
        nearby = [i for i in items
                  if _text(i.get("slide_no")) and int(i["slide_no"]) in slides]
        text = spawn_prompt(run_dir, group, batch, out_path, nearby, prep)
        spawn_file = out_dir / f"occl.{batch}.md"
        spawn_file.write_text(text, encoding="utf-8")
        made.append({
            "batch": batch,
            "maps": sum(1 for r in group if r.get("map")),
            "slides": sorted(slides),
            "labels": sum(len(r["labels"]) for r in group),
            "spawn": str(spawn_file),
            "out": str(out_path),
            "chars": len(text),
        })
    return {"candidates": len(rows), "batches": made}


def main() -> int:
    parser = argparse.ArgumentParser(description="오클루전 패스 (인터뷰 ㉙~㉟)")
    parser.add_argument("stage", choices=["plan", "render"])
    parser.add_argument("run_dir")
    parser.add_argument("--items", default=None,
                        help="render: 렌더할 파일명 (예: items.raw.occl_b01.json)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)

    if args.stage == "plan":
        with timings.stage(run_dir, "3.5-occl-plan"):
            result = plan(run_dir, args.batch_size)
        if not result["candidates"]:
            print("[occlusion/plan] 후보 슬라이드가 없다. "
                  "라벨이 잡힌 그림 슬라이드가 없거나 1단계가 아직 안 돌았다")
            return 0
        print(f"[occlusion/plan] 후보 {result['candidates']}장 → "
              f"배치 {len(result['batches'])}개")
        for b in result["batches"]:
            print(f"  {b['batch']}  슬라이드 {b['slides']}  라벨 {b['labels']}개  "
                  f"{b['spawn']}")
            print(f"        라벨 지도 {b['maps']}장 → {run_dir / 'occl_labelmap'}")
        print("\n배치마다 서브에이전트를 하나씩. 각자 render를 돌려 가며 고친다.")
        print("띄우기 직전·받은 직후에 찍어라 — 렌더 반복이 여기 다 들어간다:")
        print(f"    python -m quiz2.timings {run_dir} start 3.5-occlusion --label b01")
        print(f"    python -m quiz2.timings {run_dir} end   3.5-occlusion --label b01")
        return 0

    if not args.items:
        print("[occlusion/render] --items 를 줘라 (예: items.raw.occl_b01.json)")
        return 2
    result = render(run_dir, args.items)
    print(f"[occlusion/render] 카드 {result['items']}장 중 오클루전 "
          f"{result['occlusion']}장  (채널: {result['source']})")
    for row in result["cards"]:
        if row.get("kind") == "crop":
            print(f"\n  {row['id']}  s{row['slide_no']}  그림을 오려냈다")
        else:
            print(f"\n  {row['id']}  s{row['slide_no']}  "
                  f"상자 {row['boxes']} · 마스크 {row['masks']}")
        if row.get("front"):
            print(f"    앞면 {row['front']}")
        if row.get("back"):
            print(f"    뒷면 {row['back']}")
        for problem in row["problems"]:
            print(f"    ✗ {problem}")
    if result.get("sheet"):
        print("\n  앞면을 한 장으로 이어 붙였다 — **이것만 읽으면 된다**")
        print(f"    {result['sheet']}")
    if result["occlusion"]:
        print(f"\n  표시된 카드 {result['flagged']}장 / {result['occlusion']}장")
        print("  **앞면 PNG를 직접 열어 봐라.** 필기가 답을 바꿔 말하거나 "
              "그림으로 그려져 있으면 코드가 못 센다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
