"""뒷면의 차례와 세로 간격.

## 간격 — 뒤 요소의 위쪽 margin 하나가 정한다

원래 문장: **뒤 요소의 위쪽 margin 하나가** 정한다.

2026-09-03 에 `.a`·`.warn`·`.exam` 이 `display: inline-block` 에서 `display: block` 으로
바뀌었다(짧은 답 옆에 해설이 나란히 서던 것을 고치려고). 그 바꿈이 **붙어 있는 형제끼리의
margin 상쇄**를 켰다 — inline-block 은 이웃과 margin 이 합쳐지지 않는데 block 은 둘 중
큰 것 하나만 남는다. 그래서 `.a` 아래 12px + `.warn` 위 12px = 24px 이던 자리가 12px 이
됐고, 관리자가 *"답과 Warning 사이에 들여쓰기가 없다. 다른 것들도 가끔 그렇구"* 라고
짚었다. 답 → 해설(22→12), 답 → 기출 원문(24→12), 구분선 → 답(26→14)도 같이 좁아졌다.

**더해서 맞추던 값이라 한쪽만 바뀌어도 조용히 반토막이 난다.** 그래서 앞 요소의 아래쪽을
0 으로 두고 뒤 요소의 위쪽 하나가 간격을 지게 했다. 상쇄가 큰 쪽을 남기므로 그 값이
그대로 눈에 보이는 간격이 된다. 이 파일은 그 규칙이 유지되는지만 본다 — 값이 예쁜지는
눈으로 볼 일이고, 여기서 잡으려는 것은 **간격이 소리 없이 절반이 되는 것**이다.
"""

import pathlib
import re

import pytest

import quizgen.build as B
import quizgen.prequiz.build as P
from quizgen.build import CLOZE_MODEL, CSS, MODELS, TAIL
from quizgen.prequiz.build import PRE_CSS

# 답 아래로 쌓이는 것들. 이 중 하나가 답이나 경고 바로 뒤에 설 수 있다.
STACKED = [".warn", ".exp", ".exam", ".fold", ".origin", ".ox", ".a"]
# 상쇄를 이기려면 뒤 요소의 위쪽이 이만큼은 돼야 한다. 상쇄 전 제일 작던 값이 22px 이다.
MIN_TOP = 20
# 간격을 혼자 지지 않는 쪽 — 아래쪽은 0 이어야 한다.
ZERO_BOTTOM = [".a", ".warn"]


def rules(css: str) -> dict[str, str]:
    out = {}
    for sel, body in re.findall(r"(^[.#][\w.\-> ]*?)\s*\{([^}]*)\}", css, re.M):
        out.setdefault(sel.strip(), "")
        out[sel.strip()] += body
    return out


def margins(body: str) -> dict[str, int]:
    """`margin` 단축과 `margin-top`/`-bottom` 을 함께 읽어 위·아래 px 을 낸다."""
    top = bottom = None
    for prop, val in re.findall(r"(margin(?:-top|-bottom)?)\s*:\s*([^;]+);", body):
        parts = val.split()
        px = lambda s: int(s[:-2]) if s.endswith("px") else (0 if s == "0" else None)
        if prop == "margin-top":
            top = px(parts[0])
        elif prop == "margin-bottom":
            bottom = px(parts[0])
        elif len(parts) == 1:
            top = bottom = px(parts[0])
        elif len(parts) == 2:
            top = bottom = px(parts[0])
        elif len(parts) == 3:
            top, bottom = px(parts[0]), px(parts[2])
        else:
            top, bottom = px(parts[0]), px(parts[2])
    return {"top": top, "bottom": bottom}


@pytest.mark.parametrize("sel", STACKED)
def test_뒤에_오는_것이_제_간격을_지고_있다(sel):
    m = margins(rules(CSS)[sel])
    assert m["top"] is not None and m["top"] >= MIN_TOP, f"{sel} margin-top={m['top']}"


@pytest.mark.parametrize("sel", ZERO_BOTTOM)
def test_앞_요소는_아래쪽_간격을_들지_않는다(sel):
    """0 이 아니면 상쇄 때문에 「더해질 것」이라는 착각이 다시 생긴다."""
    assert margins(rules(CSS)[sel])["bottom"] == 0


def test_예습의_다리도_같은_규칙을_탄다():
    """`.bridge` 도 같은 날 block 으로 바뀌어 답과의 사이가 26→14 로 좁아졌다."""
    assert margins(rules(PRE_CSS)[".bridge"])["top"] >= MIN_TOP


def test_예습은_공용_CSS_를_그대로_물려받는다():
    """따로 베껴 두면 이 고침이 한쪽에만 남는다."""
    assert PRE_CSS.startswith(CSS)


def test_상쇄를_켠_display_는_그대로_둔다():
    """`inline-block` 으로 되돌리면 짧은 답 옆에 해설이 나란히 서던 버그가 돌아온다.

    간격 문제의 답은 display 를 되돌리는 것이 아니라 margin 을 다시 적는 것이었다.
    """
    for sel in (".a", ".warn", ".exam"):
        assert "display: block" in rules(CSS)[sel]


