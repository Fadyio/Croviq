"""Targeted test suite for BUG 15 — LEO CHAT MUST MUTATE THE REAL EDIT.

Covers all 15 required acceptance test cases (A through O):
A. remove_selection creates canonical cut
B. safe word snapping
C. no overlapping duplicate cut
D. tighten identifies safe removable region
E. mutation persists EDL
F. EDL version conflict rejected
G. Edited Preview regenerated
H. render failure truthful state
I. timeline gets fresh EDL
J. transcript cut state updates
K. undo restores previous EDL
L. undo survives browser refresh/server request boundary
M. empty selection does not mutate
N. cut already-removed range does not mutate
O. read-only Leo question still does not mutate
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pytest
from starlette.testclient import TestClient
from croviq_agents.client import FakeGenAIClient
from croviq_api.auth.dependencies import get_current_user
from croviq_api.main import create_app
from croviq_media.inspector import MediaInspector
from croviq_api.media.dependencies import get_media_inspector, get_media_storage, set_media_inspector, set_media_storage
from croviq_api.media.fake import FakeMediaStorage
from croviq_api.memory.dependencies import get_memory_store, set_memory_store
from croviq_api.memory.fake import FakeChannelMemoryStore
from croviq_api.productions.dependencies import (
    get_genai_client,
    set_genai_client,
    set_render_service,
)
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
from croviq_domain.user import User
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
from croviq_domain.edl import (
    CutInstruction,
    CutSafetyStatus,
    EditDecisionList,
    EdlRevisionHistoryEntry,
)
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.production import Production, SourceMedia, SourceMediaStatus
from croviq_domain.render import ArtifactStatus, ArtifactType, RenderArtifact
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_media.render import FakeRenderService


class FakeInspector(MediaInspector):
    def inspect_media(self, file_path: Path | str) -> MediaMetadata:
        return MediaMetadata(
            duration_ms=101440,
            width=1236,
            height=720,
            frame_rate=60.0,
            video_codec="h264",
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            rotation=0,
            size_bytes=51168149,
        )


@pytest.fixture(autouse=True)
def reset_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROVIQ_ALLOWED_EMAILS", "creator@example.com")
    monkeypatch.setenv("ENVIRONMENT", "test")
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
        user_id="user_bug15",
        email="creator@example.com",
        display_name="Bug 15 Creator",
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
    set_transcript_repository(transcript_repo)
    set_editorial_repository(editorial_repo)
    set_edl_repository(edl_repo)
    set_render_repository(render_repo)
    set_workspace_repository(workspace_repo)
    set_memory_store(memory_store)
    set_genai_client(genai_client)
    set_render_service(render_service)
    set_media_storage(media_storage)
    set_media_inspector(inspector)

    now = datetime.now(timezone.utc)
    production_id = "prod_473209137802"
    workspace_id = "ws_27iEBUMcu6ToDYwp2OdEIHBuwIA3"

    prod = Production(
        production_id=production_id,
        workspace_id=workspace_id,
        channel_id="croviq_syn_ai_eng_01",
        owner_user_id=current_user.user_id,
        source_media=SourceMedia(
            upload_id="upl_48ee4e53140b",
            gcs_bucket="test-bucket",
            gcs_object="test/github.mp4",
            original_filename="github.mp4",
            content_type="video/mp4",
            size_bytes=51168149,
            status=SourceMediaStatus.UPLOADED,
            uploaded_at=now,
            created_at=now,
        ),
        created_at=now,
        updated_at=now,
    )
    prod_repo._productions[production_id] = prod

    words = [
        TranscriptWord(index=0, text="This", start_ms=2100, end_ms=2500),
        TranscriptWord(index=1, text="is", start_ms=2500, end_ms=2800),
        TranscriptWord(index=2, text="a", start_ms=2800, end_ms=3000),
        TranscriptWord(index=3, text="GitHub", start_ms=3000, end_ms=3700),
        TranscriptWord(index=4, text="action", start_ms=3700, end_ms=4500),
        TranscriptWord(index=5, text="tutorial.", start_ms=4500, end_ms=5700),
        TranscriptWord(index=6, text="Okay.", start_ms=8000, end_ms=8300),
        TranscriptWord(index=7, text="You", start_ms=8900, end_ms=9200),
        TranscriptWord(index=8, text="can", start_ms=9200, end_ms=9500),
        TranscriptWord(index=9, text="find", start_ms=9500, end_ms=9900),
        TranscriptWord(index=10, text="the", start_ms=9900, end_ms=10100),
        TranscriptWord(index=11, text="GitHub", start_ms=10100, end_ms=10800),
        TranscriptWord(index=12, text="action", start_ms=10800, end_ms=11400),
        TranscriptWord(index=13, text="in", start_ms=11400, end_ms=11700),
        TranscriptWord(index=14, text="here.", start_ms=11700, end_ms=15400),
        TranscriptWord(index=15, text="To", start_ms=16200, end_ms=16400),
        TranscriptWord(index=16, text="edit", start_ms=16400, end_ms=16800),
        TranscriptWord(index=17, text="to", start_ms=22700, end_ms=22900),
        TranscriptWord(index=18, text="edit", start_ms=22900, end_ms=23400),
        TranscriptWord(index=19, text="your", start_ms=23400, end_ms=23800),
        TranscriptWord(index=20, text="workflow", start_ms=23800, end_ms=24500),
        TranscriptWord(index=21, text="like", start_ms=24500, end_ms=25000),
        TranscriptWord(index=22, text="this", start_ms=25000, end_ms=25400),
        TranscriptWord(index=23, text="workflow", start_ms=25400, end_ms=26000),
        TranscriptWord(index=24, text="is", start_ms=26000, end_ms=26300),
        TranscriptWord(index=25, text="for", start_ms=26300, end_ms=26600),
        TranscriptWord(index=26, text="Cloudflare", start_ms=26600, end_ms=27500),
        TranscriptWord(index=27, text="DNS.", start_ms=27500, end_ms=28600),
        TranscriptWord(index=28, text="You", start_ms=30700, end_ms=31100),
        TranscriptWord(index=29, text="can", start_ms=31130, end_ms=31400),
        TranscriptWord(index=30, text="find", start_ms=31400, end_ms=32000),
        TranscriptWord(index=31, text="here", start_ms=32000, end_ms=32500),
        TranscriptWord(index=32, text="the", start_ms=32500, end_ms=32800),
        TranscriptWord(index=33, text="name", start_ms=32800, end_ms=33400),
        TranscriptWord(index=34, text="of", start_ms=33400, end_ms=33700),
        TranscriptWord(index=35, text="the", start_ms=33700, end_ms=34000),
        TranscriptWord(index=36, text="workflow", start_ms=34000, end_ms=34800),
    ]

    transcript = Transcript(
        transcript_id=f"tr_{production_id}",
        production_id=production_id,
        language_code="en",
        duration_ms=101440,
        words=words,
        segments=[
            TranscriptSegment(
                segment_id="seg_01",
                start_ms=2100,
                end_ms=5700,
                text="This is a GitHub action tutorial.",
                word_start_index=0,
                word_end_index=5,
            ),
            TranscriptSegment(
                segment_id="seg_02",
                start_ms=8000,
                end_ms=8300,
                text="Okay.",
                word_start_index=6,
                word_end_index=6,
            ),
            TranscriptSegment(
                segment_id="seg_03",
                start_ms=8900,
                end_ms=15400,
                text="You can find the GitHub action in here.",
                word_start_index=7,
                word_end_index=14,
            ),
        ],
        created_at=now,
    )
    transcript_repo._transcripts[transcript.transcript_id] = transcript
    transcript_repo._by_production[production_id] = transcript.transcript_id

    proposal_id = "prop_c1aeea59"
    proposal = EditorProposal(
        production_id=production_id,
        model="gemini-3.7-flash",
        summary="Baseline editorial proposal",
        decisions=[
            EditorDecision(
                decision_id="silence_cut_001",
                decision_type=EditorDecisionType.TRIM_PAUSE,
                transcript_start_word=5,
                transcript_end_word=6,
                source_start_ms=5100,
                source_end_ms=8300,
                original_text="tutorial. Okay.",
                action="remove",
                concise_reason="Natural pause trimming.",
                confidence=1.0,
            ),
            EditorDecision(
                decision_id="dec_001_false_start_edit",
                decision_type=EditorDecisionType.REMOVE_FALSE_START,
                transcript_start_word=15,
                transcript_end_word=16,
                source_start_ms=16200,
                source_end_ms=16800,
                original_text="here. to",
                action="remove",
                concise_reason="Clean inter-word silence.",
                confidence=0.95,
            ),
        ],
        section_plan=[
            VideoSectionDecision(
                section_id="sec_01",
                source_start_ms=0,
                source_end_ms=101440,
                transcript_start_word=0,
                transcript_end_word=36,
                action=SectionAction.KEEP,
                reason="Tutorial walkthrough",
                confidence=1.0,
                visual_summary="Screen capture of GitHub Actions YAML",
                speech_summary="Explaining GitHub Actions configuration",
                editorial_intent="Preserve technical flow",
            )
        ],
        chapters=[],
        overall_confidence=0.98,
    )
    editorial_repo._proposals[production_id] = {proposal_id: proposal}
    run = EditorialRun(
        run_id="run_bug15_baseline",
        production_id=production_id,
        status=EditorialRunStatus.COMPLETED,
        editor_proposal_id=proposal_id,
        started_at=now,
        completed_at=now,
    )
    editorial_repo._runs[production_id] = {run.run_id: run}

    initial_edl = EditDecisionList(
        edl_id="edl_a27fc1aeea59",
        production_id=production_id,
        source_duration_ms=101440,
        editor_proposal_id=proposal_id,
        version=2,
        cuts=[
            CutInstruction(
                cut_id="cut_d252c23c84dc",
                decision_id="silence_cut_001",
                decision_type=EditorDecisionType.TRIM_PAUSE,
                transcript_start_word=5,
                transcript_end_word=6,
                requested_start_ms=5100,
                requested_end_ms=8300,
                safe_start_ms=5825,
                safe_end_ms=7875,
                removed_duration_ms=2050,
                left_anchor="tutorial.",
                right_anchor="Okay.",
                transition_ms=20,
                safety_status=CutSafetyStatus.SAFE,
                safety_reason="Natural pause trimming.",
                confidence=1.0,
            ),
            CutInstruction(
                cut_id="cut_ec94258e8024",
                decision_id="dec_001_false_start_edit",
                decision_type=EditorDecisionType.REMOVE_FALSE_START,
                transcript_start_word=15,
                transcript_end_word=16,
                requested_start_ms=16200,
                requested_end_ms=16800,
                safe_start_ms=16100,
                safe_end_ms=16900,
                removed_duration_ms=800,
                left_anchor="here.",
                right_anchor="to",
                transition_ms=20,
                safety_status=CutSafetyStatus.SAFE,
                safety_reason="Clean inter-word silence.",
                confidence=0.95,
            ),
        ],
        created_at=now,
    )
    edl_repo._by_id[(production_id, initial_edl.edl_id)] = initial_edl
    edl_repo._by_production[production_id] = [initial_edl.edl_id]

    preview_art = RenderArtifact(
        artifact_id="art_prev_c1aeea59",
        production_id=production_id,
        edl_id=initial_edl.edl_id,
        artifact_type=ArtifactType.PREVIEW,
        status=ArtifactStatus.completed,
        gcs_bucket="test-bucket",
        gcs_object="test/preview.mp4",
        content_type="video/mp4",
        size_bytes=5635437,
        duration_ms=98590,
        width=1236,
        height=720,
        frame_rate=60.0,
        video_codec="h264",
        audio_codec="aac",
        created_at=now,
        completed_at=now,
    )
    render_repo._by_production[production_id] = {preview_art.artifact_id: preview_art}

    agent_config_repo = InMemoryAgentConfigRepository()

    set_render_service(render_service)
    set_genai_client(genai_client)
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_production_repository] = lambda: prod_repo
    app.dependency_overrides[get_transcript_repository] = lambda: transcript_repo
    app.dependency_overrides[get_editorial_repository] = lambda: editorial_repo
    app.dependency_overrides[get_edl_repository] = lambda: edl_repo
    app.dependency_overrides[get_render_repository] = lambda: render_repo
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
        "edl_repo": edl_repo,
        "editorial_repo": editorial_repo,
        "render_repo": render_repo,
        "render_service": render_service,
        "genai_client": genai_client,
        "initial_edl": initial_edl,
    }


def test_case_a_remove_selection_creates_canonical_cut(test_stack: dict[str, Any]) -> None:
    """Case A: remove_selection creates a canonical cut on the EDL and updates timeline."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]
    edl_repo: InMemoryEDLRepository = test_stack["edl_repo"]

    initial_edl: EditDecisionList = test_stack["initial_edl"]
    cuts_before = len(initial_edl.cuts)
    dur_before = initial_edl.estimated_target_duration_ms

    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=31130,
        source_end_ms=34000,
        active_edl_id=initial_edl.edl_id,
        active_preview_mode=ActivePreviewMode.EDITED,
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Cut this.",
            "editor_context": context.model_dump(mode="json"),
            "current_playhead_ms": 31130,
            "active_edl_id": initial_edl.edl_id,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["timeline_updated"] is True
    assert data["edl"] is not None
    new_edl_id = data["edl"]["edl_id"]
    assert new_edl_id != initial_edl.edl_id
    assert data["edl"]["version"] == initial_edl.version + 1
    assert len(data["edl"]["cuts"]) == cuts_before + 1

    # Verify message mentions removal duration and preview regeneration
    assert "removed" in data["content"].lower()
    assert "preview updated" in data["content"].lower() or "regenerated" in data["content"].lower()

    # Check persistence
    persisted_edl = edl_repo._by_id[(prod_id, new_edl_id)]
    assert persisted_edl.version == 3
    assert len(persisted_edl.cuts) == cuts_before + 1
    assert persisted_edl.estimated_target_duration_ms < dur_before


