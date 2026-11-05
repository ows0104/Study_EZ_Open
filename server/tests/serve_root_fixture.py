"""Owned local browser fixture. Always a fresh isolated database and synthetic content."""
from tests.root_support import setup,publish
client,user,SessionLocal=setup()
publish(client,user)
from app.main import app
from fastapi import Request
from app.auth import CurrentUser,get_current_user,APP_POLICY,ROLE_ADMIN
def test_user(request:Request):
    uid=request.headers.get('X-Root-Test-User','a')
    return CurrentUser(id=uid,email=f'{uid}@example.com',is_admin=False,apps=dict.fromkeys(APP_POLICY,ROLE_ADMIN))
app.dependency_overrides[get_current_user]=test_user
import uvicorn
if __name__=='__main__':
    uvicorn.run(app,host='127.0.0.1',port=8027,log_level='warning')
