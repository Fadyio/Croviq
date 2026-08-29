"""Regression tests verifying that all backend provider factories strictly fail closed in production."""

import os
import pytest
from unittest.mock import patch

from croviq_api.config import Settings
from croviq_api.auth.verifier import FirebaseTokenVerifier, get_token_verifier
from croviq_api.channels.research_repository import (
    FirestoreResearchRepository,
    InMemoryResearchRepository,
    get_research_repository,
    set_research_repository,
)
from croviq_api.channels.token_encryption import (
    LocalTinkOAuthTokenEncryptor,
    TinkKmsOAuthTokenEncryptor,
    get_oauth_token_encryptor,
    set_oauth_token_encryptor,
)
from croviq_api.channels.youtube_publisher import (
    FakeYouTubePublishClient,
    GoogleYouTubePublishClient,
    get_youtube_publish_client,
    set_youtube_publish_client,
)
from croviq_api.channels.youtube_repository import (
    FirestoreYouTubeConnectionRepository,
    InMemoryYouTubeConnectionRepository,
    get_youtube_connection_repository,
    set_youtube_connection_repository,
)
from croviq_api.media.dependencies import (
    FakeMediaStorage,
    GoogleMediaStorage,
    get_media_storage,
    get_transcription_service,
    set_media_storage,
    set_transcription_service,
)
from croviq_api.memory.dependencies import (
    get_memory_store,
    set_memory_store,
)
from croviq_api.memory.fake import FakeChannelMemoryStore
from croviq_api.memory.google import GoogleMemoryBankStore
from croviq_api.productions.broll_repository import (
    FirestoreBRollRepository,
    get_broll_repository,
    set_broll_repository,
)
from croviq_api.productions.dependencies import (
    FakeGenAIClient,
    GoogleGenAIClient,
    get_genai_client,
    set_genai_client,
)
from croviq_api.productions.edl_repository import (
    FirestoreEDLRepository,
    get_edl_repository,
    set_edl_repository,
)
from croviq_api.productions.editorial_repository import (
    FirestoreEditorialRepository,
    get_editorial_repository,
    set_editorial_repository,
)
from croviq_api.productions.packaging_repository import (
    FirestorePackagingRepository,
    get_packaging_repository,
    set_packaging_repository,
)
from croviq_api.productions.publish_job_repository import (
    FirestorePublishJobRepository,
    get_publish_job_repository,
    set_publish_job_repository,
)
from croviq_api.productions.render_repository import (
    FirestoreRenderRepository,
    get_render_repository,
    set_render_repository,
)
from croviq_api.productions.render_review_repository import (
    FirestoreRenderReviewRepository,
    get_render_review_repository,
)
from croviq_api.productions.repository import (
    FirestoreProductionRepository,
    get_production_repository,
)
from croviq_api.productions.studio_voice_repository import (
    FirestoreStudioVoiceRepository,
    get_studio_voice_repository,
)
from croviq_api.productions.thumbnail_repository import (
    FirestoreThumbnailRepository,
    get_thumbnail_repository,
)
from croviq_api.productions.transcript_repository import (
    FirestoreTranscriptRepository,
    get_transcript_repository,
)
from croviq_api.workspaces.agent_config_repository import (
    FirestoreAgentConfigRepository,
    get_agent_config_repository,
)
from croviq_api.workspaces.repository import (
    FirestoreWorkspaceRepository,
    get_workspace_repository,
)


@pytest.fixture(autouse=True)
def clean_singletons():
    import croviq_api.productions.dependencies as prod_deps
    import croviq_api.memory.dependencies as mem_deps
    import croviq_api.media.dependencies as media_deps
    import croviq_api.channels.token_encryption as token_enc
    import croviq_api.channels.youtube_publisher as yt_pub
    import croviq_api.channels.youtube_repository as yt_repo
    import croviq_api.channels.research_repository as res_repo
    import croviq_api.workspaces.repository as ws_repo
    import croviq_api.workspaces.agent_config_repository as ac_repo
    import croviq_api.productions.broll_repository as broll_repo
    import croviq_api.productions.studio_voice_repository as sv_repo
    import croviq_api.productions.thumbnail_repository as thumb_repo
    import croviq_api.productions.publish_job_repository as pub_job_repo
    import croviq_api.productions.render_repository as rend_repo
    import croviq_api.productions.render_review_repository as rr_repo
    import croviq_api.productions.packaging_repository as pkg_repo
    import croviq_api.productions.edl_repository as edl_repo
    import croviq_api.productions.editorial_repository as ed_repo
    import croviq_api.productions.transcript_repository as tr_repo
    import croviq_api.productions.repository as p_repo

    def _reset_all():
        prod_deps._custom_genai_client = None
        prod_deps._default_genai_client = None
        mem_deps._memory_store_override = None
        mem_deps._default_store = None
        media_deps._custom_media_storage = None
        media_deps._custom_transcription_service = None
        token_enc._global_encryptor = None
        yt_pub._global_youtube_publish_client = None
        yt_repo._global_youtube_repo = None
        res_repo._global_repository = None
        ws_repo._global_workspace_repo = None
        ac_repo._global_agent_config_repo = None
        broll_repo._global_broll_repo = None
        sv_repo._global_studio_voice_repo = None
        thumb_repo._global_thumbnail_repo = None
        pub_job_repo._global_publish_job_repo = None
        rend_repo._global_render_repo = None
        rr_repo._global_render_review_repo = None
        pkg_repo._global_packaging_repo = None
        edl_repo._global_edl_repo = None
        ed_repo._global_editorial_repo = None
        tr_repo._global_transcript_repo = None
        p_repo._global_production_repo = None

    _reset_all()
    yield
    _reset_all()

