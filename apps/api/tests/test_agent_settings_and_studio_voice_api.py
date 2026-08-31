"""Integration tests for Agent Settings, Prompt Versioning, Voice Audition, and Studio Voice API endpoints."""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from croviq_api.main import app
from croviq_api.auth.dependencies import get_current_user
from croviq_api.media.dependencies import get_media_storage
from croviq_api.media.fake import FakeMediaStorage
from croviq_api.productions.dependencies import get_render_service
from croviq_api.productions.edl_repository import (
    InMemoryEDLRepository,
    get_edl_repository,
)
from croviq_api.productions.render_repository import (
    InMemoryRenderRepository,
    get_render_repository,
)
from croviq_api.productions.repository import (
    InMemoryProductionRepository,
    get_production_repository,
)
from croviq_api.productions.studio_voice_repository import (
    InMemoryStudioVoiceRepository,
    get_studio_voice_repository,
)
from croviq_api.productions.transcript_repository import (
    InMemoryTranscriptRepository,
    get_transcript_repository,
)
from croviq_api.productions.dependencies import get_genai_client
from croviq_api.workspaces.agent_config_repository import (
    InMemoryAgentConfigRepository,
    get_agent_config_repository,
)
from croviq_api.workspaces.repository import (
    InMemoryWorkspaceRepository,
    get_workspace_repository,
)
from croviq_domain.agent_config import AgentId, NarrationMode
from croviq_domain.edl import EditDecisionList
from croviq_domain.production import Production, ProductionStatus, SourceMedia, SourceMediaStatus
from croviq_domain.transcript import (
    CorrectedTranscript,
    CorrectedTranscriptSegment,
    EntailmentVerdict,
    ScriptCorrectionChangeType,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
)
from croviq_domain.user import User
from croviq_media.render import FakeRenderService
from croviq_domain.render import ArtifactStatus, ArtifactType
from croviq_agents.client import FakeGenAIClient


@pytest.fixture
def api_test_context():
    test_user = User(
        user_id="user_sv_test",
        email="creator@croviq.app",
        display_name="Creator Test",
        avatar_url=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    ws_repo = InMemoryWorkspaceRepository()
    agent_config_repo = InMemoryAgentConfigRepository()
    prod_repo = InMemoryProductionRepository()
    transcript_repo = InMemoryTranscriptRepository()
    edl_repo = InMemoryEDLRepository()
    render_repo = InMemoryRenderRepository()
    sv_repo = InMemoryStudioVoiceRepository()
    fake_storage = FakeMediaStorage()
    fake_render = FakeRenderService()

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_workspace_repository] = lambda: ws_repo
    app.dependency_overrides[get_agent_config_repository] = lambda: agent_config_repo
    app.dependency_overrides[get_production_repository] = lambda: prod_repo
    app.dependency_overrides[get_transcript_repository] = lambda: transcript_repo
    app.dependency_overrides[get_edl_repository] = lambda: edl_repo
    app.dependency_overrides[get_render_repository] = lambda: render_repo
    app.dependency_overrides[get_studio_voice_repository] = lambda: sv_repo
    app.dependency_overrides[get_media_storage] = lambda: fake_storage
    app.dependency_overrides[get_render_service] = lambda: fake_render

    client = TestClient(app)

    yield {
        "client": client,
        "user": test_user,
        "prod_repo": prod_repo,
        "transcript_repo": transcript_repo,
        "edl_repo": edl_repo,
        "sv_repo": sv_repo,
        "render_repo": render_repo,
        "storage": fake_storage,
        "render_service": fake_render,
        "agent_config_repo": agent_config_repo,
        "workspace_repo": ws_repo,
    }
    app.dependency_overrides.clear()


