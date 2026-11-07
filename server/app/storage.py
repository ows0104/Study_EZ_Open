"""R2. 파일은 서명 URL로 나간다.

버킷이 비공개이므로 서명이 곧 접근 수단이다. 공개 버킷으로 바꾸면 로그인을
지나지 않고도 파일이 열리게 되고, 그러면 "로그인 필수"가 화면에만 걸린 말이
된다. 수명은 `STUDYEZ_SIGNED_URL_TTL`이 정하고 기본은 한 시간이다.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import get_settings


class StorageNotConfigured(RuntimeError):
    """R2가 아직 없다. 파일 경로만 잠기고 나머지 화면은 그대로 돈다."""


class ObjectStorage:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.storage_configured:
            raise StorageNotConfigured("R2가 아직 설정되지 않았습니다.")
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

    def presign_download(
        self,
        key: str,
        *,
        filename: str | None = None,
        inline: bool = False,
        content_type: str | None = None,
        expires_in: int | None = None,
    ) -> str:
        """서명된 GET URL.

        `inline`은 브라우저에게 받지 말고 열라는 뜻이다. 필기 PDF를 내려받지
        않고 새 탭에서 바로 읽으려고 있다. 이때는 저장된 content type도 같이
        덮어쓴다 — 올릴 때 `application/octet-stream`으로 들어간 것이 있으면
        `inline`을 줘도 브라우저가 뷰어 대신 저장 창을 연다.
        """
        settings = get_settings()
        expires_in = expires_in or settings.signed_url_ttl
        if self.local_root is not None:
            url = f"{settings.public_api_base_url}/api/local-storage/{quote(key, safe='/')}"
            # 배포에서는 `filename`이 붙은 것만 첨부(attachment)로 나간다. 로컬도
            # 같아야 한다 — 안 그러면 .apkg가 text/plain으로 화면에 펼쳐진다.
            # 슬라이드 이미지는 filename 없이 부르므로 그대로 인라인이다.
            if not filename:
                return url
            key_name = "inline" if inline else "download"
            return f"{url}?{key_name}={quote(filename, safe='')}"
        params: dict[str, Any] = {"Bucket": self.bucket, "Key": key}
        if filename:
            # 한글 파일명은 헤더에 그대로 못 들어간다. ASCII 사본과 RFC 5987
            # 형식을 함께 실어야 브라우저마다 다르게 깨지는 것을 막는다.
            ascii_name = filename.encode("ascii", "ignore").decode("ascii").strip().replace('"', "")
            params["ResponseContentDisposition"] = (
                f'{"inline" if inline else "attachment"}; filename="{ascii_name or "studyez"}"; '
                f"filename*=UTF-8''{quote(filename, safe='')}"
            )
        if inline and content_type:
            params["ResponseContentType"] = content_type
        return self.client.generate_presigned_url("get_object", Params=params, ExpiresIn=expires_in)

    def get_bytes(self, key: str) -> bytes | None:
        """객체를 통째로 읽는다. 서버가 내용을 봐야 하는 것에만 쓴다.

        파일은 원칙적으로 서명 URL로 나간다 — 바이트가 서버를 지나가지 않는
        것이 이 앱에서 Cloud Run이 싼 이유다. 예외는 **서버가 그 내용을
        가공해서 내보내는 것**뿐이고, 지금은 땡시 문항 DB 하나다(gzip으로
        줄여서 ETag와 함께 낸다. 서명 URL은 매번 주소가 달라 브라우저 캐시가
        안 듣는다).
        """
        if self.local_root is not None:
            path = self.local_path(key)
            return path.read_bytes() if path.is_file() else None
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as exc:
            if str(exc.response.get("Error", {}).get("Code", "")) in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise

    def open_stream(self, key: str, *, chunk_size: int = 1 << 20,
                    byte_range: tuple[int, int] | None = None) -> tuple[Iterator[bytes], int] | None:
        """객체를 조각으로 흘려 보낸다. `(조각들, 바이트 수)` — 없으면 `None`.

        **`get_bytes` 와 달리 통째로 안 올린다.** 덱 하나가 200MB 까지 가는데
        (`실습` 편), Cloud Run 은 `--memory 512Mi` 다. 조각으로 흘리면 그 값과
        상관없이 지나간다.

        바이트가 서버를 지나가는 자리가 여기 하나 더 생겼다. 원래는 서명 URL로
        R2 에서 곧바로 받는데, **브라우저가 `fetch` 로 읽으려면 R2 쪽에 CORS 가
        있어야 하고 지금은 없다**(2026-09-15 실측 — 서명 GET 에
        `Access-Control-Allow-Origin` 이 안 붙는다. `<img>`·`<a>` 는 CORS 를 안
        타므로 지금까지 걸리지 않았다). 버킷에 CORS 규칙이 붙으면 이 자리는
        없어져도 된다 — 그때는 `routes/bundles.py` 가 서명 URL 을 주면 된다.
        Main-Quiz 참고 PDF(`routes/root_learning.py`)도 같은 사정으로 여기를 지난다.

        `byte_range=(처음, 끝)`은 양끝을 포함한 바이트 범위다(HTTP Range와 같다).
        호출하는 쪽이 `head`로 크기를 확인해 범위가 파일 안에 있음을 보장한다.
        돌려주는 바이트 수는 그 범위의 길이다.
        """
        if self.local_root is not None:
            path = self.local_path(key)
            if not path.is_file():
                return None
            start, end = byte_range or (0, path.stat().st_size - 1)

            def _file_chunks() -> Iterator[bytes]:
                with path.open("rb") as handle:
                    handle.seek(start)
                    left = end - start + 1
                    while left > 0 and (chunk := handle.read(min(chunk_size, left))):
                        left -= len(chunk)
                        yield chunk

            return _file_chunks(), max(0, end - start + 1)
        try:
            extra = {"Range": f"bytes={byte_range[0]}-{byte_range[1]}"} if byte_range else {}
            answer = self.client.get_object(Bucket=self.bucket, Key=key, **extra)
        except ClientError as exc:
            if str(exc.response.get("Error", {}).get("Code", "")) in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        return answer["Body"].iter_chunks(chunk_size), int(answer["ContentLength"])

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
