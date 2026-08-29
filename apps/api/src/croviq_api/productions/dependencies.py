"""FastAPI dependency injection for GenAI and production services."""

from functools import lru_cache
from typing import Annotated
from fastapi import Depends

from croviq_agents.client import FakeGenAIClient, GenAIClient, GoogleGenAIClient
from croviq_api.config import Settings, get_settings
from croviq_api.media.dependencies import get_media_inspector, get_media_storage
from croviq_api.media.storage import MediaStorage
from croviq_media.inspector import MediaInspector
from croviq_media.render import FakeRenderService, FFmpegRenderService, RenderService
from croviq_api.productions.render_repository import (
    RenderRepository,
    get_render_repository,
    set_render_repository,
)
from croviq_api.productions.packaging_repository import (
    PackagingRepository,
    get_packaging_repository,
    set_packaging_repository,
)
from croviq_api.productions.release_review_repository import (
    ReleaseReviewRepository,
    get_release_review_repository,
    set_release_review_repository,
)
from croviq_api.memory.dependencies import get_memory_store
from croviq_api.memory.store import ChannelMemoryStore
from croviq_api.productions.editorial_repository import (
    EditorialRepository,
    get_editorial_repository,
)
from croviq_api.productions.edl_repository import (
    EDLRepository,
    get_edl_repository,
)
from croviq_api.productions.edl_service import EDLService
from croviq_api.productions.editorial_service import EditorialService
from croviq_api.productions.repository import (
    ProductionRepository,
    get_production_repository,
)
from croviq_api.productions.transcript_repository import (
    TranscriptRepository,
    get_transcript_repository,
)
from croviq_api.productions.thumbnail_repository import (
    ThumbnailRepository,
    get_thumbnail_repository,
    set_thumbnail_repository,
)
from croviq_api.productions.publish_job_repository import (
    PublishJobRepository,
    get_publish_job_repository,
    set_publish_job_repository,
)
from croviq_api.channels.youtube_repository import (
    YouTubeConnectionRepository,
    get_youtube_connection_repository,
)
from croviq_api.workspaces.repository import (
    WorkspaceRepository,
    get_workspace_repository,
)
from croviq_api.productions.studio_voice_repository import (
    StudioVoiceRepository,
    get_studio_voice_repository,
)
from croviq_api.productions.broll_repository import (
    BRollRepository,
    get_broll_repository,
)
from croviq_api.channels.youtube_publisher import (
    YouTubePublishClient,
    get_youtube_publish_client,
    set_youtube_publish_client,
)
from croviq_api.productions.publish_service import YouTubePublishService

_custom_render_service: RenderService | None = None
_default_render_service: RenderService | None = None

_custom_genai_client: GenAIClient | None = None
_default_genai_client: GenAIClient | None = None


def get_genai_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> GenAIClient:
    """Resolve active GenAIClient provider based on environment configuration."""
    global _custom_genai_client, _default_genai_client
    if _custom_genai_client is not None:
        if settings.is_production and isinstance(_custom_genai_client, FakeGenAIClient):
            raise RuntimeError(
                "Production mode strictly forbids FakeGenAIClient overrides."
            )
        return _custom_genai_client

    if _default_genai_client is None:
        if settings.is_production:
            if settings.genai_backend_provider != "google" or not settings.gcp_project_id:
                raise RuntimeError(
                    "Production mode requires Google GenAI client (genai_backend_provider='google' and valid gcp_project_id). FakeGenAIClient is strictly forbidden in production."
                )
            _default_genai_client = GoogleGenAIClient(
                project_id=settings.gcp_project_id,
                location=settings.vertexai_location,
                model_id=settings.gemini_model_id,
            )
        elif settings.genai_backend_provider == "google" and settings.gcp_project_id:
            _default_genai_client = GoogleGenAIClient(
                project_id=settings.gcp_project_id,
                location=settings.vertexai_location,
                model_id=settings.gemini_model_id,
            )
        else:
            _default_genai_client = FakeGenAIClient()

    return _default_genai_client


