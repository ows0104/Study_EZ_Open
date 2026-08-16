"""R2 대역. 로컬에서 화면을 굴려 보려고 있는 것이다.

서명 URL은 Authorization 헤더를 달고 오지 않으므로 이 두 경로는 나머지 API의
로그인 게이트 바깥에 있다. 대신 스스로를 막는다: local-test 모드가 아니면 아예
없는 경로이고, 산출물 접두 아래만 받는다.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.config import get_settings
from app.storage import ObjectStorage

router = APIRouter()

_ALLOWED_PREFIX = "lectures/"


def _guard(object_key: str) -> None:
    if not get_settings().local_test_mode or not object_key.startswith(_ALLOWED_PREFIX):
        raise HTTPException(status_code=404, detail="Not found")


@router.put("/local-storage/{object_key:path}")
async def local_storage_upload(object_key: str, request: Request) -> dict[str, bool]:
    _guard(object_key)
    ObjectStorage().put_bytes(object_key, await request.body())
    return {"ok": True}


@router.get("/local-storage/{object_key:path}")
def local_storage_download(object_key: str) -> FileResponse:
    _guard(object_key)
    path = ObjectStorage().local_path(object_key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path)
