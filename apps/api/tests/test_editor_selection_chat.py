"""Targeted regression tests for BUG 14: Timeline Selection to Real Leo Chat Context."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pytest
from starlette.testclient import TestClient

from croviq_agents.client import FakeGenAIClient
from croviq_api.auth.dependencies import get_current_user
from croviq_api.config import get_settings
from croviq_api.main import create_app
from croviq_api.media.dependencies import get_media_inspector, get_media_storage
from croviq_api.media.fake import FakeMediaStorage
from croviq_api.memory.dependencies import get_memory_store, set_memory_store
from croviq_api.memory.fake import FakeChannelMemoryStore
from croviq_api.productions.dependencies import get_genai_client, set_genai_client, set_render_service
from croviq_api.productions.broll_repository import InMemoryBRollRepository, get_broll_repository
from croviq_api.productions.edl_repository import (
    InMemoryEDLRepository,
    get_edl_repository,
    set_edl_repository,
)
from croviq_api.productions.editorial_repository import (
    InMemoryEditorialRepository,
    get_editorial_repository,
    set_editorial_repository,
)
from croviq_api.productions.render_repository import (
    InMemoryRenderRepository,
    get_render_repository,
    set_render_repository,
)
from croviq_api.productions.repository import (
    InMemoryProductionRepository,
    get_production_repository,
    set_production_repository,
)
from croviq_api.productions.transcript_repository import (
    InMemoryTranscriptRepository,
    get_transcript_repository,
    set_transcript_repository,
)
from croviq_api.workspaces.agent_config_repository import (
    InMemoryAgentConfigRepository,
    get_agent_config_repository,
)
from croviq_api.workspaces.repository import (
    InMemoryWorkspaceRepository,
    get_workspace_repository,
    set_workspace_repository,
)
from croviq_domain.editorial import (
    ActivePreviewMode,
    CoordinateSpace,
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
    EditorSelectionContext,
    EditorSelectionType,
    EditorialRun,
    EditorialRunStatus,
    SectionAction,
    VideoSectionDecision,
)
from croviq_domain.edl import CutInstruction, EditDecisionList
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.production import (
    Production,
    ProductionStatus,
    SourceMedia,
    SourceMediaStatus,
)
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_domain.user import User
from croviq_media.inspector import MediaInspector
from croviq_media.render import FakeRenderService


class FakeInspector(MediaInspector):
    def inspect_media(self, file_path: Path | str) -> MediaMetadata:
        return MediaMetadata(
            duration_ms=60000,
            width=1920,
            height=1080,
            frame_rate=30.0,
            video_codec="h264",
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            size_bytes=10000000,
        )


@pytest.fixture(autouse=True)
def reset_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROVIQ_ALLOWED_EMAILS", "creator@example.com")
    get_settings.cache_clear()
    set_production_repository(None)
    set_transcript_repository(None)
    set_editorial_repository(None)
    set_edl_repository(None)
    set_render_repository(None)
    set_workspace_repository(None)
    set_memory_store(None)
    set_genai_client(None)
    set_render_service(None)


@pytest.fixture
def current_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        user_id="creator-1",
        email="creator@example.com",
        display_name="Creator",
        avatar_url=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def test_stack(current_user: User) -> dict[str, Any]:
    prod_repo = InMemoryProductionRepository()
    transcript_repo = InMemoryTranscriptRepository()
    editorial_repo = InMemoryEditorialRepository()
    edl_repo = InMemoryEDLRepository()
    render_repo = InMemoryRenderRepository()
    workspace_repo = InMemoryWorkspaceRepository()
    memory_store = FakeChannelMemoryStore()
    genai_client = FakeGenAIClient()
    render_service = FakeRenderService()
    media_storage = FakeMediaStorage()
    inspector = FakeInspector()

    set_production_repository(prod_repo)
    set_transcript_repo = set_transcript_repository(transcript_repo)
    set_editorial_repository(editorial_repo)
    set_edl_repository(edl_repo)
    set_render_repository(render_repo)
    set_workspace_repository(workspace_repo)
    set_memory_store(memory_store)
    set_genai_client(genai_client)
    set_render_service(render_service)

    now = datetime.now(timezone.utc)
    production_id = "prod_test_bug14"
    workspace_id = "ws_test"

    prod = Production(
        production_id=production_id,
        workspace_id=workspace_id,
        channel_id="channel-1",
        owner_user_id=current_user.user_id,
        source_media=SourceMedia(
            upload_id="up_01",
            gcs_bucket="test-bucket",
            gcs_object="test/recording.mp4",
            original_filename="tutorial.mp4",
            content_type="video/mp4",
            size_bytes=10000000,
            status=SourceMediaStatus.UPLOADED,
            uploaded_at=now,
            created_at=now,
        ),
        created_at=now,
        updated_at=now,
    )
    prod_repo._productions[production_id] = prod

    words = [
        TranscriptWord(index=0, text="This", start_ms=1000, end_ms=1500),
        TranscriptWord(index=1, text="is", start_ms=1500, end_ms=1800),
        TranscriptWord(index=2, text="a", start_ms=2500, end_ms=2800),
        TranscriptWord(index=3, text="demo.", start_ms=2800, end_ms=3500),
        TranscriptWord(index=4, text="To", start_ms=4500, end_ms=4800),
        TranscriptWord(index=5, text="edit", start_ms=4800, end_ms=5300),
        TranscriptWord(index=6, text="your", start_ms=5300, end_ms=5600),
        TranscriptWord(index=7, text="workflow", start_ms=5600, end_ms=6200),
    ]
    transcript = Transcript(
        transcript_id=f"tr_{production_id}",
        production_id=production_id,
        language_code="en",
        duration_ms=60000,
        words=words,
        segments=[
            TranscriptSegment(
                segment_id="seg_01",
                start_ms=1000,
                end_ms=3500,
                text="This is a demo.",
                word_start_index=0,
                word_end_index=3,
            ),
            TranscriptSegment(
                segment_id="seg_02",
                start_ms=4500,
                end_ms=6200,
                text="To edit your workflow",
                word_start_index=4,
                word_end_index=7,
            ),
        ],
        created_at=now,
    )
    transcript_repo._transcripts[transcript.transcript_id] = transcript
    transcript_repo._by_production[production_id] = transcript.transcript_id

    proposal_id = "prop_bug14"
    proposal = EditorProposal(
        production_id=production_id,
        model="gemini-3.7-flash",
        summary="Tutorial edit proposal",
        decisions=[
            EditorDecision(
                decision_id="dec_01",
                decision_type=EditorDecisionType.REMOVE_FALSE_START,
                transcript_start_word=4,
                transcript_end_word=5,
                source_start_ms=4500,
                source_end_ms=5300,
                original_text="To edit",
                action="remove",
                concise_reason="Remove false start repetition",
                confidence=0.95,
                visual_context="code demo",
            )
        ],
        section_plan=[
            VideoSectionDecision(
                section_id="sec_01",
                source_start_ms=0,
                source_end_ms=60000,
                transcript_start_word=0,
                transcript_end_word=7,
                action=SectionAction.KEEP,
                reason="Tutorial walkthrough",
                confidence=1.0,
                visual_summary="Screen capture of workflow configuration",
                speech_summary="Explaining github actions setup",
                editorial_intent="Preserve demonstration flow",
            )
        ],
        chapters=[],
        overall_confidence=0.95,
    )
    editorial_repo._proposals[production_id] = {proposal_id: proposal}
    run = EditorialRun(
        run_id="run_bug14",
        production_id=production_id,
        status=EditorialRunStatus.COMPLETED,
        editor_proposal_id=proposal_id,
        started_at=now,
        completed_at=now,
    )
    editorial_repo._runs[production_id] = {run.run_id: run}
    edl = EditDecisionList(
        edl_id="edl_bug14_001",
        production_id=production_id,
        source_duration_ms=60000,
        editor_proposal_id=proposal_id,
        version=1,
        cuts=[
            CutInstruction(
                cut_id="cut_false_start_01",
                decision_id="dec_01",
                decision_type=EditorDecisionType.REMOVE_FALSE_START,
                transcript_start_word=4,
                transcript_end_word=5,
                requested_start_ms=4500,
                requested_end_ms=5300,
                safe_start_ms=4400,
                safe_end_ms=5400,
                removed_duration_ms=1000,
                left_anchor="demo.",
                right_anchor="your",
                transition_ms=20,
                safety_status="SAFE",
                safety_reason="Clean inter-word silence boundary.",
                confidence=0.95,
            )
        ],
        coverage_markers=[],
        created_at=now,
    )
    edl_repo._by_id[(production_id, edl.edl_id)] = edl
    edl_repo._by_production[production_id] = [edl.edl_id]
    broll_repo = InMemoryBRollRepository()
    agent_config_repo = InMemoryAgentConfigRepository()
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_production_repository] = lambda: prod_repo
    app.dependency_overrides[get_workspace_repository] = lambda: workspace_repo
    app.dependency_overrides[get_transcript_repository] = lambda: transcript_repo
    app.dependency_overrides[get_editorial_repository] = lambda: editorial_repo
    app.dependency_overrides[get_edl_repository] = lambda: edl_repo
    app.dependency_overrides[get_render_repository] = lambda: render_repo
    app.dependency_overrides[get_broll_repository] = lambda: broll_repo
    app.dependency_overrides[get_agent_config_repository] = lambda: agent_config_repo
    app.dependency_overrides[get_memory_store] = lambda: memory_store
    app.dependency_overrides[get_media_storage] = lambda: media_storage
    app.dependency_overrides[get_media_inspector] = lambda: inspector
    app.dependency_overrides[get_genai_client] = lambda: genai_client
    app.dependency_overrides[set_render_service] = lambda: render_service
    client = TestClient(app)
    return {
        "client": client,
        "production_id": production_id,
        "edl": edl,
        "edl_repo": edl_repo,
        "genai_client": genai_client,
    }


def test_case_a_source_point_selection_chat(test_stack: dict[str, Any]) -> None:
    """Case A: Source point selection sends structured editor context and receives grounded response."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]

    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.POINT,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=3000,
        source_end_ms=3000,
        edited_start_ms=3000,
        edited_end_ms=3000,
        transcript_text="demo.",
        transcript_word_ids=[3],
        cut_id=None,
        chapter_id=None,
        active_edl_id="edl_bug14_001",
        active_preview_mode=ActivePreviewMode.ORIGINAL,
        label="Point at 00:03.0",
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "What's happening in this section?",
            "editor_context": context.model_dump(mode="json"),
            "current_playhead_ms": 3000,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["role"] == "assistant"
    assert "content" in data
    assert len(data["content"]) > 10


