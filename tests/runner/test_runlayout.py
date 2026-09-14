"""`runs/<편>/` 안에서 강의 것과 시도 것을 가른다 (`docs/runs-layout.md` 5단계).

그 문서의 ③ 이 여기서 풀린다 — **섞여 있어서 「다시 돌리기」가 위험하다.**

지키는 것은 셋이다.

    ① 강의 것은 비울 때 살아남는다      파이프라인이 다시 만들 수 없다
    ② 옛 모양과 새 모양을 같이 읽는다    반쯤 옮긴 나무에서도 돈다
    ③ 「제일 새 판」은 이름순이다        mtime 으로 고르지 않는다
"""

from __future__ import annotations

import pytest

from runner import runlayout as L


# ── ① 강의 것 ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", [
    "HOLD",                 # 안에 적힌 글이 그대로 보류 사유다
    "CHOSEN.json",          # 사람이 고른 판 (2026-09-15)
    "preview.md",           # 공유된 예습 대화. 다시 못 받는다
    "pre_target.json",
    "note.md",
    "source.json",          # 어느 파일 몇 판으로 만들었나
    "run.meta.json",        # 서버 계약
    "pre_run.meta.json",
    "main_items.final.json",
    "pre_items.final.json",
    "slides",
    "BUILDING",             # 지우면 두 일꾼이 같은 편을 잡는다
    "[260812_01] 병리학 소개(정경천).apkg",
])
def test_강의_것은_비울_때_살아남는다(name):
    assert L.is_lecture_own(name), name


@pytest.mark.parametrize("name", [
    "prep.json", "prep.md", "items.raw.json", "items.checked.json",
    "items.reproduced.json", "run.report.json", "run.config.json",
    "prequiz.config.json", "usage.jsonl", "suspects.json", "plan.json",
    "must_know.json", "reproduce.grades.json", "clean.pdf", "annotated.pdf",
    "prompt.cards.1of2.md", "context.1of4.md", "media", "jokbo.used.json",
])
def test_시도_것은_다시_만들면_생긴다(name):
    assert not L.is_lecture_own(name), name


def test_HOLD와_CHOSEN이_import_에서_살아남는다():
    """**2026-09-15 까지 이 둘이 지워질 수 있었다.**

    `runner import` 가 그 자리를 비울 때 남기는 것을 둘만 알고 있었다
    (`preview.md`·`pre_target.json`). `.gitignore` 는 `HOLD` 를 두고 *"잃으면
    막아 둔 이유를 아무도 모른 채 덱이 나간다"* 고 적고 있었는데 거기는 몰랐다.
    """
    from runner.__main__ import KEEP_ON_IMPORT
    assert KEEP_ON_IMPORT("HOLD")
    assert KEEP_ON_IMPORT("CHOSEN.json")
    assert KEEP_ON_IMPORT("source.json")
    assert not KEEP_ON_IMPORT("items.raw.json")


