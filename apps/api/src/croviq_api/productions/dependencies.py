"""FastAPI dependency injection for GenAI client and DirectorEditorService."""

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
from croviq_api.productions.render_review_repository import (
    RenderReviewRepository,
    get_render_review_repository,
    set_render_review_repository,
)
from croviq_api.productions.packaging_repository import (
    PackagingRepository,
    get_packaging_repository,
    set_packaging_repository,
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
from croviq_api.productions.editorial_service import DirectorEditorService
from croviq_api.productions.repository import (
    ProductionRepository,
    get_production_repository,
)
from croviq_api.productions.transcript_repository import (
    TranscriptRepository,
    get_transcript_repository,
)

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
        return _custom_genai_client

    if _default_genai_client is None:
        if settings.genai_backend_provider == "google" and settings.gcp_project_id:
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
    global _custom_genai_client
    _custom_genai_client = client


def get_editorial_service(
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    transcript_repo: Annotated[TranscriptRepository, Depends(get_transcript_repository)],
    memory_store: Annotated[ChannelMemoryStore, Depends(get_memory_store)],
    media_inspector: Annotated[MediaInspector, Depends(get_media_inspector)],
    editorial_repo: Annotated[EditorialRepository, Depends(get_editorial_repository)],
    genai_client: Annotated[GenAIClient, Depends(get_genai_client)],
    render_review_repo: Annotated[RenderReviewRepository, Depends(get_render_review_repository)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)],
    media_inspector_svc: Annotated[MediaInspector, Depends(get_media_inspector)],
    settings: Annotated[Settings, Depends(get_settings)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> DirectorEditorService:
    """FastAPI dependency provider for DirectorEditorService."""
    edl_svc = EDLService(
        production_repo=production_repo,
        transcript_repo=transcript_repo,
        editorial_repo=editorial_repo,
        edl_repo=edl_repo,
        media_inspector=media_inspector,
    )
    render_svc = get_render_service(settings=settings)
    return DirectorEditorService(
        production_repo=production_repo,
        transcript_repo=transcript_repo,
        memory_store=memory_store,
        media_inspector=media_inspector,
        editorial_repo=editorial_repo,
        genai_client=genai_client,
        render_review_repo=render_review_repo,
        edl_repo=edl_repo,
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
    media_inspector: Annotated[MediaInspector, Depends(get_media_inspector)],
) -> EDLService:
    """FastAPI dependency provider for EDLService."""
    return EDLService(
        production_repo=production_repo,
        transcript_repo=transcript_repo,
        editorial_repo=editorial_repo,
        edl_repo=edl_repo,
        media_inspector=media_inspector,
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
