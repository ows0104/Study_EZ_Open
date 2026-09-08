"""마스터 테이블 + 이미지 풀 + 출제빈도로 모의 땡시를 만든다.

    uv run --python 3.13 python scripts/generate_exam.py --sets 5 --questions 40

출력: data/generated_exams.json
      data/generated_preview.txt   사람이 훑어볼 미리보기

설계 원칙
  - 표집 가중치는 족보 출제빈도 sqrt(정답횟수+1). 참고 레포와 같은 공식.
  - 오답은 표본의 confusable_with를 1순위로 쓴다. 아무 종이나 섞으면 너무 쉬워진다.
  - 문항 유형·분류군 비율은 족보 279문항에서 뽑은 실제 비율을 따른다.
  - 문항 순서는 족보를 따랐다. 충란은 앞쪽에 몰리지만(5개년 예외 없음)
    분류군 순으로 정렬되지는 않는다(8개년 전부 섞여 있음).
"""

import argparse
import hashlib
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

# 족보 279문항에서 뽑은 유형 비율. '기타'는 실체가 없어 나머지에 흡수시켰다.
QTYPE_MIX = {
    "충란 동정": 0.17,
    "종 동정": 0.20,
    "indicator": 0.20,
    "감염경로": 0.16,
    "감염형": 0.08,
    "증상·질병": 0.08,
    "기생부위": 0.04,
    "치료": 0.03,
    "매개질환": 0.02,
    "숙주": 0.02,
    "진단": 0.02,
}
# 정답 종의 분류군 비율
GROUP_MIX = {"선충": 0.29, "흡충": 0.25, "원충": 0.22, "조충": 0.14,
             "말라리아": 0.07, "의용곤충": 0.03}
GROUP_ORDER = ["선충", "흡충", "조충", "원충", "말라리아", "의용곤충"]

STEMS = {
    "충란 동정": ["다음 충란을 가지는 기생충은?", "다음은 어떤 기생충의 충란인가?",
                "다음 현미경에서 관찰되는 충란의 기생충을 고르시오."],
    "종 동정": ["다음 기생충의 학명으로 옳은 것은?", "다음은 어떤 기생충인가?",
              "현미경에서 관찰되는 기생충을 고르시오."],
    # 실제 땡시의 indicator는 현미경 접안렌즈에 걸린 선분이지만, 여기 쓰는 사진은
    # 정리본에 그려진 화살표·동그라미다. 그래서 "표시"라고 부른다.
    "indicator": ["Indicator(표시)가 가리키는 구조물의 이름은?",
                  "다음 표본에서 표시가 가리키는 구조물은?"],
    "특징 구조물": ["다음 기생충이 가진 특징적 구조물은?",
                 "다음 기생충에서 가장 특징적인 구조물은?"],
    "감염경로": ["다음 기생충의 감염 원인으로 알맞은 것은?",
               "환자에게서 다음 표본이 검출되었다. 감염 원인은?"],
    "감염형": ["다음 기생충의 인체 감염형은?", "다음 기생충의 감염형으로 옳은 것은?"],
    "증상·질병": ["다음 기생충에 감염된 환자의 병명으로 옳은 것은?",
                "다음 기생충이 일으키는 질환은?"],
    "기생부위": ["다음 기생충의 성충 기생 부위는?", "다음 기생충이 기생하는 부위는?"],
    "치료": ["다음 기생충 감염의 치료로 옳은 것은?"],
    "매개질환": ["다음 생물이 매개하는 질환은?", "해당 생물이 매개하는 질병으로 적절한 것은?"],
    "숙주": ["다음 기생충의 종숙주로 옳은 것은?"],
    "진단": ["다음 기생충 감염의 진단법으로 옳은 것은?",
            "다음 기생충을 진단하는 검사로 알맞은 것은?"],
    # 아래는 기존 유형 안의 변형 — 구성비를 흔들지 않으면서 문장만 다르게 낸다
    "전파방식": ["다음 기생충의 전파 방식은?", "다음 기생충이 감염되는 방식은?"],
    "중간숙주": ["다음 기생충의 중간숙주로 옳은 것은?"],
}

# 진단법 표기가 자료마다 갈려 보기로 쓰기 전에 통일한다
DIAG_FIX = {"대변 충란": "대변검사", "대변검사": "대변검사", "소변 충란": "소변검사",
            "객담 충란": "객담검사", "혈액도말": "혈액도말검사"}

NORM = re.compile(r"[^0-9a-z가-힣]")
# 보기 값을 낱말로 가르는 구분자. 자료의 여러 값 표기(`사람·소`, `간세포 → 적혈구`,
# `대변검사 - modified acid-fast`)가 전부 여기서 갈린다.
SPLIT = re.compile(r"[·/,→\-—~()\[\]|]|\s+")
# 낱말 끝의 조사. `사람이 중간숙주가 됨`의 `사람이`를 `사람`과 같은 것으로 본다.
JOSA = ("으로", "에서", "이나", "에게", "은", "는", "이", "가", "을", "를",
        "의", "와", "과", "에", "로")


