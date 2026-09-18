"""「어디까지 왔고 얼마나 남았나」를 지난 편들에서 셈하는 자리.

**표본이 없으면 아무 말도 안 한다**가 이 모듈의 약속이다. 지어낸 숫자를 「예상
18분」이라고 적으면 그 뒤로 아무도 그 값을 안 믿는다.
"""

import json

from runner import eta


def _run(runs, run_id, kind, wall, steps, stages, finished=True):
    """한 편의 산출물. `finished=False`면 도중에 죽은 편이다 — 마지막 단계가 없다."""
    if finished and eta.FINAL_STAGE not in [name for name, _ in steps]:
        steps = [*steps, (eta.FINAL_STAGE, 5)]
        stages = [*stages, eta.FINAL_STAGE] if eta.FINAL_STAGE not in stages else stages
    run_dir = runs / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.report.json").write_text(json.dumps({
        "wall_seconds": wall,
        "steps": [{"step": name, "seconds": seconds} for name, seconds in steps],
    }), encoding="utf-8")
    log = "pipeline.log" if kind == eta.MAIN else "prequiz.log"
    (run_dir / log).write_text("\n".join(f"── {stage}" for stage in stages), encoding="utf-8")
    return run_dir


def _fresh():
    eta._cache.clear()


def test_표본이_없으면_아무_값도_안_낸다(tmp_path):
    _fresh()
    guess = eta.estimate(tmp_path, eta.MAIN, "② 카드", elapsed=300)
    assert (guess.index, guess.total, guess.eta_seconds) == (0, 0, 0)


def test_몇_번째_단계인지는_로그의_차례에서_온다(tmp_path):
    _fresh()
    _run(tmp_path, "260831_01", eta.MAIN, 1800,
         [("② 카드", 600), ("풀이", 120)], ["자료 준비 (prep)", "② 카드", "풀이", "덱 빌드"])
    guess = eta.estimate(tmp_path, eta.MAIN, "② 카드", elapsed=300)
    assert (guess.index, guess.total) == (2, 4)


def test_남은_단계들의_합으로_센다(tmp_path):
    _fresh()
    _run(tmp_path, "260831_01", eta.MAIN, 1800,
         [("② 카드", 600), ("풀이", 120), ("덱 빌드", 30)],
         ["② 카드", "풀이", "덱 빌드"])
    # ② 카드에 100초 있었으면 남은 것은 (600-100) + 120 + 30.
    guess = eta.estimate(tmp_path, eta.MAIN, "② 카드", elapsed=100, stage_elapsed=100)
    assert 640 <= guess.eta_seconds <= 660


def test_마지막_단계에서_전체_중앙값으로_물러서지_않는다(tmp_path):
    """물러서면 다 끝나 가는 편이 「20분 남았다」고 말한다."""
    _fresh()
    _run(tmp_path, "260831_01", eta.MAIN, 1800,
         [("② 카드", 600), ("덱 빌드", 30)], ["② 카드", "덱 빌드"])
    guess = eta.estimate(tmp_path, eta.MAIN, "덱 빌드", elapsed=700, stage_elapsed=10)
    assert guess.eta_seconds <= 30


def test_단계를_모르면_편_전체의_중앙값에서_뺀다(tmp_path):
    _fresh()
    _run(tmp_path, "260831_01", eta.MAIN, 1800, [], ["② 카드"])
    guess = eta.estimate(tmp_path, eta.MAIN, "처음 보는 단계", elapsed=600)
    assert 1150 <= guess.eta_seconds <= 1250


def test_이어_돌린_회차는_시간_표본이_아니다(tmp_path):
    """`--resume`으로 몇 초 만에 끝난 편이 섞이면 중앙값이 통째로 내려간다."""
    _fresh()
    _run(tmp_path, "260831_01", eta.MAIN, 1800, [], ["② 카드"])
    _run(tmp_path, "260831_02", eta.MAIN, 5, [], ["② 카드"])
    assert eta.samples(tmp_path, eta.MAIN).totals == [1800]


def test_갈래를_섞지_않는다(tmp_path):
    """예습과 복습은 걸리는 시간이 다르다. 섞으면 예습이 복습 쪽으로 끌려간다."""
    _fresh()
    _run(tmp_path, "260831_01", eta.MAIN, 1800, [], ["② 카드"])
    _run(tmp_path, "250915_01", eta.PRE, 900, [], ["② 카드"])
    assert eta.samples(tmp_path, eta.MAIN).totals == [1800]
    assert eta.samples(tmp_path, eta.PRE).totals == [900]


