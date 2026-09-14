"""실행마다 어느 모델이 냈는지 적어 둔다.

2026-08-26에 `260821_03` 을 8-23과 **같은 커밋·같은 자료**로 다시 돌렸더니 카드가
78장에서 23장이 됐다. 코드가 아니라는 것(같은 커밋), 입력이 아니라는 것
(`context.1of2.md` 가 26841바이트로 동일)까지는 실험으로 좁혔는데, 남은 변수인
모델을 어디에도 안 적어 둬서 거기서 멈췄다.

값이 흔들렸을 때 무엇이 흔들렸는지 물을 수 있어야 한다. 봉투(`claude -p
--output-format json`)의 `modelUsage` 가 이미 들고 있었고, 세느라 세션을 더 띄우지
않는다 — 그냥 안 적고 있었을 뿐이다.
"""

import json

from quizgen import ledger

ENV = {
    "modelUsage": {
        "claude-opus-5": {"outputTokens": 45318, "inputTokens": 42},
        "claude-haiku-4-5-20251001": {"outputTokens": 318, "inputTokens": 918},
    }
}


def test_봉투에서_모델별_출력량을_꺼낸다():
    assert ledger.models_of(ENV) == {"claude-opus-5": 45318,
                                     "claude-haiku-4-5-20251001": 318}


def test_봉투가_없거나_이상해도_견딘다():
    for bad in (None, {}, {"modelUsage": None}, {"modelUsage": []},
                {"modelUsage": {"x": "이상한 값"}}):
        assert ledger.models_of(bad) == {}


def test_단계마다_적히고_합쳐진다(tmp_path):
    ledger.append(tmp_path, "① 학습목표", seconds=354, cost=1.5,
                  usage={"output_tokens": 45318}, models=ledger.models_of(ENV))
    ledger.append(tmp_path, "② 카드", seconds=691, cost=2.4,
                  usage={"output_tokens": 56439}, models={"claude-opus-5": 56439})

    rows = ledger.read(tmp_path)
    assert rows[0]["models"] == {"claude-opus-5": 45318,
                                 "claude-haiku-4-5-20251001": 318}
    # 출력이 많은 쪽이 앞에 온다 — 주 모델이 무엇이었는지가 먼저 보여야 한다
    assert list(ledger.models_used(rows)) == ["claude-opus-5",
                                              "claude-haiku-4-5-20251001"]
    assert ledger.models_used(rows)["claude-opus-5"] == 45318 + 56439


def test_모델을_안_주면_줄에_넣지_않는다(tmp_path):
    """옛 실행의 usage.jsonl 과 섞여도 읽히게 둔다."""
    ledger.append(tmp_path, "덱 빌드", seconds=2, cost=None, sessions=0)
    assert "models" not in ledger.read(tmp_path)[0]
    assert ledger.models_used(ledger.read(tmp_path)) == {}


def test_보고서에_실린다(tmp_path):
    ledger.append(tmp_path, "① 학습목표", seconds=10, cost=1.0,
                  usage={"output_tokens": 5}, models=ledger.models_of(ENV))
    rep = ledger.summarize(tmp_path)
    assert rep["models"]["claude-opus-5"] == 45318
    assert rep["models_cumulative"]["claude-opus-5"] == 45318
    # 사람이 보는 표에도 뜬다
    assert "claude-opus-5" in ledger.table(ledger.read(tmp_path))


def test_옛_보고서를_읽어도_터지지_않는다(tmp_path):
    (tmp_path / ledger.LOG).write_text(
        json.dumps({"run": "r1", "step": "② 카드", "seconds": 1, "cost_usd": 0,
                    "sessions": 1, "output_tokens": 3}) + "\n", encoding="utf-8")
    assert ledger.summarize(tmp_path)["models"] == {}
    assert ledger.table(ledger.read(tmp_path))
