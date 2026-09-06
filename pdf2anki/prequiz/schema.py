"""예습 퀴즈의 공용 계약.

복습 덱(`pdf2anki.schema`)과 **일부러** 다른 파일이다. 두 덱의 목적 함수가 다르기 때문이다.

    복습(quiz)  — 시험에 나올 수 있는 것
    예습(prequiz) — 이 강의에서 꼭 반드시 알아야 하는 것

예습의 목적은 수업 중에 「저 단어가 뭐지? 저 약어가 뭐지? 저 기전이 뭐지?」로
막히지 않게 하고, 「오 이거 어제 외웠던 거다」를 만드는 것이다. 흥미를 유발하고
학습에 장애물이 없게 하는 것이 목표이며, 강의를 따라가는 것은 그 수단이다.

축이 다르니 계약도 다르다 —
  · `trap`(함정) 유형이 없다. 수업 전날 함정은 장애물을 하나 더 세우는 것이다.
  · `importance` 축이 없다. 예습 덱은 **전부** '꼭 반드시'다. 등급이 있으면 축이 흐려진다.
  · 대신 **개수 상한이 계약이다.** 30장을 넘기는 순간 '꼭 반드시'가 아니게 된다.

사용:
    python -m pdf2anki.prequiz.schema -o out/prequiz_schema
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
# 한 강의가 77장까지 갔다. 예습은 강의 전날 한 번에 끝나야 하고, 30장을 넘는 순간
# 사용자가 막으려던 바로 그 느낌 — 「외워야 될 게 너무 많은데?」 — 을 예습이 만든다.
MIN_CARDS, MAX_CARDS = 20, 30

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
            "description": "reason=repeated 의 근거가 된 문항. 그 밖에는 비운다.",
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
            "type": "array", "minItems": 8, "maxItems": 25,
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
                    "cards": {"type": "integer", "minimum": 1, "maximum": 3,
                              "description": "이 항목에 배정할 카드 수. 합이 20~30 이어야 한다."},
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
              "- 카드 앞면에 선지·연도·문항 번호가 나와서는 안 된다."]
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
              "판정은 둘이다 — **회수할 값어치가 있는 것을, 무엇을 묻는지 문맥으로 알 수 "
              "있게** 비웠는가. 빈칸을 맞히는 일이 곧 그 지식을 아는 일이어야 한다 — "
              "표지(단계 이름·번호·기호)만 두지 말고 실체와 함께 적는다. "
              "빈칸이 여럿이면 각 자리의 축이 남는 문장에 서 있어야 한다 — 낱말 가운데를 "
              "끊어도 되고, 문맥이 서면 어디서 끊든 상관없다. 그 위에 둘을 지킨다 — "
              "**① 갈림을 앞면에 보일 수 있다**: 빈칸의 셋째 칸(`{{c1::답::갈림}}`)은 "
              "앞면에 힌트로 뜬다. 방향·대소·유무처럼 답이 몇 가지로 갈리는 자리에 쓴다. "
              "**② 문맥이 답을 알려주면 안 된다**: 반대말을 대 놓고 그 반대를 묻는 것이 "
              "흔한 실패다(`{{c1::겨울}}이 여름보다 …`) — 축을 세운 것처럼 보이지만 답을 "
              "준 것이다. "
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
