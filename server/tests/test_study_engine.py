"""Study Engine 이 시제품(JS)과 같은 결정을 내리는가.

AdaptiveStudy3/tests/engine.test.mjs 를 하나씩 옮겼다(2026-10-04). 엔진은 DB 도 시계도 없는
순수 함수라 한 프로세스에서 시각을 손으로 밀며 잰다(`test_srs.py` 와 같은 방식).

    server/.venv/Scripts/python.exe -m tests.test_study_engine
"""

from __future__ import annotations

import copy
import json
import os
import sys
from datetime import datetime

os.environ.setdefault("ENVIRONMENT", "local-test")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.study_engine import (DEFAULT, days_until, empty_state, end_session, rank_questions,  # noqa: E402
                              record_review, select_question, session_summary, start_session, upgrade_state)
from app.study_engine.engine import concept_map, concept_readiness, target_for  # noqa: E402
from app.study_engine.policy import validate_policy  # noqa: E402
from tests.bank_fixtures import example_bank, simulation_bank  # noqa: E402

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


def ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp() * 1000)


NOW = ms("2026-10-03T12:00:00+09:00")
EXAM = "2026-10-12"


def set_mastery(state: dict, cid: str, d: str, value: float) -> None:
    state["dimensions"][f"{cid}:{d}"] = {"mastery": value, "reviews": 3, "updated_at": NOW}


def raises(fn) -> bool:
    try:
        fn()
    except ValueError:
        return True
    return False


print("평가와 숙련도")
bank, initial = example_bank(), empty_state()
hard = good = initial
for i in range(20):
    hard = record_review(bank, hard, "Q1", "Hard", NOW + i)
    good = record_review(bank, good, "Q1", "Good", NOW + i)
check("Hard 만 누르면 0.46 아래에 머문다", hard["dimensions"]["C1:direct"]["mastery"] < 0.46)
check("Good 으로는 상한 목표를 넘는다", good["dimensions"]["C1:direct"]["mastery"] > DEFAULT["mastery"]["maxTarget"])
check("다른 방향은 건드리지 않는다", "C1:reverse" not in good["dimensions"])
check("원래 상태는 그대로다", len(initial["history"]) == 0)
lowered = record_review(bank, good, "Q1", "Hard", NOW + 30)
check("Hard 는 숙련도를 내린다", lowered["dimensions"]["C1:direct"]["mastery"] < good["dimensions"]["C1:direct"]["mastery"])
check("모르는 평가는 거절", raises(lambda: record_review(bank, good, "Q1", "bad", NOW)))
bank["retrieval_plan"][0]["target_mastery"] = 1
check("요청 목표 1 은 Core 상한 .85로", target_for(bank, bank["questions"][0]) == {"requested": 1, "effective": 0.85})

print("선행 문항 보충")
bank = example_bank()
bank["questions"][2]["prerequisites"] = ["Q1", "Q2"]
initial = empty_state()
set_mastery(initial, "C1", "direct", 0.9)
set_mastery(initial, "C1", "reverse", 0.1)
state = record_review(bank, initial, "Q3", "Again", NOW)
check("가장 약한 선행 문항을 고른다", state["remediations"][0]["prerequisite_id"] == "Q2")
snapshot = json.dumps(state, sort_keys=True)
check("진단 조회는 횟수를 안 쓴다",
      all(select_question(bank, state, EXAM, NOW)["question"]["question_id"] == "Q2" for _ in range(4)))
check("진단 조회는 상태를 안 바꾼다", json.dumps(state, sort_keys=True) == snapshot)
check("보충 중 부모 문항은 못 고른다",
      not next(r for r in rank_questions(bank, state, EXAM, NOW) if r["question_id"] == "Q3")["eligible"])
recovered = record_review(bank, state, "Q2", "Good", NOW + 1)
check("Good 으로 보충이 풀린다", recovered["remediations"] == [] and recovered["remediation_events"][-1]["action"] == "recovered")
check("풀려도 약한 기초는 부모를 막는다",
      not next(r for r in rank_questions(bank, recovered, EXAM, NOW + 2) if r["question_id"] == "Q3")["eligible"])