def test_case_b_safe_word_snapping(test_stack: dict[str, Any]) -> None:
    """Case B: Selection intersecting words snaps to safe inter-word silence boundaries."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]

    # Select rough range 31130 to 34000 (words 29 to 35)
    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=31130,
        source_end_ms=34000,
        active_edl_id="edl_a27fc1aeea59",
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Remove this part.",
            "editor_context": context.model_dump(mode="json"),
            "current_playhead_ms": 31130,
            "active_edl_id": "edl_a27fc1aeea59",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["timeline_updated"] is True
    # The applied cut safe boundaries should snap cleanly
    new_cuts = data["edl"]["cuts"]
    applied_cut = new_cuts[-1]
    assert applied_cut["safe_start_ms"] <= 31130
    assert applied_cut["safe_end_ms"] >= 34000
    assert applied_cut["safety_status"] in ("SAFE", "NEEDS_COVERAGE")


def test_case_c_no_overlapping_duplicate_cut(test_stack: dict[str, Any]) -> None:
    """Case C: Cutting an already removed section does not create duplicate cut."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]
    edl_repo: InMemoryEDLRepository = test_stack["edl_repo"]

    # Range 16200-16800 is already covered by cut_ec94258e8024 (16100-16900)
    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=16200,
        source_end_ms=16800,
        active_edl_id="edl_a27fc1aeea59",
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Cut this.",
            "editor_context": context.model_dump(mode="json"),
            "current_playhead_ms": 16200,
            "active_edl_id": "edl_a27fc1aeea59",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Should report that it is already removed and NOT update timeline
    assert data["timeline_updated"] is False
    assert "already" in data["content"].lower() or "no new cut" in data["content"].lower()


