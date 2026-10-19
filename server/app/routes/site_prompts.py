"""기본 예습 링크를 만들 때 사용하는 공통 문구. 읽기와 쓰기 모두 관리자 전용."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_admin
from app.database import get_db
from app.models import SitePrompt

router = APIRouter()
KEY = "shared-preview"


class PromptIn(BaseModel):
    # 빈 값은 웹의 기본 문구로 복원한다.
    prompt: str = Field(max_length=20000)


@router.get("/preview-prompt")
def read_prompt(
    user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db),
) -> dict[str, str]:
    row = db.get(SitePrompt, KEY)
    return {"prompt": row.prompt if row else ""}


@router.put("/preview-prompt")
def write_prompt(
    payload: PromptIn,
    user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db),
) -> dict[str, str]:
    # 한 개의 key에 대해 동시 최초 저장도 원자적으로 처리한다.
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    insert = sqlite_insert if db.get_bind().dialect.name == "sqlite" else pg_insert
    value = payload.prompt.strip()
    statement = insert(SitePrompt).values(key=KEY, prompt=value)
    db.execute(statement.on_conflict_do_update(index_elements=[SitePrompt.key], set_={"prompt": value}))
    db.commit()
    return {"prompt": value}
