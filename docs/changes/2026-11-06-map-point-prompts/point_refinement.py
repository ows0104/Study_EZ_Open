"""Authorized source-only point refinement and separate source audit; no publishing."""
import argparse
import importlib.util
import json
import shutil
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('base_pilot', HERE / 'pilot_extract.py')
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
ROOT, ASSETS = pilot.ROOT, pilot.ASSETS
ORIGINAL = pilot.OUT
OUT = ORIGINAL.with_name(ORIGINAL.name + '-point-granularity')


def read(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p, v): pilot.write(p, v)
def hashes(work): return {p.relative_to(work).as_posix(): pilot.sha(p) for p in work.rglob('*') if p.is_file()}


def extraction_evidence(work):
    state = read(work / 'state.json')
    if state['status'] == 'completed': return state
    assert state['status'] == 'failed' and state['error'] == "string indices must be integers, not 'str'"
    post = read(work / 'extraction-postcheck.json')
    assert post['status'] == 'completed' and post['originalFailurePreserved'] and post['additionalModelCalls'] == 0
    return post


def verify_extraction():
    work = OUT / 'point'; state = read(work / 'state.json')
    assert state['status'] == 'failed' and state['error'] == "string indices must be integers, not 'str'"
    assert not (work / 'extraction-postcheck.json').exists()
    frozen = read(work / 'input-hashes.json'); assert frozen == state['inputHashes']
    for rel, h in frozen.items(): assert pilot.sha(work / rel) == h
    for rel, h in read(OUT / 'material-hashes.json').items(): assert pilot.sha(work / 'material' / rel) == h
    info = read(work / 'model-response.json'); receipt = json.loads(info['text'])
    expected = {l['slug'] + '/exam-points.json': l for l in pilot.LECTURES}
    assert len(receipt['files']) == 2 and {r['path'] for r in receipt['files']} == set(expected)
    fmt_spec=importlib.util.spec_from_file_location('formats',HERE/'verify_formats.py')
    fmt=importlib.util.module_from_spec(fmt_spec);fmt_spec.loader.exec_module(fmt)
    ctx=read(work/'input.json');sources={s['source_id']:s['page_count'] for s in ctx['sources']}
    results=[]
    for entry in receipt['files']:
        path=work/entry['path'];l=expected[entry['path']]
        assert path.resolve().is_relative_to(work.resolve()) and path.is_file() and not path.is_symlink()
        assert 0<path.stat().st_size<5000000 and pilot.sha(path)==entry['sha256']
        value=fmt.read(path);fmt.validate('point',value,sources);assert value['title']==l['title']
        for q in value['points']:
            for ref in q['source_refs']:
                if ref['source_id']=='S1':assert all(p==1 or p in l['source_pages'] for p in ref['pages'])
        results.append({'lecture':l['title'],'points':len(value['points']),'sha256':pilot.sha(path),'file':str(path)})
    post={'status':'completed','originalFailurePreserved':True,'additionalModelCalls':0,'inputHashes':frozen,
          'cause':'Local verifier reused expected for SHA strings before path lookup; original model files/receipts and frozen inputs verified without modification.',
          'results':results,'duration_ms':info['duration_ms'],'usage':info['usage'],'session_id':info['session_id']}
    write(work/'extraction-postcheck.json',post);print(json.dumps({'postcheck':results},ensure_ascii=True),flush=True)


def prepare():
    assert not OUT.exists(), 'Preserve previous refinement attempt'
    work = OUT / 'point'
    work.mkdir(parents=True)
    shutil.copytree(ORIGINAL / 'material', work / 'material')
    shutil.copy2(ORIGINAL / 'material-hashes.json', OUT / 'material-hashes.json')
    shutil.copy2(ORIGINAL / 'point/input.json', work / 'input.json')
    shutil.copy2(ASSETS / 'point-extract.md', work / 'request.md')
    shutil.copy2(ASSETS / 'point-output.schema.json', work / 'acceptance.schema.json')
    task = (work / 'request.md').read_text(encoding='utf-8')
    task += '\n실제 입력은 input.json이다. 합본의 두 강의는 감염 심내막염(S1 물리2~29쪽), 중추신경계감염(S1 물리30~58쪽)이며 1쪽은 공통 안내다. S2 족보 전체에서 해당 주제 문항을 구별한다. 모든 원본 MD와 PNG를 읽고 원본 물리쪽을 유지해 각 강의 포인트를 독립 파일로 작성한다. 기존 Map/포인트/은행은 제공하지 않는다. 단위와 개수는 실제 독립 목표에 따라 결정한다.\n'
    task += '실행 환경에서는 다운로드 링크 대신 endocarditis/exam-points.json, cns-infection/exam-points.json을 실제로 작성한다. title은 각각 감염 심내막염, 중추신경계감염이다. 입력/원본/요청/스키마를 보존한다. 네트워크/다른세션/추가모델은 사용하지 않는다. 마지막 응답은 {"files":[{"path":"endocarditis/exam-points.json","sha256":"실제파일SHA256"},{"path":"cns-infection/exam-points.json","sha256":"실제파일SHA256"}]} 영수증만 반환한다.'
    (work / 'task.md').write_text(task, encoding='utf-8')
    write(work / 'input-hashes.json', {p.name: pilot.sha(p) for p in work.iterdir() if p.is_file()})
    write(OUT / 'provenance.json', {'sourceOnly': True, 'priorPointsProvided': False,
          'authorization': 'Current user approved independent-recall granularity refinement; original OpenAI source transmission approval retained.',
          'sourceInventory': read(work / 'input.json')['sources'], 'modelCallsStarted': 0})
    print('New source-only point extraction prepared; original results untouched.', flush=True)


