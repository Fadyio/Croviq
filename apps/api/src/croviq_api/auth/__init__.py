"""Croviq API Authentication Package."""

from croviq_api.auth.dependencies import get_current_principal, get_current_user
from croviq_api.auth.exceptions import (
    AuthError,
    DemoAccessRestrictedError,
    ExpiredTokenError,
    InvalidTokenError,
    MalformedHeaderError,
    MissingTokenError,
)
from croviq_api.auth.principal import AuthenticatedPrincipal
from croviq_api.auth.routes import router as auth_router
from croviq_api.auth.verifier import FirebaseTokenVerifier, TokenVerifier, get_token_verifier

__all__ = [
    "AuthError",
    "AuthenticatedPrincipal",
    "DemoAccessRestrictedError",
    "ExpiredTokenError",
    "FirebaseTokenVerifier",
    "InvalidTokenError",
    "MalformedHeaderError",
    "MissingTokenError",
    "TokenVerifier",
    "auth_router",
    "get_current_principal",
    "get_current_user",
    "get_token_verifier",
]
