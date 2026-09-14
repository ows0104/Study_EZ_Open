"""정리본·필기본 PDF 셋에서 실습 사진을 뽑는다 (이지석 · 신은주 · 2026 필기본).

    uv run --python 3.13 --with pymupdf --with pillow python scripts/extract_summary_pdf.py
    uv run ... python scripts/extract_summary_pdf.py --source jiseok --dry

`extract_practical_pdf.py`가 실제실습본 하나를 다루던 것을 **여러 묶음**으로
넓힌 것이다. 실제실습본과 달리 이 셋은 성격이 제각각이라 한 파일에 모았다.

    jiseok  이지석 정리본   6개 PDF · 19쪽   한 쪽에 사진이 수십 장 깔린 포스터형
    eunju   신은주 정리본   5개 PDF · 11쪽   같은 포스터형, 사진이 작다
    note    2026 실습 필기본 4개 PDF · 267쪽  강의 슬라이드를 학생이 필기한 것

**사진이 inline image라 xref로 원본을 꺼낼 수 없다.** 페이지를 래스터화해서
잘라내야 하고, 그래서 자르는 해상도가 곧 결과물의 해상도가 된다. 사진마다
자기 원본 해상도로 자른다(`render_dpi`).

세 가지를 조심한다.

  ① **글자를 먼저 지운다.** 정리본은 사진 위에 「oral cavity」·「stichosome」
     같은 설명을 얹어 놓는데, 그대로 구우면 정답을 적어 둔 문항이 된다.
     얹힌 것이 PDF 텍스트라 지우면 사진이 온전히 남는다. 화살표(선화)는
     남긴다 — indicator 문항이 가리키는 것이 그것이다.

  ② **표본이 아닌 그림을 버린다.** 필기본에는 현미경 사진(장비), 도표,
     그리고 **정답까지 체크된 연습문제 스크린샷**이 섞여 있다. 마지막 것은
     그대로 나가면 답이 통째로 새므로 반드시 걸러야 한다.

  ③ **버린 것을 남긴다.** 걸러 내는 규칙은 픽셀 휴리스틱이라 틀린다.
     `images/_rejects/<출처>/`에 이유를 붙여 떨어뜨려 두니 눈으로 훑고
     기준을 고치면 된다. 조용히 버리면 뭘 잃었는지 알 길이 없다.

출력: images/<출처>/<쪽>_<n>.png
      data/<출처>_manifest.json      (practical_manifest.json 과 같은 모양)
      images/_rejects/<출처>/...      (버린 것 + 이유)
"""

import contextlib
import hashlib
import json
import os
import re
import shutil
import sys

import pymupdf
from PIL import Image

from jsonio import load_json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
IMAGES = os.path.join(ROOT, "images")
KOREAN = os.path.join(ROOT, "기생충학")

# ── 출처 셋
#
# `key`가 파일 이름과 매니페스트의 `source`가 되고, `ko`가 화면에 뜨는 이름이다
# (`build_web.py`의 `SOURCE_KO`와 같아야 한다).
SOURCES = {
    "jiseok": {
        "ko": "실습 정리본(이지석)",
        "dir": os.path.join(KOREAN, "기생충학 실습 정리본_22이지석",
                            "기생충학 실습 정리본_22이지석"),
    },
    "eunju": {
        "ko": "실습 정리본(신은주)",
        "dir": os.path.join(KOREAN, "기생충학 실습 정리본_22신은주",
                            "기생충학 실습 정리본_22신은주"),
    },
    "note": {
        "ko": "2026 실습 필기본",
        "dir": os.path.join(KOREAN, "2026 실습 필기본"),
    },
}

# ── 무엇을 사진으로 볼 것인가
MIN_PX = 250          # 내장 원본이 이보다 작으면 아이콘·장식이다
MIN_PT = 28           # 페이지에 놓인 크기. 너무 작으면 캡션 옆 표식이다
MAX_ASPECT = 3.0      # 이보다 길쭉하면 띠·구분선·표다
DPI_MIN, DPI_MAX = 150, 600
MAX_SIDE = 2400       # 여기서는 넉넉히 남긴다. 화면용 축소는 `build_web.py`가 한다

# ── 글자판 판정 (표본이 아닌 그림 거르기)
#
# 현미경 사진은 시야가 밝아도 **순백이 거의 없다** — 조명이 고르지 않고
# 표본 때문에 색이 진다. 반면 슬라이드를 찍은 스크린샷은 배경이 순백에 딱
# 붙고 글자만 새까맣다. 그 차이를 흰 픽셀 비율과 채도로 가른다.
#
# 기준을 **느슨하게** 잡았다. 여기 걸리는 것은 그대로 버려지므로, 애매한
# 것은 통과시키고 `_rejects`를 훑어 좁히는 편이 낫다 — 반대로 하면 잃은
# 사진이 뭐였는지 볼 수가 없다.
PAPER_WHITE = 0.55    # 순백에 가까운 픽셀이 이만큼을 넘고
PAPER_SAT = 20        # 채도가 이만큼 아래면 '종이'다
TITLE_MAX_Y = 90      # 이 위쪽 텍스트를 페이지 제목으로 본다
CAPTION_GAP = 34      # 사진 아래 이만큼까지의 짧은 글을 캡션으로 본다