def set_genai_client(client: GenAIClient | None) -> None:
    """Override GenAIClient instance for unit testing and test isolation."""
    global _custom_genai_client, _default_genai_client
    _custom_genai_client = client
    if client is None:
        _default_genai_client = None

def get_editorial_service(
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    transcript_repo: Annotated[TranscriptRepository, Depends(get_transcript_repository)],
    memory_store: Annotated[ChannelMemoryStore, Depends(get_memory_store)],
    media_inspector: Annotated[MediaInspector, Depends(get_media_inspector)],
    editorial_repo: Annotated[EditorialRepository, Depends(get_editorial_repository)],
    genai_client: Annotated[GenAIClient, Depends(get_genai_client)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> EditorialService:
    """FastAPI dependency provider for the active editorial pipeline."""
    edl_svc = EDLService(
        production_repo=production_repo,
        transcript_repo=transcript_repo,
        editorial_repo=editorial_repo,
        edl_repo=edl_repo,
    )
    render_svc = get_render_service(settings=settings)
    return EditorialService(
        production_repo=production_repo,
        transcript_repo=transcript_repo,
        memory_store=memory_store,
        media_inspector=media_inspector,
        editorial_repo=editorial_repo,
        genai_client=genai_client,
        render_repo=render_repo,
        edl_service=edl_svc,
        render_service=render_svc,
        media_storage=media_storage,
    )

def get_edl_service(
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    transcript_repo: Annotated[TranscriptRepository, Depends(get_transcript_repository)],
    editorial_repo: Annotated[EditorialRepository, Depends(get_editorial_repository)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
) -> EDLService:
    """FastAPI dependency provider for EDLService."""
    return EDLService(
        production_repo=production_repo,
        transcript_repo=transcript_repo,
        editorial_repo=editorial_repo,
        edl_repo=edl_repo,
    )


def get_render_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> RenderService:
    """Resolve active RenderService implementation."""
    global _custom_render_service, _default_render_service
    if _custom_render_service is not None:
        return _custom_render_service

    if _default_render_service is None:
        _default_render_service = FFmpegRenderService()

    return _default_render_service


def set_render_service(service: RenderService | None) -> None:
    """Override RenderService instance for test isolation."""
    global _custom_render_service
    _custom_render_service = service


_custom_publish_service: YouTubePublishService | None = None


def get_publish_service(
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    youtube_repo: Annotated[YouTubeConnectionRepository, Depends(get_youtube_connection_repository)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
    release_review_repo: Annotated[ReleaseReviewRepository, Depends(get_release_review_repository)],
    packaging_repo: Annotated[PackagingRepository, Depends(get_packaging_repository)],
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)],
    studio_voice_repo: Annotated[StudioVoiceRepository, Depends(get_studio_voice_repository)],
    broll_repo: Annotated[BRollRepository, Depends(get_broll_repository)],
    thumbnail_repo: Annotated[ThumbnailRepository, Depends(get_thumbnail_repository)],
    publish_job_repo: Annotated[PublishJobRepository, Depends(get_publish_job_repository)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> YouTubePublishService:
    global _custom_publish_service
    if _custom_publish_service is not None:
        return _custom_publish_service
    return YouTubePublishService(
        production_repo=production_repo,
        workspace_repo=workspace_repo,
        youtube_repo=youtube_repo,
        edl_repo=edl_repo,
        release_review_repo=release_review_repo,
        packaging_repo=packaging_repo,
        render_repo=render_repo,
        studio_voice_repo=studio_voice_repo,
        broll_repo=broll_repo,
        thumbnail_repo=thumbnail_repo,
        publish_job_repo=publish_job_repo,
        media_storage=media_storage,
    )


def set_publish_service(service: YouTubePublishService | None) -> None:
    global _custom_publish_service
    _custom_publish_service = service
