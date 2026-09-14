"""어느 시도를 왜 골랐는지 적는다 (`docs/runs-layout.md` 4단계).

그 문서가 「왜 바꾸나」의 ④로 적어 둔 자리다 — **어느 시도가 왜 이겼는지 적는
자리가 없다. 지금 「정본」은 어쩌다 `runs/<id>/`에 놓여 있는 것이다.**

여기서 지키는 것은 넷이다.

    ① `why` 없이는 기록을 만들지 않는다        왜 골랐는지는 코드가 쓸 수 없다
    ② 판정은 경로가 아니라 **카드 해시**다      카드를 옮기면 그 자리에서 맞는다
    ③ 기록이 없으면 문지기가 아무 말도 안 한다  306편 대부분이 그렇다
    ④ 고른 것이 딴 데 있으면 **덱을 미룬다**    적어 놓고 아무 일도 안 나면 안 적은 것과 같다
"""

from __future__ import annotations

import json

import pytest

from runner import attempts as att
from runner import chosen, gate


def _attempt(d, cards, *, exam_hit=0, jokbo_ref=0, verdict="same", cut_id=None):
    """카드 몇 장을 낸 시도 폴더."""
    d.mkdir(parents=True, exist_ok=True)
    rows = [{"id": f"c{i:03}", "q": f"질문 {i}", "a": "답",
             "exam_hit": i < exam_hit, "jokbo_ref": "2023-1" if i < jokbo_ref else "",
             "reproduce": {"verdict": verdict}} for i in range(cards)]
    (d / "items.raw.json").write_text(json.dumps({"cards": rows}, ensure_ascii=False),
                                      encoding="utf-8")
    if cut_id:
        (d / "jokbo.used.json").write_text(json.dumps(
            {"cut_id": cut_id, "slice": "L1_강의.json", "attached": True}), encoding="utf-8")
    return d


# ── ① why 없이는 안 적는다 ───────────────────────────────────────────
def test_why가_없으면_기록을_안_만든다(tmp_path):
    """무엇이 좋은 시도인지가 아직 안 정해졌다. 코드가 이유를 지어내면 안 된다."""
    a = att.measure(_attempt(tmp_path / "runs" / "260812_01", 10))
    for blank in ("", "   ", None):
        with pytest.raises(ValueError, match="why"):
            chosen.build("260812_01", a, why=blank, repo_root=tmp_path)


def test_고른_이유가_그대로_남는다(tmp_path):
    a = att.measure(_attempt(tmp_path / "runs" / "260812_01", 10))
    rec = chosen.build("260812_01", a, why="기출이 더 많다", repo_root=tmp_path)
    assert rec["publish"]["main_why"] == "기출이 더 많다"
    assert rec["publish"]["main"]["cards"] == 10
    assert rec["run_id"] == "260812_01"


def test_비교한_시도를_원값으로_같이_적는다(tmp_path):
    """**비어 있으면 「비교 안 했다」로 읽어야 한다** — 나중에 그걸 알아야 한다."""
    runs, out = tmp_path / "runs", tmp_path / "out"
    keep = att.measure(_attempt(runs / "260812_01", 83, exam_hit=13, jokbo_ref=37))
    other = att.measure(_attempt(out / "redo_260812_01", 58, exam_hit=8, jokbo_ref=23))

    rec = chosen.build("260812_01", keep, why="기출을 잃는다", repo_root=tmp_path,
                       considered=[keep, other])

    assert len(rec["considered"]) == 1           # 고른 것 자신은 안 센다
    assert rec["considered"][0]["exam_hit"] == 8
    assert rec["considered"][0]["path"] == "out/redo_260812_01"
    # 점수도 등수도 없다 (docs/runs-layout.md 「아직 안 정한 것」)
    assert "score" not in rec["considered"][0]
    assert "rank" not in rec["considered"][0]


