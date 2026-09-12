"""「족보가 없다」가 두 가지라는 것과, 밀린 것이 몇 편인가.

둘 다 2026-09-12 에 실물에서 나왔다.

**① 두 가지 0.** 블럭이 미생물학으로 넘어갔는데 `studyez jokbo 미생물학` 을
아무도 안 쳤다. 원본 PDF 는 `족보/2026/` 에 있었다. 그동안 화면에 뜬 것은
「족보가 아직 안 잘려 있다」 한 줄이었고 편마다 떴고 아무도 안 봤다. 세 편이
기출 0 으로 나갔고(그 과목 족보의 반복률은 32~74% 다), `260911_03` 은
22.9분·$8.53 을 다 쓴 뒤 **마지막 줄**에서 죽었다 — 모델이 강의록 뒤의 족보
부록에서 기출 카드 3장을 뽑았는데 물릴 조각이 없었다.

같은 날 같은 과목의 다른 세 편은 살았다. **기출 카드를 안 뽑아서였다.** 그러니
그 셋이 산 것은 옳아서가 아니라 운이다. 여기서 지키는 것은 그 운을 없애는 것 —
**자를 수 있는 것을 안 자른 채로는 시작하지 않는다.** 자를 게 없는 과목은 막지
않는다. 사람이 어찌할 수 없는 것을 막으면 그 과목은 영영 안 만들어진다.

**② 밀린 것.** 같은 날 기생충학 7편이 하루 상한 뒤에 줄 서 있었고 제일 오래된
것이 12일째였다. 한 줄씩은 「건너뜀」에 적혀 있었지만 다른 사유와 섞여 있어
**세어지지 않았다.** 상한(2)보다 하루 들어오는 양이 많으면 큐는 원리상 안 주는데,
그 사실이 로그 어디에도 없었다.
"""

import types
from pathlib import Path

from studyez import watch


def _world(tmp_path: Path, *, cut: bool, source: bool) -> tuple[Path, Path]:
    """자료 폴더와 산출물 폴더. 족보의 두 자리를 따로 켠다."""
    root, runs = tmp_path / "drive", tmp_path / "runs"
    (root / "미생물학" / "필기" / "2026").mkdir(parents=True)
    if source:
        folder = watch.jokbo_source_dir(root, "미생물학", "2026")
        folder.mkdir(parents=True)
        (folder / "2026 감염의 기초(미생물학) 족보.pdf").write_bytes(b"%PDF-1.4\n")
    if cut:
        cut_dir = runs / "_jokbo" / "미생물학"
        cut_dir.mkdir(parents=True)
        (cut_dir / "index.json").write_text("{}", encoding="utf-8")
    runs.mkdir(parents=True, exist_ok=True)
    return root, runs


# ------------------------------------------------------------------ ① 두 가지 0

def test_잘려_있으면_ready(tmp_path):
    root, runs = _world(tmp_path, cut=True, source=True)
    assert watch.jokbo_state(runs, "미생물학", root, "2026") == watch.JOKBO_READY


def test_원본이_있는데_안_잘랐으면_uncut(tmp_path):
    root, runs = _world(tmp_path, cut=False, source=True)
    assert watch.jokbo_state(runs, "미생물학", root, "2026") == watch.JOKBO_UNCUT


def test_원본이_없으면_absent(tmp_path):
    """자를 것이 없는 것은 잘못이 아니다. 미생물학 실습 기출이 실제로 그렇다."""
    root, runs = _world(tmp_path, cut=False, source=False)
    assert watch.jokbo_state(runs, "미생물학", root, "2026") == watch.JOKBO_ABSENT


def test_원본_자리를_모르면_막지_않는다(tmp_path):
    """`root` 없이 물으면 UNCUT 을 못 가른다. **덜 아는 쪽이 덜 막아야 한다.**"""
    _root, runs = _world(tmp_path, cut=False, source=True)
    assert watch.jokbo_state(runs, "미생물학") == watch.JOKBO_ABSENT


def test_두_0은_다른_말로_나온다(tmp_path):
    """같은 말로 나오면 사람도 못 가른다 — 그게 이 함정의 전부였다."""
    uncut = watch.jokbo_note(watch.JOKBO_UNCUT, "미생물학")
    absent = watch.jokbo_note(watch.JOKBO_ABSENT, "미생물학")
    assert uncut != absent
    # 고칠 수 있는 쪽에는 고치는 명령이 실려 있어야 한다.
    assert "studyez jokbo 미생물학" in uncut
    assert "studyez jokbo" not in absent
    assert watch.jokbo_note(watch.JOKBO_READY, "미생물학") == ""


# ------------------------------------------------------------------ 자르는 쪽과 세는 쪽

def test_자르는_쪽이_세는_쪽과_같은_함수로_폴더를_찾는다(tmp_path, monkeypatch):
    """`studyez jokbo` 안에 경로가 글자로 박혀 있던 자리다.

    갈리면 조용히 어긋난다 — 자르는 쪽은 원본을 찾는데 세는 쪽은 못 찾아서
    UNCUT 이 안 뜨고, 그러면 이 검사 전체가 무력해진다. 그래서 **같은 함수를
    부르는지**를 본다. 폴더가 맞는지만 보면 두 곳에 같은 글자를 적어 두어도 통과한다.
    """
    from studyez import __main__ as cli

    root, runs = _world(tmp_path, cut=False, source=True)
    asked: list[tuple] = []
    real = watch.jokbo_source_dir

    def spy(base, subject, year):
        asked.append((Path(base), subject, year))
        return real(base, subject, year)

    monkeypatch.setattr(watch, "jokbo_source_dir", spy)
    args = types.SimpleNamespace(subject="미생물학", root=str(root), this="2026",
                                 runs=str(runs), practical="")
    # 자르기 자체는 PDF 가 가짜라 실패한다. 보려는 것은 **어디를 물었는가**다.
    cli.run_jokbo(args)
    assert (root, "미생물학", "2026") in asked


