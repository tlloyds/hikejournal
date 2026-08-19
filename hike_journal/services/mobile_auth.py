from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import os
import secrets
from typing import Any, Callable
from uuid import uuid4

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
import jwt
from supabase import Client


ACCESS_TOKEN_MINUTES = 20
REFRESH_TOKEN_DAYS = 30
SESSION_ISSUER = "hikejournal-mobile"
SESSION_AUDIENCE = "com.hikejournal.app"


class MobileAuthError(ValueError):
    pass


@dataclass(frozen=True)
class MobileSession:
    access_token: str
    refresh_token: str
    expires_in: int
    account: dict[str, str]

    def payload(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_in": self.expires_in,
            "token_type": "Bearer",
            "account": self.account,
        }


def mobile_auth_mode() -> str:
    return os.getenv("MOBILE_AUTH_MODE", "legacy").strip().lower() or "legacy"


def google_web_client_id() -> str:
    return os.getenv("GOOGLE_WEB_CLIENT_ID", "").strip()


def mobile_session_secret() -> str:
    return os.getenv("MOBILE_SESSION_SECRET", "").strip()


def mobile_auth_configuration_errors() -> list[str]:
    if mobile_auth_mode() != "google":
        return []
    errors: list[str] = []
    if not google_web_client_id().endswith(".apps.googleusercontent.com"):
        errors.append("GOOGLE_WEB_CLIENT_ID must identify the Google OAuth web client")
    secret = mobile_session_secret()
    if len(secret) < 32 or len(set(secret)) < 12:
        errors.append("MOBILE_SESSION_SECRET must be a high-entropy value of at least 32 characters")
    return errors


def verify_google_credential(
    credential: str,
    *,
    expected_nonce: str | None = None,
    verifier: Callable[..., dict[str, Any]] = google_id_token.verify_oauth2_token,
) -> dict[str, str]:
    if not credential.strip():
        raise MobileAuthError("Google sign-in did not return a credential.")
    try:
        claims = verifier(
            credential,
            google_requests.Request(),
            google_web_client_id(),
        )
    except Exception as exc:
        raise MobileAuthError("Google sign-in could not be verified.") from exc
    subject = str(claims.get("sub") or "").strip()
    email = str(claims.get("email") or "").strip().lower()
    issuer = str(claims.get("iss") or "")
    if not subject or not email or claims.get("email_verified") is not True:
        raise MobileAuthError("A verified Google account is required.")
    if issuer not in {"accounts.google.com", "https://accounts.google.com"}:
        raise MobileAuthError("Google sign-in returned an unexpected issuer.")
    if expected_nonce and not secrets.compare_digest(str(claims.get("nonce") or ""), expected_nonce):
        raise MobileAuthError("Google sign-in could not be matched to this device request.")
    return {
        "subject": subject,
        "email": email,
        "display_name": str(claims.get("name") or email).strip() or email,
        "picture_url": str(claims.get("picture") or "").strip(),
    }


def _refresh_token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _session_account(user: dict[str, Any]) -> dict[str, str]:
    return {
        "subject": str(user.get("google_subject") or ""),
        "email": str(user.get("email") or "").strip().lower(),
        "display_name": str(user.get("display_name") or user.get("email") or "Hiker"),
        "picture_url": str(user.get("picture_url") or ""),
    }


def _access_token(user: dict[str, Any], *, now: datetime) -> tuple[str, int]:
    expires_at = now + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    account = _session_account(user)
    token = jwt.encode(
        {
            "iss": SESSION_ISSUER,
            "aud": SESSION_AUDIENCE,
            "sub": account["subject"],
            "email": account["email"],
            "name": account["display_name"],
            "picture": account["picture_url"],
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": str(uuid4()),
        },
        mobile_session_secret(),
        algorithm="HS256",
    )
    return token, int((expires_at - now).total_seconds())


