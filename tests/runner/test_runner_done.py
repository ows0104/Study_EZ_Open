"""한 편이 끝난 뒤 러너가 내리는 판정.

여기도 사람이 안 본다. 그리고 여기서 갈리는 것이 **무엇을 실패로 볼 것인가**다 —
`explain_missing_run`이 돌려준 값이 그대로 `publish`의 종료 코드가 되고, 스케줄러는
그걸로 밤일이 잘 끝났는지 판단한다.

이 파일을 쓰다가 실제로 하나 잡았다. `374071a`(pdf2anki 이관 — 지금의 `quizgen/`)에서 `prep.json`의
키가 `source_pdf` → `source`로 바뀌었는데 `explain_missing_run`만 옛 이름을 계속
찾고 있었다. 그래서 **「작년 run이라 정상이다」 분기가 통째로 죽어** 있었고, 예습을
진도보다 앞서 만들어 둔 정상 상황이 매번 실패로 보고됐다. 아래 첫 세 개가 그 자리다.
"""

import json
from pathlib import Path

from runner import cycle, watch

PREV = "[250825_02] 종양의 병태생리(3) 종양의 분자생물학(2)(전윤경)_박지원v1.pdf"
THIS = "[260812_01] 병리학 소개(정경천)_정현영v2.pdf"


def _run_dir(tmp_path: Path, run_id: str, *, prep: dict | None = None,
             config: dict | None = None) -> Path:
    d = tmp_path / run_id
    d.mkdir(parents=True, exist_ok=True)
    if prep is not None:
        (d / "prep.json").write_text(json.dumps(prep, ensure_ascii=False), encoding="utf-8")
    if config is not None:
        (d / "run.config.json").write_text(json.dumps(config, ensure_ascii=False),
                                           encoding="utf-8")
    return d


# ------------------------------------------------- 무엇을 실패로 볼 것인가

def test_작년_필기로_돈_run은_정상이라_0이다(tmp_path):
    """예습을 진도보다 앞서 만들면 올해 필기가 아직 없다. 실패가 아니다."""
    _run_dir(tmp_path, "250825_02", prep={"source": PREV})
    assert cycle.explain_missing_run(tmp_path, "250825_02", "2025") == 0


def test_올해_run을_못_찾으면_1이다(tmp_path):
    _run_dir(tmp_path, "260812_01", prep={"source": THIS})
    assert cycle.explain_missing_run(tmp_path, "260812_01", "2025") == 1


def test_prep이_source_키를_쓴다(tmp_path):
    """`prep.py`가 쓰는 이름은 `source`다. 옛 이름(`source_pdf`)만 찾으면 못 읽는다."""
    _run_dir(tmp_path, "250825_02", prep={"source_pdf": PREV})   # 옛 이름만 있는 자리
    assert cycle.explain_missing_run(tmp_path, "250825_02", "2025") == 0
    _run_dir(tmp_path, "250826_01", prep={"source": PREV})       # 지금 이름
    assert cycle.explain_missing_run(tmp_path, "250826_01", "2025") == 0


def test_run_config가_있으면_그것도_읽는다(tmp_path):
    _run_dir(tmp_path, "250825_02", config={"pdf": f"C:/x/병리학/필기/2025/{PREV}"})
    assert cycle.explain_missing_run(tmp_path, "250825_02", "2025") == 0


def test_아무_기록도_없으면_죽지_않고_1이다(tmp_path):
    _run_dir(tmp_path, "260812_01")
    assert cycle.explain_missing_run(tmp_path, "260812_01", "2025") == 1


def test_prep이_깨져_있어도_죽지_않는다(tmp_path):
    d = _run_dir(tmp_path, "260812_01")
    (d / "prep.json").write_text("{ 깨진 json", encoding="utf-8")
    assert cycle.explain_missing_run(tmp_path, "260812_01", "2025") == 1


# ------------------------------------------------- 과목은 경로에서 읽는다

def test_필기_폴더_바로_위가_과목이다():
    assert cycle.subject_of(Path("C:/드라이브/병리학/필기/2026") / THIS) == "병리학"


def test_필기가_없는_경로면_모른다고_한다():
    assert cycle.subject_of(Path("C:/어딘가/그냥") / THIS) is None


