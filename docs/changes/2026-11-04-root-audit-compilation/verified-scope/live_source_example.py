"""One nonmedical CLI example, never a production lecture or publication."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests/contracts'))
import automation_fixture as f
from quizbank import connection_generate as g
from studyez_contracts.roots.source_assessment import envelope,compile_source_assessment

out=ROOT/'runs/_development/2026-11-04-root-audit-compilation/live-source-1'
out.mkdir(parents=True,exist_ok=False)
material=out/'material';material.mkdir()
body=b'Fictional lookup table for a software test only: the partner of A is B. The partner of B is A. These are two directed lookup facts; no medical content is involved.'
(material/'S1.md').write_bytes(body)
brief=f.brief();bank=f.bank()
brief['sources'][0].update(label='toy-pairs.txt',sha256=hashlib.sha256(body).hexdigest())
for i,(left,right) in enumerate([('A','B'),('B','A')]):
    d=brief['targets'][0]['directions'][i]
    d.update(cue=f'What is the partner of {left}?',answer_scope=right)
    brief['relations'][i].update(condition=f'Lookup partner of {left}',reason=f'The fictional table maps {left} to {right}.')
    q=bank['questions'][i]
    q.update(question=d['cue'],answer=right,answer_units=[right],explanation=brief['relations'][i]['reason'])
bank['concepts'][0]['core_facts']=['A maps to B.','B maps to A.']
context={'title':'Fictional directed lookup example','scope':'Nonmedical software example only',
    'conceptMap':'A -> B and B -> A','points':'Recall both directed lookup facts',
    'examDate':None,'brief':brief,'bank':bank,'sources':brief['sources']}
g.write(out/'input.json',context)
g.write(out/'wire-schema.json',g.output_schema(g.source_assessment_schema(brief,bank)))
assessment,usage=g.call_model('source-example',context,material,None)
raw=envelope(brief,bank,assessment)
g.write(out/'assessment.raw.json',raw);g.write(out/'usage.json',usage)
audit=compile_source_assessment(brief,bank,raw)
g.write(out/'audit.json',audit)
document=g.make_document(brief,bank,audit,revision='synthetic-only',title=context['title'],exam_date=None)
g.write(out/'document.json',document)
summary={'sourceFormat':g.SOURCE_FORMAT,'model':g.codex.model_name(),
    'runtimeHash':g.identity({'inputHash':g.document_hash(context)},None),
    'wireSchemaHash':g.document_hash(g.output_schema(g.source_assessment_schema(brief,bank))),
    'questions':len(bank['questions']),'tasks':len(document['tasks']),
    'auditHash':g.document_hash(audit),'rawHash':g.document_hash(raw),
    'coverage':[c['status']for c in audit['review']['coverage']],
    'published':False,'productionDataUsed':False}
g.write(out/'summary.json',summary)
print(json.dumps(summary,ensure_ascii=False))
assert len(document['tasks'])==2,'The toy example should demonstrate both whole-direction tasks.'
