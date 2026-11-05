import copy
from datetime import datetime, UTC, timedelta
from tests.root_support import document,POLICY,NOW
from app.root_learning.planning import plan
from app.root_learning.policy import study_day
from app.root_learning.state import replay, summary

doc=document();available={'task1','task2','task3'}
p=plan(doc,[],available,NOW,POLICY)
assert p['newGoalQuota']==1 and [x['task_id'] for x in p['tasks']]==['task1','task2','task3']
assert p['habitualTasks'] is None and p['unpreparedGoals']==1
assert p==plan(doc,[],available,NOW,POLICY)
assert plan(doc,[],set(),NOW,POLICY)['tasks']==[]
boundary=datetime(2026,11,2,19,tzinfo=UTC)
assert study_day(boundary-timedelta(seconds=1),POLICY).isoformat()=='2026-11-02'
assert study_day(boundary,POLICY).isoformat()=='2026-11-03'
unknown=copy.deepcopy(doc);unknown['exam_date']=None
assert plan(unknown,[],available,NOW,POLICY)['days'] is None
expired=copy.deepcopy(doc);expired['exam_date']='2026-11-02'
assert plan(expired,[],available,NOW,POLICY)['newGoalQuota']==2
events=[]
for i,did in enumerate(['D1','D2','D3']):
    events += [{'id':f'reveal{i}','kind':'reveal','revision':'v1','at':NOW,
                'payload':{'direction_id':did,'task_id':f'task{i+1}','attempted':True,'policy':POLICY}},
               {'id':f'rate{i}','kind':'rate','revision':'v1','at':NOW+timedelta(seconds=1),
                'payload':{'direction_id':did,'task_id':f'task{i+1}','grade':'independent','helped':False,'policy':POLICY}}]
assert plan(doc,events,available,NOW+timedelta(minutes=1),POLICY)['tasks']==[]
assert summary(doc,events,available,NOW+timedelta(minutes=1),POLICY)['unready']==1
due=plan(doc,events,available,NOW+timedelta(days=1),POLICY)
assert len(due['tasks'])==3 and due['newGoalQuota']==0 and due['habitualTasks']==3
failed=copy.deepcopy(events);failed[-1]['payload']['grade']='partial'
assert plan(doc,failed,available,NOW+timedelta(minutes=1),POLICY)['tasks']==[]
assert len(plan(doc,failed,available,NOW+timedelta(days=1),POLICY)['tasks'])==3
later=copy.deepcopy(events)
later.append({'id':'later','kind':'rate','revision':'v1','at':NOW+timedelta(days=1),
              'payload':{'direction_id':'D1','task_id':'task1','grade':'independent','helped':False,'policy':POLICY,'exam_date':doc['exam_date']}})
_,states=replay(doc,later,NOW+timedelta(days=1,minutes=1),POLICY)
assert states['D1']['baseDays']==2 and states['D1']['due']=='2026-11-05'
same=copy.deepcopy(later);same.append({**same[-1],'id':'same-day','at':NOW+timedelta(days=1,seconds=1)})
_,again=replay(doc,same,NOW+timedelta(days=1,minutes=1),POLICY)
assert again['D1']['baseDays']==states['D1']['baseDays'] and again['D1']['due']==states['D1']['due']
assert p['tasks']==plan(doc,[],available,NOW,POLICY)['tasks']
print('PASS: deterministic finite lists, protected new goals, explicit prerequisites, missing tasks, unknown/past exams, UTC/KST boundary, due reviews, same-day no forced repeats, activity history and intervals')
