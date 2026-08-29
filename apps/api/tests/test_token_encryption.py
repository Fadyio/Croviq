"""Unit tests for YouTube OAuth Token Envelope Encryption using Google Tink AEAD."""

import base64
from datetime import UTC, datetime, timedelta
import pytest

from unittest.mock import AsyncMock, patch
import httpx

from croviq_api.channels.token_refresh import (
    YouTubeReauthRequiredError,
    refresh_youtube_access_token_if_needed,
)

from croviq_api.channels.token_encryption import (
    LocalTinkOAuthTokenEncryptor,
    OAuthTokenEncryptor,
    TokenPayload,
    build_record_aad,
)
from croviq_api.channels.youtube_repository import (
    FirestoreYouTubeConnectionRepository,
    InMemoryYouTubeConnectionRepository,
    YouTubeConnection,
    YouTubeConnectionRecord,
)


@pytest.fixture
def encryptor() -> OAuthTokenEncryptor:
    return LocalTinkOAuthTokenEncryptor()


def test_token_payload_model() -> None:
    payload = TokenPayload(
        access_token="mock_access_token_12345",
        refresh_token="mock_refresh_token_67890",
        token_type="Bearer",
    )
    assert payload.access_token == "mock_access_token_12345"
    assert payload.refresh_token == "mock_refresh_token_67890"
    assert payload.token_type == "Bearer"


