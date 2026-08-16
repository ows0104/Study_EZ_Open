"""예습확인퀴즈 Anki 노트 유형.

`quiz/notetype.py`의 MedDeck Basic과 별개 유형이다. 예습 문항은 앞면에 선지가
같이 떠야 하고(객관식·OX), 뒷면에서 어느 선지가 정답이었는지 보여야 하므로
필드 구성 자체가 다르다. 같은 유형에 욱여넣으면 두 덱의 템플릿이 서로를
망가뜨린다.

모델 이름·ID는 상수로 고정한다. 반복 import해도 Anki에 노트 유형이 쌓이지 않는다.
"""

from __future__ import annotations

import genanki

from quiz.textutil import stable_int_id

ANKI_MODEL_NAME = "MedDeck Preview"
ANKI_MODEL_ID = stable_int_id("model:meddeck:preview:v1")

FIELD_NAMES = [
    "Question", "Choices", "ChoicesMarked", "Answer",
    "Explanation", "SlideNo", "SlideImage", "QType", "Focus",
]

ANKI_CARD_CSS = """
.card { font-family: Arial, sans-serif; padding: 20px; background-color: white; text-align: center; color: #222; line-height: 1.5; }
.question-box { display: block; font-size: 20px; color: #1a5f7a; line-height: 1.5; font-weight: bold; white-space: pre-line; text-align: center; }
.choices { display: inline-block; text-align: left; margin: 18px 0 0 0; padding: 0; list-style: none; max-width: 100%; }
.choices li { display: block; margin-bottom: 0.55em; font-size: 18px; line-height: 1.5; }
.choices li .num { display: inline-block; min-width: 1.6em; font-weight: bold; color: #1a5f7a; }
.choices li.correct { color: #1e7a45; font-weight: bold; }
.choices li.correct .num { color: #1e7a45; }
.answer-box { margin-top: 18px; font-size: 20px; color: #222; line-height: 1.6; font-weight: bold; white-space: pre-line; text-align: left; display: inline-block; max-width: 100%; }
.explanation-box { display: block; margin-top: 16px; font-size: 14px; color: #555; line-height: 1.5; text-align: left; white-space: pre-line; }
.meta-box { margin-top: 16px; font-size: 12px; color: #777; }
.source-pill { display: inline-block; margin-left: 6px; padding: 2px 6px; border-radius: 8px; background: #eef3f7; color: #456; }
.focus-pill { display: inline-block; margin-left: 6px; padding: 2px 6px; border-radius: 8px; background: #fdf0d5; color: #7a5c1a; }
.slide-box { margin-top: 12px; border: 1px solid #ddd; padding: 0; background: #f9f9f9; display: inline-block; max-width: 100%; line-height: 0; }
.slide-box img { display: block; }
img { max-width: 100%; height: auto; }
.nightMode .card { background-color: #2b2b2b; color: #e0e0e0; }
.nightMode .question-box { color: #6bb2e2; }
.nightMode .choices li .num { color: #6bb2e2; }
.nightMode .choices li.correct { color: #7ed6a2; }
.nightMode .choices li.correct .num { color: #7ed6a2; }
.nightMode .answer-box { color: #e0e0e0; }
.nightMode .explanation-box { color: #aaaaaa; }
.nightMode .focus-pill { background: #4a3d1c; color: #f0d79a; }
/* 슬라이드 흰 배경이 좌우로 번지지 않게 박스를 이미지에 딱 붙인다. */
.nightMode .slide-box { background: #ffffff; border-color: #444; }
"""

_QUESTION_TEMPLATE = """
<div class="question-box">{{Question}}</div>
{{#Choices}}{{Choices}}{{/Choices}}
"""

_ANSWER_TEMPLATE = """
<div class="question-box">{{Question}}</div>
{{#ChoicesMarked}}{{ChoicesMarked}}{{/ChoicesMarked}}
<hr id="answer">
<div class="answer-box">{{Answer}}</div>
{{#Explanation}}<div class="explanation-box">{{Explanation}}</div>{{/Explanation}}
<div class="meta-box">출처: Slide {{SlideNo}} <span class="source-pill">{{QType}}</span> <span class="focus-pill">{{Focus}}</span></div>
{{#SlideImage}}<div class="slide-box">{{SlideImage}}</div>{{/SlideImage}}
"""


def get_anki_model(model_id: int | None = None, model_name: str | None = None) -> genanki.Model:
    """예습확인퀴즈 공용 단일 노트 유형. 객관식·단답·OX가 같은 유형을 쓴다."""
    return genanki.Model(
        model_id or ANKI_MODEL_ID,
        model_name or ANKI_MODEL_NAME,
        fields=[{"name": name} for name in FIELD_NAMES],
        templates=[{
            "name": "Card 1",
            "qfmt": _QUESTION_TEMPLATE,
            "afmt": _ANSWER_TEMPLATE,
        }],
        css=ANKI_CARD_CSS,
    )