def test_회차와_개수가_붙은_단계는_한_이름으로_모은다():
    assert eta.canon("수선 1/2  (결함 4장)") == "수선"
    assert eta.canon("수선 2/2") == "수선"
    # 원래 이름에 붙어 있는 괄호는 이름의 일부다.
    assert eta.canon("자료 준비 (prep)") == "자료 준비 (prep)"


def test_러너가_잰_단계도_표본이_된다(tmp_path):
    """`run.report.json`의 `steps`는 파이프라인이 아는 단계만 적는다. 러너가 화면에
    올리는 단계는 더 촘촘해서, 겹치지 않는 것은 이 길이 아니면 잴 수 없다."""
    _fresh()
    _run(tmp_path, "260831_01", eta.MAIN, 1800, [], ["자료 준비 (prep)", "② 카드"])
    eta.observe(tmp_path, eta.MAIN, "자료 준비 (prep)", 42)
    _fresh()
    assert eta.samples(tmp_path, eta.MAIN).stage_seconds["자료 준비 (prep)"] == 42


# ── 분모는 한 편에 안 걸린다 ──────────────────────────────────────────
# 2026-09-02에 같은 배치의 예습 두 편이 `7/7`과 `7/18`로 끝났다. 차례를 「가장
# 최근에 끝난 편」 하나에서만 가져왔기 때문이다.


def _aged(run_dir, stamp):
    import os
    for name in ("run.report.json", "prequiz.log", "pipeline.log"):
        path = run_dir / name
        if path.is_file():
            os.utime(path, (stamp, stamp))


def test_도중에_죽은_편은_분모를_못_바꾼다(tmp_path):
    """2026-09-02에 한도로 죽은 복습 셋이 최근 표본을 채우자 `main`의 총 단계가
    5로 떨어졌고 `② 카드`가 차례에서 아예 빠졌다 — 그 편들은 거기까지 못 갔다."""
    _fresh()
    full = ["자료 준비 (prep)", "① 반드시 알아야 할 것", "② 카드", "누출", "풀이", "채점", "덱 빌드"]
    for index, run_id in enumerate(("250917_01", "250917_02", "250917_03")):
        _aged(_run(tmp_path, run_id, eta.PRE, 900, [("② 카드", 400)], full), 1_000 + index)
    # 가장 최근 편이 앞부분에서 죽었다. 그 로그에는 앞 두 단계밖에 없다.
    _aged(_run(tmp_path, "250917_05", eta.PRE, 900, [("자료 준비 (prep)", 3)],
               ["자료 준비 (prep)", "① 반드시 알아야 할 것"], finished=False), 9_999)

    guess = eta.estimate(tmp_path, eta.PRE, "② 카드", elapsed=300)
    assert guess.total == len(full), "죽은 편이 분모를 끌어내렸다"
    assert guess.index == 3


def test_끝까지_간_편이_하나도_없으면_아무_말도_안_한다(tmp_path):
    _fresh()
    _run(tmp_path, "250917_05", eta.PRE, 900, [("자료 준비 (prep)", 3)],
         ["자료 준비 (prep)"], finished=False)
    assert eta.samples(tmp_path, eta.PRE).order == []


def test_차례는_실제로_있던_한_편의_것이다(tmp_path):
    """이름을 여러 편에서 기워 붙이면 어느 편에도 없던 차례가 만들어진다."""
    _fresh()
    _aged(_run(tmp_path, "250917_01", eta.PRE, 900, [], ["prep", "카드"]), 1_000)
    _aged(_run(tmp_path, "250917_02", eta.PRE, 900, [], ["prep", "누출"]), 2_000)
    order = eta.samples(tmp_path, eta.PRE).order
    assert order in (["prep", "카드", eta.FINAL_STAGE], ["prep", "누출", eta.FINAL_STAGE])


# ── 시도가 판 폴더로 내려간 뒤 ────────────────────────────────────────
# 2026-09-15에 새 실행이 `runs/<편>/<갈래>/<판>/` 에 쓰기 시작했는데
# (`runlayout.WRITES_ATTEMPT_DIRS`) 보고서를 훑는 글롭이 안 따라갔다. 2026-09-18에
# 트리의 보고서 226개 중 **1개**만 읽히고 있었다.


