from __future__ import annotations

import os
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / ".runtime"
INAT_TOKEN_PATH = RUNTIME_DIR / "inat_token.json"
INAT_TOKENS_PATH = RUNTIME_DIR / "inat_tokens.json"
load_dotenv(BASE_DIR / ".env")


def load_inat_access_token(env_fallback: str = "") -> str:
    if INAT_TOKEN_PATH.exists():
        try:
            payload = json.loads(INAT_TOKEN_PATH.read_text(encoding="utf-8"))
            token = str(payload.get("api_token") or "").strip()
            if token:
                return token
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    return env_fallback.strip()


def save_inat_access_token(access_token: str) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    INAT_TOKEN_PATH.write_text(
        json.dumps({"api_token": access_token.strip()}, indent=2),
        encoding="utf-8",
    )


def build_inat_token_identity(subject: str | None, email: str | None) -> str | None:
    if subject:
        return f"sub:{str(subject).strip()}"
    if email:
        return f"email:{str(email).strip().lower()}"
    return None


def _load_inat_tokens_payload() -> dict[str, dict[str, str]]:
    if not INAT_TOKENS_PATH.exists():
        return {}
    try:
        payload = json.loads(INAT_TOKENS_PATH.read_text(encoding="utf-8"))
        tokens = payload.get("tokens") or {}
        if isinstance(tokens, dict):
            return {
                str(key): value
                for key, value in tokens.items()
                if isinstance(value, dict)
            }
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}
    return {}


def load_inat_token_record_for_user(
    *,
    subject: str | None,
    email: str | None,
) -> dict[str, Any] | None:
    identity = build_inat_token_identity(subject, email)
    tokens = _load_inat_tokens_payload()
    if identity and identity in tokens:
        return dict(tokens[identity])
    if email:
        email_identity = build_inat_token_identity(None, email)
        if email_identity and email_identity in tokens:
            return dict(tokens[email_identity])
    return None


def load_inat_access_token_for_user(
    *,
    subject: str | None,
    email: str | None,
    env_fallback: str = "",
) -> str:
    record = load_inat_token_record_for_user(subject=subject, email=email)
    if record:
        token = str(record.get("access_token") or record.get("api_token") or "").strip()
        if token:
            return token
    return env_fallback.strip()


def save_inat_access_token_for_user(
    *,
    access_token: str,
    subject: str | None,
    email: str | None,
) -> None:
    identity = build_inat_token_identity(subject, email)
    if not identity:
        save_inat_access_token(access_token)
        return
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    payload = _load_inat_tokens_payload()
    payload[identity] = {
        "subject": str(subject or "").strip(),
        "email": str(email or "").strip().lower(),
        "api_token": access_token.strip(),
    }
    INAT_TOKENS_PATH.write_text(
        json.dumps({"tokens": payload}, indent=2),
        encoding="utf-8",
    )


def save_inat_token_record_for_user(
    *,
    record: dict[str, Any],
    subject: str | None,
    email: str | None,
) -> None:
    identity = build_inat_token_identity(subject, email)
    if not identity:
        raise ValueError("Cannot save an iNaturalist token record without a user identity.")
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    payload = _load_inat_tokens_payload()
    normalized_record = dict(record)
    normalized_record["subject"] = str(subject or "").strip()
    normalized_record["email"] = str(email or "").strip().lower()
    payload[identity] = normalized_record
    INAT_TOKENS_PATH.write_text(
        json.dumps({"tokens": payload}, indent=2),
        encoding="utf-8",
    )


def delete_inat_token_record_for_user(*, subject: str | None, email: str | None) -> None:
    identity = build_inat_token_identity(subject, email)
    if not identity or not INAT_TOKENS_PATH.exists():
        return
    payload = _load_inat_tokens_payload()
    if identity in payload:
        del payload[identity]
        INAT_TOKENS_PATH.write_text(
            json.dumps({"tokens": payload}, indent=2),
            encoding="utf-8",
        )