def verify_access_token(value: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            value,
            mobile_session_secret(),
            algorithms=["HS256"],
            audience=SESSION_AUDIENCE,
            issuer=SESSION_ISSUER,
            options={"require": ["exp", "iat", "sub", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise MobileAuthError("Your HikeJournal session has expired.") from exc
    if claims.get("type") != "access":
        raise MobileAuthError("Your HikeJournal session is invalid.")
    return {
        "mode": "google",
        "email": str(claims.get("email") or "").strip().lower() or None,
        "subject": str(claims.get("sub") or "").strip() or None,
        "display_name": str(claims.get("name") or "Hiker"),
        "picture_url": str(claims.get("picture") or ""),
        "auth_configured": True,
        "is_logged_in": True,
    }


def _upsert_user(client: Client, identity: dict[str, str], *, now: datetime) -> dict[str, Any]:
    payload = {
        "google_subject": identity["subject"],
        "email": identity["email"],
        "display_name": identity["display_name"],
        "picture_url": identity["picture_url"] or None,
        "last_signed_in_at": now.isoformat(),
        "deletion_requested_at": None,
    }
    response = client.table("app_users").upsert(payload, on_conflict="google_subject").execute()
    rows = response.data or []
    if not rows:
        lookup = (
            client.table("app_users")
            .select("*")
            .eq("google_subject", identity["subject"])
            .limit(1)
            .execute()
        )
        rows = lookup.data or []
    if not rows:
        raise MobileAuthError("HikeJournal could not create your account.")
    return rows[0]


def _issue_session(
    client: Client,
    user: dict[str, Any],
    *,
    device_id: str,
    now: datetime,
    existing_session_id: str | None = None,
) -> MobileSession:
    refresh_token = secrets.token_urlsafe(48)
    refresh_expires_at = now + timedelta(days=REFRESH_TOKEN_DAYS)
    session_payload = {
        "user_id": user["id"],
        "device_id": device_id[:160],
        "refresh_token_hash": _refresh_token_hash(refresh_token),
        "expires_at": refresh_expires_at.isoformat(),
        "last_used_at": now.isoformat(),
        "revoked_at": None,
    }
    if existing_session_id:
        (
            client.table("mobile_user_sessions")
            .update(session_payload)
            .eq("id", existing_session_id)
            .execute()
        )
    else:
        client.table("mobile_user_sessions").insert(session_payload).execute()
    access_token, expires_in = _access_token(user, now=now)
    return MobileSession(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        account=_session_account(user),
    )


def create_google_session(
    client: Client,
    *,
    credential: str,
    device_id: str,
    nonce: str | None = None,
    now: datetime | None = None,
    verifier: Callable[..., dict[str, Any]] = google_id_token.verify_oauth2_token,
) -> MobileSession:
    current = now or datetime.now(UTC)
    identity = verify_google_credential(credential, expected_nonce=nonce, verifier=verifier)
    user = _upsert_user(client, identity, now=current)
    return _issue_session(client, user, device_id=device_id, now=current)


def refresh_mobile_session(
    client: Client,
    *,
    refresh_token: str,
    device_id: str,
    now: datetime | None = None,
) -> MobileSession:
    current = now or datetime.now(UTC)
    response = (
        client.table("mobile_user_sessions")
        .select("*,app_users(*)")
        .eq("refresh_token_hash", _refresh_token_hash(refresh_token))
        .is_("revoked_at", "null")
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise MobileAuthError("Your HikeJournal session has expired. Sign in again.")
    session = rows[0]
    expires_at = datetime.fromisoformat(str(session.get("expires_at") or "").replace("Z", "+00:00"))
    if expires_at <= current:
        raise MobileAuthError("Your HikeJournal session has expired. Sign in again.")
    user = session.get("app_users") or {}
    if not user or user.get("deletion_requested_at"):
        raise MobileAuthError("This HikeJournal account is not active.")
    return _issue_session(
        client,
        user,
        device_id=device_id,
        now=current,
        existing_session_id=str(session["id"]),
    )


def revoke_mobile_session(client: Client, *, refresh_token: str, now: datetime | None = None) -> None:
    if not refresh_token:
        return
    current = now or datetime.now(UTC)
    (
        client.table("mobile_user_sessions")
        .update({"revoked_at": current.isoformat()})
        .eq("refresh_token_hash", _refresh_token_hash(refresh_token))
        .execute()
    )


def delete_mobile_account(client: Client, *, google_subject: str) -> None:
    subject = google_subject.strip()
    if not subject:
        raise MobileAuthError("A signed-in HikeJournal account is required.")
    try:
        client.rpc(
            "delete_hikejournal_account",
            {"p_google_subject": subject},
        ).execute()
    except Exception as exc:
        raise MobileAuthError("HikeJournal could not delete this account. No database records were removed.") from exc
