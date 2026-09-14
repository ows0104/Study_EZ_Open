"""교수별 전략이 붙는지. 표 자체는 관리자 판단이고 여기서는 배선만 본다."""

from runner import watch


def item(professors=(), reason="new", **kw):
    return watch.WorkItem(
        subject="기생충학", run_id="260904_03", key="260904_03", date="2026-09-04",
        title="말라리아(2)", this_pdf="x.pdf", this_version=1, reason=reason,
        professors=tuple(professors), **kw)


def test_표에_있는_교수면_전략이_붙는다():
    assert watch.build_extra(item(["최민호"])) == ["--strategy", "필기"]


def test_표에_없는_교수면_아무것도_안_붙는다():
    assert watch.build_extra(item(["송현범"])) == []
    assert watch.build_extra(item()) == []


def test_연강이라_교수가_둘이어도_잡는다():
    assert "--strategy" in watch.build_extra(item(["신은희", "최민호"]))


def test_사람이_지정한_전략을_덮지_않는다():
    """`--strategy`는 그 편을 지목한 사람이 준 것이다. 표보다 뒤에 온 판단이다."""
    got = watch.build_extra(item(["최민호"]), ["--strategy", "사진"])
    assert got == ["--strategy", "사진"]
    assert got.count("--strategy") == 1


def test_판이_갈린_편은_revise와_같이_붙는다():
    got = watch.build_extra(item(["최민호"], reason="newer_version"))
    assert got == ["--revise", "--strategy", "필기"]


def test_strategy_for는_표에_없으면_None():
    assert watch.strategy_for(["최민호"]) == "필기"
    assert watch.strategy_for(["여선주"]) is None
    assert watch.strategy_for(()) is None