# ------------------------------------------------ 차례

def test_해설이_경고보다_먼저_선다():
    """답 다음으로 읽을 것은 곁말이 아니라 해설이다(2026-09-03 관리자 지시)."""
    assert TAIL.index("{{#Explanation}}") < TAIL.index("{{Warning}}")


@pytest.mark.parametrize("fmt", sorted(MODELS))
def test_네_형식_모두_같은_차례다(fmt):
    afmt = MODELS[fmt].templates[0]["afmt"]
    assert afmt.index("{{#Explanation}}") < afmt.index("{{Warning}}")


def test_빈칸_카드도_같은_차례다():
    """cloze 는 해설이 `Extra` 에 들어 템플릿이 따로다 — 갈라지기 쉬운 자리."""
    afmt = CLOZE_MODEL.templates[0]["afmt"]
    assert afmt.index("{{#Extra}}") < afmt.index("{{Warning}}")


def test_예습도_해설이_먼저다():
    """예습은 처음부터 이 차례였다. 복습을 여기에 맞춘 것이라 둘이 어긋나면 안 된다."""
    assert P.PRE_TAIL.index("{{#Explanation}}") < P.PRE_TAIL.index("{{Warning}}")


# ------------------------------------------------ 세 층

@pytest.mark.parametrize("mod", [B, P], ids=["복습", "예습"])
def test_층은_겹치지_않고_라벨을_다_덮는다(mod):
    """한 플래그가 두 층에 있으면 카드에 두 번 뜬다. 어느 층에도 없으면 조용히 안 뜬다."""
    t, m, c = set(mod.WARN_TRUST), set(mod.WARN_MINOR), set(mod.WARN_CHORE)
    assert not (t & m) and not (m & c) and not (t & c)
    assert t | m | c == set(mod.FLAG_LABEL)


@pytest.mark.parametrize("mod", [B, P], ids=["복습", "예습"])
def test_검증기가_내는_플래그에_빠진_층이_없다(mod):
    """`validate` 가 낼 수 있는데 표에 없으면 그 플래그는 영영 안 보인다.

    여기서 빠뜨린 것만 적어 둔다 — `off_plan` 은 지금 어느 편에서도 0건이고
    라벨이 붙은 적이 없다(2026-09-03 실측). 붙일 때 이 목록에서 빼라.
    """
    src = (mod.__file__.replace("build.py", "validate.py"))
    emitted = set(re.findall(r'append\("([a-z_]+)"\)', pathlib.Path(src).read_text("utf-8")))
    known_silent = {"off_plan", "photo_focus_without_lecture_figures",
                    "photo_focus_below_half", "reason_mismatch"}
    assert emitted - set(mod.FLAG_LABEL) <= known_silent


def test_카드_겉면에_남는_경고는_믿음_층뿐이다():
    """②·③ 은 접힌 출처 안이 자리다. `Warning` 으로 새면 답 밑으로 돌아온다."""
    c = {"review_flags": sorted(B.WARN_MINOR) + sorted(B.WARN_CHORE)}
    assert B.warning_of(c) == ""
    assert B.fold_notes_of(c)


@pytest.mark.parametrize("sel", [".minor", ".chore"])
def test_두_층_모두_접힌_출처_안에_있다(sel):
    c = {"source_type": "lecture",
         "review_flags": ["points_at_source", "similar_duplicate"]}
    _, tail = B.tail_of(c, "제목", "", "", B.fold_notes_of(c))
    assert tail.index("<details") < tail.index(f'class="{sel[1:]}"') < tail.index("</details>")


def test_출처_줄_아래_반쪽이_먼저_잔소리가_나중이다():
    c = {"review_flags": ["points_at_source", "similar_duplicate"]}
    out = B.fold_notes_of(c)
    assert out.index('class="minor"') < out.index('class="chore"')


def test_예습도_같은_자리다():
    c = {"review_flags": ["points_at_source", "similar_duplicate"]}
    assert P.warning_of(c) == "" and P.fold_notes_of(c)


# ------------------------------------------------ 생김새

def test_믿음_층은_노란_상자다():
    """①은 답을 의심하라는 말이다. 잔글씨로 내리면 잔소리 속에 묻힌다."""
    warn = rules(CSS)[".warn"]
    assert "background" in warn
    assert int(re.search(r"font-size:\s*(\d+)px", warn).group(1)) >= 16


def test_접힌_안의_두_층은_색과_크기로_갈린다():
    """같은 자리에 있어도 층이 남아야 한다 — ② 가 ③ 보다 진하고 크다."""
    n = lambda s: int(re.search(r"font-size:\s*(\d+)px", rules(CSS)[s]).group(1))
    grey = lambda s: int(re.search(r"color:\s*#(\w\w)", rules(CSS)[s]).group(1), 16)
    assert n(".src") >= n(".minor") > n(".chore")
    assert grey(".minor") < grey(".chore")      # 값이 작을수록 진하다
    for sel in (".minor", ".chore"):
        assert "background" not in rules(CSS)[sel]
