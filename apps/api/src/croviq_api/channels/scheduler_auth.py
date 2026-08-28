"""Cloud Scheduler OIDC Authentication and Principal Verification."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from croviq_api.config import get_settings

logger = logging.getLogger(__name__)

# Reusable HTTP request adapter for Google public key caching
_google_request_adapter = google_requests.Request()


async def verify_scheduler_identity(request: Request) -> str:
    """Verify that incoming request carries a valid Google OIDC token from the dedicated Cloud Scheduler identity.

    Fails closed if the token is missing, invalid, expired, from the wrong issuer, or
    from an unauthorized principal (e.g. normal creator or wrong service account).
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header for Cloud Scheduler.",
        )

    raw_token = auth_header.split(" ", 1)[1].strip()
    settings = get_settings()
    expected_email = settings.scheduler_service_account_email or (
        f"croviq-scheduler@{settings.gcp_project_id}.iam.gserviceaccount.com"
        if settings.gcp_project_id
        else "croviq-scheduler@croviq-506602.iam.gserviceaccount.com"
    )
    expected_audience = settings.cloud_run_service_url or "https://croviq-api-uhz5nod4gq-uc.a.run.app"

    # Local test bypass only in non-production test environments when mock token is passed
    if not settings.is_production and (
        raw_token.startswith("mock-scheduler-") or raw_token.startswith("test-scheduler-")
    ):
        if raw_token in {"mock-scheduler-valid", "test-scheduler-valid"}:
            return expected_email
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unauthorized test scheduler identity in token: {raw_token}",
        )

    try:
        # Verify token signature and expiration against Google's live public certificates
        claim: dict[str, Any] = id_token.verify_oauth2_token(
            raw_token,
            _google_request_adapter,
            audience=expected_audience,
        )

        email = claim.get("email")
        email_verified = claim.get("email_verified", False)
        issuer = claim.get("iss")

        if issuer not in {"https://accounts.google.com", "accounts.google.com"}:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid OIDC token issuer: {issuer}",
            )

        if not email_verified or email != expected_email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Expected scheduler service account {expected_email}, got {email}.",
            )

        return str(email)

    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Cloud Scheduler OIDC verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google OIDC identity token: {exc}",
        ) from exc
