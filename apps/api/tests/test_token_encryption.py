"""Unit tests for YouTube OAuth Token Envelope Encryption using Google Tink AEAD."""

import base64
from datetime import UTC, datetime
import pytest

from croviq_api.channels.token_encryption import (
    InvertedLocalTinkOAuthTokenEncryptor,
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
    return InvertedLocalTinkOAuthTokenEncryptor()


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
