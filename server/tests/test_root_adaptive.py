from copy import deepcopy
from datetime import UTC, datetime, timedelta
from tests.root_support import POLICY,LEGACY_POLICY,document
from app.root_learning.policy import transition,effective_due,validate_policy,study_day,day_start,configured_policy
from app.root_learning.state import summary,replay
from app.root_learning.planning import plan

now=datetime(2026,11,3,1,tzinfo=UTC)
empty={'stage':-1,'lastDay':None,'rating':None}
def success(previous,at,exam=None):return transition(previous,'independent',False,at,POLICY,exam)
a=success(empty,now);b=success(a,now+timedelta(days=1));c=success(b,now+timedelta(days=3));d=success(c,now+timedelta(days=7))
assert [x['baseDays'] for x in (a,b,c,d)]==[1,2,4,8]
assert success(b,now+timedelta(days=6))['baseDays']==10
assert success(c,now+timedelta(days=3,hours=2))['baseDays']==4
assert success(c,now+timedelta(days=3,hours=19))['baseDays']==4
partial=transition(d,'partial',False,now+timedelta(days=15),POLICY)
missed=transition(d,'missed',False,now+timedelta(days=15),POLICY)
helped=transition(d,'independent',True,now+timedelta(days=15),POLICY)
assert partial['baseDays']==4 and missed['baseDays']==1
assert helped['rating']=='partial' and helped['baseDays']==4
assert success(d,now+timedelta(days=100))['baseDays']==POLICY['max_days']
near=success(b,now+timedelta(days=3),'2026-11-12')
far=success(b,now+timedelta(days=3),'2026-12-06')
past=success(b,now+timedelta(days=3),'2026-11-05')
assert near['baseDays']==far['baseDays']==past['baseDays']==4
assert near['scheduledDays']==1 and far['scheduledDays']==past['scheduledDays']==4
exam_day=success(d,now+timedelta(days=8),'2026-11-11')
assert exam_day['scheduledDays']==1
assert effective_due(d,now+timedelta(days=11),POLICY,'2026-11-16')=='2026-11-11'
assert effective_due(d,now+timedelta(days=11),POLICY,None)==d['due']
assert effective_due(d,now+timedelta(days=11),POLICY,'2026-11-09')==d['due']
old=transition(empty,'independent',False,now,LEGACY_POLICY)
old=transition(old,'independent',False,now+timedelta(days=1),LEGACY_POLICY)
assert old['due']=='2026-11-07' and old['scheduledDays']==3
for mutate in [lambda p:p.update(day_hour=True),lambda p:p.update(success_growth=float('nan')),
               lambda p:p.update(partial_factor=1),lambda p:p.update(max_days=0),lambda p:p.update(exam_fraction=0)]:
    invalid=deepcopy(POLICY);mutate(invalid)
    try:validate_policy(invalid)
    except ValueError:pass
    else:raise AssertionError('Invalid policy accepted')
assert validate_policy(LEGACY_POLICY)==LEGACY_POLICY
edge=datetime(2026,11,3,19,tzinfo=UTC)
event={'id':'before-4','revision':'v1','kind':'reveal','at':edge-timedelta(seconds=1),
       'payload':{'direction_id':'D1','task_id':'task1','attempted':True,'policy':POLICY}}
doc=document();available={'task1','task2','task3'}
assert summary(doc,[event],available,edge-timedelta(seconds=1),POLICY)['newToday']==1
after=summary(doc,[event],available,edge,POLICY)
assert after['newToday']==0 and after['learned']==1
assert day_start(edge,POLICY)==edge
# Reclassify a 06:00 assessment under the new 04:00 activity day, even if its stored
# policy used 09:00. Its old 'lastDay' must not trigger another same-day review.
mixed=[]
six=datetime(2026,11,3,21,tzinfo=UTC)
for i in (1,2,3):
    for kind in ('reveal','rate'):
        mixed.append({'id':f'{kind}{i}','revision':'v1','kind':kind,'at':six,
          'payload':{'direction_id':f'D{i}','task_id':f'task{i}','attempted':True,'grade':'independent','helped':False,'policy':LEGACY_POLICY}})
assert plan(doc,mixed,available,six+timedelta(hours=1),POLICY)['tasks']==[]
# Undo changes the derived interval, while retaining all source events.
no_exam=deepcopy(doc);no_exam['exam_date']=None
history=[{'id':f'g{i}','revision':'v1','kind':'rate','at':now+timedelta(days=offset),
    'payload':{'direction_id':'D1','grade':'independent','helped':False,'policy':POLICY}}
    for i,offset in enumerate([0,1,3])]
history.append({'id':'undo-last','revision':'v1','kind':'undo','at':now+timedelta(days=3,minutes=1),'payload':{'undo':'g2'}})
saved=deepcopy(history)
_,restored=replay(no_exam,history,now+timedelta(days=3,minutes=2),POLICY)
assert restored['D1']['baseDays']==2 and history==saved
history.append({'id':'next','revision':'v1','kind':'rate','at':now+timedelta(days=5),
    'payload':{'direction_id':'D1','grade':'independent','helped':False,'policy':POLICY}})
_,restored=replay(no_exam,history,now+timedelta(days=5,minutes=1),POLICY)
assert restored['D1']['baseDays']==8
# A partial result with a derived four-day interval must not be forced back tomorrow.
single=deepcopy(no_exam);single['adopted_target_ids']=['T2'];single['tasks']=[single['tasks'][2]];single['prerequisites']=[]
partial_history=[{'id':'first','revision':'v1','kind':'reveal','at':now,
    'payload':{'direction_id':'D3','task_id':'task3','attempted':True,'policy':POLICY}}]
for i,(offset,grade) in enumerate([(0,'independent'),(1,'independent'),(3,'independent'),(7,'independent'),(15,'partial')]):
    partial_history.append({'id':f'p{i}','revision':'v1','kind':'rate','at':now+timedelta(days=offset),
        'payload':{'direction_id':'D3','task_id':'task3','grade':grade,'helped':False,'policy':POLICY}})
assert plan(single,partial_history,{'task3'},now+timedelta(days=16),POLICY)['tasks']==[]
assert len(plan(single,partial_history,{'task3'},now+timedelta(days=19),POLICY)['tasks'])==1
print('PASS: selected 04:00 adaptive policy, elapsed-time success, partial/help/failure, no same-day gain, exam pressure without drifting, legacy preservation, invalid config, daily counts and mixed policy days')
