"""Four free self-ratings, exposure kept separately, old requests unchanged."""
from copy import deepcopy
from datetime import timedelta
from tests.root_support import setup,publish,start,view,action,NOW,POLICY,LEGACY_POLICY
from app.root_learning.policy import transition
client,user,SessionLocal=setup();publish(client,user)
from app.models.root_learning import RootEvent

for i,rating in enumerate(('Again','Hard','Good','Easy')):
    user('four-'+str(i));sid=start(client,'start-'+str(i))
    assert action(client,sid,'map-'+str(i),'map').status_code==200
    assert action(client,sid,'reveal-'+str(i),'reveal',attempted=False).status_code==200
    assert view(client,sid)['task']['helped']
    request={'requestId':'rate-'+str(i),'version':view(client,sid)['version'],'kind':'rate','selfRating':rating}
    url='/api/root-learning/sessions/'+sid+'/events'
    result=client.post(url,json=request);assert result.status_code==200,result.text
    assert client.post(url,json=request).json()==result.json()
    assert view(client,sid)['position']==1
    with SessionLocal()as db:
        event=db.get(RootEvent,('four-'+str(i),'rate-'+str(i)))
        assert event.payload['selfRating']==rating and event.payload['helped']
        assert event.payload['ratingPolicy']=='roots-four-rating/2' and event.payload['targetParameters']['maxTarget']==0.9
        assert event.payload['ratingParameters']['growth']['Easy']==3
        saved=deepcopy(event.payload)
    assert action(client,sid,'undo-'+str(i),'undo').status_code==200
    assert view(client,sid)['position']==0
    with SessionLocal()as db:assert db.get(RootEvent,('four-'+str(i),'rate-'+str(i))).payload==saved

user('old-client');sid=start(client)
assert action(client,sid,'old-reveal','reveal',attempted=False).status_code==200
assert action(client,sid,'old-reject','rate',grade='independent').status_code==422
user('unrevealed');sid=start(client)
assert action(client,sid,'before-answer','rate',selfRating='Good').status_code==409
assert action(client,sid,'invalid','rate',selfRating='Other').status_code==422

empty={'stage':-1,'lastDay':None,'rating':None}
good=transition(empty,'independent',False,NOW,POLICY,None,'Good')
easy=transition(empty,'independent',False,NOW,POLICY,None,'Easy')
assert good['scheduledDays']==1 and easy['scheduledDays']==2
later=transition(easy,'independent',False,NOW+timedelta(days=2),POLICY,None,'Easy')
assert later['baseDays']==6
helped=transition(empty,'independent',True,NOW,POLICY,None,'Good')
assert helped['rating']=='partial' and helped['selfRating']=='Good'
old=transition(empty,'independent',False,NOW,LEGACY_POLICY)
assert old['scheduledDays']==1 and 'selfRating' not in old
mixed=transition(later,'partial',False,NOW+timedelta(days=8),POLICY)
assert 'ratingDays' not in mixed and 'selfRating' not in mixed
print('PASS: all four ratings after map/answer-only, exact retries, retained events/undo, old guards and distinct new spacing')
