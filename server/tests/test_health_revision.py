"""Public health reports only the nonsecret deployed commit, preserving existing fields."""
import os
import tempfile
from pathlib import Path

os.environ.update(ENVIRONMENT='local-test', DATABASE_URL='sqlite:///' +
                  (Path(tempfile.mkdtemp()) / 'health.db').as_posix(), STUDYEZ_REVISION='a' * 40)

from fastapi.testclient import TestClient
from app.main import app

if __name__ == '__main__':
    client = TestClient(app)
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'environment': 'local-test', 'revision': 'a' * 40}
    os.environ.pop('STUDYEZ_REVISION')
    assert client.get('/api/health').json()['revision'] == ''
    print('PASS health commit and backward-compatible local default')
