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

    # Media Inspect events
    MEDIA_INSPECT_COMPLETED = "media.inspect.completed"
    MEDIA_INSPECT_FAILED = "media.inspect.failed"

    # Transcription events
    TRANSCRIPTION_STARTED = "transcription.started"
    TRANSCRIPTION_COMPLETED = "transcription.completed"
    TRANSCRIPTION_FAILED = "transcription.failed"

    MEMORY_PROFILE_GENERATE_STARTED = "memory.profile.generate.started"
    MEMORY_PROFILE_GENERATE_COMPLETED = "memory.profile.generate.completed"
    MEMORY_PROFILE_RETRIEVE = "memory.profile.retrieve"
    MEMORY_PROFILE_FAILED = "memory.profile.failed"

    # Client browser events (allowlisted)
    CLIENT_ERROR = "client.error"

    # AI and Agent telemetry events
    AI_CALL_STARTED = "ai.call.started"
    AI_CALL_COMPLETED = "ai.call.completed"
    AI_CALL_FAILED = "ai.call.failed"

    # Editor / Leo events
    EDITOR_ANALYSIS_STARTED = "editor.analysis.started"
    EDITOR_ANALYSIS_COMPLETED = "editor.analysis.completed"
    EDITOR_ANALYSIS_FAILED = "editor.analysis.failed"

    # Director / Maya events
    DIRECTOR_REVIEW_STARTED = "director.review.started"
    DIRECTOR_REVIEW_COMPLETED = "director.review.completed"
    DIRECTOR_REVIEW_FAILED = "director.review.failed"

    # Editorial Run lifecycle events
    EDITORIAL_RUN_COMPLETED = "editorial.run.completed"
    EDITORIAL_RUN_FAILED = "editorial.run.failed"
    # EDL assembly events
    EDL_ASSEMBLY_STARTED = "edl.assembly.started"
    EDL_ASSEMBLY_COMPLETED = "edl.assembly.completed"
    EDL_ASSEMBLY_FAILED = "edl.assembly.failed"
    CUT_SAFETY_EVALUATED = "cut.safety.evaluated"

    # Media Rendering events
    RENDER_STARTED = "render.started"
    RENDER_COMPLETED = "render.completed"
    RENDER_FAILED = "render.failed"


    # Director Render Review events (Issue #30)
    DIRECTOR_RENDER_REVIEW_STARTED = "director.render_review.started"
    DIRECTOR_RENDER_REVIEW_COMPLETED = "director.render_review.completed"
    DIRECTOR_RENDER_REVIEW_FAILED = "director.render_review.failed"

    # Editor Correction events (Issue #30)
    EDITOR_CORRECTION_STARTED = "editor.correction.started"
    EDITOR_CORRECTION_COMPLETED = "editor.correction.completed"
    EDITOR_CORRECTION_FAILED = "editor.correction.failed"

    # Master render approval event (Issue #30)
    MASTER_APPROVED = "master.approved"

    # Vertical Short Rendering events (Issue #31)
    SHORT_RENDER_STARTED = "short.render.started"
    SHORT_RENDER_COMPLETED = "short.render.completed"
    SHORT_RENDER_FAILED = "short.render.failed"

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