# ── ② 두 모양을 같이 읽는다 ───────────────────────────────────────────
def _flat(run_dir):
    """옛 모양 — 시도 것이 강의 폴더에 그대로 널려 있다. 127편이 이 모양이다."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prep.json").write_text("{}", encoding="utf-8")
    (run_dir / "items.raw.json").write_text("{}", encoding="utf-8")
    return run_dir


def _nested(run_dir, kind, version):
    d = run_dir / kind / version
    d.mkdir(parents=True, exist_ok=True)
    (d / "prep.json").write_text("{}", encoding="utf-8")
    return d


def test_옛_모양은_강의_폴더_자신이_작업_폴더다(tmp_path):
    run_dir = _flat(tmp_path / "260812_01")
    assert L.work_dir(run_dir) == run_dir
    assert L.versions(run_dir) == []
    assert L.is_migrated(run_dir) is False
    assert L.find(run_dir, "prep.json") == run_dir / "prep.json"


def test_새_모양이면_그_판을_준다(tmp_path):
    run_dir = tmp_path / "260812_01"
    d = _nested(run_dir, L.MAIN, "260827-2300")
    assert L.work_dir(run_dir) == d
    assert L.is_migrated(run_dir) is True
    assert L.find(run_dir, "prep.json") == d / "prep.json"


def test_반쯤_옮긴_나무에서도_찾는다(tmp_path):
    """복습만 옮기고 예습은 옛 자리에 있는 상태. **이행이 한 번에 안 되게 하려는 것이다.**"""
    run_dir = _flat(tmp_path / "260812_01")
    (run_dir / "prequiz.config.json").write_text("{}", encoding="utf-8")
    main = _nested(run_dir, L.MAIN, "260827-2300")

    assert L.work_dir(run_dir, L.MAIN) == main
    assert L.work_dir(run_dir, L.PREQUIZ) == run_dir      # 아직 옛 자리다
    assert L.find(run_dir, "prequiz.config.json", L.PREQUIZ) == run_dir / "prequiz.config.json"


def test_새_자리에_없으면_옛_자리를_본다(tmp_path):
    """옮기다 만 편이 있을 수 있다. 새 자리를 먼저 보고 없으면 내려간다."""
    run_dir = _flat(tmp_path / "260812_01")
    _nested(run_dir, L.MAIN, "260827-2300")              # prep.json 만 있다
    assert L.find(run_dir, "items.raw.json").parent == run_dir


def test_강의_것은_판을_안_묻는다(tmp_path):
    """「어느 판의 HOLD 인가」는 없는 질문이다."""
    run_dir = tmp_path / "260812_01"
    _nested(run_dir, L.MAIN, "260827-2300")
    (run_dir / "HOLD").write_text("사람이 봐야 한다", encoding="utf-8")
    assert L.find(run_dir, "HOLD") == run_dir / "HOLD"


def test_없으면_None이다(tmp_path):
    run_dir = _flat(tmp_path / "260812_01")
    assert L.find(run_dir, "없는파일.json") is None
    assert L.find(run_dir, "HOLD") is None


# ── ③ 제일 새 판은 이름순이다 ─────────────────────────────────────────
def test_판을_이름순으로_고른다_mtime이_아니다(tmp_path):
    """파일을 옮기거나 복사하면 mtime 이 뒤집힌다 (`runner/fingerprint.py` 실측)."""
    import os
    run_dir = tmp_path / "260812_01"
    old = _nested(run_dir, L.MAIN, "260823-1450")
    new = _nested(run_dir, L.MAIN, "260827-2300")
    # 옛 판을 방금 만진 것처럼 해 둔다
    os.utime(old, None)
    os.utime(old / "prep.json", None)

    assert L.versions(run_dir) == ["260823-1450", "260827-2300"]
    assert L.work_dir(run_dir) == new


def test_판_모양이_아닌_폴더는_판이_아니다(tmp_path):
    run_dir = tmp_path / "260812_01"
    (run_dir / L.MAIN / "임시").mkdir(parents=True)
    (run_dir / L.MAIN / "media").mkdir(parents=True)
    assert L.versions(run_dir) == []
    assert L.work_dir(run_dir) == run_dir


def test_같은_분에_두_번이면_꼬리가_붙은_것도_판이다(tmp_path):
    run_dir = tmp_path / "260812_01"
    _nested(run_dir, L.MAIN, "260914-2312")
    _nested(run_dir, L.MAIN, "260914-2312.2")
    assert L.versions(run_dir) == ["260914-2312", "260914-2312.2"]


def test_시도를_전부_센다(tmp_path):
    run_dir = tmp_path / "260812_01"
    _nested(run_dir, L.MAIN, "260823-1450")
    _nested(run_dir, L.MAIN, "260827-2300")
    _nested(run_dir, L.PREQUIZ, "260826-0410")
    got = L.attempt_dirs(run_dir)
    assert [(k, v) for k, v, _ in got] == [
        (L.MAIN, "260823-1450"), (L.MAIN, "260827-2300"), (L.PREQUIZ, "260826-0410")]


def test_갈래는_폴더_안의_설정이_말한다(tmp_path):
    main, pre = tmp_path / "a", tmp_path / "b"
    main.mkdir()
    pre.mkdir()
    (main / "run.config.json").write_text("{}", encoding="utf-8")
    (pre / "prequiz.config.json").write_text("{}", encoding="utf-8")
    assert L.kind_of(main) == L.MAIN
    assert L.kind_of(pre) == L.PREQUIZ


# ── 작업 폴더를 고르는 순서 넷 (2026-09-15) ───────────────────────────
#
# ① CHOSEN → ② 계약의 `attempt` → ③ 제일 새 **온전한** 판 → ④ 강의 폴더.
# ②와 ③의 「온전한」이 실제 트리를 접자마자 필요해졌다.

def _whole(run_dir, kind, version, cards=b'{"cards": []}'):
    """설정 파일까지 있는 판 — 온전한 시도."""
    d = run_dir / kind / version
    d.mkdir(parents=True, exist_ok=True)
    (d / "items.raw.json").write_bytes(cards)
    cfg = "prequiz.config.json" if kind == L.PREQUIZ else "run.config.json"
    (d / cfg).write_text('{"pdf": "C:/필기.pdf"}', encoding="utf-8")
    return d


def test_설정이_없는_판은_작업_폴더로_안_고른다(tmp_path):
    """**실제 트리를 접자마자 나왔다.**

    `260901_01` 은 cloze 프롬프트를 아홉 번 돌린 편이라 판이 11개인데, 이름이 제일
    새 것에 `prep.json` 도 `run.config.json` 도 없다 — 카드만 남은 실험 폴더다.
    그것을 고르면 `deck.source_pdf` 가 빈 값을 내고 `publish` 가 주인을 확인할 수 없다.
    """
    run_dir = tmp_path / "260901_01"
    good = _whole(run_dir, L.MAIN, "260906-1341")
    scrap = run_dir / L.MAIN / "260906-1619"      # 카드만 있다
    scrap.mkdir(parents=True)
    (scrap / "items.raw.json").write_bytes(b'{"cards": []}')

    assert L.versions(run_dir)[-1] == "260906-1619"   # 이름은 이것이 제일 새것
    assert L.work_dir(run_dir) == good                # 고르는 것은 온전한 쪽


def test_온전한_판이_없으면_그냥_제일_새것이다(tmp_path):
    """모르는 자리에서 조용히 빈 값을 주면 그 편만 이유 없이 안 나간다."""
    run_dir = tmp_path / "260901_01"
    for v in ("260906-1341", "260906-1619"):
        d = run_dir / L.MAIN / v
        d.mkdir(parents=True)
        (d / "items.raw.json").write_bytes(b'{"cards": []}')
    assert L.work_dir(run_dir).name == "260906-1619"


def test_계약이_말한_판이_제일_새것을_이긴다(tmp_path):
    """`run.meta.json` 의 `attempt` — 지금 나가는 덱을 만든 판이다."""
    run_dir = tmp_path / "260812_01"
    _whole(run_dir, L.MAIN, "260823-1450")
    _whole(run_dir, L.MAIN, "260827-2300")
    (run_dir / "run.meta.json").write_text(
        '{"attempt": {"kind": "main", "version": "260823-1450"}}', encoding="utf-8")
    assert L.work_dir(run_dir).name == "260823-1450"


def test_CHOSEN이_계약을_이긴다(tmp_path):
    """사람이 적어 둔 것이 제일 세다."""
    import hashlib
    run_dir = tmp_path / "260812_01"
    a = _whole(run_dir, L.MAIN, "260823-1450", cards=b'{"cards": [1]}')
    _whole(run_dir, L.MAIN, "260827-2300", cards=b'{"cards": [2]}')
    want = hashlib.sha256((a / "items.raw.json").read_bytes()).hexdigest()
    (run_dir / "run.meta.json").write_text(
        '{"attempt": {"kind": "main", "version": "260827-2300"}}', encoding="utf-8")
    (run_dir / "CHOSEN.json").write_text(
        '{"publish": {"main": {"cards_sha256": "' + want + '"}}}', encoding="utf-8")
    assert L.work_dir(run_dir).name == "260823-1450"


def test_계약이_없는_판을_말하면_무시한다(tmp_path):
    """옮기다 지워졌거나 다른 편의 값이 들어온 경우."""
    run_dir = tmp_path / "260812_01"
    _whole(run_dir, L.MAIN, "260827-2300")
    (run_dir / "run.meta.json").write_text(
        '{"attempt": {"kind": "main", "version": "없는판-0000"}}', encoding="utf-8")
    assert L.work_dir(run_dir).name == "260827-2300"
