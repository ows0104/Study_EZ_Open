"""Frozen input download, authoring subprocess and idempotent publication."""
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from http.client import IncompleteRead
from urllib.error import HTTPError
from uuid import uuid4
import urllib.parse
import urllib.request
from studyez_contracts.roots.automation import packet_hash, validate_result
from .subprocesses import run_forwarded
from studyez_contracts.roots import document_hash
from studyez_contracts.roots.parallel import is_v2_source


def frozen_source(path, url, source):
    """Reuse only an exact immutable copy; transient fetch failures precede models."""
    if path.exists():
        body=path.read_bytes()
    else:
        for attempt in range(3):
            try:
                # Never forward the API's runner token to signed object storage.
                with urllib.request.urlopen(urllib.request.Request(url),timeout=120) as response:
                    body=response.read(source['sizeBytes']+1)
                break
            except (OSError,IncompleteRead) as error:
                if isinstance(error,HTTPError) and error.code!=429 and not 500<=error.code<600:raise
                if attempt==2:raise
                time.sleep(0.25*(2**attempt))
    if len(body)!=source['sizeBytes'] or hashlib.sha256(body).hexdigest()!=source['sha256']:
        raise ValueError('자동출제 원본 사본 지문 불일치 — 보관본을 덮어쓰지 않고 보류합니다.')
    if not path.exists():
        temporary=path.with_name(path.name+'.'+uuid4().hex+'.download')
        temporary.write_bytes(body)
        if path.exists() and path.read_bytes()!=body:raise ValueError('동시에 저장된 원본 사본이 다릅니다.')
        temporary.replace(path)
    return path

def completed_result(out,packet):
    """Reuse a completed revision after a code upgrade without resetting any calls."""
    payload=json.loads((out/'result.json').read_text(encoding='utf-8'))
    validate_result(payload,packet)
    ledger=json.loads((out/'ledger.json').read_text(encoding='utf-8'));meta=payload['manifest']
    if ledger.get('identity')!=meta['runtimeHash']or ledger.get('repairRounds')!=meta['repairRounds']:
        raise ValueError('완료 결과의 원래 실행 지문/상한이 다릅니다.')
    if meta.get('normalizationRecoveries',[])!=ledger.get('normalizationRecoveries',[]):raise ValueError('초기 지도 재검증 이력이 다릅니다.')
    if ledger.get('normalizationRecoveries'):
        if json.loads((out/'normalize.recovery.json').read_text(encoding='utf-8'))!=ledger['normalizationRecoveries'][0]:raise ValueError('초기 지도 재검증 증거가 다릅니다.')
    for stage in meta['stages']:
        name=stage['name'];entry=ledger.get('stages',{}).get(name)
        if entry!={k:v for k,v in stage.items()if k!='name'}:raise ValueError('완료 결과의 원래 단계 이력이 다릅니다.')
        if entry['status']=='blocked':
            if json.loads((out/(name+'.blocked.json')).read_text(encoding='utf-8'))!=entry['blockedReport']:raise ValueError('검수 보류 기록 불일치')
            continue
        value=json.loads((out/(name+'.json')).read_text(encoding='utf-8'))
        if document_hash(value)!=entry['outputHash']:raise ValueError('완료 단계 사본이 다릅니다.')
        usage=json.loads((out/(name+'.usage.json')).read_text(encoding='utf-8'))
        if 'usageHash'in entry and document_hash(usage)!=entry['usageHash']:raise ValueError('사용량 증거가 다릅니다.')
        if 'rawOutputHash'in entry:
            raw=json.loads((out/(name+'.raw.json')).read_text(encoding='utf-8'))
            if document_hash(raw)!=entry['rawOutputHash']:raise ValueError('원본 단계 응답이 다릅니다.')
    validate_continuations(out,payload)
    return payload

def validate_continuations(out,payload):
    for entry in payload['manifest']['stages']:
        if 'continuationProofHash'in entry:
            from .root_authoring_resume import validate_cached_continuation
            validate_cached_continuation(out,entry)
    from .root_native_json import validate_all
    validate_all(out,payload)


def map_tree_front(packet, out, *, model=None, resume=None, run=None):
    """map-tree/1: run the front stages (runner.root_front) and return the derived generation packet.

    The derived packet is re-derived here from the request and the front evidence, exactly as the server
    will, before any generation call uses it."""
    from studyez_contracts.roots import map_tree
    front, derived_path = out / 'front', out / 'front' / 'derived-packet.json'
    if not derived_path.exists():
        args = [sys.executable, '-m', 'runner.root_front', '--packet', str((out / 'packet.json').resolve()), '--out', str(front.resolve())]
        if model: args += ['--model', model]
        if resume: args += ['--resume', resume]
        result = (run or run_forwarded)(args, cwd=Path(__file__).resolve().parents[1])
        if result.returncode: return None
    derived = json.loads(derived_path.read_text(encoding='utf-8'))
    again = map_tree.derive_packet(packet, derived['conceptMap'], derived['points'], derived['frontStages'])
    if map_tree.public(again) != map_tree.public(derived): raise ValueError('앞 단계 결과로 만든 생성 입력이 요청과 맞지 않습니다.')
    gen = out / 'generation'; gen.mkdir(exist_ok=True)
    path = gen / 'packet.json'
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != again: raise ValueError('기존 생성 입력이 다릅니다. 이력을 보존합니다.')
    else:
        path.write_text(json.dumps(again, ensure_ascii=False, indent=2), encoding='utf-8')
    return again