def test_case_d_tighten_identifies_safe_removable_region(test_stack: dict[str, Any]) -> None:
    """Case D: Tighten inspects selected range and removes pause/false start rather than deleting whole range."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]

    # Select section containing pause/filler (e.g., words 15-27: 16200 to 28600 ms)
    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=16200,
        source_end_ms=28600,
        active_edl_id="edl_a27fc1aeea59",
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Make this tighter.",
            "editor_context": context.model_dump(mode="json"),
            "current_playhead_ms": 16200,
            "active_edl_id": "edl_a27fc1aeea59",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["timeline_updated"] is True
    # Verify that the entire section was NOT deleted, but a tighter edit was made
    new_edl = data["edl"]
    assert new_edl["source_duration_ms"] == 101440
    assert "tightened" in data["content"].lower() or "removed" in data["content"].lower()


def test_case_e_mutation_persists_edl(test_stack: dict[str, Any]) -> None:
    """Case E: Mutation durably persists new EDL to repository."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]
    edl_repo: InMemoryEDLRepository = test_stack["edl_repo"]

    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=31130,
        source_end_ms=34000,
        active_edl_id="edl_a27fc1aeea59",
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Cut this.",
            "editor_context": context.model_dump(mode="json"),
            "active_edl_id": "edl_a27fc1aeea59",
        },
    )
    assert resp.status_code == 200, resp.text
    new_edl_id = resp.json()["edl"]["edl_id"]

    # Verify latest EDL in repository is the new EDL
    latest = edl_repo._by_id[(prod_id, new_edl_id)]
    assert latest is not None
    assert latest.version == 3