@dataclass(frozen=True)
class Settings:
    app_name: str = "HikeJournal"
    storage_backend: str = os.getenv("STORAGE_BACKEND", "supabase").strip().lower()
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")
    supabase_bucket: str = os.getenv("SUPABASE_BUCKET", "hike-journal")
    r2_endpoint: str = os.getenv("R2_ENDPOINT", "").rstrip("/")
    r2_bucket: str = os.getenv("R2_BUCKET", "hike-journal")
    r2_access_key_id: str = os.getenv("R2_ACCESS_KEY_ID", "")
    r2_secret_access_key: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
    r2_public_base_url: str = os.getenv("R2_PUBLIC_BASE_URL", "").rstrip("/")
    r2_region: str = os.getenv("R2_REGION", "auto")
    r2_api_token: str = os.getenv("R2_API_TOKEN", "")
    inat_access_token_env: str = os.getenv("INAT_ACCESS_TOKEN", "")
    inat_base_url: str = os.getenv("INAT_BASE_URL", "https://api.inaturalist.org/v1").rstrip("/")
    inat_cv_request_interval_seconds: float = float(os.getenv("INAT_CV_REQUEST_INTERVAL_SECONDS", "2.5"))
    inat_oauth_client_id: str = os.getenv("INAT_OAUTH_CLIENT_ID", "")
    inat_oauth_client_secret: str = os.getenv("INAT_OAUTH_CLIENT_SECRET", "")
    inat_oauth_redirect_uri: str = os.getenv("INAT_OAUTH_REDIRECT_URI", "http://localhost:8505/")
    inat_oauth_authorize_url: str = os.getenv("INAT_OAUTH_AUTHORIZE_URL", "https://www.inaturalist.org/oauth/authorize").rstrip("/")
    inat_oauth_token_url: str = os.getenv("INAT_OAUTH_TOKEN_URL", "https://www.inaturalist.org/oauth/token").rstrip("/")
    inat_api_token_url: str = os.getenv("INAT_API_TOKEN_URL", "https://www.inaturalist.org/users/api_token").rstrip("/")
    image_max_dimension: int = int(os.getenv("IMAGE_MAX_DIMENSION", "1600"))
    image_quality: int = int(os.getenv("IMAGE_QUALITY", "86"))
    thumbnail_max_dimension: int = int(os.getenv("THUMBNAIL_MAX_DIMENSION", "560"))
    thumbnail_quality: int = int(os.getenv("THUMBNAIL_QUALITY", "72"))
    admin_emails_raw: str = os.getenv("ADMIN_EMAILS", "")
    allowed_emails_raw: str = os.getenv("ALLOWED_EMAILS", "")
    require_google_auth: bool = os.getenv("REQUIRE_GOOGLE_AUTH", "false").strip().lower() in {"1", "true", "yes", "on"}

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def r2_configured(self) -> bool:
        return bool(
            self.r2_endpoint
            and self.r2_bucket
            and self.r2_access_key_id
            and self.r2_secret_access_key
            and self.r2_public_base_url
        )

    @property
    def inat_access_token(self) -> str:
        return load_inat_access_token(self.inat_access_token_env)

    @property
    def inat_configured(self) -> bool:
        return bool(self.inat_access_token)

    @property
    def admin_emails(self) -> set[str]:
        return {
            email.strip().lower()
            for email in self.admin_emails_raw.split(",")
            if email.strip()
        }

    @property
    def allowed_emails(self) -> set[str]:
        configured = {
            email.strip().lower()
            for email in self.allowed_emails_raw.split(",")
            if email.strip()
        }
        return configured or self.admin_emails

    @property
    def inat_oauth_configured(self) -> bool:
        return bool(self.inat_oauth_client_id and self.inat_oauth_client_secret and self.inat_oauth_redirect_uri)


settings = Settings()
