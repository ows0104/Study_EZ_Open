"""시도의 산출물을 강의 폴더로 **올린다** (`docs/runs-layout.md` 5단계의 마지막 조각).

강의 폴더의 루트는 「지금 나가는 것」만 들고 시도는 `main/<판>/` 에 산다. 그 둘을
잇는 걸음이 `deck.promote` 다.

**4단계가 「안 만들었다」고 적어 둔 명령과 같은 것이다.** 고른 시도를 그 자리로
올리는 일과 새로 구운 시도를 올리는 일이 같은 걸음이었다.

지키는 것은 넷.

    ① 판 폴더의 덱이 강의 폴더로 올라간다        `apkg_of` 가 강의 폴더를 훑는다
    ② 올리는 것은 `CHOSEN` 이 고른 판이다        제일 새 판이 아니다
    ③ 내용이 같으면 다시 안 쓴다                 `publish` 가 mtime 으로 다시 민다
    ④ 옛 모양에서는 아무것도 안 한다             이미 그 자리에 있다
"""

from __future__ import annotations

import json
import os
import time

import pytest

from runner import attempts as att
from runner import chosen, deck
from runner import runlayout as L


def attempt(d, cards, *, started=None, deck_name="[260812_01] 강의.apkg", body=b"deck"):
    d.mkdir(parents=True, exist_ok=True)
    rows = [{"id": f"c{i:03}", "q": f"질문 {i}", "a": "답",
             "slide_no": 1, "reproduce": {"verdict": "same"}} for i in range(cards)]
    for name in ("items.raw.json", "items.reproduced.json"):
        (d / name).write_text(json.dumps({"cards": rows}), encoding="utf-8")
    (d / "prep.json").write_text(json.dumps({"source": "필기.pdf", "slides": 5}),
                                 encoding="utf-8")
    (d / "run.config.json").write_text(
        json.dumps({"pdf": "C:/필기.pdf", "id": "p260812_01", "deck": "병리학::강의"}),
        encoding="utf-8")
    (d / "suspects.json").write_text("{}", encoding="utf-8")
    if started is not None:
        (d / "usage.jsonl").write_text(
            json.dumps({"run": "r1", "t": started, "step": "prep"}) + "\n", encoding="utf-8")
    if deck_name:
        (d / deck_name).write_bytes(body)
    return d


# ── ① 덱이 올라간다 ──────────────────────────────────────────────────
def test_판_폴더의_덱을_강의_폴더로_올린다(tmp_path):
    run_dir = tmp_path / "260812_01"
    attempt(run_dir / L.MAIN / "260827-2300", 10, started=1786100000)

    got = deck.promote(run_dir)

    assert got == run_dir / "[260812_01] 강의.apkg"
    assert got.is_file()
    assert deck.apkg_of(run_dir, deck.MAIN) == got     # 계약이 이제 찾는다


def test_덱이_없으면_그렇게_말한다(tmp_path):
    run_dir = tmp_path / "260812_01"
    attempt(run_dir / L.MAIN / "260827-2300", 10, started=1786100000, deck_name="")
    with pytest.raises(FileNotFoundError, match="올릴 것이 없다"):
        deck.promote(run_dir)


# ── ② 고른 판을 올린다 ───────────────────────────────────────────────
def test_고른_판을_올린다_제일_새_판이_아니다(tmp_path):
    """**이것이 4단계를 5단계 앞에 둔 이유다.**"""
    run_dir = tmp_path / "260812_01"
    old = attempt(run_dir / L.MAIN / "260823-1450", 83, started=1786100000, body=b"cards83")
    attempt(run_dir / L.MAIN / "260827-2300", 58, started=1786300000, body=b"cards58")

    a = att.measure(old)
    chosen.write(run_dir, chosen.build("260812_01", a, why="기출을 잃지 않는다",
                                       repo_root=tmp_path, considered=[a]))

    got = deck.promote(run_dir)
    assert got.read_bytes() == b"cards83"
    assert chosen.verdict(run_dir) == ""


def test_판을_지목하면_그것을_올린다(tmp_path):
    run_dir = tmp_path / "260812_01"
    attempt(run_dir / L.MAIN / "260823-1450", 83, started=1786100000, body=b"cards83")
    attempt(run_dir / L.MAIN / "260827-2300", 58, started=1786300000, body=b"cards58")
    assert deck.promote(run_dir, version="260823-1450").read_bytes() == b"cards83"


