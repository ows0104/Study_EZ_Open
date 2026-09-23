"""사이트 판정이 덱까지 가는가 — 당겨 와 적고, 어긋난 편만 다시 굽고, 거두면 되돌린다.

2026-09-23 관리자 지시 — 「사이트에서 고친 카드가 apkg에도 반영되게 해줘.」
설계는 `runner/site_edits.py` 머리에 있다.
"""

import json
from pathlib import Path

import pytest

from runner import deck, rebuild, site_edits


class FakeClient:
    def __init__(self, edits):
        self.edits = edits

    def call(self, method, path, payload=None):
        assert (method, path) == ("GET", site_edits.ROUTE)
        return {"edits": self.edits}


def a_row(item_id="c002", action="edit", subject="미생물학", run_id="260921_03", kind="main"):
    return {"subject": subject, "runId": run_id, "kind": kind, "itemId": item_id,
            "action": action, "stem": "고친 질문", "sourceStem": None,
            "answer": "morphology alteration", "explanation": None,
            "original": {"qtype": "basic", "stem": "원래 질문", "answer": "morphology alteration",
                         "explanation": "해설"}}


@pytest.fixture
def runs(tmp_path, monkeypatch):
    """덱이 하나 있는 미생물학 편. 굽기는 흉내 낸다 — 무엇을 언제 굽는지가 여기 관심이다."""
    run = tmp_path / "260921_03"
    run.mkdir()
    (run / "deck.apkg").write_bytes(b"old")
    monkeypatch.setattr(deck, "config_of",
                        lambda run_dir, kind: {"deck": "미생물학::[260921_03] 인수공통감염", "id": "x"})
    baked = []

    def fake_one(t, runs_dir):
        # 진짜 `deck.rebuild` 가 하는 것처럼 판정 표시를 남긴다.
        apkg = t.run_dir / "deck.apkg"
        apkg.write_bytes(b"new")
        edits = deck.site_edits_path(t.run_dir, t.kind)
        mark = deck.site_edits_mark(t.run_dir, t.kind)
        if edits.is_file():
            mark.write_text(json.dumps({"sha256": deck._sha(edits), "apkg": apkg.name,
                                        "mtime_ns": apkg.stat().st_mtime_ns}), encoding="utf-8")
        elif mark.is_file():
            mark.unlink()
        baked.append((t.run_dir.name, t.kind))
        return True, {"site_edits": {"edited": ["c002"]} if edits.is_file() else {}}

    monkeypatch.setattr(rebuild, "one", fake_one)
    monkeypatch.setattr(rebuild, "target",
                        lambda run_dir, kind: rebuild.Target(run_dir, kind, {"deck": "미생물학::x"}, run_dir))
    monkeypatch.setattr(deck, "apkg_of", lambda run_dir, kind: Path(run_dir) / "deck.apkg")
    return tmp_path, baked


def test_판정을_적고_그_편만_굽는다(runs):
    root, baked = runs
    lines = site_edits.sync(FakeClient([a_row()]), root)

    written = json.loads((root / "260921_03" / "site_edits.main.json").read_text(encoding="utf-8"))
    assert [e["item_id"] for e in written["edits"]] == ["c002"]
    assert "editedAt" not in json.dumps(written), "시각을 실으면 같은 판정에도 괜히 다시 굽는다"
    assert baked == [("260921_03", "main")]
    assert "다시 구운 덱 1편" in lines[0]


def test_같은_판정이면_다시_안_굽는다(runs):
    root, baked = runs
    site_edits.sync(FakeClient([a_row()]), root)
    site_edits.sync(FakeClient([a_row()]), root)
    assert baked == [("260921_03", "main")]


