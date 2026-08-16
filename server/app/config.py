from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


if not os.getenv("DATABASE_URL"):
    load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _csv(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(name, default).split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    environment: str
    local_test_mode: bool
    local_storage_dir: str
    database_url: str
    supabase_url: str
    supabase_jwt_audience: str
    supabase_jwt_secret: str
    r2_endpoint_url: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str
    runner_token: str
    admin_emails: tuple[str, ...]
    cors_allowed_origins: tuple[str, ...]
    public_api_base_url: str
    signed_url_ttl: int
    max_upload_mb: int

    @property
    def supabase_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    environment = os.getenv("ENVIRONMENT", "development").strip().lower()
    local_test_mode = environment == "local-test"

    def _storage(name: str) -> str:
        # In local-test mode R2 is replaced by a directory on disk, so demanding
        # real credentials would make the first run impossible.
        return os.getenv(name, "").strip() if local_test_mode else _required(name)

    return Settings(
        environment=environment,
        local_test_mode=local_test_mode,
        local_storage_dir=os.getenv("STUDYEZ_LOCAL_STORAGE_DIR", "local_test_data/storage").strip(),
        database_url=_required("DATABASE_URL"),
        supabase_url=os.getenv("SUPABASE_URL", "").strip() if local_test_mode else _required("SUPABASE_URL"),
        supabase_jwt_audience=os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated").strip(),
        supabase_jwt_secret=os.getenv("SUPABASE_JWT_SECRET", "").strip(),
        r2_endpoint_url=_storage("R2_ENDPOINT_URL"),
        r2_access_key_id=_storage("R2_ACCESS_KEY_ID"),
        r2_secret_access_key=_storage("R2_SECRET_ACCESS_KEY"),
        r2_bucket_name=_storage("R2_BUCKET_NAME"),
        # The local runner authenticates with this instead of a Supabase session:
        # it is a script, not a person, and it only ever writes.
        runner_token=os.getenv("RUNNER_TOKEN", "").strip() if local_test_mode else _required("RUNNER_TOKEN"),
        # Bootstrap: these addresses get is_admin on first sign-in. After that the
        # flag lives in the database and this list can shrink.
        admin_emails=tuple(email.lower() for email in _csv("STUDYEZ_ADMIN_EMAILS")),
        cors_allowed_origins=_csv(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ),
        public_api_base_url=os.getenv("PUBLIC_API_BASE_URL", "").strip().rstrip("/"),
        # Third-party material. Long-lived links are the thing we are avoiding, so
        # this stays in minutes rather than hours.
        signed_url_ttl=max(60, int(os.getenv("STUDYEZ_SIGNED_URL_TTL", "300"))),
        max_upload_mb=max(1, int(os.getenv("STUDYEZ_MAX_UPLOAD_MB", "200"))),
    )