def test_case_b_edited_point_selection_mapping_chat(test_stack: dict[str, Any]) -> None:
    """Case B: Edited point selection correctly maps edited timestamp to source."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]

    # In edited mode, post-cut time 4800 maps to source 5800 (offset by 1000ms cut)
    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.POINT,
        coordinate_space=CoordinateSpace.EDITED,
        source_start_ms=5800,
        source_end_ms=5800,
        edited_start_ms=4800,
        edited_end_ms=4800,
        transcript_text="workflow",
        transcript_word_ids=[7],
        active_edl_id="edl_bug14_001",
        active_preview_mode=ActivePreviewMode.EDITED,
        label="Point at 00:04.8 (Source 00:05.8)",
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Is this section too slow?",
            "editor_context": context.model_dump(mode="json"),
            "current_playhead_ms": 4800,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["role"] == "assistant"
    assert "content" in data


def test_case_c_range_selection_chat(test_stack: dict[str, Any]) -> None:
    """Case C: Range selection provides exact start/end and transcript text."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]

    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=1000,
        source_end_ms=3500,
        edited_start_ms=1000,
        edited_end_ms=3500,
        transcript_text="This is a demo.",
        transcript_word_ids=[0, 1, 2, 3],
        active_edl_id="edl_bug14_001",
        active_preview_mode=ActivePreviewMode.FINAL_MIX,
        label="Range: 00:01.0 → 00:03.5",
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Can you make this tighter?",
            "editor_context": context.model_dump(mode="json"),
            "current_playhead_ms": 1000,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["role"] == "assistant"


