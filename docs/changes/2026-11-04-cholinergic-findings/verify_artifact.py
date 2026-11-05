"""Check immutable execution/provenance and actual preview data, offline only."""
import base64,importlib.util,json,hashlib,re
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('followup',HERE/'followup.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    f.check();value=f.read(f.OUT/'result.json');ledger=f.read(f.OUT/'ledger.json')
    packet=f.read(f.ORIGIN/'packet.json');origin=f.read(f.ORIGIN/'ledger.json')
    assert f.g.packet_hash(packet)==packet['inputHash']
    assert origin['repairRounds']==3 and len(origin['stages'])==13
    for name,s in origin['stages'].items():assert s['status']=='completed'and f.g.document_hash(f.read(f.ORIGIN/(name+'.json')))==s['outputHash']
    for name,entry in ledger['stages'].items():
        stage=f.OUT/'stages'/name
        if name=='map-2' and entry['status']=='failed':
            assert entry==value['technicalRecoveryProof']['failedStage']
            assert f.g.document_hash(f.read(stage/'input.json'))==entry['inputHash']
            assert digest(stage/'prompt.txt')==entry['promptHash']
            assert f.g.document_hash(f.read(stage/'schema.json'))==entry['schemaHash']
            assert not list((stage/'workspace/material').glob('stimulus*'))
            assert not(stage/'workspace/references').exists()
            continue
        if name=='assembly-map2':
            sp=importlib.util.spec_from_file_location('recover_completed_map',HERE/'recover_completed_map.py');rc=importlib.util.module_from_spec(sp);sp.loader.exec_module(rc)
            raw,patch,usage,_=rc.extract();ctx=f.read(stage/'input.json')
            assert raw==(stage/'raw.txt').read_text(encoding='utf-8')and patch==f.read(stage/'output.json')and usage==f.read(stage/'usage.json')
            normalized,changes,rejected=rc.normalize_classification_orientation(rc.mp.replay(ctx['previous_source_only_brief'],patch))
            assert normalized==f.read(f.OUT/'brief-before-direction-fix.json') and changes==value['technicalRecoveryProof']['classificationOrientation']
            assert rejected==value['technicalRecoveryProof']['unadoptedPrerequisiteProposals']
            assert ctx['operatorScriptHash']==digest(HERE/'map_patch.py')
            assert value['technicalRecoveryProof']['operatorScriptHash']==digest(HERE/'recover_completed_map.py')
            assert set(ctx)==set(f.context(packet))|{'previous_source_only_brief','operatorScriptHash','sourceOnlyFiles','source_completeness_diagnostics'}
            assert len(ctx['sourceOnlyFiles'])==37
            for row in ctx['sourceOnlyFiles']:assert digest(f.OUT/'stages/map-2/workspace/material'/row['name'])==row['sha256']
            continue
        if not name.startswith('medical-'):
            assert f.g.document_hash(f.read(stage/'schema.json'))==entry['schemaHash']
        if name.startswith('map-'):
            assert name=='map-1' and f.read(stage/'output.json')==f.read(f.OUT/'brief-before-map2.json')
            assert not (stage/'workspace/references').exists()
        elif not name.startswith('medical-'):
            copied=f.read(stage/'workspace/references/manifest.json')
            latest={r['id']:r for r in value['referenceManifest']['references']}
            assert all(latest[r['id']]==r for r in copied['references'])
            if copied!=value['referenceManifest']:
                assert copied==f.read(f.OUT/'references/manifest-before-E17E18.json')
            for r in copied['references']:
                path=stage/'workspace/references'/r['textFile']
                assert digest(path)==digest(f.OUT/'references'/r['textFile'])
                assert digest(path)==r['textSha256']or hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()==r['textSha256']
        if name.startswith('source-'):
            n=int(name.split('-')[1]);ctx=f.read(stage/'input.json')
            expected=f.read(f.OUT/'brief-before-map2.json')if n==1 else f.read(f.OUT/'brief-before-direction-fix.json')if n==2 else value['brief']
            assert ctx['brief']==expected and ctx['bank']==f.read(f.OUT/f'bank-{n}.json')
            if n>1:assert ctx['structuralNormalization']=={k:value['technicalRecoveryProof'][k]for k in ('classificationOrientation','unadoptedPrerequisiteProposals')}
        if name.startswith('medical-'):
            n=int(name.split('-')[1]);assert entry['bankHash']==f.g.document_hash(f.read(f.OUT/f'bank-{n}.json'))
            assert digest(stage/'input-images.json')==entry['imageInputHash']
            path=stage/'prompt.txt'
            assert digest(path)==entry['promptHash']or hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()==entry['promptHash']
            assert f.read(stage/'input-images.json')==[{k:s[k]for k in ('question_id','imageFile','imageSha256')}for s in f.read(f.OUT/f'stimuli-{n}.json')]
            if (stage/'blind-events.jsonl').exists():f.codex.parse_events((stage/'blind-events.jsonl').read_text(encoding='utf-8'),model=f.codex.model_name(),blind=True)
        if name.startswith('repair-'):
            n=int(name.split('-')[1]);authored=f.read(stage/'output.json')
            if 'bank'in authored:assert authored['bank']==f.read(f.OUT/f'bank-{n}.json')
            else:
                spec2=importlib.util.spec_from_file_location('round_patch',HERE/'round_patch.py');operator=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(operator)
                assert operator.replay(f.read(f.OUT/f'bank-{n-1}.json'),authored)==f.read(f.OUT/f'bank-{n}.json')
                assert f.read(stage/'input.json')['operatorScriptHash']==digest(HERE/('final_patch.py'if n==3 else 'round_patch.py'))
                if n==3:
                    sp=importlib.util.spec_from_file_location('final_patch',HERE/'final_patch.py');fp=importlib.util.module_from_spec(sp);sp.loader.exec_module(fp)
                    assert fp.apply_refs(f.read(f.OUT/'brief-before-direction-fix.json'),authored['direction_relation_fixes'])==value['brief']
                    assert value['mapChanges']['directionReferenceFixes']['fixes']==authored['direction_relation_fixes']
        if name.startswith('source-')and int(name.split('-')[1])>1:
            assert f.read(stage/'input.json')['operatorScriptHash']==digest(HERE/'round_patch.py')
    transition=f.read(f.OUT/'runtime/visual-transition.json')
    targeted=value['targetedMapTransition']
    recovery=value['technicalRecoveryProof']
    assert transition['after']==targeted['before'] and targeted['after']==recovery['before'] and recovery['after']==value['proof']
    assert recovery['modelCompleted'] and recovery['cliTimedOut'] and recovery['additionalModelCalls']==0 and not recovery['budgetsReset']
    assert digest(f.OUT/'runtime/followup-before-map-recovery.py')==recovery['before']['helperHash']
    assert not transition['budgetsReset'] and not targeted['budgetsReset']
    assert digest(f.OUT/'runtime/followup-before-targeted-map.py')==targeted['before']['helperHash']
    assert transition['before']==f.read(f.OUT/'runtime/proof-before-visual.json')
    assert digest(f.OUT/'runtime/followup-before-visual.py')==transition['before']['helperHash']
    assert transition['mapStage']==ledger['stages']['map-1']
    assert transition['mapOutputHash']==f.g.document_hash(f.read(f.OUT/'brief-before-map2.json'))
    verification=f.read(f.OUT/'runtime/final-check-transition.json')
    assert verification['before']==value['proof']and verification['after']==f.proof()and verification['modelCalls']==0
    assert digest(f.OUT/'runtime/followup-before-final-check.py')==value['proof']['helperHash']
    assert digest(f.OUT/'runtime/reference-newline-proof.json')==verification['referenceNewlineProofHash']
    for row in f.read(f.OUT/'runtime/reference-newline-proof.json')['references']:
        path=f.OUT/'references'/row['textFile'];assert digest(path)==row['originalByteHash']and hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()==row['declaredCanonicalLfHash']
    for r in value['referenceManifest']['references']:
        if r.get('rawFile'):assert digest(f.OUT/'references'/r['rawFile'])==r['rawSha256']
    proof=f.read(f.OUT/'preview-proof.json');p=Path(proof['preview']);text=p.read_text(encoding='utf-8')
    assert proof['resultHash']==digest(f.OUT/'result.json') and proof['previewHash']==digest(p)
    assert proof['builderHash']==digest(HERE/'build_preview.py')
    assert proof['templateHash']==digest(p.with_name('cholinergic-corrected.template.html'))
    match=re.search(r'<script type="application/json" id="cholinergic-corrected-data-1104">(.*?)</script>',text,re.S)
    data=json.loads(match.group(1));assert data['summary']==value['summary']
    assert data['concepts']==value['brief']['concepts'] and data['targets']==value['brief']['targets']
    assert data['points']==value['brief']['points']
    presentation=f.read(f.OUT/'presentation-audit.json')
    assert presentation['resultHash']==digest(f.OUT/'result.json')and presentation['resolutionHash']==f.g.document_hash(value['resolution'])
    assert presentation['builderHash']==digest(HERE/'prepare_presentation.py')
    assert data['resolution']==value['resolution'] and data['presentation']==presentation
    assert data['tasks']==presentation['reviewedTasks']and data['sourceTasks']==value['document']['tasks']
    held={r['direction_id']for r in presentation['reviewHolds']}
    checks={r['question_id']:r for r in value['sourceAudit']['question_checks']['reviews']};med={r['question_id']:r for r in value['medical']['reviews']}
    assert data['tasks']==[t for t in value['document']['tasks']if t['direction_id']not in held and checks[t['question_id']]['verdict']=='ok'and med[t['question_id']]['verdict']=='ok']
    directions={d['direction_id']:d for t in value['brief']['targets']for d in t['directions']}
    ready={t['direction_id']for t in value['document']['tasks']}
    assert {did for did,d in directions.items()if d['requirement']=='required'}<=ready
    mappings=value['sourceAudit']['review']['mappings']
    for claim in value['resolution']['directions']:
        if claim['ready']:
            assert claim['current_direction_ids']and set(claim['current_direction_ids'])<=ready
            for did in claim['current_direction_ids']:
                assert any(m['direction_id']==did and m['question_id']in claim['question_ids']and set(directions[did]['relation_ids'])<=set(m['tested_relation_ids'])for m in mappings)
    assert [{k:v for k,v in s.items()if k!='dataUrl'}for s in data['visualStimuli']]==value['visualStimuli']
    for s in data['visualStimuli']:
        assert digest(f.OUT/'material'/s['imageFile'])==s['imageSha256']
        assert hashlib.sha256(base64.b64decode(s['dataUrl'].split(',')[1])).hexdigest()==s['imageSha256']
    from studyez_contracts.bank.cloze import normalize_cloze
    assert all({k:v for k,v in q.items()if k!='displayQuestion'}=={k:raw[k]for k in q if k!='displayQuestion'}and q['displayQuestion']==normalize_cloze(raw)['question']for q,raw in zip(data['questions'],value['bank']['questions'],strict=True))
    assert not re.search(r'<(?:html|head|body|!doctype)\b',text,re.I)
    qa=f.read(f.OUT/'preview-qa.json');assert qa['pass'] and qa['previewHash']==digest(p)and qa['scriptHash']==digest(HERE/'preview_qa.cjs')
    print(json.dumps({'artifactPass':True,'stageCounts':{k:sum(name.split('-')[0]==k for name in ledger['stages']) for k in f.LIMITS},
        'sourceTasks':len(value['document']['tasks']),'reviewedTasks':len(data['tasks']),'postReviewHolds':sorted(held),
        'originalPilotUntouched':True,'published':False,'verifierHash':digest(Path(__file__)),'previewQa':qa},ensure_ascii=False))
if __name__=='__main__':main()
