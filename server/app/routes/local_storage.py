"""R2 대역. 로컬에서 화면을 굴려 보려고 있는 것이다.

서명 URL은 Authorization 헤더를 달고 오지 않으므로 이 두 경로는 나머지 API의
로그인 게이트 바깥에 있다. 대신 스스로를 막는다: local-test 모드가 아니면 아예
없는 경로이고, 산출물 접두 아래만 받는다.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from app.config import get_settings
from app.storage import ObjectStorage

router = APIRouter()

# 산출물이 사는 접두사. **여기 없는 것은 local-test에서도 안 나간다** —
# 이 경로가 로그인 게이트 바깥에 있으므로, 열어 주는 범위가 곧 이 우회로의
# 위험 범위다. `spotter/`는 기생충학 땡시의 문항 DB와 사진이다.
_ALLOWED_PREFIXES = ("lectures/", "spotter/", "jokbo-solve/")


def _guard(object_key: str) -> None:
    if not get_settings().local_test_mode or not object_key.startswith(_ALLOWED_PREFIXES):
        raise HTTPException(status_code=404, detail="Not found")


@router.put("/local-storage/{object_key:path}")
async def local_storage_upload(object_key: str, request: Request) -> dict[str, bool]:
    _guard(object_key)
    ObjectStorage().put_bytes(object_key, await request.body())
    return {"ok": True}


@router.get("/local-storage/{object_key:path}")
def local_storage_download(
    object_key: str,
    download: str | None = Query(None, description="주면 첨부로 내보낸다. R2의 ResponseContentDisposition 자리다."),
    inline: str | None = Query(None, description="주면 이름을 달되 첨부가 아니라 인라인으로 내보낸다."),
) -> FileResponse:
    _guard(object_key)
    path = ObjectStorage().local_path(object_key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    # 이름을 주면 Starlette가 Content-Disposition을 붙이고, 그 이름으로 media
    # type도 고른다. `inline`은 이름은 달되 받지 말고 열라는 쪽이다 — 필기를
    # 새 탭에서 읽는 자리가 그것이다. 둘 다 없으면 그냥 인라인이고, 슬라이드
    # 이미지가 그 쪽이다.
    if inline:
        return FileResponse(path, filename=inline, content_disposition_type="inline")
    return FileResponse(path, filename=download) if download else FileResponse(path)
