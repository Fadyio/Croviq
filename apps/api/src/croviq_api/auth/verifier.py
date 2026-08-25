"""Token verification interface and Firebase Admin implementation."""

from abc import ABC, abstractmethod
from typing import Any
import firebase_admin
from firebase_admin import auth, exceptions as firebase_exceptions

from croviq_api.auth.exceptions import ExpiredTokenError, InvalidTokenError
from croviq_api.config import get_settings


class TokenVerifier(ABC):
    """Abstract interface for Identity Platform / Firebase ID token verification."""

    @abstractmethod
    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify the ID token and return the decoded claims dict.

        Raises:
            ExpiredTokenError: If the token is valid but has expired.
            InvalidTokenError: If signature, audience, issuer, or format is invalid.
        """
        ...


class FirebaseTokenVerifier(TokenVerifier):
    """Production verifier using Firebase Admin SDK with Application Default Credentials (ADC)."""

    def __init__(self, project_id: str | None = None) -> None:
        self._project_id = project_id
        self._ensure_firebase_initialized()

    def _ensure_firebase_initialized(self) -> None:
        """Initialize Firebase Admin default app if not already initialized."""
        if not firebase_admin._apps:
            options: dict[str, Any] = {}
            if self._project_id:
                options["projectId"] = self._project_id
            firebase_admin.initialize_app(options=options if options else None)

    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify Identity Platform ID token using Firebase Admin SDK.

        Validates signature, expiration, issuer, audience, and public JWKS certs.
        """
        if not token or not isinstance(token, str) or not token.strip():
            raise InvalidTokenError("Empty or invalid token format")

        try:
            # Firebase Admin SDK verify_id_token validates signature, expiration, issuer, audience
            return auth.verify_id_token(token.strip(), check_revoked=False)
        except auth.ExpiredIdTokenError as e:
            raise ExpiredTokenError(f"Token has expired: {e}") from e
        except (
            auth.InvalidIdTokenError,
            auth.RevokedIdTokenError,
            auth.CertificateFetchError,
            auth.UserDisabledError,
        ) as e:
            raise InvalidTokenError(f"Token verification failed: {e}") from e
        except (ValueError, firebase_exceptions.FirebaseError) as e:
            raise InvalidTokenError(f"Firebase token verification failed: {e}") from e
        except Exception as e:
            raise InvalidTokenError("Token verification error") from e


def get_token_verifier() -> TokenVerifier:
    """FastAPI dependency provider for TokenVerifier."""
    settings = get_settings()
    return FirebaseTokenVerifier(project_id=settings.gcp_project_id)
