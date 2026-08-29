"""Secret and credential redaction for structured logging."""

import re
from typing import Any

# Specific key names that contain credentials and should be masked
EXACT_SENSITIVE_KEYS: frozenset[str] = frozenset(
    [
        "password",
        "passwd",
        "secret",
        "token",
        "id_token",
        "access_token",
        "refresh_token",
        "oauth_token",
        "api_key",
        "apikey",
        "authorization",
        "credentials",
        "private_key",
        "client_secret",
        "auth_token",
        "session_token",
    ]
)

# Keys that end with sensitive suffixes (e.g., user_password, auth_secret)
SENSITIVE_SUFFIXES: tuple[str, ...] = (
    "_password",
    "_passwd",
    "_secret",
    "_token",
    "_apikey",
    "_api_key",
    "_credentials",
    "_private_key",
)

# Explicitly safe telemetry / metrics keys containing the word 'token'
SAFE_METRIC_KEYS: frozenset[str] = frozenset(
    [
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "token_count",
        "tokens",
    ]
)

REDACTED_PLACEHOLDER = "[REDACTED]"

# Regex patterns to detect embedded secrets inside strings or URLs
BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+([A-Za-z0-9_\-\.]+)", re.IGNORECASE)
JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+")
API_KEY_PATTERN = re.compile(r"(AIza[0-9A-Za-z_\-]{30,40}|sk-[A-Za-z0-9_\-]{20,})")
QUERY_SECRET_PATTERN = re.compile(
    r"(?i)(password|passwd|secret|id_token|access_token|refresh_token|api_key|key|credentials|X-Goog-Signature|X-Goog-Credential|X-Amz-Signature|signature)=([^&\s]+)"
)


def is_sensitive_key(key: str) -> bool:
    """Determine whether a dictionary key represents credentials."""
    key_lower = key.lower().strip()
    if key_lower in SAFE_METRIC_KEYS:
        return False
    if key_lower in EXACT_SENSITIVE_KEYS:
        return True
    if any(key_lower.endswith(suffix) for suffix in SENSITIVE_SUFFIXES):
        return True
    return False


def redact_string(value: str) -> str:
    """Mask tokens, secrets, and authorization signatures within text."""
    if not value:
        return value

    redacted = BEARER_PATTERN.sub(f"Bearer {REDACTED_PLACEHOLDER}", value)
    redacted = JWT_PATTERN.sub(REDACTED_PLACEHOLDER, redacted)
    redacted = API_KEY_PATTERN.sub(REDACTED_PLACEHOLDER, redacted)
    redacted = QUERY_SECRET_PATTERN.sub(r"\1=" + REDACTED_PLACEHOLDER, redacted)
    return redacted


def sanitize_payload(obj: Any) -> Any:
    """Recursively sanitize dicts, lists, and primitives to remove sensitive data."""
    if isinstance(obj, dict):
        sanitized: dict[str, Any] = {}
        for k, v in obj.items():
            if is_sensitive_key(str(k)):
                sanitized[k] = REDACTED_PLACEHOLDER
            else:
                sanitized[k] = sanitize_payload(v)
        return sanitized
    elif isinstance(obj, (list, tuple, set)):
        return [sanitize_payload(item) for item in obj]
    elif isinstance(obj, str):
        return redact_string(obj)
    return obj
