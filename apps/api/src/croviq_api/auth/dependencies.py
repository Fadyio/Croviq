"""FastAPI authentication dependencies and Bearer token extraction."""

from typing import Annotated
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from croviq_api.auth.exceptions import (
    AuthError,
    DemoAccessRestrictedError,
    ExpiredTokenError,
    InvalidTokenError,
    MalformedHeaderError,
    MissingTokenError,
)
from croviq_api.auth.logging import log_auth_event
from croviq_api.auth.principal import AuthenticatedPrincipal
from croviq_api.auth.verifier import TokenVerifier, get_token_verifier
from croviq_api.config import get_settings
from croviq_domain.user import User
# HTTPBearer security scheme for OpenAPI documentation
http_bearer = HTTPBearer(
    auto_error=False,
    description="Identity Platform / Firebase ID Token: 'Bearer <TOKEN>'",
)


def get_current_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
) -> AuthenticatedPrincipal:
    """Extract and verify Bearer token from Authorization header.

    Validates header presence, Bearer format, and token claims against Identity Platform.
    Emits structured JSON logs for audit trails without leaking sensitive tokens.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    auth_header = request.headers.get("Authorization")

    # 1. Missing Authorization header
    if not auth_header or not auth_header.strip():
        log_auth_event(
            event_type="auth.verification_failed",
            status=status.HTTP_401_UNAUTHORIZED,
            request_id=request_id,
            error_code="missing_authorization_header",
            message="Missing Authorization header",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Malformed header check: must be strictly 'Bearer <token>'
    raw_header = auth_header.strip()
    parts = raw_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        log_auth_event(
            event_type="auth.verification_failed",
            status=status.HTTP_401_UNAUTHORIZED,
            request_id=request_id,
            error_code="malformed_authorization_header",
            message="Malformed Authorization header",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1].strip()

    # 3. Verify token with verifier
    try:
        claims = verifier.verify_token(token)
        principal = AuthenticatedPrincipal.from_claims(claims)
        log_auth_event(
            event_type="auth.login_verified",
            status=status.HTTP_200_OK,
            request_id=request_id,
            user_id=principal.uid,
            authenticated_user_id=principal.uid,
            message=f"Identity token verified for user {principal.uid}",
        )
    except ExpiredTokenError:
        log_auth_event(
            event_type="auth.verification_failed",
            status=status.HTTP_401_UNAUTHORIZED,
            request_id=request_id,
            error_code="expired_token",
            message="Token has expired",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (InvalidTokenError, AuthError, Exception):
        log_auth_event(
            event_type="auth.verification_failed",
            status=status.HTTP_401_UNAUTHORIZED,
            request_id=request_id,
            error_code="invalid_token",
            message="Invalid token",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. Enforce demo access policy
    settings = get_settings()
    is_allowed = False
    if principal.email:
        normalized_email = principal.email.strip().lower()
        if normalized_email in settings.allowed_emails:
            is_allowed = True

    if not is_allowed:
        log_auth_event(
            event_type="auth.access_denied",
            status=status.HTTP_403_FORBIDDEN,
            request_id=request_id,
            user_id=principal.uid,
            authenticated_user_id=principal.uid,
            error_code="demo_access_restricted",
            message="This Croviq demo is restricted to an approved account.",
        )
        raise DemoAccessRestrictedError(
            message="This Croviq demo is restricted to an approved account.",
            error_code="demo_access_restricted",
        )

    log_auth_event(
        event_type="auth.access_allowed",
        status=status.HTTP_200_OK,
        request_id=request_id,
        user_id=principal.uid,
        authenticated_user_id=principal.uid,
        message=f"Authenticated user {principal.uid}",
    )
    return principal


def get_current_user(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> User:
    """Resolve the canonical User entity from verified principal."""
    return principal.to_domain_user()