def test_채점만_다시_돌린_판은_비교_대상이_아니다(tmp_path):
    """카드가 같은 것을 「비교했다」고 적으면 정보에 근거한 판단처럼 보인다."""
    runs, out = tmp_path / "runs", tmp_path / "out"
    keep = att.measure(_attempt(runs / "260820_02", 97))
    twin = att.measure(_attempt(out / "var1_260820_02", 97))
    twin.cards_sha256 = keep.cards_sha256        # 카드가 한 바이트도 안 다르다
    att.dedupe([keep, twin])

    rec = chosen.build("260820_02", keep, why="그대로 둔다", repo_root=tmp_path,
                       considered=[keep, twin])
    assert rec["considered"] == []


def test_고른_시도가_본_컷이_current에_남는다(tmp_path):
    """그 컷을 다시 자르면 `cut_id` 가 달라진다. 이 값이 그때의 답으로 남는다."""
    a = att.measure(_attempt(tmp_path / "runs" / "260907_05", 20, cut_id="260908-0130"))
    rec = chosen.build("260907_05", a, why="이걸 쓴다", repo_root=tmp_path)
    assert rec["current"]["jokbo"]["cut_id"] == "260908-0130"


# ── ② 판정은 카드 해시로 한다 ─────────────────────────────────────────
def test_고른_것이_그_자리에_있으면_아무_말도_안_한다(tmp_path):
    run_dir = _attempt(tmp_path / "runs" / "260812_01", 83)
    a = att.measure(run_dir)
    chosen.write(run_dir, chosen.build("260812_01", a, why="이걸 쓴다", repo_root=tmp_path))
    assert chosen.verdict(run_dir) == ""


def test_카드를_옮겨_놓으면_경로가_달라도_맞는다(tmp_path):
    """**경로로 보면 안 맞는다고 한다.** 시도의 신원은 카드 해시다."""
    runs, out = tmp_path / "runs", tmp_path / "out"
    run_dir = _attempt(runs / "260812_01", 10)
    picked = _attempt(out / "redo_260812_01", 58)
    chosen.write(run_dir, chosen.build(
        "260812_01", att.measure(picked), why="이걸 쓴다", repo_root=tmp_path))
    assert "이 자리에 없다" in chosen.verdict(run_dir)

    # 고른 카드를 그 자리로 옮긴다 — 기록을 안 고쳐도 맞아야 한다
    (run_dir / "items.raw.json").write_bytes((picked / "items.raw.json").read_bytes())
    assert chosen.verdict(run_dir) == ""


def test_신원을_안_적은_기록은_판정하지_않는다(tmp_path):
    run_dir = _attempt(tmp_path / "runs" / "260812_01", 10)
    chosen.write(run_dir, {"run_id": "260812_01",
                           "publish": {"main": {"path": "runs/260812_01"}}})
    assert chosen.verdict(run_dir) == ""


def test_카드_파일이_없으면_모른다고_한다(tmp_path):
    """옆 저장소에서 옮겨 온 편이 이 자리에 온다. 모르는 것을 틀렸다고 하지 않는다."""
    runs, out = tmp_path / "runs", tmp_path / "out"
    run_dir = runs / "260812_01"
    picked = _attempt(out / "redo_260812_01", 58)
    run_dir.mkdir(parents=True)
    chosen.write(run_dir, chosen.build(
        "260812_01", att.measure(picked), why="이걸 쓴다", repo_root=tmp_path))
    assert chosen.verdict(run_dir) == ""


# ── ③④ 문지기 ────────────────────────────────────────────────────────
def _meta(run_dir, count=10):
    """문지기를 지나갈 최소한의 `run.meta.json`."""
    p = run_dir / "run.meta.json"
    p.write_text(json.dumps({"item_count": count, "verified": {"notes": count}}),
                 encoding="utf-8")
    return p