LATIN_RE = re.compile(r"\b([A-Z][a-z]{3,})\s+([a-z]{3,})\b")
# **「이」를 낱자로 넣지 않는다.** 넣으면 「식도를 이룸」·「보이는」·「같이」처럼
# 거의 모든 한글 글월이 종 이름을 부르는 것으로 잡힌다. 이(louse)는 자료에서
# 「머릿니」·「몸니」·「사면발이」로 불린다.
KO_NAME_RE = re.compile(
    r"(회충|편충|구충|요충|분선충|선모충|사상충|고래회충|간흡충|폐흡충|요코가와흡충"
    r"|간질|주걱흡충|큰입흡충|주혈흡충|조충|낭미충|고충|아메바|편모충|섬모충"
    r"|열원충|포자충|말라리아|진드기|모기|벼룩|머릿니|몸니|사면발이|빈대)")
SECTION_RE = [("충란", r"연충란|충란|Helminth\s*eggs"), ("선충", r"선충|Nematod"),
              ("흡충", r"흡충|Tremato"), ("조충", r"조충|Cestod"),
              ("원충", r"원충|Protozoa"), ("말라리아", r"말라리아|Plasmodium"),
              ("의용곤충", r"의용곤충|위생곤충|Arthropod")]


# ══════════ 페이지에서 글 읽기 ══════════

def page_lines(page):
    """이 페이지의 글줄. **글자를 지우기 전에** 불러야 한다."""
    out = []
    for blk in page.get_text("dict")["blocks"]:
        if blk.get("type") != 0:
            continue
        for line in blk["lines"]:
            text = "".join(sp["text"] for sp in line["spans"]).strip()
            if text:
                out.append({"text": text, "bbox": line["bbox"],
                            "size": max(sp["size"] for sp in line["spans"])})
    return out


def title_of(lines):
    """페이지 위쪽에서 가장 큰 글씨. 슬라이드(필기본)에서는 이것이 곧 주제다."""
    top = [ln for ln in lines if ln["bbox"][1] < TITLE_MAX_Y]
    if not top:
        return ""
    top.sort(key=lambda ln: (-ln["size"], ln["bbox"][1]))
    return top[0]["text"].strip()


def captions_for(bbox, lines, others=(), above=False):
    """이 사진을 가리키는 글. 포스터형에서는 **이것만이 사진의 이름표다.**

    한 쪽에 사진이 마흔 장 깔린 정리본에서는 페이지 제목이 아무것도 말해
    주지 않는다. 사진 안·바로 아래·바로 옆의 짧은 글을 거리순으로 모은다.

    **바로 위도 본다.** 항목 제목이 사진 위에 서는 쪽이 있다. 신은주 정리본
    「포자충류, 말라리아, 의용곤충」 p3이 그렇다 — 「[5] 작은소피참진드기
    Haemaphysalis longicornis」 바로 밑에 그 사진이 놓인다. 그 쪽은 글씨
    크기가 전부 같아서 `headings_of`가 표제를 하나도 못 잡고(제목만 크다),
    아래만 보던 이 함수는 **다음 항목의 제목**을 집었다. 그래서 접시에 담긴
    진드기가 「[6] 흰줄숲모기 Aedes albopictus」로 나갔다. 정작 이 사진에
    달린 설명은 「-> 다리 8개 !!! 거미st」였다.

    **줄은 제일 가까운 사진의 것이다.** `others`에 같은 쪽의 다른 사진 자리를
    넘기면, 위아래 양쪽으로 그 규칙을 지킨다 — 내 아래에 있는 줄이라도 그
    밑의 사진에 더 붙어 있으면 그 사진의 제목이고, 내 위의 줄이라도 그 위의
    사진에 더 붙어 있으면 그 사진의 설명이다.

    `above`는 **표제를 하나도 못 찾은 쪽에서만** 켠다(호출부가 정한다). 표제가
    잡히는 쪽에서는 위쪽 글이 이미 `heading_for`로 제대로 붙으므로, 거기까지
    캡션으로 끌어오면 슬라이드(필기본)에서 윗 문단이 사진 이름표가 된다 —
    267쪽을 견줘 보니 그쪽에서만 라벨이 나빠졌다.
    """
    x0, y0, x1, y1 = bbox
    near = []
    for ln in lines:
        lx0, ly0, lx1, ly1 = ln["bbox"]
        if len(ln["text"]) > 90:
            continue
        wide = not (lx1 < x0 or lx0 > x1)          # 가로로 겹친다 = 같은 단
        tall = not (ly1 < y0 or ly0 > y1)
        if lx0 >= x0 - 4 and lx1 <= x1 + 4 and ly0 >= y0 - 4 and ly1 <= y1 + 4:
            gap = 0.0                              # 사진 안
        elif wide and y1 <= ly0 <= y1 + CAPTION_GAP:
            gap = ly0 - y1                         # 바로 아래 — 설명
            if _stolen(ln["bbox"], gap, others, bbox, below=True):
                continue
        elif above and wide and y0 - CAPTION_GAP <= ly1 <= y0:
            gap = y0 - ly1                         # 바로 위 — 항목 제목
            if _stolen(ln["bbox"], gap, others, bbox, below=False):
                continue
        elif tall and x1 <= lx0 <= x1 + CAPTION_GAP:
            gap = lx0 - x1                         # 바로 옆
        else:
            continue
        near.append((gap, ln["text"].strip()))
    near.sort(key=lambda t: t[0])
    return [t for _, t in near]


