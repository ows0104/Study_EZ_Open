"""`--resume` 이 폴더가 기억한 경로를 되살리는가.

2026-09-07 에 이게 없어 세 번 걸렸다 — 이어 돌린 편이 기본값 `out/jokbo` 를 보고
「기출 조각을 못 찾았다」로 빌드가 거부되고(두 번), 한 번은 덱 파일이 규칙 밖
이름(`p260902_01.apkg`)으로 구워져 나갔다. `studyez watch` 가 늘 같이 넘겨 주던
값이라 손으로 `--resume` 할 때만 드러난다.
"""

import json

from pdf2anki import run as R


def write_cfg(d, **extra):
    (d / R.CONFIG).write_text(json.dumps({
        "deck": "기생충학::[260902_01] 주혈흡충증(여선주)",
        "id": "p260902_01",
        "pdf": "", "pdf_name": "[260902_01]주혈흡충증(여선주)_박재민v1.pdf",
        "subject": "기생충학", "lecture": "[260902_01] 주혈흡충증(여선주)",
        "strategy": "base", "domain": "medical_ko",
        **extra}, ensure_ascii=False), encoding="utf-8")


def test_기억한_족보폴더와_덱이름이_되살아난다(tmp_path, monkeypatch):
    d = tmp_path / "260902_01"
    d.mkdir()
    write_cfg(d, jokbo_dir="runs/_jokbo/기생충학",
              apkg_name="[260902_01] 주혈흡충증(여선주)",
              jokbo="", check_dir="runs/_image_check")

    seen = {}

    class Stub(R.Runner):
        def all(self):
            seen.update(vars(self.args))

    monkeypatch.setattr(R, "Runner", Stub)
    R.main(["--resume", str(d)])

    assert seen["jokbo_dir"] == "runs/_jokbo/기생충학"
    assert seen["apkg_name"] == "[260902_01] 주혈흡충증(여선주)"
    assert seen["check_dir"] == "runs/_image_check"


def test_명령줄이_기억을_이긴다(tmp_path, monkeypatch):
    d = tmp_path / "260902_01"
    d.mkdir()
    write_cfg(d, jokbo_dir="runs/_jokbo/기생충학")

    seen = {}

    class Stub(R.Runner):
        def all(self):
            seen.update(vars(self.args))

    monkeypatch.setattr(R, "Runner", Stub)
    R.main(["--resume", str(d), "--jokbo-dir", "다른곳"])
    assert seen["jokbo_dir"] == "다른곳"


def test_기억에_없으면_기본값으로_간다(tmp_path, monkeypatch):
    """2026-09-07 이전에 만든 폴더는 이 키를 안 들고 있다. 죽지 않고 기본으로 간다."""
    d = tmp_path / "260902_01"
    d.mkdir()
    write_cfg(d)                       # jokbo_dir 없음

    seen = {}

    class Stub(R.Runner):
        def all(self):
            seen.update(vars(self.args))

    monkeypatch.setattr(R, "Runner", Stub)
    R.main(["--resume", str(d)])
    assert seen["jokbo_dir"] == R.DEFAULT_JOKBO_DIR
    assert seen["check_dir"] == R.DEFAULT_CHECK_DIR
    assert seen["apkg_name"] is None


def test_save_config_가_그_넷을_적는다():
    """적히지 않으면 되살릴 것도 없다 — 오늘 걸린 자리가 여기였다."""
    assert set(R.RESTORED) == {"jokbo_dir", "jokbo", "apkg_name", "check_dir"}
    import inspect
    body = inspect.getsource(R.Runner.save_config)
    assert "RESTORED" in body
