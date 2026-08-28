"""YouTube OAuth Token Envelope Encryption using Google Tink AEAD and Cloud KMS."""

from __future__ import annotations

from abc import ABC, abstractmethod
import base64
import json
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
import tink
from tink import aead
from tink.integration import gcpkms

from croviq_api.config import get_settings

logger = logging.getLogger(__name__)

# Register Tink AEAD primitives once
aead.register()

DEFAULT_ENCRYPTION_SCHEMA_VERSION = "v1"
DEFAULT_KMS_KEY_URI = (
    "gcp-kms://projects/croviq-506602/locations/us-central1/keyRings/croviq-keyring/cryptoKeys/youtube-oauth-kek"
)


class TokenPayload(BaseModel):
    """Internal plaintext token structure encrypted as a single versioned payload."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    access_token: str = Field(..., min_length=1)
    refresh_token: str | None = None
    token_type: str = "Bearer"


def build_record_aad(
    *,
    workspace_id: str,
    user_id: str,
    connection_id: str = "youtube_connection",
    schema_version: str = DEFAULT_ENCRYPTION_SCHEMA_VERSION,
) -> bytes:
    """Build canonical Authenticated Associated Data (AAD) for record binding.

    Prevents ciphertext swap attacks across workspaces, users, or connections.
    """
    return f"{workspace_id}:{user_id}:{connection_id}:{schema_version}".encode("utf-8")


class OAuthTokenEncryptor(ABC):
    """Abstract contract for envelope AEAD token encryption and decryption."""

    @abstractmethod
    def encrypt_tokens(
        self,
        payload: TokenPayload,
        *,
        workspace_id: str,
        user_id: str,
        connection_id: str = "youtube_connection",
        schema_version: str = DEFAULT_ENCRYPTION_SCHEMA_VERSION,
    ) -> str:
        """Encrypt token payload into an opaque base64-encoded ciphertext."""
        pass

    @abstractmethod
    def decrypt_tokens(
        self,
        ciphertext_b64: str,
        *,
        workspace_id: str,
        user_id: str,
        connection_id: str = "youtube_connection",
        schema_version: str = DEFAULT_ENCRYPTION_SCHEMA_VERSION,
    ) -> TokenPayload:
        """Decrypt opaque ciphertext and return verified token payload."""
        pass


class TinkKmsOAuthTokenEncryptor(OAuthTokenEncryptor):
    """Production envelope AEAD encryptor using Google Tink backed by Cloud KMS KEK."""

    def __init__(self, key_uri: str | None = None) -> None:
        self.key_uri = key_uri or DEFAULT_KMS_KEY_URI
        self._envelope_aead: Any = None

    def _get_envelope_aead(self) -> Any:
        if self._envelope_aead is None:
            client = gcpkms.GcpKmsClient(key_uri=self.key_uri, credentials_path="")
            kms_aead = client.get_aead(self.key_uri)
            self._envelope_aead = aead.KmsEnvelopeAead(
                aead.aead_key_templates.AES256_GCM, kms_aead
            )
        return self._envelope_aead

    def encrypt_tokens(
        self,
        payload: TokenPayload,
        *,
        workspace_id: str,
        user_id: str,
        connection_id: str = "youtube_connection",
        schema_version: str = DEFAULT_ENCRYPTION_SCHEMA_VERSION,
    ) -> str:
        aad = build_record_aad(
            workspace_id=workspace_id,
            user_id=user_id,
            connection_id=connection_id,
            schema_version=schema_version,
        )
        plaintext_bytes = payload.model_dump_json().encode("utf-8")
        envelope = self._get_envelope_aead()
        ciphertext_bytes = envelope.encrypt(plaintext_bytes, aad)
        return base64.b64encode(ciphertext_bytes).decode("utf-8")

    def decrypt_tokens(
        self,
        ciphertext_b64: str,
        *,
        workspace_id: str,
        user_id: str,
        connection_id: str = "youtube_connection",
        schema_version: str = DEFAULT_ENCRYPTION_SCHEMA_VERSION,
    ) -> TokenPayload:
        aad = build_record_aad(
            workspace_id=workspace_id,
            user_id=user_id,
            connection_id=connection_id,
            schema_version=schema_version,
        )
        ciphertext_bytes = base64.b64decode(ciphertext_b64.encode("utf-8"))
        envelope = self._get_envelope_aead()
        plaintext_bytes = envelope.decrypt(ciphertext_bytes, aad)
        data = json.loads(plaintext_bytes.decode("utf-8"))
        return TokenPayload.model_validate(data)


class LocalTinkOAuthTokenEncryptor(OAuthTokenEncryptor):
    """Local / Test Tink AEAD encryptor using an in-memory keyset for deterministic testing."""

    def __init__(self) -> None:
        self._keyset_handle = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
        self._primitive = self._keyset_handle.primitive(aead.Aead)

    def encrypt_tokens(
        self,
        payload: TokenPayload,
        *,
        workspace_id: str,
        user_id: str,
        connection_id: str = "youtube_connection",
        schema_version: str = DEFAULT_ENCRYPTION_SCHEMA_VERSION,
    ) -> str:
        aad = build_record_aad(
            workspace_id=workspace_id,
            user_id=user_id,
            connection_id=connection_id,
            schema_version=schema_version,
        )
        plaintext_bytes = payload.model_dump_json().encode("utf-8")
        ciphertext_bytes = self._primitive.encrypt(plaintext_bytes, aad)
        return base64.b64encode(ciphertext_bytes).decode("utf-8")

    def decrypt_tokens(
        self,
        ciphertext_b64: str,
        *,
        workspace_id: str,
        user_id: str,
        connection_id: str = "youtube_connection",
        schema_version: str = DEFAULT_ENCRYPTION_SCHEMA_VERSION,
    ) -> TokenPayload:
        aad = build_record_aad(
            workspace_id=workspace_id,
            user_id=user_id,
            connection_id=connection_id,
            schema_version=schema_version,
        )
        ciphertext_bytes = base64.b64decode(ciphertext_b64.encode("utf-8"))
        plaintext_bytes = self._primitive.decrypt(ciphertext_bytes, aad)
        data = json.loads(plaintext_bytes.decode("utf-8"))
        return TokenPayload.model_validate(data)


# Alias for backward compatibility
InvertedLocalTinkOAuthTokenEncryptor = LocalTinkOAuthTokenEncryptor

_global_encryptor: OAuthTokenEncryptor | None = None


def get_oauth_token_encryptor() -> OAuthTokenEncryptor:
    """Factory returning the configured OAuth token encryptor."""
    global _global_encryptor
    if _global_encryptor is None:
        settings = get_settings()
        if settings.is_production or settings.gcp_project_id:
            try:
                _global_encryptor = TinkKmsOAuthTokenEncryptor()
            except Exception as e:
                logger.warning(
                    "Cloud KMS Tink encryptor initialization failed, using local encryptor: %s",
                    e,
                )
                _global_encryptor = LocalTinkOAuthTokenEncryptor()
        else:
            _global_encryptor = LocalTinkOAuthTokenEncryptor()
    return _global_encryptor


def set_oauth_token_encryptor(encryptor: OAuthTokenEncryptor | None) -> None:
    """Override the global token encryptor for tests."""
    global _global_encryptor
    _global_encryptor = encryptor