def _stolen(line_box, gap, others, mine, below):
    """이 줄이 **다른 사진에 더 가까운가.** 가로로 겹치는 사진만 견준다.

    `below=True`면 줄이 내 아래에 있는 경우다 — 줄 **밑**의 사진들과 견준다.
    `below=False`면 줄이 내 위에 있는 경우 — 줄 **위**의 사진들과 견준다.
    """
    lx0, ly0, lx1, ly1 = line_box
    for o in others:
        if o is mine or o[2] < lx0 or o[0] > lx1:
            continue
        d = (o[1] - ly1) if below else (ly0 - o[3])
        if 0 <= d < gap:
            return True
    return False


HEADING_RE = re.compile(r"^\s*\d+\s*[.)]")
# 번호를 매긴 **항목 제목**. 「4. Ascaris…」·「[6] 흰줄숲모기…」.
# 번호가 있다는 것은 한 쪽에 항목이 여럿이라는 뜻이고, 그때에만 「내 아래에
# 선 제목은 남의 것」이 성립한다. 필기본 슬라이드는 종 이름만 크게 적어
# 두어서(「Schistosoma mansoni」) 번호가 없고, 그 이름은 사진 아래에 있어도
# 그 사진의 것이다.
ITEM_RE = re.compile(r"^\s*[\[(]?\s*\d+\s*[\]).]")
BAND = 30          # 표제가 이만큼 안에 있으면 같은 띠(가로줄)로 본다

# ── 표로 된 쪽
#
# 신은주 정리본은 포스터가 아니라 **표**다. `이름 | 학명 | 특징(사진들)` 이고
# 칸마다 선이 그어져 있다. 그러면 한 행의 사진은 전부 그 행의 종이라 헷갈릴
# 자리가 없다 — 표제와 가까운 캡션을 견주는 짐작이 아예 필요 없다.
#
# 처음에는 이 구조를 못 보고 포스터로 다뤘다. 표를 표로 읽으면 이 문서의
# 라벨은 짐작이 아니라 사실이 된다.
TABLE_MIN_LINES = 10    # 가로·세로 선이 각각 이만큼 넘으면 표로 본다


def is_table(page):
    """이 쪽이 표인가. 그어진 선을 센다."""
    h = v = 0
    for d in page.get_drawings():
        for item in d["items"]:
            if item[0] == "l":
                (x0, y0), (x1, y1) = item[1], item[2]
                if abs(y1 - y0) < 1 and abs(x1 - x0) > 40:
                    h += 1
                elif abs(x1 - x0) < 1 and abs(y1 - y0) > 40:
                    v += 1
            elif item[0] == "re":
                r = item[1]
                if r.height < 2 and r.width > 40:
                    h += 1
                elif r.width < 2 and r.height > 40:
                    v += 1
            if h > TABLE_MIN_LINES and v > TABLE_MIN_LINES:
                return True
    return h > TABLE_MIN_LINES and v > TABLE_MIN_LINES


def _species_names():
    """아는 종 이름 전부(학명·한국어·별칭). 짧은 것은 뺀다.

    **모양으로 판단하지 않는다.** 처음에는 「대문자로 시작하는 낱말 + 소문자
    낱말」을 학명으로 봤는데, 그러면 「Oral sucker」와 「Ventral pit」이 학명이
    된다. 실제로 그 둘이 이름표로 뽑혀서 사진이 엉뚱한 종에 붙었다.
    아는 이름과 견주는 것이 유일하게 안 틀리는 방법이다.
    """
    path = os.path.join(DATA, "species.json")
    out = set()
    try:
        for s in load_json(path):
            for k in [s.get("scientific_name"), s.get("name_ko")] + (s.get("aliases") or []):
                k = (k or "").strip().lower()
                if len(k) >= 2:
                    out.add(k)
    except (OSError, ValueError):
        pass
    return out


SPECIES_NAMES = _species_names()


def names_species(text):
    """이 글이 아는 종을 부르고 있는가. 이름표와 설명을 가르는 잣대다."""
    t = (text or "").lower()
    return any(name in t for name in SPECIES_NAMES)