def test_고른_기록이_없으면_제일_새_판이다(tmp_path):
    run_dir = tmp_path / "260812_01"
    attempt(run_dir / L.MAIN / "260823-1450", 83, started=1786100000, body=b"cards83")
    attempt(run_dir / L.MAIN / "260827-2300", 58, started=1786300000, body=b"cards58")
    assert deck.promote(run_dir).read_bytes() == b"cards58"


def test_고른_것과_올린_것이_어긋나면_문지기가_막는다(tmp_path, monkeypatch):
    """사람이 고른 판이 있는데 다른 판을 올린 경우. **조용히 지나가면 안 된다.**"""
    run_dir = tmp_path / "260812_01"
    old = attempt(run_dir / L.MAIN / "260823-1450", 83, started=1786100000, body=b"cards83")
    attempt(run_dir / L.MAIN / "260827-2300", 58, started=1786300000, body=b"cards58")
    a = att.measure(old)
    chosen.write(run_dir, chosen.build("260812_01", a, why="이걸 쓴다",
                                       repo_root=tmp_path, considered=[a]))

    monkeypatch.setattr(deck.quizgen_build, "counts",
                        lambda p: {"n_notes": 58, "n_cards": 58, "n_media": 0,
                                   "n_decks": 1, "missing_media": []})
    # 고른 것이 아닌 판을 지목해서 올린다. **판을 계약에도 같이 줘야 한다** —
    # 안 주면 계약이 `work_dir` 에게 다시 물어 「고른 판」을 적고, 그러면 올라간 것과
    # 적힌 것이 갈려 검사가 꺼진다(`_attempt_mark`). `runner promote` 가 같이 준다.
    deck.contract(run_dir, "260812_01", "병리학 소개", deck.MAIN, "260827-2300")

    from runner import gate
    got = gate.inspect(run_dir, run_dir / "덱.apkg", run_dir / "run.meta.json", "복습")
    assert not got.ok
    assert any("고른 시도가 이 자리에 없다" in b for b in got.blocking)


def test_옮겼는데_계약이_판을_안_말하면_덱으로_되짚는다(tmp_path):
    """2026-09-15 이전에 쓰인 계약이 이 자리에 온다. **짐작하지 않고 덱으로 본다.**"""
    run_dir = tmp_path / "260812_01"
    old = attempt(run_dir / L.MAIN / "260823-1450", 83, started=1786100000, body=b"cards83")
    attempt(run_dir / L.MAIN / "260827-2300", 58, started=1786300000, body=b"cards58xx")
    a = att.measure(old)
    chosen.write(run_dir, chosen.build("260812_01", a, why="이걸 쓴다",
                                       repo_root=tmp_path, considered=[a]))

    # 고른 것이 아닌 판의 덱만 올려 두고, 계약은 판을 안 말하는 옛 모양으로 둔다
    deck.promote(run_dir, version="260827-2300")
    (run_dir / "run.meta.json").write_text('{"item_count": 58}', encoding="utf-8")

    assert "고른 시도가 이 자리에 없다" in chosen.verdict(run_dir)


# ── ③ 같은 내용이면 다시 안 쓴다 ─────────────────────────────────────
def test_내용이_같으면_덱을_다시_안_쓴다(tmp_path):
    """`publish` 가 (크기, mtime)으로 다시 밀 것을 고른다. 수백 MB 가 다시 올라간다."""
    run_dir = tmp_path / "260812_01"
    attempt(run_dir / L.MAIN / "260827-2300", 10, started=1786100000)
    first = deck.promote(run_dir)
    stamp = first.stat().st_mtime_ns
    time.sleep(0.01)

    again = deck.promote(run_dir)

    assert again == first
    assert again.stat().st_mtime_ns == stamp           # 안 건드렸다


def test_크기가_같아도_판_폴더가_더_새것이면_다시_쓴다(tmp_path):
    """**크기만으로는 안 갈린다.** 2026-09-18 에 예습 덱 둘을 카드 하나씩 고쳐 다시
    구웠는데 둘 다 바이트 수가 이틀 전 것과 같았다. 크기만 보던 때는 새 덱이 강의
    폴더로 안 올라갔고 **옛 덱이 그대로 나갔다** — 계약은 카드 파일을 읽으므로
    깨끗해서 화면 어디에도 어긋남이 안 떴다.
    """
    run_dir = tmp_path / "260812_01"
    work = attempt(run_dir / L.MAIN / "260827-2300", 10, started=1786100000, body=b"old deck")
    first = deck.promote(run_dir)
    assert first.read_bytes() == b"old deck"

    src = work / "[260812_01] 강의.apkg"
    src.write_bytes(b"new deck")                       # 같은 길이 · 다른 내용
    # Windows CI can give adjacent writes the same timestamp. Establish the
    # test's newer-source premise explicitly instead of relying on clock ticks.
    os.utime(src, ns=(src.stat().st_atime_ns, first.stat().st_mtime_ns + 2_000_000_000))
    assert src.stat().st_size == first.stat().st_size

    assert deck.promote(run_dir).read_bytes() == b"new deck"


