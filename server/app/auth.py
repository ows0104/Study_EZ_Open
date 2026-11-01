"""Supabase가 로그인시키고 우리는 검증만 한다.

비밀번호 해시도, 재설정 메일도, 세션 회전도 만들지 않는다. 여기 있는 것은 토큰
검증과 「누가 어느 앱에 들어갈 수 있나」 둘뿐이다.

문은 **앱마다 다르다**(`require_app`). 전에는 `profile.is_approved` 불리언
하나가 그 일을 했고, 이름은 전역인데 뜻은 Study_EZ 전용이었다.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.orm import Session, load_only

from app.config import get_settings
from app.database import get_db
from app.models import (
    APP_POLICY,
    APP_STUDYEZ,
    POLICY_AUTO,
    ROLE_ADMIN,
    ROLE_MEMBER,
    AppGrant,
    Profile,
)

bearer_scheme = HTTPBearer(auto_error=False)

LOCAL_TEST_USER_ID = "00000000-0000-0000-0000-000000000001"
LOCAL_TEST_EMAIL = "local-test@studyez.local"


@dataclass
class CurrentUser:
    """지금 요청을 보낸 사람.

    `apps`는 이 사람이 들어갈 수 있는 앱과 그 안에서의 역할이다(`app_grant`).
    `is_admin`은 그것과 별개인 **플랫폼** 관리자다 — 앱을 더해도 안 갈라진다.

    `frozen`을 뗀 것은 `require_app`이 자동 정책 앱의 권한을 그 자리에서
    발급하고 `apps`에 반영하기 때문이다.
    """

    id: str
    email: str
    is_admin: bool
    apps: dict[str, str] = field(default_factory=dict)

    @property
    def is_approved(self) -> bool:
        """Study_EZ를 볼 수 있나. **옛 이름이다.**

        `profile.is_approved` 불리언이 하던 일이 `app_grant`로 옮겨 갔지만,
        이 이름을 부르는 자리(`/api/me`, `require_approved_user`, 관리자 화면)가
        여럿이라 뜻을 그대로 둔 채 계산으로 바꿨다.
        """
        return APP_STUDYEZ in self.apps


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
        return CurrentUser(
            id=LOCAL_TEST_USER_ID,
            email=LOCAL_TEST_EMAIL,
            is_admin=True,
            apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN),
        )

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

    profile = db.get(Profile, user_id, options=[load_only(Profile.id, Profile.email, Profile.is_admin)])
    if profile is None:
        # 첫 로그인에서만 환경 변수를 본다. 그 뒤로는 DB의 값이 사실이다.
        is_admin = bool(email) and email.lower() in settings.admin_emails
        profile = Profile(id=user_id, email=email, is_admin=is_admin)
        db.add(profile)
        db.flush()
        if is_admin:
            # 관리자는 스스로를 승인할 사람이 없으므로 자동으로 통과시킨다.
            # 안 그러면 첫 배포에서 아무도 /admin에 못 들어간다.
            db.add(AppGrant(user_id=user_id, app=APP_STUDYEZ, role=ROLE_ADMIN))
        db.commit()
    elif email and profile.email != email:
        profile.email = email
        db.commit()

    apps = {
        app: role
        for app, role in db.execute(select(AppGrant.app, AppGrant.role).where(AppGrant.user_id == user_id))
    }
    return CurrentUser(id=user_id, email=email, is_admin=profile.is_admin, apps=apps)


def require_app(app: str, role: str | None = None) -> Callable[..., CurrentUser]:
    """이 앱에 들어갈 수 있는가. **형제 앱이 갈리는 유일한 자리다.**

    앱마다 문이 다르다는 것을 여기 한 곳에 모았다(`APP_POLICY`). 자동 정책인
    앱은 처음 들어올 때 권한을 그 자리에서 발급한다 — 「로그인하면 열린다」를
    표에도 남겨서, 나중에 그 사람을 막아야 할 때 지울 줄이 있게 한다.

    수동 정책인 앱은 사람이 `/admin`에서 준다. 가입은 누구나 하지만 강의
    자료는 그것만으로 열리면 안 되기 때문이다.
    """

    def dependency(
        user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
    ) -> CurrentUser:
        granted = user.apps.get(app)
        if granted is None and APP_POLICY.get(app) == POLICY_AUTO:
            db.add(AppGrant(user_id=user.id, app=app, role=ROLE_MEMBER))
            db.commit()
            granted = ROLE_MEMBER
            user.apps[app] = granted
        if granted is None:
            raise HTTPException(
                status_code=403,
                detail={"code": "pending_approval", "message": "승인 대기 중입니다."},
            )
        # 플랫폼 관리자는 앱 안의 역할과 무관하게 지난다. 관리자가 하나뿐이라
        # 앱마다 자기에게 역할을 주게 하는 것은 절차만 늘린다.
        if role == ROLE_ADMIN and granted != ROLE_ADMIN and not user.is_admin:
            raise HTTPException(status_code=403, detail="권한이 없습니다.")
        return user

    return dependency


# 옛 이름. `lectures`·`prequiz`·`me`가 이것을 부르고 있어서 그대로 둔다 —
# 뜻은 「Study_EZ에 들어갈 수 있는가」로 처음부터 같았다.
require_approved_user = require_app(APP_STUDYEZ)


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