set_mastery(recovered, "C1", "reverse", 0.9)
check("기초가 차면 부모가 열린다",
      next(r for r in rank_questions(bank, recovered, EXAM, NOW + 60001) if r["question_id"] == "Q3")["eligible"])

print("보충은 영원히 우선하지 않는다")
bank = example_bank()
state = record_review(bank, empty_state(), "Q3", "Again", NOW)
for i in range(DEFAULT["remediation"]["maxReviews"]):
    state = record_review(bank, state, "Q1", "Hard", NOW + i + 1)
check("Hard 만으로는 만료된다", state["remediations"] == [] and state["remediation_events"][-1]["action"] == "expired")

print("있는 단계부터 시작한다")
bank = example_bank()
bank["questions"] = [bank["questions"][1]]
bank["questions"][0]["prerequisites"] = []
check("reverse 만 있으면 2단계", concept_readiness(bank, empty_state(), "C1") == 2)
check("그것을 고른다", select_question(bank, empty_state(), EXAM, NOW)["question"]["question_id"] == "Q2")
bank["questions"][0]["retrieval_direction"] = "mechanism"
check("mechanism 만 있으면 3단계", concept_readiness(bank, empty_state(), "C1") == 3)
check("그래도 고를 것이 있다", select_question(bank, empty_state(), EXAM, NOW)["question"] is not None)

print("약한 중요 Core 가 Optional 을 막는다")
bank = example_bank()
bank["questions"][1]["tier"], bank["questions"][1]["importance"] = "Optional", 2
state = record_review(bank, empty_state(), "Q1", "Good", NOW)
choice = select_question(bank, state, "2026-10-04", NOW + 1)
check("Core 가 쉬는 중이어도 Optional 을 안 낸다", choice["question"] is None)
check("이유에 Core 가 있다", "Core" in " ".join(next(r for r in choice["ranked"] if r["question_id"] == "Q2")["reasons"]))
set_mastery(state, "C1", "direct", 0.9)
check("Core 가 차면 열린다",
      next(r for r in rank_questions(bank, state, "2026-10-04", NOW + 1) if r["question_id"] == "Q2")["eligible"])

print("시험 임박과 한국 날짜")
bank = example_bank()
bank["questions"][1]["importance"], bank["questions"][1]["tier"] = 1, "Core"
early = next(r for r in rank_questions(bank, empty_state(), "2026-11-01", NOW) if r["question_id"] == "Q2")
late = next(r for r in rank_questions(bank, empty_state(), "2026-10-05", NOW) if r["question_id"] == "Q2")
check("임박하면 안 본 저중요 문항을 누른다", early["score"] > late["score"] * 5, (early["score"], late["score"]))
check("날짜는 한국 기준", days_until("2026-10-04", ms("2026-10-03T15:01:00+00:00")) == 0)

print("진단")
ranked = rank_questions(example_bank(), empty_state(), EXAM, NOW)
q3 = next(r for r in ranked if r["question_id"] == "Q3")
check("막힌 후보도 원점수와 이유를 남긴다", q3["score"] == 0 and q3["raw_score"] > 0 and q3["reasons"])

print("150회 연속 학습")
bank, state, previous, ok = simulation_bank(), empty_state(), None, True
for i in range(150):
    sel = select_question(bank, state, "2026-10-20", NOW + i * 90000)
    if not sel["question"]:
        ok = False
        break
    qid = sel["question"]["question_id"]
    if not next(r for r in sel["ranked"] if r["question_id"] == qid)["remediation"] and qid == previous:
        ok = False
        break
    previous = qid
    state = record_review(bank, state, qid, "Good" if i % 7 else "Again", NOW + i * 90000)
check("늘 고를 것이 있고 의도치 않은 연속 반복이 없다", ok, i)
check("숙련도는 0–1 안", all(0 <= d["mastery"] <= 1 for d in state["dimensions"].values()))

