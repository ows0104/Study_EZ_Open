"""시간표 한 칸의 `details`를 제목과 담당으로 가른다.

2026-08-31, 캘린더의 감염의 기초 실습이 제목 없이 「담당: 연충란 최민호, …」로 떴다.
`연충란`은 그날 실습의 이름이지 사람이 아니다. 시간표 JSON에서 그 줄이 담당 칸으로
넘어와 있었고, 화면은 담당에 든 줄을 제목에서 빼도록 되어 있어서(그게 교수 이름을
제목에서 빼는 정상 동작이다) 제목이 통째로 사라졌다.

여기서 지키는 것은 **되돌리되 함부로 손대지 않는다**는 것이다. 소제목과 사람 이름은
글자로 안 갈린다 — `연충란`·`천식`은 `고정민`·`김만진`과 길이도 꼴도 같다. 그래서
규칙을 짜지 않고 시간표 자신이 아는 이름에 물어본다. 물어볼 데가 없으면 그냥 둔다.

    server/.venv/Scripts/python.exe -m tests.test_details_split
"""

from __future__ import annotations

from app.naming import professor_names, strip_lead_topic

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


# 2026 시간표에서 그대로 가져온 칸들. 손으로 지어낸 것이 아니다.
REAL = [
    # ① 고쳐야 하는 칸 — 소제목이 담당 앞에 붙어 왔다.
    ("(MDL)\n연충란\n최민호, 신은희, 여선주,\n송현범, 김주현",
     "연충란 최민호, 신은희, 여선주, 송현범, 김주현",
     "최민호, 신은희, 여선주, 송현범, 김주현"),
    ("혈관염\n박진균", "혈관염 박진균", "박진균"),
    ("암면역\n(분반) A: 김태민\n(분반) B: 김범석",
     "암면역 (분반) A: 김태민 (분반) B: 김범석",
     "(분반) A: 김태민 (분반) B: 김범석"),
    ("미생물의 병인론 2:\n세균\n방예지", "세균 방예지", "방예지"),

    # ② 손대면 안 되는 칸 — 첫 줄이 진짜 교수다.
    ("염색체이상질환\n고정민", "고정민", "고정민"),
    ("(가계도 분석과\n위험도 계산)\n고정민\n문장섭\n김만진",
     "고정민 문장섭 김만진", "고정민 문장섭 김만진"),
    ("감염학) 세균 감염\n(분반) A: 문송미\n(분반) B: 강창경",
     "(분반) A: 문송미 (분반) B: 강창경",
     "(분반) A: 문송미 (분반) B: 강창경"),
    ("성승용, 조남혁, 이원우,\n석승혁, 김동현, 염진기,\n방예지, 김현제",
     "성승용, 조남혁, 이원우, 석승혁, 김동현, 염진기, 방예지, 김현제",
     "성승용, 조남혁, 이원우, 석승혁, 김동현, 염진기, 방예지, 김현제"),
    ("기생충학 총론 (1)\n최민호", "최민호", "최민호"),
    ("세계화와 국제보건\n박영수", "박영수", "박영수"),
]


def main() -> None:
    names = professor_names([(details, professor) for details, professor, _ in REAL])

    print("[1] 사전은 소제목을 이름으로 배우지 않는다")
    check("연충란은 이름이 아니다", "연충란" not in names)
    check("혈관염은 이름이 아니다", "혈관염" not in names)
    # 셋째 규칙(앞 토큰의 끝 낱말)이 없으면 이 이름을 배울 데가 없다.
    check("박진균은 이름이다", "박진균" in names)
    check("고정민은 이름이다", "고정민" in names)

    print("\n[2] 실측한 칸을 그대로 통과시킨다")
    for details, professor, want in REAL:
        got = strip_lead_topic(details, professor, names)
        head = details.split("\n")[0]
        check(f"{head} → {want[:24]}", got == want, got)

    print("\n[3] 물어볼 이름이 없으면 손대지 않는다")
    # 사전이 비면 ③(남는 쪽이 이름인가)이 서지 않는다. 그때 떼면 담당이 통째로
    # 빈다 — 제목을 잃는 것보다 나쁘다.
    check(
        "빈 사전에서는 그대로 둔다",
        strip_lead_topic("혈관염\n박진균", "혈관염 박진균", frozenset()) == "혈관염 박진균",
    )

    print("\n[4] 담당이 뒷줄들과 안 맞으면 건드릴 자리가 없다")
    # `details`에 없는 말이 담당에 있으면 어디서 잘렸는지 알 수 없다.
    check(
        "이어 붙인 것과 다르면 그대로 둔다",
        strip_lead_topic("세계화와 의료윤리 (2)\n(13:00~13:30)", "김훈", names) == "김훈",
    )

    print()
    if failures:
        raise SystemExit(f"{len(failures)}개 실패: {failures}")
    print("전부 통과.")


if __name__ == "__main__":
    main()
