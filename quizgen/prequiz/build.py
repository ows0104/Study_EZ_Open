"""검증된 예습 카드를 `.apkg` 로 만든다.

**렌더링 부품은 복습 쪽 것을 쓴다** — CSS, 답 앵커, 그림 크롭, 족보 지면,
접촉 시트, 재개봉 검증. 손으로 다듬어 둔 것을 다시 만들 이유가 없다.

여기서만 다른 것은 넷이다.
  · **뒷면에서 `explanation` 을 펼쳐 보인다.** 복습은 접는다 — 77장짜리 덱에서 매 장
    해설을 펼치면 회독이 느려지기 때문이다. 예습은 그 해설이 「이것이 수업에서 어디에
    쓰이는지」를 잇는 다리이고 목적의 절반이라, 접어 두면 아무도 안 누른다.
    그래서 노트 모델을 따로 뒀다 (`PDF2ANKI Prequiz *`).
  · 덱이 하나다. `<과목>::<강의>::예습`. 복습처럼 강의록/기출로 가르지 않는다 —
    예습 덱은 10~15장이라 나누면 조각만 남고, 출처는 태그로 이미 갈린다.
  · guid 씨앗에 `::pre` 를 붙인다. 복습 카드와 질문이 같아져도 Anki 가 한 노트로
    보지 않게 하기 위해서다. **이것이 없으면 한쪽이 다른 쪽을 덮는다.**
  · 재현 검사 결과가 있으면 반영하되, 없다고 덱을 막지는 않는다 (`--require-reproduce` 로 켠다).

사용:
    python -m quizgen.prequiz.build out/pre_xxx --deck "병리학::종양의 분자생물학(1)::예습" --id p250825_01
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import Counter
from pathlib import Path

import genanki

from .. import site_edits
from ..build import (
    ANCHOR,
    CSS,
    DEFECT_REASONS,
    FIELDS,
    GuidClash,
    Jokbo,
    Media,
    _labels,
    _mid,
    check_guids,
    collapse_cloze,
    contact_sheet,
    find_jokbo_source,
    guid_of,
    print_site_edits,
    render_answer,
    verify,
)
from .schema import MAX_CARDS, MIN_CARDS, WHY_TAG_LABEL

# ── 노트 모델 — 복습과 뒷면 구조가 다르다 ─────────────────────────
#
# 복습 덱은 `explanation` 을 「출처 · 해설」 접힘 안에 넣는다. 카드가 77장까지 가는
# 덱에서 매 장 해설을 펼쳐 보이면 회독이 느려지기 때문이다.
#
# **예습은 반대다.** 예습 카드의 `explanation` 은 「이것이 수업에서 어디에 쓰이는지」를
# 잇는 다리이고, 그게 이 덱의 목적 절반이다. 접어 두면 아무도 안 누른다.
# 답 바로 아래 펼쳐 놓는다.
#
# 모델 이름을 복습과 다르게 둔다. 같은 이름에 다른 템플릿을 넣으면 Anki 가 임포트할 때
# 한쪽 노트 타입을 덮어써 **복습 덱의 뒷면까지 바뀐다.**
# **해설은 답 아래 줄에 선다.** `display: inline-block` 이던 동안 짧은 답과 짧은 해설이
# 한 줄에 나란히 붙었다(2026-09-03 관리자 보고). 이웃 `.a` 도 inline-block 이라 둘이
# 같은 줄 상자를 나눠 쓴 것이다 — 공용 CSS 쪽에서 함께 고쳤다.
# 위쪽 경계선이 답 전체 폭으로 늘어지지 않게 `fit-content` 는 그대로 둔다.
# 간격은 공용 CSS 와 같은 규칙을 탄다 — `.a` 아래쪽이 0 이므로 **여기 위쪽 하나가**
# 답과의 사이를 정한다. 12+14 로 더해지던 26px 을 그대로 적는다.
PRE_CSS = CSS + """
.bridge { border-top: 1px solid #e2e2e2; margin: 26px auto 0; padding-top: 10px;
          font-size: 17px; line-height: 1.55; color: #3a3a3a;
          text-align: left; max-width: 100%;
          display: block; width: -webkit-fit-content; width: fit-content; }
