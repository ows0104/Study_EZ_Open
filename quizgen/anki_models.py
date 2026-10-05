"""Anki 노트의 CSS, 필드, 모델 정의와 안정적인 모델/덱 ID.

복습 빌드는 이 모듈의 MODELS를 쓰고, 예습은 같은 CSS/필드로 별도 모델을 만든다.
기존 Anki 복습 이력을 유지하려면 모델 이름, ID, 필드 순서를 보존해야 한다.
"""

import hashlib

import genanki

CSS = """
.card { font-family: -apple-system, "Segoe UI", "Malgun Gothic", sans-serif;
        font-size: 20px; line-height: 1.6; text-align: center;
        color: #1a1a1a; background: #ffffff; padding: 16px; }
.nightMode.card, .card.nightMode { color: #e8e8e8; background: #1e1e1e; }
.q { font-size: 22px; font-weight: 600; margin-bottom: 12px; white-space: pre-line; }
/* **가운데로 모으되 줄은 각자 쓴다.** `.a`·`.warn`·`.exam` 은 안쪽 글을 왼쪽으로
   세우면서 덩어리 자체는 가운데 두려고 `display: inline-block` 이었는데, 그러면
   이웃한 inline-block 과 **같은 줄에 나란히 선다.** 2026-09-03 에 예습 덱에서
   그것이 났다 — 답 아래 있어야 할 해설(`.bridge`)이 짧은 답 옆으로 붙었다.
   폭이 좁아 다음 줄로 밀리기도 해서 편마다 다르게 보인다.
   `display: block` + `width: fit-content` 는 생김새가 같으면서 줄을 안 나눠 쓴다.

   **다만 그 바꿈이 뒷면의 세로 간격을 통째로 반으로 줄였다.** inline-block 은 위아래
   margin 이 이웃과 합쳐지지 않는데 block 은 **붙어 있는 형제끼리 상쇄된다**(margin
   collapsing) — 둘 중 큰 것 하나만 남는다. `.a` 아래 12px 와 `.warn` 위 12px 는
   24px 이었는데 12px 이 됐고, 답과 노란 상자가 붙어 나왔다(2026-09-03 관리자 보고).
   같은 자리가 여럿이라 "다른 것도 가끔" 그래 보인 것이다.

       답 → 경고        24 → 12        답 → 기출 원문    24 → 12
       답 → 해설        22 → 12        답 → 출처         26 → 14
       경고 → 해설      22 → 12        구분선 → 답       26 → 14

   **그래서 아래 요소들은 간격을 더하지 않고 혼자 정한다.** 아래쪽 margin 을 0 으로
   두고 **뒤에 오는 것의 위쪽 margin 하나가** 그 사이를 책임진다. 상쇄가 큰 쪽을
   남기므로 그 값이 그대로 눈에 보이는 간격이 된다. 여기 숫자를 고칠 때는 앞 요소의
   아래쪽이 아니라 **뒤 요소의 위쪽**을 만져라. */
.a { font-size: 24px; font-weight: 700; color: #0b5cad; margin: 26px auto 0;
     display: block; width: -webkit-fit-content; width: fit-content;
     text-align: left; max-width: 100%; white-space: pre-line; }
.nightMode .a { color: #7ab8f5; }
/* 답이 통째로 파라면 그 안에서 강조가 서지 않는다. 강조할 자리를 찾은 답만 본문 색을
   내리고(`.body`) 회수 핵심에만 파랑을 남긴다. 자리를 못 찾은 답 — 대개 한 덩어리가
   그대로 회수 대상인 짧은 답 — 은 `.body` 가 없어 예전처럼 통째로 파랗다. */
/* 프레임은 **읽기만 하면 되는 글자다.** 회수 대상과 같은 무게로 서 있으면 눈이 매번
   전부를 훑는다 — 답 글자의 중앙 43% 가 이 부분이다. 한 단계 눌러 강조에 먼저 앉게
   한다. 지우지는 않는다 — 답이 무슨 말인지는 프레임이 쥐고 있다.
   **글자 크기는 건드리지 않는다.** `.key` 가 `.body` 안에 들어 있어서(`render_answer`)
   `em` 으로 줄이면 강조까지 같이 줄어든다. */
.a .body { color: #4a4a4a; font-weight: 500; }
.nightMode .a .body { color: #b0b0b0; }
.a .key { color: #0b5cad; font-weight: 700; }
.nightMode .a .key { color: #7ab8f5; }
/* 빈칸 카드는 `a` 필드를 안 쓰고 뒷면이 문장을 통째로 다시 그린다. Anki 가 드러난
   답을 `.cloze` 로 감싸 주는데 규칙이 없어서, 뒷면이 앞면과 똑같아 보였다 —
   무엇을 회수해야 했는지 눈으로 못 찾는다. `.a` 와 같은 색·굵기를 준다.
   앞면의 `[...]` 도 같은 규칙을 타서 어디가 빈칸인지 함께 드러난다. */
.cloze { font-weight: 700; color: #0b5cad; }
.nightMode .cloze { color: #7ab8f5; }
.a ul { text-align: left; margin: 4px 0; padding-left: 1.15em; }
.a li { margin: 3px 0; }
.a ul ul { margin: 2px 0 2px 0; padding-left: 1.0em; font-size: 0.94em; font-weight: 600; }
.a .lead { margin-bottom: 5px; }
img { max-width: 100%; height: auto; border-radius: 4px; }
hr { border: none; border-top: 1px solid #d8d8d8; margin: 14px 0; }
.nightMode hr { border-top-color: #3a3a3a; }
/* **경고는 세 층으로 나뉜다** (2026-09-03 관리자 지시). 가르는 축은 「푸는 사람이 지금
   할 일이 있나」이고, 층마다 보이는 세기가 다르다. 어느 층인지는 `WARN_*` 표가 정한다.

     ① .warn    답을 그대로 믿지 마라   노란 상자로 답 아래 선다
     ② .minor   카드가 반쪽이다        접힌 출처 안, 출처 줄 바로 아래
     ③ .chore   기록용 잔소리          접힌 출처 안, ② 아래

   **카드 겉면에 남는 것은 ① 뿐이다**(2026-09-03 관리자 지시). ② 는 풀다 막혔을 때
   왜 막혔는지 알려 주는 값이라 없애지는 않지만, 안 막힌 사람에게는 볼 것이 아니다.

   나누기 전에는 셋이 한 상자였다. 실측하면 「자료 주의」로 뜬 272건 중 202건(74%)이
   ③ 이었다 — 노란 상자가 거의 잔소리 전용이었던 셈이라, 정작 ① 이 그 속에 묻혔다. */
.warn { border-left: 4px solid #d08700; background: #fff8e6; padding: 8px 12px;
        margin: 24px auto 0; font-size: 16px; border-radius: 3px;
        display: block; width: -webkit-fit-content; width: fit-content;
        text-align: left; max-width: 100%; }
.warn .h { font-weight: 700; color: #8a5a00; }
.nightMode .warn { background: #33290f; border-left-color: #d0a040; }
.nightMode .warn .h { color: #e8bc60; }
/* ②·③ 은 접힌 출처 안에 든다. 카드에서 치우지는 않는다 — 표시가 `suspects.json` 에만
   있으면 볼 일이 없다는 것이 CLAUDE.md 「계수기는 아직 사람을 부를 줄 모른다」의
   결론이다. 펴 보면 있고, 안 펴면 안 보인다.
   둘을 같은 자리에 두되 색과 크기로 층을 남긴다 — ② 가 ③ 보다 진하고 크다. */
.minor { font-size: 14px; color: #7a7a7a; margin-top: 9px; text-align: center; }
.nightMode .minor { color: #909090; }
.chore { font-size: 13px; color: #a2a2a2; margin-top: 6px; text-align: center; }
.nightMode .chore { color: #6f6f6f; }
.exp { font-size: 17px; color: #444; margin: 22px auto 0;
       display: block; text-align: center; max-width: 100%; }
.nightMode .exp { color: #b8b8b8; }
.src { font-size: 14px; color: #888; margin-top: 6px; text-align: center; }
.ox { font-size: 30px; font-weight: 800; letter-spacing: 6px; margin-top: 26px; }
.slide { margin-top: 16px; border: 1px solid #ddd; display: inline-block;
         line-height: 0; background: #fff; }
.nightMode .slide { border-color: #444; }
.slide img { display: block; }
.fold { margin: 22px auto 0; text-align: center; max-width: 100%; display: block; }
.fold > summary { cursor: pointer; font-size: 15px; color: #6a6a6a; list-style: none;
                  padding: 6px 0; border-top: 1px solid #e2e2e2; user-select: none; }
.fold > summary::before { content: "▸ "; }
.fold[open] > summary::before { content: "▾ "; }
.nightMode .fold > summary { color: #9a9a9a; border-top-color: #3a3a3a; }
.origin { margin-top: 24px; }
/* 기출 원문은 왼쪽으로 세운다. 선지가 줄줄이 붙는 덩어리라 가운데 정렬하면
   줄마다 시작점이 달라져 읽는 눈이 매번 처음을 다시 찾는다. */
.exam { font-size: 15px; color: #555; margin: 24px auto 0; white-space: pre-line;
        display: block; width: -webkit-fit-content; width: fit-content;
        text-align: left; max-width: 100%; }
.exam .h { font-weight: 700; color: #0b5cad; }
.nightMode .exam { color: #b0b0b0; }
.nightMode .exam .h { color: #7ab8f5; }
"""

