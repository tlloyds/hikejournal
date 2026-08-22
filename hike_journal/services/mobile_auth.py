from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import os
import re
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
APPLE_IDENTITY_ISSUER = "https://appleid.apple.com"
APPLE_IDENTITY_JWKS_URL = "https://appleid.apple.com/auth/keys"
_APPLE_CLIENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{2,254}$")
_apple_jwks_client = jwt.PyJWKClient(
    APPLE_IDENTITY_JWKS_URL,
    cache_keys=True,
    lifespan=3600,
    timeout=5,
)


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


def apple_sign_in_client_id() -> str:
    """Return the server-side audience for native Sign in with Apple tokens."""
    return os.getenv("APPLE_SIGN_IN_CLIENT_ID", "").strip()


def mobile_session_secret() -> str:
    return os.getenv("MOBILE_SESSION_SECRET", "").strip()


def apple_auth_configuration_errors() -> list[str]:
    client_id = apple_sign_in_client_id()
    if not client_id:
        return [
            "APPLE_SIGN_IN_CLIENT_ID must match the Services ID or app bundle ID used as the Apple token audience"
        ]
    if not _APPLE_CLIENT_ID_PATTERN.fullmatch(client_id):
        return [
            "APPLE_SIGN_IN_CLIENT_ID must be a valid Services ID or app bundle ID"
        ]
    return []


def mobile_auth_configuration_errors() -> list[str]:
    if mobile_auth_mode() != "google":
        return []
    errors: list[str] = []
    if not google_web_client_id().endswith(".apps.googleusercontent.com"):
        errors.append("GOOGLE_WEB_CLIENT_ID must identify the Google OAuth web client")
    secret = mobile_session_secret()
    if len(secret) < 32 or len(set(secret)) < 12:
        errors.append("MOBILE_SESSION_SECRET must be a high-entropy value of at least 32 characters")
    # Apple sign-in is optional during the existing Android-only rollout. Once
    # an audience is configured, fail readiness on a malformed value rather
    # than advertising a verifier that can never accept a credential.
    if apple_sign_in_client_id():
        errors.extend(apple_auth_configuration_errors())
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


def _verify_apple_signed_token(
    credential: str,
    audience: str,
    issuer: str,
) -> dict[str, Any]:
    """Verify an Apple ID token with Apple's current public signing key."""
    signing_key = _apple_jwks_client.get_signing_key_from_jwt(credential)
    return jwt.decode(
        credential,
        signing_key.key,
        algorithms=["RS256"],
        audience=audience,
        issuer=issuer,
        options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]},
    )


def _apple_audience_matches(claim: Any, expected: str) -> bool:
    if isinstance(claim, str):
        return secrets.compare_digest(claim, expected)
    if isinstance(claim, list):
        return any(
            isinstance(item, str) and secrets.compare_digest(item, expected)
            for item in claim
        )
    return False


def _apple_nonce_matches(claim: Any, expected: str) -> bool:
    actual = str(claim or "")
    if not actual:
        return False
    # AuthenticationServices clients normally put SHA-256(raw nonce) in the
    # Apple request and send the raw nonce to this endpoint. Accepting an exact
    # match as well keeps the seam usable for clients that submit the already-
    # hashed challenge; both forms remain bound to the signed token claim.
    expected_hash = hashlib.sha256(expected.encode("utf-8")).hexdigest()
    return secrets.compare_digest(actual, expected) or secrets.compare_digest(actual, expected_hash)


