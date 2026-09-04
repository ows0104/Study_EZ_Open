"""판 교체 프롬프트는 **갈린 자리만** 읽힌다.

전 페이지를 읽히면 새로 만드는 것과 비용이 같아진다. 그렇다고 갈린 한 장만 떼어
보여 주면 그 장이 어느 흐름의 어디인지 모른다 — 앞뒤 한 장을 같이 연다.
"""

import json

from pdf2anki import assemble, schema, slidediff
from pdf2anki import prep as prep_mod


def page(no, text):
    return {"slide": no, "size": [960, 540], "lecture_text": text,
            "lecture_figures": [], "lecture_emphasis": [], "annotations": [],
            "markers": [], "pasted_images": [], "occlusion_candidates": [],
            "covered_by_annotation": []}


def prep_of(texts, source="x_v1.pdf"):
    return {"source": source, "source_sha256": "sha", "slides": len(texts),
            "annotated_pdf": "annotated.pdf", "clean_pdf": "clean.pdf",
            "channel_policy": {"lecture_text": "근거 가능"},
            "lecture_palette": {"body_color": None, "colors": {}, "template_slots": []},
            "annotation_years": {}, "stamp_markers": {}, "badge_failed_slides": [],
            "slides_with_covered_lecture_content": [],
            "pages": [page(i + 1, t) for i, t in enumerate(texts)]}


BODY = ["표지", "생활사", "excyst 는 duodenum 에서", "감별", "치료", "정리"]


def test_갈린_슬라이드와_그_앞뒤만_읽힌다(tmp_path):
    old = prep_of(BODY)
    new = prep_of(list(BODY), "x_v2.pdf")
    new["pages"][2] = page(3, "성충은 폐에서 worm capsule 안에 자리잡는다")

    (tmp_path / "prep.json").write_text(json.dumps(new, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "prep.md").write_text(prep_mod.to_markdown(new), encoding="utf-8")
    schema.dump(tmp_path / "schema")

    diff = slidediff.diff(old, new, hints=[5])
    assert diff["changed_slides"] == [3, 5]

    res = assemble.assemble(tmp_path, None, tmp_path / "schema", "base", revise=diff)
    text = "\n".join((tmp_path / f["name"]).read_text(encoding="utf-8")
                     for f in res["revise"])

    assert 'pages="2-6"' in text                  # 3±1 과 5±1 이 이어진 구간
    assert 'pages="1-6"' not in text              # 전 페이지를 읽히지 않는다
    assert "Slide 3" in text and "Slide 5" in text
    assert "items.carry.json" in text             # 남은 카드를 보고 겹치지 않게 쓴다
    assert "revise.out.json" in text

    # ① 목표·② 카드 프롬프트는 그대로 남는다 — 통째로 다시 만드는 길이 막히면 안 된다
    assert res["plan"] and res["cards"]


def test_revise_가_지어_둔_블록이_있으면_그것을_싣는다(tmp_path):
    """`change_block` 에는 갈린 문구·그 자리의 카드·v1 의 판단이 들어 있다.
    채널 이름만 실으면 모델이 오타인지 내용 정정인지 가릴 수 없다."""
    new = prep_of(BODY, "x_v2.pdf")
    (tmp_path / "prep.json").write_text(json.dumps(new, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "prep.md").write_text(prep_mod.to_markdown(new), encoding="utf-8")
    schema.dump(tmp_path / "schema")

    diff = slidediff.diff(prep_of(BODY), new, hints=[3])
    diff["prompt_block"] = "## 갈린 슬라이드\n\n### Slide 3\n- `c012` [basic] Q. 어디에서 성충이 되는가?"

    res = assemble.assemble(tmp_path, None, tmp_path / "schema", "base", revise=diff)
    text = "\n".join((tmp_path / f["name"]).read_text(encoding="utf-8") for f in res["revise"])
    assert "`c012`" in text                      # 카드가 프롬프트에 실렸다
    assert "items.carry.json" in text            # 남은 카드를 볼 자리도 알려 준다
    assert "keep" in text and "revise" in text and "drop" in text


def test_앞뒤_한_장은_슬라이드_범위를_넘지_않는다():
    assert assemble.revise_pages([1], 6) == [1, 2]
    assert assemble.revise_pages([6], 6) == [5, 6]
    assert assemble.revise_pages([], 6) == []
