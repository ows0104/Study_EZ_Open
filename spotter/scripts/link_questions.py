"""복원한 족보 문항을 마스터 테이블에 연결하고 출제빈도를 낸다.

    uv run --python 3.13 python scripts/link_questions.py

입력: data/past_questions.json, species.json, specimens.json, glossary.json
출력: data/past_questions_linked.json   문항별 유형 + 정답 종/표본/구조물
      data/exam_frequency.json          종·표본·구조물별 출제 횟수와 가중치
      data/exam_frequency.csv           엑셀 검토용
"""

import csv
import difflib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# 문항 유형: 앞에 있는 규칙이 우선한다.
QTYPES = [
    ("계측",        [r"크기를\s*측정", r"계측", r"ocular", r"micrometer", r"눈금"]),
    ("indicator",  [r"indicator", r"화살표", r"구조물"]),
    ("감염경로",    [r"감염\s*경로", r"감염\s*원", r"먹으면", r"섭취", r"먹고", r"먹은",
                    r"전파\s*방식", r"감염되는\s*방식", r"감염\s*원인", r"어떤\s*음식"]),
    ("감염형",      [r"감염\s*형", r"인체감염형", r"발육\s*단계", r"발육단계"]),
    ("매개질환",    [r"매개", r"발생하는\s*병", r"일으키는\s*질환"]),
    ("치료",       [r"치료", r"복용", r"도포", r"약물"]),
    ("숙주",       [r"숙주"]),
    ("기생부위",    [r"기생\s*부위", r"서식", r"거주하는\s*조직", r"기생하는\s*부위"]),
    ("증상·질병",   [r"증상", r"병명", r"질병", r"질환", r"소견", r"특징적인\s*소견"]),
    ("진단",       [r"진단", r"검사법", r"검사\s*방법"]),
    ("충란 동정",   [r"충란"]),
    ("종 동정",     [r"학명", r"이름", r"무엇인가", r"어떤\s*기생충", r"고르시오",
                    r"기생충은\?", r"원충은\?", r"종은\?"]),
]

NORM_RE = re.compile(r"[^0-9a-z가-힣]")


def norm(s):
    return NORM_RE.sub("", (s or "").lower())


def load(name):
    return json.load(open(os.path.join(DATA, name), encoding="utf-8"))


def build_species_index(species):
    """학명·한글명·별칭에 더해 병명과 '속명 축약형'(E. histolytica)까지 색인한다."""
    idx = {}
    for s in species:
        keys = [s["scientific_name"], s["name_ko"], s.get("name_en"),
                s.get("disease_ko"), s.get("disease_en")] + s.get("aliases", [])
        sci = s["scientific_name"].split()
        if len(sci) == 2:
            keys.append(f"{sci[0][0]}. {sci[1]}")
            keys.append(f"{sci[0][0]}{sci[1]}")
        for key in keys:
            if key and norm(key):
                idx.setdefault(norm(key), s["id"])
    return idx


def build_stage_index(species):
    """감염형·발육단계 어휘."""
    idx = {}
    for term in ["cercaria", "metacercaria", "miracidium", "sporocyst", "redia",
                 "plerocercoid", "procercoid", "cysticercus", "cysticercoid",
                 "hydatid cyst", "protoscolex", "oncosphere", "filariform larva",
                 "rhabditoid larva", "embryonated egg", "sporozoite", "merozoite",
                 "trophozoite", "schizont", "gametocyte", "ring form", "oocyst",
                 "tachyzoite", "bradyzoite", "amastigote", "promastigote",
                 "epimastigote", "trypomastigote", "microfilaria",
                 "자충포장란", "사상유충", "간상유충", "피낭유충", "유미유충",
                 "의미충", "전미충", "낭미충", "포낭"]:
        idx[norm(term)] = term
    return idx


def build_structure_index(specimens, glossary):
    idx = {}
    for x in specimens:
        for st in x.get("structures", []):
            idx.setdefault(norm(st), st)
    for term, alts in glossary.get("aliases", {}).items():
        idx.setdefault(norm(term), term)
        for a in alts:
            idx.setdefault(norm(a), term)
    for fake in glossary.get("fake_distractors", []):
        idx.setdefault(norm(fake["term"]), fake["term"])
    return idx


def qtype_of(stem):
    s = stem.lower()
    for name, pats in QTYPES:
        if any(re.search(p, s) for p in pats):
            return name
    return "기타"