# 뒷면 공통 꼬리. **순서가 기원에 따라 다르다.**
#
#     기출     정답 · 해설 · 경고① · 기출 원문 · 출처(접힘 · 경고②③) · 참고 슬라이드
#     강의록   정답 · 해설 · 경고① · 참고 슬라이드 · 출처(접힘 · 경고②③)
#
# 기출 카드에서 원본은 족보 문항 자체다. 그래서 원문이 해설 바로 뒤에 서고, 그 문항이
# 실린 지면은 맨 끝으로 간다 — 글로 읽어 확인이 끝나는데 지면 사진이 그 사이를 막고
# 있을 이유가 없다. 강의록 카드는 반대다. 원본이 슬라이드라서 답 다음으로 볼 것이 그것이다.
#
# 해설은 접지 않는다. 접어 두면 답만 보고 넘기게 되는데, 왜 그런가가 답과 같은 무게라는
# 것이 이 덱의 전제다(CLAUDE.md 「암기와 이해는 동등하다」). 접는 것은 출처 한 줄뿐이다.
# 경고도 접지 않는다 — 자료가 미덥지 않다는 사실은 카드 안에서 보여야 한다.
#
# **다만 경고가 해설보다 앞에 서지는 않는다.** 2026-09-03 이전에는 답 바로 밑이었는데,
# 그러면 답 다음으로 읽히는 것이 해설이 아니라 곁말이 된다. 관리자가 자리를 바꾸라고
# 했고(*"해설과 위치를 바꾸고 저거를 좀 더 눈에 덜 띄게 하자"*) 생김새도 같이 낮췄다
# (`.warn` — 바탕 없는 14px 회색). **예습 덱은 처음부터 이 순서였다**(`prequiz/build.py`
# 의 `PRE_TAIL`) — 복습만 반대였던 것이라, 바꾼 것이 아니라 맞춘 것이다.
# 「정답 의심」·「족보 검토」도 같은 `Warning` 필드라 함께 내려간다.
#
# **순서를 템플릿이 정하지 않는다.** Anki 템플릿은 필드가 비었나만 볼 수 있어서 한 벌로
# 두 순서를 낼 수 없고, 갈라내려고 필드를 늘리면 이미 임포트한 덱의 노트 타입이 흔들린다.
# 그래서 `Source` 에 **해설 뒤에 올 것을 순서대로 조립해** 담는다(`tail_of`).
# `SlideImage` 는 강의록 카드의 슬라이드만 든다 — 기출 카드에서는 비어 있고, 그 이미지는
# `Source` 꼬리의 맨 끝에 들어간다.
TAIL = ('{{#Explanation}}<div class="exp">{{Explanation}}</div>{{/Explanation}}'
        '{{Warning}}'
        '{{#SlideImage}}<div class="origin">{{SlideImage}}</div>{{/SlideImage}}'
        '{{Source}}')