def test_get_and_update_agent_settings(api_test_context):
    client = api_test_context["client"]

    # 1. Get initial agent settings
    resp = client.get("/api/workspace/agent-settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "leo_prompt" in data
    assert "alex_prompt" in data
    assert "iris_prompt" in data
    assert "maya_prompt" not in data
    assert data["alex_prompt"]["agent_id"] == "alex"
    assert "voice_settings" in data
    assert "voices" in data
    assert len(data["voices"]) >= 4

    # 2. Update Leo prompt
    custom_prompt = "You are Leo. Keep cuts ultra tight."
    put_resp = client.put(
        "/api/workspace/agent-settings/prompts/leo",
        json={"prompt_text": custom_prompt},
    )
    assert put_resp.status_code == 200
    leo_data = put_resp.json()
    assert leo_data["prompt_text"] == custom_prompt
    assert leo_data["is_custom"] is True
    assert leo_data["version"] >= 1

    alex_prompt = "You are Alex. Separate facts, inferences, research, and recommendations."
    alex_resp = client.put(
        "/api/workspace/agent-settings/prompts/alex",
        json={"prompt_text": alex_prompt},
    )
    assert alex_resp.status_code == 200
    assert alex_resp.json()["prompt_text"] == alex_prompt

    # 3. Reset Leo prompt
    reset_resp = client.post("/api/workspace/agent-settings/prompts/leo/reset")
    assert reset_resp.status_code == 200
    reset_data = reset_resp.json()
    assert reset_data["is_custom"] is False
    assert "Editorial Principles:" in reset_data["prompt_text"]


def test_agent_memory_read_only_endpoint(api_test_context):
    client = api_test_context["client"]
    resp = client.get("/api/workspace/agent-settings/memory")
    assert resp.status_code == 200
    data = resp.json()
    assert "channel_title" in data
    assert "memories" in data


def test_agent_memory_create_search_delete_lifecycle(api_test_context):
    client = api_test_context["client"]

    # 1. Create a memory
    create_resp = client.post(
        "/api/workspace/agent-settings/memory",
        json={
            "fact": "Use subtle background music during technical walkthroughs.",
            "provenance": "Creator preference",
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    created_data = create_resp.json()
    assert "memory_id" in created_data
    assert "subtle background music" in created_data["fact"]
    mem_id = created_data["memory_id"]

    # 2. Search for memory
    search_resp = client.post(
        "/api/workspace/agent-settings/memory/search",
        json={"query": "background music"},
    )
    assert search_resp.status_code == 200
    results = search_resp.json()
    assert len(results) >= 1
    assert any("subtle background music" in r["fact"] for r in results)

    # 3. Delete the memory
    del_resp = client.delete(f"/api/workspace/agent-settings/memory/{mem_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True

def test_voice_settings_and_sample_endpoint(api_test_context):
    client = api_test_context["client"]

    # Update voice settings
    put_resp = client.put(
        "/api/workspace/agent-settings/voice",
        json={
            "narration_mode": "studio_voice",
            "selected_voice": "Charon",
            "language": "en-US",
        },
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["selected_voice"] == "Charon"

    # Audition voice sample
    sample_resp = client.post(
        "/api/workspace/agent-settings/voice/sample",
        json={
            "voice_id": "Charon",
            "sample_text": "Welcome to Croviq. I'll make your video clear, concise, and easy to follow.",
        },
    )
    assert sample_resp.status_code == 200
    sample_data = sample_resp.json()
    assert sample_data["voice_id"] == "Charon"
    assert "audio_base64" in sample_data
    assert len(sample_data["audio_base64"]) > 0
    import base64
    import wave
    import io
    raw_wav = base64.b64decode(sample_data["audio_base64"])
    # Audio must contain real audio frames (strictly greater than 44-byte empty header)
    assert len(raw_wav) > 44
    with wave.open(io.BytesIO(raw_wav), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 24000
        assert wf.getnframes() > 0


@pytest.mark.asyncio
async def test_studio_voice_generation_endpoint(api_test_context):
    client = api_test_context["client"]
    prod_repo = api_test_context["prod_repo"]
    transcript_repo = api_test_context["transcript_repo"]
    edl_repo = api_test_context["edl_repo"]
    user = api_test_context["user"]

    prod_id = "prod_sv_demo_1"
    now = datetime.now(timezone.utc)
    prod = Production(
        production_id=prod_id,
        owner_user_id=user.user_id,
        workspace_id="ws_user_sv_test",
        channel_id="croviq_syn_ai_eng_01",
        status=ProductionStatus.UPLOADED,
        source_media=SourceMedia(
            upload_id="up_sv_01",
            original_filename="demo.mp4",
            content_type="video/mp4",
            size_bytes=5000000,
            gcs_bucket="test-bucket",
            gcs_object="workspaces/ws_user_sv_test/productions/prod_sv_demo_1/source/demo.mp4",
            status=SourceMediaStatus.UPLOADED,
            uploaded_at=now,
            created_at=now,
        ),
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    # Save transcript with 2 segments
    transcript = Transcript(
        transcript_id="tr_sv_01",
        production_id=prod_id,
        language_code="en",
        duration_ms=8000,
        words=[
            TranscriptWord(index=0, text="Hello", start_ms=0, end_ms=800, confidence=0.99),
            TranscriptWord(index=1, text="world", start_ms=900, end_ms=1800, confidence=0.99),
            TranscriptWord(index=2, text="here", start_ms=3000, end_ms=4500, confidence=0.99),
            TranscriptWord(index=3, text="we", start_ms=4600, end_ms=5500, confidence=0.99),
            TranscriptWord(index=4, text="go", start_ms=5600, end_ms=7500, confidence=0.99),
        ],
        segments=[
            TranscriptSegment(
                segment_id="seg_01",
                start_ms=0,
                end_ms=2000,
                text="Hello world",
                word_start_index=0,
                word_end_index=1,
            ),
            TranscriptSegment(
                segment_id="seg_02",
                start_ms=3000,
                end_ms=8000,
                text="Here we go install everything.",
                word_start_index=2,
                word_end_index=4,
            ),
        ],
        created_at=now,
    )
    await transcript_repo.save_transcript(transcript)

    edl = EditDecisionList(
        edl_id="edl_sv_demo",
        production_id=prod_id,
        source_duration_ms=8000,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )
    await edl_repo.save_edl(edl)
    await transcript_repo.save_corrected_transcript(
        CorrectedTranscript(
            transcript_id="corrected_sv_demo_revision_1",
            production_id=prod_id,
            segments=[
                CorrectedTranscriptSegment(
                    segment_id="seg_01",
                    source_start_ms=0,
                    source_end_ms=2000,
                    edited_start_ms=0,
                    edited_end_ms=2000,
                    original_text="Hello world",
                    corrected_text="Hello, world.",
                    change_type=ScriptCorrectionChangeType.PUNCTUATION,
                    target_duration_ms=2000,
                ),
                CorrectedTranscriptSegment(
                    segment_id="seg_02",
                    source_start_ms=3000,
                    source_end_ms=8000,
                    edited_start_ms=3000,
                    edited_end_ms=8000,
                    original_text="Here we go install everything.",
                    corrected_text="Here we go. Install everything.",
                    change_type=ScriptCorrectionChangeType.PUNCTUATION,
                    target_duration_ms=5000,
                ),
            ],
            created_at=now,
        ),
        edl_id=edl.edl_id,
    )

    # Trigger Studio Voice generation
    gen_resp = client.post(f"/api/productions/{prod_id}/studio-voice")
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["production_id"] == prod_id
    assert "result" in gen_data
    result = gen_data["result"]
    assert result["total_segments"] == 2
    assert result["accepted_segments"] == 2
    assert result["all_within_budget"] is True

    assert gen_data["studio_voice_preview_url"] is not None

    # Verify the completed Voiceover Preview artifact is the recorded lineage target.
    render_repo = api_test_context["render_repo"]
    artifacts = await render_repo.list_render_artifacts(prod_id)
    voiceover_artifacts = [
        artifact
        for artifact in artifacts
        if artifact.artifact_type == ArtifactType.VOICEOVER_PREVIEW
    ]
    assert len(voiceover_artifacts) == 1
    assert result["preview_artifact_id"] == voiceover_artifacts[0].artifact_id

    # Retrieve Studio Voice result
    get_resp = client.get(f"/api/productions/{prod_id}/studio-voice")
    assert get_resp.status_code == 200
    assert get_resp.json()["total_segments"] == 2

    # Get playback URLs
    playback_resp = client.get(f"/api/productions/{prod_id}/playback")
    assert playback_resp.status_code == 200
    playback_data = playback_resp.json()
    assert playback_data["production_id"] == prod_id
    assert playback_data["playback_url"] is not None
    assert playback_data["studio_voice_preview_url"] is not None

@pytest.mark.asyncio
async def test_studio_voice_generation_marks_incomplete_when_no_audio_synthesized(api_test_context):
    client = api_test_context["client"]
    prod_repo = api_test_context["prod_repo"]
    transcript_repo = api_test_context["transcript_repo"]
    edl_repo = api_test_context["edl_repo"]
    user = api_test_context["user"]

    prod_id = "prod_sv_fail_test"
    now = datetime.now(timezone.utc)
    prod = Production(
        production_id=prod_id,
        owner_user_id=user.user_id,
        workspace_id="ws_user_sv_test",
        channel_id="croviq_syn_ai_eng_01",
        status=ProductionStatus.UPLOADED,
        source_media=SourceMedia(
            upload_id="up_sv_02",
            original_filename="fail_demo.mp4",
            content_type="video/mp4",
            size_bytes=5000000,
            gcs_bucket="test-bucket",
            gcs_object="workspaces/ws_user_sv_test/productions/prod_sv_fail_test/source/fail_demo.mp4",
            status=SourceMediaStatus.UPLOADED,
            uploaded_at=now,
            created_at=now,
        ),
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    # 1 segment with very short available window (500ms) that will fail to fit
    transcript = Transcript(
        transcript_id="tr_sv_fail",
        production_id=prod_id,
        language_code="en",
        duration_ms=1000,
        words=[TranscriptWord(index=0, text="Impossible", start_ms=0, end_ms=500, confidence=0.99)],
        segments=[
            TranscriptSegment(
                segment_id="seg_fail_01",
                start_ms=0,
                end_ms=500,
                text="This is an exceedingly long sentence that cannot possibly fit into a 500ms window.",
                word_start_index=0,
                word_end_index=0,
            ),
        ],
        created_at=now,
    )
    await transcript_repo.save_transcript(transcript)

    edl = EditDecisionList(
        edl_id="edl_sv_fail",
        production_id=prod_id,
        source_duration_ms=1000,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )
    await edl_repo.save_edl(edl)
    await transcript_repo.save_corrected_transcript(
        CorrectedTranscript(
            transcript_id="corrected_sv_fail_revision_1",
            production_id=prod_id,
            segments=[
                CorrectedTranscriptSegment(
                    segment_id="seg_fail_01",
                    source_start_ms=0,
                    source_end_ms=500,
                    edited_start_ms=0,
                    edited_end_ms=500,
                    original_text="This is an exceedingly long sentence that cannot possibly fit into a 500ms window.",
                    corrected_text="This is an exceedingly long sentence that cannot possibly fit into a 500ms window.",
                    change_type=ScriptCorrectionChangeType.KEEP,
                    target_duration_ms=500,
                ),
            ],
            created_at=now,
        ),
        edl_id=edl.edl_id,
    )

    # Create fake genai client where TTS returns 10,000ms audio (exceeds 500ms budget)
    class AlwaysOverbudgetClient(FakeGenAIClient):
        async def synthesize_studio_voice(self, text: str, voice_id: str = "Puck", production_id: str = "unknown", request_id: str = "unknown"):
            return 10000, b"\x00" * 480000

        async def generate_narration_rewrite(self, original_text: str, available_duration_s: float, attempt: int = 1, production_id: str = "unknown", request_id: str = "unknown"):
            return original_text

    app.dependency_overrides[get_genai_client] = lambda: AlwaysOverbudgetClient()

    gen_resp = client.post(f"/api/productions/{prod_id}/studio-voice")
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["result"]["accepted_segments"] == 0
    assert gen_data["result"]["status"] == "incomplete"
    assert gen_data["studio_voice_preview_url"] is None
    artifacts = await api_test_context["render_repo"].list_render_artifacts(prod_id)
    assert not any(
        artifact.artifact_type == ArtifactType.VOICEOVER_PREVIEW
        and artifact.status == ArtifactStatus.completed
        for artifact in artifacts
    )


class _RecordingStudioVoiceClient(FakeGenAIClient):
    """TTS fake that records route inputs and can return failed or missing audio."""

    def __init__(self, fault: str | None = None) -> None:
        super().__init__()
        self.fault = fault
        self.synthesized_texts: list[str] = []
        self.synthesized_voices: list[str] = []
    async def correct_transcript_with_video_grounding(self, *args, **kwargs):
        raise AssertionError("Studio Voice generation must use the persisted corrected script")

    async def synthesize_studio_voice(
        self,
        text: str,
        voice_id: str = "Puck",
        production_id: str = "unknown",
        request_id: str = "unknown",
    ):
        self.synthesized_texts.append(text)
        self.synthesized_voices.append(voice_id)
        if self.fault == "failed" and "second canonical" in text.lower():
            return 20_000, b"\x01" * 960_000
        if self.fault == "missing" and "second canonical" in text.lower():
            return 500, b""
        return 500, b"\x01" * 24_000

    async def generate_narration_rewrite(
        self,
        original_text: str,
        available_duration_s: float,
        attempt: int = 1,
        production_id: str = "unknown",
        request_id: str = "unknown",
    ):
        return original_text


async def _seed_voiceover_lineage(
    api_test_context,
    *,
    production_id: str,
) -> tuple[EditDecisionList, CorrectedTranscript]:
    now = datetime.now(timezone.utc)
    source = SourceMedia(
        upload_id=f"up_{production_id}",
        original_filename="lineage.mp4",
        content_type="video/mp4",
        size_bytes=1000,
        gcs_bucket="test-bucket",
        gcs_object=f"productions/{production_id}/source.mp4",
        status=SourceMediaStatus.UPLOADED,
        uploaded_at=now,
        created_at=now,
    )
    await api_test_context["prod_repo"].create_production(
        Production(
            production_id=production_id,
            owner_user_id=api_test_context["user"].user_id,
            workspace_id="ws_user_sv_test",
            channel_id="croviq_syn_ai_eng_01",
            status=ProductionStatus.UPLOADED,
            source_media=source,
            created_at=now,
            updated_at=now,
        )
    )
    transcript = Transcript(
        transcript_id=f"tr_{production_id}",
        production_id=production_id,
        language_code="en",
        duration_ms=8000,
        words=[
            TranscriptWord(index=0, text="raw", start_ms=0, end_ms=1000),
            TranscriptWord(index=1, text="words", start_ms=1001, end_ms=2000),
            TranscriptWord(index=2, text="more", start_ms=4000, end_ms=5000),
            TranscriptWord(index=3, text="raw", start_ms=5001, end_ms=6000),
        ],
        segments=[
            TranscriptSegment(
                segment_id="seg_first",
                start_ms=0,
                end_ms=3000,
                text="Raw first transcript wording.",
                word_start_index=0,
                word_end_index=1,
            ),
            TranscriptSegment(
                segment_id="seg_second",
                start_ms=4000,
                end_ms=8000,
                text="Raw second transcript wording.",
                word_start_index=2,
                word_end_index=3,
            ),
        ],
        created_at=now,
    )
    await api_test_context["transcript_repo"].save_transcript(transcript)
    edl = EditDecisionList(
        edl_id=f"edl_{production_id}",
        production_id=production_id,
        version=7,
        source_duration_ms=8000,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )
    await api_test_context["edl_repo"].save_edl(edl)
    corrected = CorrectedTranscript(
        transcript_id=f"corrected_{production_id}_revision_4",
        production_id=production_id,
        segments=[
            CorrectedTranscriptSegment(
                segment_id="seg_first",
                source_start_ms=0,
                source_end_ms=3000,
                edited_start_ms=0,
                edited_end_ms=3000,
                original_text="Raw first transcript wording.",
                corrected_text="First canonical corrected sentence.",
                change_type=ScriptCorrectionChangeType.KEEP,
                target_duration_ms=3000,
                entailment_verdict=EntailmentVerdict.SUPPORTED,
            ),
            CorrectedTranscriptSegment(
                segment_id="seg_second",
                source_start_ms=4000,
                source_end_ms=8000,
                edited_start_ms=4000,
                edited_end_ms=8000,
                original_text="Raw second transcript wording.",
                corrected_text="Second canonical corrected sentence.",
                change_type=ScriptCorrectionChangeType.GRAMMAR,
                target_duration_ms=4000,
                entailment_verdict=EntailmentVerdict.SUPPORTED,
            ),
        ],
        created_at=now,
    )
    await api_test_context["transcript_repo"].save_corrected_transcript(
        corrected,
        edl_id=edl.edl_id,
    )
    api_test_context["storage"].simulate_uploaded_object(
        bucket=source.gcs_bucket,
        object_name=source.gcs_object,
        size_bytes=source.size_bytes,
        content_type=source.content_type,
        content=b"source video",
    )
    voice_response = api_test_context["client"].put(
        "/api/workspace/agent-settings/voice",
        json={
            "narration_mode": "studio_voice",
            "selected_voice": "Charon",
            "language": "en-US",
        },
    )
    assert voice_response.status_code == 200
    return edl, corrected


@pytest.mark.asyncio
async def test_studio_voice_generation_uses_persisted_canonical_text_and_records_complete_lineage(
    api_test_context,
):
    production_id = "prod_voiceover_lineage"
    edl, corrected = await _seed_voiceover_lineage(
        api_test_context,
        production_id=production_id,
    )
    genai = _RecordingStudioVoiceClient()
    app.dependency_overrides[get_genai_client] = lambda: genai

    response = api_test_context["client"].post(
        f"/api/productions/{production_id}/studio-voice"
    )

    assert response.status_code == 200
    payload = response.json()
    result = payload["result"]
    assert genai.synthesized_texts == [
        "First canonical corrected sentence.",
        "Second canonical corrected sentence.",
    ]
    assert result["status"] == "completed"
    assert result["edl_id"] == edl.edl_id
    assert result["edl_version"] == edl.version
    assert result["voice_id"] == "Charon"
    assert result["corrected_script_version"] == corrected.transcript_id
    assert result["total_segments"] == 2
    assert result["accepted_segments"] == 2
    assert payload["studio_voice_preview_url"] is not None

    artifacts = await api_test_context["render_repo"].list_render_artifacts(
        production_id
    )
    completed_voiceovers = [
        artifact
        for artifact in artifacts
        if artifact.artifact_type == ArtifactType.VOICEOVER_PREVIEW
        and artifact.status == ArtifactStatus.completed
    ]
    assert len(completed_voiceovers) == 1
    assert result["preview_artifact_id"] == completed_voiceovers[0].artifact_id


@pytest.mark.parametrize("fault", ["failed", "missing"])
@pytest.mark.asyncio
async def test_studio_voice_generation_fails_closed_when_any_expected_audio_is_unusable(
    api_test_context,
    fault,
):
    production_id = f"prod_voiceover_{fault}"
    await _seed_voiceover_lineage(api_test_context, production_id=production_id)
    genai = _RecordingStudioVoiceClient(fault=fault)
    app.dependency_overrides[get_genai_client] = lambda: genai

    response = api_test_context["client"].post(
        f"/api/productions/{production_id}/studio-voice"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["status"] == "incomplete"
    assert payload["result"]["total_segments"] == 2
    assert payload["result"]["accepted_segments"] == 1
    assert payload["result"]["preview_artifact_id"] is None
    assert payload["studio_voice_preview_url"] is None
    artifacts = await api_test_context["render_repo"].list_render_artifacts(
        production_id
    )
    assert not any(
        artifact.artifact_type == ArtifactType.VOICEOVER_PREVIEW
        and artifact.status == ArtifactStatus.completed
        for artifact in artifacts
    )


@pytest.mark.asyncio
async def test_studio_voice_generation_falls_back_to_surviving_source_segment_omitted_from_canonical_script(
    api_test_context,
):
    production_id = "prod_voiceover_missing_segment"
    edl, corrected = await _seed_voiceover_lineage(
        api_test_context,
        production_id=production_id,
    )
    await api_test_context["transcript_repo"].save_corrected_transcript(
        corrected.model_copy(update={"segments": corrected.segments[:1]}),
        edl_id=edl.edl_id,
    )
    genai = _RecordingStudioVoiceClient()
    app.dependency_overrides[get_genai_client] = lambda: genai

    response = api_test_context["client"].post(
        f"/api/productions/{production_id}/studio-voice"
    )

    assert response.status_code == 200
    payload = response.json()
    result = payload["result"]
    assert genai.synthesized_texts == [
        "First canonical corrected sentence.",
        "Raw second transcript wording.",
    ]
    assert genai.synthesized_voices == ["Charon", "Charon"]
    assert result["status"] == "completed"
    assert result["edl_id"] == edl.edl_id
    assert result["edl_version"] == edl.version
    assert result["corrected_script_version"] == corrected.transcript_id
    assert result["voice_id"] == "Charon"
    assert result["total_segments"] == 2
    assert result["accepted_segments"] == 2
    assert result["all_within_budget"] is True
    assert result["preview_artifact_id"] is not None
    assert payload["studio_voice_preview_url"] is not None

    active_edl = await api_test_context["edl_repo"].get_latest_edl(production_id)
    assert active_edl is not None
    assert active_edl.edl_id == edl.edl_id
    assert active_edl.version == edl.version
    assert [segment.segment_id for segment in active_edl.voiceover_segments] == [
        "seg_first",
        "seg_second",
    ]
    assert [segment.text for segment in active_edl.voiceover_segments] == [
        "First canonical corrected sentence.",
        "Raw second transcript wording.",
    ]
    assert {
        segment.voice_id for segment in active_edl.voiceover_segments
    } == {"Charon"}
    assert {
        segment.preview_artifact_id for segment in active_edl.voiceover_segments
    } == {result["preview_artifact_id"]}

    artifacts = await api_test_context["render_repo"].list_render_artifacts(
        production_id
    )
    completed_voiceovers = [
        artifact
        for artifact in artifacts
        if artifact.artifact_type == ArtifactType.VOICEOVER_PREVIEW
        and artifact.status == ArtifactStatus.completed
    ]
    assert len(completed_voiceovers) == 1
    assert completed_voiceovers[0].artifact_id == result["preview_artifact_id"]
    assert completed_voiceovers[0].edl_id == edl.edl_id
    assert completed_voiceovers[0].voice_id == "Charon"

    playback = api_test_context["client"].get(
        f"/api/productions/{production_id}/playback"
    )
    assert playback.status_code == 200
    playback_payload = playback.json()
    assert playback_payload["studio_voice_preview_url"] is not None
    assert playback_payload["voiceover"]["available"] is True
    assert playback_payload["voiceover"]["status"] == "ready"
    assert playback_payload["voiceover"]["artifact_id"] == result["preview_artifact_id"]
    assert playback_payload["voiceover"]["edl_id"] == edl.edl_id
    assert playback_payload["voiceover"]["voice_id"] == "Charon"
    assert playback_payload["voiceover"]["url"] is not None


@pytest.mark.asyncio
async def test_studio_voice_generation_counts_merged_short_sections_as_generated_narration(
    api_test_context,
):
    production_id = "prod_voiceover_merged_sections"
    edl, corrected = await _seed_voiceover_lineage(
        api_test_context,
        production_id=production_id,
    )
    transcript = await api_test_context[
        "transcript_repo"
    ].get_transcript_by_production_id(production_id)
    assert transcript is not None
    short_source_segments = [
        transcript.segments[0].model_copy(
            update={
                "segment_id": "seg_short_intro",
                "start_ms": 0,
                "end_ms": 600,
                "text": "Quick intro.",
            }
        ),
        transcript.segments[1].model_copy(
            update={
                "segment_id": "seg_short_followup",
                "start_ms": 600,
                "end_ms": 1500,
                "text": "Brief followup.",
            }
        ),
    ]
    await api_test_context["transcript_repo"].save_transcript(
        transcript.model_copy(update={"segments": short_source_segments})
    )
    merged_script = corrected.model_copy(
        update={
            "segments": [
                corrected.segments[0].model_copy(
                    update={
                        "segment_id": "seg_short_intro",
                        "source_start_ms": 0,
                        "source_end_ms": 600,
                        "edited_start_ms": 0,
                        "edited_end_ms": 600,
                        "original_text": "Quick intro.",
                        "corrected_text": "Quick canonical intro.",
                        "target_duration_ms": 600,
                    }
                ),
                corrected.segments[1].model_copy(
                    update={
                        "segment_id": "seg_short_followup",
                        "source_start_ms": 600,
                        "source_end_ms": 1500,
                        "edited_start_ms": 600,
                        "edited_end_ms": 1500,
                        "original_text": "Brief followup.",
                        "corrected_text": "Brief canonical followup.",
                        "target_duration_ms": 900,
                    }
                ),
            ]
        }
    )
    await api_test_context["transcript_repo"].save_corrected_transcript(
        merged_script,
        edl_id=edl.edl_id,
    )
    genai = _RecordingStudioVoiceClient()
    app.dependency_overrides[get_genai_client] = lambda: genai

    response = api_test_context["client"].post(
        f"/api/productions/{production_id}/studio-voice"
    )

    assert response.status_code == 200
    payload = response.json()
    result = payload["result"]
    assert genai.synthesized_texts == [
        "Quick canonical intro. Brief canonical followup."
    ]
    assert genai.synthesized_voices == ["Charon"]
    assert result["status"] == "completed"
    assert result["edl_id"] == edl.edl_id
    assert result["edl_version"] == edl.version
    assert result["corrected_script_version"] == merged_script.transcript_id
    assert result["voice_id"] == "Charon"
    assert result["total_segments"] == 1
    assert result["accepted_segments"] == 1
    assert result["all_within_budget"] is True
    assert result["preview_artifact_id"] is not None
    assert payload["studio_voice_preview_url"] is not None

    active_edl = await api_test_context["edl_repo"].get_latest_edl(production_id)
    assert active_edl is not None
    assert active_edl.edl_id == edl.edl_id
    assert active_edl.version == edl.version
    assert len(active_edl.voiceover_segments) == 1
    persisted_segment = active_edl.voiceover_segments[0]
    assert persisted_segment.segment_id == "seg_short_intro_seg_short_followup"
    assert persisted_segment.source_start_ms == 0
    assert persisted_segment.source_end_ms == 1500
    assert (
        persisted_segment.text
        == "Quick canonical intro. Brief canonical followup."
    )
    assert persisted_segment.voice_id == "Charon"
    assert persisted_segment.preview_artifact_id == result["preview_artifact_id"]

    artifacts = await api_test_context["render_repo"].list_render_artifacts(
        production_id
    )
    completed_voiceovers = [
        artifact
        for artifact in artifacts
        if artifact.artifact_type == ArtifactType.VOICEOVER_PREVIEW
        and artifact.status == ArtifactStatus.completed
    ]
    assert len(completed_voiceovers) == 1
    assert completed_voiceovers[0].artifact_id == result["preview_artifact_id"]
    assert completed_voiceovers[0].edl_id == edl.edl_id
    assert completed_voiceovers[0].voice_id == "Charon"

    playback = api_test_context["client"].get(
        f"/api/productions/{production_id}/playback"
    )
    assert playback.status_code == 200
    playback_payload = playback.json()
    assert playback_payload["studio_voice_preview_url"] is not None
    assert playback_payload["voiceover"]["available"] is True
    assert playback_payload["voiceover"]["status"] == "ready"
    assert playback_payload["voiceover"]["artifact_id"] == result["preview_artifact_id"]
    assert playback_payload["voiceover"]["edl_id"] == edl.edl_id
    assert playback_payload["voiceover"]["voice_id"] == "Charon"
    assert playback_payload["voiceover"]["url"] is not None


@pytest.mark.parametrize(
    ("stale_reason", "expected_status"),
    [
        ("incomplete", "incomplete"),
        ("edl_version", "needs_regeneration"),
        ("selected_voice", "needs_regeneration"),
        ("corrected_script", "needs_regeneration"),
    ],
)
@pytest.mark.asyncio
async def test_playback_rejects_completed_voiceover_with_incomplete_or_stale_lineage(
    api_test_context,
    stale_reason,
    expected_status,
):
    production_id = f"prod_playback_{stale_reason}"
    edl, corrected = await _seed_voiceover_lineage(
        api_test_context,
        production_id=production_id,
    )
    genai = _RecordingStudioVoiceClient()
    app.dependency_overrides[get_genai_client] = lambda: genai
    generation = api_test_context["client"].post(
        f"/api/productions/{production_id}/studio-voice"
    )
    assert generation.status_code == 200
    assert generation.json()["result"]["status"] == "completed"

    result = await api_test_context["sv_repo"].get_by_production_id(production_id)
    assert result is not None
    if stale_reason == "incomplete":
        await api_test_context["sv_repo"].save(
            result.model_copy(update={"status": "incomplete"})
        )
    elif stale_reason == "edl_version":
        await api_test_context["edl_repo"].save_edl(
            edl.model_copy(update={"version": edl.version + 1})
        )
    elif stale_reason == "selected_voice":
        voice_response = api_test_context["client"].put(
            "/api/workspace/agent-settings/voice",
            json={
                "narration_mode": "studio_voice",
                "selected_voice": "Aoede",
                "language": "en-US",
            },
        )
        assert voice_response.status_code == 200
    else:
        await api_test_context["transcript_repo"].save_corrected_transcript(
            corrected.model_copy(
                update={
                    "transcript_id": f"{corrected.transcript_id}_new",
                    "created_at": datetime.now(timezone.utc),
                }
            ),
            edl_id=edl.edl_id,
        )

    playback = api_test_context["client"].get(
        f"/api/productions/{production_id}/playback"
    )

    assert playback.status_code == 200
    payload = playback.json()
    assert payload["studio_voice_preview_url"] is None
    assert payload["voiceover"]["available"] is False
    assert payload["voiceover"]["url"] is None
    assert payload["voiceover"]["status"] == expected_status


@pytest.mark.asyncio
async def test_voice_selection_regeneration_end_to_end_truth(api_test_context):
    """Verify canonical state contract: selected_voice, rendered_voice, and regeneration."""
    production_id = "prod_voice_selection_truth"
    client = api_test_context["client"]
    edl, corrected = await _seed_voiceover_lineage(
        api_test_context,
        production_id=production_id,
    )
    genai = _RecordingStudioVoiceClient()
    app.dependency_overrides[get_genai_client] = lambda: genai

    # 1. Initial generation with Charon (default from _seed_voiceover_lineage was Charon)
    gen_resp1 = client.post(f"/api/productions/{production_id}/studio-voice")
    assert gen_resp1.status_code == 200
    gen_data1 = gen_resp1.json()
    assert gen_data1["result"]["status"] == "completed"
    assert gen_data1["result"]["voice_id"] == "Charon"
    assert genai.synthesized_voices == ["Charon", "Charon"]

    # Check playback: selected_voice == rendered_voice == "Charon" -> READY
    pb1 = client.get(f"/api/productions/{production_id}/playback")
    assert pb1.status_code == 200
    pb1_data = pb1.json()
    assert pb1_data["voiceover"]["available"] is True
    assert pb1_data["voiceover"]["status"] == "ready"
    assert pb1_data["voiceover"]["voice_id"] == "Charon"
    assert pb1_data["voiceover"]["url"] is not None

    # 2. Select Kore in settings
    put_resp = client.put(
        "/api/workspace/agent-settings/voice",
        json={
            "narration_mode": "studio_voice",
            "selected_voice": "Kore",
            "language": "en-US",
        },
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["selected_voice"] == "Kore"

    # Check playback immediately after selecting Kore:
    # selected_voice = Kore, rendered_voice = Charon -> STALE (needs_regeneration)
    pb2 = client.get(f"/api/productions/{production_id}/playback")
    assert pb2.status_code == 200
    pb2_data = pb2.json()
    assert pb2_data["voiceover"]["available"] is False
    assert pb2_data["voiceover"]["status"] == "needs_regeneration"
    assert pb2_data["voiceover"]["voice_id"] == "Charon"  # Rendered voice is still Charon!
    assert pb2_data["voiceover"]["url"] is None

    # 3. Regenerate Voiceover with Kore (passing voice_id or relying on saved settings)
    genai.synthesized_voices.clear()
    gen_resp2 = client.post(
        f"/api/productions/{production_id}/studio-voice",
        json={"voice_id": "Kore"},
    )
    assert gen_resp2.status_code == 200
    gen_data2 = gen_resp2.json()
    assert gen_data2["result"]["status"] == "completed"
    assert gen_data2["result"]["voice_id"] == "Kore"
    assert genai.synthesized_voices == ["Kore", "Kore"]

    # Check playback: selected_voice == rendered_voice == "Kore" -> READY
    pb3 = client.get(f"/api/productions/{production_id}/playback")
    assert pb3.status_code == 200
    pb3_data = pb3.json()
    assert pb3_data["voiceover"]["available"] is True
    assert pb3_data["voiceover"]["status"] == "ready"
    assert pb3_data["voiceover"]["voice_id"] == "Kore"
    assert pb3_data["voiceover"]["url"] is not None

    # 4. Regenerate with Puck
    genai.synthesized_voices.clear()
    gen_resp3 = client.post(
        f"/api/productions/{production_id}/studio-voice",
        json={"voice_id": "Puck"},
    )
    assert gen_resp3.status_code == 200
    gen_data3 = gen_resp3.json()
    assert gen_data3["result"]["status"] == "completed"
    assert gen_data3["result"]["voice_id"] == "Puck"
    assert genai.synthesized_voices == ["Puck", "Puck"]

    # Check playback: rendered_voice == "Puck"
    pb4 = client.get(f"/api/productions/{production_id}/playback")
    assert pb4.status_code == 200
    pb4_data = pb4.json()
    assert pb4_data["voiceover"]["available"] is True
    assert pb4_data["voiceover"]["status"] == "ready"
    assert pb4_data["voiceover"]["voice_id"] == "Puck"


@pytest.mark.asyncio
async def test_regenerated_voiceover_invalidates_completed_final_mix_until_rebuilt(
    api_test_context,
):
    production_id = "prod_voice_regeneration_final_mix_lineage"
    client = api_test_context["client"]
    render_repo = api_test_context["render_repo"]
    await _seed_voiceover_lineage(
        api_test_context,
        production_id=production_id,
    )
    genai = _RecordingStudioVoiceClient()
    app.dependency_overrides[get_genai_client] = lambda: genai

    initial_generation = client.post(
        f"/api/productions/{production_id}/studio-voice"
    )
    assert initial_generation.status_code == 200
    initial_result = initial_generation.json()["result"]
    assert initial_result["status"] == "completed"
    assert initial_result["voice_id"] == "Charon"
    initial_voiceover_artifact_id = initial_result["preview_artifact_id"]

    initial_final_mix = client.post(
        f"/api/productions/{production_id}/renders/final-mix"
    )
    assert initial_final_mix.status_code == 200
    initial_final_mix_data = initial_final_mix.json()
    assert initial_final_mix_data["status"] == "completed"
    initial_final_mix_artifact = await render_repo.get_render_artifact(
        production_id,
        initial_final_mix_data["artifact_id"],
    )
    assert initial_final_mix_artifact is not None
    assert (
        initial_final_mix_artifact.voiceover_artifact_id
        == initial_voiceover_artifact_id
    )

    initial_playback = client.get(
        f"/api/productions/{production_id}/playback"
    )
    assert initial_playback.status_code == 200
    initial_playback_data = initial_playback.json()
    assert initial_playback_data["final_mix"]["status"] == "ready"
    assert initial_playback_data["final_mix"]["available"] is True
    assert (
        initial_playback_data["final_mix"]["artifact_id"]
        == initial_final_mix_data["artifact_id"]
    )

    voice_response = client.put(
        "/api/workspace/agent-settings/voice",
        json={
            "narration_mode": "studio_voice",
            "selected_voice": "Kore",
            "language": "en-US",
        },
    )
    assert voice_response.status_code == 200

    regenerated = client.post(
        f"/api/productions/{production_id}/studio-voice"
    )
    assert regenerated.status_code == 200
    regenerated_result = regenerated.json()["result"]
    assert regenerated_result["status"] == "completed"
    assert regenerated_result["voice_id"] == "Kore"
    regenerated_voiceover_artifact_id = regenerated_result["preview_artifact_id"]
    assert regenerated_voiceover_artifact_id != initial_voiceover_artifact_id

    stale_playback = client.get(
        f"/api/productions/{production_id}/playback"
    )
    assert stale_playback.status_code == 200
    stale_playback_data = stale_playback.json()
    assert stale_playback_data["final_mix"]["status"] == "needs_regeneration"
    assert stale_playback_data["final_mix"]["available"] is False
    assert stale_playback_data["final_mix"]["url"] is None
    assert stale_playback_data["final_mix_url"] is None
    assert stale_playback_data["voiceover"]["status"] == "ready"
    assert stale_playback_data["voiceover"]["available"] is True
    assert stale_playback_data["voiceover"]["voice_id"] == "Kore"
    assert (
        stale_playback_data["voiceover"]["artifact_id"]
        == regenerated_voiceover_artifact_id
    )
    assert stale_playback_data["voiceover"]["url"] is not None

    rebuilt_final_mix = client.post(
        f"/api/productions/{production_id}/renders/final-mix"
    )
    assert rebuilt_final_mix.status_code == 200
    rebuilt_final_mix_data = rebuilt_final_mix.json()
    assert (
        rebuilt_final_mix_data["artifact_id"]
        != initial_final_mix_data["artifact_id"]
    )
    rebuilt_final_mix_artifact = await render_repo.get_render_artifact(
        production_id,
        rebuilt_final_mix_data["artifact_id"],
    )
    assert rebuilt_final_mix_artifact is not None
    assert (
        rebuilt_final_mix_artifact.voiceover_artifact_id
        == regenerated_voiceover_artifact_id
    )

    rebuilt_playback = client.get(
        f"/api/productions/{production_id}/playback"
    )
    assert rebuilt_playback.status_code == 200
    rebuilt_playback_data = rebuilt_playback.json()
    assert rebuilt_playback_data["final_mix"]["status"] == "ready"
    assert rebuilt_playback_data["final_mix"]["available"] is True
    assert (
        rebuilt_playback_data["final_mix"]["artifact_id"]
        == rebuilt_final_mix_data["artifact_id"]
    )
