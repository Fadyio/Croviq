"""FastAPI dependency injection for GenAI client and DirectorEditorService."""

from functools import lru_cache
from typing import Annotated
from fastapi import Depends

from croviq_agents.client import FakeGenAIClient, GenAIClient, GoogleGenAIClient
from croviq_api.config import Settings, get_settings
from croviq_api.media.dependencies import get_media_inspector
from croviq_media.inspector import MediaInspector
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
) -> DirectorEditorService:
    """FastAPI dependency provider for DirectorEditorService."""
    return DirectorEditorService(
        production_repo=production_repo,
        transcript_repo=transcript_repo,
        memory_store=memory_store,
        media_inspector=media_inspector,
        editorial_repo=editorial_repo,
        genai_client=genai_client,
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
