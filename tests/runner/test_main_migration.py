from runner import deck
from quizgen import run


def test_old_main_entry_points_do_not_generate(tmp_path, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("기존 Main 생성기를 실행하면 안 된다")

    monkeypatch.setattr(deck, "_spawn", unexpected)
    monkeypatch.setattr(run, "_legacy_main", unexpected)
    result = deck.run_main(pdf="notes.pdf", run_id="261002_02", subject="약리학", lecture="강의",
                           runs_dir=tmp_path, repo_root=tmp_path)
    assert not result.ok and "Quizbank" in result.error
    assert run.main(["notes.pdf"]) == 2
    assert not list(tmp_path.iterdir())
