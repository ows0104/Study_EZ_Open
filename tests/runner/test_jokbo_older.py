"""`runner jokbo <과목>` 은 올해 판에 옛 판(2020판)을 덧붙여 자른다.

2026-10-05 관리자 — *"족보를 2026, 2020년꺼를 써서, 2026-2015까지를 커버할 수 있도록
하자."* 2026판이 2020~2025 시험을, 2020판이 2015~2019 시험을 싣는다.

병리학·기생충학의 2020 폴더에는 본문과 `_실습` 이 따로 있다. 실습 족보는 실습 조각을
따로 세우는 길(`--practical`)이 있어서 여기로 들어오면 필기 섹션에 섞인다.
"""

from pathlib import Path

from runner import __main__ as cli
from runner import deck


def _pdf(path: Path, size: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF" + b"0" * size)
    return path


def test_해마다_과목_족보_하나를_고르고_실습과_표지는_뺀다(tmp_path):
    folder = tmp_path / "병리학" / "족보" / "2020"
    body = _pdf(folder / "2020 질병의 병리학적 이해 본문.pdf", 100)
    _pdf(folder / "2020 질병의 병리학적 이해_실습.pdf", 500)
    _pdf(folder / "2020 표지.pdf", 900)
    assert cli.older_pdfs(tmp_path, "병리학", "2020") == [body]


def test_옛_판_폴더가_없으면_말하고_건너뛴다(tmp_path, capsys):
    assert cli.older_pdfs(tmp_path, "약리학", "2020") == []
    assert "2020판 없이 자른다" in capsys.readouterr().out


def test_빈_값이면_옛_판을_안_붙인다(tmp_path):
    _pdf(tmp_path / "병리학" / "족보" / "2020" / "a.pdf", 10)
    assert cli.older_pdfs(tmp_path, "병리학", "") == []


def test_자르는_쪽에_older_로_넘긴다(tmp_path, monkeypatch):
    seen = {}

    class Done:
        returncode = 0

    def fake_run(argv, **_):
        seen["argv"] = argv
        return Done()

    monkeypatch.setattr(deck.subprocess, "run", fake_run)
    old = tmp_path / "2020.pdf"
    deck.cut_jokbo(tmp_path / "2026.pdf", tmp_path / "out", tmp_path, older=[old])
    argv = seen["argv"]
    assert argv[argv.index("--older") + 1] == str(old)