def row_label(bbox, lines):
    """이 사진이 앉은 **행의 이름표.**

    정리본은 줄이 그어져 있든 아니든 결국 표다 — 왼쪽에 이름, 오른쪽에 그
    종의 사진들. 그래서 **사진 왼쪽에서, 세로로 같은 자리에 있는 글**을 찾는다.

    두 가지를 지킨다.

      ① **"위에 있는" 것이 아니라 "겹치는" 것.** 이름표는 행 가운데에 서므로
         사진보다 조금 아래에서 시작할 수 있다. 위아래로만 따지면 1.2pt
         차이로 윗 행 이름이 붙는다 — 이지석 실습3 p.2의 참굴큰입흡충
         사진이 요코가와흡충이 되고 있었다.

      ② **종을 부르는 글을 고른다.** 왼쪽 칸에는 이름 밑에 설명이 딸려
         오는데(「- 큰 oral sucker 존재」) 그쪽이 더 오른쪽에 있어서, 자리만
         보면 설명이 이름표가 된다.

    그중에서는 가장 오른쪽 것이다. 표는 왼쪽이 뭉뚱그린 이름이고(「구충」)
    오른쪽이 구체적이다(「두비니구충」, 그 옆이 학명).
    """
    x0, y0, y1 = bbox[0], bbox[1], bbox[3]
    beside = [ln for ln in lines
              if ln["bbox"][2] <= x0 + 2                     # 사진 왼쪽에 있고
              and ln["bbox"][3] > y0 and ln["bbox"][1] < y1]  # 세로로 겹친다
    # **종을 못 찾으면 아무 말도 안 한다.** 자리만 맞고 이름이 아닌 글
    # (「<3개의 lip>」)을 돌려주면, 표제로 제대로 붙을 수 있었던 사진까지
    # 그 설명이 이름표가 되어 버린다. 확신이 없을 때는 비켜서는 편이 낫다.
    named = [ln for ln in beside if names_species(ln["text"])]
    if not named:
        return ""
    return max(named, key=lambda ln: ln["bbox"][0])["text"].strip()


def headings_of(lines):
    """이 쪽에서 종을 알리는 표제들.

    정리본은 포스터다 — 한 쪽이 가로줄 몇 개로 나뉘고, 각 줄이 다시 좌·우
    칸으로 갈린다. 칸마다 맨 위에 「3. Ancylostoma duodenale (두비니구충)」
    같은 표제가 서고 그 아래 사진 여러 장이 딸린다.

    **표제는 본문보다 크다.** 그 한 가지로 가른다 — 번호나 학명 같은 생김새로
    고르면 「2) Dorsal costa -> 2분지가 짧음」 같은 본문 설명이 같이 걸린다.
    """
    if not lines:
        return []
    top = max(ln["size"] for ln in lines)
    return [ln for ln in lines if ln["size"] >= top - 0.5
            and (HEADING_RE.match(ln["text"]) or LATIN_RE.search(ln["text"])
                 or KO_NAME_RE.search(ln["text"]))]


def heading_for(bbox, heads):
    """이 사진을 거느리는 표제.

    **가장 가까운 글이 아니라 자기 칸의 표제다.** 가까운 것을 집으면
    「크기: 90 μm까지」처럼 사진 바로 밑에 붙은 설명이 이름표가 되어 버린다
    (실제로 이지석 123장 중 31%만 종에 붙었던 이유가 이것이었다).

    읽는 순서를 따라간다 — 위에 있는 표제 중 가장 아래 띠를 고르고, 그 띠
    안에서 내 왼쪽에 있는 것 중 제일 오른쪽을 고른다. 한 띠에 두 종이
    나란히 선 쪽에서 왼쪽 종에 오른쪽 사진이 붙는 것을 막는다.
    """
    x0, y0 = bbox[0], bbox[1]
    above = [h for h in heads if h["bbox"][1] <= y0]
    if not above:
        return ""
    band = max(h["bbox"][1] for h in above)
    row = [h for h in above if h["bbox"][1] >= band - BAND]
    left = [h for h in row if h["bbox"][0] <= x0]
    pick = max(left, key=lambda h: h["bbox"][0]) if left \
        else min(row, key=lambda h: h["bbox"][0])
    return pick["text"].strip()


def section_of(text):
    for name, pat in SECTION_RE:
        if re.search(pat, text, re.I):
            return name
    return None


def wipe_text(page):
    """이 페이지의 **글자만** 지운다. 사진과 화살표는 그대로 둔다.

    `extract_practical_pdf.wipe_text`와 같은 일이다. 두 스크립트가 다루는
    PDF가 달라 각자 들고 있지만 규칙은 하나다 — `fill=None`으로 흰 상자를
    안 그리고, 사진과 선화는 손대지 않는다.
    """
    words = page.get_text("words")
    if not words:
        return 0
    for w in words:
        page.add_redact_annot(pymupdf.Rect(w[:4]), fill=None)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                          graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                          text=pymupdf.PDF_REDACT_TEXT_REMOVE)
    return len(words)


# ══════════ 사진 고르기 ══════════

def render_dpi(info):
    """이 사진을 잘라낼 해상도. 원본이 가진 만큼만 뽑고, 그 위로는 안 올린다."""
    w_pt = info["bbox"][2] - info["bbox"][0]
    if w_pt <= 0:
        return DPI_MIN
    return int(min(max(info["width"] / (w_pt / 72.0), DPI_MIN), DPI_MAX))


def overlaps(a, b, ratio=0.75):
    """두 자리가 사실상 같은 자리인가. 겹친 넓이가 작은 쪽의 대부분이면 같다."""
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return small > 0 and inter / small >= ratio


