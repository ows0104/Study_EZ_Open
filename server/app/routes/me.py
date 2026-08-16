"""내가 누구인가. 로그인 직후 화면이 무엇을 그릴지 정하는 값이다.

승인 게이트(`require_approved_user`)를 지나지 **않는다.** 승인 대기 중인
사람도 자기 상태는 알아야 "승인을 기다려 주세요"를 볼 수 있기 때문이다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user

router = APIRouter()


@router.get("/me")
def read_me(user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "isAdmin": user.is_admin,
        "isApproved": user.is_approved,
    }
