"""YouTube OAuth Token Refresh Service for Channel Intelligence and Publishing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging

import httpx

from croviq_api.channels.youtube_provider import YOUTUBE_OAUTH_TOKEN_URL
from croviq_api.channels.youtube_repository import YouTubeConnection, YouTubeConnectionRepository
from croviq_api.config import get_settings

logger = logging.getLogger(__name__)

class YouTubeReauthRequiredError(Exception):
    """Raised when YouTube access token is expired and cannot be refreshed without user re-authorization."""


async def refresh_youtube_access_token_if_needed(
    connection: YouTubeConnection,
    youtube_repo: YouTubeConnectionRepository,
    buffer_seconds: int = 300,
) -> tuple[str, YouTubeConnection]:
    """Verify and refresh YouTube access token if expired, updating secure repository.

    If the token is valid, returns the active token.
    If the token is expired or expiring soon, attempts refresh via Google OAuth endpoint.
    If the token is already expired and cannot be refreshed (missing credentials, missing refresh token,
    revoked authorization, or network failure), raises YouTubeReauthRequiredError.
    """
    now = datetime.now(UTC)
    is_strictly_expired = bool(
        connection.token_expiry and (connection.token_expiry - now).total_seconds() <= 0
    )

    if connection.token_expiry and (connection.token_expiry - now).total_seconds() > buffer_seconds:
        return connection.access_token, connection

    if not connection.refresh_token:
        if is_strictly_expired:
            raise YouTubeReauthRequiredError(
                "YouTube access token has expired and no refresh token is stored. Please reconnect your YouTube channel."
            )
        logger.warning("YouTube token expiring soon but no refresh token is available.")
        return connection.access_token, connection

    client_id = get_settings().google_oauth_client_id
    client_secret = get_settings().google_oauth_client_secret
    if not client_id or not client_secret:
        if is_strictly_expired:
            raise YouTubeReauthRequiredError(
                "Google OAuth client credentials are not configured to refresh expired token. Please reconnect your YouTube channel."
            )
        logger.warning("Google OAuth client credentials missing for pre-expiry token refresh.")
        return connection.access_token, connection

    try:
        async with httpx.AsyncClient(timeout=20) as http_client:
            token_resp = await http_client.post(
                YOUTUBE_OAUTH_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": connection.refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            if token_resp.status_code == 200:
                token_data = token_resp.json()
                new_access = token_data.get("access_token", connection.access_token)
                new_refresh = token_data.get("refresh_token") or connection.refresh_token
                expires_in = token_data.get("expires_in", 3600)
                updated_conn = connection.model_copy(
                    update={
                        "access_token": new_access,
                        "refresh_token": new_refresh,
                        "token_expiry": now + timedelta(seconds=expires_in),
                        "last_sync_at": now,
                    }
                )
                saved = await youtube_repo.save_connection(updated_conn)
                return new_access, saved

            error_detail = token_resp.text
            try:
                err_json = token_resp.json()
                error_detail = (
                    err_json.get("error_description")
                    or err_json.get("error")
                    or token_resp.text
                )
            except Exception:
                pass

            logger.warning(
                "YouTube token refresh returned status %s: %s",
                token_resp.status_code,
                error_detail,
            )
            if is_strictly_expired:
                raise YouTubeReauthRequiredError(
                    f"YouTube token refresh failed (HTTP {token_resp.status_code}: {error_detail}). Please reconnect your YouTube channel."
                )
    except YouTubeReauthRequiredError:
        raise
    except Exception as exc:
        logger.warning("Token refresh call failed: %s", exc)
        if is_strictly_expired:
            raise YouTubeReauthRequiredError(
                f"Failed to refresh expired YouTube token due to network/server error: {exc}. Please reconnect your YouTube channel."
            ) from exc

    return connection.access_token, connection
