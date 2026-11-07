"""Adapter to the runner's existing per-task batch cards; never controls workers."""
import json
import os
from pathlib import Path
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)

STAGES={'queued':'대기','running':'CLI 실행 중','applied':'완료',
    'failed':'실패·기록 보존','integrating':'세 결과 통합 중','reviewing':'원본·독립 정답 검수 중',
    'repairing':'남은 상한 내 수정 중','local-ready':'격리 결과 준비·운영 미게시'}


def refresh(out,phase=None,error=None):
    path=Path(out)/'parallel-status.json'
    if not path.exists():return
    from studyez_contracts.roots.parallel import progress_state
    write(path,progress_state(read(path),phase,error,os.getpid()))


def register(project,out,script,log):
    """Register exact paths; the existing reader checks PID and command-line match."""
    project=Path(project).resolve();out=Path(out).resolve()
    def rel(p):return Path(p).resolve().relative_to(project).as_posix()
    config={'id':'main-quiz-parallel-'+out.name,'label':'Main Quiz 병렬 CLI','owner':'Codex 병렬 Main Quiz',
        'overview':True,'script':rel(script),'log':rel(log),'outputs':rel(out),
        'state_file':rel(out/'parallel-status.json'),'stages':STAGES}
    write(project/'runs/status-jobs'/('main-quiz-parallel-'+out.name+'.json'),config)
    return config