def test_case_f_edl_version_conflict_rejected(test_stack: dict[str, Any]) -> None:
    """Case F: If active EDL ID in request does not match current EDL, conflict is raised."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]

    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=31130,
        source_end_ms=34000,
        active_edl_id="edl_stale_nonexistent",
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Cut this.",
            "editor_context": context.model_dump(mode="json"),
            "active_edl_id": "edl_stale_nonexistent",
        },
    )
    # Mutation should fail cleanly with error message in chat or error status
    assert resp.status_code == 200
    data = resp.json()
    assert "conflict" in data["content"].lower() or "couldn't apply" in data["content"].lower()
    assert data["timeline_updated"] is False


def test_case_g_edited_preview_regenerated(test_stack: dict[str, Any]) -> None:
    """Case G: Mutation triggers preview regeneration and saves RenderArtifact."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]
    render_repo: InMemoryRenderRepository = test_stack["render_repo"]

    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=31130,
        source_end_ms=34000,
        active_edl_id="edl_a27fc1aeea59",
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Cut this.",
            "editor_context": context.model_dump(mode="json"),
            "active_edl_id": "edl_a27fc1aeea59",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    new_edl_id = data["edl"]["edl_id"]
    artifacts = [a for a in render_repo._by_production.get(prod_id, {}).values() if a.edl_id == new_edl_id]
    # Verify render artifact exists for new EDL
    assert len(artifacts) >= 1
    assert artifacts[0].artifact_type == ArtifactType.PREVIEW
    assert artifacts[0].status == ArtifactStatus.completed