def head(text):
    """괄호 주석·부연 설명을 떼고 핵심 답만 남긴다."""
    t = re.split(r"[(（]", text or "", maxsplit=1)[0]
    t = re.split(r"\s*[-–—]\s", t, maxsplit=1)[0]
    return t.strip(" .,:;")


def lookup(text, index, keys, cutoff=0.86):
    """정확 일치 -> 부분 일치 -> 퍼지 순으로 찾는다."""
    n = norm(text)
    if not n:
        return None
    if n in index:
        return index[n]
    for k in keys:
        if len(k) >= 8 and (k in n or n in k):
            return index[k]
    hit = difflib.get_close_matches(n, keys, n=1, cutoff=cutoff)
    return index[hit[0]] if hit else None


def main():
    payload = load("past_questions.json")
    questions = payload["questions"]
    species = load("species.json")
    specimens = load("specimens.json")
    glossary = load("glossary.json")

    sp_idx = build_species_index(species)
    sp_keys = sorted(sp_idx, key=len, reverse=True)
    st_idx = build_structure_index(specimens, glossary)
    st_keys = sorted(st_idx, key=len, reverse=True)
    stage_idx = build_stage_index(species)
    stage_keys = sorted(stage_idx, key=len, reverse=True)
    sp_by_id = {s["id"]: s for s in species}
    by_species = defaultdict(list)
    for x in specimens:
        by_species[x["species_id"]].append(x)

    # 표본 유형을 짐작하는 지문 신호
    TYPE_HINT = [("충란", ["충란", "알"]), ("gross", ["gross", "육안", "적출", "jar"]),
                 ("조직", ["조직", "표본이다", "단면", "section", "간 표본", "뇌조직"]),
                 ("혈액도말", ["도말", "혈액", "smear"])]

    linked = []
    for q in questions:
        row = dict(q)
        row["qtype"] = qtype_of(q["stem"])

        correct = None
        if (q.get("answer_index") is not None and q["options"]
                and 0 <= q["answer_index"] < len(q["options"])):
            correct = q["options"][q["answer_index"]]
        if not correct:
            correct = q.get("answer_text") or q.get("answer_raw")
        row["correct_text"] = correct

        cand = head(correct) if correct else None
        row["answer_species_id"] = None
        row["answer_structure"] = None
        row["answer_stage"] = None
        for text in filter(None, (cand, correct)):
            row["answer_species_id"] = row["answer_species_id"] or lookup(text, sp_idx, sp_keys)
            row["answer_structure"] = row["answer_structure"] or lookup(text, st_idx, st_keys)
            row["answer_stage"] = row["answer_stage"] or lookup(text, stage_idx, stage_keys)
        if row["answer_species_id"]:
            row["answer_kind"] = "species"
        elif row["answer_structure"]:
            row["answer_kind"] = "structure"
        elif row["answer_stage"]:
            row["answer_kind"] = "stage"
        elif correct:
            row["answer_kind"] = "other"
        else:
            row["answer_kind"] = None

        # 보기에 등장한 종 전부 (오답 후보 학습용)
        mentioned = []
        for opt in q["options"]:
            sid = lookup(opt, sp_idx, sp_keys)
            if sid and sid not in mentioned:
                mentioned.append(sid)
        row["option_species_ids"] = mentioned

        # 정답 종이 잡히면 표본까지 좁혀본다
        row["answer_specimen_id"] = None
        sid = row["answer_species_id"]
        if sid and by_species[sid]:
            blob = (q["stem"] + " " + (correct or "")).lower()
            want = None
            for stype, toks in TYPE_HINT:
                if any(t in blob for t in toks):
                    want = stype
                    break
            pool = [x for x in by_species[sid] if x["specimen_type"] == want] if want else []
            if not pool:
                pool = by_species[sid]
            if len(pool) == 1:
                row["answer_specimen_id"] = pool[0]["id"]
            else:
                # 정답·지문에 나온 단어를 표본의 stage·라벨과 맞춰 좁힌다
                scored = []
                for x in pool:
                    words = norm(x.get("stage") or "") + norm(x["label_ko"]) + norm(x["label_en"])
                    sc = 0
                    for tok in re.findall(r"[a-z]{5,}|[가-힣]{2,}", blob):
                        if norm(tok) and norm(tok) in words:
                            sc += 1
                    scored.append((sc, x))
                scored.sort(key=lambda t: -t[0])
                if scored[0][0] > 0 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
                    row["answer_specimen_id"] = scored[0][1]["id"]
        linked.append(row)

    with open(os.path.join(DATA, "past_questions_linked.json"), "w", encoding="utf-8") as fh:
        json.dump({"questions": linked, "recall_lists": payload["recall_lists"]},
                  fh, ensure_ascii=False, indent=2)

    # ── 출제빈도 집계
    ans_years = defaultdict(list)
    opt_count = Counter()
    for q in linked:
        if q["answer_species_id"]:
            ans_years[q["answer_species_id"]].append(q["year"])
        for sid in q["option_species_ids"]:
            opt_count[sid] += 1
    spec_years = defaultdict(list)
    for q in linked:
        if q["answer_specimen_id"]:
            spec_years[q["answer_specimen_id"]].append(q["year"])
    struct_years = defaultdict(list)
    for q in linked:
        if q["answer_structure"]:
            struct_years[q["answer_structure"]].append(q["year"])

    def entries(table, extra=None):
        out = []
        for key, years in table.items():
            years = sorted(years)
            out.append({
                "id": key,
                "answer_count": len(years),
                "years": years,
                "recent_year": years[-1],
                "option_count": (extra or {}).get(key, 0),
                "exam_weight": round(math.sqrt(len(years) + 1), 3),
            })
        out.sort(key=lambda e: (-e["answer_count"], e["id"]))
        return out

    freq = {
        "species": entries(ans_years, opt_count),
        "specimens": entries(spec_years),
        "structures": entries(struct_years),
    }
    # 한 번도 정답이 아니었던 종도 가중치 1.0으로 남겨둔다
    seen = {e["id"] for e in freq["species"]}
    for s in species:
        if s["id"] not in seen:
            freq["species"].append({"id": s["id"], "answer_count": 0, "years": [],
                                    "recent_year": None,
                                    "option_count": opt_count.get(s["id"], 0),
                                    "exam_weight": 1.0})
    with open(os.path.join(DATA, "exam_frequency.json"), "w", encoding="utf-8") as fh:
        json.dump(freq, fh, ensure_ascii=False, indent=2)

    with open(os.path.join(DATA, "exam_frequency.csv"), "w",
              encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["구분", "id", "이름", "정답횟수", "보기등장", "출제연도",
                    "최근", "가중치"])
        for e in freq["species"]:
            s = sp_by_id[e["id"]]
            w.writerow(["종", e["id"], s["name_ko"], e["answer_count"],
                        e["option_count"], " ".join(e["years"]),
                        e["recent_year"] or "", e["exam_weight"]])
        spec_by_id = {x["id"]: x for x in specimens}
        for e in freq["specimens"]:
            w.writerow(["표본", e["id"], spec_by_id[e["id"]]["label_ko"],
                        e["answer_count"], "", " ".join(e["years"]),
                        e["recent_year"], e["exam_weight"]])
        for e in freq["structures"]:
            w.writerow(["구조물", e["id"], e["id"], e["answer_count"], "",
                        " ".join(e["years"]), e["recent_year"], e["exam_weight"]])

    # ── 리포트
    print(f"문항 {len(linked)}개\n")
    print("─ 문항 유형")
    for k, v in Counter(q["qtype"] for q in linked).most_common():
        print(f"    {k:12s} {v:4d}")
    print()
    hit_sp = sum(1 for q in linked if q["answer_species_id"])
    hit_st = sum(1 for q in linked if q["answer_structure"])
    hit_sg = sum(1 for q in linked if q["answer_stage"])
    hit_any = sum(1 for q in linked
                  if q["answer_species_id"] or q["answer_structure"] or q["answer_stage"])
    have_ans = sum(1 for q in linked if q["correct_text"])
    print(f"정답 텍스트가 있는 문항 {have_ans}개 중")
    print(f"    종에 연결      {hit_sp}")
    print(f"    구조물에 연결   {hit_st}")
    print(f"    감염형에 연결   {hit_sg}")
    print(f"    둘 중 하나 연결 {hit_any}  (미연결 {have_ans - hit_any})")
    print()
    print("─ 정답으로 가장 많이 나온 종 top 15")
    for e in freq["species"][:15]:
        s = sp_by_id[e["id"]]
        print(f"    {e['answer_count']:2d}회 (보기 {e['option_count']:2d}회) w={e['exam_weight']:.2f}  "
              f"{s['name_ko']} — {' '.join(e['years'])}")
    print()
    print("─ indicator 정답 구조물 top 12")
    for e in freq["structures"][:12]:
        print(f"    {e['answer_count']:2d}회  {e['id']}  — {' '.join(e['years'])}")


if __name__ == "__main__":
    main()
