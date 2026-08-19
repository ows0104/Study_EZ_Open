"""Anki 노트 유형 정의.

meddeck-local-app/pdf_to_anki/anki_build.py 를 그대로 가져왔다. 모델 이름과 ID를
동일하게 유지하는 것이 중요하다 - 같은 상수를 쓰면 반복 import해도 Anki에
노트 유형이 쌓이지 않고, 기존 MedDeck 덱과 같은 유형을 공유한다.
"""

from __future__ import annotations

import genanki

from quiz.textutil import stable_int_id

ANKI_MODEL_NAME = "MedDeck Basic"
ANKI_MODEL_ID = stable_int_id("model:meddeck:basic:v1")

FIELD_NAMES = [
    "Question", "Answer", "Explanation", "SlideNo",
    "SlideImage", "SourceType", "CardType", "ReviewNote",
]

ANKI_CARD_CSS = """
.card { font-family: Arial, sans-serif; padding: 20px; background-color: white; text-align: center; color: #222; line-height: 1.5; }
.question-box { min-height: 0; display: block; font-size: 20px; color: #1a5f7a; line-height: 1.5; font-weight: bold; white-space: pre-line; text-align: center; }
.answer-box { margin-top: 18px; font-size: 20px; color: #222; line-height: 1.6; font-weight: bold; white-space: pre-line; text-align: left; display: inline-block; max-width: 100%; }
.explanation-box { display: block; margin-top: 16px; font-size: 14px; color: #555; line-height: 1.5; text-align: left; white-space: pre-line; }
.review-box { display: block; margin-top: 16px; padding: 10px 14px; border: 2px solid #c0392b; border-radius: 8px; background: #fdecea; color: #922b21; font-size: 15px; font-weight: bold; line-height: 1.5; text-align: left; white-space: pre-line; }
.meta-box { margin-top: 12px; font-size: 12px; color: #777; }
/* 해설·출처는 접어 둔다. 뒷면에서 먼저 봐야 하는 것은 정답과 슬라이드이고,
   해설은 "왜 그런지" 되짚을 때만 필요하다. 펼치는 데 한 번의 탭이 들지만
   매 카드마다 눈이 걸리는 비용보다 싸다.
   칩은 슬라이드 그림 **아래**에 선다. 그림 위에 두면 펼칠 때 해설이 그림을
   화면 밖으로 밀어낸다. */
.detail-box { display: block; margin-top: 16px; text-align: center; }
.detail-box > summary { display: inline-block; cursor: pointer; list-style: none; padding: 3px 12px; border-radius: 999px; background: #eef3f7; color: #567; font-size: 13px; -webkit-user-select: none; user-select: none; }
.detail-box > summary::-webkit-details-marker { display: none; }
.detail-box > summary::after { content: " ▾"; }
.detail-box[open] > summary::after { content: " ▴"; }
.detail-box .explanation-box { margin-top: 10px; }
.nightMode .detail-box > summary { background: #3a3a3a; color: #b8c4cc; }
.source-pill { display: inline-block; margin-left: 6px; padding: 2px 6px; border-radius: 8px; background: #eef3f7; color: #456; }
.slide-box { margin-top: 12px; border: 1px solid #ddd; padding: 0; background: #f9f9f9; display: inline-block; max-width: 100%; line-height: 0; }
.slide-box img { display: block; }
.cloze-blank { font-weight: bold; color: #1a5f7a; }
/* 오클루전 카드의 앞면 그림. 가려진 자리를 보고 답해야 하므로 질문 텍스트보다
   먼저, 크게 나와야 한다. 이 카드에서는 그림이 문제 그 자체다. */
.occlusion-box { display: block; margin-bottom: 14px; line-height: 0; }
.occlusion-box img { display: block; margin: 0 auto; max-width: 100%; height: auto; }
ul { display: inline-block; text-align: left; margin-top: 1em; margin-left: 0; padding-left: 1.5em; }
li { display: list-item; margin-bottom: 0.6em; }
img { max-width: 100%; height: auto; }
.nightMode .card { background-color: #2b2b2b; color: #e0e0e0; }
.nightMode .question-box { color: #6bb2e2; }
.nightMode .cloze-blank { color: #6bb2e2; }
.nightMode .answer-box { color: #e0e0e0; }
.nightMode .explanation-box { color: #aaaaaa; }
.nightMode .review-box { background: #4a1f1c; border-color: #e57373; color: #ffb3ab; }
/* 나이트 모드에서 박스가 이미지에 딱 붙게 해서 (inline-block, padding 0) 슬라이드
   흰 배경이 좌우로 번지지 않게 한다. */
.nightMode .slide-box { background: #ffffff; border-color: #444; }
"""

# 순서가 이 템플릿의 내용이다.
#   정답 → 경고 → 슬라이드 그림 → 접힌 해설·출처
# 해설을 그림 위에 두면 접혀 있는 칩이 정답과 그림 사이를 밀고 들어서,
# 펼치는 순간 그림이 화면 밖으로 쓸려난다. 그림을 먼저 세우면 펼쳐도 그림이
# 제자리에 있고 해설이 그 아래로 자란다.
#
# `Answer`를 조건부로 감싸는 것은 오클루전 때문이다 - 그 카드는 **드러난
# 슬라이드 그림 자체가 정답**이라 빌드가 이 필드를 비워서 보낸다(build.py 참조).
# 빈 필드를 그대로 그리면 빈 answer-box가 자리를 차지해 그림이 밀린다.
_ANSWER_TEMPLATE = """
<div class="question-box">{{Question}}</div>
<hr id="answer">
{{#Answer}}<div class="answer-box">{{Answer}}</div>{{/Answer}}
{{#ReviewNote}}<div class="review-box">⚠ {{ReviewNote}}</div>{{/ReviewNote}}
{{#SlideImage}}<div class="slide-box">{{SlideImage}}</div>{{/SlideImage}}
<details class="detail-box">
<summary>해설 · 출처</summary>
{{#Explanation}}<div class="explanation-box">{{Explanation}}</div>{{/Explanation}}
<div class="meta-box">출처: Slide {{SlideNo}} <span class="source-pill">{{SourceType}}</span> <span class="source-pill">{{CardType}}</span></div>
</details>
"""


def get_anki_model(model_id: int | None = None, model_name: str | None = None) -> genanki.Model:
    """전체 덱 공용 단일 노트 유형. cloze도 같은 유형을 쓴다 (빈칸은 텍스트에 구워 넣음)."""
    return genanki.Model(
        model_id or ANKI_MODEL_ID,
        model_name or ANKI_MODEL_NAME,
        fields=[{"name": name} for name in FIELD_NAMES],
        templates=[{
            "name": "Card 1",
            "qfmt": '<div class="question-box">{{Question}}</div>',
            "afmt": _ANSWER_TEMPLATE,
        }],
        css=ANKI_CARD_CSS,
    )


def deck_component(value: str, fallback: str) -> str:
    component = str(value or "").replace("::", " - ")
    component = "".join(ch for ch in component if ord(ch) >= 32).strip()
    return component or fallback


def hierarchical_deck_name(project_title: str, lecture_title: str) -> str:
    return f"{deck_component(project_title, '프로젝트')}::{deck_component(lecture_title, '강의')}"