def test_필기가_맨_앞이면_과목이_없다():
    assert cycle.subject_of(Path("필기/2026") / THIS) is None


# ------------------------------------------------- 표시는 올해 것에만 찍는다

def _stamped(monkeypatch) -> list:
    seen: list = []
    monkeypatch.setattr(watch, "stamp_run",
                        lambda runs_dir, run_id, pdf: seen.append((run_id, pdf)) or True)
    return seen


def test_올해_run은_표시한다(tmp_path, monkeypatch):
    seen = _stamped(monkeypatch)
    _run_dir(tmp_path, "260812_01", config={"pdf": f"C:/x/병리학/필기/2026/{THIS}"})
    assert cycle.stamp_source(tmp_path, "260812_01", "2026") == "병리학"
    assert [r for r, _ in seen] == ["260812_01"]


def test_작년_run에는_표시하지_않는다(tmp_path, monkeypatch):
    """표시는 올해 폴더를 다시 안 훑으려는 장치다. 작년에 찍으면 쓰이지 않는 파일만 남는다."""
    seen = _stamped(monkeypatch)
    _run_dir(tmp_path, "250825_02", config={"pdf": f"C:/x/병리학/필기/2025/{PREV}"})
    assert cycle.stamp_source(tmp_path, "250825_02", "2026") == "병리학"
    assert seen == []


def test_dry_run이면_표시하지_않는다(tmp_path, monkeypatch):
    seen = _stamped(monkeypatch)
    _run_dir(tmp_path, "260812_01", config={"pdf": f"C:/x/병리학/필기/2026/{THIS}"})
    cycle.stamp_source(tmp_path, "260812_01", "2026", dry_run=True)
    assert seen == []


def test_원본을_못_읽으면_건너뛴다(tmp_path, monkeypatch):
    seen = _stamped(monkeypatch)
    _run_dir(tmp_path, "260812_01")
    assert cycle.stamp_source(tmp_path, "260812_01", "2026") is None
    assert seen == []


# ------------------------------------------------- 토큰을 어디서 찾나

def test_인자가_가장_세다(tmp_path, monkeypatch):
    monkeypatch.setattr(cycle, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("STUDYEZ_RUNNER_TOKEN", "환경변수")
    assert cycle.runner_token("  인자  ") == "인자"


def test_인자가_없으면_환경변수다(tmp_path, monkeypatch):
    monkeypatch.setattr(cycle, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("STUDYEZ_RUNNER_TOKEN", "환경변수")
    assert cycle.runner_token(None) == "환경변수"


def test_마지막이_server_env다(tmp_path, monkeypatch):
    monkeypatch.setattr(cycle, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("STUDYEZ_RUNNER_TOKEN", raising=False)
    (tmp_path / "server").mkdir()
    (tmp_path / "server" / ".env").write_text(
        'ENVIRONMENT=production\nRUNNER_TOKEN="따옴표친값"\n', encoding="utf-8")
    assert cycle.runner_token(None) == "따옴표친값"


def test_아무_데도_없으면_빈_문자열이다(tmp_path, monkeypatch):
    monkeypatch.setattr(cycle, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("STUDYEZ_RUNNER_TOKEN", raising=False)
    assert cycle.runner_token(None) == ""


# ------------------------------------------------- 비용은 읽어 보여 주기만 한다

def test_보고서가_없거나_깨져도_죽지_않는다(tmp_path):
    cycle.report_cost(tmp_path)                       # 파일 자체가 없다
    (tmp_path / "run.report.json").write_text("{ 깨진", encoding="utf-8")
    cycle.report_cost(tmp_path)                       # 깨져 있다
    (tmp_path / "run.report.json").write_text("{}", encoding="utf-8")
    cycle.report_cost(tmp_path)                       # cumulative 가 없다


def test_누적이_있으면_찍는다(tmp_path, capsys):
    (tmp_path / "run.report.json").write_text(json.dumps(
        {"cumulative": {"cost_usd": 1.5, "seconds": 600, "sessions": 4,
                        "tokens_total": 123456}}), encoding="utf-8")
    cycle.report_cost(tmp_path)
    out = capsys.readouterr().out
    assert "$1.50" in out and "10.0분" in out and "123,456" in out
