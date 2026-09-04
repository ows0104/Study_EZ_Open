"""진짜 PDF 두 판을 `prep` 에 통과시켜 끝까지 맞대 본다.

앞의 시험들은 손으로 지은 `prep.json` 을 쓴다. 그러면 **키 이름이 실제와 어긋나도
전부 통과한다** — 채널을 하나 못 읽으면 그 채널의 갈림은 영원히 안 보이는데,
가짜 사전으로는 그것을 못 잡는다. 여기서는 `pdf2anki.prep` 이 실제로 낸 것을 쓴다.
"""

import fitz

from pdf2anki import prep as prep_mod
from pdf2anki import revise, slidediff
from studyez import fingerprint

BODY = ["Life cycle of Paragonimus", "Excystation in the duodenum",
        "Adult worm in the lung"]


def make_pdf(path, texts, note=None, figures=()):
    doc = fitz.open()
    for i, text in enumerate(texts):
        page = doc.new_page(width=720, height=540)
        page.insert_text((72, 100), text, fontsize=18)
        if i + 1 in figures:
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 400, 400))
            pix.set_rect(pix.irect, (200, 30, 30))
            page.insert_image(fitz.Rect(200, 200, 480, 480), pixmap=pix)
        if note and note[0] == i + 1:
            page.add_freetext_annot(fitz.Rect(300, 300, 500, 340), note[1])
    doc.save(path)
    doc.close()
    return path


def build(tmp_path, name, texts, note=None, figures=()):
    src = make_pdf(tmp_path / name, texts, note, figures)
    out = tmp_path / f"out_{name}"
    return src, prep_mod.build(src, out)


def card(cid, slide, q="Q", media=None, fmt="basic"):
    c = {"id": cid, "q": q, "a": "A", "card_format": fmt, "card_type": "fact",
         "importance": "core", "source_type": "lecture",
         "evidence_type": "lecture_text", "exam_hit": False, "slide_no": slide}
    if media:
        c["media"] = media
    return c


def test_prep_이_원본의_지문을_적는다(tmp_path):
    src, prep = build(tmp_path, "v1.pdf", BODY)
    assert prep[fingerprint.KEY] == fingerprint.sha256_of(src)
    assert prep["source_bytes"] == src.stat().st_size


def test_같은_PDF_를_두_번_읽어도_갈린_슬라이드가_없다(tmp_path):
    """`prep` 이 실행마다 흔들리면 갈아 끼우기가 매번 전부를 다시 쓴다."""
    _, a = build(tmp_path, "a.pdf", BODY)
    _, b = build(tmp_path, "b.pdf", BODY)
    d = slidediff.diff(a, b)
    assert d["changed_slides"] == []
    assert d["skipped_channels"] == []
    assert len(d["carry_map"]) == 3


def test_필기_한_줄이_붙으면_그_슬라이드만_갈린다(tmp_path):
    _, a = build(tmp_path, "v1.pdf", BODY)
    _, b = build(tmp_path, "v2.pdf", BODY, note=(3, "폐에서 worm capsule 안에 성충이 된다"))
    d = slidediff.diff(a, b)
    assert d["changed_slides"] == [3]
    assert d["pairs"][2]["changed"] == ["annotations"]

    cards = [{"id": "c001", "q": "Q1", "a": "A", "card_format": "basic",
              "card_type": "fact", "importance": "core", "source_type": "lecture",
              "evidence_type": "lecture_text", "exam_hit": False, "slide_no": s}
             for s in (1, 2, 3)]
    keep, review, orphan = revise.split_cards(cards, d)
    assert [c["slide_no"] for c in keep] == [1, 2]
    assert [c["slide_no"] for c in review] == [3]     # 버리지 않고 모델에게 처분을 묻는다
    assert not orphan


def test_슬라이드가_끼면_뒤_카드의_번호와_그림_id_가_같이_밀린다(tmp_path):
    """새 판에서 슬라이드가 늘어나는 경우. **여기가 제일 조용히 틀리는 자리다** —
    카드는 `slide_no` 정수 하나로 묶이고, 그림 id(`fig_p02_01`)는 쪽 번호를 품는다.
    밀린 것을 안 밀어 주면 카드가 엉뚱한 지면을 가리키고, 그림은 아예 못 찾는다."""
    _, a = build(tmp_path, "v1.pdf", BODY, figures=(2,))
    _, b = build(tmp_path, "v2.pdf",
                 [BODY[0], "Newly added: metacercaria", *BODY[1:]], figures=(3,))

    d = slidediff.diff(a, b)
    assert d["added"] == [2]                       # 2번 자리에 한 장이 꼈다
    assert d["changed_slides"] == [2]              # 다시 쓸 곳은 그 한 장뿐
    assert d["carry_map"] == {"1": 1, "2": 3, "3": 4}

    cards = [card("c001", 1),
             card("c002", 2, fmt="image_basic", media={"figure_id": "fig_p02_01"}),
             card("c003", 3)]
    keep, review, orphan = revise.split_cards(cards, d)
    assert not review and not orphan               # 끼었다고 남의 카드를 건드리지 않는다
    assert [c["slide_no"] for c in keep] == [1, 3, 4]
    assert keep[1]["media"]["figure_id"] == "fig_p03_01"

    # 민 id 가 **새 판에 실제로 있는가.** 이름만 맞고 없는 id 면 뒷면이 조용히 빈다.
    fresh = {f["id"] for p in b["pages"] for f in p["lecture_figures"]}
    assert keep[1]["media"]["figure_id"] in fresh


def test_본문이_고쳐지면_잡는다(tmp_path):
    _, a = build(tmp_path, "v1.pdf", BODY)
    _, b = build(tmp_path, "v2.pdf",
                 [BODY[0], "Excystation happens in the lung, not the duodenum", BODY[2]])
    d = slidediff.diff(a, b)
    assert d["changed_slides"] == [2]
    assert "lecture_text" in d["pairs"][1]["changed"]
