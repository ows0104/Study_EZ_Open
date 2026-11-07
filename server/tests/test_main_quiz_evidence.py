"""Evidence never silently substitutes another source or an arbitrary first page."""
from types import SimpleNamespace
from copy import deepcopy
from unittest.mock import patch
from tests.root_support import setup,document
client,user,SessionLocal=setup()
from app.root_learning.evidence import attach_evidence
doc=document();doc['review']['sources'][0].update(page_count=5,label='original.pdf')
row=SimpleNamespace(document=doc,subject='test',run_id='demo')
source={'id':'S1','sha256':doc['review']['sources'][0]['sha256'],'filename':'original.pdf',
        'snapshotKey':'frozen/original.pdf','pageCount':5,'contentType':'application/pdf'}
generation=SimpleNamespace(web_dispatch=None,packet={'sources':[source]})
question={'question_id':'Q1','source_refs':[{'source_id':'S1','locator':'p2-3'},{'source_id':'S1','locator':'p99'},
    {'source_id':'EXT','locator':'p1'}]}
before=deepcopy(doc)
with patch('app.root_learning.evidence.ObjectStorage')as storage:
    storage.return_value.presign_download.return_value='https://example.invalid/signed.pdf?token=synthetic'
    out={};attach_evidence(None,row,question,generation,out)
    assert [s['page']for s in out['pdfSlides']]==[2,3]
    assert all(s['sourceSha256']==source['sha256']for s in out['pdfSlides'])
    assert out['sourceLinks'][0]['label']=='original.pdf'
    assert storage.return_value.presign_download.call_args.kwargs['inline']
    no_page={};attach_evidence(None,row,{'source_refs':[]},generation,no_page)
    assert no_page['pdfSlides']==[]
    changed=SimpleNamespace(web_dispatch=None,packet={'sources':[{**source,'sha256':'0'*64}]})
    mismatch={};attach_evidence(None,row,question,changed,mismatch)
    assert mismatch['pdfSlides']==[] and mismatch['sourceLinks']==[]
    unrelated={};attach_evidence(None,row,question,None,unrelated)
    assert unrelated=={}
assert row.document==before
print('PASS: exact source hash and bounded cited pages, inline PDF, no invented page, no mutation')
