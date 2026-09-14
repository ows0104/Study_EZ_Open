"""족보에 보기가 빠진 문항의 보기를 채운다.

    uv run --python 3.13 python scripts/fill_gaps.py

입력: data/past_questions_linked.json, species.json, specimens.json, exam_frequency.json
출력: data/past_questions_filled.json

오답은 지어내지 않고 **같은 유형의 다른 해 문항에 실제로 쓰인 보기**에서 뽑는다.
정답이 종이면 그 종의 표본에 적힌 confusable_with를 1순위로 쓴다.
채워 넣은 문항은 options_generated=true 로 표시하므로 원본과 구분된다.
"""

import json
import os
import random
import re
import sys
from collections import Counter, defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SEED = 20260905
N_OPTIONS = 4

BAD_OPTION = re.compile(r"복원|미복원|^\s*$")
# 객관식이 아닌 문항 유형 — 보기를 만들지 않는다
NO_FILL_QTYPES = {"계측"}
# 감염경로 보기는 '전파방식'과 '감염원 음식'이 섞이면 안 된다
MODE_RE = re.compile(r"(토양|식품|접촉|패류|절지동물|수인성|공기|성).{0,2}(매개|감염)|경구감염|경피감염|피부감염")


def load(n):
    return json.load(open(os.path.join(DATA, n), encoding="utf-8"))


def norm(s):
    return re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())


def similar(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    return na == nb or (len(na) > 5 and (na in nb or nb in na))


def main():
    payload = load("past_questions_linked.json")
    questions = payload["questions"]
    species = load("species.json")
    specimens = load("specimens.json")
    freq = load("exam_frequency.json")

    sp_by_id = {s["id"]: s for s in species}
    spec_by_id = {x["id"]: x for x in specimens}
    by_species = defaultdict(list)
    for x in specimens:
        by_species[x["species_id"]].append(x)
    opt_count = {e["id"]: e["option_count"] for e in freq["species"]}

    # 유형별 실제 보기 풀 (같은 유형의 다른 문항에서 실제로 쓰인 보기)
    pool = defaultdict(Counter)
    for q in questions:
        for o in q["options"]:
            if not BAD_OPTION.search(o) and 1 < len(o) < 60:
                pool[q["qtype"]][o.strip()] += 1
    allpool = Counter()
    for c in pool.values():
        allpool.update(c)

    def species_distractors(sid, correct, want):
        """혼동 표본 -> 같은 분류군 순으로, 실제 족보에서 오답으로 자주 쓰인 순."""
        out, seen = [], {norm(correct)}
        cand = []
        for x in by_species.get(sid, []):
            for ref in x.get("confusable_with", []):
                target = spec_by_id.get(ref)
                other = target["species_id"] if target else ref
                if other != sid and other in sp_by_id:
                    cand.append(other)
        group = sp_by_id[sid]["group"]
        rest = [s["id"] for s in species if s["group"] == group and s["id"] != sid]
        rest.sort(key=lambda i: -opt_count.get(i, 0))
        for other in cand + rest:
            name = sp_by_id[other]["scientific_name"]
            if norm(name) in seen:
                continue
            seen.add(norm(name))
            out.append(name)
            if len(out) >= want:
                break
        return out

    def structure_distractors(struct, correct, want):
        """같은 표본의 다른 구조물 -> 혼동 표본의 구조물."""
        hosts = [x for x in specimens if struct in x.get("structures", [])]
        cand = []
        for x in hosts:
            cand += [s for s in x["structures"] if s != struct]
            for ref in x.get("confusable_with", []):
                cand += spec_by_id.get(ref, {}).get("structures", [])
        out, seen = [], {norm(correct), norm(struct)}
        for c in cand:
            if norm(c) in seen:
                continue
            seen.add(norm(c))
            out.append(c)
            if len(out) >= want:
                break
        return out

    def pool_distractors(qtype, correct, exclude, want):
        rng = random.Random(SEED + hash(correct) % 10000)
        cands = [o for o, _ in pool[qtype].most_common()]
        cands += [o for o, _ in allpool.most_common()]
        if qtype == "감염경로":
            # 정답이 전파방식이면 전파방식끼리, 감염원 음식이면 음식끼리 묶는다
            want_mode = bool(MODE_RE.search(correct))
            cands = [c for c in cands if bool(MODE_RE.search(c)) == want_mode]
        out = []
        for c in cands:
            if similar(c, correct) or any(similar(c, e) for e in exclude + out):
                continue
            out.append(c)
            if len(out) >= want * 3:
                break
        rng.shuffle(out)
        return out[:want]

    filled = 0
    for q in questions:
        opts = [o for o in q["options"] if not BAD_OPTION.search(o)]
        correct = q.get("correct_text")
        q["options_generated"] = False
        if q["qtype"] in NO_FILL_QTYPES:
            q["options"] = opts
            continue
        if not correct or len(opts) >= N_OPTIONS:
            q["options"] = opts if len(opts) >= N_OPTIONS else q["options"]
            if len(q["options"]) >= N_OPTIONS and q["answer_index"] is not None:
                pass
            continue
        if q["format"] == "unrestored" and not correct:
            continue

        keep = [o for o in opts if not similar(o, correct)]
        need = N_OPTIONS - 1 - len(keep)
        extra = []
        if need > 0:
            if q.get("answer_species_id"):
                extra = species_distractors(q["answer_species_id"], correct, need)
            elif q.get("answer_structure"):
                extra = structure_distractors(q["answer_structure"], correct, need)
            if len(extra) < need:
                extra += pool_distractors(q["qtype"], correct,
                                          keep + extra, need - len(extra))
        distractors = (keep + extra)[:N_OPTIONS - 1]
        if len(distractors) < N_OPTIONS - 1:
            continue

        rng = random.Random(SEED + hash(f'{q["year"]}{q["no"]}') % 100000)
        new = distractors + [correct]
        rng.shuffle(new)
        q["options"] = new
        q["answer_index"] = new.index(correct)
        q["options_generated"] = True
        q["format"] = "mcq"
        filled += 1

    payload["questions"] = questions
    with open(os.path.join(DATA, "past_questions_filled.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(f"보기를 채운 문항 {filled}개\n")
    print("연도      문항  객관식  단답  미복원  (그중 보기생성)")
    for year in sorted({q["year"] for q in questions}):
        qs = [q for q in questions if q["year"] == year]

        def c(f, rows=qs):
            return sum(1 for q in rows if q["format"] == f)

        g = sum(1 for q in qs if q["options_generated"])
        print(f"{year:8s} {len(qs):4d}  {c('mcq'):5d}  {c('short_answer'):4d}"
              f"  {c('unrestored'):6d}   {g:5d}")
    qs = questions

    def c(f, rows=qs):
        return sum(1 for q in rows if q["format"] == f)

    print(f"{'합계':8s} {len(qs):4d}  {c('mcq'):5d}  {c('short_answer'):4d}"
          f"  {c('unrestored'):6d}   {sum(1 for q in qs if q['options_generated']):5d}")
    print()
    print("─ 생성 예시")
    for q in [x for x in questions if x["options_generated"]][:6]:
        print(f"\n  [{q['year']} {q['no']}] ({q['qtype']}) {q['stem'][:46]}")
        for i, o in enumerate(q["options"]):
            print(f"     {i+1}) {o}{'  <== 정답' if i == q['answer_index'] else ''}")


if __name__ == "__main__":
    main()