# ------------------------------------------------------------------ ② 밀린 것을 센다

def _queue_with(n_items: int, max_items: int) -> watch.Queue:
    items = [
        watch.WorkItem(subject="기생충학", run_id=f"26090{i}_01", key=f"k{i}",
                       date=f"2026-09-0{i}", title=f"강의 {i}", this_pdf="x.pdf",
                       this_version=1, reason="new")
        for i in range(1, n_items + 1)
    ]
    items.sort(key=lambda w: (w.date, w.run_id))
    backlog = items[max_items:]
    return watch.Queue(generated_at="2026-09-12T00:00:00", items=items[:max_items],
                       skipped=[], warnings=[], backlog=backlog)


def test_상한에_밀린_것이_따로_센다():
    queue = _queue_with(7, max_items=2)
    assert len(queue.items) == 2
    assert len(queue.backlog) == 5
    # 가장 오래된 것이 앞에 선다 — 며칠째인지는 이 날짜로만 안다.
    assert queue.backlog[0].date == "2026-09-03"


def test_밀린_것이_없으면_비어_있다():
    queue = _queue_with(2, max_items=2)
    assert queue.backlog == []


def test_밀린_것이_파일에도_남는다(tmp_path):
    """로그는 흘러간다. 「줄고 있는가」는 날마다 같은 자리를 봐야 보인다."""
    import json

    path = tmp_path / "queue.json"
    watch.save(_queue_with(7, max_items=2), path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert len(saved["backlog"]) == 5
    assert saved["backlog"][0]["run_id"] == "260903_01"


# ------------------------------------------------------------------ 시작 전에 멈춘다

def _one_item_queue(subject="미생물학", run_id="260911_03"):
    return watch.Queue(
        generated_at="2026-09-12T09:52:00",
        items=[watch.WorkItem(subject=subject, run_id=run_id, key="k", date="2026-09-11",
                              title="세균의 형태와 미세구조 및 합성(김범준)", this_pdf="x.pdf",
                              this_version=1, reason="new")],
        skipped=[], warnings=[])


def _watch_one_args(root, runs, **over):
    base = {"runs": str(runs), "run_id": "260911_03", "root": str(root), "this": "2026",
            "subject": "미생물학", "now": True, "force": False, "slides": "",
            "model": "", "timeout": 60, "no_jokbo": False, "build": False}
    base.update(over)
    return types.SimpleNamespace(**base)


def _stub_queue(monkeypatch):
    from studyez import runner
    monkeypatch.setattr(runner.watch, "build_queue", lambda **_k: _one_item_queue())
    return runner


def test_안_잘린_족보면_시작도_안_한다(tmp_path, monkeypatch, capsys):
    """**22.9분 뒤가 아니라 여기서 멈춘다.** `260911_03` 이 그 값을 실제로 버렸다."""
    root, runs = _world(tmp_path, cut=False, source=True)
    runner = _stub_queue(monkeypatch)
    # 문이 열렸으면 여기를 지난다. 안 지나는 것이 이 검사의 본문이다.
    monkeypatch.setattr(runner.deck, "apkg_of", lambda *_a, **_k: pytest_fail())

    code = runner.run_watch_one(_watch_one_args(root, runs))
    out = capsys.readouterr().out
    assert code == 1                                  # 러너가 이 값으로 실패를 적는다
    assert "studyez jokbo 미생물학" in out             # 한 줄이면 풀린다는 것을 같이 준다
    assert "--no-jokbo" in out                        # 넘어갈 길도 같이 준다


def test_족보_원본이_없는_과목은_안_막는다(tmp_path, monkeypatch):
    """미생물학 실습 기출이 실제로 이 자리다. 막으면 그 편은 영영 안 만들어진다."""
    root, runs = _world(tmp_path, cut=False, source=False)
    runner = _stub_queue(monkeypatch)
    reached: list[str] = []
    monkeypatch.setattr(runner.deck, "apkg_of", lambda *_a, **_k: reached.append("갔다"))

    runner.run_watch_one(_watch_one_args(root, runs))
    assert reached == ["갔다"]                        # 족보 문에 안 걸렸다


def test_no_jokbo면_안_잘려_있어도_간다(tmp_path, monkeypatch):
    root, runs = _world(tmp_path, cut=False, source=True)
    runner = _stub_queue(monkeypatch)
    reached: list[str] = []
    monkeypatch.setattr(runner.deck, "apkg_of", lambda *_a, **_k: reached.append("갔다"))

    runner.run_watch_one(_watch_one_args(root, runs, no_jokbo=True))
    assert reached == ["갔다"]


def test_이미_잘려_있으면_안_막는다(tmp_path, monkeypatch):
    root, runs = _world(tmp_path, cut=True, source=True)
    runner = _stub_queue(monkeypatch)
    reached: list[str] = []
    monkeypatch.setattr(runner.deck, "apkg_of", lambda *_a, **_k: reached.append("갔다"))

    runner.run_watch_one(_watch_one_args(root, runs))
    assert reached == ["갔다"]


def pytest_fail():
    raise AssertionError("족보를 자르기 전에 덱을 만들면 안 된다")
