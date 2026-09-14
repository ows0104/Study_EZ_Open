"""시도 것을 판 폴더로 접는다 (`docs/runs-layout.md` 5단계).

옮기기 전에 실제 편 하나를 사본으로 떠서 돌려 봤고, **그 실컷 시험이 버그 셋을
잡았다.** 그 셋을 여기서 굳힌다.

    ① 판 이름을 mtime 으로만 따면 사본에서 전부 같은 분이 된다
    ② 접고 나면 「제일 새 판」이 배포 중인 판이 아니게 된다 — 계약이 딴 카드를 센다
    ③ 시도 안의 `.apkg` 를 강의 것으로 보면 `out/` 에 껍데기가 남는다
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from runner import attempts as att  # noqa: E402
from runner import chosen, deck  # noqa: E402
from runner import runlayout as L  # noqa: E402
from scripts import migrate_attempts as M  # noqa: E402


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """`runs/` 와 `out/` 을 임시로 세우고 스크립트가 그것을 보게 한다."""
    runs, out = tmp_path / "runs", tmp_path / "out"
    runs.mkdir()
    out.mkdir()
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M, "RUNS", runs)
    monkeypatch.setattr(M, "OUT", out)
    return tmp_path


def attempt(d: Path, cards: int, *, started: int | None = None, apkg: bool = False,
            kind: str = L.MAIN) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    rows = [{"id": f"c{i:03}", "q": f"질문 {i}", "a": "답"} for i in range(cards)]
    (d / "items.raw.json").write_text(json.dumps({"cards": rows}), encoding="utf-8")
    (d / "items.reproduced.json").write_text(json.dumps({"cards": rows}), encoding="utf-8")
    (d / "prep.json").write_text(json.dumps({"source": "필기.pdf", "slides": 5}),
                                 encoding="utf-8")
    cfg = "prequiz.config.json" if kind == L.PREQUIZ else "run.config.json"
    (d / cfg).write_text(json.dumps({"pdf": "C:/필기.pdf", "id": "p260812_01"}),
                         encoding="utf-8")
    if started is not None:
        (d / "usage.jsonl").write_text(
            json.dumps({"run": "r1", "t": started, "step": "prep"}) + "\n", encoding="utf-8")
    if apkg:
        (d / "p260812_01.apkg").write_bytes(b"deck")
    return d


def lecture_own(run_dir: Path) -> None:
    """강의 것 — 지금 나가는 것과 사람이 만든 것."""
    (run_dir / "run.meta.json").write_text('{"item_count": 83}', encoding="utf-8")
    (run_dir / "source.json").write_text('{"stem": "필기v1", "version": 1}', encoding="utf-8")
    (run_dir / "[260812_01] 강의.apkg").write_bytes(b"published")
    (run_dir / "slides").mkdir(exist_ok=True)
    (run_dir / "HOLD").write_text("사람이 봐야 한다", encoding="utf-8")


# ── ① 판 이름은 파일 안의 시각에서 딴다 ───────────────────────────────
def test_판을_원장의_시각에서_딴다(tmp_path):
    """`usage.jsonl` 의 `t` 는 복사해도 안 바뀐다. mtime 은 바뀐다."""
    d = attempt(tmp_path / "시도", 10, started=1786000000)   # 2026-08-06 쯤
    os.utime(d / "items.raw.json", (0, 0))                    # mtime 을 1970으로
    assert M.version_of(d).startswith("2608")                 # 원장을 봤다


def test_원장이_없으면_mtime으로_내려간다(tmp_path):
    d = attempt(tmp_path / "시도", 10)
    assert M.version_of(d) is not None


def test_카드가_없는_폴더는_시도가_아니다(tmp_path):
    d = tmp_path / "시도"
    d.mkdir()
    (d / "prep.json").write_text("{}", encoding="utf-8")
    assert M.version_of(d) is None


# ── ② 접은 뒤에도 계약이 배포 중인 판을 본다 ──────────────────────────
def test_접은_뒤_계약이_고른_판을_본다(tree):
    """**이것이 실컷 시험에서 잡힌 자리다.**

    `out/` 시도를 접으면 그중 제일 새것이 「제일 새 판」이 된다. 그때 `work_dir` 이
    그것을 주면 `deck.contract` 가 **배포 중인 덱과 다른 카드**로 계약을 다시 쓴다 —
    83장으로 나가 있는 편의 `item_count` 가 58이 된다.
    """
    run_dir = tree / "runs" / "260812_01"
    attempt(run_dir, 83, started=1786100000)
    lecture_own(run_dir)
    attempt(tree / "out" / "redo_260812_01", 58, started=1786300000, apkg=True)

    now = att.measure(run_dir)
    chosen.write(run_dir, chosen.build("260812_01", now, why="배포 중인 판이다",
                                       repo_root=tree, considered=[now]))

    M.apply(M.plan_for(run_dir))

    assert len(L.versions(run_dir)) == 2
    assert len(deck.cards_of(run_dir)) == 83          # 58 이면 안 된다
    assert chosen.verdict(run_dir) == ""              # 문지기가 안 막는다


def test_고른_기록이_없으면_제일_새_판이다(tree):
    run_dir = tree / "runs" / "260812_01"
    attempt(run_dir, 83, started=1786100000)
    lecture_own(run_dir)
    attempt(tree / "out" / "redo_260812_01", 58, started=1786300000)
    M.apply(M.plan_for(run_dir))
    assert len(deck.cards_of(run_dir)) == 58


# ── ③ 시도 안의 덱은 시도와 같이 간다 ─────────────────────────────────
def test_시도_안의_덱은_같이_옮긴다(tree):
    """안 옮기면 `out/` 에 주인 없는 덱 껍데기가 남고 폴더도 안 치워진다."""
    run_dir = tree / "runs" / "260812_01"
    attempt(run_dir, 83, started=1786100000)
    lecture_own(run_dir)
    attempt(tree / "out" / "redo_260812_01", 58, started=1786300000, apkg=True)

    M.apply(M.plan_for(run_dir))

    assert not list((tree / "out").iterdir())          # out/ 이 접혔다
    moved = [d for _, _, d in L.attempt_dirs(run_dir) if list(d.glob("*.apkg"))]
    assert len(moved) == 1


def test_강의_폴더의_덱은_남는다(tree):
    """**서버 계약이 그 자리를 본다.** 지금 나가는 것이다."""
    run_dir = tree / "runs" / "260812_01"
    attempt(run_dir, 83, started=1786100000)
    lecture_own(run_dir)
    M.apply(M.plan_for(run_dir))
    left = sorted(p.name for p in run_dir.iterdir())
    assert "[260812_01] 강의.apkg" in left
    assert "run.meta.json" in left
    assert "HOLD" in left
    assert "source.json" in left
    assert "slides" in left
    assert "prep.json" not in left                     # 시도 것은 갔다


def test_사람이_만든_것을_시도_안으로_묻지_않는다(tree):
    """`out/` 시도에 `preview.md` 가 있으면 옮기지 않고 말한다."""
    run_dir = tree / "runs" / "260812_01"
    attempt(run_dir, 83, started=1786100000)
    lecture_own(run_dir)
    d = attempt(tree / "out" / "pre_p260812_01", 20, started=1786300000, kind=L.PREQUIZ)
    (d / "preview.md").write_text("공유된 대화", encoding="utf-8")

    plan = M.plan_for(run_dir)
    assert any("preview.md" in n for n in plan.skipped)
    M.apply(plan)
    assert (d / "preview.md").is_file()               # 그 자리에 그대로 있다


# ── 한 번 더 돌려도 값이 같다 ─────────────────────────────────────────
def test_두_번_돌려도_같다(tree):
    run_dir = tree / "runs" / "260812_01"
    attempt(run_dir, 83, started=1786100000)
    lecture_own(run_dir)
    attempt(tree / "out" / "redo_260812_01", 58, started=1786300000, apkg=True)

    M.apply(M.plan_for(run_dir))
    before = sorted(p.name for p in run_dir.rglob("*"))
    plan2 = M.plan_for(run_dir)
    assert plan2.empty
    assert M.apply(plan2) == 0
    assert sorted(p.name for p in run_dir.rglob("*")) == before


def test_같은_분에_두_시도면_꼬리를_붙인다(tree):
    """`260820_02` 의 var1·var2 가 실제로 같은 14:09 이다. **덮지 않는다.**"""
    run_dir = tree / "runs" / "260820_02"
    attempt(run_dir, 97, started=1786100000)
    lecture_own(run_dir)
    attempt(tree / "out" / "var1_260820_02", 97, started=1786300000)
    attempt(tree / "out" / "var2_260820_02", 97, started=1786300000)

    M.apply(M.plan_for(run_dir))
    got = L.versions(run_dir)
    assert len(got) == 3
    assert len(set(got)) == 3


# ── 쓰는 쪽이 판 폴더를 안다 (2026-09-15 에 켰다) ─────────────────────
#
# 켜기 전에는 `--apply` 가 거부했다. **옮긴 편에 새 실행이 강의 폴더로 쓰면 그
# 산출물이 판 폴더에 가려 조용히 무시된다** — 그 함정을 열어 두지 않으려고 막았다.
# 지금은 셋이 다 섰으므로(`runlayout.WRITES_ATTEMPT_DIRS` 위 주석) 풀렸다.

def test_새_실행은_새_판을_연다(tmp_path):
    run_dir = tmp_path / "260812_01"
    first = deck.new_work_dir(run_dir, deck.MAIN)
    assert first.parent.name == L.MAIN
    assert L.RE_VERSION.match(first.name)


def test_resume은_새_판을_열지_않는다(tmp_path):
    """이어 돌리는 것은 그 시도를 계속하는 것이다. 새 판을 열면 prep 부터 다시 돈다."""
    run_dir = tmp_path / "260812_01"
    attempt(run_dir / L.MAIN / "260827-2300", 10, started=1786100000)
    assert deck.new_work_dir(run_dir, deck.MAIN, resume=True).name == "260827-2300"
    assert deck.new_work_dir(run_dir, deck.MAIN, resume=False).name != "260827-2300"


def test_같은_분에_두_번_돌려도_판을_안_덮는다(tmp_path, monkeypatch):
    run_dir = tmp_path / "260812_01"
    monkeypatch.setattr(L, "new_version", lambda when=None: "260915-0100")
    first = deck.new_work_dir(run_dir, deck.MAIN)
    attempt(first, 10, started=1786100000)
    assert deck.new_work_dir(run_dir, deck.MAIN).name == "260915-0100.2"