def test_기록이_없으면_문지기가_지금과_똑같이_돈다(tmp_path):
    """그 문서의 4단계가 그렇게 정했다 — 「없으면 지금처럼 동작하게」."""
    run_dir = _attempt(tmp_path / "runs" / "260812_01", 10)
    verdict = gate.inspect(run_dir, run_dir / "덱.apkg", _meta(run_dir), "복습")
    assert verdict.ok
    assert not any("고른" in b for b in verdict.blocking)


def test_고른_것이_딴_데_있으면_덱을_미룬다(tmp_path):
    """**적기만 하면 안 적은 것과 같다.** 편마다 뜬 경고를 세 번 놓쳤다."""
    runs, out = tmp_path / "runs", tmp_path / "out"
    run_dir = _attempt(runs / "260812_01", 10)
    picked = _attempt(out / "redo_260812_01", 58)
    chosen.write(run_dir, chosen.build(
        "260812_01", att.measure(picked), why="이걸 쓴다", repo_root=tmp_path))

    verdict = gate.inspect(run_dir, run_dir / "덱.apkg", _meta(run_dir), "복습")

    assert not verdict.ok
    blocked = " ".join(verdict.blocking)
    assert "고른 시도가 이 자리에 없다" in blocked
    assert "out/redo_260812_01" in blocked        # 무엇을 골랐는지 말한다
    assert "runner chosen 260812_01" in blocked   # 어떻게 되돌리는지도 말한다


def test_예습은_자기_칸을_본다(tmp_path):
    """복습을 골라 둔 것이 예습 덱을 막으면 안 된다."""
    runs, out = tmp_path / "runs", tmp_path / "out"
    run_dir = _attempt(runs / "260812_01", 10)
    picked = _attempt(out / "redo_260812_01", 58)
    chosen.write(run_dir, chosen.build(
        "260812_01", att.measure(picked), why="복습은 이걸 쓴다", repo_root=tmp_path))

    pre = gate.inspect(run_dir, run_dir / "pre.apkg",
                       _meta(run_dir), "예습", prefix="pre_")
    assert not any("고른" in b for b in pre.blocking)


def test_한쪽을_적어도_다른쪽이_안_지워진다(tmp_path):
    runs = tmp_path / "runs"
    run_dir = _attempt(runs / "260812_01", 10)
    a = att.measure(run_dir)
    first = chosen.build("260812_01", a, why="복습", repo_root=tmp_path, kind=chosen.MAIN)
    second = chosen.build("260812_01", a, why="예습", repo_root=tmp_path,
                          kind=chosen.PREQUIZ, previous=first)
    assert second["publish"]["main_why"] == "복습"
    assert second["publish"]["prequiz_why"] == "예습"


# ── 이미지 카드는 재현 분모에서 빠진다 ────────────────────────────────
def test_재현_분모는_실제로_채점된_카드뿐이다(tmp_path):
    """이미지 카드는 검사에서 `skipped` 다. 분모에 넣으면 사진 많은 편이 낮게 나온다.

    2026-09-14 의 첫 표가 넣은 채로 찍고 있었다 — `260813_01` 은 154장 중 18장이
    그랬고 67% 대 72% 로 갈렸다. 25편을 짝지어 본 결론은 그대로다.
    """
    d = tmp_path / "runs" / "260813_01"
    d.mkdir(parents=True)
    rows = [{"id": "c1", "q": "글", "reproduce": {"verdict": "same"}},
            {"id": "c2", "q": "글", "reproduce": {"verdict": "different"}},
            {"id": "c3", "q": "사진", "reproduce": {"status": "skipped",
                                                    "why": "앞면에 그림이 필요해 텍스트만으로 검사 불가"}}]
    (d / "items.raw.json").write_text(json.dumps({"cards": rows}, ensure_ascii=False),
                                      encoding="utf-8")
    a = att.measure(d)
    assert a.cards == 3
    assert a.graded == 2                 # 사진 카드는 채점된 것이 아니다
    assert a.same_rate == pytest.approx(0.5)