# ── 사진에 구워진 글자 읽기
#
# **PDF 텍스트를 지우는 것만으로는 부족하다.** 필기본에는 슬라이드를 통째로
# 찍은 스크린샷이 섞여 있는데, 거기 적힌 글자는 픽셀이라 지울 수가 없다.
# 실제로 연습문제 네 장이 「Clonorchis sinensis | Metagonimus yokogawai …」
# 라는 보기를 그대로 달고 통과했다. 그건 정답표를 문항으로 내는 것이다.
#
# 픽셀 휴리스틱(순백 비율·채도)으로는 못 잡았다. 읽어 봐야 안다.
#
# 배율(`400x`)이나 미터자의 눈금 숫자는 남긴다 — 그건 답이 아니라 크기 정보고,
# 오히려 있어야 푸는 문항이 있다. 그래서 **숫자만인 것은 글자로 치지 않는다.**
OCR_MIN_SCORE = 0.5    # 이보다 흐린 인식은 믿지 않는다
OCR_MAX_SIDE = 1000    # 읽기 전에 줄인다. 원본 그대로 넣으면 장당 몇 초씩 든다
NUMERIC_RE = re.compile(r"^[\d.,\s]*[xX×]?$")

# **글자 수로 재지 않는다.** 처음에는 "숫자를 뺀 글자 12자까지는 봐준다"로
# 두었는데, 통과분 546장을 다시 읽어 보니 그 틈으로 `Operculum`(9자),
# `Mucoid plug`(10자), `dorsal costa`, `bandform`이 그대로 나갔다. 하나같이
# 그 문항의 정답이다 — 짧다고 덜 새는 것이 아니다.
#
# 그래서 길이가 아니라 **말이 되는가**로 가른다. 알파벳 네 자가 이어지거나
# 한글 두 자가 이어지면 이름이고, 그 아래는 잡음이다. 남기고 싶은 것들이
# 정확히 이 아래에 있다 — `50um`(스케일), `10kv291`(SEM 촬영정보),
# `CH2`(경통 각인), 그리고 표본의 결을 글자로 잘못 읽은 헛것들.
#
# 546장으로 맞춰 본 결과 진짜 유출 25장쯤을 잡고, 헛것 때문에 멀쩡한 사진
# 두 장을 잃는다. 그 둘은 `_rejects`에 남으니 되찾을 수 있다.
WORDY_RE = re.compile(r"[A-Za-z]{4,}|[가-힣]{2,}")

# **글자를 못 읽어도 문제지인 줄은 알아야 한다.** 필기본에는 답을 손으로 적어
# 둔 시험문제가 통째로 들어 있는데, RapidOCR이 그 한글을 한자 비슷한 것으로
# 잘못 읽어(`3)号 4)号全`) 위의 낱말 규칙을 그냥 지나갔다. 「22. 다음 충란의
# 기생충의 중간숙주는?」에 보기 넷과 손글씨 정답이 그대로 붙은 사진이었다.
#
# 그래서 **읽은 내용이 아니라 생긴 꼴**로도 본다. 표본 사진에는 글상자가
# 없거나 한둘이고(배율·스케일), 번호를 매긴 목록이 있을 리 없다.
# 정리본 둘(264장)에서는 이 규칙에 걸리는 것이 **한 장도 없다** — 필기본의
# 문제지만 골라낸다.
OCR_MAX_BOXES = 2                       # 글상자가 이보다 많으면 글이 적힌 것이다
NUMBERED_RE = re.compile(r"\d\s*[)）]")   # `1)` `2)` … 보기를 매긴 자국
NUMBERED_MIN = 2


# 읽어 둔 것. 그림 내용의 지문 → 낱말 목록. 그림이 그대로면 결과도 그대로다.
OCR_CACHE_PATH = os.path.join(DATA, "_ocr_cache.json")
OCR_CACHE = {}


def load_ocr_cache():
    if os.path.isfile(OCR_CACHE_PATH):
        # 깨졌으면 그냥 다시 읽는다. 캐시가 없는 것과 같은 자리가 된다.
        with contextlib.suppress(OSError, ValueError), \
                open(OCR_CACHE_PATH, encoding="utf-8") as fh:
            OCR_CACHE.update(json.load(fh))
    return len(OCR_CACHE)


def save_ocr_cache():
    with open(OCR_CACHE_PATH, "w", encoding="utf-8") as fh:
        json.dump(OCR_CACHE, fh, ensure_ascii=False)


def make_reader():
    """OCR 한 벌. 못 들이면 `None`을 돌려주고 그 사실을 말한다."""
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        print("  ! rapidocr-onnxruntime 이 없어 구워진 글자는 못 거릅니다."
              " (--with rapidocr-onnxruntime 을 붙여 주세요)")
        return None
    return RapidOCR()