def test_tink_aead_encrypt_decrypt_roundtrip(encryptor: OAuthTokenEncryptor) -> None:
    payload = TokenPayload(
        access_token="mock_sample_access_token",
        refresh_token="mock_sample_refresh_token",
    )
    workspace_id = "ws_test_01"
    user_id = "usr_creator_01"

    ciphertext_b64 = encryptor.encrypt_tokens(
        payload,
        workspace_id=workspace_id,
        user_id=user_id,
    )

    # Ciphertext must be valid base64 and non-empty
    raw_cipher = base64.b64decode(ciphertext_b64)
    assert len(raw_cipher) > 32
    assert "sample_access_token" not in ciphertext_b64
    assert "sample_refresh_token" not in ciphertext_b64

    # Decrypt with correct AAD
    decrypted = encryptor.decrypt_tokens(
        ciphertext_b64,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    assert decrypted.access_token == payload.access_token
    assert decrypted.refresh_token == payload.refresh_token
    assert decrypted.token_type == "Bearer"


def test_tink_aead_aad_tamper_protection(encryptor: OAuthTokenEncryptor) -> None:
    payload = TokenPayload(
        access_token="mock_secret_token",
        refresh_token="mock_secret_refresh",
    )
    ciphertext_b64 = encryptor.encrypt_tokens(
        payload,
        workspace_id="ws_legit",
        user_id="usr_legit",
    )

    # 1. Swapping workspace_id must fail decryption
    with pytest.raises(Exception):
        encryptor.decrypt_tokens(
            ciphertext_b64,
            workspace_id="ws_attacker",
            user_id="usr_legit",
        )

    # 2. Swapping user_id must fail decryption
    with pytest.raises(Exception):
        encryptor.decrypt_tokens(
            ciphertext_b64,
            workspace_id="ws_legit",
            user_id="usr_attacker",
        )

    # 3. Altering ciphertext bytes must fail decryption (AEAD integrity)
    raw = bytearray(base64.b64decode(ciphertext_b64))
    raw[10] ^= 0xFF
    tampered_b64 = base64.b64encode(raw).decode("utf-8")
    with pytest.raises(Exception):
        encryptor.decrypt_tokens(
            tampered_b64,
            workspace_id="ws_legit",
            user_id="usr_legit",
        )


def test_refresh_token_preservation_when_none() -> None:
    """When refreshing tokens and Google returns null refresh_token, preserve existing."""
    existing_payload = TokenPayload(
        access_token="old_access_token",
        refresh_token="permanent_refresh_token",
    )
    new_access_token = "new_access_token_v2"
    new_refresh_token = None  # Google did not return a new refresh token

    updated_payload = TokenPayload(
        access_token=new_access_token,
        refresh_token=new_refresh_token or existing_payload.refresh_token,
    )
    assert updated_payload.access_token == "new_access_token_v2"
    assert updated_payload.refresh_token == "permanent_refresh_token"


@pytest.mark.asyncio
async def test_in_memory_repository_stores_and_retrieves_encrypted_connection(
    encryptor: OAuthTokenEncryptor,
) -> None:
    repo = InMemoryYouTubeConnectionRepository(encryptor=encryptor)
    now = datetime.now(UTC)
    conn = YouTubeConnection(
        workspace_id="ws_mem_01",
        user_id="usr_mem_01",
        channel_id="UC_test_channel_01",
        channel_title="Test YouTube Channel",
        avatar_url="https://example.com/avatar.png",
        subscriber_count=12500,
        access_token="mock_live_access_test",
        refresh_token="mock_live_refresh_test",
        token_expiry=now,
        scopes=["https://www.googleapis.com/auth/youtube.readonly"],
        connected_at=now,
        last_sync_at=now,
    )

    saved = await repo.save_connection(conn)
    assert saved.channel_id == "UC_test_channel_01"

    # Verify repository storage contains no plaintext tokens
    raw_record = repo.get_raw_record("ws_mem_01")
    assert raw_record is not None
    assert isinstance(raw_record, YouTubeConnectionRecord)
    assert raw_record.encrypted_token_payload != ""
    assert "live_access_test" not in raw_record.encrypted_token_payload
    assert "live_refresh_test" not in raw_record.encrypted_token_payload

    # Retrieved connection is decrypted in memory
    retrieved = await repo.get_connection("ws_mem_01")
    assert retrieved is not None
    assert retrieved.access_token == "mock_live_access_test"
    assert retrieved.refresh_token == "mock_live_refresh_test"

    # Disconnect deletes record
    deleted = await repo.delete_connection("ws_mem_01")
    assert deleted is True
    assert await repo.get_connection("ws_mem_01") is None


@pytest.mark.asyncio
async def test_refresh_youtube_access_token_unexpired_returns_current(
    encryptor: OAuthTokenEncryptor,
) -> None:
    repo = InMemoryYouTubeConnectionRepository(encryptor=encryptor)
    now = datetime.now(UTC)
    conn = YouTubeConnection(
        workspace_id="ws_unexpired",
        user_id="usr_01",
        channel_id="UC_test",
        channel_title="Test Channel",
        subscriber_count=50000,
        access_token="valid_active_access_token",
        refresh_token="valid_refresh_token",
        token_expiry=now + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/youtube.readonly"],
        connected_at=now,
        last_sync_at=now,
    )
    await repo.save_connection(conn)
    token, updated_conn = await refresh_youtube_access_token_if_needed(conn, repo)
    assert token == "valid_active_access_token"
    assert updated_conn.token_expiry == conn.token_expiry


@pytest.mark.asyncio
async def test_refresh_youtube_access_token_expired_without_credentials_raises_reauth_required(
    encryptor: OAuthTokenEncryptor,
) -> None:
    repo = InMemoryYouTubeConnectionRepository(encryptor=encryptor)
    now = datetime.now(UTC)
    conn = YouTubeConnection(
        workspace_id="ws_expired",
        user_id="usr_01",
        channel_id="UC_test",
        channel_title="Test Channel",
        subscriber_count=50000,
        access_token="old_expired_access_token",
        refresh_token="some_refresh_token",
        token_expiry=now - timedelta(minutes=10),
        scopes=["https://www.googleapis.com/auth/youtube.readonly"],
        connected_at=now - timedelta(days=1),
        last_sync_at=now - timedelta(days=1),
    )
    await repo.save_connection(conn)

    with pytest.raises(YouTubeReauthRequiredError) as exc_info:
        await refresh_youtube_access_token_if_needed(conn, repo)
    assert "Google OAuth client credentials are not configured" in str(exc_info.value)
    assert "Please reconnect" in str(exc_info.value)


@pytest.mark.asyncio
async def test_refresh_youtube_access_token_expired_without_refresh_token_raises_reauth_required(
    encryptor: OAuthTokenEncryptor,
) -> None:
    repo = InMemoryYouTubeConnectionRepository(encryptor=encryptor)
    now = datetime.now(UTC)
    conn = YouTubeConnection(
        workspace_id="ws_no_refresh",
        user_id="usr_01",
        channel_id="UC_test",
        channel_title="Test Channel",
        subscriber_count=50000,
        access_token="old_expired_access_token",
        refresh_token=None,
        token_expiry=now - timedelta(minutes=10),
        scopes=["https://www.googleapis.com/auth/youtube.readonly"],
        connected_at=now - timedelta(days=1),
        last_sync_at=now - timedelta(days=1),
    )
    await repo.save_connection(conn)

    with pytest.raises(YouTubeReauthRequiredError) as exc_info:
        await refresh_youtube_access_token_if_needed(conn, repo)
    assert "no refresh token is stored" in str(exc_info.value)
    assert "Please reconnect" in str(exc_info.value)


@pytest.mark.asyncio
async def test_refresh_youtube_access_token_expired_successful_refresh(
    encryptor: OAuthTokenEncryptor,
) -> None:
    repo = InMemoryYouTubeConnectionRepository(encryptor=encryptor)
    now = datetime.now(UTC)
    conn = YouTubeConnection(
        workspace_id="ws_refresh_ok",
        user_id="usr_01",
        channel_id="UC_test",
        channel_title="Test Channel",
        subscriber_count=50000,
        access_token="old_expired_access_token",
        refresh_token="valid_refresh_token_123",
        token_expiry=now - timedelta(minutes=10),
        scopes=["https://www.googleapis.com/auth/youtube.readonly"],
        connected_at=now - timedelta(days=1),
        last_sync_at=now - timedelta(days=1),
    )
    await repo.save_connection(conn)

    mock_response = httpx.Response(
        status_code=200,
        json={
            "access_token": "newly_refreshed_access_token_xyz",
            "expires_in": 3600,
            "token_type": "Bearer",
        },
        request=httpx.Request("POST", "https://oauth2.googleapis.com/token"),
    )

    with patch("croviq_api.channels.token_refresh.get_settings") as mock_settings:
        mock_settings.return_value.google_oauth_client_id = "test-client-id"
        mock_settings.return_value.google_oauth_client_secret = "test-client-secret"
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            new_token, updated_conn = await refresh_youtube_access_token_if_needed(conn, repo)

            assert new_token == "newly_refreshed_access_token_xyz"
            assert updated_conn.access_token == "newly_refreshed_access_token_xyz"
            assert updated_conn.token_expiry is not None
            assert updated_conn.token_expiry > now

            # Verify persistence in encrypted repository
            persisted = await repo.get_connection("ws_refresh_ok")
            assert persisted is not None
            assert persisted.access_token == "newly_refreshed_access_token_xyz"


@pytest.mark.asyncio
async def test_refresh_youtube_access_token_expired_rejected_by_google_raises_reauth_required(
    encryptor: OAuthTokenEncryptor,
) -> None:
    repo = InMemoryYouTubeConnectionRepository(encryptor=encryptor)
    now = datetime.now(UTC)
    conn = YouTubeConnection(
        workspace_id="ws_revoked",
        user_id="usr_01",
        channel_id="UC_test",
        channel_title="Test Channel",
        subscriber_count=50000,
        access_token="old_expired_access_token",
        refresh_token="revoked_refresh_token",
        token_expiry=now - timedelta(minutes=10),
        scopes=["https://www.googleapis.com/auth/youtube.readonly"],
        connected_at=now - timedelta(days=1),
        last_sync_at=now - timedelta(days=1),
    )
    await repo.save_connection(conn)

    mock_response = httpx.Response(
        status_code=400,
        json={"error": "invalid_grant", "error_description": "Token has been expired or revoked."},
        request=httpx.Request("POST", "https://oauth2.googleapis.com/token"),
    )

    with patch("croviq_api.channels.token_refresh.get_settings") as mock_settings:
        mock_settings.return_value.google_oauth_client_id = "test-client-id"
        mock_settings.return_value.google_oauth_client_secret = "test-client-secret"
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(YouTubeReauthRequiredError) as exc_info:
                await refresh_youtube_access_token_if_needed(conn, repo)
            assert "Token has been expired or revoked" in str(exc_info.value)
            assert "Please reconnect" in str(exc_info.value)
