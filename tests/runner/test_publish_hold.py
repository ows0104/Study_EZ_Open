"""`publish.hold_pre` — 링크가 바뀐 편에서 무엇이 나가고 무엇이 남는가.

여기 있는 것이 이 함수의 존재 이유다: **덱은 붙들고 링크는 내보낸다.** 반대로
하면(`hold_artifacts`처럼 링크까지 붙들면) `publish`가 관리자가 방금 저장한
링크를 옛 것으로 되돌린다 — 막으려던 바로 그 일이다.
"""

from pathlib import Path

from runner import publish


def a_plan(tmp_path: Path) -> publish.LecturePlan:
    plan = publish.LecturePlan(
        subject="병리학", run_id="260824_01",
        item=publish.LectureFile.__new__(publish.LectureFile),
        prev_run_id="250825_01")
    for kind in ("notes_current", "notes_prev", "main_apkg", "pre_apkg", "media", "media"):
        path = tmp_path / f"{kind}.bin"
        path.write_bytes(b"x")
        plan.uploads.append(publish.Upload(kind, path))
    plan.run_meta = {"main": tmp_path / "run.meta.json", "pre": tmp_path / "pre_run.meta.json"}
    plan.pre_items = tmp_path / "pre_items.final.json"
    plan.preview_url = "https://chatgpt.com/share/새-대화"
    return plan


def test_링크는_나가고_예습_산출물만_남는다(tmp_path):
    plan = a_plan(tmp_path)
    publish.hold_pre(plan, "링크가 바뀌었다")

    assert plan.preview_url == "https://chatgpt.com/share/새-대화"
    assert plan.pre_items is None
    assert "pre" not in plan.run_meta
    assert [u.kind for u in plan.uploads] == ["notes_current", "notes_prev", "main_apkg"]
    assert any("미룬 것" in note for note in plan.notes)


def test_미룬_것을_적는다(tmp_path):
    plan = a_plan(tmp_path)
    publish.hold_pre(plan, "링크가 바뀌었다")
    note = next(n for n in plan.notes if "미룬 것" in n)
    for held in ("pre_apkg", "media×2", "run-meta pre", "pre-items"):
        assert held in note


def test_예습이_없는_편은_그대로다(tmp_path):
    plan = publish.LecturePlan(
        subject="병리학", run_id="260824_01",
        item=publish.LectureFile.__new__(publish.LectureFile))
    path = tmp_path / "notes.pdf"
    path.write_bytes(b"x")
    plan.uploads.append(publish.Upload("notes_current", path))
    publish.hold_pre(plan, "링크가 바뀌었다")

    assert [u.kind for u in plan.uploads] == ["notes_current"]
    assert plan.notes == []


# ── 한 장이 없다고 편 전체를 버리지 않는다 ────────────────────────────
# 2026-09-02, 계획을 세운 뒤 슬라이드 한 장이 사라져서 103장짜리 덱이 통째로 안
# 올라갔다. 그 자리를 다시 채우는 코드가 따로 돌기 때문에 생길 수 있는 일이다.


class FakeClient:
    base = "http://test"

    def __init__(self, vanish: Path | None = None):
        self.put = []
        # 서명을 받아 온 **뒤** 사라진다. 실제로 그 순서였다 — 계획도 서명도 그
        # 파일이 있을 때 만들어졌고, 올리려고 열었을 때 없었다.
        self.vanish = vanish

    def call(self, method, path, body=None):
        if path.endswith("/uploads"):
            if self.vanish is not None:
                self.vanish.unlink()
            return {"files": [{"filename": row["filename"], "uploadUrl": f"/u/{row['filename']}"}
                              for row in body]}
        if path.endswith("/uploads/complete"):
            return {"missing": []}
        return {}

    def put_file(self, url, path):
        self.put.append(path.name)


def test_사라진_한_장은_건너뛰고_나머지를_올린다(tmp_path):
    plan = publish.LecturePlan(
        subject="기생충학", run_id="260902_01",
        item=publish.LectureFile.__new__(publish.LectureFile))
    for name in ("s008.png", "s025.png"):
        path = tmp_path / name
        path.write_bytes(b"png")
        plan.uploads.append(publish.Upload("main_media", path))
    client, report = FakeClient(vanish=tmp_path / "s008.png"), publish.Report()
    publish._publish_one(plan, client, {}, report, force=True, log=lambda *_: None)

    assert client.put == ["s025.png"], "남은 것을 안 올렸다"
    assert any("사라졌다" in line and "s008.png" in line for line in report.failures)


# ── 걸린 갈래만 미룬다 ────────────────────────────────────────────────
# 2026-09-19. `blocking`이 문자열 한 뭉치라 **올해 필기가 v2로 갈렸다는 사유
# 하나가 작년 폴더의 예습 덱까지 붙들었다.** 예습은 작년 자료로 만들고 올해
# 필기를 읽지도 않는다. 그때 재 보니 검문에 걸린 10편 중 7편이 자기와 무관한
# 갈래 때문에 같이 묶여 있었다.


def test_main_사유는_예습을_안_붙든다(tmp_path):
    plan = a_plan(tmp_path)
    plan.main_items = tmp_path / "main_items.final.json"
    plan.blocking.append(publish.Block(
        publish.MAIN, "260911_02의 산출물이 지금 필기와 다르다 — 산출물은 v1 로 만들었는데 필기는 v2 이다"))
    publish.hold_blocked(plan)

    assert [u.kind for u in plan.uploads] == ["notes_current", "notes_prev", "pre_apkg", "media", "media"]
    assert plan.pre_items is not None, "예습 문항이 같이 미뤄졌다"
    assert plan.run_meta == {"pre": tmp_path / "pre_run.meta.json"}
    assert plan.preview_url, "예습 링크가 같이 미뤄졌다"
    assert plan.main_items is None


def test_pre_사유는_복습을_안_붙든다(tmp_path):
    plan = a_plan(tmp_path)
    plan.main_items = tmp_path / "main_items.final.json"
    plan.blocking.append(publish.Block(
        publish.PRE, "Pre-Quiz 문항 결함으로 갈린 카드가 덱에 1장 남아 있다 (c016)"))
    publish.hold_blocked(plan)

    assert "main_apkg" in [u.kind for u in plan.uploads]
    assert plan.main_items is not None, "복습 문항이 같이 미뤄졌다"
    assert plan.pre_items is None


def test_둘_다_걸리면_통째로_미룬다(tmp_path):
    plan = a_plan(tmp_path)
    plan.main_items = tmp_path / "main_items.final.json"
    plan.blocking += [publish.Block(publish.MAIN, "Main-Quiz 보류"),
                      publish.Block(publish.PRE, "Pre-Quiz 보류")]
    publish.hold_blocked(plan)

    assert [u.kind for u in plan.uploads] == ["notes_current", "notes_prev"]
    assert plan.pre_items is None and plan.main_items is None
    assert plan.preview_url == ""


def test_사유는_문자열로_찍힌다(tmp_path):
    """`cycle`이 `f"✋ {reason}"`으로 찍는다 — 갈래를 붙이면서 깨지면 안 된다."""
    block = publish.Block(publish.MAIN, "산출물이 지금 필기와 다르다")
    assert f"{block}" == "산출물이 지금 필기와 다르다"
