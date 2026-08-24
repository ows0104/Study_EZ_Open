"""「다시 만들기」가 어디까지 가는가.

이 길에는 **조용히 아무것도 안 하는 자리**가 있다. `prequeue`는 이미 만든 편을
`done`으로 보고 건너뛰므로, 사람이 다시 만들라고 눌러도 산출물이 그대로 남아
있으면 아무 일도 일어나지 않는다. 그러면 러너는 「덱을 못 만들었다」로 적는다 —
만든 것이 있는데 실패로 보이는 자리다. 그래서 눌렀다는 사실이 여기까지 온다.
"""

import json
import types
from pathlib import Path

from studyez import deck, prequeue

URL = "https://chatgpt.com/share/abc"


def _seat(tmp_path: Path, *, built: bool, url: str = URL) -> prequeue.Target:
    """작년 자리 하나를 세운다. 예습 대화가 앉아 있고, 문항은 있을 수도 없을 수도."""
    run_dir = tmp_path / "250825_02"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "preview.md").write_text(f"# 예습 대화\n\n- 출처: {url}\n", encoding="utf-8")
    if built:
        (run_dir / "pre_items.final.json").write_text("[]", encoding="utf-8")
    return prequeue.Target(
        link=prequeue.Link(subject="병리학", run_id="260824_02", date="2026-08-24",
                           title="종양의 병태 생리(2)", share_url=URL),
        prev_run_id="250825_02",
        prev_pdf=str(tmp_path / "250825_02.pdf"),
        this_title="종양의 병태 생리(2)")


def test_같은_대화면_이미_있는_것이다(tmp_path):
    target = _seat(tmp_path, built=True)
    prequeue.prepare([target], tmp_path)
    assert target.state == prequeue.DONE
    assert target.force is False


def test_다시_만들라고_누르면_다시_만든다(tmp_path):
    target = _seat(tmp_path, built=True)
    prequeue.prepare([target], tmp_path, force=True)
    assert target.state == prequeue.STALE
    assert target.force is True


def test_아직_만든_것이_없어도_눌릴_수_있다(tmp_path):
    # 덱은 서버에 있는데 이 노트북에는 없을 수 있다. 그때도 만들 자리는 선다.
    target = _seat(tmp_path, built=False)
    prequeue.prepare([target], tmp_path, force=True)
    assert target.state == prequeue.READY
    assert target.force is True


def test_눌린_편은_pdf2anki까지_force로_간다(tmp_path, monkeypatch):
    """중간 산출물을 이어받으면 「다시 만들었는데 그대로다」가 된다."""
    seen: dict = {}

    def fake_run_pre(**kwargs):
        seen.update(kwargs)
        return types.SimpleNamespace(ok=False, error="여기까지만 본다", log=tmp_path / "x.log")

    monkeypatch.setattr(deck, "run_pre", fake_run_pre)

    target = _seat(tmp_path, built=True)
    prequeue.prepare([target], tmp_path, force=True)
    ok, _ = prequeue.build_one(target, tmp_path, tmp_path)
    assert ok is False                       # 가짜라 여기서 멈춘다
    assert "--force" in seen["extra"]


def test_그냥_만드는_편에는_안_붙는다(tmp_path, monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(deck, "run_pre", lambda **kwargs: (
        seen.update(kwargs) or types.SimpleNamespace(ok=False, error="", log=tmp_path / "x.log")))

    target = _seat(tmp_path, built=False)
    prequeue.prepare([target], tmp_path)
    prequeue.build_one(target, tmp_path, tmp_path)
    assert "--force" not in seen["extra"]


def test_자리_표시에_올해_강의가_적힌다(tmp_path):
    # 다시 만들 때도 덱 이름은 올해 강의로 서야 한다. 그 값이 여기서 간다.
    target = _seat(tmp_path, built=True)
    prequeue.prepare([target], tmp_path, force=True)
    row = json.loads((tmp_path / "250825_02" / deck.TARGET_NAME).read_text(encoding="utf-8"))
    assert row["run_id"] == "260824_02"