def baked_text(reader, im):
    """이 그림에 적혀 있는 글. 숫자·배율은 뺀다.

    **읽다 실패하면 시끄럽게 군다.** 조용히 빈 목록을 돌려주면 OCR이 꺼진
    채로 전부 통과해 버리는데, 그게 바로 막으려던 사고다.
    """
    if reader is None:
        return []
    small = im.copy().convert("RGB")
    small.thumbnail((OCR_MAX_SIDE, OCR_MAX_SIDE))
    # 읽은 것은 남겨 둔다. 한 바퀴가 22분이라 기준을 한 번 고칠 때마다 그만큼
    # 기다리게 되는데, 고치는 것은 판정이지 읽기가 아니다.
    key = hashlib.sha1(small.tobytes()).hexdigest()
    if key in OCR_CACHE:
        return OCR_CACHE[key]
    try:
        import numpy as np
        result, _ = reader(np.asarray(small))
    except Exception as e:
        raise SystemExit(f"OCR이 실패했습니다: {e}\n"
                         "  --no-ocr 로 끄고 돌릴 수는 있지만, 그러면 사진에 구워진"
                         " 글자를 못 거릅니다.") from e
    out = []
    for item in result or []:
        text, score = str(item[1]).strip(), float(item[2])
        if score < OCR_MIN_SCORE or len(text) < 3 or NUMERIC_RE.match(text):
            continue
        out.append(text)
    OCR_CACHE[key] = out
    return out


def paper_look(im):
    """(순백 비율, 평균 채도). 글자판·도표를 가려내는 데 쓴다."""
    g = im.convert("RGB").copy()
    g.thumbnail((160, 160))
    raw = g.tobytes()                      # r,g,b,r,g,b… (`getdata`는 곧 없어진다)
    n = len(raw) // 3 or 1
    white = sat = 0
    for i in range(0, len(raw), 3):
        r, gg, b = raw[i], raw[i + 1], raw[i + 2]
        if r > 238 and gg > 238 and b > 238:
            white += 1
        sat += max(r, gg, b) - min(r, gg, b)
    return white / n, sat / n


def ahash(im):
    """같은 사진이 여러 쪽에 되풀이되는 것을 잡는다."""
    g = im.convert("L").resize((8, 8), Image.BILINEAR)
    px = g.tobytes()
    avg = sum(px) / len(px)
    bits = "".join("1" if p > avg else "0" for p in px)
    return hashlib.sha1(bits.encode()).hexdigest()[:16]


def judge(im, info, reader):
    """이 그림을 쓸 것인가. 쓰지 않으면 그 이유를 돌려준다.

    싼 것부터 본다 — 크기·모양·색은 픽셀 몇 개만 세면 되고, OCR은 장당
    수백 밀리초가 든다. 앞에서 걸러지면 읽을 필요가 없다.
    """
    w, h = im.size
    if min(info["width"], info["height"]) < MIN_PX:
        return f"작음({info['width']}x{info['height']})"
    box = info["bbox"]
    if (box[2] - box[0]) < MIN_PT or (box[3] - box[1]) < MIN_PT:
        return "쪽에서 작음"
    if max(w, h) / max(1, min(w, h)) > MAX_ASPECT:
        return f"길쭉({w}x{h})"
    white, sat = paper_look(im)
    if white >= PAPER_WHITE and sat < PAPER_SAT:
        return f"글자판(순백 {white:.0%}·채도 {sat:.0f})"
    seen = baked_text(reader, im)
    words = [t for t in seen if WORDY_RE.search(t)]
    if words:
        return f"글자 박힘({' '.join(words)[:40]})"
    blob = " ".join(seen)
    if len(seen) > OCR_MAX_BOXES:
        return f"글이 많음({len(seen)}칸: {blob[:32]})"
    if len(NUMBERED_RE.findall(blob)) >= NUMBERED_MIN:
        return f"보기 매김({blob[:36]})"
    return None


# ══════════ 한 묶음 뽑기 ══════════

