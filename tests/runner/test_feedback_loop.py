"""Feedback deduplication, stale approvals and read-only production collection."""

import copy
import json
from unittest.mock import patch

import pytest

from runner.feedback import main, reconcile, record


def item(message="버튼이 안 눌려요", kind="site"):
    return {"id": "site:1", "kind": kind, "message": message}


def decision(ledger, state, **extra):
    return {"id": "site:1", "fingerprint": ledger["items"]["site:1"]["fingerprint"],
            "state": state, "note": "검토함", **extra}


def test_unchanged_pull_preserves_pending_approval_and_history():
    ledger = reconcile({}, [item()])
    record(ledger, decision(ledger, "awaiting_approval", proposal={"change": "버튼 개선"}))
    expected = copy.deepcopy(ledger["items"])
    reconcile(ledger, [item()])
    assert ledger["items"] == expected


def test_changed_or_reopened_source_revokes_approval_but_keeps_history():
    ledger = reconcile({}, [item()])
    record(ledger, decision(ledger, "awaiting_approval", proposal={"change": "버튼 개선"}))
    record(ledger, decision(ledger, "approved", approval="사용자: 1번 적용해"))
    stale = decision(ledger, "resolved", evidence="확인함", validation="통과")
    reconcile(ledger, [item("모바일에서만 버튼이 안 눌려요")])
    entry = ledger["items"]["site:1"]
    assert entry["state"] == "pending" and entry["decision"] is None
    assert entry["history"][-1]["decision"]["approval"]
    with pytest.raises(ValueError, match="changed"):
        record(ledger, stale)
    reconcile(ledger, [])
    assert entry["sourceClosed"]
    reconcile(ledger, [item("모바일에서만 버튼이 안 눌려요")])
    assert not entry["sourceClosed"] and entry["state"] == "pending"


def test_site_resolution_requires_approved_exact_proposal_and_validation():
    ledger = reconcile({}, [item()])
    with pytest.raises(ValueError, match="explicit user approval"):
        record(ledger, decision(ledger, "resolved", evidence="확인", validation="통과"))
    record(ledger, decision(ledger, "awaiting_approval", proposal={"change": "버튼 개선"}))
    with pytest.raises(ValueError, match="Changed proposals"):
        record(ledger, decision(ledger, "approved", approval="동의", proposal={"change": "화면 전체 변경"}))
    record(ledger, decision(ledger, "approved", approval="사용자: 이 제안 적용해"))
    with pytest.raises(ValueError, match="validation"):
        record(ledger, decision(ledger, "resolved", evidence="원인 확인"))
    record(ledger, decision(ledger, "resolved", evidence="원인 확인", validation="실제 화면에서 확인"))
    assert ledger["items"]["site:1"]["decision"]["approval"] == "사용자: 이 제안 적용해"


def test_question_correction_needs_evidence_but_no_site_approval():
    ledger = reconcile({}, [item(kind="question")])
    record(ledger, decision(ledger, "resolved", evidence="원문 4쪽 대조", validation="수정 후 재조회"))
    assert ledger["items"]["site:1"]["state"] == "resolved"


def test_failed_pull_keeps_last_good_ledger_and_does_not_leak_exception(tmp_path, capsys):
    path = tmp_path / "ledger.json"
    before = json.dumps(reconcile({}, [item()]), ensure_ascii=False)
    path.write_text(before, encoding="utf-8")
    with patch("runner.feedback.collect", side_effect=RuntimeError("postgres://secret-password")):
        assert main(["pull", "--home", str(tmp_path)]) == 1
    assert path.read_text(encoding="utf-8") == before
    assert "secret-password" not in capsys.readouterr().err
    assert not (tmp_path / ".lock").exists()


def test_duplicate_ids_fail_before_modifying_ledger():
    ledger = reconcile({}, [item()])
    before = copy.deepcopy(ledger)
    with pytest.raises(ValueError, match="Duplicate"):
        reconcile(ledger, [item(), item()])
    assert ledger == before


def test_priority_metadata_preserves_review_but_changed_correction_requires_review():
    source = item(kind="question")
    ledger = reconcile({}, [source])
    record(ledger, decision(ledger, "deferred"))
    revision = ledger["items"]["site:1"]["fingerprint"]
    reconcile(ledger, [{**source, "highlighted": False, "correction": None}])
    assert ledger["items"]["site:1"]["state"] == "deferred"
    assert ledger["items"]["site:1"]["fingerprint"] == revision
    correction = {"original": {"answer": "원문"}, "proposed": {"answer": "수정"}}
    reconcile(ledger, [{**source, "highlighted": False, "correction": correction}])
    assert ledger["items"]["site:1"]["state"] == "pending"
    assert ledger["items"]["site:1"]["history"][-1]["decision"]["state"] == "deferred"
