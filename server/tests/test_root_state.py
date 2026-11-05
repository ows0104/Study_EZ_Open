from datetime import timedelta
from tests.root_support import document, POLICY, NOW
from app.root_learning.state import summary, replay

doc=document();available={'task1','task2','task3'}
events=[]
def add(id,kind,did='D1',**fields):
    events.append({'id':id,'kind':kind,'revision':'v1','at':NOW+timedelta(seconds=len(events)),
                   'payload':{'direction_id':did,'task_id':'task1','policy':POLICY,**fields}})
def current():return summary(doc,events,available,NOW+timedelta(minutes=1),POLICY)
add('reveal','reveal',attempted=True)
assert current()['learned']==1 and current()['recalled']==0
assert current()['targets'][0]['status']=='미평가'
add('rate','rate',grade='independent',helped=False)
assert current()['learned']==1 and current()['recalled']==0
add('reveal2','reveal','D2',attempted=True)
add('rate2','rate','D2',grade='independent',helped=False)
assert current()['learned']==1 and current()['recalled']==1 and current()['newToday']==1
invalid_help = events[:4] + [{'id':'invalid-help','kind':'rate','revision':'v1','at':NOW+timedelta(seconds=30),
    'payload':{'direction_id':'D2','task_id':'task2','policy':POLICY,'grade':'independent','helped':True}}]
assert summary(doc,invalid_help,available,NOW+timedelta(minutes=1),POLICY)['recalled']==0
add('undo','undo',undo='rate2')
assert current()['recalled']==0 and current()['learned']==1
add('rate3','rate','D2',grade='partial',helped=True)
assert current()['recalled']==0
assert current()['total']==3 and current()['unready']==1
assert summary(doc,events,set(),NOW+timedelta(minutes=1),POLICY)['total']==3
assert summary(doc,events,set(),NOW+timedelta(minutes=1),POLICY)['recalled']==0
before=summary(doc,[],available,NOW,POLICY)
assert before['learned']==0 and before['newToday']==0
print('PASS: first learning, unassessed state, every required direction, unique goals, undo preservation, partial/help, readiness denominator')