def _attempt(runs, run_id, kind, version, wall, steps, stages, log_at="attempt"):
    """새 모양으로 한 판. `log_at="lecture"`면 로그가 강의 폴더에만 있다."""
    if eta.FINAL_STAGE not in [name for name, _ in steps]:
        steps = [*steps, (eta.FINAL_STAGE, 5)]
    if eta.FINAL_STAGE not in stages:
        stages = [*stages, eta.FINAL_STAGE]
    folder = eta._KIND_DIRS[kind]
    work = runs / run_id / folder / version
    work.mkdir(parents=True, exist_ok=True)
    (work / "run.report.json").write_text(json.dumps({
        "wall_seconds": wall,
        "steps": [{"step": name, "seconds": seconds} for name, seconds in steps],
    }), encoding="utf-8")
    log = (work if log_at == "attempt" else runs / run_id) / eta._LOGS[kind]
    log.write_text("\n".join(f"── {stage}" for stage in stages), encoding="utf-8")
    return work


def test_판_폴더에_있는_보고서를_읽는다(tmp_path):
    _fresh()
    _attempt(tmp_path, "260917_05", eta.MAIN, "260917-0410", 1800,
             [("② 카드", 600)], ["자료 준비 (prep)", "② 카드"])
    data = eta.samples(tmp_path, eta.MAIN)
    assert data.totals == [1800]
    assert data.order == ["자료 준비 (prep)", "② 카드", eta.FINAL_STAGE]


def test_갈래는_판_폴더_이름에서_온다(tmp_path):
    """**한 편에 두 갈래가 다 있는 자리가 흔하다** — 작년 강의록으로 예습을 만들고
    같은 자리에서 복습도 만든 편들. 옛 모양에서는 로그 시각으로 짐작해야 했고
    그래서 뒤에 돈 갈래 쪽으로만 세어졌다. 판 폴더는 갈래를 적어 둔다.
    """
    _fresh()
    _attempt(tmp_path, "250904_05", eta.MAIN, "260918-0100", 1700, [], ["② 카드"])
    _attempt(tmp_path, "250904_05", eta.PRE, "260918-0543", 850, [], ["② 카드"])
    assert eta.samples(tmp_path, eta.MAIN).totals == [1700]
    _fresh()
    assert eta.samples(tmp_path, eta.PRE).totals == [850]


def test_수선_회차는_한_편의_시간이_아니다(tmp_path):
    """`revisions/` 안의 보고서는 그 회차가 걸린 시간이다. 판 폴더 바로 밑만 센다."""
    _fresh()
    work = _attempt(tmp_path, "260917_05", eta.MAIN, "260917-0410", 1800, [], ["② 카드"])
    fix = work / "revisions" / "v1_260918-1838"
    fix.mkdir(parents=True)
    (fix / "run.report.json").write_text(json.dumps({"wall_seconds": 400}), encoding="utf-8")
    assert eta.samples(tmp_path, eta.MAIN).totals == [1800]


def test_로그가_강의_폴더에만_있어도_차례를_읽는다(tmp_path):
    """옮기는 중인 편이 그렇다 — 2026-09-18에 예습 보고서 64개 중 판 폴더에 로그가
    같이 있는 것은 38개였다."""
    _fresh()
    _attempt(tmp_path, "250901_03", eta.PRE, "260916-1456", 960, [],
             ["자료 준비 (prep)", "① 반드시 알아야 할 것"], log_at="lecture")
    assert eta.samples(tmp_path, eta.PRE).order[:2] == ["자료 준비 (prep)", "① 반드시 알아야 할 것"]


def test_두_모양이_같은_표본에_섞여도_센다(tmp_path):
    """한 나무에 옛 모양과 새 모양이 같이 있다. `runlayout` 이 둘을 같이 읽는 이유와
    같다 — **한 번에 안 갈아도 되게** 한다."""
    _fresh()
    _run(tmp_path, "260831_01", eta.MAIN, 1500, [], ["② 카드"])
    _attempt(tmp_path, "260917_05", eta.MAIN, "260917-0410", 1900, [], ["② 카드"])
    assert sorted(eta.samples(tmp_path, eta.MAIN).totals) == [1500, 1900]