def verify_apple_credential(
    credential: str,
    *,
    expected_nonce: str,
    now: datetime | None = None,
    verifier: Callable[[str, str, str], dict[str, Any]] = _verify_apple_signed_token,
) -> dict[str, str]:
    """Verify signature and security claims for a native Apple ID token.

    ``verifier`` is an explicit test seam. The production verifier fetches and
    caches Apple's public JWKS; the app never receives or embeds server secrets.
    """
    if not credential.strip():
        raise MobileAuthError("Sign in with Apple did not return an identity token.")
    if not expected_nonce.strip():
        raise MobileAuthError("Sign in with Apple did not return a nonce challenge.")
    configuration_errors = apple_auth_configuration_errors()
    if configuration_errors:
        raise MobileAuthError(configuration_errors[0])
    audience = apple_sign_in_client_id()
    try:
        claims = verifier(credential, audience, APPLE_IDENTITY_ISSUER)
    except Exception as exc:
        raise MobileAuthError("Sign in with Apple could not be verified.") from exc

    current = now or datetime.now(UTC)
    issuer = str(claims.get("iss") or "")
    subject = str(claims.get("sub") or "").strip()
    try:
        expires_at = int(claims.get("exp"))
        issued_at = int(claims.get("iat"))
    except (TypeError, ValueError) as exc:
        raise MobileAuthError("Sign in with Apple returned invalid time claims.") from exc
    if issuer != APPLE_IDENTITY_ISSUER:
        raise MobileAuthError("Sign in with Apple returned an unexpected issuer.")
    if not _apple_audience_matches(claims.get("aud"), audience):
        raise MobileAuthError("Sign in with Apple returned an unexpected audience.")
    if expires_at <= int(current.timestamp()):
        raise MobileAuthError("Sign in with Apple returned an expired identity token.")
    if issued_at > int(current.timestamp()) + 300:
        raise MobileAuthError("Sign in with Apple returned an invalid issue time.")
    if not subject:
        raise MobileAuthError("Sign in with Apple did not identify an account.")
    if not _apple_nonce_matches(claims.get("nonce"), expected_nonce):
        raise MobileAuthError("Sign in with Apple could not be matched to this device request.")

    email = str(claims.get("email") or "").strip().lower()
    email_verified = claims.get("email_verified")
    verified_email_claim = email_verified is True or (
        isinstance(email_verified, str) and email_verified.casefold() == "true"
    )
    if email and not verified_email_claim:
        raise MobileAuthError("Sign in with Apple did not return a verified email address.")
    return {
        "subject": subject,
        "email": email,
        "display_name": email or "Hiker",
        "picture_url": "",
    }


def _refresh_token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _ownership_subject(provider: str, provider_subject: str) -> str:
    """Keep Google ownership stable and namespace every new provider."""
    return provider_subject if provider == "google" else f"{provider}:{provider_subject}"


def _legacy_google_identity(user: dict[str, Any]) -> dict[str, Any] | None:
    subject = str(user.get("google_subject") or "").strip()
    if not subject:
        return None
    return {
        "id": None,
        "user_id": str(user.get("id") or ""),
        "provider": "google",
        "provider_subject": subject,
        "email": str(user.get("email") or "").strip().lower() or None,
    }


def _session_account(
    user: dict[str, Any],
    identity: dict[str, Any] | None = None,
) -> dict[str, str]:
    selected_identity = identity or _legacy_google_identity(user) or {}
    provider = str(selected_identity.get("provider") or "").strip().lower()
    provider_subject = str(selected_identity.get("provider_subject") or "").strip()
    subject = (
        _ownership_subject(provider, provider_subject)
        if provider and provider_subject
        else str(user.get("google_subject") or "")
    )
    account = {
        "subject": subject,
        "email": str(user.get("email") or selected_identity.get("email") or "").strip().lower(),
        "display_name": str(user.get("display_name") or user.get("email") or "Hiker"),
        "picture_url": str(user.get("picture_url") or ""),
    }
    user_id = str(user.get("id") or "").strip()
    if user_id:
        account["user_id"] = user_id
    if provider:
        account["identity_provider"] = provider
    return account


