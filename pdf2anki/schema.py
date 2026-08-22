"""카드와 학습계획의 공용 계약.

계약은 여기 한 곳에만 둔다. 프롬프트 산문에 다시 적지 않는다.
프롬프트 조립기·validator·builder가 모두 이 파일을 읽는다.

사용:
    python -m pdf2anki.schema -o out/schema     # 프롬프트에 붙일 JSON Schema 를 쓴다
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
)
IMAGE_FORMATS = ("image_basic", "image_occlusion")
REJECT_REASONS = (
    "decorative", "obvious", "out_of_scope", "duplicate", "unsupported", "low_yield",
)
DROP_REASONS = (
    "exact_duplicate", "semantic_duplicate", "unsupported", "out_of_scope",
    "obvious_or_decorative", "ambiguous_unrepairable", "over_fragmented",
    "style_mismatch", "invalid_unrepairable",
)
DISPOSITIONS = ("keep", "revise", "keep_with_warning", "drop")

# 한 카드가 한 번에 회수시킬 항목 수 상한 (2.5 목록·순서·선지 묶음)
MAX_RECALL_ITEMS = 6

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
              "description": "핵심 정답만. 이유와 부연은 explanation 으로."},
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
    },
}

PLAN_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "LearningPlan",
    "type": "object",
    "additionalProperties": False,
    "required": ["objectives"],
    "properties": {
        "objectives": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["objective", "retrieval_targets", "slides"],
                "properties": {
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
    "basic": "q 는 질문문, a 는 핵심 정답. media 는 null.",
    "cloze": "q 에 {{c1::...}} 가 하나 이상. a 는 가려진 내용을 모은 것. media 는 null.",
    "ox": "q 는 진술문, a 는 'O' 또는 'X'. 틀린 진술이면 explanation 에 왜 틀렸는지 적는다.",
    "image_basic": "media.figure_id 필수. 앞면에 그림 전체를 붙이고 무엇인지 묻는다.",
    "image_occlusion": "media.figure_id 와 media.occlusion_ids 필수. "
                       "가린 라벨이 답이며, 답을 q 에 노출하지 않는다.",
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
              "- 축(회수 방향)이 다르면 카드가 다르다. 한 카드에 여러 축을 몰지 않는다.",
              # 빈칸 번호가 곧 카드 수라는 것을 모르면 「나머지가 앞면에 인쇄된 카드」가
              # 나온다. 임계값과 마찬가지로 **계약에 실려야 모델이 안다.**
              "- **cloze 의 번호 하나가 카드 하나다.** 한 축에 나란히 놓인 항목은 같은 번호로 "
              "함께 가린다. 번호를 가르면 카드가 그 수만큼 갈리고 각 카드는 나머지를 앞면에 "
              "인쇄한다. 번호를 가르는 것은 축이 서로 다를 때뿐이다.",
              f"- 빈칸 문장도 {MAX_Q_CHARS}자를 넘으면 표시된다. 정의문을 통째로 옮겨 놓고 "
              "여기저기 뚫지 말고, 정의를 묻고 싶으면 `basic` 을 쓴다.",
              "- **`a` 의 항목이 둘 이상이면 줄바꿈과 `- ` 로 나눈다.** 범주와 내용은 `:` 로 가르고 "
              "`—` 는 쓰지 않는다. 두 칸 들여쓰기로 한 단계까지 중첩할 수 있다. "
              "한 마디짜리 답에는 불릿을 붙이지 않는다.",
              "- `evidence_type=annotation` 은 기출이 그 지점을 실제로 물었을 때만 쓸 수 있다.",
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
