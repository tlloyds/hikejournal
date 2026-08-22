from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
import hashlib
from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from starlette.requests import Request

import mobile_api
from hike_journal.services.mobile_auth import (
    APPLE_IDENTITY_ISSUER,
    MobileAuthError,
    _access_token,
    _resolve_provider_user,
    apple_auth_configuration_errors,
    create_apple_session,
    delete_mobile_account,
    mobile_auth_configuration_errors,
    refresh_mobile_session,
    verify_access_token,
    verify_apple_credential,
    verify_google_credential,
)


def test_google_credential_requires_verified_identity_and_matching_nonce(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_WEB_CLIENT_ID", "web-client.apps.googleusercontent.com")

    identity = verify_google_credential(
        "signed-google-id-token",
        expected_nonce="device-nonce",
        verifier=lambda credential, _request, audience: {
            "sub": "google-subject-1",
            "email": "Hiker@Example.com",
            "email_verified": True,
            "iss": "https://accounts.google.com",
            "aud": audience,
            "nonce": "device-nonce",
            "name": "Trail Hiker",
        },
    )

    assert identity == {
        "subject": "google-subject-1",
        "email": "hiker@example.com",
        "display_name": "Trail Hiker",
        "picture_url": "",
    }

    with pytest.raises(MobileAuthError, match="matched"):
        verify_google_credential(
            "signed-google-id-token",
            expected_nonce="different-nonce",
            verifier=lambda *_args: {
                "sub": "google-subject-1",
                "email": "hiker@example.com",
                "email_verified": True,
                "iss": "accounts.google.com",
                "nonce": "device-nonce",
            },
        )


def test_hikejournal_access_token_round_trips_owner_context(monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_SESSION_SECRET", "a-high-entropy-mobile-session-secret-0123456789")
    token, expires_in = _access_token(
        {
            "google_subject": "google-subject-1",
            "email": "hiker@example.com",
            "display_name": "Trail Hiker",
            "picture_url": None,
        },
        now=datetime.now(UTC),
    )

    assert expires_in == 1_200
    assert verify_access_token(token) == {
        "mode": "google",
        "email": "hiker@example.com",
        "subject": "google-subject-1",
        "display_name": "Trail Hiker",
        "picture_url": "",
        "auth_configured": True,
        "is_logged_in": True,
    }


def test_provider_neutral_claims_are_additive_and_keep_google_subject(monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_SESSION_SECRET", "a-high-entropy-mobile-session-secret-0123456789")
    token, _ = _access_token(
        {
            "id": "89f9e113-0798-4e10-bd9f-120694e085a7",
            "google_subject": "unchanged-google-subject",
            "email": "hiker@example.com",
            "display_name": "Trail Hiker",
        },
        identity={
            "id": "7bcae2fc-ed18-4356-b400-a720f58491d4",
            "provider": "google",
            "provider_subject": "unchanged-google-subject",
        },
        now=datetime.now(UTC),
    )

    context = verify_access_token(token)
    assert context["subject"] == "unchanged-google-subject"
    assert context["user_id"] == "89f9e113-0798-4e10-bd9f-120694e085a7"
    assert context["identity_provider"] == "google"
    assert context["mode"] == "google"


def test_apple_credential_verifies_security_claims_and_hashed_nonce(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_SIGN_IN_CLIENT_ID", "com.hikejournal.app")
    current = datetime(2026, 8, 21, 12, tzinfo=UTC)
    raw_nonce = "fresh-device-nonce-12345"
    captured: dict[str, str] = {}

    def verifier(token: str, audience: str, issuer: str):
        captured.update(token=token, audience=audience, issuer=issuer)
        return {
            "iss": issuer,
            "aud": audience,
            "sub": "apple-user-001",
            "iat": int(current.timestamp()) - 5,
            "exp": int(current.timestamp()) + 300,
            "nonce": hashlib.sha256(raw_nonce.encode()).hexdigest(),
            "email": "PrivateRelay@Example.com",
            "email_verified": "true",
        }

    identity = verify_apple_credential(
        "signed-apple-identity-token",
        expected_nonce=raw_nonce,
        now=current,
        verifier=verifier,
    )

    assert captured == {
        "token": "signed-apple-identity-token",
        "audience": "com.hikejournal.app",
        "issuer": APPLE_IDENTITY_ISSUER,
    }
    assert identity == {
        "subject": "apple-user-001",
        "email": "privaterelay@example.com",
        "display_name": "privaterelay@example.com",
        "picture_url": "",
    }


@pytest.mark.parametrize(
    ("claim_update", "message"),
    [
        ({"iss": "https://attacker.example"}, "issuer"),
        ({"aud": "some.other.app"}, "audience"),
        ({"exp": 1}, "expired"),
        ({"nonce": "wrong-nonce"}, "matched"),
    ],
)
def test_apple_credential_rejects_invalid_claims(monkeypatch, claim_update, message) -> None:
    monkeypatch.setenv("APPLE_SIGN_IN_CLIENT_ID", "com.hikejournal.app")
    current = datetime(2026, 8, 21, 12, tzinfo=UTC)
    claims = {
        "iss": APPLE_IDENTITY_ISSUER,
        "aud": "com.hikejournal.app",
        "sub": "apple-user-001",
        "iat": int(current.timestamp()),
        "exp": int(current.timestamp()) + 300,
        "nonce": "fresh-device-nonce-12345",
    }
    claims.update(claim_update)

    with pytest.raises(MobileAuthError, match=message):
        verify_apple_credential(
            "signed-apple-identity-token",
            expected_nonce="fresh-device-nonce-12345",
            now=current,
            verifier=lambda *_args: claims,
        )


def test_apple_configuration_names_the_exact_required_server_value(monkeypatch) -> None:
    monkeypatch.delenv("APPLE_SIGN_IN_CLIENT_ID", raising=False)
    assert apple_auth_configuration_errors() == [
        "APPLE_SIGN_IN_CLIENT_ID must match the Services ID or app bundle ID used as the Apple token audience"
    ]

    monkeypatch.setenv("APPLE_SIGN_IN_CLIENT_ID", "not a client id")
    assert apple_auth_configuration_errors() == [
        "APPLE_SIGN_IN_CLIENT_ID must be a valid Services ID or app bundle ID"
    ]


def test_provider_resolution_does_not_merge_google_and_apple_by_email() -> None:
    calls: list[dict[str, object]] = []
    users = {
        "google": {
            "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "google_subject": "google-subject-1",
            "email": "same@example.com",
            "display_name": "Google Hiker",
        },
        "apple": {
            "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            "google_subject": None,
            "email": "same@example.com",
            "display_name": "Apple Hiker",
        },
    }

    class RpcResult:
        def __init__(self, payload):
            self.data = payload

        def execute(self):
            return self

    class Client:
        def rpc(self, name, payload):
            assert name == "resolve_hikejournal_identity"
            calls.append(payload)
            provider = payload["p_provider"]
            return RpcResult(
                {
                    "user": users[provider],
                    "identity": {
                        "id": f"{provider}-identity-id",
                        "user_id": users[provider]["id"],
                        "provider": provider,
                        "provider_subject": payload["p_provider_subject"],
                        "email": payload["p_email"],
                    },
                }
            )

    current = datetime(2026, 8, 21, 12, tzinfo=UTC)
    google_user, _ = _resolve_provider_user(
        Client(),
        {
            "subject": "google-subject-1",
            "email": "same@example.com",
            "display_name": "Google Hiker",
            "picture_url": "",
        },
        provider="google",
        now=current,
    )
    apple_user, _ = _resolve_provider_user(
        Client(),
        {
            "subject": "apple-subject-1",
            "email": "same@example.com",
            "display_name": "Apple Hiker",
            "picture_url": "",
        },
        provider="apple",
        now=current,
    )

    assert google_user["id"] != apple_user["id"]
    assert [call["p_provider"] for call in calls] == ["google", "apple"]
    assert calls[0]["p_email"] == calls[1]["p_email"] == "same@example.com"


def test_apple_session_uses_namespaced_subject_and_canonical_identity(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_SIGN_IN_CLIENT_ID", "com.hikejournal.app")
    monkeypatch.setenv("MOBILE_SESSION_SECRET", "a-high-entropy-mobile-session-secret-0123456789")
    current = datetime.now(UTC)
    inserted_sessions: list[dict[str, object]] = []

    class Result:
        def __init__(self, data=None):
            self.data = data

        def execute(self):
            return self

    class SessionTable:
        def insert(self, payload):
            inserted_sessions.append(payload)
            return Result([payload])

    class Client:
        def rpc(self, name, payload):
            assert name == "resolve_hikejournal_identity"
            assert payload["p_provider"] == "apple"
            return Result(
                {
                    "user": {
                        "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                        "google_subject": None,
                        "email": "relay@example.com",
                        "display_name": "Apple Hiker",
                        "picture_url": None,
                    },
                    "identity": {
                        "id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
                        "user_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                        "provider": "apple",
                        "provider_subject": "apple-subject-1",
                        "email": "relay@example.com",
                    },
                }
            )

        def table(self, name):
            assert name == "mobile_user_sessions"
            return SessionTable()

    session = create_apple_session(
        Client(),
        identity_token="signed-apple-identity-token",
        device_id="ios-device-12345",
        nonce="fresh-device-nonce-12345",
        display_name="Apple Hiker",
        now=current,
        verifier=lambda _token, audience, issuer: {
            "iss": issuer,
            "aud": audience,
            "sub": "apple-subject-1",
            "iat": int(current.timestamp()),
            "exp": int(current.timestamp()) + 300,
            "nonce": "fresh-device-nonce-12345",
            "email": "relay@example.com",
            "email_verified": True,
        },
    )

    assert session.account["subject"] == "apple:apple-subject-1"
    assert session.account["user_id"] == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    assert session.account["identity_provider"] == "apple"
    assert inserted_sessions[0]["identity_id"] == "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    context = verify_access_token(session.access_token)
    assert context["subject"] == "apple:apple-subject-1"
    assert context["user_id"] == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    assert context["identity_provider"] == "apple"


def test_apple_auth_route_is_additive_and_passes_only_public_credential_data(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Session:
        @staticmethod
        def payload():
            return {
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 1200,
                "token_type": "Bearer",
                "account": {
                    "subject": "apple:apple-subject-1",
                    "email": "relay@example.com",
                    "display_name": "Apple Hiker",
                    "picture_url": "",
                },
            }

    def create_session(client, **kwargs):
        captured["client"] = client
        captured.update(kwargs)
        return Session()

    service = SimpleNamespace(client=object())
    monkeypatch.setattr(mobile_api, "mobile_auth_mode", lambda: "google")
    monkeypatch.setattr(mobile_api, "apple_auth_configuration_errors", lambda: [])
    monkeypatch.setattr(mobile_api, "get_services", lambda: service)
    monkeypatch.setattr(mobile_api, "create_apple_session", create_session)

    response = mobile_api.authenticate_apple(
        mobile_api.AppleAuthInput(
            identity_token="signed-apple-identity-token",
            device_id="ios-device-12345",
            nonce="fresh-device-nonce-12345",
            display_name="Apple Hiker",
        )
    )

    assert response["account"]["subject"] == "apple:apple-subject-1"
    assert captured == {
        "client": service.client,
        "identity_token": "signed-apple-identity-token",
        "device_id": "ios-device-12345",
        "nonce": "fresh-device-nonce-12345",
        "display_name": "Apple Hiker",
    }
    assert "/v1/auth/apple" in mobile_api.app.openapi()["paths"]


def test_apple_refresh_session_retains_its_provider_identity(monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_SESSION_SECRET", "a-high-entropy-mobile-session-secret-0123456789")
    current = datetime.now(UTC)
    updates: list[dict[str, object]] = []
    user = {
        "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "google_subject": None,
        "email": "relay@example.com",
        "display_name": "Apple Hiker",
        "picture_url": None,
        "deletion_requested_at": None,
    }
    identity = {
        "id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        "user_id": user["id"],
        "provider": "apple",
        "provider_subject": "apple-subject-1",
        "email": "relay@example.com",
    }

    class Query:
        def __init__(self, table_name):
            self.table_name = table_name
            self.operation = "select"
            self.payload = None

        def select(self, *_args):
            return self

        def eq(self, *_args):
            return self

        def is_(self, *_args):
            return self

        def limit(self, *_args):
            return self

        def update(self, payload):
            self.operation = "update"
            self.payload = payload
            updates.append(payload)
            return self

        def execute(self):
            if self.operation == "update":
                return SimpleNamespace(data=[self.payload])
            if self.table_name == "mobile_user_sessions":
                return SimpleNamespace(
                    data=[
                        {
                            "id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
                            "identity_id": identity["id"],
                            "expires_at": (current.replace(microsecond=0) + timedelta(days=1)).isoformat(),
                            "app_users": user,
                        }
                    ]
                )
            assert self.table_name == "user_identities"
            return SimpleNamespace(data=[identity])

    class Client:
        @staticmethod
        def table(name):
            return Query(name)

    session = refresh_mobile_session(
        Client(),
        refresh_token="existing-refresh-token-with-enough-characters",
        device_id="ios-device-12345",
        now=current,
    )

    assert session.account["subject"] == "apple:apple-subject-1"
    assert session.account["identity_provider"] == "apple"
    assert updates[0]["identity_id"] == identity["id"]


def test_provider_neutral_identity_migration_backfills_without_email_merging() -> None:
    migration = Path("sql/provider_neutral_identity_migration.sql").read_text(encoding="utf-8")
    resolver = migration.split(
        "create or replace function public.resolve_hikejournal_identity", 1
    )[1].split(
        "revoke all on function public.resolve_hikejournal_identity", 1
    )[0]

    assert "create table if not exists public.user_identities" in migration
    assert "alter column google_subject drop not null" in migration
    assert "insert into public.user_identities" in migration
    assert "app_user.google_subject" in resolver
    assert "lower(app_user.email)" not in resolver
    assert "drop index if exists public.app_users_lower_email_idx" in migration
    assert "add column if not exists user_id uuid" in migration
    assert "save_mobile_inat_token_for_user" in migration
    assert "load_mobile_inat_token_for_user" in migration
    assert "delete_hikejournal_account_by_user_id" in migration
    assert "create or replace function public.delete_hikejournal_account(p_google_subject text)" in migration


def test_provider_neutral_inat_function_signature_is_structurally_valid() -> None:
    migration = Path("sql/provider_neutral_identity_migration.sql").read_text(encoding="utf-8")
    match = re.search(
        r"create\s+or\s+replace\s+function\s+public\.save_mobile_inat_token_for_user\s*"
        r"\((?P<parameters>.*?)\)\s*returns\s+void",
        migration,
        flags=re.IGNORECASE | re.DOTALL,
    )

    assert match is not None
    parameter_lines = [
        line.strip()
        for line in match.group("parameters").splitlines()
        if line.strip()
    ]
    assert parameter_lines == [
        "p_user_id uuid,",
        "p_access_token text,",
        "p_encryption_key text",
    ]
    assert migration.count("create or replace function public.save_mobile_inat_token_for_user(") == 1


def test_google_identity_rpc_fallback_performs_exactly_one_legacy_upsert(monkeypatch) -> None:
    class FailedRpc:
        @staticmethod
        def execute():
            raise RuntimeError("resolve_hikejournal_identity is not installed")

    class Client:
        @staticmethod
        def rpc(_name, _payload):
            return FailedRpc()

    writes: list[dict[str, str]] = []

    def fake_upsert(_client, identity, *, now):
        writes.append({**identity, "signed_in_at": now.isoformat()})
        return {
            "id": "11111111-1111-4111-8111-111111111111",
            "google_subject": identity["subject"],
            "email": identity["email"],
            "display_name": identity["display_name"],
        }

    monkeypatch.setattr("hike_journal.services.mobile_auth._upsert_user", fake_upsert)

    user, identity = _resolve_provider_user(
        Client(),
        {
            "subject": "legacy-google-subject",
            "email": "legacy@example.com",
            "display_name": "Legacy Hiker",
            "picture_url": "",
        },
        provider="google",
        now=datetime(2026, 8, 21, 12, tzinfo=UTC),
    )

    assert len(writes) == 1
    assert user["google_subject"] == "legacy-google-subject"
    assert identity["provider"] == "google"


def test_inat_oauth_state_round_trips_canonical_user_and_legacy_google(monkeypatch) -> None:
    monkeypatch.setattr(mobile_api, "_mobile_server_secret", lambda: "oauth-state-secret-1234567890")
    user_id = "89f9e113-0798-4e10-bd9f-120694e085a7"

    canonical = mobile_api._mobile_oauth_state(
        "same@example.com",
        user_id=user_id,
    )
    legacy = mobile_api._mobile_oauth_state("legacy@example.com")

    assert mobile_api._verify_mobile_oauth_state(canonical) == {
        "user_id": user_id,
        "identity_provider": None,
        "email": "same@example.com",
    }
    assert mobile_api._verify_mobile_oauth_state(legacy) == {
        "user_id": None,
        "identity_provider": "google",
        "email": "legacy@example.com",
    }
    assert mobile_api._verify_mobile_oauth_state(canonical + "tampered") is None


def test_apple_inat_credentials_are_loaded_only_by_canonical_user_id(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        mobile_api,
        "_user_context",
        lambda: {
            "mode": "apple",
            "identity_provider": "apple",
            "user_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            "subject": "apple:apple-subject-1",
            "email": "same@example.com",
        },
    )
    monkeypatch.setattr(
        mobile_api,
        "_load_mobile_inat_token_for_user",
        lambda user_id: calls.append(user_id) or "apple.jwt.token",
    )
    monkeypatch.setattr(
        mobile_api,
        "_load_mobile_inat_token",
        lambda _email: pytest.fail("Apple must not load an email-keyed Google token"),
    )

    client = mobile_api._mobile_inat_client()

    assert client.access_token == "apple.jwt.token"
    assert calls == ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"]


def test_inat_oauth_callback_saves_canonical_user_credential(monkeypatch) -> None:
    monkeypatch.setattr(mobile_api, "_mobile_server_secret", lambda: "oauth-state-secret-1234567890")
    user_id = "89f9e113-0798-4e10-bd9f-120694e085a7"
    state = mobile_api._mobile_oauth_state("same@example.com", user_id=user_id)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        mobile_api,
        "exchange_oauth_code",
        lambda **_kwargs: {"access_token": "oauth-token", "refresh_token": "refresh-token"},
    )
    monkeypatch.setattr(mobile_api, "_mobile_oauth_redirect_uri", lambda: "https://api.example/callback")
    monkeypatch.setattr(mobile_api, "get_services", lambda: object())
    monkeypatch.setattr(
        mobile_api,
        "_save_mobile_inat_oauth_token_for_user",
        lambda service, **kwargs: captured.update(service=service, **kwargs),
    )
    monkeypatch.setattr(
        mobile_api,
        "_save_mobile_inat_oauth_token",
        lambda *_args, **_kwargs: pytest.fail("Canonical OAuth must not save by email"),
    )

    response = mobile_api.finish_mobile_inat_oauth(code="authorization-code", state=state)

    assert response.headers["location"] == "hikejournal://inat?status=connected"
    assert captured["user_id"] == user_id
    assert captured["token_payload"] == {
        "access_token": "oauth-token",
        "refresh_token": "refresh-token",
    }


def test_google_mode_rejects_weak_hosted_configuration(monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_AUTH_MODE", "google")
    monkeypatch.setenv("GOOGLE_WEB_CLIENT_ID", "not-a-google-client")
    monkeypatch.setenv("MOBILE_SESSION_SECRET", "short")

    assert mobile_auth_configuration_errors() == [
        "GOOGLE_WEB_CLIENT_ID must identify the Google OAuth web client",
        "MOBILE_SESSION_SECRET must be a high-entropy value of at least 32 characters",
    ]


def test_google_bearer_dependency_populates_request_owner(monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_AUTH_MODE", "google")
    monkeypatch.setenv("MOBILE_SESSION_SECRET", "a-high-entropy-mobile-session-secret-0123456789")
    token, _ = _access_token(
        {
            "google_subject": "google-subject-2",
            "email": "second@example.com",
            "display_name": "Second Hiker",
        },
        now=datetime.now(UTC),
    )
    request = Request({"type": "http", "method": "GET", "path": "/v1/hikes", "headers": []})

    async def authenticated_subject() -> str | None:
        await mobile_api.require_mobile_key(request, authorization=f"Bearer {token}")
        return mobile_api._user_context()["subject"]

    assert asyncio.run(authenticated_subject()) == "google-subject-2"


def test_account_deletion_uses_server_only_rpc() -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    class Result:
        def execute(self):
            return self

    class Client:
        def rpc(self, name, payload):
            calls.append((name, payload))
            return Result()

    delete_mobile_account(Client(), google_subject=" google-subject-3 ")

    assert calls == [
        ("delete_hikejournal_account", {"p_google_subject": "google-subject-3"})
    ]


def test_account_deletion_prefers_canonical_user_id_and_keeps_legacy_wrapper() -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    class Result:
        def execute(self):
            return self

    class Client:
        def rpc(self, name, payload):
            calls.append((name, payload))
            return Result()

    delete_mobile_account(
        Client(),
        user_id=" 89f9e113-0798-4e10-bd9f-120694e085a7 ",
        google_subject="ignored-legacy-subject",
    )

    assert calls == [
        (
            "delete_hikejournal_account_by_user_id",
            {"p_user_id": "89f9e113-0798-4e10-bd9f-120694e085a7"},
        )
    ]


def test_place_library_includes_shared_and_current_users_places_only(monkeypatch) -> None:
    class Repository:
        def list_hike_locations(self):
            return [
                {"id": "florida", "name": "Shared Florida Place"},
                {"id": "mine", "name": "My Place", "owner_subject": "google-subject-1"},
                {"id": "theirs", "name": "Their Place", "owner_subject": "google-subject-2"},
            ]

    monkeypatch.setattr(
        mobile_api,
        "_user_context",
        lambda: {"mode": "google", "subject": "google-subject-1", "email": "hiker@example.com"},
    )

    assert [item["id"] for item in mobile_api._visible_hike_locations(Repository())] == [
        "florida",
        "mine",
    ]


def test_species_process_cache_is_isolated_between_two_durable_subjects(monkeypatch) -> None:
    shared_email = "shared@example.com"
    current = {
        "value": {
            "mode": "google",
            "subject": "subject-one",
            "email": shared_email,
            "auth_configured": True,
        }
    }

    class Repository:
        observation_reads = 0

        def list_hikes(self):
            return [
                {
                    "id": "hike-one",
                    "owner_subject": "subject-one",
                    "owner_email": shared_email,
                },
                {
                    "id": "hike-two",
                    "owner_subject": "subject-two",
                    "owner_email": shared_email,
                },
            ]

        def list_hike_locations(self):
            return []

        def list_hike_location_tags(self):
            return []

        def list_lightweight_observations(self, *, status):
            assert status == "confirmed"
            self.observation_reads += 1
            return [
                {"id": "observation-one", "photo_id": "photo-one", "hike_id": "hike-one"},
                {"id": "observation-two", "photo_id": "photo-two", "hike_id": "hike-two"},
            ]

        def list_photo_records_for_ids(self, photo_ids):
            rows = {
                "photo-one": {"id": "photo-one", "hike_id": "hike-one"},
                "photo-two": {"id": "photo-two", "hike_id": "hike-two"},
            }
            return [rows[photo_id] for photo_id in photo_ids]

    repository = Repository()
    service = SimpleNamespace(repository=repository)
    monkeypatch.setattr(mobile_api, "_species_data_cache", None)
    monkeypatch.setattr(mobile_api, "_user_context", lambda: current["value"])

    first_observations, _, first_hikes = mobile_api._visible_species_data(service)
    current["value"] = {
        "mode": "google",
        "subject": "subject-two",
        "email": shared_email,
        "auth_configured": True,
    }
    second_observations, _, second_hikes = mobile_api._visible_species_data(service)
    current["value"] = {
        "mode": "google",
        "subject": "subject-one",
        "email": shared_email,
        "auth_configured": True,
    }
    cached_first_observations, _, _ = mobile_api._visible_species_data(service)

    assert [row["id"] for row in first_observations] == ["observation-one"]
    assert set(first_hikes) == {"hike-one"}
    assert [row["id"] for row in second_observations] == ["observation-two"]
    assert set(second_hikes) == {"hike-two"}
    assert [row["id"] for row in cached_first_observations] == ["observation-one"]
    assert repository.observation_reads == 2
    assert len(mobile_api._species_data_cache or {}) == 2


def test_field_briefing_fetches_the_selected_life_group(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Repository:
        def list_hike_locations(self):
            return [{"id": "chuluota", "name": "Chuluota Wilderness Area", "lat": 28.63, "lng": -81.12}]

        def list_species_quests(self, **_kwargs):
            return []

    class Discovery:
        def __init__(self, _repository):
            pass

        @staticmethod
        def resolve_area(_repository, area_id, *, locations):
            assert area_id == "chuluota"
            return locations[0]

        def nearby(self, **kwargs):
            captured.update(kwargs)
            return {
                "area": kwargs["area"],
                "period": {"label": "August"},
                "source": {"provider": "iNaturalist"},
                "taxa": [{"taxon_id": 1, "iconic_taxon_name": "Plantae"}],
            }

    service = type("Services", (), {"repository": Repository()})()
    monkeypatch.setattr(mobile_api, "get_services", lambda: service)
    monkeypatch.setattr(mobile_api, "SpeciesDiscoveryService", Discovery)
    monkeypatch.setattr(mobile_api, "_require_discovery_enabled", lambda: None)
    monkeypatch.setattr(mobile_api, "_discovery_collection_data", lambda _svc: ([], {}))
    monkeypatch.setattr(mobile_api, "_visible_hikes", lambda _repository: [])
    monkeypatch.setattr(mobile_api, "_dated_visible_observations", lambda _svc: [])
    monkeypatch.setattr(mobile_api, "_user_context", lambda: {"subject": "google-subject-1", "email": "hiker@example.com"})
    monkeypatch.setattr(
        mobile_api,
        "build_field_briefing",
        lambda **_kwargs: {"sections": [{"title": "Plants", "items": []}]},
    )

    payload = mobile_api.get_field_briefing(
        location_id="chuluota",
        target_date=date(2026, 8, 18),
        radius_km=10,
        iconic_taxon="Plantae",
        limit=18,
    )

    assert captured["iconic_taxon"] == "Plantae"
    assert captured["limit"] == 50
    assert payload["sections"][0]["title"] == "Plants"