print("회차")
bank = example_bank()
state = start_session(bank, empty_state(), 10, NOW)
sid = state["session"]["id"]
state = record_review(bank, state, "Q1", "Good", NOW + 100)
state = record_review(bank, state, "Q2", "Hard", NOW + 200)
check("진행 중 회차는 다시 열어도 같다", start_session(bank, state, 20, NOW)["session"]["id"] == sid)
state = end_session(bank, state, "user_finished", NOW + 300)
summary = session_summary(bank, state)
check("평가 수", summary["reviewed"] == 2 and summary["ratings"]["Good"] == 1 and summary["ratings"]["Hard"] == 1)
check("오른 방향 둘, 약점 있음", len(summary["improved"]) == 2 and summary["weaknesses"])
check("Core 가 올랐다", summary["core_after"] > summary["core_before"])
check("두 번 끝내도 요약은 하나", len(end_session(bank, state, "user_finished", NOW + 400)["sessions"]) == 1)

print("옛 상태 옮기기")
old = {"dimensions": {"C1:direct": {"mastery": .32, "reviews": 1}}, "items": {},
       "history": [{"question_id": "Q1", "rating": "Good", "timestamp": NOW}],
       "remediation": {"target": "Q3"}, "served": {"question_id": "Q2"}}
migrated = upgrade_state(example_bank(), old, DEFAULT, NOW)
check("기록과 숙련도를 지킨다", migrated["history"] == old["history"] and migrated["dimensions"] == old["dimensions"])
check("남은 보충에 상한", migrated["remediations"][0]["remaining"] == DEFAULT["remediation"]["maxReviews"])
check("내주던 문항을 거둔다", migrated["served"] is None and old["served"]["question_id"] == "Q2")

print("개념 지도")
bank = example_bank()
bank["concepts"][0]["related_concepts"] = ["C1", "C9"]  # 자기 자신 · 없는 개념
bank["retrieval_plan"][0]["directions"].append("trap")  # 계획엔 있고 문항은 없는 방향
fresh = concept_map(bank, empty_state())
check("옛 은행은 그래프 요약 없이도 열린다", fresh[0]["graph_title"] == "")
bank["concepts"][0]["graph_title"] = "그래프용 이름"
with_label = concept_map(bank, empty_state())[0]
check("그래프 요약과 전체 제목을 따로 전달한다", with_label["graph_title"] == "그래프용 이름"
      and with_label["title"] == bank["concepts"][0]["title"])
check("개념마다 한 줄", [c["concept_id"] for c in fresh] == ["C1"])
check("방향은 문항이 있는 것만 · direct 가 먼저", [d["direction"] for d in fresh[0]["directions"]]
      == ["direct", "reverse", "integration"], fresh[0]["directions"])
check("목표는 문항 중요도별 상한을 씌운 값", all(d["target"] == max(target_for(bank, q)["effective"] for q in bank["questions"] if q["retrieval_direction"] == d["direction"])
                                    for d in fresh[0]["directions"]))
check("처음엔 숙련도 0 · 진척 0", fresh[0]["progress"] == 0 and all(d["mastery"] == 0 for d in fresh[0]["directions"]))
check("관련 개념은 있는 것만, 자기 자신은 빼고", fresh[0]["related_concepts"] == [])
studied = record_review(bank, empty_state(), "Q1", "Good", NOW)
after = {d["direction"]: d for d in concept_map(bank, studied)[0]["directions"]}
check("푼 방향만 오른다", after["direct"]["mastery"] > 0 and after["direct"]["reviews"] == 1
      and after["reverse"]["mastery"] == 0, after)
check("진척은 목표 대비 평균", abs(concept_map(bank, studied)[0]["progress"]
                              - min(after["direct"]["mastery"] / after["direct"]["target"], 1) / 3) < 1e-9)

print("정책 검사")
changes = [lambda p: p["mastery"].__setitem__("alpha", 2), lambda p: p["mastery"].__setitem__("maxTarget", 1),
           lambda p: p["mastery"]["ratings"].__setitem__("Good", 0.75),
           lambda p: p["progression"].__setitem__("prerequisiteMastery", 1),
           lambda p: p["remediation"].__setitem__("maxReviews", -1), lambda p: p["session"].__setitem__("sizes", []),
           lambda p: p["exam"].__setitem__("middleDays", 99)]
for n, change in enumerate(changes):
    policy = copy.deepcopy(DEFAULT)
    change(policy)
    check(f"도달할 수 없는 정책 {n} 을 거절", raises(lambda: validate_policy(policy)))

print()
print(f"{'FAIL' if failures else 'OK'} — 실패 {len(failures)}")
sys.exit(1 if failures else 0)
