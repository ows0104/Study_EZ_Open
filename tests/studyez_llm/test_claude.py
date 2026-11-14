"""Claude Code CLI 실행기(docs/changes/2026-11-14-root-claude-provider). 모델 호출 없이 명령·해석·분기만 본다."""

import json
import subprocess
from pathlib import Path

import pytest

from studyez_llm import claude, codex

MODEL = "claude-opus-5-5"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("STUDYEZ_CODEX_USAGE_DIR", str(tmp_path / "usage"))
    monkeypatch.setenv("STUDYEZ_CLAUDE_BIN", "claude-test-bin")


def stream(result=None, *, assistant_stop="end_turn", extra=()):
    rows = [{"type": "system", "subtype": "init", "session_id": "s-1"},
            {"type": "assistant", "message": {"stop_reason": assistant_stop, "content": []}},
            *extra]
    rows.append({"type": "result", "subtype": "success", "is_error": False, "result": '{"ok":true}',
                 "session_id": "s-1", "num_turns": 3, "total_cost_usd": 0.5, "stop_reason": "end_turn",
                 "usage": {"input_tokens": 100, "output_tokens": 7, "cache_read_input_tokens": 40,
                           "cache_creation_input_tokens": 5}, **(result or {})})
    return "\n".join(json.dumps(r) for r in rows)


def fake_process(stdout, calls, code=0):
    def run(argv, *, input, cwd, timeout, stdin=None, **kw):
        assert input is None and stdin is not None   # 첫 메시지는 파일로 넘긴다
        calls.append({"argv": argv, "input": stdin.read().decode("utf-8"), "cwd": cwd})
        return subprocess.CompletedProcess(argv, code, stdout, "")
    return run


def test_모델_이름으로_공급자를_고른다():
    assert codex.provider("gpt-6.1-sol") == "codex"
    assert codex.provider(MODEL) == "claude"
    assert codex.model_name(MODEL) == MODEL
    with pytest.raises(codex.SessionError):
        codex.model_name("opus")


