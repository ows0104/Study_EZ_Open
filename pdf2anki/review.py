"""학습 목표를 사람이 1분 안에 훑을 수 있게 펼친다.

이 파이프라인에서 사람이 개입하는 유일한 지점이다.
완성된 카드 100장을 검토하면 5분이 들고 '빠진 것'은 보이지 않는다.
학습 목표 40줄을 훑으면 1분이 들고 빠진 단원이 보인다.

사용:
    python -m pdf2anki.review out/lec03              # plan.review.md 를 만들고 요약을 찍는다
    python -m pdf2anki.review out/lec03 --approve    # plan.approved.json 으로 확정한다
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def render(plan: dict, prep: dict) -> tuple[str, dict]:
    objs = sorted(plan.get("objectives", []),
                  key=lambda o: (min(o.get("slides") or [10 ** 6]), o["objective"]))
    # 기출 목표는 슬라이드가 아니라 연도 순으로 읽는다 — 강의 진행 순서가 없다.
    jobjs = sorted(plan.get("jokbo_objectives", []),
                   key=lambda o: (sorted(o.get("jokbo_refs") or [], reverse=True),
                                  o["objective"]))
    rejected = plan.get("rejected_candidates", [])
    n_slides = prep["slides"]

    covered = {s for o in objs for s in o.get("slides", [])}
    declared = {s for r in rejected for s in r.get("slides", [])}
    untouched = sorted(set(range(1, n_slides + 1)) - covered - declared)

    # 슬라이드별 사이드카 요약 — 빠진 슬라이드에 무엇이 있었는지 바로 보이게 한다
    brief = {}
    for s in prep["pages"]:
        head = (s["lecture_text"] or "").strip().split("\n")[0][:52]
        if not head and s["annotations"]:
            head = "(필기) " + s["annotations"][0]["text"][:44]
        if not head and s["lecture_figures"]:
            head = f"(그림 {len(s['lecture_figures'])}개)"
        brief[s["slide"]] = head or "(빈 슬라이드)"

    L = [f"# 학습 목표 검토 — {prep['source']}", "",
         f"목표 {len(objs)}개 · 제외 기록 {len(rejected)}건 · 슬라이드 {n_slides}장", "",
         "빠진 것이 있는지만 본다. 문장을 다듬을 필요는 없다.", ""]
    for i, o in enumerate(objs, 1):
        sl = o.get("slides") or []
        tag = f"S{min(sl)}" + (f"-{max(sl)}" if len(sl) > 1 else "") if sl else "S?"
        mark = "★" if o.get("importance") == "core" else " "
        jk = f"  [기출 {', '.join(o['jokbo_refs'])}]" if o.get("jokbo_refs") else ""
        L.append(f"{i:3d}. {mark} `{tag:<8}` {o['objective']}{jk}")
        L.append(f"        └ {' · '.join(o.get('retrieval_targets', []))}")
    L.append("")
    if jobjs:
        L += [f"## 기출 파트 — 목표 {len(jobjs)}개", "",
              "강의록 파트와 겹쳐도 된다. **같은 것을 같은 방향으로** 묻고 있지 않은지만 봐라.", ""]
        for i, o in enumerate(jobjs, 1):
            mark = "★" if o.get("importance") == "core" else " "
            ax = f"  [{o['axis']}]" if o.get("axis") else ""
            n = len(o.get("jokbo_refs") or [])
            yrs = f"{n}해 반복" if n > 1 else (o.get("jokbo_refs") or ["?"])[0]
            L.append(f"{i:3d}. {mark} `{yrs:<10}` {o['objective']}{ax}")
            L.append(f"        └ {' · '.join(o.get('retrieval_targets', []))}")
            L.append(f"        └ 기출 {', '.join(o.get('jokbo_refs') or [])}")
        L.append("")
    # 족보 부록은 "뺐다" 가 아니라 "기출로 다룬다" 이므로 같은 목록에 두지 않는다.
    appendix = [r for r in rejected if r.get("reason") == "jokbo_appendix"]
    dropped = [r for r in rejected if r.get("reason") != "jokbo_appendix"]
    if dropped:
        L += ["## 일부러 뺀 것", ""]
        for r in dropped:
            sl = ",".join(str(x) for x in r.get("slides", [])) or "-"
            L.append(f"- `S{sl}` {r['candidate']}  ({r['reason']})")
        L.append("")
    if appendix:
        L += ["## 기출 파트로 넘긴 구간", "",
              "강의록 목표로 안 삼았을 뿐 버린 것이 아니다. "
              "여기에 **강의록 내용까지** 섞여 있지 않은지만 봐라.", ""]
        for r in appendix:
            sl = ",".join(str(x) for x in r.get("slides", [])) or "-"
            L.append(f"- `S{sl}` {r['candidate']}")
        L.append("")
    if untouched:
        L += ["## ⚠ 목표에도 제외 기록에도 없는 슬라이드", "",
              "여기에 배울 것이 있었는지만 확인해라.", ""]
        for s in untouched:
            L.append(f"- Slide {s:<3} {brief.get(s, '')}")
        L.append("")
    return "\n".join(L), {"objectives": len(objs), "rejected": len(rejected),
                          "untouched": untouched, "core": sum(
                              1 for o in objs if o.get("importance") == "core"),
                          "with_jokbo": sum(1 for o in objs if o.get("jokbo_refs")),
                          "jokbo_objectives": len(jobjs)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="학습 목표를 사람이 훑도록 펼친다")
    ap.add_argument("prep_dir")
    ap.add_argument("--approve", action="store_true",
                    help="plan.json 을 plan.approved.json 으로 확정한다")
    args = ap.parse_args(argv)

    d = Path(args.prep_dir)
    plan_path = d / "plan.json"
    if not plan_path.exists():
        print(f"{plan_path} 가 없다. 먼저 prompt.plan.md 를 실행해라.")
        return 1
    raw = json.loads(plan_path.read_text(encoding="utf-8"))
    plan = raw.get("learning_plan", raw)
    prep = json.loads((d / "prep.json").read_text(encoding="utf-8"))

    text, stats = render(plan, prep)
    (d / "plan.review.md").write_text(text, encoding="utf-8")

    if args.approve:
        shutil.copyfile(plan_path, d / "plan.approved.json")
        print(f"승인 확정 → {d}/plan.approved.json")
        print(f"이제 prompt.cards.md 를 실행하면 된다.")
        return 0

    print(f"강의록 목표 {stats['objectives']}개 (core {stats['core']}, "
          f"기출 연결 {stats['with_jokbo']}개) · "
          f"기출 목표 {stats['jokbo_objectives']}개 · 제외 기록 {stats['rejected']}건")
    if stats["untouched"]:
        print(f"⚠ 목표에도 제외 기록에도 없는 슬라이드 {len(stats['untouched'])}장: "
              f"{stats['untouched'][:20]}{' …' if len(stats['untouched']) > 20 else ''}")
    print(f"\n→ {d}/plan.review.md  (1분 훑고, 고칠 게 있으면 plan.json 을 고쳐라)")
    print(f"   확정: python -m pdf2anki.review {args.prep_dir} --approve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