.nightMode .bridge { color: #c6c6c6; border-top-color: #3a3a3a; }
.why { display: block; margin: 0 auto 12px; font-size: 14px; line-height: 1.5;
       color: #6a6a6a; font-weight: normal; }
.why .tag { display: inline-block; margin-right: 6px; padding: 1px 7px; border-radius: 9px;
            background: #eef1f6; color: #4a5568; font-size: 12px; font-weight: 600; }
.why .tag.challenge { background: #fff1e0; color: #a0521a; }
.why-back { margin-bottom: 8px; font-size: 15px; color: #555; }
.why-back .lbl { margin-right: 8px; font-size: 12px; font-weight: 700; color: #888; }
.nightMode .why-back { color: #b8b8b8; }
.nightMode .why-back .lbl { color: #8a8a8a; }
.why .tag.exam { background: #fdecec; color: #b42318; }
.why .tag.clinical { background: #e6f6f2; color: #0f766e; }
.why .tag.later { background: #edf2fe; color: #3a5bc7; }
.why .tag.annotation { background: #f3eefe; color: #6d3fc0; }
.nightMode .why .tag.exam { background: #46201f; color: #f4a3a0; }
.nightMode .why .tag.clinical { background: #133b36; color: #7fd8c7; }
.nightMode .why .tag.later { background: #1d2a52; color: #a9bcff; }
.nightMode .why .tag.annotation { background: #33255a; color: #c9b2fa; }
.nightMode .why { color: #a8a8a8; }
.nightMode .why .tag { background: #2e3440; color: #c9d1dc; }
.nightMode .why .tag.challenge { background: #4a3420; color: #f2c089; }
"""

# 답 다음에 다리, 그다음 원본 슬라이드. 출처만 접는다.
PRE_TAIL = ('{{#Explanation}}<div class="bridge">{{Explanation}}</div>{{/Explanation}}'
            '{{#SlideImage}}<div class="origin">{{SlideImage}}</div>{{/SlideImage}}'
            '{{Warning}}'
            '<details class="fold"><summary>출처</summary>{{Source}}</details>')


def _pre_model(name: str, qfmt: str, afmt: str) -> genanki.Model:
    return genanki.Model(_mid(name), name, fields=FIELDS,
                         templates=[{"name": "Card 1", "qfmt": qfmt, "afmt": afmt}],
                         css=PRE_CSS)


MODELS = {
    "basic": _pre_model("PDF2ANKI Prequiz Basic",
                        '<div class="q">{{Question}}</div>',
                        '<div class="q">{{Question}}</div>' + ANCHOR +
                        '<div class="a">{{Answer}}</div>' + PRE_TAIL),
    "ox": _pre_model("PDF2ANKI Prequiz OX",
                     '<div class="q">{{Question}}</div><div class="ox">O / X</div>',
                     '<div class="q">{{Question}}</div>' + ANCHOR +
                     '<div class="ox">{{Answer}}</div>' + PRE_TAIL),
    "image_basic": _pre_model("PDF2ANKI Prequiz Image",
                              '{{#Question}}<div class="q">{{Question}}</div>{{/Question}}'
                              '<div>{{Image}}</div>',
                              '{{#Question}}<div class="q">{{Question}}</div>{{/Question}}'
                              '<div>{{Image}}</div>' + ANCHOR +
                              '<div class="a">{{Answer}}</div>' + PRE_TAIL),
    "image_occlusion": _pre_model("PDF2ANKI Prequiz Occlusion",
                                  '{{#Question}}<div class="q">{{Question}}</div>{{/Question}}'
                                  '<div>{{Image}}</div>',
                                  '{{#Question}}<div class="q">{{Question}}</div>{{/Question}}'
                                  + ANCHOR + '<div>{{Answer}}</div>' + PRE_TAIL),
}

CLOZE_MODEL = genanki.Model(
    _mid("PDF2ANKI Prequiz Cloze"), "PDF2ANKI Prequiz Cloze",
    fields=[{"name": "Text"}, {"name": "Extra"}, {"name": "Warning"},
            {"name": "Source"}, {"name": "SlideImage"}],
    templates=[{"name": "Cloze",
                "qfmt": '<div class="q">{{cloze:Text}}</div>',
                "afmt": '<div class="q">{{cloze:Text}}</div>'
                        '{{#Extra}}<div class="bridge">{{Extra}}</div>{{/Extra}}'
                        '{{Warning}}'
                        '{{#SlideImage}}<div class="origin">{{SlideImage}}</div>'
                        '{{/SlideImage}}'
                        '<details class="fold"><summary>출처</summary>{{Source}}'
                        '</details>'}],
    css=PRE_CSS, model_type=genanki.Model.CLOZE)

def why_of(c: dict) -> str:
    """앞면 질문 위에 붙는 배지 줄 — 도전 문제 표시와 「왜 냈나」의 유형(2026-10-04 관리자).

    **이유를 적은 글은 여기 없다** — 답 뒤로 간다(`why_back`). 관리자: 「문제 풀기 전에는
    배지만 보이고, 풀고 나서 이유가 보이는 건 어때」. 도전 문제의 「강의의 ‘○○’ 대목에서
    풀린다」가 앞면에 있으면 답의 절반을 알려 줬다.

    **필드를 새로 두지 않고 질문 칸 머리에 넣는다.** 노트 모델에 칸을 늘리면 이미 예습
    덱을 받은 사람의 Anki 가 같은 이름의 노트 타입을 하나 더 만든다. guid 는 `q` 로
    잡으므로 안 바뀐다.
    """
    tags = '<span class="tag challenge">도전 문제</span>' if c.get("challenge") else ""
    # 모르는 값은 안 그린다.
    tags += "".join(f'<span class="tag {t}">{WHY_TAG_LABEL[t]}</span>'
                    for t in c.get("why_tags") or [] if t in WHY_TAG_LABEL)
    return f'<div class="why">{tags}</div>' if tags else ""


def why_back(c: dict) -> str:
    """답 뒤 해설 칸 머리에 붙는 「왜 냈나」 글. 해설 칸은 뒷면에만 그려진다."""
    why = (c.get("why_asked") or "").strip()
    if not why:
        return ""
    return f'<div class="why-back"><span class="lbl">왜 냈나</span>{html.escape(why)}</div>'


# 층은 복습과 같은 축으로 가른다(`build.WARN_TRUST` 첫머리). 예습에만 있는 셋의 자리:
#   `repeated_without_jokbo_ref` → ①  「반복 출제라서 냈다」는 근거가 없다는 말이다
#   `missing_bridge_to_lecture`  → ②  답은 맞는데 수업으로 잇는 다리가 없다
#   `off_must`                   → ③  승인본과 안 맞는 것은 덱을 다시 만들 때 볼 일이다
# 「왜 냈나」(2026-10-04)의 넷도 같은 축이다 — 기출을 말하는데 문항이 없으면 ①
# (근거 없는 이유를 학생에게 보인 것), 비었으면 ②, 길면 ③.
WARN_TRUST = {
    "repeated_without_jokbo_ref": "반복 출제를 이유로 들었는데 근거 문항이 없다",
    "why_cites_exam_without_ref": "「왜 냈나」가 기출을 말하는데 근거 문항이 없다",
}

WARN_MINOR = {
    "points_at_source": "질문이 원본 자료를 가리킨다",
    "answer_leaked_in_question": "정답 단서가 질문에 노출됐을 수 있다",
    "occlusion_answer_leaked_in_question": "가린 라벨이 질문에 그대로 나온다",
    "ox_is_question_not_statement": "O/X 카드인데 진술문이 아니다",
    "missing_bridge_to_lecture": "수업으로 잇는 해설이 없다",
    "missing_why_asked": "왜 이 문제를 냈는지가 비어 있다",
    "why_tag_not_in_signals": "「왜 냈나」 배지가 승인된 근거에 없는 유형이다",
}

WARN_CHORE = {
    "similar_duplicate": "다른 카드와 회수 방향이 겹칠 수 있다",
    "too_many_items": "한 번에 회수할 항목이 많다 — 예습 카드는 하루에 외워져야 한다",
    "too_many_clozes": "가린 곳이 많다",
    "question_too_long": "질문이 길다",
    "why_asked_too_long": "「왜 냈나」가 길다",
    "missing_why_tags": "「왜 냈나」의 유형 배지가 없다",
    "off_must": "승인된 must-know 항목 어디에도 안 붙는 카드다",
    "media_on_text_card": "그림이 붙지 않는 형식인데 media 가 있었다 (제거됨)",
    "jokbo_ref_outside_slice": "족보 조각에 없는 연도의 기출이다",
    "jokbo_ref_not_found": "인용한 기출 문항을 족보에서 찾지 못했다",
}

FLAG_LABEL = {**WARN_TRUST, **WARN_MINOR, **WARN_CHORE}

REASON_TAG = {
    "spine": "1-뼈대", "vocabulary": "2-용어", "mechanism": "3-기전",
    "clinical": "4-임상", "repeated": "5-반복출제",
}


def guid_seed(lecture_id: str) -> str:
    """복습 덱과 절대 겹치지 않게 한다.

    `build.py` 의 guid 는 `(강의 ID, 정규화한 질문)` 이다. 예습과 복습이 같은 용어를
    같은 문장으로 물으면 — 용어 카드에서 충분히 일어난다 — 두 노트의 guid 가 같아지고,
    Anki 는 나중에 임포트한 쪽을 **기존 노트의 수정**으로 처리한다. 한 장이 사라진다.
    """
    return f"{lecture_id}::pre"


def tags_of(c: dict, lecture_id: str) -> list[str]:
    t = ["예습", f"강의::{lecture_id}",
         f"이유::{REASON_TAG.get(c['reason'], c['reason'])}",
         f"형식::{c['card_format']}", f"유형::{c['card_type']}",
         f"출처::{c['source_type']}"]
    if c.get("slide_no"):
        t.append(f"슬라이드::{c['slide_no']:02d}")
    if c.get("jokbo_ref"):
        t.append(f"기출::{c['jokbo_ref']['year']}-{c['jokbo_ref']['no']}")
    if c.get("challenge"):
        t.append("도전문제")
    if c.get("review_flags"):
        t.append("검토필요")
    r = c.get("reproduce") or {}
    if r.get("verdict"):
        t.append(f"재현::{r['verdict']}")
    return t


def warning_of(c: dict) -> str:
    """`Warning` 필드. 복습과 같은 층·같은 생김새다 (`build.warning_of` 첫머리).

    ① 만 카드 겉면에 남는다. ②·③ 은 접힌 출처 안으로 간다(`fold_notes_of`).
    """
    trust = []
    if c.get("review_note"):
        trust.append(f'<span class="h">검토</span><br>{html.escape(c["review_note"])}')
    if flags := _labels(c, WARN_TRUST):
        trust.append('<span class="h">자료 주의</span><br>' + " · ".join(flags))

    return '<div class="warn">' + "<br><br>".join(trust) + "</div>" if trust else ""


def fold_notes_of(c: dict) -> str:
    """접힌 출처 안에 들어갈 ②·③. 출처 줄 아래에 ② 가 먼저, ③ 이 나중이다."""
    out = ""
    if minor := _labels(c, WARN_MINOR):
        out += '<div class="minor">' + html.escape(" · ".join(minor)) + "</div>"
    if chore := _labels(c, WARN_CHORE):
        out += '<div class="chore">' + html.escape(" · ".join(chore)) + "</div>"
    return out


def source_of(c: dict, title: str) -> str:
    bits = [f"{title} · 예습"]
    if c.get("slide_no"):
        bits.append(f"작년 Slide {c['slide_no']}")
    if c.get("jokbo_ref"):
        r = c["jokbo_ref"]
        bits.append(f"기출 {r['year']}-{r['no']} (반복 출제 근거)")
    return html.escape(" · ".join(bits))


def build(prep_dir: Path, deck_name: str, lecture_id: str, src: Path | None = None,
          apkg_name: str | None = None,
          jokbo_slice: Path | None = None, jokbo_pdf: Path | None = None,
          edits: list[dict] | None = None) -> dict:
    prep = json.loads((prep_dir / "prep.json").read_text(encoding="utf-8"))
    src = src or (prep_dir / "items.checked.json")
    cards = json.loads(src.read_text(encoding="utf-8"))["cards"]
    if edits:
        cards, _ = site_edits.apply(cards, edits)
    cards, folded = check_guids(cards, guid_seed(lecture_id), qkey=lambda q: q)
    if folded:
        print(f"  같은 카드 {folded}장을 접었다 (질문·답·그림이 전부 같다)")
    title = deck_name.split("::")[-2] if "::" in deck_name else deck_name
    media = Media(prep_dir, prep, lecture_id, prep_dir / "media")
    jokbo = Jokbo(jokbo_slice, jokbo_pdf, lecture_id, prep_dir / "media")

    deck = genanki.Deck(_mid(deck_name), deck_name)
    seed = guid_seed(lecture_id)
    stats = Counter()
    # **그림을 만든 자리가 이름을 넘긴다.** 검수 PDF 가 `figure_id` 와 crop 으로 이름을
    # 다시 유추하면 가림이 붙은 판을 못 찾아 빌드가 통째로 죽는다 (복습 쪽은 d6ae3e3
    # 에서 고쳤는데 이 호출부만 옛 시그니처로 남아 예습 덱이 전부 죽고 있었다).
    rendered: dict[int, tuple[str, ...]] = {}

    for c in cards:
        fmt = c["card_format"]
        # 사이트에서 질문을 고친 카드는 원래 질문으로 씨앗을 잡는다(`site_edits` 머리).
        guid = guid_of(seed, site_edits.guid_q(c), c)
        warn, srctxt, tags = warning_of(c), source_of(c, title), tags_of(c, lecture_id)
        notes = fold_notes_of(c)
        exp = why_back(c) + html.escape(c.get("explanation") or "").replace("\n", "<br>")
        origin = (f'<div class="slide"><img src="{media.slide(c["slide_no"])}"></div>'
                  if c.get("slide_no") else "")
        if c.get("jokbo_ref"):
            exam_text, exam_imgs = jokbo.block(c["jokbo_ref"])
            origin += exam_imgs
            if exam_text:
                srctxt += exam_text
        # 출처 안쪽을 여기서 조립한다 — ②·③ 층 경고가 출처 줄 아래 붙는다.
        srctxt = f'<div class="src">{srctxt}</div>{notes}'

        m = c.get("media") or {}
        crop = m.get("crop")

        if fmt == "cloze":
            # 복습과 같은 자리에서 번호를 모은다 (`build.collapse_cloze` 주석).
            note = genanki.Note(model=CLOZE_MODEL, guid=guid, tags=tags,
                                fields=[why_of(c) + collapse_cloze(c["q"]), exp, warn,
                                        srctxt, origin])
        else:
            img, answer = "", render_answer(c["a"])
            if fmt == "image_basic":
                name = media.figure(m["figure_id"], crop)
                rendered[id(c)] = (name,)
                img = f'<img src="{name}">'
            elif fmt == "image_occlusion":
                front, back = media.occlusion(m["figure_id"], m["occlusion_ids"], crop)
                rendered[id(c)] = (front, back)
                img, answer = f'<img src="{front}">', f'<img src="{back}">'
            note = genanki.Note(model=MODELS[fmt], guid=guid, tags=tags,
                                fields=[why_of(c) + html.escape(c["q"]), answer, exp, warn,
                                        srctxt, img, origin])
        deck.add_note(note)
        stats[fmt] += 1
        stats["이유:" + c["reason"]] += 1

    contact = contact_sheet(prep_dir, cards, media, lecture_id, rendered)
    apkg = prep_dir / f"{apkg_name or lecture_id + '_pre'}.apkg"
    pkg = genanki.Package([deck])
    pkg.media_files = ([str(p) for p in media.files.values()]
                       + [str(p) for p in jokbo.files.values()])
    pkg.write_to_file(apkg)
    return {"apkg": apkg, "n_notes": len(cards),
            "n_media": len(media.files) + len(jokbo.files),
            "stats": dict(stats), "contact": contact}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="검증된 예습 카드를 .apkg 로 만든다")
    ap.add_argument("prep_dir")
    ap.add_argument("--deck", required=True, help='"<과목>::<강의>::예습" 형태')
    ap.add_argument("--id", help="강의 ID (태그·파일명·guid 씨앗)")
    ap.add_argument("--jokbo-dir", default="out/jokbo")
    ap.add_argument("--jokbo-slice")
    ap.add_argument("--jokbo-pdf")
    ap.add_argument("--apkg-name", help="덱 파일 이름 (확장자 없이). 기본은 <강의 ID>_pre")
    ap.add_argument("--require-reproduce", action="store_true",
                    help="재현 검사 결과가 없으면 덱을 만들지 않는다")
    ap.add_argument("--allow-size", action="store_true",
                    help=f"{MIN_CARDS}~{MAX_CARDS}장 계약을 어겨도 만든다")
    ap.add_argument("--site-edits", help="사이트 「카드 검토」의 판정. runner 가 적는다 (quizgen/site_edits.py)")
    args = ap.parse_args(argv)

    prep_dir = Path(args.prep_dir)
    lecture_id = args.id or args.deck.split("::")[-2]

    done = prep_dir / "items.reproduced.json"
    if done.exists():
        src, how = done, "재현 검사 반영"
    elif args.require_reproduce:
        print(f"재현 검사 결과가 없다: {done}")
        return 1
    else:
        src, how = prep_dir / "items.checked.json", "재현 검사 없음"
    print(f"입력 {src.name} — {how}")

    cards = json.loads(src.read_text(encoding="utf-8"))["cards"]
    edits = site_edits.load(args.site_edits)
    if edits:
        cards, applied = site_edits.apply(cards, edits)
        print_site_edits(applied)
    n = len(cards)
    if not MIN_CARDS <= n <= MAX_CARDS:
        msg = f"카드가 {n}장이다 — 예습 덱의 계약은 {MIN_CARDS}~{MAX_CARDS}장이다"
        if not args.allow_size:
            print(f"{msg}. 그대로 만들려면 --allow-size")
            return 1
        print(f"⚠ {msg} (--allow-size 로 진행)")

    bad = [c for c in cards if (c.get("reproduce") or {}).get("reason") in DEFECT_REASONS]
    if bad:
        print(f"⚠ 재현 불가로 갈린 카드 {len(bad)}장이 그대로 들어간다")

    slice_path, pdf_path = find_jokbo_source(prep_dir, Path(args.jokbo_dir),
                                             args.jokbo_slice, args.jokbo_pdf)
    if slice_path:
        print(f"기출 원본: {slice_path.name} · {pdf_path.name if pdf_path else '(지면 없음)'}")

    try:
        res = build(prep_dir, args.deck, lecture_id, src, args.apkg_name,
                    slice_path, pdf_path, edits=edits)
    except GuidClash as e:
        print(f"\n{e}")
        return 1
    print(f"덱: {args.deck}   (강의 ID {lecture_id}, guid 씨앗 {guid_seed(lecture_id)})")
    print(f"노트 {res['n_notes']}장 · 미디어 {res['n_media']}개 → {res['apkg']}")
    print(f"형식·이유 {res['stats']}")
    if res["contact"]:
        print(f"\n⚠ 이미지 카드 검수: {res['contact']}")

    v = verify(res["apkg"], res["n_notes"], res["n_media"])
    if not v["ok"]:
        print("\nAPKG 재개봉 검증 실패:")
        for p in v["problems"]:
            print(f"   - {p}")
        return 1
    print(f"\nAPKG 재개봉 검증 통과 — 덱 {v['n_decks']}개 · 노트 {v['n_notes']} · "
          f"카드 {v['n_cards']} · 미디어 {v['n_media']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
