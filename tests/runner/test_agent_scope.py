"""시간표가 없을 때 전체 과목으로 넓히던 회귀와 범위 밖 일감의 재개를 막는다."""

import json
import sqlite3
from datetime import date

import pytest

from runner import agent, ahead, watch


@pytest.fixture
def scoped_agent(tmp_path, monkeypatch):
    class Today(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 14)

    monkeypatch.setattr(agent, "Date", Today)
    root = tmp_path / "drive"
    for subject in ("약리학", "기초신경과학"):
        (root / subject / "필기" / "2026").mkdir(parents=True)
    monkeypatch.setattr(watch, "DEFAULT_ROOT", root)
    runs = tmp_path / "runs"
    pairs = runs / ahead.PAIRS_DIR
    pairs.mkdir(parents=True)
    for subject, block in (("약리학", "약물의 이해"), ("기초신경과학", "기초신경과학")):
        (pairs / f"{subject}.json").write_text(
            json.dumps({ahead.BLOCK_KEY: block}), encoding="utf-8")
    table = tmp_path / "timetable.json"
    table.write_text(json.dumps([
        {"date": day, "startTime": "09:00", "title": "약물의 이해", "category": "lecture"}
        for day in ("2026-10-13", "2026-10-14")
    ]), encoding="utf-8")
    worker = agent.Agent(None, runs, tmp_path, timetable=table, announce=lambda *_: None)
    return worker


def test_current_block_publishes_only_pharmacology(scoped_agent):
    commands = []
    scoped_agent._run = lambda argv, log: (commands.append(argv) or 0, [])
    scoped_agent.sweep()
    assert len(commands) == 1
    assert commands[0][3:5] == ["publish", "약리학"]
    assert "--all" not in commands[0]
    assert commands[0][commands[0].index("--timetable") + 1] == str(scoped_agent.timetable)
    assert commands[0][commands[0].index("--runs") + 1] == str(scoped_agent.runs_dir)


@pytest.mark.parametrize("cause", [FileNotFoundError("missing"), ValueError("bad table"),
                                    sqlite3.OperationalError("bad database")])
def test_unreadable_timetable_never_publishes_or_claims(scoped_agent, monkeypatch, cause):
    def fail(*args):
        raise cause

    monkeypatch.setattr(ahead, "subjects_in_block", fail)
    scoped_agent.subject = "약리학"  # 지정 과목도 시간표 확인 실패를 우회하지 않는다.
    scoped_agent._run = lambda *args: pytest.fail("must not publish")
    scoped_agent.claim = lambda *args: pytest.fail("must not claim")
    scoped_agent.sweep()
    assert scoped_agent.tick() is False
    assert "파일 처리를 중단" in scoped_agent.sweep_subjects()[1]


@pytest.mark.parametrize("note", ["블럭을 못 찾았다", "이번 블럭 → 과목 없다"])
def test_empty_scope_never_means_all(scoped_agent, monkeypatch, note):
    monkeypatch.setattr(ahead, "subjects_in_block", lambda *args: ([], note))
    scoped_agent._run = lambda *args: pytest.fail("must not publish")
    scoped_agent.claim = lambda *args: pytest.fail("must not claim")
    scoped_agent.sweep()
    assert scoped_agent.tick() is False


def test_startup_stops_before_claiming_when_timetable_is_missing(scoped_agent):
    scoped_agent.timetable = scoped_agent.repo_root / "missing.db"
    scoped_agent.claim = lambda *args: pytest.fail("must not start workers")
    assert scoped_agent.loop(poll=0) == 2
    assert not scoped_agent.lock_path().exists()


def test_explicit_subject_cannot_escape_current_block(scoped_agent):
    scoped_agent.subject = "기초신경과학"
    subjects, note = scoped_agent.sweep_subjects()
    assert subjects == []
    assert "파일 처리를 중단" in note


def test_resumed_neuroscience_job_is_held_without_processing(scoped_agent):
    updates = []
    scoped_agent.claim = lambda slot: agent.Job(12, "기초신경과학", "260604_07", kind=agent.BANK)
    scoped_agent.report = lambda job, **fields: updates.append(fields)
    scoped_agent.handle = lambda job: pytest.fail("must not download or build")
    assert scoped_agent.tick("w2") is False
    assert updates[0]["state"] == "held"
    assert "약리학" in updates[0]["message"]
    assert scoped_agent.building == {}


def test_current_block_job_is_processed(scoped_agent):
    handled = []
    job = agent.Job(13, "약리학", "261014_01", kind=agent.BANK)
    scoped_agent.claim = lambda slot: job
    scoped_agent.handle = handled.append
    assert scoped_agent.tick() is True
    assert handled == [job]
    assert scoped_agent.building == {}


def test_claimed_explicit_root_runs_outside_block_with_exact_generation(scoped_agent):
    class Client:
        def call(self,*args):
            return {'job':{'id':524,'subject':'기초신경과학','runId':'260604_07',
                'kind':agent.BANK,'rootGenerationId':'a'*32}}
    scoped_agent.client=Client()
    handled=[];scoped_agent.handle=handled.append
    assert scoped_agent.tick()
    job=handled[0]
    assert job.explicit_root and job.what=='뿌리 학습'
    argv=scoped_agent.make_argv(job)
    assert argv[argv.index('--root-generation')+1]=='a'*32
    assert argv[argv.index('--run-id')+1]=='260604_07'
    assert scoped_agent.building=={}


@pytest.mark.parametrize('kind,ident',[(agent.BANK,''),(agent.BANK,'not-an-id'),(agent.BANK_POINTS,'a'*32),(agent.deck.PRE,'a'*32)])
def test_unbound_or_nonroot_job_cannot_expand_block(scoped_agent,kind,ident):
    updates=[]
    scoped_agent.claim=lambda slot:agent.Job(524,'기초신경과학','260604_07',kind=kind,root_generation_id=ident)
    scoped_agent.report=lambda job,**fields:updates.append(fields)
    scoped_agent.handle=lambda job:pytest.fail('must not process')
    assert not scoped_agent.tick()
    assert updates[0]['state']=='held'


@pytest.mark.parametrize('choice',['held','canceled'])
def test_explicit_root_preserves_desktop_stop(scoped_agent,monkeypatch,choice):
    monkeypatch.setattr(agent.desktop_control,'decision',lambda *args:choice if len(args)>1 else '')
    job=agent.Job(524,'기초신경과학','260604_07',kind=agent.BANK,root_generation_id='a'*32)
    scoped_agent.claim=lambda slot:job
    updates=[];scoped_agent.report=lambda job,**fields:updates.append(fields)
    scoped_agent.handle=lambda job:pytest.fail('stopped root must not process')
    assert not scoped_agent.tick()
    assert updates[0]['state']==choice


def test_root_cli_uses_bound_request_without_latest_bank_lookup(tmp_path,monkeypatch):
    from runner.cli import main as cli
    from runner import connection_generation
    calls=[]
    monkeypatch.setattr(cli.cycle,'runner_token',lambda *_:'synthetic-token')
    monkeypatch.setattr(connection_generation,'run_generation',lambda *args,**kwargs:calls.append((args,kwargs)) or 0)
    monkeypatch.setattr(cli.bank,'run',lambda *args,**kwargs:pytest.fail('must not select latest bank'))
    assert cli.main(['bank','약리학','--run-id','demo','--runs',str(tmp_path),'--root-generation','a'*32])==0
    assert calls[0][0][1:]==('약리학','demo',tmp_path,'a'*32)
