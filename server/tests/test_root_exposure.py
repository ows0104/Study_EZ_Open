from concurrent.futures import ThreadPoolExecutor
from tests.root_support import setup,publish,start,view,action,document
client,user,SessionLocal=setup()
doc=document();doc['review']['mappings'][0]['explanation_relation_ids']=['R2']
publish(client,user,doc);sid=start(client)
assert action(client,sid,'r1','reveal',attempted=True).status_code==200
assert action(client,sid,'g1','rate',grade='independent').status_code==200
assert view(client,sid)['task']['helped']
assert action(client,sid,'r2','reveal',attempted=True).status_code==200
assert action(client,sid,'g2','rate',grade='independent').status_code==422
assert action(client,sid,'partial','rate',grade='partial').status_code==200
assert view(client,sid)['summary']['learned']==1 and view(client,sid)['summary']['recalled']==0
version=view(client,sid)['version']
def send(i):
    return client.post('/api/root-learning/sessions/'+sid+'/events',json={
        'requestId':f'parallel{i}','version':version,'kind':'reveal','attempted':True}).status_code
with ThreadPoolExecutor(max_workers=2) as pool:
    results=list(pool.map(send,[1,2]))
assert sorted(results)==[200,409],results
assert view(client,sid)['version']==version+1
print('PASS: earlier explanations mark provided relations as helped, no whole-goal promotion, concurrent revision writes accept exactly once')
