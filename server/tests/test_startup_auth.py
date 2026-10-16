"""Every API authenticates without reading stored prompt bodies or caching revoked grants."""
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="studyez-startup-auth-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}")

from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import delete, event

from app.auth import APP_STUDYEZ, ROLE_MEMBER, get_current_user
from app.database import Base, SessionLocal, engine
from app.models import AppGrant, Profile


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Profile(id="one", email="old@example.com", preview_prompt="large preview" * 100_000,
                       review_prompt="large review" * 100_000, is_admin=True))
        db.add(AppGrant(user_id="one", app=APP_STUDYEZ, role=ROLE_MEMBER))
        db.commit()
    captured = []
    def observe(conn, cursor, statement, parameters, context, executemany):
        captured.append(statement.lower())
    event.listen(engine, "before_cursor_execute", observe)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="synthetic-local-token")
    with patch("app.auth.get_settings", return_value=SimpleNamespace(local_test_mode=False, admin_emails=set())), \
         patch("app.auth._decode", return_value={"sub": "one", "email": "new@example.com"}):
        with SessionLocal() as db:
            user = get_current_user(credentials, db)
            assert user.is_admin and user.is_approved and user.email == "new@example.com"
        assert not any("preview_prompt" in sql or "review_prompt" in sql for sql in captured)
        with SessionLocal() as db:
            db.execute(delete(AppGrant).where(AppGrant.user_id == "one"))
            db.commit()
        with SessionLocal() as db:
            assert not get_current_user(credentials, db).is_approved
    event.remove(engine, "before_cursor_execute", observe)
    with SessionLocal() as db:
        profile = db.get(Profile, "one")
        assert profile.email == "new@example.com" and profile.preview_prompt == "large preview" * 100_000
        assert profile.review_prompt == "large review" * 100_000
    print("PASS: authentication skips prompt bodies, preserves email updates and promptly reads grant revocation")


if __name__ == "__main__":
    main()
