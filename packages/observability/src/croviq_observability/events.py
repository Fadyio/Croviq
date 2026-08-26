"""Canonical event taxonomy for Croviq structured observability."""

from enum import StrEnum


class EventType(StrEnum):
    # HTTP events
    HTTP_REQUEST = "http.request"
    HTTP_RESPONSE = "http.response"

    # Auth events
    AUTH_LOGIN_ATTEMPT = "auth.login_attempt"
    AUTH_LOGIN_VERIFIED = "auth.login_verified"
    AUTH_LOGIN_FAILED = "auth.login_failed"
    AUTH_ACCESS_ALLOWED = "auth.access_allowed"
    AUTH_ACCESS_DENIED = "auth.access_denied"
    AUTH_LOGOUT_OBSERVED = "auth.logout_observed"

    # Workspace events
    WORKSPACE_CREATED = "workspace.created"
    WORKSPACE_LOADED = "workspace.loaded"
    WORKSPACE_LOAD_FAILED = "workspace.load_failed"

    # Firestore persistence events
    FIRESTORE_READ = "firestore.read"
    FIRESTORE_WRITE = "firestore.write"
    FIRESTORE_ERROR = "firestore.error"

    # Media Upload events
    UPLOAD_CREATED = "upload.created"
    UPLOAD_STARTED = "upload.started"
    UPLOAD_COMPLETED = "upload.completed"
    UPLOAD_FAILED = "upload.failed"

    # Memory Bank events
    MEMORY_PROFILE_GENERATE_STARTED = "memory.profile.generate.started"
    MEMORY_PROFILE_GENERATE_COMPLETED = "memory.profile.generate.completed"
    MEMORY_PROFILE_RETRIEVE = "memory.profile.retrieve"
    MEMORY_PROFILE_FAILED = "memory.profile.failed"

    # Client browser events (allowlisted)
    CLIENT_ERROR = "client.error"

    # Future AI / Agent events (defined for future agent & model telemetry)
    AI_CALL_STARTED = "ai.call.started"
    AI_CALL_COMPLETED = "ai.call.completed"
    AI_CALL_FAILED = "ai.call.failed"


# Normalized set of all standard event names
NORMALIZED_EVENT_TYPES: frozenset[str] = frozenset(e.value for e in EventType)

# Strict allowlist for browser telemetry ingesting at /api/client-events
CLIENT_ALLOWED_EVENT_TYPES: frozenset[str] = frozenset(
    [
        EventType.CLIENT_ERROR.value,
        EventType.AUTH_LOGIN_ATTEMPT.value,
        EventType.AUTH_LOGIN_FAILED.value,
        EventType.UPLOAD_STARTED.value,
        EventType.UPLOAD_COMPLETED.value,
        EventType.UPLOAD_FAILED.value,
    ]
)
