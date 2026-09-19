"""내가 누구인가. 로그인 직후 화면이 무엇을 그릴지 정하는 값이다.

승인 게이트(`require_approved_user`)를 지나지 **않는다.** 승인 대기 중인
사람도 자기 상태는 알아야 "승인을 기다려 주세요"를 볼 수 있기 때문이다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user, require_approved_user
from app.database import get_db
from app.models import Profile

router = APIRouter()


@router.get("/me")
def read_me(user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "isAdmin": user.is_admin,
        "isApproved": user.is_approved,
    }


class PreviewPromptIn(BaseModel):
    prompt: str


@router.get("/me/preview-prompt")
def read_preview_prompt(
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """예습을 시작할 때 AI에 보낼 프롬프트.

    빈 문자열이면 "아직 안 고쳤다"는 뜻이고 화면이 기본값을 쓴다. 여기서 기본
    문구를 돌려주지 않는 이유가 그것이다 — 돌려주면 저장한 적 없는 사람도
    그 시점의 문구를 든 것이 되어, 기본이 바뀌어도 안 따라온다.
    """
    profile = db.get(Profile, user.id)
    return {"prompt": profile.preview_prompt if profile else ""}


@router.put("/me/preview-prompt")
def write_preview_prompt(
    payload: PreviewPromptIn,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    profile = db.get(Profile, user.id)
    if profile is None:
        profile = Profile(id=user.id, email=user.email)
        db.add(profile)
    # 빈 문자열로 저장하는 것이 곧 "기본값으로 되돌리기"다.
    profile.preview_prompt = payload.prompt.strip()
    db.commit()
    return {"prompt": profile.preview_prompt}