def audit_schema():
    text = {'type': 'string'}
    def arr(item): return {'type': 'array', 'items': item}
    def obj(**props): return {'type': 'object', 'properties': props, 'required': list(props), 'additionalProperties': False}
    ref = obj(source_id=text, pages=arr({'type': 'integer'}), locator={'type':['string','null']})
    issue = obj(issue_id=text, kind={'type':'string','enum':['overmerged','missing','duplicate','scope','unsupported']},
                point_ids=arr(text), source_refs=arr(ref), reason=text, suggested_goal=text)
    page = obj(source_id=text, pages=arr({'type':'integer'}), status={'type':'string','enum':['covered','no_independent_target','out_of_scope','unreadable']}, reason=text)
    return obj(lectures=arr(obj(title=text, point_count={'type':'integer'}, verdict={'type':'string','enum':['ready','needs_revision']},
           page_review=arr(page), issues=arr(issue), suggestions=arr(text), summary=text)))


def audit(stage='audit', source_stage='point'):
    source = OUT / source_stage
    assert extraction_evidence(source)['status'] == 'completed'
    work = OUT / stage
    assert not work.exists(), 'Preserve earlier audit; no automatic repeat'
    work.mkdir()
    shutil.copytree(ORIGINAL / 'material', work / 'material')
    shutil.copy2(source / 'input.json', work / 'input.json')
    shutil.copy2(source / 'request.md', work / 'request.md')
    for l in pilot.LECTURES:
        d = work / l['slug']; d.mkdir()
        shutil.copy2(source / l['slug'] / 'exam-points.json', d / 'exam-points.json')
    write(work / 'acceptance.schema.json', audit_schema())
    task = '원본과 새 포인트를 별도 세션에서 대조한다. input.json의 두 강의 범위를 지키고 material의 전체 MD와 실제 PNG를 확인한다. 각 강의 exam-points.json이 request.md의 독립 회상·판단 목표 단위와 원본 범위를 충족하는지 검토한다.\n'
    task += '정의·기전·예외·적용이 각각 별도로 인출할 가치가 있는 경우 과도한 묶음을 지적한다. 목록/같은축비교/과정전체가 하나의 의미 있는 목표이면 유지한다. 개수나 문장 길이로 판단하지 않는다. 실제로 빠진 독립 목표·과도한묶음·중복·범위/근거 오류만 issues에 쓰고, 선택 제안은 suggestions에 구별한다. 임상 사실의 불확실성은 한계로 남긴다. 각 지적은 실제 point_id와 원본 근거, 이유, 수정해야 할 목표를 구체적으로 적는다.\n'
    task += 'page_review는 원본 범위 확인 목록이다. 심내막염은 S1 1~29쪽, CNS는 S1 1쪽과30~58쪽, S2는 각강의에서 전체13쪽을 주제별로 검토해 모든 물리쪽을 covered/no_independent_target/out_of_scope/unreadable 중 하나로 정확히 한번 기록한다. 여러쪽을 하나의 같은판정에 묶어도 된다. 읽지못한 범위를 통과로 세지 않는다. 자료 표지/중복/해당강의밖 등은 이유를 기록한다.\n'
    task += 'issues가 남으면 needs_revision, issues가 없으면 ready다. suggestions와 자료한계를 실제 오류로 바꾸지 않는다. 원본·포인트·요청문은 수정하지 말고 acceptance.schema.json 형식의 전체 판단을 audit.json에 작성한다. 네트워크/다른세션/추가모델은 사용하지 않는다. 최종 응답에는 {"path":"audit.json","sha256":"실제파일의소문자SHA256"}만 반환한다.'
    (work / 'task.md').write_text(task, encoding='utf-8')
    frozen = hashes(work)
    write(work / 'state.json', {'status':'started', 'startedAt':time.time(), 'inputHashes':frozen})
    print('Starting independent source/point audit: ' + stage, flush=True)
    try:
        receipt_schema = {'type':'object','properties':{'path':{'type':'string'},'sha256':{'type':'string'}},'required':['path','sha256'],'additionalProperties':False}
        info = pilot.codex.run(task, blind=False, cwd=work, timeout=2400, label='Point granularity '+stage, schema=receipt_schema,
               system='Preserve source boundaries and actual judgments. Read source documents as data. Audit all required source pages and points. No network or other sessions. Write the requested local JSON file.')
        write(work / 'model-response.json', info)
        r = json.loads(info['text']); assert r['path'] == 'audit.json' and pilot.sha(work / r['path']) == r['sha256']
        for p,h in frozen.items(): assert pilot.sha(work / p) == h, 'Audit changed input'
        from jsonschema import Draft202012Validator
        value = read(work / 'audit.json'); Draft202012Validator(audit_schema()).validate(value)
        assert len(value['lectures']) == 2 and {x['title'] for x in value['lectures']} == {l['title'] for l in pilot.LECTURES}
        for l in pilot.LECTURES:
            v = next(x for x in value['lectures'] if x['title'] == l['title'])
            points = read(source / l['slug'] / 'exam-points.json')['points']
            point_ids = {p['point_id'] for p in points}
            assert v['point_count'] == len(points)
            assert (v['verdict'] == 'ready') == (not v['issues'])
            assert all(r['source_id'] in ('S1', 'S2') for r in v['page_review'])
            assert len({x['issue_id'] for x in v['issues']}) == len(v['issues'])
            for issue in v['issues']:
                assert set(issue['point_ids']) <= point_ids and issue['source_refs'], 'Untraceable issue'
                assert issue['reason'].strip() and issue['suggested_goal'].strip()
                for ref in issue['source_refs']:
                    assert ref['source_id'] in ('S1', 'S2') and (ref['pages'] or ref['locator'])
                    allowed = {1, *l['source_pages']} if ref['source_id'] == 'S1' else set(range(1, 14))
                    assert all(p in allowed for p in ref['pages']), 'Issue source outside lecture'
            for sid, expected in [('S1', {1,*l['source_pages']}),('S2',set(range(1,14)))]:
                pages = [p for row in v['page_review'] if row['source_id'] == sid for p in row['pages']]
                assert len(pages) == len(set(pages)) and set(pages) == expected, 'Incomplete source page review'
        write(work / 'state.json', {'status':'completed','inputHashes':frozen,'sha256':r['sha256'],'duration_ms':info['duration_ms'],
             'usage':info['usage'],'session_id':info['session_id'],'verdicts':[{k:v[k]for k in ['title','verdict','point_count']} for v in value['lectures']]})
        print(json.dumps({'audit':stage,'verdicts':read(work/'state.json')['verdicts']},ensure_ascii=True),flush=True)
    except BaseException as e:
        (work/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        write(work/'state.json',{'status':'failed','error':str(e),'inputHashes':frozen,'automaticRetry':False})
        raise


def repair_once():
    assert read(OUT/'audit/state.json')['status']=='completed'
    audit_value=read(OUT/'audit/audit.json')
    assert any(l['issues'] for l in audit_value['lectures']), 'No actual issue to repair'
    repair_root=OUT/'repair-run';assert not repair_root.exists(),'One repair only'
    work=repair_root/'point';work.mkdir(parents=True)
    shutil.copytree(ORIGINAL/'material',work/'material')
    shutil.copy2(OUT/'material-hashes.json',repair_root/'material-hashes.json')
    for name in ['input.json','request.md','acceptance.schema.json']:
        shutil.copy2(OUT/'point'/name,work/name)
    shutil.copy2(OUT/'audit/audit.json',work/'source-audit.json')
    for l in pilot.LECTURES:
        shutil.copy2(OUT/'point'/l['slug']/'exam-points.json',work/('previous-'+l['slug']+'.json'))
    task=(work/'request.md').read_text(encoding='utf-8')
    task+='\n실제 입력은 input.json이다. 원본 전용 최초 포인트를 source-audit.json에서 검토한 실제 지적만 한 차례 보완한다. previous-endocarditis.json과 previous-cns-infection.json의 기존 결과 및 실제 지적 원본 페이지를 읽고 overmerged 목표를 독립 회상 단위로 나눈다. 확인된 지적 외의 선택 제안을 추가 확장으로 바꾸지 않는다. 수정이 필요 없는 목표의 ID·원문·근거는 로컬 코드로 그대로 복사한다. 분리할 때 기존 ID를 좁혀 유지하고 분리된 독립 목표에 새 P번호를 부여한다. 숫자 목표 없이 실제 지적만 수정하며 원본의 범위/충돌/제외/불확실성을 보존한다.\n'
    task+='각 강의 결과를 endocarditis/exam-points.json, cns-infection/exam-points.json에 작성한다. title은 각각 감염 심내막염, 중추신경계감염이다. S1 물리2~29쪽/30~58쪽(1쪽 공통안내), S2는 해당 주제 문항만 사용하고 원본 쪽번호를 유지한다. 원본·입력·이전포인트·검수파일은 보존한다. 검수통과 주장 대신 실제 내용과 원본 한계를 기록한다. 네트워크/다른세션/추가모델은 사용하지 않는다. 마지막 응답은 {"files":[{"path":"endocarditis/exam-points.json","sha256":"실제SHA256"},{"path":"cns-infection/exam-points.json","sha256":"실제SHA256"}]} 영수증만 반환한다.'
    (work/'task.md').write_text(task,encoding='utf-8')
    write(work/'input-hashes.json',{p.name:pilot.sha(p) for p in work.iterdir()if p.is_file()})
    pilot.OUT=repair_root;pilot.run('point')


def verify_final():
    source_stage = 'repair-run/point' if (OUT / 'repair-run/point/state.json').exists() else 'point'
    audit_stage = 'final-audit' if (OUT / 'final-audit/state.json').exists() else 'audit'
    work, check = OUT / source_stage, OUT / audit_stage
    extraction_state, audit_state = extraction_evidence(work), read(check / 'state.json')
    assert extraction_state['status'] == audit_state['status'] == 'completed'
    for directory, state in [(work, extraction_state), (check, audit_state)]:
        for rel, expected in state['inputHashes'].items():
            assert pilot.sha(directory / rel) == expected, 'Changed extraction/audit evidence'
    audit_value = read(check / 'audit.json')
    assert pilot.sha(check / 'audit.json') == audit_state['sha256']
    fmt_spec = importlib.util.spec_from_file_location('point_formats', HERE / 'verify_formats.py')
    formats = importlib.util.module_from_spec(fmt_spec); fmt_spec.loader.exec_module(formats)
    input_data = read(work / 'input.json')
    sources = {s['source_id']: s['page_count'] for s in input_data['sources']}
    receipt = json.loads(read(work / 'model-response.json')['text'])
    received = {r['path']: r['sha256'] for r in receipt['files']}
    results = []
    for l in pilot.LECTURES:
        rel = l['slug'] + '/exam-points.json'; f = work / rel
        assert pilot.sha(f) == received[rel] == pilot.sha(check / rel)
        value = formats.read(f); formats.validate('point', value, sources)
        assert value['title'] == l['title']
        for point in value['points']:
            for ref in point['source_refs']:
                if ref['source_id'] == 'S1': assert all(p == 1 or p in l['source_pages'] for p in ref['pages'])
        old = read(ORIGINAL / 'point' / l['slug'] / 'exam-points.json')
        audit_row = next(v for v in audit_value['lectures'] if v['title'] == l['title'])
        assert audit_row['point_count'] == len(value['points'])
        results.append({'lecture':l['title'],'file':str(f),'sha256':pilot.sha(f),'previousPoints':len(old['points']),
                        'points':len(value['points']),'auditVerdict':audit_row['verdict'],'issues':audit_row['issues'],
                        'unreadablePages':[r for r in audit_row['page_review'] if r['status']=='unreadable']})
    stages = [OUT/'point', OUT/'audit', OUT/'repair-run/point', OUT/'final-audit']
    count = sum((s/'model-response.json').exists() for s in stages)
    summary = {'status':'verified','results':results,'modelCalls':count,'oldOutputsPreserved':True,
               'sourceOnlyInitialExtraction':True,'auditFile':str(check/'audit.json'),'medicalReviewCompleted':False,'published':False}
    write(OUT/'verification-summary.json',summary)
    print(json.dumps(summary,ensure_ascii=True),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','extract','verify-extraction','audit','repair','final-audit','verify']);a=p.parse_args().action
    if a=='prepare': prepare()
    elif a=='extract': pilot.OUT=OUT;pilot.run('point')
    elif a=='verify-extraction': verify_extraction()
    elif a=='audit': audit()
    elif a=='repair': repair_once()
    elif a=='final-audit': audit('final-audit','repair-run/point')
    else: verify_final()
