"""프롬프트 파트가 지난 실행 것과 섞이면 안 된다.

2026-09-08에 실습 5편을 다시 구웠다. 그날 붙인 기출 조각이 화면에 「물렸다」고
찍혔는데 **넷이 9월 1~4일 프롬프트로 돌았고 모델은 그 조각을 한 글자도 못 봤다.**

파트 수가 실행마다 다른 것이 원인이다. 자료가 늘면 `prompt.cards.1of2.md` 였던 편이
`1of3.md` 가 되는데, 옛 파일을 안 지우니 둘이 나란히 남는다. 그리고 고르는 규칙이
**둘 다 옛것을 먼저 집는다** — `<stem>.md`(1파트짜리)를 무조건 먼저 보고, 없으면
`1of*` 를 이름순으로 집으니 `1of2` 가 `1of3` 을 이긴다.

**카드는 멀쩡히 나온다.** 그래서 스키마도 재현 검사도 문지기도 안 걸린다. 드러나는
자리는 「기출을 왜 안 썼지」뿐이고, 그건 모델 변덕으로 읽힌다.
"""

import json

import pytest

from quizgen.pack import write_parts

LONG = "가" * 40_000       # 한 파트에 안 들어가는 길이


def _run(tmp_path):
    """`quizgen.run` 의 프롬프트 고르기만 떼어 쓴다."""
    from quizgen.run import Runner

    obj = Runner.__new__(Runner)
    obj.out = tmp_path
    return obj


def test_파트_수가_줄면_옛_파일이_남지_않는다(tmp_path):
    write_parts(tmp_path, "prompt.cards", [LONG, LONG, LONG], manifest=True)
    assert sorted(p.name for p in tmp_path.glob("prompt.cards*")) == [
        "prompt.cards.1of3.md", "prompt.cards.2of3.md", "prompt.cards.3of3.md"]

    write_parts(tmp_path, "prompt.cards", ["짧다"], manifest=True)
    assert sorted(p.name for p in tmp_path.glob("prompt.cards*")) == ["prompt.cards.md"]


def test_파트_수가_늘면_옛_파일이_남지_않는다(tmp_path):
    write_parts(tmp_path, "prompt.plan", [LONG, LONG], manifest=True)
    write_parts(tmp_path, "prompt.plan", [LONG, LONG, LONG], manifest=True)
    assert sorted(p.name for p in tmp_path.glob("prompt.plan*")) == [
        "prompt.plan.1of3.md", "prompt.plan.2of3.md", "prompt.plan.3of3.md"]


def test_다른_stem_은_건드리지_않는다(tmp_path):
    write_parts(tmp_path, "prompt.plan", [LONG, LONG], manifest=True)
    write_parts(tmp_path, "prompt.cards", [LONG, LONG], manifest=True)
    write_parts(tmp_path, "context", [LONG, LONG, LONG])
    write_parts(tmp_path, "prompt.cards", ["짧다"], manifest=True)

    assert (tmp_path / "prompt.plan.1of2.md").is_file()
    assert len(list(tmp_path.glob("context.*of*.md"))) == 3


def test_옛_판이_남아_있으면_새것을_고르고_말한다(tmp_path, capsys):
    """`write_parts` 가 안 돈 자리(재개 등)를 위한 두 번째 그물."""
    old = tmp_path / "prompt.cards.1of2.md"
    old.write_text("어제 것", encoding="utf-8")
    single = tmp_path / "prompt.cards.md"
    single.write_text("그저께 것", encoding="utf-8")
    import os
    import time
    stale = time.time() - 3 * 86400
    for p in (old, single):
        os.utime(p, (stale, stale))
    fresh = tmp_path / "prompt.cards.1of3.md"
    fresh.write_text("오늘 것", encoding="utf-8")

    got = _run(tmp_path).prompt_path("cards")
    assert got == fresh
    out = capsys.readouterr().out
    assert "제일 새것을 쓴다" in out
    assert "prompt.cards.md" in out       # 버린 것을 이름으로 적는다


def test_프롬프트가_아예_없으면_실패한다(tmp_path):
    from quizgen.run import Failed

    with pytest.raises(Failed):
        _run(tmp_path).prompt_path("cards")


def test_파트1이_나머지를_읽으라고_적는다(tmp_path):
    """옛 파일을 지운 뒤에도 목록은 새 파일들을 가리켜야 한다."""
    write_parts(tmp_path, "context", [LONG, LONG])
    files = write_parts(tmp_path, "prompt.plan", [LONG, LONG, LONG], manifest=True)
    head = (tmp_path / files[0]["name"]).read_text(encoding="utf-8")
    assert "prompt.plan.1of3.md" in head
    assert "prompt.plan.3of3.md" in head
    assert "1of2" not in head
    assert json.dumps([f["name"] for f in files])  # 목록을 돌려준다