def norm(s):
    return NORM.sub("", (s or "").lower())


def strip_josa(t):
    if not re.fullmatch(r"[가-힣]+", t):
        return t
    for j in sorted(JOSA, key=len, reverse=True):
        if len(t) > len(j) + 1 and t.endswith(j):
            return t[: -len(j)]
    return t


def words(s):
    """보기 하나를 낱말 집합으로. 순서와 조사는 버린다."""
    return {w for w in (strip_josa(norm(t)) for t in SPLIT.split(s or "")) if w}


def similar(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    return len(na) > 6 and len(nb) > 6 and (na in nb or nb in na)


def contains(a, b):
    """한쪽 보기가 다른 쪽에 **포함**되는가.

    `사람` / `사람·소`, `소장` / `소장 상부`, `포낭` / `4핵성 포낭` 처럼
    한 보기가 다른 보기의 부분집합이면 채점이 성립하지 않는다 — 좁은 쪽을
    고른 사람도 틀렸다고 할 수 없기 때문이다.

    **낱말 단위로만 본다.** 글자 단위로 보면 `회충증`⊂`고래회충증`,
    `scolex`⊂`protoscolex`처럼 서로 다른 답까지 같은 것으로 묶인다.
    """
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return False
    return wa < wb or wb < wa


# ── 같은 것을 다르게 부른 말
#
# 자료가 종마다 다른 표기를 쓴다. 구충의 감염형은 `사상유충 (filariform larva,
# L3)`인데 고래회충·사상충 쪽은 같은 것을 `L3 유충`이라 적어 두었고,
# 폐포자충의 `cyst`는 대장아메바의 `포낭`과 같은 말이다. 글자도 낱말도 겹치지
# 않아 `contains`가 못 잡는데, 보기 넷 안에서 만나면 **답이 둘이 된다** —
# 구충의 감염형을 묻고 `L3 유충`을 오답으로 세워 놓은 문항이 그랬다.
#
# 표기가 통일되면 이 표는 비어도 된다. 값을 고치는 쪽이 낫지만, 자료의 표기는
# 필기본과 정리본에서 그대로 온 것이라 함부로 바꾸면 출처와 어긋난다.
ALIAS = {
    "l3유충": "감염기 유충 (L3)",
    "사상유충": "감염기 유충 (L3)",
    "포낭": "포낭 (cyst)",
    "cyst": "포낭 (cyst)",
}


def alias(text):
    """이 보기가 가리키는 것. 같은 것이면 표기가 달라도 같은 값이 나온다.

    **보기 전체를 본다.** `hydatid cyst`·`oocyst`처럼 다른 것을 가리키는
    말까지 낱말 단위로 훑으면 같은 것으로 묶여 버린다.
    """
    for key in (norm(text), norm(short(text))):
        if key in ALIAS:
            return ALIAS[key]
    return None


def conflict(a, b):
    """보기 둘을 한 문항에 나란히 놓을 수 없는가."""
    ta = alias(a)
    return (norm(a) == norm(b) or similar(a, b) or contains(a, b)
            or bool(ta and ta == alias(b)))


def clash(cand, chosen):
    """이 보기를 이미 고른 보기들 옆에 놓아도 되는가."""
    return any(conflict(cand, c) for c in chosen)


def load(n):
    return json.load(open(os.path.join(DATA, n), encoding="utf-8"))


# 앞머리가 알파벳이라고 다 약은 아니다.
#
#   PAIR   단방조충의 치료. 천자·흡인·주입·재흡인(Puncture, Aspiration,
#          Injection, Re-aspiration)을 하는 **시술**이라 삼키는 것이 아니다.
#   AIDS   「AIDS는 항레트로바이러스 치료」의 말머리. 조건을 적어 둔 것이라
#   CNS    「CNS 침범 시 + corticosteroid」처럼 떼어 내면 뜻이 없어진다.
#
# 이런 것은 원문을 그대로 둔다 — 「PAIR 복용」·「AIDS 복용」으로 나가고 있었다.
NOT_A_DRUG = {"pair", "aids", "cns"}
# 두 낱말이 한 이름인 약. 뒤를 자르면 다른 것이 되거나 반쪽이 된다.
DRUG_TAIL = r"(?:\s+(?:B|pamoate|antimonials))?"


def drug_only(text):
    """치료 보기에서 용량을 떼어 낸다. 용량까지 적으면 보기가 부자연스러워진다.

    **「복용」은 약일 때만 붙인다** (`NOT_A_DRUG`).
    """
    t = (text or "").strip()
    m = re.match(r"([A-Za-z][A-Za-z\-]+" + DRUG_TAIL + ")", t)
    if not m:
        return t
    head = m.group(1)
    if norm(head.split()[0]) in NOT_A_DRUG:
        return t
    return f"{head} 복용"


def short(text, limit=40):
    """보기로 쓸 수 있게 괄호 부연을 떼고 줄인다."""
    t = re.split(r"\s*[(（]", text or "", maxsplit=1)[0].strip(" .,")
    return t if t else (text or "")[:limit]


# 값 하나에 답이 **여럿** 적힌 자리를 가르는 구분자. 띄어 쓴 '/'만 본다 —
# 붙여 쓴 것은 `25mg/kg`·`thick/thin smear`·`IgG/IgM`처럼 한 낱말의 일부여서
# 가르면 없는 답이 생긴다.
LISTED = re.compile(r"\s+/\s+")


def listed(text):
    """'A / B'처럼 나란히 적힌 값을 낱개로. 하나뿐이면 한 개짜리 목록.

    **여기 적힌 것은 전부 정답이다.** 만손열두조충의 인체 감염형은
    `전미충 (procercoid) / 의미충 (plerocercoid)`인데, 물벼룩을 삼켜도
    개구리를 먹어도 걸리기 때문에 둘 다 맞다. `short()`는 첫 괄호에서
    자르므로 '전미충'만 남고, 남은 '의미충'이 광절열두조충 쪽에서 오답으로
    실려 나왔다 — 보기 넷 중 둘이 정답인 문항이 그렇게 만들어졌다.
    """
    return [t.strip(" .,") for t in LISTED.split(text or "") if t.strip(" .,")]


def stage_option(text):
    """감염형 보기 하나. **괄호 속 영문을 남긴다.**

    전미충·의미충·유미유충·피낭유충은 한글만 놓으면 글자 한 자로 갈리는데
    시험에서 쓰는 말은 procercoid·plerocercoid·cercaria·metacercaria 쪽이다.
    영문은 답을 알려 주는 것이 아니라 같은 말의 다른 표기여서, 남겨 두면
    보기가 무엇을 가리키는지가 분명해진다.

    **남기는 것은 영문 이름뿐이다.** `영양형 (포낭기 없음)`의 괄호는 다른
    표기가 아니라 설명이고, 옆에 `포낭`이 보기로 서 있으면 그 설명이 곧
    답이 된다.

    답이 여럿 적혀 있으면 **첫 번째만** 보기로 낸다. 나머지도 정답이므로
    오답으로는 절대 쓰지 않는다(`Generator.also_correct`).
    """
    parts = listed(text)
    if not parts:
        return short(text)
    one = parts[0]
    inside = re.search(r"[(（]([^)）]*)[)）]", one)
    return one if inside and re.search(r"[A-Za-z]", inside.group(1)) else short(one)


def unparen(options):
    """보기 넷에서 괄호를 통째로 뗀다.

    영문을 남기면 **괄호가 붙은 보기와 안 붙은 보기가 섞이는** 자리가 있다.
    `충란`·`포낭`·`영양형`처럼 자료에 영문이 없는 값이 있어서다. 넷 중
    정답 하나만 괄호가 붙어(또는 정답 하나만 안 붙어) 있으면 무엇을 묻든
    모양만 보고 고를 수 있으므로, 그때는 넷 다 한글만 남긴다.
    """
    return [short(o) for o in options]


class Generator:
    def variant_rng(self, cand):
        """사진까지 포함한 키로 난수를 고정한다.
        같은 표본·유형이라도 사진이 다르면 오답 조합이 달라진다.

        **`hash()`를 쓰면 안 된다.** 파이썬의 문자열 해시는 프로세스마다 소금이
        달라서(`PYTHONHASHSEED`) 같은 키가 매번 다른 값이 된다. 그러면 구울
        때마다 오답 조합이 바뀌고, 보기가 부딪혀 버려지는 문항도 달라져서
        **같은 자료로 구워도 문항 수가 흔들린다** — 실제로 연달아 구운 두 번이
        5,609개와 5,608개였고 문항 목록도 서로 달랐다.

        문항 번호(`build_web.question_id`)는 내용에서 뽑으므로 사라지지만 않으면
        그대로다. 그래서 흔들리는 것은 「어제 틀린 문제가 오늘 없다」로 나타난다 —
        오답노트가 가리킬 곳을 잃는다. `sha1`은 어디서 돌려도 같은 값이다.
        """
        key = f'{cand["specimen"]["id"]}|{cand["qtype"]}|{cand["correct"]}|{cand["image"]["path"]}'
        digest = hashlib.sha1(key.encode("utf-8")).digest()[:4]
        return random.Random(self.seed + int.from_bytes(digest, "big"))

    def __init__(self, seed):
        self.seed = seed
        self.rng = random.Random(seed)
        # 세트 간 중복 기록. 사진까지 넣어야 '같은 질문 다른 사진'이 새 문항으로 나온다.
        self.seen_pairs = set()
        self.species = load("species.json")
        self.specimens = load("specimens.json")
        # 빈 시야·초점 나간 사진은 문제로 쓰기 어렵다. 하위 10%를 제외한다.
        # 문제 사진은 '실습' 섹션만 쓴다. 강의록·기타 열에는 모식도와
        # 교과서 그림이 섞여 있어 시험 사진으로 적절하지 않다.
        usable = [r for r in load("images.json")
                  if r.get("quiz_usable") and r.get("section") == "실습"]
        scores = sorted(r["sharpness"] for r in usable if r.get("sharpness"))
        self.min_sharp = scores[len(scores) // 10] if scores else 0
        self.images = [r for r in usable
                       if (r.get("sharpness") or 0) >= self.min_sharp]
        self.dropped_blurry = len(usable) - len(self.images)
        # indicator 사진. 화살표가 그려진 것만 따로 잘라 라벨을 가린 것이다
        # (`scripts/extract_indicators.py`). 없으면 indicator 문항을 안 낸다.
        self.ind_images = defaultdict(list)
        ind_path = os.path.join(DATA, "indicator_images.json")
        if os.path.exists(ind_path):
            # **이쪽도 출처를 가린다.** `images.json` 은 `map_images.py` 가
            # 걸러 주지만 indicator 사진은 별도 파일이라 그 손을 안 탄다.
            # 실제실습본을 말라리아만 쓰기로 하고도 17장이 이 통로로 새어
            # 나왔다 — 거르는 자리가 둘이면 한 곳만 고쳐서는 안 걸러진다.
            from map_images import PARTIAL  # noqa: PLC0415
            groups = {s["id"]: s.get("group") for s in self.species}
            spec_sp = {x["id"]: x["species_id"] for x in self.specimens}
            for r in load("indicator_images.json"):
                keep = PARTIAL.get(r.get("source"))
                if keep is not None and groups.get(spec_sp.get(r["specimen_id"])) not in keep:
                    continue
                self.ind_images[r["specimen_id"]].append(r)
        self.glossary = load("glossary.json")
        freq = load("exam_frequency.json")

        self.sp = {s["id"]: s for s in self.species}
        self.spec = {x["id"]: x for x in self.specimens}
        self.weight = {e["id"]: e["exam_weight"] for e in freq["species"]}
        self.years = {e["id"]: e["years"] for e in freq["species"]}
        self.opt_count = {e["id"]: e["option_count"] for e in freq["species"]}

        self.by_specimen = defaultdict(list)
        for r in self.images:
            self.by_specimen[r["specimen_id"]].append(r)
        self.by_group = defaultdict(list)
        for s in self.species:
            self.by_group[s["group"]].append(s)

        self.fakes = [f["term"] for f in self.glossary.get("fake_distractors", [])]

    # ── 오답 만들기 ────────────────────────────────────────────────
    def species_distractors(self, specimen, correct, want, rnd=None):
        sid = specimen["species_id"]
        banned = set(specimen.get("exclude_distractors", [])) | {sid}
        cand = []
        for ref in specimen.get("confusable_with", []):
            target = self.spec.get(ref)
            other = target["species_id"] if target else ref
            if other not in banned and other in self.sp:
                cand.append(other)
        group = self.sp[sid]["group"]
        rest = [s["id"] for s in self.by_group[group] if s["id"] not in banned]
        rest.sort(key=lambda i: -self.opt_count.get(i, 0))
        # 족보에서 오답으로 자주 쓰인 종을 앞에 두되, 그 안에서 순서를 섞어
        # 사진마다 다른 조합이 나오게 한다
        if rnd:
            head, tail = rest[:6], rest[6:]
            rnd.shuffle(head)
            rest = head + tail
            rnd.shuffle(cand)
        out = []
        for other in cand + rest:
            name = self.sp[other]["scientific_name"]
            if clash(name, [correct] + out):
                continue
            out.append(name)
            if len(out) >= want:
                break
        return out

    def structure_distractors(self, specimen, correct, want, same_specimen=True, rnd=None):
        """same_specimen=False면 이 표본이 실제로 가진 구조물은 오답에서 뺀다."""
        own = set(specimen.get("structures", []))
        cand = [s for s in own if not similar(s, correct)] if same_specimen else []
        for ref in specimen.get("confusable_with", []):
            cand += self.spec.get(ref, {}).get("structures", [])
        cand += self.fakes
        if not same_specimen:
            # 혼동 표본에서 가져온 구조물이 이 표본에도 있을 수 있다 (operculum 등).
            # 그건 오답이 아니라 정답이므로 여기서 한 번 더 거른다.
            cand = [c for c in cand if c not in own]
        out = []
        (rnd or self.rng).shuffle(cand)
        for c in cand:
            if clash(c, [correct] + out):
                continue
            out.append(c)
            if len(out) >= want:
                break
        if len(out) < want:   # 같은 분류군 표본의 구조물로 보충
            group = self.sp[specimen["species_id"]]["group"]
            pool = [st for x in self.specimens
                    if self.sp[x["species_id"]]["group"] == group
                    for st in x.get("structures", [])
                    if same_specimen or st not in own]
            (rnd or self.rng).shuffle(pool)
            for c in pool:
                if clash(c, [correct] + out):
                    continue
                out.append(c)
                if len(out) >= want:
                    break
        return out

    def field_distractors(self, field, sid, correct, want, rnd=None, also=()):
        """같은 분류군의 다른 종에서 같은 필드 값을 가져온다.

        `also`는 **보기에 안 실렸을 뿐 정답인 값들**이다. 오답 후보가 그중
        하나와 같으면 버린다 — 안 그러면 다른 종에서 온 값이 이 문항에서도
        맞는 답인 채로 오답 자리에 앉는다.
        """
        group = self.sp[sid]["group"]
        pool = [s for s in self.by_group[group] if s["id"] != sid]
        pool += [s for s in self.species if s["id"] != sid and s["group"] != group]
        if rnd:
            same = [s for s in pool if s["group"] == group]
            rest = [s for s in pool if s["group"] != group]
            rnd.shuffle(same); rnd.shuffle(rest)
            pool = same + rest
        out = []
        for s in pool:
            v = s.get(field)
            if isinstance(v, list):
                v = v[0] if v else None
            if not v:
                continue
            v = self.option_text(field, v)
            if field == "transmission_mode" and v == "해당 없음":
                continue
            if clash(v, [correct, *also] + out):
                continue
            out.append(v)
            if len(out) >= want:
                break
        return out

    # ── 필드 값을 보기 문장으로 ────────────────────────────────────
    @staticmethod
    def option_text(field, value):
        """필드 값 하나를 보기로 쓸 문장으로 바꾼다.

        **정답도 오답도 반드시 이것을 거친다.** 한쪽만 바꾸면 넷 중 하나만
        모양이 달라져 그것이 곧 답이 된다. 예전에는 이 변환이 정답 만드는
        자리와 오답 만드는 자리에 따로 적혀 있었다.
        """
        if field == "treatment":
            return drug_only(value)
        if field == "intermediate_host":
            return re.sub(r"^제\d\s*-\s*", "", short(value))
        if field == "diagnosis":
            return DIAG_FIX.get(short(value), short(value))
        if field == "infective_stage":
            return stage_option(value)
        return short(value)

    # ── 종까지 안 갈리는 표본 ──────────────────────────────────────
    def field_value(self, sp, field):
        """`candidates()`가 정답을 만들 때 쓰는 것과 같은 변환."""
        v = sp.get(field)
        if isinstance(v, list):
            v = v[0] if v else None
        return self.option_text(field, v) if v else None

    def also_correct(self, sp, field, correct):
        """보기에는 안 실렸지만 **이 문항에서도 정답인** 값들.

        답이 여럿인 자리가 둘 있다.

        하나는 한 칸에 '/'로 나란히 적힌 값이다(`listed`) — 만손열두조충의
        감염형 `전미충 (procercoid) / 의미충 (plerocercoid)`.

        다른 하나는 **목록으로 적힌 필드**다. `vector_for`·`diagnosis`·
        `treatment`는 값이 여럿인데 첫 값만 정답으로 내보낸다. 나머지도
        맞는 답이라 오답으로 쓰면 안 된다 — 편충의 진단은 대장내시경이자
        대변검사이고(오히려 대변검사가 먼저다), 단방조충의 치료는 PAIR이자
        외과적 적출이며, 작은소피참진드기는 SFTS도 재귀열도 매개한다.

        둘 다 그중 하나만 보기로 나가므로, 나머지가 다른 종에서 오답으로
        돌아오는 길을 여기서 막는다.
        """
        v = sp.get(field)
        values = v if isinstance(v, list) else [v]
        parts = [p for value in values for p in listed(value)]
        if len(parts) < 2:
            return []
        # 낱개·줄인 것·보기 문장 셋 다 막는다. 오답이 어느 모양으로 돌아올지는
        # 필드마다 다르다 — '의미충 (plerocercoid)'은 '의미충'으로, '대변 충란'은
        # `DIAG_FIX`를 거쳐 '대변검사'로 온다.
        out = []
        for p in parts:
            out += [p, short(p), self.option_text(field, p)]
        return [x for x in dict.fromkeys(out) if x and norm(x) != norm(correct)]

    def same_across(self, x, field):
        """`answer_label`이 있는 표본에서 이 필드로 문항을 내도 되는가.

        구충란과 유무구조충란은 **사진으로 종까지 갈리지 않는다.** 그래서 정답이
        `Hookworm`, `Taenia spp.`이고 갈라지는 종은 `exclude_distractors`에 있다.

        그런데 감염형·치료 같은 종 지식 문항은 표본의 `species_id` 하나만 보고
        만들어져 왔다. 유무구조충 충란 사진에 "인체 감염형은?"을 물으면 정답이
        유구낭미충으로 나가지만 무구낭미충도 맞다 — 사진이 둘을 안 가르기 때문이다.

        그래서 갈라지는 종들이 **같은 값**을 가질 때만 낸다. 기생부위(소장)·치료·
        숙주(사람)는 통과하고, 감염경로(돼지고기/소고기)·감염형·병명은 걸린다.
        """
        if not x.get("answer_label"):
            return True
        ids = [x["species_id"]] + list(x.get("exclude_distractors", []))
        vals = set()
        for sid in ids:
            sp = self.sp.get(sid)
            if not sp:
                return False
            vals.add(norm(self.field_value(sp, field) or ""))
        return len(vals) == 1

    # ── 문항 후보 만들기 ───────────────────────────────────────────
    def candidates(self):
        out = []
        for x in self.specimens:
            imgs = self.by_specimen.get(x["id"])
            if not imgs:
                continue
            s = self.sp[x["species_id"]]
            w = self.weight.get(s["id"], 1.0)
            answer_name = x.get("answer_label") or s["scientific_name"]

            def add(qtype, correct, kind, field=None, image_filter=None,
                    stem_key=None):
                pool = [i for i in imgs if not image_filter or image_filter(i)]
                if not pool or not correct:
                    return
                # 사진이 종까지 안 가르는 표본에서는, 갈라지는 종들이 같은 답을
                # 낼 때만 종 지식 문항을 낸다.
                also = ()
                if kind == "field":
                    if not self.same_across(x, field):
                        return
                    also = self.also_correct(s, field, correct)
                for img in pool:
                    out.append({"qtype": qtype, "specimen": x, "species": s,
                                "correct": correct, "kind": kind, "field": field,
                                "also": also,
                                "image": img, "images": pool, "weight": w,
                                "stem_key": stem_key or qtype})

            if x["specimen_type"] == "충란":
                add("충란 동정", answer_name, "species")
            else:
                add("종 동정", answer_name, "species")

            if x.get("structures"):
                # ── indicator
                #
                # 예전에는 "행 라벨에 구조물 이름이 있으면 그 사진에는 화살표가
                # 그려져 있을 것"이라고 보고 냈다. **사진을 열어 보니 아니었다** —
                # 화살표가 없거나, 있어도 이름이 옆에 적혀 있어 답이 새어 나왔다.
                #
                # 지금은 화살표가 실제로 그려진 사진만 따로 잘라 이름을 가려 두고
                # (`scripts/extract_indicators.py`) 그것만 쓴다.
                own = {norm(st): st for st in x["structures"]}
                for rec in self.ind_images.get(x["id"], []):
                    st = own.get(norm(rec["structure"]))
                    if not st:
                        continue   # 이 표본에 등록되지 않은 구조물이면 오답을 못 만든다
                    out.append({"qtype": "indicator", "specimen": x, "species": s,
                                "correct": st, "kind": "structure", "field": None,
                                "image": rec, "images": [rec], "weight": w,
                                "stem_key": "indicator"})
                # 구조물을 하나만 쓰면 표본당 문항이 1개로 묶인다. 전부 낸다.
                for st in x["structures"]:
                    add("특징 구조물", st, "structure")

            # 정답도 오답과 같은 `option_text`를 거친다. 예전에는 여기에
            # 변환이 따로 적혀 있어 둘이 어긋날 수 있었다.
            def field_add(qtype, field, value, **kw):
                add(qtype, self.option_text(field, value), "field", field, **kw)

            field_add("감염경로", "source", s.get("source"))
            mode = s.get("transmission_mode")
            if mode and mode != "해당 없음":
                field_add("감염경로", "transmission_mode", mode, stem_key="전파방식")
            field_add("감염형", "infective_stage", s.get("infective_stage"))
            field_add("증상·질병", "disease_ko", s.get("disease_ko"))
            field_add("기생부위", "habitat", s.get("habitat"))
            field_add("숙주", "definitive_host", s.get("definitive_host"))
            # 중간숙주는 자료의 값이 '패류'처럼 뭉뚱그려져 있어
            # '쇠우렁'과 상하위 관계가 되므로 문항으로 쓰지 않는다.
            #
            # 아래 셋은 값이 **목록**이다. 첫 값만 정답으로 내보내고 나머지는
            # `also_correct`가 오답에서 막는다 — 나머지도 맞는 답이다.
            if s.get("diagnosis"):
                field_add("진단", "diagnosis", s["diagnosis"][0])
            if s.get("treatment"):
                field_add("치료", "treatment", s["treatment"][0])
            if s.get("vector_for"):
                field_add("매개질환", "vector_for", s["vector_for"][0])
        return out

    # ── 한 문항 완성 ──────────────────────────────────────────────
    def build(self, cand, no, set_no):
        x, s = cand["specimen"], cand["species"]
        correct = cand["correct"]
        vr = self.variant_rng(cand)
        if cand["kind"] == "species":
            distractors = self.species_distractors(x, correct, 3, rnd=vr)
        elif cand["kind"] == "structure":
            # indicator는 화살표가 하나를 짚어주므로 같은 표본의 다른 구조물도 오답이 된다.
            # '특징 구조물'은 그렇지 않다 — 이 표본이 가진 구조물은 전부 정답이기 때문.
            distractors = self.structure_distractors(
                x, correct, 3, same_specimen=(cand["qtype"] == "indicator"), rnd=vr)
        else:
            distractors = self.field_distractors(cand["field"], s["id"], correct, 3,
                                                 rnd=vr, also=cand.get("also") or ())
        if len(distractors) < 3:
            return None

        options = distractors[:3] + [correct]
        # 괄호가 정답 하나만 갈라 놓으면 넷 다 뗀다 (`unparen`). 답을 아는
        # 것과 상관없이 모양만으로 고를 수 있는 자리가 그렇게 생긴다.
        has = [bool(re.search(r"[(（]", o)) for o in options]
        if has.count(has[-1]) == 1:
            options = unparen(options)
            correct = options[-1]
        # 안전망. 위에서 걸렀어도 오답끼리 포함관계가 생길 수 있다 —
        # 정답이 안 끼어도 보기 넷 중 둘이 상하위면 문항으로 내지 않는다.
        for i in range(len(options)):
            for j in range(i + 1, len(options)):
                if conflict(options[i], options[j]):
                    return None
        vr.shuffle(options)
        # 실습 사진 우선, 그다음 선명한 것 우선
        img = cand["image"]
        stem = vr.choice(STEMS[cand.get("stem_key") or cand["qtype"]])
        if x["specimen_type"] == "충란" and cand["qtype"] in (
                "감염경로", "감염형", "증상·질병", "기생부위", "숙주", "치료", "진단"):
            if "기생충의 " in stem:
                stem = "다음 충란을 가지는 기생충의 " + stem.split("기생충의 ", 1)[1]
            else:
                stem = stem.replace("다음 기생충", "다음 충란을 가지는 기생충", 1)
        why = " / ".join(x.get("key_features", [])[:2])
        expl = f"{x['label_ko']} — {why}" if why else x["label_ko"]
        # 사진 감별점만 적으면 왜 그 답인지가 빠진다. 유형별 근거를 한 줄 덧붙인다.
        reason = {
            "감염경로": lambda: f"{s['name_ko']}은(는) {s.get('transmission_route','')}으로 감염되며, 감염원은 {s.get('source','')}이다.",
            "감염형": lambda: f"{s['name_ko']}의 인체 감염형은 {s.get('infective_stage','')}이다.",
            "증상·질병": lambda: f"{s['name_ko']} 감염증의 병명은 {s.get('disease_ko','')} ({s.get('disease_en','')})이다.",
            "기생부위": lambda: f"{s['name_ko']} 성충은 {s.get('habitat','')}에 기생한다.",
            "숙주": lambda: f"{s['name_ko']}의 종숙주는 {s.get('definitive_host','')}이다.",
            "치료": lambda: f"{s['name_ko']} 치료: {', '.join(s.get('treatment', [])[:2])}",
            "매개질환": lambda: f"{s['name_ko']}은(는) {', '.join(s.get('vector_for', []))}을(를) 매개한다.",
            "진단": lambda: f"{s['name_ko']} 진단: {', '.join(s.get('diagnosis', [])[:2])}",
            "전파방식": lambda: f"{s['name_ko']}의 전파 방식은 {s.get('transmission_mode','')}이다.",
            "중간숙주": lambda: f"{s['name_ko']}의 중간숙주는 {', '.join(s.get('intermediate_host', []))}이다.",
        }.get(cand.get("stem_key") or cand["qtype"])
        if reason:
            expl += "\n" + reason()
        if x.get("note"):
            expl += "\n" + x["note"]
        if s.get("exam_notes"):
            expl += f"\n출제 포인트: {s['exam_notes']}"

        return {
            "quiz_id": f"set{set_no}_q{no:02d}",
            "set": set_no, "no": no,
            "qtype": cand["qtype"],
            "stem": stem,
            "image_path": img["path"],
            "image_source": img["source"],
            "stain": x.get("stain"),
            "magnification": x.get("magnification"),
            "options": options,
            "answer_index": options.index(correct),
            "answer": correct,
            "explanation": expl,
            "species_id": s["id"],
            "specimen_id": x["id"],
            "group": s["group"],
            "exam_weight": cand["weight"],
            "past_years": self.years.get(s["id"], []),
        }

    # ── 한 세트 조립 ──────────────────────────────────────────────
    def make_set(self, cands, n, set_no):
        want_q = {k: max(1, round(v * n)) for k, v in QTYPE_MIX.items()}
        want_g = {k: max(1, round(v * n)) for k, v in GROUP_MIX.items()}
        used_spec, used_sp = set(), Counter()
        picked = []

        pools = defaultdict(list)
        for c in cands:
            pools[c["qtype"]].append(c)

        order = sorted(want_q, key=lambda k: -want_q[k])
        guard = 0
        while len(picked) < n and guard < n * 60:
            guard += 1
            qt = next((k for k in order if want_q[k] > 0), None)
            if qt is None:
                want_q = {k: max(1, round(v * n)) for k, v in QTYPE_MIX.items()}
                continue
            def ok(c, allow_repeat):
                if c["specimen"]["id"] in used_spec:
                    return False
                if used_sp[c["species"]["id"]] >= 2:
                    return False
                if not allow_repeat and (
                        c["specimen"]["id"], qt, c["image"]["path"]) in self.seen_pairs:
                    return False
                return (want_g.get(c["species"]["group"], 0) > 0
                        or sum(want_g.values()) <= 0)
            # 앞선 세트에 이미 낸 조합은 후순위로 미룬다
            pool = [c for c in pools.get(qt, []) if ok(c, False)]
            if not pool:
                pool = [c for c in pools.get(qt, []) if ok(c, True)]
            if not pool:
                if qt == "indicator" and pools.get("특징 구조물"):
                    pool = [c for c in pools["특징 구조물"]
                            if c["specimen"]["id"] not in used_spec
                            and used_sp[c["species"]["id"]] < 2]
                if not pool:
                    want_q[qt] = 0
                    continue
            weights = [c["weight"] for c in pool]
            cand = self.rng.choices(pool, weights=weights, k=1)[0]
            q = self.build(cand, len(picked) + 1, set_no)
            if not q:
                pool.remove(cand)
                continue
            picked.append(q)
            self.seen_pairs.add(
                (cand["specimen"]["id"], qt, cand["image"]["path"]))
            used_spec.add(cand["specimen"]["id"])
            used_sp[cand["species"]["id"]] += 1
            want_q[qt] -= 1
            g = cand["species"]["group"]
            want_g[g] = want_g.get(g, 0) - 1

        # 족보를 보면 충란은 앞쪽에 몰리지만 분류군 순으로 정렬되지는 않는다.
        # 그래서 충란 블록만 앞으로 빼고 나머지는 섞는다.
        eggs = [q for q in picked if self.spec[q["specimen_id"]]["specimen_type"] == "충란"]
        rest = [q for q in picked if self.spec[q["specimen_id"]]["specimen_type"] != "충란"]
        self.rng.shuffle(eggs)
        self.rng.shuffle(rest)
        picked = eggs + rest
        for i, q in enumerate(picked, 1):
            q["no"] = i
            q["quiz_id"] = f"set{set_no}_q{i:02d}"
        return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", type=int, default=5)
    ap.add_argument("--questions", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20260906)
    args = ap.parse_args()

    gen = Generator(args.seed)
    cands = gen.candidates()
    print(f"사용 사진 {len(gen.images)}장 (실습 사진만, 흐린 사진 {gen.dropped_blurry}장 제외, "
          f"기준 선명도 {gen.min_sharp})")
    print(f"문항 후보 {len(cands)}개 (표본 {len({c['specimen']['id'] for c in cands})}건)")
    print("─ 유형별 후보 수")
    for k, v in Counter(c["qtype"] for c in cands).most_common():
        print(f"    {k:12s} {v:4d}")
    print()

    exams = []
    for i in range(1, args.sets + 1):
        qs = gen.make_set(cands, args.questions, i)
        exams.append({"set": i, "questions": qs})
        c = Counter(q["qtype"] for q in qs)
        g = Counter(q["group"] for q in qs)
        print(f"세트 {i}: {len(qs)}문항  유형 {dict(c)}")
        print(f"         분류군 {dict(g)}")

    with open(os.path.join(DATA, "generated_exams.json"), "w", encoding="utf-8") as fh:
        json.dump({"seed": args.seed, "exams": exams}, fh, ensure_ascii=False, indent=2)

    lines = []
    for ex in exams:
        lines.append(f"{'='*70}\n모의 땡시 {ex['set']}세트  ({len(ex['questions'])}문항)\n{'='*70}")
        for q in ex["questions"]:
            lines.append(f"\n{q['no']:2d}. [{q['qtype']}] {q['stem']}")
            lines.append(f"    사진: {q['image_path']}")
            for i, o in enumerate(q["options"]):
                lines.append(f"     {'①②③④'[i]} {o}{'   <== 정답' if i == q['answer_index'] else ''}")
            for ln in q["explanation"].splitlines():
                lines.append(f"    해설: {ln}" if ln == q["explanation"].splitlines()[0] else f"          {ln}")
    with open(os.path.join(DATA, "generated_preview.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"\ndata/generated_exams.json, data/generated_preview.txt 생성")


if __name__ == "__main__":
    main()
