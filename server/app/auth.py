"""Supabase가 로그인시키고 우리는 검증만 한다.

비밀번호 해시도, 재설정 메일도, 세션 회전도 만들지 않는다. 여기 있는 것은 토큰
검증과 `is_admin` 불리언 하나뿐이다.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Profile


bearer_scheme = HTTPBearer(auto_error=False)

LOCAL_TEST_USER_ID = "00000000-0000-0000-0000-000000000001"
LOCAL_TEST_EMAIL = "local-test@studyez.local"


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str
    is_admin: bool


@lru_cache(maxsize=1)
def _jwk_client() -> PyJWKClient:
    return PyJWKClient(get_settings().supabase_jwks_url, cache_jwk_set=True, lifespan=300)


def _decode(token: str) -> dict:
    settings = get_settings()
    common = {
        "audience": settings.supabase_jwt_audience,
        "issuer": settings.supabase_issuer,
        "options": {"require": ["exp", "sub"]},
    }
    if settings.supabase_jwt_secret:
        return jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"], **common)
    signing_key = _jwk_client().get_signing_key_from_jwt(token)
    return jwt.decode(token, signing_key.key, algorithms=["RS256", "ES256"], **common)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    settings = get_settings()
    if settings.local_test_mode:
        if credentials is None or credentials.credentials != "local-test-token":
            raise HTTPException(status_code=401, detail="로컬 테스트 토큰이 필요합니다.")
        return CurrentUser(id=LOCAL_TEST_USER_ID, email=LOCAL_TEST_EMAIL, is_admin=True)

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    try:
        payload = _decode(credentials.credentials)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="로그인 정보가 유효하지 않습니다.") from exc

    user_id = str(payload.get("sub", "")).strip()
    email = str(payload.get("email", "")).strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="로그인 정보가 유효하지 않습니다.")

    profile = db.get(Profile, user_id)
    if profile is None:
        profile = Profile(
            id=user_id,
            email=email,
            # 첫 로그인에서만 환경 변수를 본다. 그 뒤로는 DB의 값이 사실이다.
            is_admin=bool(email) and email.lower() in settings.admin_emails,
        )
        db.add(profile)
        db.commit()
    elif email and profile.email != email:
        profile.email = email
        db.commit()

    return CurrentUser(id=user_id, email=email, is_admin=profile.is_admin)


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="관리자만 쓸 수 있습니다.")
    return user


def require_runner(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """산출물을 밀어 넣는 쪽. 로컬 러너의 공유 토큰이거나 관리자 세션이다.

    러너는 사람이 아니라 스크립트라서 Supabase 세션이 없다. 사람이 `/admin`
    화면에서 같은 일(예습 링크 입력 등)을 하기도 하므로 두 갈래를 다 받는다.
    """
    settings = get_settings()
    token = credentials.credentials if credentials else ""
    if settings.runner_token and token and secrets.compare_digest(token, settings.runner_token):
        return CurrentUser(id="runner", email="", is_admin=True)
    return require_admin(get_current_user(credentials, db))
