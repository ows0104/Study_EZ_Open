"""R2. 파일은 서명 URL로만 나가고 그 수명은 분 단위다.

작년 필기와 족보는 제3자 저작물이다. 공개 URL로 서빙하지 않는다는 것이 이
모듈의 존재 이유이므로, 여기에 "그냥 링크를 준다"는 경로는 없다.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import get_settings


class ObjectStorage:
    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.r2_bucket_name
        self.local_root = Path(settings.local_storage_dir).resolve() if settings.local_test_mode else None
        if self.local_root is not None:
            self.local_root.mkdir(parents=True, exist_ok=True)
            self.client = None
            return
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )

    def presign_upload(self, key: str, *, content_type: str, expires_in: int = 900) -> str:
        if self.local_root is not None:
            return f"{get_settings().public_api_base_url}/api/local-storage/{quote(key, safe='/')}"
        return self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )

    def presign_download(self, key: str, *, filename: str | None = None, expires_in: int | None = None) -> str:
        settings = get_settings()
        expires_in = expires_in or settings.signed_url_ttl
        if self.local_root is not None:
            return f"{settings.public_api_base_url}/api/local-storage/{quote(key, safe='/')}"
        params: dict[str, Any] = {"Bucket": self.bucket, "Key": key}
        if filename:
            # 한글 파일명은 헤더에 그대로 못 들어간다. ASCII 사본과 RFC 5987
            # 형식을 함께 실어야 브라우저마다 다르게 깨지는 것을 막는다.
            ascii_name = filename.encode("ascii", "ignore").decode("ascii").strip().replace('"', "")
            params["ResponseContentDisposition"] = (
                f'attachment; filename="{ascii_name or "studyez"}"; '
                f"filename*=UTF-8''{quote(filename, safe='')}"
            )
        return self.client.generate_presigned_url("get_object", Params=params, ExpiresIn=expires_in)

    def head(self, key: str) -> dict[str, Any] | None:
        if self.local_root is not None:
            path = self.local_path(key)
            return {"ContentLength": path.stat().st_size} if path.is_file() else None
        try:
            return self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if str(exc.response.get("Error", {}).get("Code", "")) in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise

    def upload_fileobj(self, fileobj, key: str, *, content_type: str) -> None:
        if self.local_root is not None:
            destination = self.local_path(key)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("wb") as handle:
                shutil.copyfileobj(fileobj, handle)
            return
        self.client.upload_fileobj(fileobj, self.bucket, key, ExtraArgs={"ContentType": content_type})

    def delete(self, key: str) -> None:
        if self.local_root is not None:
            self.local_path(key).unlink(missing_ok=True)
            return
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def put_bytes(self, key: str, content: bytes) -> None:
        if self.local_root is None:
            raise RuntimeError("Local storage is not enabled")
        destination = self.local_path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    def local_path(self, key: str) -> Path:
        if self.local_root is None:
            raise RuntimeError("Local storage is not enabled")
        candidate = (self.local_root / key.replace("\\", "/")).resolve()
        if candidate != self.local_root and self.local_root not in candidate.parents:
            raise ValueError("Invalid local storage key")
        return candidate
