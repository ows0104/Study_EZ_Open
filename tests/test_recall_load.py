"""답의 무게는 뒷면 길이가 아니라 「외워야 하는 글자」로 잰다.

관리자 지시(2026-09-05) — *"clozed가 해답이 될 수 있는 부분은 회상해야할 것이 전체
문장이 아니라 그 강조 단어가 되기 때문이야."* 길이로만 재면 그 구분이 사라진다.

두 깃발이 잡는 고장이 다르다. `260824` 이후 2083장에서 겹친 것이 9장(3%)뿐이었다.

    recall_load_high     외울 것이 많다          → 축을 갈라 나눈다
    answer_frame_heavy   외울 건 적은데 읽을 게 많다  → 해설로 보내거나 cloze 를 본다
"""

from pdf2anki.schema import (FRAME_HEAVY_MIN_CHARS, MAX_RECALL_CHARS,
                             MIN_RECALL_SHARE)
from pdf2anki.validate import recall_load, validate

# 화면으로 받은 실제 카드. 강의 `260901_01` 의 c012 — 뒷면 167자 가운데 회수 대상은
# 62자(37%)뿐이고 나머지 105자는 읽기만 하면 되는 프레임이다.
C012 = ("- 각피(cuticle): **키틴질**이며 대사적으로 **불활성**\n"
        "- 4개의 **종선(longitudinal cord)**: dorsal & ventral cords는 **nerve**, "
        "lateral cords는 **excretion**\n"
        "- 근육층: **근육세포 수**에 따라 선충을 분류할 수 있어 "
        "**병리 조직표본에서 충체 동정**에 쓰인다")


def _prep(n_slides=10):
    return {"slides": n_slides,
            "pages": [{"slide": i, "lecture_figures": [], "occlusion_candidates": []}
                      for i in range(1, n_slides + 1)]}


def _card(a, fmt="basic", q="선충 체벽의 각피는 어떤 성분·상태인가?"):
    return {"q": q, "a": a, "explanation": "", "card_format": fmt,
            "card_type": "fact", "importance": "core", "source_type": "lecture",
            "evidence_type": "lecture_text", "exam_hit": False, "slide_no": 1}


def _flags(*cards):
    kept, _ = validate({"cards": list(cards)}, _prep(), None)
    return [set(c.get("review_flags") or []) for c in kept]


def test_강조가_있으면_강조만_센다():
    recall, printed = recall_load(C012, "basic")
    assert printed == 167
    assert recall == 62


def test_강조가_없으면_답이_통째로_회수_대상이다():
    # `quality.md` — "답이 한 덩어리라 통째로 회수 대상이면 그대로 두고 씌우지 않는다"
    assert recall_load("Alcohol drinking", "basic") == (16, 16)


def test_cloze_는_a_가_이미_빈칸만_모은_것이다():
    # 프레임은 앞면에 주어지므로 회수 부담에 안 든다 — 비율이 늘 1이라
    # `answer_frame_heavy` 에 구조적으로 걸릴 수 없다.
    recall, printed = recall_load("- **41.7 mg**\n- **24**", "cloze")
    assert recall == printed


def test_프레임이_눌러앉은_카드가_걸린다():
    assert "answer_frame_heavy" in _flags(_card(C012))[0]


def test_짧고_비율만_낮은_답은_안_걸린다():
    # 「**흡혈**하는 선충」 꼴. 비율은 낮아도 읽을 것이 없다 — 뒷면 길이를 함께 무는 이유다.
    short = "주된 기전은 **흡혈**이며 이때 장점막에 단단히 붙어 오래 머문다"
    recall, printed = recall_load(short, "basic")
    assert recall / printed < MIN_RECALL_SHARE
    assert printed < FRAME_HEAVY_MIN_CHARS
    assert "answer_frame_heavy" not in _flags(_card(short))[0]


def test_외울_것이_많으면_따로_걸린다():
    heavy = "- " + "\n- ".join(f"**{'가나다라마바사아자차' * 2}{i}**" for i in range(4))
    recall, _ = recall_load(heavy, "basic")
    assert recall > MAX_RECALL_CHARS
    flags = _flags(_card(heavy))[0]
    assert "recall_load_high" in flags
    # 강조가 답의 거의 전부라 프레임 깃발은 서지 않는다 — 두 축이 다른 고장이다.
    assert "answer_frame_heavy" not in flags


def test_평범한_카드에는_아무_깃발도_안_선다():
    plain = "주요 감염경로는 **경구감염 & 경피감염**이다"
    flags = _flags(_card(plain))[0]
    assert "recall_load_high" not in flags
    assert "answer_frame_heavy" not in flags