def run(key, reader, dry=False):
    spec = SOURCES[key]
    folder = spec["dir"]
    if not os.path.isdir(folder):
        raise SystemExit(f"폴더가 없습니다: {folder}")
    pdfs = [os.path.join(folder, n) for n in sorted(os.listdir(folder))
            if n.lower().endswith(".pdf")]

    out_dir = os.path.join(IMAGES, key)
    rej_dir = os.path.join(IMAGES, "_rejects", key)
    if not dry:
        for d in (out_dir, rej_dir):
            if os.path.isdir(d):
                shutil.rmtree(d)
            os.makedirs(d, exist_ok=True)

    records, rejects, seen_hash, dropped, wiped = [], [], {}, {}, 0
    tabled = 0
    print(f"\n══ {spec['ko']} ({key}) · PDF {len(pdfs)}개")

    for pdf in pdfs:
        stem = os.path.splitext(os.path.basename(pdf))[0]
        # 파일 이름이 곧 단원인 경우가 많다 (「기생충 실습 (선충류)」).
        doc = pymupdf.open(pdf)
        # **파일 이름이 말해 주지 않으면 첫 쪽 제목을 본다.** 이지석은 파일이
        # 「실습 1」·「실습 2」라 이름만으로는 단원을 알 수 없고, 첫 쪽 제목이
        # 「실습 1 - 연충란」·「실습 2 - 선충류」로 적혀 있다.
        #
        # 이것이 없으면 아래 「앞 12줄에서 찾기」로 떨어지는데, 그 12줄에는
        # **다른 행의 종 이름**이 섞여 있다. 실습1 p2는 다섯 행이 전부 충란인
        # 표인데 마지막 행이 「폐흡충」이라 단원이 「흡충」으로 잡혔고, 그래서
        # 구충란 넉 장이 「충란 시트가 아니다」라는 이유로 충란 표본 후보에서
        # 밀려 성충으로 붙었다.
        file_topic = section_of(stem) or (
            section_of(title_of(page_lines(doc[0]))) if doc.page_count else None)
        for pno in range(doc.page_count):
            page = doc[pno]
            lines = page_lines(page)
            title = title_of(lines)
            topic = section_of(title) or file_topic or section_of(" ".join(
                ln["text"] for ln in lines[:12]))

            infos = [i for i in page.get_image_info(xrefs=False)
                     if i["width"] >= 60 and i["height"] >= 60]
            infos.sort(key=lambda i: -(i["width"] * i["height"]))
            # 같은 자리에 겹쳐 놓인 것은 큰 쪽만 남긴다. 정리본은 사진 위에
            # 반투명 판을 덧대 놓는 일이 있어 한 자리가 두 번 잡힌다.
            picked = []
            for i in infos:
                if not any(overlaps(i["bbox"], j["bbox"]) for j in picked):
                    picked.append(i)
            picked.sort(key=lambda i: (round(i["bbox"][1] / 30), i["bbox"][0]))

            heads = headings_of(lines)
            boxes = [i["bbox"] for i in picked]
            # **표제가 하나도 안 잡힌 쪽에서만 사진 위쪽 글을 본다.** 그런 쪽은
            # 글씨 크기가 전부 같아 항목 제목이 표제로 안 걸린다(신은주 정리본의
            # 서술형 쪽이 그렇다). 표제가 잡히는 쪽은 `heading_for`에 맡긴다.
            caps = {id(i): captions_for(i["bbox"], lines, boxes, above=not heads)
                    for i in picked}
            # **행으로 먼저 읽는다.** 줄이 그어졌든 아니든 정리본은 표다 —
            # 왼쪽에 이름, 오른쪽에 그 종의 사진들. 행에서 못 찾을 때만
            # 표제식(위에 선 제목)으로 내려간다. 슬라이드(필기본)가 그쪽이다.
            owns = {}
            for i in picked:
                lab = row_label(i["bbox"], lines)
                if lab:
                    tabled += 1
                else:
                    lab = heading_for(i["bbox"], heads)
                owns[id(i)] = lab

            # 글은 다 읽었다. 이제 지운다 — 아래에서 그리면 사진에 구워진다.
            wiped += wipe_text(page)

            for k, info in enumerate(picked, 1):
                name = f"{stem[:22]}_{pno + 1:03d}_{k}.png".replace(" ", "_")
                # **자리를 페이지 안으로 물린다.** 슬라이드에는 가장자리를 넘어
                # 걸친 그림이 있고, 페이지 밖을 자르면 빈 픽스맵이 나와 저장에서
                # 터진다(필기본에서 실제로 그랬다).
                rect = pymupdf.Rect(info["bbox"]) & page.rect
                if rect.is_empty or rect.width < 1 or rect.height < 1:
                    dropped["빈 자리"] = dropped.get("빈 자리", 0) + 1
                    continue
                pix = page.get_pixmap(clip=rect, dpi=render_dpi(info))
                if pix.width < 2 or pix.height < 2:
                    dropped["빈 그림"] = dropped.get("빈 그림", 0) + 1
                    continue
                im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                im.thumbnail((MAX_SIDE, MAX_SIDE))
                if min(im.size) < 2:          # 너무 길쭉해서 한 변이 0이 됐다
                    dropped["빈 그림"] = dropped.get("빈 그림", 0) + 1
                    continue

                why = judge(im, info, reader)
                if not why:
                    h = ahash(im)
                    if h in seen_hash:
                        why = f"중복({seen_hash[h]})"
                    else:
                        seen_hash[h] = name

                if why:
                    kind = why.split("(")[0]
                    dropped[kind] = dropped.get(kind, 0) + 1
                    if not dry:
                        # **이유는 파일 이름에 안 넣는다.** OCR이 읽어 온 글자가
                        # 그대로 들어가는데 거기에는 따옴표도 있고 길이도 제멋대로라
                        # Windows가 파일을 못 만든다. 이름은 종류만, 나머지는 옆의
                        # 목록에 적는다.
                        safe = f"[{kind}]_{name}"
                        im.save(os.path.join(rej_dir, safe))
                        rejects.append({"file": safe, "why": why,
                                        "page": pno + 1, "px": list(im.size)})
                    continue

                rel = f"{key}/{name}"
                if not dry:
                    im.save(os.path.join(out_dir, name))
                caption = caps.get(id(info)) or []
                head = owns.get(id(info)) or ""
                # 캡션 중에 **아는 종**을 부르는 것이 있는가.
                #
                # `row_label`과 같은 잣대를 쓴다 — 생김새가 아니라 종 테이블과
                # 견준다. 예전에는 `KO_NAME_RE`로 봤는데 그 안에 낱자 「이」가
                # 있어서 「식도를 이룸」 같은 설명이 전부 이름표가 됐고, 캡션이
                # 행 이름표(`head`)를 밀어냈다. 표로 된 쪽에서 행 이름은 짐작이
                # 아니라 사실인데 그것이 설명에 밀렸다.
                # **내 아래에 선 표제는 다음 항목의 것이다.**
                #
                # 항목 제목이 사진 위에 서는 쪽에서는, 사진 아래 34pt 안에 든
                # 표제가 곧 아래 칸의 제목이다. 그것을 캡션으로 집으면 아래 칸의
                # 종이 이 사진의 이름표가 된다 — 이지석 실습2 p2-7은 회충 수컷
                # 단면인데 밑에 선 「5. Anisakis simplex (고래회충)」을 집어
                # 고래회충이 됐고, p3-1·p3-2는 선모충 근육절편인데 밑에 선
                # 「7. Enterobius vermicularis (요충)」을 집어 요충이 됐다.
                #
                # **아래 것만 뺀다.** 옆이나 위의 표제는 내 것일 수 있다 —
                # 이지석 표는 사진이 왼쪽이고 이름이 오른쪽이라 행 이름이 「옆의
                # 표제」로 잡힌다. 방향을 안 보고 걷어내면 그 행 이름까지 잃고,
                # 실제로 광절열두조충 충란이 구충란이 됐다.
                downstairs = {h["text"].strip() for h in heads
                              if h["bbox"][1] >= info["bbox"][3]
                              and ITEM_RE.match(h["text"])} - {head}
                caption = [c for c in caption if c not in downstairs]
                named = next((c for c in caption
                              if LATIN_RE.search(c) or names_species(c)), "")
                # 학명도 **가까운 것부터** 찾는다. 쪽 제목을 먼저 훑으면 그 쪽의
                # 다른 종이 이 사진의 학명이 된다 — `name_en`은 매칭이 가장 먼저
                # 보는 칸이라(`match_species`의 `near[0]`) 사진 자신의 이름표를
                # 그대로 이긴다.
                latin = ""
                m = LATIN_RE.search(" / ".join([named, head] + caption + [title]))
                if m:
                    latin = f"{m.group(1)} {m.group(2)}"
                records.append({
                    "source": key,
                    "sheet": spec["ko"],
                    "page": pno + 1,
                    "cell": f"{stem[:18]} p{pno + 1}-{k}",
                    "section": "실습",
                    "topic": topic,
                    # **캡션이 종을 부르면 캡션이 이름표고, 아니면 표제다.**
                    #
                    # 어느 쪽이 맞는지는 문서마다 다르다. 신은주는 사진 옆에
                    # 종 이름을 적어 두고(그래서 캡션이 옳다), 이지석은 설명만
                    # 적고 종은 칸 머리의 표제로 준다(그래서 표제가 옳다).
                    # 무조건 표제를 쓰게 했더니 신은주가 80%에서 66%로 떨어졌다.
                    #
                    # 못 쓴 쪽도 `name_sub`에 남긴다 — `map_images.py`가 두 칸을
                    # 다 훑으므로 한쪽이 틀려도 다른 쪽으로 붙을 수 있다.
                    "name_ko": (named or head or title
                                or (caption[0] if caption else ""))[:120],
                    "name_sub": (head if named else title)[:120],
                    "name_en": latin,
                    "stage": " / ".join(caption[:3])[:120],
                    "size": "",
                    "features": " / ".join(caption)[:200],
                    "path": rel,
                    "px_w": im.size[0],
                    "px_h": im.size[1],
                })
        doc.close()

    if not dry:
        with open(os.path.join(DATA, f"{key}_manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(records, fh, ensure_ascii=False, indent=2)
        # 버린 것의 이유. 파일 이름에는 종류만 들어가므로 여기가 원장이다.
        with open(os.path.join(rej_dir, "_why.json"), "w", encoding="utf-8") as fh:
            json.dump(rejects, fh, ensure_ascii=False, indent=2)

    sides = sorted(min(r["px_w"], r["px_h"]) for r in records) or [0]
    named = sum(1 for r in records if r["name_en"] or r["name_ko"])
    print(f"  뽑음 {len(records)}장 · 글자 {wiped}낱말 지움"
          + (f" · 행으로 읽은 것 {tabled}장" if tabled else ""))
    print(f"  짧은변 중앙 {sides[len(sides) // 2]}px · 600px 이상 "
          f"{sum(1 for s in sides if s >= 600)}장 · 이름표가 붙은 것 {named}장")
    if dropped:
        print("  버림: " + " · ".join(f"{k} {n}" for k, n in
                                     sorted(dropped.items(), key=lambda x: -x[1])))
    if not dry:
        print(f"  버린 것은 {os.path.relpath(rej_dir, ROOT)} 에 이유를 붙여 두었습니다.")
    return records


def main():
    reader = None if "--no-ocr" in sys.argv else make_reader()
    if reader is not None:
        n = load_ocr_cache()
        if n:
            print(f"읽어 둔 OCR {n}장분을 씁니다 ({os.path.basename(OCR_CACHE_PATH)})")
    dry = "--dry" in sys.argv
    want = [sys.argv[sys.argv.index("--source") + 1]] if "--source" in sys.argv \
        else list(SOURCES)
    for key in want:
        if key not in SOURCES:
            raise SystemExit(f"모르는 출처: {key} (있는 것: {', '.join(SOURCES)})")
        run(key, reader, dry)
    if reader is not None:
        save_ocr_cache()


if __name__ == "__main__":
    main()