def test_크기가_다르면_다시_쓴다(tmp_path):
    run_dir = tmp_path / "260812_01"
    work = attempt(run_dir / L.MAIN / "260827-2300", 10, started=1786100000, body=b"short")
    deck.promote(run_dir)
    (work / "[260812_01] 강의.apkg").write_bytes(b"rebuilt and longer")
    assert deck.promote(run_dir).read_bytes() == b"rebuilt and longer"


# ── ④ 옛 모양 ────────────────────────────────────────────────────────
def test_옛_모양에서는_아무것도_안_한다(tmp_path):
    """시도가 강의 폴더에 있으면 덱도 이미 그 자리다. 127편이 이 모양이다."""
    run_dir = tmp_path / "260812_01"
    attempt(run_dir, 10, started=1786100000)
    got = deck.promote(run_dir)
    assert got == run_dir / "[260812_01] 강의.apkg"
    assert not (run_dir / L.MAIN).exists()


# ── 계약이 올린 뒤에 돈다 ────────────────────────────────────────────
def test_계약이_올리기를_스스로_한다(tmp_path, monkeypatch):
    """`contract` 가 `promote` 를 먼저 부른다 — 안 부르면 「덱이 없다」가 된다."""
    run_dir = tmp_path / "260812_01"
    attempt(run_dir / L.MAIN / "260827-2300", 7, started=1786100000)
    monkeypatch.setattr(deck.quizgen_build, "counts",
                        lambda p: {"n_notes": 7, "n_cards": 7, "n_media": 0,
                                   "n_decks": 1, "missing_media": []})

    meta = deck.contract(run_dir, "260812_01", "병리학 소개", deck.MAIN)

    assert meta["item_count"] == 7
    assert (run_dir / "[260812_01] 강의.apkg").is_file()
    assert (run_dir / "run.meta.json").is_file()


# ── 다시 구운 판이 계약에 오르는가 ────────────────────────────
#
# `contract` 에 판을 안 넘기면 `work_dir` 이 `run.meta.json` 의 「이미 배포된 판」을
# 먼저 고른다. 그러면 **한 번 배포된 편은 다시 구워도 옛 판이 계속 나간다.**
# 2026-09-15 `260914_03` 이 그랬다 — 두 번 다시 구웠는데 계약은 첫 판을 가리켰고,
# 그 판의 결함 카드로 문지기에 걸렸다.

def test_이번에_구운_판을_계약에_넘긴다(tmp_path):
    from runner import deck
    work = tmp_path / "main" / "260915-1533"
    assert deck.version_of(work) == "260915-1533"


def test_옛_모양이면_판이_없다(tmp_path):
    """강의 폴더에 그대로 쓰는 편은 넘길 판 이름이 없다 — `None` 이 맞다."""
    from runner import deck
    assert deck.version_of(tmp_path / "260812_01") is None
    assert deck.version_of(None) is None


def test_배포된_판이_있어도_새_판을_고른다(tmp_path):
    """이것이 그 버그다. 판을 지목하면 `run.meta.json` 의 옛 판을 안 따라간다."""
    import json

    from runner import runlayout as L

    run_dir = tmp_path / "260914_03"
    for v in ("260915-1303", "260915-1533"):
        (run_dir / "main" / v).mkdir(parents=True)
        (run_dir / "main" / v / "run.config.json").write_text("{}", encoding="utf-8")
    (run_dir / "run.meta.json").write_text(
        json.dumps({"attempt": {"kind": "main", "version": "260915-1303"}}),
        encoding="utf-8")

    # 안 지목하면 배포된 판(옛것)이 나온다 — 그래서 재빌드가 묻혔다
    assert L.work_dir(run_dir, L.MAIN).name == "260915-1303"
    # 지목하면 그 판이다
    assert L.work_dir(run_dir, L.MAIN, "260915-1533").name == "260915-1533"