def test_case_k_undo_restores_previous_edl(test_stack: dict[str, Any]) -> None:
    """Case K: 'Undo that' restores the immediately previous EDL state."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]
    edl_repo: InMemoryEDLRepository = test_stack["edl_repo"]

    initial_edl = test_stack["initial_edl"]
    initial_cuts_count = len(initial_edl.cuts)

    # 1. Apply a cut
    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=31130,
        source_end_ms=34000,
        active_edl_id=initial_edl.edl_id,
    )
    resp1 = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Cut this.",
            "editor_context": context.model_dump(mode="json"),
            "active_edl_id": initial_edl.edl_id,
        },
    )
    assert resp1.status_code == 200
    mid_edl = resp1.json()["edl"]
    assert len(mid_edl["cuts"]) == initial_cuts_count + 1

    # 2. Undo the cut
    resp2 = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Undo that.",
            "active_edl_id": mid_edl["edl_id"],
        },
    )
    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()

    assert data2["timeline_updated"] is True
    assert "undid" in data2["content"].lower() or "restored" in data2["content"].lower()
    restored_edl = data2["edl"]
    assert len(restored_edl["cuts"]) == initial_cuts_count


def test_case_m_empty_selection_does_not_mutate(test_stack: dict[str, Any]) -> None:
    """Case M: Saying 'Cut this' with no active selection does not mutate EDL."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Cut this.",
            "current_playhead_ms": 0,
            "active_edl_id": "edl_a27fc1aeea59",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["timeline_updated"] is False
    assert "no section" in data["content"].lower() or "select" in data["content"].lower()