def run_generation(client, subject, run_id, runs_dir, generation_id, *, model=None, resume=None):
    """resume: the administrator's reason to continue a failed/held request (stage-resume/1, root_front --resume)."""
    if not re.fullmatch(r'[a-f0-9]{32}', generation_id): raise ValueError('잘못된 생성 작업 ID')
    base = '/api/admin/root-generation/' + generation_id
    got = client.call('GET', base + '/input')
    if got.get('published'):
        print(f'Quiz Bank {run_id}: 뿌리 학습 게시 완료 (기존 결과)', flush=True)
        return 0
    packet = got['packet']
    if (packet['subject'], packet['runId'], packet['generationId']) != (subject, run_id, generation_id):
        raise ValueError('다른 강의의 자동출제 입력입니다.')
    if packet_hash(packet) != packet['inputHash']: raise ValueError('자동출제 입력 지문 불일치')
    if packet.get('authoring')=='web' and document_hash(packet.get('webResponse'))!=packet.get('webResponseHash'):
        raise ValueError('수신된 웹 원문 지문 불일치')
    out = Path(runs_dir) / '_root-generation' / generation_id
    out.mkdir(parents=True, exist_ok=True)
    for i, source in enumerate(packet['sources']):
        url = urllib.parse.urljoin(client.base + '/', source['downloadUrl'])
        if urllib.parse.urlparse(url).scheme not in ('http', 'https'): raise ValueError('잘못된 원본 주소')
        suffix = Path(source['filename']).suffix.lower()
        path = out / f'source-{i}{suffix}'
        frozen_source(path,url,source)
        del source['downloadUrl']
        source['localPath'] = str(path.resolve())
    packet_path = out / 'packet.json'
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding='utf-8')
    if packet.get('parallelAuthoring'):
        from .parallel_status import register
        project=Path(runs_dir).resolve().parent
        # The reader binds this exact -m token AND the observed child PID.
        register(project,out,project/'runner.root_native_json',out/'runner.log')
    # map-tree/1 runs the front stages first; the generator then works in <run>/generation on the derived packet.
    gen_out, gen_packet, gen_packet_path = out, packet, packet_path
    if packet.get('pipeline') is not None:
        gen_packet = map_tree_front(packet, out, model=model, resume=resume)
        if gen_packet is None: return 1
        gen_out = out / 'generation'; gen_packet_path = gen_out / 'packet.json'
    module='runner.root_native_json'if is_v2_source(gen_packet)else'quizbank.connection_generate'
    args = [sys.executable, '-m', module, '--packet', str(gen_packet_path.resolve()), '--out', str(gen_out.resolve())]
    if model: args += ['--model', model]
    if resume and module == 'runner.root_native_json' and (gen_out / 'ledger.json').exists(): args += ['--resume', resume]
    if (gen_out/'result.json').exists():payload=completed_result(gen_out,gen_packet)
    else:
        result = run_forwarded(args, cwd=Path(__file__).resolve().parents[1])
        if result.returncode: return result.returncode
        payload = completed_result(gen_out,gen_packet)if is_v2_source(gen_packet)else json.loads((gen_out / 'result.json').read_text(encoding='utf-8'))
    validate_result(payload, packet)  # map-tree/1: re-derives gen_packet from the request, as the server does
    validate_continuations(gen_out,payload)
    posted = client.call('PUT', base + '/result', payload)
    if posted.get('status') != 'ready': raise ValueError('게시 완료 응답을 받지 못했습니다.')
    (out / 'published.json').write_text(json.dumps(posted, ensure_ascii=False), encoding='utf-8')
    if packet.get('parallelAuthoring'):
        from .parallel_status import refresh
        refresh(out,'published')
    print(f'Quiz Bank {run_id}: Concept map·포인트 → 뿌리 학습 게시 완료', flush=True)
    # Quiz Bank와 같은 핵심 근거·족보 지면(2026-11-08). 실패해도 게시 결과는 그대로다.
    from .root_evidence import publish as publish_evidence
    publish_evidence(client, subject, run_id, gen_out, gen_packet, payload, model=model, run=run_forwarded)
    return 0
