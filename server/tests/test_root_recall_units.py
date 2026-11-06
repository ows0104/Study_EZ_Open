"""Real HTTP consumer accepts explicit recall units, preserving separate tasks."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests/contracts'))
import generation_v2_fixture as f
from studyez_contracts.roots import generation_v2 as c
from studyez_contracts.roots.source_assessment import envelope
from tests.root_support import setup,publish,start,view,action

client,user,_=setup()
b=f.brief();b['recall_policy']='recall-units/1';bank=f.old.bank()
d=b['targets'][0]['directions'][0]
d['recall_units']=[{'unit_id':'UNIT1','cue':d['cue'],'answer_scope':d['answer_scope'],
    'component_ids':['fact'],'relation_ids':d['relation_ids']}]
a=f.assessment(b,bank);a['design_checks']=[{'question_id':q['question_id'],'verdict':'ok','reason':'Synthetic clear single recall'}for q in bank['questions']]
audit=c.compile_assessment(b,bank,envelope(b,bank,a))
doc=c.make_document(b,bank,audit,revision='units-http',title='Synthetic units',exam_date=None,medical=f.old.checks(bank))
publish(client,user,doc)
sid=start(client,'units-session');front=view(client,sid)
assert front['task']['question']['question_id']=='Q1'
assert 'Secret answer'not in str(front)
assert action(client,sid,'units-reveal','reveal',attempted=True).status_code==200
assert view(client,sid)['task']['answer']['answer']=='Secret answer 1'
assert any(task['direction_id']=='UNIT1'for task in doc['tasks'])
print('PASS opt-in recall unit document, real publication, separate task identity and private answer reveal')
