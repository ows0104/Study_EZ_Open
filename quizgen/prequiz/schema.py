"""예습 퀴즈의 공용 계약.

복습 덱(`quizgen.schema`)과 **일부러** 다른 파일이다. 두 덱의 목적 함수가 다르기 때문이다.

    복습(quiz)  — 시험에 나올 수 있는 것
    예습(prequiz) — 이 강의에서 꼭 반드시 알아야 하는 것

예습의 목적은 수업 중에 「저 단어가 뭐지? 저 약어가 뭐지? 저 기전이 뭐지?」로
막히지 않게 하고, 「오 이거 어제 외웠던 거다」를 만드는 것이다. 흥미를 유발하고
학습에 장애물이 없게 하는 것이 목표이며, 강의를 따라가는 것은 그 수단이다.

축이 다르니 계약도 다르다 —
  · `trap`(함정) 유형이 없다. 수업 전날 함정은 장애물을 하나 더 세우는 것이다.
  · `importance` 축이 없다. 예습 덱은 **전부** '꼭 반드시'다. 등급이 있으면 축이 흐려진다.
  · 대신 **개수 상한이 계약이다.** 상한을 넘기는 순간 '꼭 반드시'가 아니게 된다.

사용:
    python -m quizgen.prequiz.schema -o out/prequiz_schema
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 기계 검사의 임계값. **계약에 실려야 하는 값이다** —
# 싣지 않으면 모델이 `validate.py` 소스를 뒤져서 알아낸다 (실제로 그랬다).
from ..validate import LEAK_THRESHOLD, MAX_Q_CHARS, SIMILAR_CROSS_SLIDE, SIMILAR_SAME_SLIDE

# ─────────────────────────────────────────────────────────────── enum

CARD_FORMATS = ("basic", "cloze", "ox", "image_basic", "image_occlusion")

# 유형은 목적에서 역산했다. 왼쪽이 카드, 오른쪽이 그 카드가 수업 중에 막는 것.
CARD_TYPES = ("term", "abbrev", "mechanism", "taxonomy", "clinical", "number",
              "comparison", "sequence")
CARD_TYPE_WHY = {
    "term": "「저 단어가 뭐지」 — 강의 내내 쓰일 말의 뜻",
    "abbrev": "「저 약어가 뭐지」 — 풀어 쓴 이름과 무엇인지",
    "mechanism": "「저 기전이 뭐지」 — 뼈대만. 세부 단계는 복습 덱 소관이다",
    "taxonomy": "「이게 뭐의 하위지」 — 분류 축 하나",
    "clinical": "「이걸 왜 배우지」 — 이 개념이 실제로 무엇을 설명하는가",
    "number": "강의 중 기준으로 반복될 수치 (재태 주수·컷오프 등)",
    "comparison": "나란히 놓고 들어야 구분되는 두 가지",
    "sequence": "순서가 곧 내용인 것",
}

# 왜 이것이 '꼭 반드시'인가. 학습목표(must_know.json)와 카드가 같은 말을 쓴다.
REASONS = ("spine", "vocabulary", "mechanism", "clinical", "repeated")
REASON_WHY = {
    "spine": "강의의 뼈대. 이걸 모르면 뒤따르는 것이 안 붙는다",
    "vocabulary": "용어·약어. 모르면 문장 자체가 안 들린다",
    "mechanism": "이 강의가 설명하려는 핵심 기전",
    "clinical": "임상적·의학적으로 중요해서 이 강의가 존재하는 이유",
    "repeated": "여러 해 반복 출제됐다 — **담당 교수가 유임일 때만** 쓸 수 있다",
}

# 이 항목이 **왜 중요한가**의 근거 — 학생에게 보일 「왜 냈나」의 재료다(2026-10-04).
#
# `reason` 과 `why` 는 「모르면 수업에서 무엇이 막히는가」를 말한다 — 고르는 기준이다.
# 이것은 그 위에 **이 항목을 중요하게 들어야 하는 사실**을 적는다. ① 단계가 자료를 다
# 읽은 채로 모으고 ② 단계는 여기서 뽑는다. ② 에서 새로 지으면 근거 없는 이유가
# 끼어들 자리가 생긴다 — 그 자리를 줄이려고 한 단계 앞으로 옮겼다.
SIGNAL_KINDS = ("exam", "annotation", "clinical", "later")
SIGNAL_WHY = {
    "exam": "기출에 나왔다 — `ref` 에 문항(예: '2025-19')",
    "annotation": "작년 필기가 강조했다 — `ref` 에 슬라이드(예: 's12')",
    "clinical": "임상에서 무엇을 가르거나 설명하는 데 쓰인다",
    "later": "강의 뒤쪽이나 다른 강의·과목에서 다시 쓰인다",
}

SOURCE_TYPES = ("lecture", "annotation", "note", "jokbo")
EVIDENCE_TYPES = (
    "lecture_text",      # 작년 강의록 본문
    "lecture_figure",    # 작년 강의록 표·그림의 명시적 라벨/축/범례
    "annotation",        # 작년 필기. 예습에서는 근거로 쓸 수 있다 (아래 주석 참고)
    "preview_note",      # 예습 설명본
    "jokbo_question",    # 기출 문항 원문
    "jokbo_objection",   # 이의제기에 대한 교수 답변
)
IMAGE_FORMATS = ("image_basic", "image_occlusion")

REJECT_REASONS = (
    "not_must_know",     # 알면 좋지만 이걸 몰라도 수업이 막히지 않는다
    "exam_only",         # 시험에는 나오지만 수업을 따라가는 데는 필요 없다 → 복습 덱 소관
    "too_detailed",      # 예습 단계에서 외울 것이 아니다
    "obvious",           # 이미 아는 것
    "out_of_scope",      # 이 강의가 다루지 않는다 (다음 강의 소관 등)
    "unsupported",       # 자료 어디에도 근거가 없다
    "duplicate",
)
# out_of_scope 와 unsupported 는 다르다. 앞은 '이 강의의 범위가 아니다'(다음 시간에 한다),
# 뒤는 '아무 자료에도 없다'(모델이 지어냈을 수 있다)이다. 코드를 하나로 두면 둘이 섞여
# **자료 결함을 못 본다** — 실제로 분자생물학(1)에서 p53·Warburg 등 6건이 다음 강의
# 소관인데 unsupported 로 찍혔다. 그 상태로는 진짜 unsupported 가 나와도 묻힌다.

# 덱 크기. **이것이 품질 장치다.**
#
# 상한이 없으면 "꼭 반드시"가 슬그머니 "알면 좋은"으로 넘어간다. 실제로 복습 덱은
# 한 강의가 77장까지 갔다. 예습은 강의 전날 한 번에 끝나야 하고, 상한을 넘는 순간
# 사용자가 막으려던 바로 그 느낌 — 「외워야 될 게 너무 많은데?」 — 을 예습이 만든다.
#
# **2026-09-03 에 관리자가 상한을 30 에서 20 으로 내렸다** — 「지금 약간 부담돼」.
# **2026-10-04 에 다시 15 로 내렸다** — 「15개 정도? (필수는 아님)」. 같은 날
# 도전 문제(`challenge`)가 생겼는데, 그것도 이 15 장 안에 든다.
# 하한 10 도 관리자가 정한 값이다. 짐작으로 바꾸지 마라.
#
# 하한을 상한 바로 밑에 두지 않은 이유가 있다. 모델은 상한을 목표로 읽는다 — 상한
# 30 일 때 31 편이 전부 24~29 장이었고, 20 으로 내린 뒤 79 편 중 19~20 장이 32 편으로
# 가장 많았다. 그러니 실제 산출은 15 장 근처가 될 것이고, 하한은 「몇 장 모자란 편을
# 빌드가 거부하고 수선 고리를 한 번 더 돌리는 일」을 막는 자리로만 선다.
MIN_CARDS, MAX_CARDS = 10, 15

# 도전 문제 상한. 2026-10-04 관리자 — 「흥미를 유발할 정도의 중요하지만 어려운 문제도
# 한 두개 쯤 넣어 봐도 좋을듯. 도전문제! 해서」. 「한 두개」를 상한으로 옮겼다.
# 0 장도 계약 위반이 아니다 — 「넣어 봐도 좋을듯」이라 하한은 두지 않았다.
MAX_CHALLENGE = 2

# 「왜 냈나」 한 줄의 길이. 앞면에 질문 위로 뜨므로 질문보다 길면 질문을 가린다.
# 실측이 아니라 화면 한 줄(모바일 약 30자 × 2줄)에서 잡은 값이라 넘으면 표시만 단다.
MAX_WHY_CHARS = 60

# 「왜 냈나」의 유형 — 앞면에 배지로 뜬다(2026-10-04 관리자 「유형별로 정리해서 뱃지를」).
#
# 배지가 유형을 말하므로 글은 배지를 되풀이하지 않아도 된다. 그 덕에 기출 근거는
# 배지로 남기고 글에는 다른 근거(임상 · 뒤에서 또)를 쓸 수 있다 — 시험판(내분비 약리
# 기초 · 15장)에서 7장의 글이 「20XX 기출이 ~를 물었다」로 시작해 족보 연습처럼 읽혔다.
#
# 넷은 `SIGNAL_KINDS` 그대로고 `basis` 하나가 더 있다 — 근거(`signals`)가 빈 항목은
# 「모르면 수업에서 무엇이 막히는가」(`why`)를 옮기는데, 그 유형이다.
WHY_TAGS = (*SIGNAL_KINDS, "basis")
# 학생에게 보이는 이름. 웹(`web/src/lecture/Quiz.tsx` 의 `WHY_TAG_LABEL`)과 같아야 한다 —
# 웹은 이 폴더를 import 하지 않는다. 바꾸면 둘 다 바꾼다.
WHY_TAG_LABEL = {
    "exam": "기출",
    "clinical": "임상",
    "later": "연결 개념",  # 2026-10-05 「또 나옴」 → 관리자 「이름이 너무 별로」
    "annotation": "필기 강조",
    "basis": "기본 개념",
}
# 2 였다가 3 으로 올렸다(같은 날). 2 일 때 배지를 「글이 말하는 이유의 유형」으로 고르게
# 했더니, 글이 기출 아닌 이유를 쓰면 기출 배지가 밀려났다 — 6편에서 기출 근거가 있는
# 항목의 카드 16장이 기출 배지 없이 나갔다. 지금은 기출 배지를 코드가 채운다(`validate`).
MAX_WHY_TAGS = 3

# 「왜 냈나」가 기출을 말하는가. 말하면 그 문항(`jokbo_ref`)을 같이 적어야 한다.
WHY_CITES_EXAM = ("기출", "족보", "시험에 나왔", "출제")

# 한 카드가 한 번에 회수시킬 항목 수 상한. 복습(6)보다 낮다 —
# 예습 카드는 하루 만에 외워져야 한다.
MAX_RECALL_ITEMS = 4

# O/X 가 차지할 수 있는 비율. 예습은 알게 하는 것이 목적이라 회수량이 적은 형식이다.
OX_SHARE_MAX = 0.20

CARD_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "PrequizCard",
    "type": "object",
    "additionalProperties": False,
    "required": ["q", "a", "card_format", "card_type", "reason",
                 "source_type", "evidence_type"],
    "properties": {
        "id": {"type": ["string", "null"],
               "description": "비워 둘 것. 코드가 부여한다."},
        "q": {"type": "string", "minLength": 1,
              "description": "질문. cloze 는 {{c1::...}} 를 포함한 문장."},
        "a": {"type": "string", "minLength": 1,
              "description": "회수 대상을 담는다. 회수 대상이 아닌 부연은 explanation 으로."},
        "explanation": {"type": ["string", "null"],
                        "description": "왜 이 답인지. q/a 의 근거가 되어서는 안 된다. "
                                       "예습 카드에서는 **수업에서 이것이 어디에 쓰이는지**를 "
                                       "한 줄 붙이면 좋다."},
        "slide_no": {"type": ["integer", "null"], "minimum": 1,
                     "description": "작년 강의록의 슬라이드 번호. source_type=lecture/annotation 이면 필수."},
        "card_format": {"enum": list(CARD_FORMATS)},
        "card_type": {"enum": list(CARD_TYPES)},
        "reason": {"enum": list(REASONS),
                   "description": "왜 이것이 '꼭 반드시'인가. must_know 의 같은 항목과 일치해야 한다."},
        "source_type": {"enum": list(SOURCE_TYPES)},
        "evidence_type": {"enum": list(EVIDENCE_TYPES)},
        "jokbo_ref": {
            "type": ["object", "null"], "additionalProperties": False,
            "required": ["year", "no"],
            "properties": {"year": {"type": "string"}, "no": {"type": "string"}},
            "description": "reason=repeated 의 근거가 된 문항, 또는 why_asked 가 기출을 "
                           "말할 때 그 문항. 그 밖에는 비운다.",
        },
        "media": {
            "type": ["object", "null"], "additionalProperties": False,
            "required": ["figure_id"],
            "properties": {
                "figure_id": {"type": "string",
                              "description": "prep.json 의 lecture_figures[].id (fig_pNN_MM)"},
                "occlusion_ids": {"type": "array", "items": {"type": "string"}},
                "reveal_all": {"type": "boolean"},
                "crop": {"type": "array", "items": {"type": "number", "minimum": 0, "maximum": 1},
                         "minItems": 4, "maxItems": 4,
                         "description": "그림 안에서 다시 자를 구간 [x0,y0,x1,y1] (비율). "
                                        "캡션이 정답을 흘릴 때 쓴다. 예: 아래 25% 를 잘라내려면 [0,0,1,0.75]"},
            },
            "description": "image_basic / image_occlusion 에서만 채운다.",
        },
        "review_note": {"type": ["string", "null"],
                        "description": "사용자에게 보일 경고. 없으면 null."},
        # 2026-10-04 관리자 — 생소한 문제를 본 학생이 「이것까지 알아야 하나? 과한 거
        # 아니야?」 싶지 않게 **이 문제를 왜 냈는지** 알려 준다. 앞면에는 유형 배지
        # (`why_tags`)만 뜨고 이 글은 답을 편 뒤에 보인다(같은 날 관리자).
        "why_asked": {"type": ["string", "null"],
                      "description": f"학생이 답을 편 뒤 보는 한 줄 — **왜 이 문제를 "
                                     f"냈나.** {MAX_WHY_CHARS}자 이하."},
        "why_tags": {"type": "array", "maxItems": MAX_WHY_TAGS,
                     "items": {"enum": list(WHY_TAGS)},
                     "description": "why_asked 의 유형. 앞면에 배지로 뜬다. 항목의 signals 에 "
                                    "있는 kind 만 쓰고, signals 가 비어 why 를 옮겼으면 basis."},
        "challenge": {"type": "boolean",
                      "description": f"도전 문제면 true. 한 덱에 {MAX_CHALLENGE}장 이하."},
        # **이 카드가 어느 must-know 항목을 위한 것인가.** 승인본의 `items[].id` 를 적는다.
        # 이 끈이 없으면 「승인한 항목에 카드가 갔는가」도 「항목에 배정한 수를 지켰는가」도
        # 글자 유사도로 추측해야 한다 — 실측에서 문턱 0.05~0.20 사이에 미달 항목이
        # 8%~72% 로 흔들렸다. 2026-08-30 이전에 만든 편에는 없으므로 필수가 아니다.
        "must_id": {"type": ["string", "null"],
                    "description": "이 카드가 옮긴 must-know 항목의 id (예: 'm03'). "
                                   "승인본에 있는 것만 쓰고 지어내지 않는다."},
    },
}

MUST_KNOW_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "MustKnow",
    "type": "object",
    "additionalProperties": False,
    "required": ["items"],
    "properties": {
        "items": {
            # 상한은 카드 수 상한을 따라간다. 항목 하나에 카드가 최소 한 장이라
            # 항목이 카드보다 많으면 배정이 성립하지 않는다 — 25 로 굳어 있던 동안
            # 카드 상한이 20 으로 내려오면서 그 자리가 어긋났다.
            "type": "array", "minItems": 8, "maxItems": MAX_CARDS,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["item", "reason", "why", "slides"],
                "properties": {
                    # 승인할 때 `run.py` 가 코드로 찍는다. 모델이 짓지 않는다 — 편마다
                    # 정확히 한 번 도는 자리라야 이미 나간 카드의 `must_id` 가 안 어긋난다.
                    "id": {"type": ["string", "null"]},
                    "item": {"type": "string",
                             "description": "반드시 알아야 할 것 하나. 명사구로 쓴다."},
                    "reason": {"enum": list(REASONS)},
                    "why": {"type": "string", "minLength": 1,
                            "description": "**이걸 모르면 수업에서 무엇이 막히는가**를 한 줄로. "
                                           "'중요하다'는 이유가 아니다."},
                    "slides": {"type": "array", "items": {"type": "integer", "minimum": 1}},
                    "jokbo_refs": {"type": "array", "items": {"type": "string"},
                                   "description": "reason=repeated 의 근거 (예: '2025-19')"},
                    "signals": {
                        "type": "array",
                        "items": {
                            "type": "object", "additionalProperties": False,
                            "required": ["kind", "detail"],
                            "properties": {
                                "kind": {"enum": list(SIGNAL_KINDS)},
                                "detail": {"type": "string", "minLength": 1,
                                           "description": "자료에서 확인한 사실 한 줄"},
                                "ref": {"type": ["string", "null"],
                                        "description": "exam 이면 기출 문항, annotation 이면 슬라이드"},
                            },
                        },
                        "description": "이 항목을 중요하게 들어야 하는 근거. 카드의 why_asked 가 "
                                       "여기서 나온다. 자료에서 확인되는 것만 — 없으면 비운다.",
                    },
                    "cards": {"type": "integer", "minimum": 1, "maximum": 3,
                              "description": f"이 항목에 배정할 카드 수. "
                                             f"합이 {MIN_CARDS}~{MAX_CARDS} 이어야 한다."},
                },
            },
        },
        "rejected_candidates": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["candidate", "reason"],
                "properties": {
                    "candidate": {"type": "string"},
                    "reason": {"enum": list(REJECT_REASONS)},
                },
            },
            "description": "봤지만 예습에 넣지 않은 것. 누락과 의도적 제외를 가르는 흔적이며, "
                           "`exam_only` 로 걸린 것은 복습 덱이 가져갈 몫이다.",
        },
    },
}

GENERATE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "PrequizOutput",
    "type": "object",
    "additionalProperties": False,
    "required": ["cards"],
    "properties": {
        "must_know": MUST_KNOW_SCHEMA,
        "cards": {"type": "array", "minItems": MIN_CARDS, "maxItems": MAX_CARDS,
                  "items": CARD_SCHEMA},
    },
}

FORMAT_RULES = {
    "basic": "q 는 질문문, a 는 핵심 정답. 이유·조건·부연은 a 가 아니라 explanation 에 둔다. "
             "**기본형이다.** 질문 하나로 무엇을 묻는지 세울 수 있으면 이 형식이다 — 답이 "
             "하나든 목록이든 질문이 그 답을 닫아 주기만 하면 된다. media 는 null.",
    "cloze": "q 에 {{c1::...}} 가 하나 이상. **번호는 언제나 c1 하나만 쓴다** — 빈칸이 "
             "여럿이어도 전부 c1 이고, 한 노트가 카드 한 장이다. a 는 가려진 내용을 모은 것. "
             "media 는 null. 가린 말이 같은 문장 다른 자리에 맨몸으로 또 나오면 안 된다 — "
             "같은 말이 두 번 필요하면 두 자리를 함께 가린다. "
             "**긴 문장에서 핵심만 회상하게 하는 형식이다.** 회수할 핵심이 여럿인데 "
             "그 문장이 있어야 무엇을 묻는지 서는 자리에 쓴다. 문장이 길다고 쓰는 것이 아니다. "
             "세거나 나열하는 것은 문장이 하는 일이 없으므로 basic 이다.",
    "ox": "q 는 진술문, a 는 'O' 또는 'X'. 틀린 진술이면 explanation 에 왜 틀렸는지 적는다.",
    "image_basic": "media.figure_id 필수. 앞면에 그림을 붙이고 무엇인지 묻는다.",
    "image_occlusion": "media.figure_id 와 media.occlusion_ids 필수. 이름 있는 must-know 라벨만 "
                       "선택하며 가린 원문 라벨이 a 에 들어 있어야 한다. 자료가 제공한 한국어·영어 "
                       "대응 표기는 고정된 병기로 함께 쓸 수 있으나 q 에 노출하지 않는다.",
}


def dump(outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    for name, obj in (("card.schema.json", CARD_SCHEMA),
                      ("must_know.schema.json", MUST_KNOW_SCHEMA),
                      ("generate.schema.json", GENERATE_SCHEMA)):
        (outdir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    lines = ["# 출력 계약 (예습)", "",
             "아래 JSON Schema 를 그대로 지킨다. 모르는 키를 추가하지 않는다.", "",
             "```json", json.dumps(GENERATE_SCHEMA, ensure_ascii=False, indent=2), "```", "",
             "## `card_type` — **카드에만 있는 축.** 각 유형이 수업 중에 막는 것", ""]
    lines += [f"- `{k}` — {v}" for k, v in CARD_TYPE_WHY.items()]
    lines += ["", "## `reason` — 왜 이것이 '꼭 반드시'인가. 카드와 must_know 항목이 같이 쓴다", ""]
    lines += [f"- `{k}` — {v}" for k, v in REASON_WHY.items()]
    # 두 목록이 이 문서에서 나란히 서 있고 값이 둘 겹친다. 겹치는 자리에서는 스키마가
    # 못 잡으니 여기서 가른다 — 아래 두 실패는 겹치지 않는 값이라 잡힌 것뿐이다.
    lines += ["",
              f"**두 축은 값을 섞어 쓰지 않는다.** `card_type` 전용 값"
              f"(`{'`·`'.join(k for k in CARD_TYPES if k not in REASONS)}`)을 `reason` 에 적지 "
              f"마라. 약어 항목이라도 `reason` 은 `abbrev` 가 아니라 `vocabulary` 이고, 분류 축이 "
              f"강의의 뼈대면 `taxonomy` 가 아니라 `spine` 이다.",
              f"**`{'`·`'.join(sorted(set(CARD_TYPES) & set(REASONS)))}` 는 두 축에 다 있다.** "
              f"이 둘은 값만 보고는 어느 축에서 온 것인지 알 수 없어 코드가 잡아 주지 못한다. "
              f"카드의 생김새가 아니라 **왜 이것이 '꼭 반드시'인가**를 보고 골라라.",
              "(실측 — 병리학 `250825_03` 에서 카드 한 장이 `reason` 에 `taxonomy` 를 적어 "
              "스키마에서 버려졌고, 2026-08-31 에 기생충학 두 편이 `abbrev`·`taxonomy` 로 "
              "① 에서 멈췄다.)"]
    lines += ["", "## `signals` — must_know 항목이 왜 중요한가의 근거. 카드의 `why_asked` 재료", ""]
    lines += [f"- `{k}` — {v}" for k, v in SIGNAL_WHY.items()]
    lines += ["", "`signals` 의 `clinical` 은 `reason=clinical` 과 다르다 — `reason` 은 고른 까닭, "
              "`signals` 는 학생에게 보일 근거다. 한 항목에 둘 다 있어도 된다."]
    lines += ["", "## 형식별 추가 규칙", ""]
    lines += [f"- `{k}` — {v}" for k, v in FORMAT_RULES.items()]
    lines += ["",
              f"- **카드는 {MIN_CARDS}~{MAX_CARDS}장이다.** 이것은 권고가 아니라 계약이며 "
              f"코드가 검사한다. 넘치면 넘치는 것이 '꼭 반드시'가 아니었다는 뜻이다.",
              f"- 목록·순서를 묻는 카드는 한 장에 {MAX_RECALL_ITEMS}개를 넘기지 않는다. "
              "예습 카드는 하루 만에 외워져야 한다.",
              "- **`a` 의 항목이 둘 이상이면 줄바꿈과 `- ` 로 나눈다.** 범주와 내용은 `:` 로 "
              "가르고 `—` 는 쓰지 않는다.",
              "- **`must_id` 에 이 카드가 옮긴 항목의 `id` 를 적는다.** 승인본 "
              "`must_know.approved.json` 의 `items[].id`(`m03` 꼴)를 그대로 쓴다. "
              "지어내지 않는다. 어느 항목에도 안 붙는 카드라면 그 카드는 만들지 않는다.",
              "- `reason=repeated` 는 **담당 교수가 유임일 때만** 쓸 수 있다. "
              "교수가 바뀐 강의에서는 과거 반복이 이 강의의 중심을 뜻하지 않는다.",
              # 2026-10-05 내분비 약리 기초 — 「왜 냈나」 한국어 규칙을 넣은 판이 15장 전부에서
              # 「TZD 가」·「receptor 는」으로 띄웠다. 바로 앞 판(같은 강의)은 0장이었다. 이 문서가
              # 「`exam` 은」처럼 코드 이름 뒤를 띄워 적는 것을 옮긴 것으로 보인다(원인은 안 쟀다).
              "- **영어 낱말 뒤의 조사는 붙여 쓴다** — `TZD가`·`receptor는`·`metformin과`. "
              "`TZD 가` 처럼 띄우지 않는다. 질문·답·해설·`why_asked` 모두 학생이 읽는 글이다. "
              "(이 문서가 코드 이름 뒤를 띄워 적는 것은 문서의 표기일 뿐이다.)",
              "- 카드 앞면에 선지·연도·문항 번호가 나와서는 안 된다. "
              "(`why_asked` 의 「20XX 기출」은 예외다 — 질문이 아니라 출제 이유다.)",
              "",
              "## `why_asked` — 왜 이 문제를 냈나 (앞면에는 배지, 글은 답 뒤)",
              "",
              "생소한 문제를 본 학생이 「이것까지 알아야 하나? 과한 거 아니야?」 싶지 않게 "
              "**이 문제를 낸 이유를 학생에게** 한 줄로 말한다. 앞면에는 `why_tags` 배지만 "
              "뜨고, 이 글은 **답을 편 뒤** 답 아래에 보인다. 그래서 답을 말해도 된다.",
              "",
              "- **승인본에서 그 카드의 항목(`must_id`)이 든 `signals` 에서 뽑는다.** 거기 없는 "
              "이유를 새로 짓지 않는다. `signals` 가 비었으면 항목의 `why`(모르면 수업에서 "
              "무엇이 막히는가)를 학생에게 하는 말로 옮긴다.",
              "- `exam` 근거를 쓰면 그 `ref` 를 카드의 `jokbo_ref` 에 옮겨 적는다.",
              f"- **`why_tags` 에 유형을 {MAX_WHY_TAGS}개까지 적는다.** 앞면에 배지로 뜬다 — "
              + " · ".join(f"`{k}` {v}" for k, v in WHY_TAG_LABEL.items()) + ". "
              "항목의 `signals` 에 있는 `kind` 만 쓰고, `signals` 가 비어 `why` 를 옮겼으면 `basis` 다. "
              "**항목에 `exam` 근거가 있으면 `exam` 은 언제나 넣는다** — 글이 다른 이유를 말해도 "
              "기출 배지는 남는다(빠뜨리면 코드가 넣고 `jokbo_ref` 도 그 근거에서 채운다).",
              "- **글은 배지를 되풀이하지 않는다.** 배지가 「기출」이라고 이미 말하므로, 그 항목에 "
              "기출 말고 다른 근거(`clinical`·`later`·`annotation`)도 있으면 **글에는 그쪽을 쓰고** "
              "기출은 배지로만 남긴다. 기출 근거 하나뿐일 때만 글이 기출을 말한다. 덱 전체의 "
              "「왜 냈나」가 기출 이야기로 몰리면 족보 연습처럼 읽힌다.",
              "- `중요하다`·`꼭 알아야 한다`·`기본 개념이다` 만으로는 이유가 아니다. "
              "**무엇에 왜 쓰이는지**까지 적는다.",
              f"- {MAX_WHY_CHARS}자 이하.",
              "- **학생에게 말하는 자연스러운 한국어 한 문장**으로 쓴다. 의대 강의에서 선배가 "
              "후배에게 설명하듯 — 영어 의학 용어는 그대로 둬도 된다. 써 놓고 소리 내어 읽어 "
              "어색하면 고친다. 실제로 어색했던 꼴(2026-10-04 관리자 지적):",
              "  - 사람이 아닌 것을 주어로 세우지 않는다 — `필기가 ~를 짚었다`·`요약 슬라이드가 "
              "~를 짚었다` → `작년 필기에 ~가 따로 표시돼 있다`",
              "  - 교수는 높인다 — `교수가 ~고 짚었다`·`강의자가 ~라고 했다` → "
              "`교수님이 ~라고 강조하셨다`",
              "  - 비유로 굳은 말을 쓰지 않는다 — `~ 위에 선다`·`~의 열이 된다`·`갈림이 된다`·"
              "`대목`·`짚다` → `~를 바탕으로 설명한다`·`~를 나누는 기준이다`·`부분`·`강조하다`",
              "  - `이 ~`로 시작하면 무엇을 가리키는지 문장 안에서 밝힌다 — 답을 본 뒤라도 "
              "`이 경로 위에서 설명된다` 보다 `AV block과 WPW를 이 전도 경로로 설명한다` 가 낫다",
              "- `explanation` 과 둘 다 답 뒤에 보이지만 할 일이 다르다. `why_asked` 는 **왜 이 "
              "문제를 냈나**, `explanation` 은 **왜 이 답이고** 수업 어디에 쓰이는지다. 같은 말을 "
              "두 번 하지 않는다.",
              "",
              "## `challenge` — 도전 문제",
              "",
              f"덱마다 **{MAX_CHALLENGE}장까지** 도전 문제를 넣을 수 있다. 어렵기만 한 문제가 "
              "아니라 **수업이 답해 줄 질문**이다 — 수업 전에 받아 두면 틀려도 그 대목을 들을 "
              "때 귀가 열린다. 노리는 것은 「오, 아까 그 문제다. 교수님이 딱 말씀하시네」다.",
              "",
              "- **왜 그런지가 궁금해지는 질문이나 임상 장면으로 시작한다.** "
              "(「○○인 환자에게 왜 △△가 생기는가」, 「A 와 B 는 같은 경로인데 왜 결과가 반대인가」)",
              "- **답이 강의 안에 있다.** 그 대목이 슬라이드에 있어야 한다 — 자료 밖 지식으로 "
              "풀리는 문제는 도전 문제가 아니다. 답은 하나로 닫힌다.",
              "- **`why_asked` 에 수업의 어느 부분에서 답이 나오는지 적는다** — "
              "「수업의 ‘○○’ 부분에서 답이 나온다」. ○○ 는 학생이 수업에서 알아볼 수 있는 "
              "부분 이름이다 — 답 뒤에 보이므로 슬라이드 제목을 그대로 써도 된다. "
              "작년 슬라이드 번호는 학생에게 뜻이 없으니 쓰지 않는다.",
              "- 지엽적인 세부·드문 예외·수치 암기로 어렵게 만들지 않는다.",
              "- 승인된 must-know 항목 안에서 고른다. 그 항목에 배정된 카드 수 안에서 한 장을 "
              "도전 문제로 쓰고, 카드 총수 계약도 그대로다.",
              "- 도전 문제가 아닌 카드는 `challenge` 를 `false` 로 둔다."]
    lines += ["", "## 코드가 기계적으로 검사하는 것", "",
              "네가 낸 JSON 은 아래 검사를 그대로 통과해야 한다. **값은 여기 적힌 것이 전부다 —**",
              "**저장소의 코드를 찾아 읽지 마라.** 검사기 소스에는 이보다 더 알 것이 없고,",
              "찾아다니는 동안 근거 위계가 흐려진다.", "",
              f"- 카드 수 {MIN_CARDS}~{MAX_CARDS}장 (벗어나면 덱을 만들지 않는다)",
              f"- `ox` 형식은 전체의 {OX_SHARE_MAX:.0%} 이하",
              # 힌트 칸은 코드·렌더·Anki 가 이미 다 다루는데 **계약에 없어서 모델이
              # 쓸 줄 몰랐다**(2026-09-06 에 관리자가 손으로 그 꼴을 다시 발명했다).
              # 싣기 전에 `reproduce.cloze_unmasked` 를 먼저 고쳤다 — 갈림 힌트는
              # 정의상 답을 품어서, 그대로 두면 답이 4글자 이상일 때 hard 로 사라졌다.
              "- **cloze 의 빈칸에는 셋째 칸을 붙일 수 있다** — `{{c1::답::앞면에 보일 것}}`. "
              "셋째 칸은 앞면에 힌트로 뜬다. 갈림이 둘뿐인 자리에 쓴다 "
              "(`{{c1::건조::건조/습윤}}`). 갈림이 셋 이상이거나 답을 통째로 적어야 하는 "
              "자리에는 쓰지 않는다.",
              f"- 질문은 {MAX_Q_CHARS}자 이하 (cloze 제외)",
              "- **빈칸을 끊는 자리가 곧 질문과 답의 경계다.** 남는 글자가 각 빈칸이 "
              "무엇을 묻는지 말하고, 가린 글자가 답을 통째로 담는다. "
              "**① 빈칸마다 그 축을 남긴다** — 빈칸이 여럿이면 각 자리가 무엇을 묻는지 "
              "남는 문장이 가려 줘야 한다. 낱말 가운데를 끊어도 된다. "
              "**② 답이 되는 덩어리를 통째로 문다** — 답의 일부가 문장에 남으면 빈칸이 "
              "짐작된다. 문맥이 서면 단위를 안에 넣든 밖에 두든 상관없다. "
              "**③ 빈칸에는 실체를 담는다** — 단계 이름·번호·기호 같은 표지만 두지 말고 "
              "실체와 함께 적는다. 분류·대응은 두 방향으로 다 물을 수 있다(감별도 쓸모가 있다). "
              "**④ 남는 문장이 답을 알려주면 안 된다** — 반대말을 대 놓고 그 반대를 묻는 "
              "것이 흔한 실패다(`{{c1::겨울}}이 여름보다 …`). "
              "**⑤ 같은 축이 한 문장 안에 있어야 한다.** "
              "**⑥ 갈림이 둘뿐이면 셋째 칸으로 갈림을 앞면에 보인다**(`{{c1::답::갈림}}`). "
              "써 놓고 빈칸을 `[ ]` 로 바꿔 읽어, 각 `[ ]` 가 무엇을 묻는지 말할 수 있고 "
              "답은 떠오르지 않는지 본다.",
              f"- 목록·순서 답의 항목은 {MAX_RECALL_ITEMS}개 이하, cloze 의 빈칸도 {MAX_RECALL_ITEMS}개 이하",
              f"- 답이 질문 안에 {LEAK_THRESHOLD:.0%} 이상 들어 있으면 정답 노출로 본다 (cloze 제외)",
              f"- 두 카드의 문구가 겹치면 중복으로 본다 — 같은 슬라이드끼리 "
              f"{SIMILAR_SAME_SLIDE:.0%}, 다른 슬라이드끼리 {SIMILAR_CROSS_SLIDE:.0%}",
              "- 질문이 원본 자료를 가리키면 걸린다 — `이 그림`, `위 표`, `강의록`, "
              "`슬라이드에 따르면`, `필기된`, `강조된` 같은 말",
              "- `source_type` 이 `lecture`·`annotation` 이면 `slide_no` 필수, "
              "`jokbo` 면 `jokbo_ref` 필수",
              "- `ox` 의 답은 `O` 또는 `X` 하나",
              f"- `challenge: true` 는 {MAX_CHALLENGE}장 이하",
              f"- `why_asked` 가 비었거나 {MAX_WHY_CHARS}자를 넘으면 표시가 붙는다",
              "- `why_tags` 가 비었거나, 항목의 `signals` 에 없는 유형이면 표시가 붙는다 "
              "(`basis` 는 언제나 된다)",
              "- `why_asked` 가 기출·족보를 말하거나 `why_tags` 에 `exam` 이 있는데 `jokbo_ref` 가 "
              "없으면 표시가 붙는다",
              "- 질문과 답이 완전히 같은 카드, 앞뒤가 똑같은 카드는 버려진다",
              "- `must_id` 가 승인본에 없는 id 이거나 비어 있으면 표시가 붙는다 "
              "(카드는 남는다). 항목별 배정 카드 수를 지켰는지도 이 끈으로 센다",
              "", "**해설(`explanation`)이 비면 깃발이 선다.** 예습 카드에서 그것은 "
              "수업으로 잇는 다리이고 이 덱의 목적 절반이다."]
    (outdir / "contract.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="예습 덱의 출력 계약을 파일로 쓴다")
    ap.add_argument("-o", "--out", default="out/prequiz_schema")
    args = ap.parse_args(argv)
    dump(Path(args.out))
    print(f"{args.out}/ 에 card/must_know/generate schema 와 contract.md 를 썼다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