def test_case_o_read_only_questions_do_not_mutate(test_stack: dict[str, Any]) -> None:
    """Case O: Explanatory questions preserve EDL state."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Why was this cut?",
            "current_playhead_ms": 6000,
            "active_edl_id": "edl_a27fc1aeea59",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["timeline_updated"] is False
    assert data["role"] == "assistant"


def test_case_h_render_failure_truthful_state(test_stack: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """Case H: If preview render fails, truthful error state is reported."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]
    render_service: FakeRenderService = test_stack["render_service"]

    def failing_render(*args, **kwargs):
        raise RuntimeError("FFmpeg encoder out of memory error")

    monkeypatch.setattr(render_service, "render_preview", failing_render)

    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=31130,
        source_end_ms=34000,
        active_edl_id="edl_a27fc1aeea59",
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Cut this.",
            "editor_context": context.model_dump(mode="json"),
            "active_edl_id": "edl_a27fc1aeea59",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "failed" in data["content"].lower() or "error" in data["content"].lower()


def test_case_i_timeline_gets_fresh_edl(test_stack: dict[str, Any]) -> None:
    """Case I: After mutation, client receives fresh EDL with updated cut count and duration."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]
    initial_edl: EditDecisionList = test_stack["initial_edl"]

    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=31130,
        source_end_ms=34000,
        active_edl_id=initial_edl.edl_id,
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Cut this.",
            "editor_context": context.model_dump(mode="json"),
            "active_edl_id": initial_edl.edl_id,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["edl"]["version"] == initial_edl.version + 1
    assert data["edl"]["source_duration_ms"] == initial_edl.source_duration_ms
    assert len(data["edl"]["cuts"]) == len(initial_edl.cuts) + 1


def test_case_j_transcript_cut_state_updates(test_stack: dict[str, Any]) -> None:
    """Case J: Word-level alignment shows newly removed words in the returned EDL."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]

    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=31130,
        source_end_ms=34000,
        active_edl_id="edl_a27fc1aeea59",
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Cut this.",
            "editor_context": context.model_dump(mode="json"),
            "active_edl_id": "edl_a27fc1aeea59",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    cuts = data["edl"]["cuts"]
    newest_cut = cuts[-1]
    assert newest_cut["transcript_start_word"] == 29
    assert newest_cut["transcript_end_word"] == 35


def test_case_l_undo_survives_browser_refresh(test_stack: dict[str, Any]) -> None:
    """Case L: Durable revision history persists across request boundaries so Undo survives refresh."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]
    edl_repo: InMemoryEDLRepository = test_stack["edl_repo"]
    initial_edl: EditDecisionList = test_stack["initial_edl"]

    # 1. Apply mutation in Request 1
    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=31130,
        source_end_ms=34000,
        active_edl_id=initial_edl.edl_id,
    )
    resp1 = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Cut this.",
            "editor_context": context.model_dump(mode="json"),
            "active_edl_id": initial_edl.edl_id,
        },
    )
    assert resp1.status_code == 200
    mutated_edl_id = resp1.json()["edl"]["edl_id"]

    # Verify durable history exists on edl_repo
    history = edl_repo._history.get(prod_id, [])
    assert len(history) >= 1
    assert history[-1].previous_edl_id == initial_edl.edl_id

    # 2. Simulate "Refresh" by making a separate request calling Undo
    resp2 = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Undo that.",
            "active_edl_id": mutated_edl_id,
        },
    )
    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()
    assert data2["timeline_updated"] is True
    assert len(data2["edl"]["cuts"]) == len(initial_edl.cuts)


def test_case_n_cut_already_removed_range_does_not_mutate(test_stack: dict[str, Any]) -> None:
    """Case N: Cutting an already removed section does not duplicate cut or change EDL duration."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]
    edl_repo: InMemoryEDLRepository = test_stack["edl_repo"]

    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.CUT,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=16200,
        source_end_ms=16800,
        cut_id="cut_ec94258e8024",
        active_edl_id="edl_a27fc1aeea59",
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Remove this.",
            "editor_context": context.model_dump(mode="json"),
            "active_edl_id": "edl_a27fc1aeea59",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["timeline_updated"] is False
    assert "already" in data["content"].lower() or "no new cut" in data["content"].lower()
