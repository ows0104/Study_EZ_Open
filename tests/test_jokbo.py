"""답가지(보기)를 문항 밖에 한 번만 인쇄하는 연결형 묶음.

족보 PDF 는 이 묶음을 두 가지로 조판한다. 동그라미(①②)면 그냥 두어도 보기로
읽히지만 **평번호(`1.` `2.`)는 문항 시작과 생김새가 똑같다.** 구분하지 않으면
답가지 15줄이 전부 가짜 문항이 되고, 번호가 겹치는 진짜 문항의 정답을 훔쳐 간다 —
실습 2021 에서 17문항, 필기에서 40여 항목이 실제로 그랬다. 조용히 틀리는 자리라
여기 묶어 둔다.

아래 줄들은 2026 족보의 실제 조판을 그대로 옮긴 것이다 (본문은 줄였다).
"""

import pytest

from quizgen.jokbo import Bank, bank_targets


def drain(bank, lines):
    """묶음이 답가지를 다 걷을 때까지 먹인다. 첫 문항 줄에서 멈춘다."""
    for i, ln in enumerate(lines):
        if bank.feed(ln) == "done":
            return lines[i:]
    return []


# ── 머리글의 문항 번호 ──────────────────────────────────────────

@pytest.mark.parametrize("raw,want", [
    ("7,8", ["7", "8"]),
    ("1, 2", ["1", "2"]),
    ("42-43", ["42", "43"]),
    ("3,4", ["3", "4"]),
])
def test_머리글_문항번호(raw, want):
    assert bank_targets(raw) == want


# ── 평번호 답가지: 여기가 무너지던 자리 ──────────────────────────

PLAIN = [
    "1.Parietal cell", "2.Hepatic artery", "3.Myocyte", "4.Hepatocyte",
    "5.Bronchiole", "6.Fatty change", "7.Alveoli", "8.Neutrophil",
    "9.Skeletal muscle", "10.Fibrosis", "11.Portal tract",
    "12.Follicular epithelial cell", "13.Eosinophil", "14.Portal vein",
    "15.Chief cell",
    "7.다음 현미경 사진에서 가장 잘 관찰되는 것을 두 가지",
]


def test_평번호_답가지는_문항이_되지_않는다():
    b = Bank.start("[문항7,8].아래 답가지(1-15) 중에서 각 문항에 해당되는", last_no=95)
    rest = drain(b, PLAIN)
    assert len(b.items) == 15                 # 답가지 15줄을 전부 걷었다
    assert b.items[0] == "1. Parietal cell"
    assert rest[0].startswith("7.다음 현미경")   # 답가지가 끝나고 문항이 시작됐다


def test_평번호_묶음_문항은_R_로_결합한다():
    """정답표가 `R7. 3,10` 으로 찍는다. 평번호 그대로 두면 남의 정답을 집는다."""
    b = Bank.start("[문항7,8].아래 답가지(1-15) 중에서 각 문항에 해당되는", last_no=95)
    drain(b, PLAIN)
    assert b.owns("7") and b.owns("8")
    assert b.key("7") == "R7"
    assert not b.owns("9")


def test_답가지가_두_줄로_넘어가면_이어붙인다():
    b = Bank.start("[문항 1,2].아래 답가지(1-13) 중에서 각 문항의 가장 적절한", last_no=7)
    drain(b, ["답을 주어진 수 만큼 고르시오."]
             + [f"{n}. 답가지 {n}" for n in range(1, 12)]
             + ["12. 바이러스 감염에 의한 편평상피유두종(squamous",
                "cell papilloma)",
                "13. 유방암 치료를 위하여 양쪽 난소를 절제한 여성의 자",
                "궁내막",
                "1.세포/ 조직 적응 과정 중 …"])
    assert len(b.items) == 13
    assert b.items[11] == "12. 바이러스 감염에 의한 편평상피유두종(squamous cell papilloma)"
    assert b.items[12] == "13. 유방암 치료를 위하여 양쪽 난소를 절제한 여성의 자 궁내막"


# ── 동그라미 답가지 ────────────────────────────────────────────

CIRCLED = [
    "① Phosphatidylserine", "② IL-1", "③ BCL2", "④ BIM", "⑤ BAX",
    "⑥ Thrombospondin", "⑦ C1q", "⑧ caspase-3", "⑨ caspase-11",
    "⑩ Caspase-6", "⑪ Caspase-9", "⑫ LC3", "⑬ RIP1", "⑭ RIP3", "⑮ BCL-XL",
    "1. Programmed cell death 중 necrosis와 apoptosis의",
]


def test_동그라미_답가지_뒤의_1번은_문항이다():
    """답가지가 1-15 로 선언돼 있어도 동그라미로 찍혔으면 `1.` 은 답가지가 아니다."""
    b = Bank.start("[문항 1, 2] 아래 답가지 (1-15) 중에서 각 문항의 정답을 주", last_no=15)
    rest = drain(b, CIRCLED)
    assert len(b.items) == 15
    assert b.items[-1] == "⑮ BCL-XL"
    assert rest[0].startswith("1. Programmed")
    assert b.key("1") == "R1"            # 앞 문항이 15번이었다 = 번호가 다시 시작했다


def test_번호가_이어지면_R_을_붙이지_않는다():
    """`[42-43]` 은 앞 문항 41번에서 이어진다. 정답표도 평번호로 찍는다."""
    b = Bank.start("[42-43] 아래 답가지(1-10)는 인체 유전질환의 범주를 나열", last_no=41)
    drain(b, ["한 것이다. 각 문항에 가장 적합한 유전질환범주를 하나씩 고",
              "르시오.",
              "① Autosomal dominant disorder", "② Autosomal recessive disorder",
              "42. 10세 남아는 정신지체, 발달 지연, …"])
    assert b.owns("42") and b.key("42") == "42"
    assert len(b.items) == 2


def test_머리글이_두_줄로_쪼개져도_답가지_범위를_읽는다():
    """`[44-45]` 은 머리글 첫 줄에 '답가지' 가 없다. 둘째 줄에 있다."""
    b = Bank.start("[44-45] 아래 문항의 임상병력을 지닌 환자에서, 핵형분석시", last_no=43)
    assert b is not None
    b.feed("가장 가능성이 있을 것으로 생각되는 핵형을 아래 답가지(1-")
    b.feed("8)에서 하나씩 고르시오.")
    assert (b.nxt, b.hi) == (1, 8)


# ── 묶음이 아닌 것 ─────────────────────────────────────────────

@pytest.mark.parametrize("line", [
    "[주관식1]",
    "[예제] 1854년 8월 28일, 영국의 수도 런던의 브로드가에서",
    "73. 답가지에 열거된 멘델법칙을 따르는 단일 유전자 돌연변",
    "이 유전자를 답가지에서 하나 고르시오.",
])
def test_묶음_머리글이_아니다(line):
    assert Bank.start(line, last_no=10) is None
