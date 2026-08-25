"""Croviq API Authentication Package."""

from croviq_api.auth.dependencies import get_current_principal, get_current_user
from croviq_api.auth.principal import AuthenticatedPrincipal
from croviq_api.auth.routes import router as auth_router
from croviq_api.auth.verifier import FirebaseTokenVerifier, TokenVerifier, get_token_verifier

__all__ = [
    "AuthenticatedPrincipal",
    "FirebaseTokenVerifier",
    "TokenVerifier",
    "auth_router",
    "get_current_principal",
    "get_current_user",
    "get_token_verifier",
]
