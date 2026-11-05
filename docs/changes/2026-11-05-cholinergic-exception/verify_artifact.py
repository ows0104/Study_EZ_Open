"""Verify final example bytes, once-only lineage and actual preview evidence."""
import base64,hashlib,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import exception as e
import assemble as a
f=e.f

def main():
    a.configure();e.check();value=f.read(e.OUT/'result.json');proof=f.read(e.OUT/'proof.json')
    assert proof['priorCorrectionRounds']==3 and proof['additionalCorrectionLimit']==1
    assert f.read(e.OUT/'ledger.json')['budgetsReset']is False
    for name,sha in proof['referenceFiles'].items():assert f.sha(e.OUT/'references'/name)==sha
    for stage in ('repair-4','source-4','resolve-4'):
        work=e.OUT/'stages'/stage/'workspace'
        for name,sha in proof['referenceFiles'].items():assert f.sha(work/'references'/name)==sha
        # Every original page image and both extracted source texts are supplied.
        original_material=[p for p in (e.OUT/'material').iterdir()if not p.name.startswith('stimulus-')]
        assert len(original_material)==37
        for p in original_material:assert f.sha(work/'material'/p.name)==f.sha(p)
    # Frozen assessment hashes must bind the exact final bank and map.
    assert f.read(e.OUT/'stages/source-4/input.json')['bank']==value['bank']
    before=f.read(e.OUT/'brief-before-review-adoption.json');adoption=f.read(e.OUT/'source-review-adoption.json')
    assert f.read(e.OUT/'stages/source-4/input.json')['brief']==before
    assert value['sourceReviewAdoption']==adoption and adoption['builderHash']==f.sha(e.HERE/'assemble.py')
    reviewed=e.deepcopy(before)
    next(r for r in reviewed['relations']if r['relation_id']=='R35')['review_status']='reviewed'
    assert reviewed==value['brief']and adoption['additionalModelCalls']==0
    raw_assessment=f.read(e.OUT/'assessment-before-review-adoption.json')
    assert raw_assessment==f.envelope(before,value['bank'],f.read(e.OUT/'stages/source-4/output.json'))
    assert value['sourceAssessment']['assessment']==raw_assessment['assessment']
    for name in ('repair-4','source-4','resolve-4'):
        stage=e.OUT/'stages'/name
        f.g.jsonschema.validate(f.read(stage/'output.json'),f.read(stage/'schema.json'))
    stage=e.OUT/'stages/medical-4';entry=f.read(e.OUT/'ledger.json')['stages']['medical-4']
    assert f.sha(stage/'input-images.json')==entry['imageInputHash']
    assert hashlib.sha256((stage/'prompt.txt').read_text(encoding='utf-8').encode()).hexdigest()==entry['promptHash']
    assert entry['bankHash']==f.g.document_hash(value['bank'])
    from quizbank.review import shape
    reshaped=shape(f.read(stage/'output.json'),value['bank'])
    assert {k:v for k,v in reshaped.items()if k!='reviewed_at'}=={k:v for k,v in value['medical'].items()if k!='reviewed_at'}
    assert f.read(e.OUT/'adjudication.json')['resolution']==value['resolution']
    final_input=f.read(e.OUT/'stages/resolve-4/input.json')
    assert final_input['orchestration']['scriptHash']==f.sha(e.HERE/'resolve_compact.py')
    base=f.read(f.BASE/'assembled-result.json')
    assert final_input['originalBaseline']=={k:base[k]for k in ('brief','summary')}
    # Every new crop must be byte-identical to the declared original-page crop.
    import fitz
    source=next(s for s in f.read(f.ORIGIN/'packet.json')['sources']if s['id']=='S1')
    with fitz.open(source['localPath'])as pdf:
        for s in value['visualStimuli']:
            page=pdf[s['page']-1];r=page.rect;x0,y0,x1,y1=s['crop']
            pix=page.get_pixmap(matrix=fitz.Matrix(2,2),clip=fitz.Rect(x0*r.width,y0*r.height,x1*r.width,y1*r.height))
            assert hashlib.sha256(pix.tobytes('png')).hexdigest()==s['imageSha256']
            assert s['sourceSha256']==source['sha256']
    preview=f.read(e.OUT/'preview-proof.json');path=Path(preview['preview']);text=path.read_text(encoding='utf-8')
    assert preview['resultHash']==f.sha(e.OUT/'result.json')and preview['previewHash']==f.sha(path)
    assert preview['builderHash']==f.sha(e.HERE/'build_preview.py')and preview['templateHash']==f.sha(path.with_name('cholinergic-exception.template.html'))
    data=json.loads(re.search(r'<script type="application/json" id="cholinergic-corrected-data-1104">(.*?)</script>',text,re.S).group(1))
    for field in ('concepts','relations','targets','points'):assert data[field]==value['brief'][field]
    assert data['summary']==value['summary']and data['resolution']==value['resolution']
    assert data['approvedItems']==value['adjudication']['approved_items']
    assert data['presentation']==f.read(e.OUT/'presentation-audit.json')
    assert data['tasks']==data['presentation']['reviewedTasks']and data['sourceTasks']==value['document']['tasks']
    assert data['sourceReviews']==value['sourceAudit']['question_checks']['reviews']and data['medicalReviews']==value['medical']['reviews']
    from studyez_contracts.bank.cloze import normalize_cloze
    for q,raw in zip(data['questions'],value['bank']['questions'],strict=True):
        assert all(v==raw[k]for k,v in q.items()if k!='displayQuestion')
        assert q['displayQuestion']==normalize_cloze(raw)['question']
    assert [{k:v for k,v in s.items()if k!='dataUrl'}for s in data['visualStimuli']]==value['visualStimuli']
    for s in data['visualStimuli']:assert hashlib.sha256(base64.b64decode(s['dataUrl'].split(',')[1])).hexdigest()==s['imageSha256']
    assert len(text.encode())<1024*1024 and not re.search(r'<(?:html|head|body|!doctype)\b',text,re.I)
    qa=f.read(e.OUT/'preview-qa.json');assert qa['pass']and qa['previewHash']==f.sha(path)and qa['scriptHash']==f.sha(e.HERE/'preview_qa.cjs')
    print(json.dumps({'artifactPass':True,'priorResultUntouched':True,'additionalCorrections':1,'cumulativeRound':4,
        'published':False,'verifierHash':f.sha(Path(__file__)),'previewQa':qa},ensure_ascii=False))

if __name__=='__main__':main()
