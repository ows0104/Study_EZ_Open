from tests.root_support import setup,publish,start,action,BASE
client,user,SessionLocal=setup()
from app.models import Profile
with SessionLocal() as db:
    db.add(Profile(id='a',email='a@example.com',is_admin=False));db.commit()
publish(client,user);sid=start(client)
assert action(client,sid,'attempt','reveal',attempted=True,response='Private draft').status_code==200
assert action(client,sid,'grade','rate',grade='partial').status_code==200
assert action(client,sid,'undo','undo').status_code==200
user('admin',True)
r=client.get('/api/admin/usage/a');assert r.status_code==200,r.text
activities=r.json()['lectures'][0]['activities']
assert activities['root_start']['count']==1 and activities['root_attempt']['count']==1
assert activities['root_rate']['count']==1 and activities['root_undo']['count']==1
assert 'Private draft' not in r.text
user('a');assert client.get('/api/admin/usage/a').status_code==403
print('PASS: confirmed starts/attempts/ratings/undos counted separately and private response never appears in usage')