def _access_token(
    user: dict[str, Any],
    *,
    now: datetime,
    identity: dict[str, Any] | None = None,
) -> tuple[str, int]:
    expires_at = now + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    account = _session_account(user, identity)
    claims = {
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
    }
    # Add canonical app identity without changing the legacy Google `sub`.
    if account.get("user_id"):
        claims["uid"] = account["user_id"]
    if account.get("user_id") and account.get("identity_provider"):
        claims["idp"] = account["identity_provider"]
    token = jwt.encode(
        claims,
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
    provider = str(claims.get("idp") or "").strip().lower()
    context = {
        # Tokens issued before provider-neutral identity intentionally have no
        # uid/idp claims and retain their exact Google owner context.
        "mode": provider or "google",
        "email": str(claims.get("email") or "").strip().lower() or None,
        "subject": str(claims.get("sub") or "").strip() or None,
        "display_name": str(claims.get("name") or "Hiker"),
        "picture_url": str(claims.get("picture") or ""),
        "auth_configured": True,
        "is_logged_in": True,
    }
    user_id = str(claims.get("uid") or "").strip()
    if user_id:
        context["user_id"] = user_id
    if provider:
        context["identity_provider"] = provider
    return context


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


def _resolved_identity_payload(value: Any) -> tuple[dict[str, Any], dict[str, Any]] | None:
    payload = value[0] if isinstance(value, list) and value else value
    if not isinstance(payload, dict):
        return None
    user = payload.get("user")
    identity = payload.get("identity")
    if not isinstance(user, dict) or not isinstance(identity, dict):
        return None
    if not user.get("id") or not identity.get("id"):
        return None
    return user, identity


def _resolve_provider_user(
    client: Client,
    identity: dict[str, str],
    *,
    provider: str,
    now: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve a provider subject without ever using email as an account key."""
    rpc_payload = {
        "p_provider": provider,
        "p_provider_subject": identity["subject"],
        "p_email": identity["email"] or None,
        "p_display_name": identity["display_name"],
        "p_picture_url": identity["picture_url"] or None,
        "p_signed_in_at": now.isoformat(),
    }
    try:
        response = client.rpc("resolve_hikejournal_identity", rpc_payload).execute()
        resolved = _resolved_identity_payload(response.data)
        if resolved is not None:
            return resolved
    except Exception as exc:
        if provider != "google":
            raise MobileAuthError(
                "Sign in with Apple is not ready on this server. Apply sql/provider_neutral_identity_migration.sql."
            ) from exc

    # A rolling backend deployment may briefly run before the additive identity
    # RPC is installed. Preserve the previous Google-only path and still issue
    # uid/idp claims from the canonical app_users row. Apple never falls back or
    # resolves by email.
    if provider == "google":
        user = _upsert_user(client, identity, now=now)
        legacy_identity = _legacy_google_identity(user)
        if legacy_identity is None:
            raise MobileAuthError("HikeJournal could not resolve your Google account.")
        return user, legacy_identity
    raise MobileAuthError("HikeJournal could not resolve your Apple account.")


def _issue_session(
    client: Client,
    user: dict[str, Any],
    *,
    identity: dict[str, Any] | None,
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
    identity_id = str((identity or {}).get("id") or "").strip()
    if identity_id:
        session_payload["identity_id"] = identity_id
    if existing_session_id:
        (
            client.table("mobile_user_sessions")
            .update(session_payload)
            .eq("id", existing_session_id)
            .execute()
        )
    else:
        client.table("mobile_user_sessions").insert(session_payload).execute()
    access_token, expires_in = _access_token(user, now=now, identity=identity)
    return MobileSession(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        account=_session_account(user, identity),
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
    user, resolved_identity = _resolve_provider_user(
        client,
        identity,
        provider="google",
        now=current,
    )
    return _issue_session(
        client,
        user,
        identity=resolved_identity,
        device_id=device_id,
        now=current,
    )


def create_apple_session(
    client: Client,
    *,
    identity_token: str,
    device_id: str,
    nonce: str,
    display_name: str | None = None,
    now: datetime | None = None,
    verifier: Callable[[str, str, str], dict[str, Any]] = _verify_apple_signed_token,
) -> MobileSession:
    current = now or datetime.now(UTC)
    identity = verify_apple_credential(
        identity_token,
        expected_nonce=nonce,
        now=current,
        verifier=verifier,
    )
    supplied_name = str(display_name or "").strip()
    if supplied_name:
        identity["display_name"] = supplied_name
    else:
        # Apple supplies fullName only on the first authorization. An empty
        # update tells the resolver to preserve an existing profile name while
        # still letting a new account fall back to verified email or "Hiker".
        identity["display_name"] = ""
    user, resolved_identity = _resolve_provider_user(
        client,
        identity,
        provider="apple",
        now=current,
    )
    return _issue_session(
        client,
        user,
        identity=resolved_identity,
        device_id=device_id,
        now=current,
    )


def _load_session_identity(
    client: Client,
    session: dict[str, Any],
    user: dict[str, Any],
) -> dict[str, Any] | None:
    identity_id = str(session.get("identity_id") or "").strip()
    if identity_id:
        try:
            response = (
                client.table("user_identities")
                .select("*")
                .eq("id", identity_id)
                .limit(1)
                .execute()
            )
            rows = response.data or []
            if rows:
                return rows[0]
        except Exception as exc:
            if not user.get("google_subject"):
                raise MobileAuthError("This HikeJournal identity is not active.") from exc
    return _legacy_google_identity(user)


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
    identity = _load_session_identity(client, session, user)
    if identity is None:
        raise MobileAuthError("This HikeJournal identity is not active.")
    return _issue_session(
        client,
        user,
        identity=identity,
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


def delete_mobile_account_by_user_id(client: Client, *, user_id: str) -> None:
    canonical_user_id = user_id.strip()
    if not canonical_user_id:
        raise MobileAuthError("A signed-in HikeJournal account is required.")
    try:
        client.rpc(
            "delete_hikejournal_account_by_user_id",
            {"p_user_id": canonical_user_id},
        ).execute()
    except Exception as exc:
        raise MobileAuthError("HikeJournal could not delete this account. No database records were removed.") from exc


def delete_mobile_account(
    client: Client,
    *,
    google_subject: str = "",
    user_id: str = "",
) -> None:
    """Delete by canonical user ID, with the original Google wrapper retained."""
    if user_id.strip():
        delete_mobile_account_by_user_id(client, user_id=user_id)
        return
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