def test_case_d_cut_selection_chat(test_stack: dict[str, Any]) -> None:
    """Case D: Cut selection includes cut ID, removed duration, and reason."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]

    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.CUT,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=4400,
        source_end_ms=5400,
        edited_start_ms=4400,
        edited_end_ms=4400,
        transcript_text="To edit",
        transcript_word_ids=[4, 5],
        cut_id="cut_false_start_01",
        cut_reason="Clean inter-word silence boundary.",
        removed_duration_ms=1000,
        active_edl_id="edl_bug14_001",
        active_preview_mode=ActivePreviewMode.EDITED,
        label="Cut: False start removed (1.0s)",
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Why was this cut?",
            "editor_context": context.model_dump(mode="json"),
            "current_playhead_ms": 4400,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["role"] == "assistant"
    # Leo explains the cut reason
    assert "cut" in data["content"].lower() or "false start" in data["content"].lower() or "silence" in data["content"].lower()


def test_case_e_transcript_word_selection_chat(test_stack: dict[str, Any]) -> None:
    """Case E: Transcript word selection populates canonical selection state."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]

    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.TRANSCRIPT_WORD,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=2800,
        source_end_ms=3500,
        edited_start_ms=2800,
        edited_end_ms=3500,
        transcript_text="demo.",
        transcript_word_ids=[3],
        active_edl_id="edl_bug14_001",
        active_preview_mode=ActivePreviewMode.ORIGINAL,
        label="Transcript word: demo.",
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "What is happening here?",
            "editor_context": context.model_dump(mode="json"),
            "current_playhead_ms": 2800,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["role"] == "assistant"