def test_파이프라인이_덱을_새로_구우면_다시_얹는다(runs):
    """판정 없이 구운 덱이 나가면 apkg 노트 수와 item_count 가 갈려 문지기가 막는다."""
    root, baked = runs
    site_edits.sync(FakeClient([a_row()]), root)
    apkg = root / "260921_03" / "deck.apkg"
    apkg.write_bytes(b"pipeline")  # 새로 구웠다
    import os
    os.utime(apkg, ns=(apkg.stat().st_atime_ns, apkg.stat().st_mtime_ns + 10_000_000))
    site_edits.sync(FakeClient([a_row()]), root)
    assert baked == [("260921_03", "main")] * 2


def test_판정을_거두면_파일을_지우고_원래대로_굽는다(runs):
    root, baked = runs
    site_edits.sync(FakeClient([a_row()]), root)
    site_edits.sync(FakeClient([]), root)

    assert not (root / "260921_03" / "site_edits.main.json").exists()
    assert not (root / "260921_03" / "site_edits.main.built.json").exists()
    assert baked == [("260921_03", "main")] * 2


def test_남의_과목_편에는_안_얹는다(runs):
    """`run_id` 에는 과목이 없다 — 같은 교시를 두 과목이 나눠 쓸 수 있다."""
    root, baked = runs
    lines = site_edits.sync(FakeClient([a_row(subject="병리학")]), root)
    assert baked == []
    assert not (root / "260921_03" / "site_edits.main.json").exists()
    assert any("구울 자리를 못 찾았다" in line for line in lines)


def test_계약이_판정을_얹고_빈칸_원문을_싣는다(tmp_path, monkeypatch):
    """덱과 계약이 **같이** 얹어야 apkg 노트 수와 item_count 가 맞는다."""
    run = tmp_path / "260921_03"
    run.mkdir()
    cards = [
        {"id": "c001", "card_format": "basic", "q": "원래 질문", "a": "답", "explanation": "해설"},
        {"id": "c002", "card_format": "cloze", "q": "먼저 {{c1::동물}}이다", "a": "동물",
         "explanation": ""},
    ]
    monkeypatch.setattr(deck, "apkg_of", lambda run_dir, kind: run_dir / "deck.apkg")
    monkeypatch.setattr(deck, "config_of", lambda run_dir, kind: {"id": "x"})
    monkeypatch.setattr(deck, "cards_of", lambda run_dir, kind=deck.MAIN, version=None: cards)
    monkeypatch.setattr(deck.quizgen_build, "counts", lambda apkg: {})
    (run / "deck.apkg").write_bytes(b"apkg")
    deck.site_edits_path(run, deck.MAIN).write_text(json.dumps({"edits": [
        {"item_id": "c001", "action": "delete",
         "original": {"stem": "원래 질문", "answer": "답", "explanation": "해설"}}]}),
        encoding="utf-8")

    meta = deck.contract(run, run.name, "제목", deck.MAIN)
    items = json.loads((run / "main_items.final.json").read_text(encoding="utf-8"))["items"]

    assert meta["item_count"] == 1
    assert meta["site_edits"] == {"deleted": ["c001"]}
    assert [i["id"] for i in items] == ["c002"]
    assert items[0]["stem"] == "먼저 [____]이다"
    assert items[0]["source_stem"] == "먼저 {{c1::동물}}이다"


def test_다시_굽기는_결함이_있어도_굽고_판정을_넘긴다(tmp_path, monkeypatch):
    calls = []

    class Done:
        returncode, stdout, stderr = 0, "", ""

    monkeypatch.setattr(deck.subprocess, "run", lambda argv, **kw: calls.append(argv) or Done())
    run = tmp_path / "r"
    run.mkdir()
    deck.site_edits_path(run, deck.MAIN).write_text('{"edits": []}', encoding="utf-8")
    ok, _ = deck.rebuild(run_dir=run, kind=deck.MAIN, deck_name="d", id="x", jokbo_dir=tmp_path,
                         apkg_name="n", repo_root=tmp_path)
    assert ok
    assert "--allow-defects" in calls[0]
    assert calls[0][calls[0].index("--site-edits") + 1] == str(deck.site_edits_path(run, deck.MAIN))
