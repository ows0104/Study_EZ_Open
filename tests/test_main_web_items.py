"""복습도 웹 문항을 낸다 — 그리고 예습이 내던 것은 한 글자도 안 바뀐다.

2026-08-31에 `deck.contract`의 갈래를 풀어 복습에도 `main_items.final.json`과
`slides/`를 내게 했다. **고친 자리가 두 갈래의 공용이라 회귀가 나는 곳은 예습이다**
— 이 파일의 절반이 그것을 지킨다.

아직 이것을 읽는 화면은 없다(`publish`도 안 올린다). 재료가 쌓이는 데 시간이
걸려서 먼저 내는 것이고, 그 사정은 `docs/artifact-contract.md`에 적혀 있다.
"""

import json
from pathlib import Path

import pytest

from studyez import deck, gate


CARDS = [
    {"id": "c001", "card_format": "basic", "q": "무엇인가?", "a": "이것이다",
     "explanation": "왜냐하면", "importance": "must", "slide_no": 3},
    {"id": "c002", "card_format": "ox", "q": "그런가?", "a": "O",
     "explanation": "", "importance": "should", "slide_no": 7},
    # 그림 카드는 웹에서 빠진다. 앞면이 이미지라 텍스트만으로 물음이 안 선다.
    {"id": "c003", "card_format": "image_basic", "q": "이 조직은?", "a": "간",
     "explanation": "해설", "importance": "must", "slide_no": 9},
]


def _run(tmp_path: Path, name: str) -> Path:
    """`contract`가 읽는 최소한의 run 디렉터리."""
    run = tmp_path / name
    (run / "media").mkdir(parents=True)
    for slide in (3, 7):
        (run / "media" / f"{name}_slide{slide:03d}.png").write_bytes(b"png")
    # 그림 크롭. 슬라이드가 아니므로 안 옮겨져야 한다.
    (run / "media" / "crop_a.png").write_bytes(b"png")
    (run / "items.reproduced.json").write_text(
        json.dumps({"cards": CARDS}, ensure_ascii=False), encoding="utf-8")
    return run


@pytest.fixture
def contract(monkeypatch):
    """apkg를 안 굽고 `contract`만 돌린다. 덱을 여는 부분은 여기 관심이 아니다."""
    monkeypatch.setattr(deck, "apkg_of", lambda run_dir, kind: run_dir / "deck.apkg")
    monkeypatch.setattr(deck, "config_of", lambda run_dir, kind: {"id": "p260820_02"})
    monkeypatch.setattr(deck, "cards_of", lambda run_dir: CARDS)
    monkeypatch.setattr(deck.pdf2anki_build, "counts", lambda apkg: {})

    def run(run_dir: Path, kind: str) -> dict:
        (run_dir / "deck.apkg").write_bytes(b"apkg")
        return deck.contract(run_dir, run_dir.name, "제목", kind)

    return run


def test_복습이_웹_문항과_슬라이드를_낸다(tmp_path, contract):
    run = _run(tmp_path, "260820_02")
    meta = contract(run, deck.MAIN)

    items = json.loads((run / "main_items.final.json").read_text(encoding="utf-8"))
    assert items["generated_by"] == "pdf2anki.main"
    assert [i["id"] for i in items["items"]] == ["c001", "c002"]
    assert meta["web_items"] == 2
    assert meta["web_excluded"] == 1

    # 슬라이드만 옮긴다. 그림 크롭은 웹이 읽지 않는다.
    assert sorted(p.name for p in (run / "slides").glob("*.png")) == [
        "260820_02_s003.png", "260820_02_s007.png"]
    assert meta["slides_exported"] == 2


def test_해설이_빈_문항을_센다(tmp_path, contract):
    """웹 풀이는 틀렸을 때 해설을 보여 준다. 복습은 그 자리가 절반쯤 빈다."""
    meta = contract(_run(tmp_path, "260820_02"), deck.MAIN)
    assert meta["web_without_explanation"] == 1


def test_복습_고유값은_그대로다(tmp_path, contract):
    meta = contract(_run(tmp_path, "260820_02"), deck.MAIN)
    assert "strategy" in meta and "strategy_why" in meta


def test_예습은_제_이름으로만_낸다(tmp_path, contract):
    """두 갈래가 같은 자리를 쓰므로, 예습이 복습 파일을 흘리면 여기서 걸린다."""
    run = _run(tmp_path, "250825_01")
    contract(run, deck.PRE)

    items = json.loads((run / "pre_items.final.json").read_text(encoding="utf-8"))
    assert items["generated_by"] == "pdf2anki.prequiz"
    assert not (run / "main_items.final.json").exists()


def test_복습의_그림_카드는_문지기가_안_읊는다(tmp_path, contract):
    """**있지도 않은 화면을 있다고 말하지 않는다.**

    `web_excluded`는 이제 복습에도 붙지만 「웹 풀이에서 빠진다」는 말은 읽을
    화면이 있는 예습에만 쓴다. 복습 웹 풀이가 서면 이 검사를 지워라.
    """
    run = _run(tmp_path, "260820_02")
    meta_path = run / "run.meta.json"
    contract(run, deck.MAIN)

    main = gate.inspect(run, run / "deck.apkg", meta_path, "Main-Quiz")
    assert not any("웹 풀이" in note for note in main.notes)

    pre_run = _run(tmp_path, "250825_01")
    contract(pre_run, deck.PRE)
    pre = gate.inspect(pre_run, pre_run / "deck.apkg", pre_run / "pre_run.meta.json",
                       "Pre-Quiz", "pre_")
    assert any("웹 풀이" in note for note in pre.notes)
