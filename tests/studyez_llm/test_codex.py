"""CLI 경계 회귀 검사: 가림, 완료 판정, 구조화 출력, 재개, 사용량 중복 계산."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from quizbank import session as bank
from quizgen import session
from runner import agent
from studyez_llm import codex


def events(text='{"ok":true}', *, extra=()):
    return "\n".join(json.dumps(e) for e in [
        {"type": "thread.started", "thread_id": "test-session"},
        *extra,
        {"type": "item.completed", "item": {"type": "agent_message", "text": text}},
        {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 60,
                                              "output_tokens": 7}},
    ])


def test_usage_does_not_count_cached_tokens_twice():
    result = codex.parse_events(events(), model="gpt-6.1-sol", blind=True)
    assert result["usage"] == {"input_tokens": 40, "cache_read_input_tokens": 60,
                               "cache_creation_input_tokens": 0, "output_tokens": 7}
    assert result["models"] == {"gpt-6.1-sol": 7}
    assert result["session_id"] == "test-session"
    assert result["cost_usd"] is None


@pytest.mark.parametrize("extra", [
    {"type": "turn.failed", "error": {"message": "usage limit reached"}},
    {"type": "error", "message": "401 Unauthorized"},
    {"type": "item.started", "item": {"type": "command_execution"}},
    {"type": "item.completed", "item": {"type": "mcp_tool_call"}},
])
def test_failed_or_tool_using_blind_session_is_rejected(extra):
    with pytest.raises(codex.SessionError):
        codex.parse_events(events(extra=[extra]), model="gpt-6.1-sol", blind=True)


def test_startup_warning_is_preserved_without_hiding_completed_response():
    warning = {"type": "item.completed", "item": {"type": "error", "message": "tool disabled"}}
    result = codex.parse_events(events(extra=[warning]), model="gpt-6.1-sol", blind=True)
    assert result["warnings"] == ["tool disabled"]


def test_recovered_stream_retains_response_and_usage():
    warning = {"type": "error", "message": "Reconnecting... 2/5 (websocket closed)"}
    result = codex.parse_events(events(extra=[warning]), model="gpt-6.1-sol", blind=True)
    assert result["text"] == '{"ok":true}'
    assert result["usage"]["output_tokens"] == 7
    assert result["warnings"] == [warning["message"]]


@pytest.mark.parametrize("completed_before", [False, True])
def test_stream_reconnect_without_later_completion_fails(completed_before):
    warning = json.dumps({"type": "error", "message": "Reconnecting... 2/5 (websocket closed)"})
    stdout = (events() + "\n" if completed_before else "") + warning
    with pytest.raises(codex.SessionError, match="Reconnecting"):
        codex.parse_events(stdout, model="gpt-6.1-sol", blind=False)


@pytest.mark.parametrize("stdout", ["not json", "[]", '{"type":"turn.started"}', events("")])
def test_truncated_or_empty_output_fails(stdout):
    with pytest.raises(codex.SessionError):
        codex.parse_events(stdout, model="gpt-6.1-sol", blind=False)


def test_blind_cli_is_isolated(monkeypatch):
    monkeypatch.setenv("STUDYEZ_CODEX_BIN", "codex.exe")
    monkeypatch.delenv("STUDYEZ_MODEL", raising=False)
    def fake(argv, **kw):
        assert argv[:3] == ["codex.exe", "exec", "--json"]
        assert "--ephemeral" in argv
        assert "--ignore-user-config" in argv and "--ignore-rules" in argv
        assert "read-only" in argv and "features.shell_tool=false" in argv
        assert "features.unified_exec=false" in argv and "features.view_image=false" in argv
        assert 'web_search="disabled"' in argv and "project_doc_max_bytes=0" in argv
        assert kw["cwd"] != Path.cwd() and not list(kw["cwd"].iterdir())
        assert argv[-1] == "-" and kw["input"] == "question only"
        return SimpleNamespace(returncode=0, stdout=events(), stderr="")
    monkeypatch.setattr(codex.subprocess, "run", fake)
    data, info = session.run_blind("question only")
    assert data == {"ok": True} and info["session_id"] == "test-session"


def test_author_resume_retains_workspace_and_pdf_adapter(monkeypatch, tmp_path):
    monkeypatch.setenv("STUDYEZ_CODEX_BIN", "codex.exe")
    def fake(argv, **kw):
        assert argv[argv.index("resume") + 1] == "previous-session"
        assert "--ephemeral" not in argv and "workspace-write" in argv
        assert "features.shell_tool=true" in argv and "features.view_image=true" in argv
        if codex.os.name == "nt":
            assert 'windows.sandbox="elevated"' in argv
        assert kw["cwd"] == tmp_path.resolve()
        assert "view_image" in kw["input"] and "pdf.py" in kw["input"]
        return SimpleNamespace(returncode=0, stdout=events("written"), stderr="")
    monkeypatch.setattr(codex.subprocess, "run", fake)
    assert session.run_agent("write", cwd=tmp_path, resume="previous-session",
                             previous_usage={})["text"] == "written"


SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}},
          "required": ["ok"], "additionalProperties": False}


def test_bank_passes_schema_file_and_verifies_output(monkeypatch):
    monkeypatch.setenv("STUDYEZ_CODEX_BIN", "codex.exe")
    def fake(argv, **kw):
        path = Path(argv[argv.index("--output-schema") + 1])
        assert json.loads(path.read_text()) == SCHEMA
        assert (path.parent / "instructions.md").read_text() == "system instruction"
        return SimpleNamespace(returncode=0, stdout=events(), stderr="")
    monkeypatch.setattr(codex.subprocess, "run", fake)
    data, info = bank.run_structured("question", SCHEMA, system="system instruction", label="bank")
    assert data == {"ok": True} and info["input_tokens"] == 100


def test_bank_rejects_malformed_structured_output(monkeypatch):
    result = codex.parse_events(events('{"ok":"wrong type"}'), model="gpt-6.1-sol", blind=True)
    result["duration_ms"] = 100
    monkeypatch.setattr(codex, "run", lambda *a, **k: result)
    with pytest.raises(bank.SessionError, match="스키마"):
        bank.run_structured("q", SCHEMA, system="s", label="bank")


def test_model_override_and_old_claude_model_rejected(monkeypatch):
    monkeypatch.setenv("STUDYEZ_MODEL", "gpt-6-luna")
    assert codex.model_name() == "gpt-6-luna"
    assert codex.model_name("gpt-6-astra") == "gpt-6-astra"
    with pytest.raises(codex.SessionError, match="GPT"):
        codex.model_name("sonnet")


def test_process_failure_and_timeout_are_session_errors(monkeypatch):
    monkeypatch.setenv("STUDYEZ_CODEX_BIN", "codex.exe")
    monkeypatch.setattr(codex.subprocess, "run", lambda *a, **k:
                        SimpleNamespace(returncode=1, stdout="", stderr="401 Unauthorized"))
    with pytest.raises(codex.SessionError, match="401"):
        session.run_blind("q")
    def timeout(*a, **k):
        raise subprocess.TimeoutExpired("codex", 1)
    monkeypatch.setattr(codex.subprocess, "run", timeout)
    with pytest.raises(codex.SessionError, match="1초"):
        session.run_blind("q", timeout=1)


@pytest.mark.parametrize("message", ["You've hit your usage limit. Try again later.",
                                     "Rate limit reached for gpt-6.1-sol", "insufficient_quota"])
def test_codex_limits_enter_existing_runner_wait_path(message):
    assert agent.limit_reason(["멈췄다 — " + message]).startswith("세션 한도에 걸렸다")


@pytest.mark.parametrize("message", ["Not logged in", "401 Unauthorized", "refresh_token_reused"])
def test_codex_auth_failure_and_old_log_are_distinguished(message):
    assert "codex login" in agent.auth_reason(["멈췄다 — " + message])
    assert agent.auth_reason([message + "\n멈췄다 — JSON validation failed"]) == ""


def test_resumed_usage_counts_only_the_new_stage(monkeypatch, tmp_path):
    monkeypatch.setenv("STUDYEZ_CODEX_BIN", "codex.exe")
    monkeypatch.setattr(codex.subprocess, "run", lambda *a, **k:
                        SimpleNamespace(returncode=0, stdout=events(), stderr=""))
    old = {"input_tokens": 25, "output_tokens": 3, "cache_read_input_tokens": 50,
           "cache_creation_input_tokens": 0}
    result = session.run_agent("continue", cwd=tmp_path, resume="previous", previous_usage=old)
    assert result["usage"] == {"input_tokens": 15, "output_tokens": 4,
                               "cache_read_input_tokens": 10, "cache_creation_input_tokens": 0}
    assert result["session_usage"]["output_tokens"] == 7
    assert sum(result["models"].values()) == 4


@pytest.mark.parametrize('stdout,stderr', [(None, 'process terminated'), ('process terminated', None), (None, None)])
def test_process_failure_without_captured_streams(monkeypatch, tmp_path, stdout, stderr):
    monkeypatch.setenv('STUDYEZ_CODEX_BIN', 'codex.exe')
    monkeypatch.setattr(codex.subprocess, 'run', lambda *a, **k:
                        SimpleNamespace(returncode=3221225773, stdout=stdout, stderr=stderr))
    with pytest.raises(codex.SessionError, match='3221225773'):
        codex.run('inspect', blind=False, cwd=tmp_path)


def test_resumed_usage_requires_a_baseline(tmp_path):
    with pytest.raises(codex.SessionError, match="session_usage"):
        session.run_agent("continue", cwd=tmp_path, resume="previous")


@pytest.mark.skipif(codex.os.name != "nt", reason="Windows desktop installation")
def test_scheduled_runner_finds_desktop_cli_without_path(monkeypatch, tmp_path):
    monkeypatch.delenv("STUDYEZ_CODEX_BIN", raising=False)
    monkeypatch.setattr(codex.shutil, "which", lambda name: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    installed = tmp_path / "OpenAI" / "Codex" / "bin" / "build" / "codex.exe"
    installed.parent.mkdir(parents=True)
    installed.touch()
    assert codex.executable() == str(installed)