def test_codex_run이_claude_모델을_넘긴다(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(claude, "run_process", fake_process(stream(), calls))
    monkeypatch.setattr(codex, "run_process", lambda *a, **k: pytest.fail("Codex CLI를 부르면 안 된다"))
    info = codex.run("task", blind=False, cwd=tmp_path, model=MODEL, schema={"type": "object"}, system="SYS")
    assert info["provider"] == "claude" and info["text"] == '{"ok":true}' and info["session_id"] == "s-1"
    assert info["models"] == {MODEL: 7} and info["turns"] == 3 and info["cost_usd"] == 0.5
    assert info["usage"] == {"input_tokens": 100, "output_tokens": 7, "cache_read_input_tokens": 40,
                             "cache_creation_input_tokens": 5}
    argv = calls[0]["argv"]
    assert argv[:2] == ["claude-test-bin", "-p"] and argv[argv.index("--model") + 1] == MODEL
    # 사용자 설정·MCP·스킬을 싣지 않고, 작업 도구만 연다.
    for flag in ("--safe-mode", "--strict-mcp-config", "--disable-slash-commands"):
        assert flag in argv
    assert argv[argv.index("--setting-sources") + 1] == ""
    assert argv[argv.index("--tools") + 1] == "Read,Write,Edit,Glob,Grep,Bash"
    assert argv[argv.index("--system-prompt") + 1] == "SYS"
    assert json.loads(argv[argv.index("--json-schema") + 1]) == {"type": "object"}
    assert Path(calls[0]["cwd"]) == tmp_path.resolve()
    message = json.loads(calls[0]["input"])
    assert message["message"]["content"] == [{"type": "text", "text": "task"}]


def test_가림_실행은_도구가_없다(monkeypatch):
    calls = []
    monkeypatch.setattr(claude, "run_process", fake_process(stream(), calls))
    codex.run("judge", blind=True, model=MODEL)
    argv = calls[0]["argv"]
    assert argv[argv.index("--tools") + 1] == "" and "--permission-mode" not in argv
    assert "--no-session-persistence" in argv


def test_구조화_출력을_응답으로_쓴다(monkeypatch, tmp_path):
    calls = []
    out = stream({"result": "", "structured_output": {"path": "result.json", "sha256": "0" * 64}})
    monkeypatch.setattr(claude, "run_process", fake_process(out, calls))
    info = codex.run("task", blind=False, cwd=tmp_path, model=MODEL)
    assert json.loads(info["text"]) == {"path": "result.json", "sha256": "0" * 64}


def test_긴_시스템_지시와_스키마는_첫_메시지에_싣는다(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(claude, "run_process", fake_process(stream({"result": "```json\n{\"a\":1}\n```"}), calls))
    big = {"type": "object", "description": "x" * (claude.ARG_LIMIT + 1)}
    info = codex.run("task", blind=False, cwd=tmp_path, model=MODEL, schema=big, system="S" * (claude.ARG_LIMIT + 1))
    argv = calls[0]["argv"]
    assert "--json-schema" not in argv and "--system-prompt" not in argv
    text = json.loads(calls[0]["input"])["message"]["content"][0]["text"]
    assert text.startswith("SYSTEM INSTRUCTIONS") and "\n\ntask\n\n" in text and big["description"] in text
    assert info["text"] == '{"a":1}'


def test_이미지는_붙이거나_경로로_알린다(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(claude, "run_process", fake_process(stream(), calls))
    pages = []
    for i in range(3):
        p = tmp_path / f"S1-000{i}.png"
        p.write_bytes(b"\x89PNG" + bytes([i]))
        pages.append(p)
    codex.run("look", blind=False, cwd=tmp_path, model=MODEL, images=pages)
    content = json.loads(calls[0]["input"])["message"]["content"]
    assert [c["type"] for c in content] == ["text", "image", "image", "image"]
    monkeypatch.setattr(claude, "INLINE_IMAGE_LIMIT", 2)
    codex.run("look again", blind=False, cwd=tmp_path, model=MODEL, images=pages)
    content = json.loads(calls[1]["input"])["message"]["content"]
    assert [c["type"] for c in content] == ["text"] and "NOT attached" in content[0]["text"]
    assert all(str(p.resolve()) in content[0]["text"] for p in pages)


def test_거절은_콘텐츠_제한_표식으로_올린다(monkeypatch, tmp_path):
    from runner import root_native_json as native
    monkeypatch.setattr(claude, "run_process", fake_process(stream(assistant_stop="refusal"), []))
    with pytest.raises(codex.SessionError) as caught:
        codex.run("task", blind=False, cwd=tmp_path, model=MODEL)
    assert claude.REFUSAL_MARKER in str(caught.value)
    kind = native.classify_error(caught.value)
    assert kind["kind"] == "model_content_restricted" and kind["automaticRetry"] is False and "Claude" in kind["message"]
    assert not codex.network_failure(caught.value)


def test_오류_결과와_중단은_실패다(monkeypatch, tmp_path):
    bad = stream({"is_error": True, "result": "Failed to authenticate"})
    monkeypatch.setattr(claude, "run_process", fake_process(bad, []))
    with pytest.raises(codex.SessionError, match="Failed to authenticate"):
        codex.run("task", blind=False, cwd=tmp_path, model=MODEL)
    monkeypatch.setattr(claude, "run_process", fake_process('{"type":"system"}', []))
    with pytest.raises(codex.SessionError, match="완료 이벤트가 없다"):
        codex.run("task", blind=False, cwd=tmp_path, model=MODEL)

    def timeout(argv, **kw):
        raise subprocess.TimeoutExpired(argv, 5)
    monkeypatch.setattr(claude, "run_process", timeout)
    with pytest.raises(codex.SessionError, match="초 안에 끝나지 않았다"):
        codex.run("task", blind=False, cwd=tmp_path, model=MODEL, timeout=5)


def test_재개는_같은_세션을_잇고_누적_사용량을_남긴다(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(claude, "run_process", fake_process(stream(), calls))
    first = codex.run("task", blind=False, cwd=tmp_path, model=MODEL)
    again = codex.run("fix", blind=False, cwd=tmp_path, model=MODEL, resume="s-1",
                      previous_usage=first["session_usage"])
    argv = calls[1]["argv"]
    assert argv[argv.index("--resume") + 1] == "s-1"
    assert again["usage"]["output_tokens"] == 7 and again["session_usage"]["output_tokens"] == 14
    with pytest.raises(codex.SessionError):
        codex.run("fix", blind=False, cwd=tmp_path, model=MODEL, resume="s-1")


def test_claude는_codex와_다른_자리를_쓴다(monkeypatch, tmp_path):
    seen = []
    real = codex.slot

    def spy(limit=None, **kw):
        seen.append((limit, kw.get("pool")))
        return real(limit, **kw)
    monkeypatch.setattr(codex, "slot", spy)
    monkeypatch.setattr(claude, "run_process", fake_process(stream(), []))
    monkeypatch.setenv("STUDYEZ_CLAUDE_SLOTS", "3")
    codex.run("task", blind=False, cwd=tmp_path, model=MODEL)
    assert seen == [(3, "claude")]


def test_요청하지_않은_모델이_답하면_받지_않는다(monkeypatch, tmp_path):
    usage = {MODEL: {"outputTokens": 0}, "claude-opus-5": {"outputTokens": 8000}}
    monkeypatch.setattr(claude, "run_process", fake_process(stream({"modelUsage": usage}), []))
    with pytest.raises(codex.SessionError) as caught:
        codex.run("task", blind=False, cwd=tmp_path, model=MODEL)
    assert claude.FALLBACK_MARKER in str(caught.value) and "claude-opus-5" in str(caught.value)
    same = {"claude-opus-5": {"outputTokens": 9}}
    monkeypatch.setattr(claude, "run_process", fake_process(stream({"modelUsage": same}), []))
    info = codex.run("task", blind=False, cwd=tmp_path, model="claude-opus-5")
    assert info["models"] == {"claude-opus-5": 9}


def test_첫_메시지는_파일로_넘기고_제한_시간은_배수를_곱한다(monkeypatch, tmp_path):
    seen = {}

    def run(argv, *, input, stdin, cwd, timeout, **kw):
        seen.update(input=input, body=stdin.read().decode("utf-8"), timeout=timeout)
        return subprocess.CompletedProcess(argv, 0, stream(), "")
    monkeypatch.setattr(claude, "run_process", run)
    codex.run("task", blind=False, cwd=tmp_path, model=MODEL, timeout=100)
    assert seen["input"] is None and json.loads(seen["body"])["message"]["content"][0]["text"] == "task"
    assert seen["timeout"] == 300
    monkeypatch.setenv("STUDYEZ_CLAUDE_TIMEOUT_FACTOR", "1")
    codex.run("task", blind=False, cwd=tmp_path, model=MODEL, timeout=100)
    assert seen["timeout"] == 100


def test_run_process는_파일_입력을_받는다(tmp_path):
    import sys
    from studyez_llm.execution import run_process
    src = tmp_path / "in.txt"
    src.write_text("hello", encoding="utf-8")
    with src.open("rb") as handle:
        done = run_process([sys.executable, "-c", "import sys;print(sys.stdin.read().upper())"], input=None,
                           stdin=handle, cwd=tmp_path, timeout=30)
    assert done.stdout.strip() == "HELLO"
