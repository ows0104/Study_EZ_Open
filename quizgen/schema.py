"""카드와 학습계획의 공용 계약.

계약은 여기 한 곳에만 둔다. 프롬프트 산문에 다시 적지 않는다.
프롬프트 조립기·validator·builder가 모두 이 파일을 읽는다.

사용:
    python -m quizgen.schema -o out/schema     # 프롬프트에 붙일 JSON Schema 를 쓴다
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────── enum

CARD_FORMATS = ("basic", "cloze", "ox", "image_basic", "image_occlusion")
CARD_TYPES = ("fact", "comparison", "mechanism", "trap", "list", "sequence")
IMPORTANCE = ("core", "detail")
SOURCE_TYPES = ("lecture", "jokbo")
EVIDENCE_TYPES = (
    "lecture_text",      # 강의록 본문
    "lecture_figure",    # 강의록 표·그림의 명시적 라벨/축/범례
    "annotation",        # 필기. 기본은 근거 불가, 기출이 그 지점을 물었을 때만 허용
    "jokbo_question",    # 기출 문항 원문
    "jokbo_objection",   # 이의제기에 대한 교수 답변
    # 기출 파트에서만 쓴다. 강의록 카드에 붙으면 `validate` 가 떨어뜨린다.
    #
    # 강의록은 정본이라 밖에서 메울 것이 없지만, **기출은 복원된 것**이다 — 족보 PDF
    # 에서 잘라 온 문항이고, 필기 부록에서 온 것은 이미지에서 읽어 낸 것이다. 문항
    # 본문도 정답도 복원 과정에서 어긋날 수 있다. 관리자 판정으로 이 자리에서는
    # 모델의 의학 지식을 근거로 쓸 수 있다.
    #
    # 다만 **웹은 아니다.** 저작 세션의 도구는 `session.AUTHOR_TOOLS` 뿐이고
    # 검색이 없다. 여기서 말하는 외부 지식은 모델 자신의 것이다.
    "medical_knowledge",
)
IMAGE_FORMATS = ("image_basic", "image_occlusion")


def resolve_jokbo_key(year: str, no: str, keys) -> tuple[str, str] | None:
    """인용한 (연도, 번호)에 맞는 조각의 열쇠. 없으면 None.

    **인용 연도가 조각의 회차 이름과 한 겹 다를 수 있다.** 실습 족보는 한 해에
    시험이 둘인 해가 있어 회차를 `2016-1`·`2016-2`로 적는데, 강의록 뒤에 붙는 기출
    부록은 그냥 `2016`이라 적는다. 모델은 부록을 읽고 인용하므로 조각과 안 맞는다 —
    2026-09-08 `260904_05` 에서 카드 6장이 그렇게 어긋났고, 그 6장은 뒷면의 문항
    원문과 지면 이미지를 잃은 채 나갈 뻔했다.

    **갈래가 여럿이면 안 고른다.** `2016-1`과 `2016-2`가 둘 다 그 번호를 들고 있으면
    어느 쪽인지 여기서는 알 수 없다. 그때는 None을 돌려주어 표시가 그대로 뜨게 둔다 —
    아무거나 집어서 남의 문항을 뒷면에 붙이는 것보다 낫다.
    """
    if (year, no) in keys:
        return (year, no)
    same = sorted(k for k in keys if k[1] == no and k[0].split("-")[0] == year)
    return same[0] if len(same) == 1 else None
# `jokbo_appendix` 만 성격이 다르다. 나머지 여섯은 "안 낸다"이고 이것은
# **"여기서는 안 낸다 — 기출 파트 소관이다"** 이다. 필기자가 강의록 뒤에 붙여 놓는
# 족보 정리 구간이 그 자리다(28편 중 27편에 있었고, 합계 116슬라이드).
# 모델은 이미 그 구간을 정확히 짚고 "필기자가 붙인 기출 문항 이미지" 라고 적고
# 있었다(꼬리 거절 48건 중 42건). 사유가 없어서 `out_of_scope` 로 흘렀을 뿐이다.
REJECT_REASONS = (
    "decorative", "obvious", "out_of_scope", "duplicate", "unsupported", "low_yield",
    "jokbo_appendix",
)
DROP_REASONS = (
    "exact_duplicate", "semantic_duplicate", "unsupported", "out_of_scope",
    "obvious_or_decorative", "ambiguous_unrepairable", "over_fragmented",
    "style_mismatch", "invalid_unrepairable",
)
DISPOSITIONS = ("keep", "revise", "keep_with_warning", "drop")

# 한 카드가 한 번에 회수시킬 항목 수 상한 (2.5 목록·순서·선지 묶음)
MAX_RECALL_ITEMS = 6

# 답의 무게를 재는 두 값. 둘 다 표시만 하고 떨어뜨리지 않는다.
#
# **재는 것은 뒷면에 찍히는 글자가 아니라 「외워야 하는 글자」다.** 형식마다 그 자리가
# 다르다 — `basic` 은 `a` 안의 `**` 강조(강조가 없으면 답이 통째로 회수 대상이다),
# `cloze` 는 `a` 전체(계약상 `a` 가 이미 가린 것만 모은 것이다). `cloze` 의 프레임
# 길이는 회수 부담이 아니므로 여기서 세지 않는다 — `cloze_sentence_too_long` 이 따로 본다.
#
# 두 값은 서로 다른 고장을 잡는다. `260824` 이후 2083장에서 겹친 것이 9장(3%)뿐이었다.
#
#   회수 부담이 크다      외울 것이 많다        → 축을 갈라 카드를 나눈다
#   프레임이 눌러앉았다    외울 건 적은데 읽을 게 많다  → explanation 으로 보내거나 cloze 를 본다
#
# 문턱은 그 2083장의 분포에서 발생률을 보고 잡았다.
#
#   회수 부담 80자 초과                       234장  11.2%
#   뒷면 100자 이상이면서 회수 비율 40% 미만      156장   7.5%
#
# **비율만으로는 못 쓴다.** 40% 하나로 걸면 27.7% 가 걸리는데, 그 대부분은 뒷면이
# 짧아서(「**흡혈**하는 선충」) 비율만 낮은 멀쩡한 카드다. 그래서 뒷면 길이를 같이 문다 —
# 외울 게 적은 것이 아니라 **읽을 게 많은 것**이 잡으려던 고장이다.
#
# 이 자리에서 한 번 덴 적이 있다. 해설 없음을 표시하던 깃발이 복습 카드의 44% 에 붙어
# 「실제로 봐야 할 신호를 통째로 덮고」 있었고 관리자가 껐다(`validate.py` 주석).
#
# **아직 사람이 「이 값이 맞다」고 판정한 적은 없다.** 걸린 것을 눈으로 보고 조정할 값이다.
MAX_RECALL_CHARS = 80
MIN_RECALL_SHARE = 0.40
FRAME_HEAVY_MIN_CHARS = 100

# 질문 길이 상한. 넘으면 표시만 하고 떨어뜨리지는 않는다.
#
# **축이 여럿인지를 문장 형태로 잡으려던 시도는 접었다.** `무엇이며`·`이며,` 를 신호로
# 넣었더니 세 덱에서 22장이 걸렸는데 사용자 판정으로 진짜 결함은 **한 장**이었다.
# 한국어에서 그 연결은 정의와 그 즉각적 귀결을 잇는 가장 흔한 형태이고,
# 이미지 카드는 철학이 오히려 "장기·진단·소견을 한 장에서" 물으라고 시킨다.
# 5% 정밀도의 깃발은 아무도 보지 않으므로 없느니만 못하다.
# 축을 나누는 판단은 저작 시점의 철학이 맡고, 여기서는 길이만 잰다.
#
# `validate.py` 가 아니라 여기 있는 이유는 **계약에 실려야 모델이 알기 때문이다** —
# 안 실으면 모델이 검사기 소스를 뒤져서 알아낸다.
MAX_Q_CHARS = 120

CARD_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Card",
    "type": "object",
    "additionalProperties": False,
    "required": ["q", "a", "card_format", "card_type", "importance",
                 "source_type", "evidence_type", "exam_hit"],
    "properties": {
        "id": {"type": ["string", "null"],
               "description": "비워 둘 것. merge 단계에서 코드가 부여한다."},
        "q": {"type": "string", "minLength": 1,
              "description": "질문. cloze 는 {{c1::...}} 를 포함한 문장."},
        "a": {"type": "string", "minLength": 1,
              "description": "회수 대상을 담는다. 회수 대상이 아닌 부연은 explanation 으로. "
                             "전략이 한 카드에서 여러 가지를 함께 회수하라고 지정했다면 그것들이 함께 핵심 정답이다."},
        "explanation": {"type": ["string", "null"],
                        "description": "왜 이 답인지. q/a 의 근거가 되어서는 안 된다."},
        "slide_no": {"type": ["integer", "null"], "minimum": 1,
                     "description": "source_type=lecture 면 필수. jokbo 면 null."},
        "card_format": {"enum": list(CARD_FORMATS)},
        "card_type": {"enum": list(CARD_TYPES)},
        "importance": {"enum": list(IMPORTANCE)},
        "source_type": {"enum": list(SOURCE_TYPES)},
        "evidence_type": {"enum": list(EVIDENCE_TYPES)},
        "exam_hit": {"type": "boolean",
                     "description": "특정 연도·문항이 같은 회수 목표를 실제로 물었을 때만 true. "
                                    "source_type=jokbo 에는 부여하지 않는다."},
        "jokbo_ref": {
            "type": ["object", "null"], "additionalProperties": False,
            "required": ["year", "no"],
            "properties": {"year": {"type": "string"}, "no": {"type": "string"},
                           "role": {"enum": ["source", "exam_hit_evidence"]}},
            "description": "기출 카드의 출처, 또는 exam_hit 의 근거가 된 문항.",
        },
        "media": {
            "type": ["object", "null"], "additionalProperties": False,
            "required": ["figure_id"],
            "properties": {
                "figure_id": {"type": "string",
                              "description": "prep.json 의 lecture_figures[].id (fig_pNN_MM)"},
                "occlusion_ids": {"type": "array", "items": {"type": "string"},
                                  "description": "prep.json 의 occlusion_candidates[].id"},
                "reveal_all": {"type": "boolean",
                               "description": "뒷면에서 모든 라벨을 드러낼지"},
                "crop": {"type": "array", "items": {"type": "number", "minimum": 0, "maximum": 1},
                         "minItems": 4, "maxItems": 4,
                         "description": "그림 안에서 다시 자를 구간 [x0,y0,x1,y1] (그림 크기 기준 비율). "
                                        "슬라이드 캡션이 그림에 함께 들어가 정답이 노출될 때 쓴다. "
                                        "예: 아래 25%를 잘라내려면 [0,0,1,0.75]"},
            },
            "description": "image_basic / image_occlusion 에서만 채운다.",
        },
        "review_note": {"type": ["string", "null"],
                        "description": "기출 정답 의심 등 사용자에게 보일 경고. 없으면 null."},
        # **이 카드가 어느 목표를 위한 것인가.** 계획의 `objectives[].id` 를 그대로 적는다.
        # 이 끈이 없으면 「목표에 카드가 갔는가」와 「계획에 없는 것을 물었는가」를 둘 다
        # 글자 유사도로 추측해야 한다. 2026-08-30 이전에 만든 편에는 없으므로 필수가 아니다.
        "objective_id": {"type": ["string", "null"],
                         "description": "이 카드가 옮긴 목표의 id (예: 'o03'). "
                                        "기출 카드는 'j01' 처럼 기출 목표의 id 를 쓴다."},
    },
}

# 계획이 두 묶음인 이유는 **기출의 예산이 하나뿐이었기 때문**이다.
#
# 260821_03 을 세 번 돌려 보면 기출직결 카드가 33 → 26 → 27 로 거의 안 움직이는데,
# 그 안의 배분만 (기출카드 2 / 태그 31) → (12 / 14) → (4 / 23) 로 뒤집힌다.
# 프롬프트로 한쪽을 밀면 다른 쪽이 그만큼 빠졌다. 강의록 목표만 있고 기출은 그
# 목표의 각주(`jokbo_refs`)였으니, 둘이 같은 주머니를 나눠 쓴 것이다.
#
# `jokbo_objectives` 는 그 주머니를 하나 더 만든다. 슬라이드가 아니라 **기출 문항**을
# 근거로 서는 목표이고, 그래서 `slides` 가 아니라 `jokbo_refs` 가 필수다.
PLAN_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "LearningPlan",
    "type": "object",
    "additionalProperties": False,
    "required": ["objectives"],
    "properties": {
        "jokbo_objectives": {
            "type": "array",
            "description": "기출 파트의 회수 목표. 강의록이 아니라 기출 문항에서 선다.",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["objective", "retrieval_targets", "jokbo_refs"],
                "properties": {
                    "id": {"type": ["string", "null"]},
                    "objective": {"type": "string",
                                  "description": "강의록 목표와 같은 규칙으로 쓴다. "
                                                 "검증 가능한 동사, '이해한다' 는 안 된다."},
                    "retrieval_targets": {"type": "array", "items": {"type": "string"},
                                          "minItems": 1},
                    "jokbo_refs": {"type": "array", "items": {"type": "string"},
                                   "minItems": 1,
                                   "description": "이 목표가 선 근거 문항. 반복 묶음이면 "
                                                  "묶음의 문항을 전부 적는다."},
                    "slides": {"type": "array", "items": {"type": "integer", "minimum": 1},
                               "description": "그 지식이 강의록에도 있으면 적는다. 없으면 비운다."},
                    "importance": {"enum": list(IMPORTANCE)},
                    "axis": {"type": "string",
                             "description": "이 목표가 그 문항의 어느 축을 무는지 한 마디. "
                                            "예: '오답 선지', '정의', '감별', '이의제기'"},
                },
            },
        },
        "objectives": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["objective", "retrieval_targets", "slides"],
                "properties": {
                    # 승인할 때 `review.py` 가 코드로 찍는다. 모델이 짓지 않는다.
                    "id": {"type": ["string", "null"]},
                    "objective": {"type": "string",
                                  "description": "'식별한다/구분한다/설명한다/적용한다/재구성한다' 처럼 "
                                                 "검증 가능한 회수 목표로 쓴다. '이해한다' 는 안 된다."},
                    "retrieval_targets": {"type": "array", "items": {"type": "string"},
                                          "minItems": 1},
                    "slides": {"type": "array", "items": {"type": "integer", "minimum": 1}},
                    "importance": {"enum": list(IMPORTANCE)},
                    "jokbo_refs": {"type": "array", "items": {"type": "string"},
                                   "description": "이 목표를 실제로 물은 기출 (예: '2025-19')"},
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
                    "slides": {"type": "array", "items": {"type": "integer"}},
                },
            },
            "description": "검토했지만 카드로 내지 않은 것. 누락과 의도적 제외를 구분하는 감사 흔적.",
        },
    },
}

GENERATE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "GenerateOutput",
    "type": "object",
    "additionalProperties": False,
    "required": ["cards"],
    "properties": {
        "learning_plan": PLAN_SCHEMA,
        "cards": {"type": "array", "items": CARD_SCHEMA},
    },
}

# 형식별 추가 계약. JSON Schema 로 표현하면 읽기 어려워 validator 가 코드로 검사한다.
FORMAT_RULES = {
    "basic": "q 는 질문문, a 는 핵심 정답. 이유·조건·부연은 a 가 아니라 explanation 에 둔다. "
             "**기본형이다.** 질문 하나로 무엇을 묻는지 세울 수 있으면 이 형식이다 — 답이 "
             "하나든 목록이든, 짧든 길든 질문이 그 답을 닫아 주기만 하면 된다. media 는 null.",
    "cloze": "q 에 {{c1::...}} 가 하나 이상. **번호는 언제나 c1 하나만 쓴다** — 빈칸이 여럿이어도 전부 c1 이다. a 는 가려진 내용을 모은 것. media 는 null. "
             "**긴 문장에서 핵심만 회상하게 하는 형식이다.** 회수할 핵심이 여럿인데 "
             "그 문장이 있어야 무엇을 묻는지 서는 자리에 쓴다 — 문장은 앞면에 그대로 주고 "
             "핵심 자리만 비운다. 문장이 길다고 쓰는 것이 아니다. "
             "세거나 나열하는 것(「네 징후는?」)은 문장이 하는 일이 없으므로 basic 이다.",
    "ox": "q 는 진술문, a 는 'O' 또는 'X'. 틀린 진술이면 explanation 에 왜 틀렸는지 적는다.",
    "image_basic": "media.figure_id 필수. 앞면에 그림 전체를 붙이고 무엇인지 묻는다.",
    "image_occlusion": "media.figure_id 와 media.occlusion_ids 필수. 이름 있는 핵심 라벨만 "
                       "선택하며 가린 원문 라벨이 a 에 들어 있어야 한다. 자료가 제공한 한국어·영어 "
                       "대응 표기는 고정된 병기로 함께 쓸 수 있으나 q 에 노출하지 않는다.",
}


def dump(outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    for name, obj in (("card.schema.json", CARD_SCHEMA),
                      ("plan.schema.json", PLAN_SCHEMA),
                      ("generate.schema.json", GENERATE_SCHEMA)):
        (outdir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 출력 계약", "",
             "아래 JSON Schema 를 그대로 지킨다. 모르는 키를 추가하지 않는다.", "",
             "```json", json.dumps(GENERATE_SCHEMA, ensure_ascii=False, indent=2), "```", "",
             "## 형식별 추가 규칙", ""]
    lines += [f"- `{k}` — {v}" for k, v in FORMAT_RULES.items()]
    lines += ["", f"- 목록·순서·선지 묶음은 한 카드에 {MAX_RECALL_ITEMS}개를 넘기지 않는다.",
              "- 축(회수 방향)이 다르면 카드가 다르다. 한 카드에 여러 축을 몰지 않는다. "
              "전략이 한 사진·한 카드에 함께 회수하라고 지정한 것은 예외다.",
              # 번호를 가르면 카드가 그 수만큼 갈리고 각 카드가 나머지 답을 앞면에 인쇄한다.
              # 그것이 관리자가 싫다고 한 모양이라 **굽는 자리에서 전부 c1 으로 모은다**
              # (`build.collapse_cloze`). 계약에도 실어야 모델이 축을 번호로 가르지 않는다.
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
              "- **cloze 의 빈칸 번호는 전부 `c1` 이다.** 한 노트가 카드 한 장이고 뚫은 자리가 "
              "한꺼번에 가려진다. `c2`·`c3` 을 적어도 코드가 `c1` 로 모으므로, 축이 다른 것을 "
              "한 문장에 몰면 **한 카드가 두 축을 함께 묻게 된다** — 축이 다르면 번호가 아니라 "
              "카드를 나눈다.",
              # 힌트 칸은 코드·렌더·Anki 가 이미 다 다루는데 **계약에 없어서 모델이
              # 쓸 줄 몰랐다**(2026-09-06 에 관리자가 손으로 그 꼴을 다시 발명했다).
              # 싣기 전에 `reproduce.cloze_unmasked` 를 먼저 고쳤다 — 갈림 힌트는
              # 정의상 답을 품어서, 그대로 두면 답이 4글자 이상일 때 hard 로 사라졌다.
              "- **cloze 의 빈칸에는 셋째 칸을 붙일 수 있다** — `{{c1::답::앞면에 보일 것}}`. "
              "셋째 칸은 앞면에 힌트로 뜬다. 갈림이 둘뿐인 자리에 쓴다 "
              "(`{{c1::건조::건조/습윤}}`). 갈림이 셋 이상이거나 답을 통째로 적어야 하는 "
              "자리에는 쓰지 않는다.",
              f"- 빈칸 문장도 {MAX_Q_CHARS}자를 넘으면 표시된다. 정의문을 통째로 옮겨 놓고 "
              "여기저기 뚫지 말고, 정의를 묻고 싶으면 `basic` 을 쓴다.",
              "- **`a` 의 항목이 둘 이상이면 줄바꿈과 `- ` 로 나눈다.** 범주와 내용은 `:` 로 가르고 "
              "`—` 는 쓰지 않는다. 두 칸 들여쓰기로 한 단계까지 중첩할 수 있다. "
              "한 마디짜리 답에는 불릿을 붙이지 않는다.",
              # **금지형으로 적었다가 관리자가 물렸다**(2026-09-05) — 「명사구로 끊고
              # 서술문으로 늘이지 않는다 · 대개 40자」. 근거는 「한 줄 40자 초과 26.6%」
              # 라는 **분포**였지 서술문이 나쁘다는 실패가 아니었다. `CLAUDE.md` 가
              # 「허용이 기본이고 금지형은 실측 실패나 관리자 지시가 있을 때만」이라고
              # 적어 둔 자리를 내가 어겼다. 관리자가 든 반례는 이것이다 —
              #
              #     야간 소양증 때문에 불면·야뇨증이 나타난다
              #
              # 인과가 회수 대상이면 문장이 맞는 답이다. 그래서 허용형으로 다시 썼다.
              # 마지막 줄은 v4 실측에서 나왔다 — 답을 깎았더니 `answer_underspecified`
              # 가 8장 나왔다. 깎은 만큼 질문이 닫아야 한다.
              "- **`a` 에는 떠올려야 하는 것을 남긴다.** 볼 때마다 다시 읽게 되는 배경은 "
              "`explanation` 으로 보낼 수 있다. 한 줄에 항목이 여럿 얽혀 있으면 나눈다. "
              "인과가 회수 대상이면 문장 그대로 둔다.",
              "- 답이 긴 까닭이 항목이 많아서라면 축을 갈라 카드를 나누고, 프레임 문장이 "
              "길어서라면 `cloze` 가 맞는 형식인지 본다.",
              # 「답을 깎으면 질문이 더 닫는다」로 적었다가 걷었다 (2026-09-05).
              # 인과가 근거 없었다 — 원본 편도 답이 같은 불릿 목록이었는데 결함 0장이고,
              # v4 에서 걸린 카드도 이미 「원인 다섯은?」으로 개수를 밝히고 있었다.
              # 실제로 일어난 일은 **개수만으로는 안 닫힌 것**이고, 그것은 「개수뿐
              # 아니라 범주나 기준을」이 이미 말하고 있다. 빠져 있던 것은 그다음 한 수라
              # 「답의 재현 가능성」쪽에 붙였다 — 범주로도 안 닫히면 cloze 로 닫는다.
              # (수선이 두 번 다 스스로 그 길을 찾았다.)
              f"- 답의 무게는 **뒷면 길이가 아니라 외워야 하는 글자로** 잰다 — `basic` 은 "
              f"`a` 안의 `**` 강조(강조가 없으면 답 전체), `cloze` 는 `a` 전체다. "
              f"그것이 {MAX_RECALL_CHARS}자를 넘거나, `basic` 의 뒷면이 "
              f"{FRAME_HEAVY_MIN_CHARS}자 이상인데 회수 대상이 그 {MIN_RECALL_SHARE:.0%} 에 "
              f"못 미치면 표시된다. 앞은 축을 나누라는 신호이고 뒤는 프레임이 답에 "
              f"눌러앉았다는 신호다.",
              "- `evidence_type=annotation` 은 기출이 그 지점을 실제로 물었을 때만 쓸 수 있다.",
              "- `evidence_type=medical_knowledge` 는 `source_type=jokbo` 에서만 쓸 수 있다. "
              "무엇을 고쳤는지 `review_note` 에 적는다.",
              "- `source_type=jokbo` 카드에 `exam_hit` 을 중복 부여하지 않는다."]
    (outdir / "contract.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="출력 계약을 파일로 쓴다")
    ap.add_argument("-o", "--out", default="out/schema")
    args = ap.parse_args(argv)
    dump(Path(args.out))
    print(f"{args.out}/ 에 card/plan/generate schema 와 contract.md 를 썼다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