def test_genai_client_production_fails_closed_without_google_or_project():
    prod_settings = Settings(
        environment="production",
        genai_backend_provider="fake",
        gcp_project_id=None,
    )
    with pytest.raises(RuntimeError, match="Production mode requires Google GenAI client"):
        get_genai_client(settings=prod_settings)


def test_genai_client_production_forbids_fake_override():
    prod_settings = Settings(
        environment="production",
        genai_backend_provider="google",
        gcp_project_id="test-prod-project",
    )
    set_genai_client(FakeGenAIClient())
    with pytest.raises(RuntimeError, match="strictly forbids FakeGenAIClient overrides"):
        get_genai_client(settings=prod_settings)

def test_oauth_token_encryptor_production_fails_closed_when_kms_fails():
    from croviq_api.channels.token_encryption import TokenPayload
    with patch("croviq_api.channels.token_encryption.get_settings") as mock_settings:
        mock_settings.return_value = Settings(environment="production", gcp_project_id=None)
        encryptor = get_oauth_token_encryptor()
        assert isinstance(encryptor, TinkKmsOAuthTokenEncryptor)
        # Calling encryption when KMS fails must raise and fail closed
        with patch("tink.integration.gcpkms.GcpKmsClient", side_effect=RuntimeError("Cloud KMS unavailable")):
            with pytest.raises(RuntimeError, match="Cloud KMS unavailable"):
                encryptor.encrypt_tokens(
                    TokenPayload(access_token="fake_tok"),
                    workspace_id="ws1",
                    user_id="u1",
                )
def test_media_storage_production_forbids_fake():
    with patch("croviq_api.media.dependencies.get_settings") as mock_settings:
        mock_settings.return_value = Settings(environment="production", media_storage_provider="fake")
        with pytest.raises(RuntimeError, match="strictly forbidden in production"):
            get_media_storage()


def test_memory_store_production_forbids_fake():
    prod_settings = Settings(environment="production", memory_store_provider="fake")
    with pytest.raises(RuntimeError, match="strictly forbidden in production"):
        get_memory_store(settings=prod_settings)


def test_all_firestore_repositories_fail_closed_in_production_without_project_id():
    with patch("croviq_api.workspaces.repository.get_settings") as mock_ws_settings:
        mock_ws_settings.return_value = Settings(environment="production", gcp_project_id=None)
        with pytest.raises(RuntimeError, match="Production mode requires FirestoreWorkspaceRepository"):
            get_workspace_repository()

    with patch("croviq_api.workspaces.agent_config_repository.get_settings") as mock_ac_settings:
        mock_ac_settings.return_value = Settings(environment="production", gcp_project_id=None)
        with pytest.raises(RuntimeError, match="Production mode requires FirestoreAgentConfigRepository"):
            get_agent_config_repository()

    with patch("croviq_api.productions.broll_repository.get_settings") as mock_broll_settings:
        mock_broll_settings.return_value = Settings(environment="production", gcp_project_id=None)
        with pytest.raises(RuntimeError, match="Production mode requires FirestoreBRollRepository"):
            get_broll_repository()

    with patch("croviq_api.productions.studio_voice_repository.get_settings") as mock_sv_settings:
        mock_sv_settings.return_value = Settings(environment="production", gcp_project_id=None)
        with pytest.raises(RuntimeError, match="Production mode requires FirestoreStudioVoiceRepository"):
            get_studio_voice_repository()

    with patch("croviq_api.productions.editorial_repository.get_settings") as mock_ed_settings:
        mock_ed_settings.return_value = Settings(environment="production", gcp_project_id=None)
        with pytest.raises(RuntimeError, match="Production mode requires FirestoreEditorialRepository"):
            get_editorial_repository()

    with patch("croviq_api.productions.edl_repository.get_settings") as mock_edl_settings:
        mock_edl_settings.return_value = Settings(environment="production", gcp_project_id=None)
        with pytest.raises(RuntimeError, match="Production mode requires FirestoreEDLRepository"):
            get_edl_repository()

    with patch("croviq_api.productions.render_repository.get_settings") as mock_rnd_settings:
        mock_rnd_settings.return_value = Settings(environment="production", gcp_project_id=None)
        with pytest.raises(RuntimeError, match="Production mode requires FirestoreRenderRepository"):
            get_render_repository()

    with patch("croviq_api.productions.render_review_repository.get_settings") as mock_rr_settings:
        mock_rr_settings.return_value = Settings(environment="production", gcp_project_id=None)
        with pytest.raises(RuntimeError, match="Production mode requires FirestoreRenderReviewRepository"):
            get_render_review_repository()

    with patch("croviq_api.productions.packaging_repository.get_settings") as mock_pkg_settings:
        mock_pkg_settings.return_value = Settings(environment="production", gcp_project_id=None)
        with pytest.raises(RuntimeError, match="Production mode requires FirestorePackagingRepository"):
            get_packaging_repository()

    with patch("croviq_api.productions.transcript_repository.get_settings") as mock_tr_settings:
        mock_tr_settings.return_value = Settings(environment="production", gcp_project_id=None)
        with pytest.raises(RuntimeError, match="Production mode requires FirestoreTranscriptRepository"):
            get_transcript_repository()

    with patch("croviq_api.productions.repository.get_settings") as mock_prod_settings:
        mock_prod_settings.return_value = Settings(environment="production", gcp_project_id=None)
        with pytest.raises(RuntimeError, match="Production mode requires FirestoreProductionRepository"):
            get_production_repository()