def _mid(name: str) -> int:
    """이름에서 안정적인 모델/덱 ID 를 만든다. 다시 빌드해도 같아야 한다."""
    return int(hashlib.sha256(name.encode()).hexdigest()[:8], 16)


FIELDS = [{"name": n} for n in
          ("Question", "Answer", "Explanation", "Warning", "Source", "Image", "SlideImage")]


def _model(name: str, qfmt: str, afmt: str) -> genanki.Model:
    return genanki.Model(_mid(name), name, fields=FIELDS,
                         templates=[{"name": "Card 1", "qfmt": qfmt, "afmt": afmt}], css=CSS)


# 답 앵커. **이것이 뒷면의 스크롤 구조 전부다.**
#
# Anki 는 뒷면을 그린 뒤 `id="answer"` 인 요소를 찾아 그 자리로 스크롤한다. 그래서
# 질문은 화면 위로 밀려나고 답이 맨 위에 서며, 질문을 다시 보려면 위로 올리면 된다.
# 앵커가 없으면 Anki 는 스크롤을 건드리지 않는다 — 뒷면이 맨 위에서 시작해 질문이
# 화면을 차지한 채 답은 그 아래 남는다. 실제로 네 형식 모두 그 상태였다.
#
# 이미지 카드에서는 앵커가 **그림 뒤**에 온다. 그래야 답이 맨 위에 서고, 위로 올리면
# 질문 → 그림 순으로 보인다.
ANCHOR = '<hr id="answer">'

