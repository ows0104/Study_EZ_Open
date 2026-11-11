import json
import os
from datetime import UTC,datetime,timedelta
from tests.root_support import setup,publish,start,view,action,POLICY,LEGACY_POLICY,BASE
client,user,SessionLocal=setup()
publish(client,user)
os.environ['STUDYEZ_ROOT_POLICY']=json.dumps(LEGACY_POLICY)
old=start(client,'old-start')
assert action(client,old,'old-reveal','reveal',attempted=True).status_code==200
assert action(client,old,'old-rate','rate',grade='independent').status_code==200
before=view(client,old)
os.environ.pop('STUDYEZ_ROOT_POLICY')
info=client.get(BASE).json()
assert info['policyReady'] and info['policy']['mode']=='adaptive' and info['policy']['day_hour']==4
assert info['sessionId'] is None and info['summary']['learned']==1
new=start(client,'new-policy-start');assert old!=new
assert view(client,new)['policy']==POLICY
assert view(client,old)['policy']==LEGACY_POLICY and view(client,old)['position']==before['position']
from app.routes import root_learning
edge=datetime(2026,11,3,19,tzinfo=UTC)
root_learning.now=lambda:edge-timedelta(seconds=1)
assert view(client,new)['blocked'] is None
assert client.get(BASE).json()['plan']['days']==3  # 03:59 KST Nov 4 is still the Nov 3 study day (2026-11-11: days count by 04:00 study day).
root_learning.now=lambda:edge
assert view(client,new)['blocked']
assert action(client,new,'expired-at-four','skip').status_code==409
after=start(client,'after-four');assert after!=new and view(client,after)['day']=='2026-11-04'
assert view(client,old)['blocked'] is None  # Explicitly opened legacy session still has its pinned 09:00 boundary.
from app.models.root_learning import RootEvent,RootSession
with SessionLocal() as db:
    assert db.get(RootSession,old).policy==LEGACY_POLICY
    assert db.get(RootEvent,('a','old-rate')).payload['policy']==LEGACY_POLICY
    assert db.get(RootEvent,('a','old-rate')).payload['exam_date']=='2026-11-07'
print('PASS: default policy selected, policy changes create a new session, original snapshots preserved, 03:59/04:00 rollover, calendar exam vs activity day, legacy session boundary')
