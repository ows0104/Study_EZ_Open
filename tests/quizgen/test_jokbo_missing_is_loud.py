"""족보를 못 물렸을 때 조용히 넘어가지 않는다.

2026-08-27 배치에서 **7편이 기출 0장으로 나왔는데 아무도 몰랐다.**
`quizgen.run` 의 `--jokbo-dir` 기본값이 `out/jokbo` 인데 그 폴더가 없었고,
`slice_for` 가 아무 말 없이 `None` 을 돌려줬다.

그 결과가 조용했던 이유가 중요하다 — **기출 카드는 지워진 것이 아니라 계획 단계부터
안 세워졌다.** 그 편들의 `plan.json` 은 기출 목표가 0개이고, 검증도 수선도 재현 검사도
지울 것이 없으니 아무 신호를 내지 않는다. `items.raw.json` 과 최종본의 기출 수가 같다.

야간 러너도 같은 구멍에 빠진다 — `deck.py` 가 `--jokbo-dir` 을 늘 넘기지만, 그 과목의
족보를 아직 안 잘랐으면 없는 경로를 넘긴다.
"""

import json

import pytest

from quizgen.assemble import slice_for


def _prep(source="[260820_02] 소아질환의 병태생리(1)(김은선)_한태희v1.pdf"):
    return {"source": source, "slides": 5,
            "pages": [{"slide": i, "lecture_figures": [], "occlusion_candidates": []}
                      for i in range(1, 6)]}


def test_족보_폴더가_없으면_크게_알린다(tmp_path, capsys):
    got = slice_for(_prep(), tmp_path / "없는폴더")
    out = capsys.readouterr().out
    assert got == (None, {}, False)              # 돌려주는 값은 예전 그대로다
    assert "기출 카드가 한 장도 안 나온다" in out
    assert "runner jokbo" in out                # 어떻게 고치는지도 말한다


def test_조각을_못_찾으면_그것도_알린다(tmp_path, capsys):
    """폴더는 있는데 이 강의에 맞는 조각이 없는 경우. 원인이 다르니 말도 달라야 한다."""
    (tmp_path / "index.json").write_text(
        json.dumps({"lectures": [{"lecture_key": "L01", "title": "전혀 다른 강의",
                                  "file": "L01_전혀-다른-강의"}]}),
        encoding="utf-8")
    got = slice_for(_prep(), tmp_path)
    out = capsys.readouterr().out
    assert got == (None, {}, False)
    assert "일치도" in out
    assert "기출 카드가 한 장도 안 나온다" not in out    # 원인이 다르다


def test_직접_지정하면_묻지도_따지지도_않는다(tmp_path, capsys):
    """`--jokbo` 로 조각을 손으로 주면 폴더를 볼 이유가 없다."""
    p = tmp_path / "조각.json"
    p.write_text(json.dumps({"stats": {"n": 3}, "may_contain": []}), encoding="utf-8")
    path, stats, mixed = slice_for(_prep(), tmp_path / "없는폴더", str(p))
    assert path == p and stats == {"n": 3} and mixed is False
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("subdir", ["없는폴더", "out/jokbo"])
def test_기본값도_예외가_아니다(tmp_path, capsys, subdir):
    """`out/jokbo` 는 기본값이라 더 조용히 지나가기 쉬웠다. 똑같이 알린다."""
    slice_for(_prep(), tmp_path / subdir)
    assert "족보를 물리지 않았다" in capsys.readouterr().out


# ── 왜 안 붙었는지가 남는가 (2026-09-14, `docs/runs-layout.md` 3단계) ──────────
#
# 위의 세 갈래는 **화면에는 다르게 찍히는데 파일에는 아무것도 안 남았다.** 그래서
# 나중에 「이 편은 기출이 왜 0장인가」를 물으면 로그를 찾아야 하고, 로그는 지워진다.
# `slice_for_recorded` 가 그 사유를 한 장으로 돌려준다.

def test_폴더가_없다는_사유가_기록에_남는다(tmp_path):
    from quizgen.assemble import slice_for_recorded
    _, _, _, rec = slice_for_recorded(_prep(), tmp_path / "없는폴더")
    assert rec["attached"] is False
    assert "안 잘렸다" in rec["why_not"]


def test_문턱에_걸렸다는_사유가_기록에_남는다(tmp_path):
    """재료가 없는 것과 **다른 사유**다 — 처방이 다르다."""
    from quizgen.assemble import slice_for_recorded
    (tmp_path / "index.json").write_text(
        json.dumps({"lectures": [{"lecture_key": "L01", "title": "전혀 다른 강의",
                                  "file": "L01_전혀-다른-강의"}]}),
        encoding="utf-8")
    _, _, _, rec = slice_for_recorded(_prep(), tmp_path)
    assert rec["attached"] is False
    assert "문턱" in rec["why_not"]
    assert "안 잘렸다" not in rec["why_not"]


def test_손으로_지정한_것도_그렇게_적힌다(tmp_path):
    """점수를 안 적는다 — 대조를 안 했으니 점수가 없다. 0.0 으로 적으면 거짓이다."""
    from quizgen.assemble import slice_for_recorded
    p = tmp_path / "조각.json"
    p.write_text(json.dumps({"stats": {}, "may_contain": []}), encoding="utf-8")
    _, _, _, rec = slice_for_recorded(_prep(), tmp_path / "없는폴더", str(p))
    assert rec["attached"] is True
    assert rec["score"] is None
    assert "사람이" in rec["by"]