MODELS = {
    "basic": _model("PDF2ANKI Basic",
                    '<div class="q">{{Question}}</div>',
                    '<div class="q">{{Question}}</div>' + ANCHOR +
                    '<div class="a">{{Answer}}</div>' + TAIL),
    "ox": _model("PDF2ANKI OX",
                 '<div class="q">{{Question}}</div><div class="ox">O / X</div>',
                 '<div class="q">{{Question}}</div>' + ANCHOR +
                 '<div class="ox">{{Answer}}</div>' + TAIL),
    # 이미지 카드는 질문이 사진 **위**에 온다. 질문이 비어 있어도 성립한다.
    "image_basic": _model("PDF2ANKI Image",
                          '{{#Question}}<div class="q">{{Question}}</div>{{/Question}}'
                          '<div>{{Image}}</div>',
                          '{{#Question}}<div class="q">{{Question}}</div>{{/Question}}'
                          '<div>{{Image}}</div>' + ANCHOR +
                          '<div class="a">{{Answer}}</div>' + TAIL),
    "image_occlusion": _model("PDF2ANKI Occlusion",
                              '{{#Question}}<div class="q">{{Question}}</div>{{/Question}}'
                              '<div>{{Image}}</div>',
                              '{{#Question}}<div class="q">{{Question}}</div>{{/Question}}'
                              + ANCHOR + '<div>{{Answer}}</div>' + TAIL),
}
CLOZE_MODEL = genanki.Model(
    _mid("PDF2ANKI Cloze"), "PDF2ANKI Cloze",
    fields=[{"name": "Text"}, {"name": "Extra"}, {"name": "Warning"},
            {"name": "Source"}, {"name": "SlideImage"}],
    templates=[{"name": "Cloze",
                "qfmt": '<div class="q">{{cloze:Text}}</div>',
                # 빈칸 카드의 해설은 `Extra` 에 든다. 나머지 순서는 TAIL 과 같다.
                "afmt": '<div class="q">{{cloze:Text}}</div>'
                        '{{#Extra}}<div class="exp">{{Extra}}</div>{{/Extra}}'
                        '{{Warning}}'
                        '{{#SlideImage}}<div class="origin">{{SlideImage}}</div>'
                        '{{/SlideImage}}'
                        '{{Source}}'}],
    css=CSS, model_type=genanki.Model.CLOZE)