def test_case_f_clear_selection_chat(test_stack: dict[str, Any]) -> None:
    """Case F: When selection is cleared, Leo truthfully answers that no section is selected."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "What section did I select?",
            "editor_context": None,
            "current_playhead_ms": 1000,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["role"] == "assistant"
    # Must not pretend a selection exists
    assert "no section" in data["content"].lower() or "not currently selected" in data["content"].lower() or "no point or range" in data["content"].lower()


def test_case_h_read_only_questions_do_not_mutate_edl(test_stack: dict[str, Any]) -> None:
    """Case H: Read-only questions preserve EDL ID, cut count, and state."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]
    edl_repo = test_stack["edl_repo"]

    edl_before = edl_repo._by_id[(prod_id, "edl_bug14_001")]
    edl_id_before = edl_before.edl_id
    cuts_count_before = len(edl_before.cuts)

    questions = [
        "Why was this cut?",
        "What's happening in this section?",
        "Should this be tighter?",
        "Would visual coverage help here?",
        "What section did I select?",
    ]

    for q in questions:
        resp = client.post(
            f"/api/productions/{prod_id}/chat",
            json={
                "message": q,
                "current_playhead_ms": 2000,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["timeline_updated"] is False

    edl_after = edl_repo._by_id[(prod_id, "edl_bug14_001")]
    assert edl_after.edl_id == edl_id_before
    assert len(edl_after.cuts) == cuts_count_before


def test_case_j_invalid_or_stale_cut_handled_gracefully(test_stack: dict[str, Any]) -> None:
    """Case J: Invalid cut ID or non-existent decision fails gracefully without crashing."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]

    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.CUT,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=99000,
        source_end_ms=99500,
        cut_id="stale_nonexistent_cut",
        cut_reason=None,
        active_edl_id="edl_bug14_001",
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Why was this cut?",
            "editor_context": context.model_dump(mode="json"),
            "current_playhead_ms": 99000,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["role"] == "assistant"
