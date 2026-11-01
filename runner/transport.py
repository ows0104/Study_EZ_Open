"""HTTP API and signed-file transport. No generation, planning, or job state."""
from __future__ import annotations

import json
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# --api or STUDYEZ_API_BASE_URL can override this deployed API address.
DEFAULT_API_BASE = "https://studyez-api-97999573571.asia-northeast3.run.app"


# Signed uploads must send the same Content-Type as their upload manifest.
CONTENT_TYPES = {".pdf": "application/pdf", ".png": "image/png", ".md": "text/markdown"}


DEFAULT_CONTENT_TYPE = "application/octet-stream"


UPLOAD_RETRIES = 3


class PublishError(RuntimeError):
    """서버가 거절했거나 연결이 끊겼다. 어느 요청이었는지까지 담는다."""


def content_type(path: Path) -> str:
    return CONTENT_TYPES.get(path.suffix.lower(), DEFAULT_CONTENT_TYPE)


@dataclass(frozen=True)
class Upload:
    """올릴 파일 하나. `kind`는 계약의 다섯 가지뿐이다."""

    kind: str
    path: Path

    @property
    def filename(self) -> str:
        # Synology 파일명 일부가 NFD다. 서버도 NFC로 모으지만 여기서 맞춰 두어야
        # 표시(`published.json`)와 서버의 키가 같은 문자열이 된다.
        return unicodedata.normalize("NFC", self.path.name)

    @property
    def size(self) -> int:
        return self.path.stat().st_size

    @property
    def mtime(self) -> int:
        return int(self.path.stat().st_mtime)

    @property
    def key(self) -> str:
        return f"{self.kind}/{self.filename}"

    def payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "filename": self.filename,
            "sizeBytes": self.size,
            "contentType": content_type(self.path),
        }


class Client:
    """러너 토큰으로 부르는 API. 실패는 삼키지 않는다."""

    def __init__(self, base: str, token: str, timeout: int = 600) -> None:
        self.base = base.rstrip("/")
        self.token = token
        self.timeout = timeout

    def call(self, method: str, path: str, payload: Any = None) -> Any:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            f"{self.base}{path}",
            data=data,
            method=method,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        return self._open(request)

    def put_file(self, url: str, path: Path) -> None:
        """서명 URL에 파일 본문을 민다.

        content-type이 서명에 들어 있으므로 발급 때 적어 보낸 값과 **같은 헤더**를
        달아야 한다. Content-Length도 직접 넣는다 — 파일 객체를 주면 urllib이
        길이를 모르고 chunked로 보내는데 R2가 그걸 서명과 함께 받지 않는다.

        주소가 상대 경로로 올 수 있다. local-test 모드에서 R2 대신 서버 자신이
        파일을 받는데, `PUBLIC_API_BASE_URL`이 비어 있으면 `/api/local-storage/…`
        만 온다. 같은 서버가 받을 자리이므로 API 주소에 이어 붙인다.
        """
        size = path.stat().st_size
        with path.open("rb") as handle:
            request = urllib.request.Request(
                urllib.parse.urljoin(f"{self.base}/", url),
                data=handle,
                method="PUT",
                headers={"Content-Type": content_type(path), "Content-Length": str(size)},
            )
            self._open(request, parse=False)

    def _open(self, request: urllib.request.Request, parse: bool = True) -> Any:
        where = f"{request.get_method()} {request.full_url.split('?')[0]}"
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace").strip()[:300]
            raise PublishError(f"{exc.code} {where} — {detail}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise PublishError(f"{where} 실패 — {exc}") from exc
        return json.loads(body) if parse and body else None


def lecture_path(subject: str, run_id: str, tail: str = "") -> str:
    quoted = urllib.parse.quote(unicodedata.normalize("NFC", subject), safe="")
    return f"/api/admin/lectures/{quoted}/{urllib.parse.quote(run_id, safe='')}{tail}"


def _put_with_retry(client: Client, url: str, upload: Upload) -> None:
    """끊긴 업로드는 다시 시도한다. 30~56MB짜리가 한 번 튄다고 편을 버리지 않는다."""
    for attempt in range(1, UPLOAD_RETRIES + 1):
        try:
            client.put_file(url, upload.path)
            return
        except PublishError:
            if attempt == UPLOAD_RETRIES:
                raise
            time.sleep(2 * attempt)
