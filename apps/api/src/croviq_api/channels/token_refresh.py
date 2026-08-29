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


async def _save_connection_state(
    connection: YouTubeConnection,
    youtube_repo: YouTubeConnectionRepository,
    *,
    status: str,
    error_message: str | None,
) -> YouTubeConnection:
    return await youtube_repo.save_connection(
        connection.model_copy(
            update={
                "status": status,
                "error_message": error_message,
            }
        )
    )



async def refresh_youtube_access_token_if_needed(
    connection: YouTubeConnection,
    youtube_repo: YouTubeConnectionRepository,
    buffer_seconds: int = 300,
) -> tuple[str, YouTubeConnection]:
    """Return a usable access token, refreshing and persisting connection state when needed."""
    if connection.status == "reauth_required":
        raise YouTubeReauthRequiredError(
            connection.error_message
            or "YouTube authorization is no longer valid. Please reconnect your YouTube channel."
        )

    now = datetime.now(UTC)
    is_strictly_expired = bool(
        connection.token_expiry and (connection.token_expiry - now).total_seconds() <= 0
    )

    if connection.token_expiry and (connection.token_expiry - now).total_seconds() > buffer_seconds:
        return connection.access_token, connection

    if not connection.refresh_token:
        if is_strictly_expired:
            error_message = (
                "YouTube access token has expired and no refresh token is stored. "
                "Please reconnect your YouTube channel."
            )
            await _save_connection_state(
                connection,
                youtube_repo,
                status="reauth_required",
                error_message=error_message,
            )
            raise YouTubeReauthRequiredError(error_message)
        logger.warning("YouTube token expiring soon but no refresh token is available.")
        return connection.access_token, connection

    client_id = get_settings().google_oauth_client_id
    client_secret = get_settings().google_oauth_client_secret
    if not client_id or not client_secret:
        if is_strictly_expired:
            error_message = (
                "Google OAuth client credentials are not configured to refresh expired token. "
                "Please reconnect your YouTube channel."
            )
            await _save_connection_state(
                connection,
                youtube_repo,
                status="reauth_required",
                error_message=error_message,
            )
            raise YouTubeReauthRequiredError(error_message)
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
                        "status": "connected",
                        "error_message": None,
                    }
                )
                saved = await youtube_repo.save_connection(updated_conn)
                return new_access, saved

            error_detail = token_resp.text
            error_code: str | None = None
            try:
                err_json = token_resp.json()
                if isinstance(err_json, dict):
                    raw_error_code = err_json.get("error")
                    if isinstance(raw_error_code, str):
                        error_code = raw_error_code
                    error_detail = (
                        err_json.get("error_description")
                        or raw_error_code
                        or token_resp.text
                    )
            except Exception:
                pass

            logger.warning(
                "YouTube token refresh returned status %s: %s",
                token_resp.status_code,
                error_detail,
            )
            permanent_auth_error = token_resp.status_code == 401 or (
                token_resp.status_code == 400
                and (
                    error_code in {"invalid_grant", "invalid_client", "unauthorized_client"}
                    or "revoked" in str(error_detail).lower()
                )
            )
            if permanent_auth_error:
                error_message = (
                    "YouTube authorization failed during token refresh "
                    f"(HTTP {token_resp.status_code}: {error_detail}). "
                    "Please reconnect your YouTube channel."
                )
                await _save_connection_state(
                    connection,
                    youtube_repo,
                    status="reauth_required",
                    error_message=error_message,
                )
                raise YouTubeReauthRequiredError(error_message)

            if token_resp.status_code >= 500 or token_resp.status_code == 429:
                error_message = (
                    "Google OAuth is temporarily unavailable while refreshing the YouTube token "
                    f"(HTTP {token_resp.status_code}: {error_detail})."
                )
            else:
                error_message = (
                    f"YouTube token refresh failed (HTTP {token_resp.status_code}: {error_detail})."
                )

            if is_strictly_expired:
                error_message = (
                    f"{error_message} The current access token is expired; try again later."
                )
                await _save_connection_state(
                    connection,
                    youtube_repo,
                    status="reauth_required",
                    error_message=error_message,
                )
                raise YouTubeReauthRequiredError(error_message)

            degraded_connection = await _save_connection_state(
                connection,
                youtube_repo,
                status="connected",
                error_message=error_message,
            )
            return degraded_connection.access_token, degraded_connection
    except YouTubeReauthRequiredError:
        raise
    except Exception as exc:
        logger.warning("Token refresh call failed: %s", exc)
        error_message = (
            "Google OAuth is temporarily unavailable due to a network/server error while "
            f"refreshing the YouTube token: {exc}"
        )
        if is_strictly_expired:
            error_message = (
                f"{error_message}. The current access token is expired; try again later."
            )
            await _save_connection_state(
                connection,
                youtube_repo,
                status="reauth_required",
                error_message=error_message,
            )
            raise YouTubeReauthRequiredError(error_message) from exc

        degraded_connection = await _save_connection_state(
            connection,
            youtube_repo,
            status="connected",
            error_message=error_message,
        )
        return degraded_connection.access_token, degraded_connection
