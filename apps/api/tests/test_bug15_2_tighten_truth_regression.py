"""Regression tests for BUG 15.2 — FIX NO-OP / FALSE-SUCCESS 'MAKE THIS TIGHTER'.

Covers all 12 regression test cases (A through L):
A. fully subsumed proposed cut => effective_removed_ms = 0
B. partially overlapping proposed cut => only newly uncovered interval counted
C. disjoint proposed cut => entire duration counted
D. multiple overlapping proposed cuts => interval union counted once
E. no-op tighten leaves EDL ID/version unchanged
F. no-op tighten leaves cut count unchanged
G. no-op tighten does not invoke render
H. no-op tighten does not stale derivatives
I. no-op tighten does not add undo revision
J. real tighten reports exact before-after duration delta
K. repeated tighten converges to no-op
L. user-facing response never says 'Tightened ... by 0.00s'
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pytest
from starlette.testclient import TestClient

from croviq_agents.client import FakeGenAIClient
from croviq_api.auth.dependencies import get_current_user
from croviq_api.main import create_app
from croviq_api.media.dependencies import set_media_inspector, set_media_storage
from croviq_api.media.fake import FakeMediaStorage
from croviq_api.memory.dependencies import set_memory_store
from croviq_api.memory.fake import FakeChannelMemoryStore
from croviq_api.productions.broll_repository import InMemoryBRollRepository, get_broll_repository
from croviq_api.productions.dependencies import set_genai_client, set_render_service
from croviq_api.productions.edl_repository import InMemoryEDLRepository, set_edl_repository
from croviq_api.productions.editorial_repository import InMemoryEditorialRepository, set_editorial_repository
from croviq_api.productions.render_repository import InMemoryRenderRepository, set_render_repository
from croviq_api.productions.repository import InMemoryProductionRepository, set_production_repository
from croviq_api.productions.transcript_repository import InMemoryTranscriptRepository, set_transcript_repository
from croviq_api.workspaces.agent_config_repository import InMemoryAgentConfigRepository, get_agent_config_repository
from croviq_api.workspaces.repository import InMemoryWorkspaceRepository, set_workspace_repository
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
    audit_proposed_cuts,
    classify_cut_overlap,
    compute_interval_union,
    compute_intervals_duration,
)
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.production import Production, SourceMedia, SourceMediaStatus
from croviq_domain.render import ArtifactStatus, ArtifactType, RenderArtifact
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_domain.user import User
from croviq_media.inspector import MediaInspector
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
        user_id="user_bug15_2",
        email="creator@example.com",
        display_name="Bug 15.2 Creator",
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
    broll_repo = InMemoryBRollRepository()
    agent_config_repo = InMemoryAgentConfigRepository()

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
        # 5900ms pause from 16800 to 22700
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
            TranscriptSegment(
                segment_id="seg_04",
                start_ms=16200,
                end_ms=28600,
                text="To edit to edit your workflow like this workflow is for Cloudflare DNS.",
                word_start_index=15,
                word_end_index=27,
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
                source_end_ms=22700,
                original_text="To edit",
                action="remove",
                concise_reason="False start and 5.9s silence.",
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

    # Initial EDL already covers 16200-22700
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
                requested_end_ms=22700,
                safe_start_ms=16200,
                safe_end_ms=22700,
                removed_duration_ms=6500,
                left_anchor="here.",
                right_anchor="to",
                transition_ms=20,
                safety_status=CutSafetyStatus.SAFE,
                safety_reason="False start and 5.9s silence.",
                confidence=0.95,
            ),
        ],
        created_at=now,
    )
    edl_repo._by_id[(production_id, initial_edl.edl_id)] = initial_edl
    edl_repo._by_production[production_id] = [initial_edl.edl_id]

    # Baseline preview render artifact
    baseline_artifact = RenderArtifact(
        artifact_id="art_preview_baseline",
        production_id=production_id,
        edl_id=initial_edl.edl_id,
        artifact_type=ArtifactType.PREVIEW,
        status=ArtifactStatus.completed,
        gcs_bucket="test-bucket",
        gcs_object="renders/edl_a27fc1aeea59/preview.mp4",
        content_type="video/mp4",
        size_bytes=5635437,
        duration_ms=initial_edl.estimated_target_duration_ms,
        created_at=now,
        completed_at=now,
    )
    render_repo._by_production[production_id] = {baseline_artifact.artifact_id: baseline_artifact}

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_broll_repository] = lambda: broll_repo
    app.dependency_overrides[get_agent_config_repository] = lambda: agent_config_repo
    client = TestClient(app)

    return {
        "client": client,
        "production_id": production_id,
        "edl_repo": edl_repo,
        "editorial_repo": editorial_repo,
        "render_repo": render_repo,
        "render_service": render_service,
        "initial_edl": initial_edl,
        "current_user": current_user,
    }


def test_test_a_fully_subsumed_proposed_cut() -> None:
    """Test A: fully subsumed proposed cut => effective_removed_ms = 0."""
    existing = [(17000, 22500)]
    proposed = (18000, 21000)
    classification, newly_eff, overlap = classify_cut_overlap(proposed, existing)
    assert classification == "FULLY_SUBSUMED"
    assert newly_eff == 0
    assert overlap == 3000

    audit = audit_proposed_cuts([proposed], existing)
    assert audit["effective_removed_ms"] == 0
    assert audit["already_removed_ms"] == 3000
    assert audit["has_effective_change"] is False


def test_test_b_partially_overlapping_proposed_cut() -> None:
    """Test B: partially overlapping proposed cut => only newly uncovered interval counted."""
    existing = [(17000, 20000)]
    proposed = (19000, 22000)
    classification, newly_eff, overlap = classify_cut_overlap(proposed, existing)
    assert classification == "PARTIALLY_OVERLAPPING"
    assert newly_eff == 2000
    assert overlap == 1000

    audit = audit_proposed_cuts([proposed], existing)
    assert audit["effective_removed_ms"] == 2000
    assert audit["already_removed_ms"] == 1000
    assert audit["has_effective_change"] is True


def test_test_c_disjoint_proposed_cut() -> None:
    """Test C: disjoint proposed cut => entire duration counted."""
    existing = [(17000, 20000)]
    proposed = (25000, 28000)
    classification, newly_eff, overlap = classify_cut_overlap(proposed, existing)
    assert classification == "NEW"
    assert newly_eff == 3000
    assert overlap == 0

    audit = audit_proposed_cuts([proposed], existing)
    assert audit["effective_removed_ms"] == 3000
    assert audit["has_effective_change"] is True


def test_test_d_multiple_overlapping_proposed_cuts() -> None:
    """Test D: multiple overlapping proposed cuts => interval union counted once."""
    existing = [(10000, 15000)]
    proposed = [(14000, 18000), (17000, 21000)]
    audit = audit_proposed_cuts(proposed, existing)
    assert audit["effective_removed_ms"] == 6000
    assert audit["has_effective_change"] is True


def test_test_e_no_op_tighten_leaves_edl_id_and_version_unchanged(test_stack: dict[str, Any]) -> None:
    """Test E: no-op tighten leaves EDL ID and version unchanged."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]
    initial_edl: EditDecisionList = test_stack["initial_edl"]

    # Select range 16200-28600 which is already cut (16200-22700 covers the pause)
    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=16200,
        source_end_ms=28600,
        active_edl_id=initial_edl.edl_id,
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Make this tighter.",
            "editor_context": context.model_dump(mode="json"),
            "current_playhead_ms": 16200,
            "active_edl_id": initial_edl.edl_id,
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["timeline_updated"] is False
    assert data["edl"]["edl_id"] == initial_edl.edl_id
    assert data["edl"]["version"] == initial_edl.version


def test_test_f_no_op_tighten_leaves_cut_count_unchanged(test_stack: dict[str, Any]) -> None:
    """Test F: no-op tighten leaves cut count unchanged."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]
    initial_edl: EditDecisionList = test_stack["initial_edl"]

    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=16200,
        source_end_ms=28600,
        active_edl_id=initial_edl.edl_id,
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Make this tighter.",
            "editor_context": context.model_dump(mode="json"),
            "current_playhead_ms": 16200,
            "active_edl_id": initial_edl.edl_id,
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["edl"]["cuts"]) == len(initial_edl.cuts)
    assert len(data["edl"]["cuts"]) == 2


def test_test_g_no_op_tighten_does_not_invoke_render(test_stack: dict[str, Any]) -> None:
    """Test G: no-op tighten does not invoke render."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]
    render_repo: InMemoryRenderRepository = test_stack["render_repo"]
    render_service: FakeRenderService = test_stack["render_service"]
    initial_edl: EditDecisionList = test_stack["initial_edl"]
    artifacts_before = len(render_repo._by_production.get(prod_id, {}))
    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=16200,
        source_end_ms=28600,
        active_edl_id=initial_edl.edl_id,
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Make this tighter.",
            "editor_context": context.model_dump(mode="json"),
            "current_playhead_ms": 16200,
            "active_edl_id": initial_edl.edl_id,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    tool_names = [t.get("tool_name") for t in data.get("tool_executions", [])]
    assert "rerender_preview" not in tool_names
    artifacts_after = len(render_repo._by_production.get(prod_id, {}))
    assert artifacts_after == artifacts_before

def test_test_h_no_op_tighten_does_not_stale_derivatives(test_stack: dict[str, Any]) -> None:
    """Test H: no-op tighten does not stale derivatives (artifacts count and status unchanged)."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]
    render_repo: InMemoryRenderRepository = test_stack["render_repo"]
    initial_edl: EditDecisionList = test_stack["initial_edl"]

    artifacts_before = list(render_repo._by_production.get(prod_id, {}).values())

    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=16200,
        source_end_ms=28600,
        active_edl_id=initial_edl.edl_id,
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Make this tighter.",
            "editor_context": context.model_dump(mode="json"),
            "current_playhead_ms": 16200,
            "active_edl_id": initial_edl.edl_id,
        },
    )
    assert resp.status_code == 200
    artifacts_after = list(render_repo._by_production.get(prod_id, {}).values())
    assert len(artifacts_after) == len(artifacts_before)
    assert artifacts_after[0].artifact_id == artifacts_before[0].artifact_id


def test_test_i_no_op_tighten_does_not_add_undo_revision(test_stack: dict[str, Any]) -> None:
    """Test I: no-op tighten does not add undo revision."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]
    edl_repo: InMemoryEDLRepository = test_stack["edl_repo"]
    initial_edl: EditDecisionList = test_stack["initial_edl"]

    revisions_before = len(edl_repo._history.get(prod_id, []))

    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=16200,
        source_end_ms=28600,
        active_edl_id=initial_edl.edl_id,
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Make this tighter.",
            "editor_context": context.model_dump(mode="json"),
            "current_playhead_ms": 16200,
            "active_edl_id": initial_edl.edl_id,
        },
    )
    assert resp.status_code == 200

    revisions_after = len(edl_repo._history.get(prod_id, []))
    assert revisions_after == revisions_before


def test_test_j_real_tighten_reports_exact_duration_delta(test_stack: dict[str, Any]) -> None:
    """Test J: real tighten reports exact before-after duration delta."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]
    edl_repo: InMemoryEDLRepository = test_stack["edl_repo"]

    # Build an EDL where the 5900ms pause (16800-22700) is NOT cut yet (cut 2 only removes 16200-16800)
    now = datetime.now(timezone.utc)
    edl_uncut_pause = EditDecisionList(
        edl_id="edl_uncut_pause",
        production_id=prod_id,
        source_duration_ms=101440,
        editor_proposal_id="prop_c1aeea59",
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
    edl_repo._by_id[(prod_id, edl_uncut_pause.edl_id)] = edl_uncut_pause
    edl_repo._by_production[prod_id] = [edl_uncut_pause.edl_id]

    before_dur = edl_uncut_pause.estimated_target_duration_ms

    context = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=16200,
        source_end_ms=28600,
        active_edl_id=edl_uncut_pause.edl_id,
    )

    resp = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Make this tighter.",
            "editor_context": context.model_dump(mode="json"),
            "current_playhead_ms": 16200,
            "active_edl_id": edl_uncut_pause.edl_id,
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["timeline_updated"] is True
    new_edl = EditDecisionList.model_validate(data["edl"])
    after_dur = new_edl.estimated_target_duration_ms
    delta_s = (before_dur - after_dur) / 1000.0
    assert delta_s > 0

    expected_delta_str = f"{delta_s:.2f}s"
    assert expected_delta_str in data["content"]


def test_test_k_repeated_tighten_converges_to_no_op(test_stack: dict[str, Any]) -> None:
    """Test K: repeated tighten converges to no-op."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]
    edl_repo: InMemoryEDLRepository = test_stack["edl_repo"]

    # First request: already tight -> no-op
    context1 = EditorSelectionContext(
        production_id=prod_id,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=16200,
        source_end_ms=28600,
        active_edl_id="edl_a27fc1aeea59",
    )
    resp1 = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Make this tighter.",
            "editor_context": context1.model_dump(mode="json"),
            "current_playhead_ms": 16200,
            "active_edl_id": "edl_a27fc1aeea59",
        },
    )
    assert resp1.status_code == 200
    assert resp1.json()["timeline_updated"] is False

    # Second repeated request -> still no-op
    resp2 = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Make this tighter.",
            "editor_context": context1.model_dump(mode="json"),
            "current_playhead_ms": 16200,
            "active_edl_id": "edl_a27fc1aeea59",
        },
    )
    assert resp2.status_code == 200
    assert resp2.json()["timeline_updated"] is False

    # Third repeated request -> still no-op
    resp3 = client.post(
        f"/api/productions/{prod_id}/chat",
        json={
            "message": "Make this tighter.",
            "editor_context": context1.model_dump(mode="json"),
            "current_playhead_ms": 16200,
            "active_edl_id": "edl_a27fc1aeea59",
        },
    )
    assert len(edl_repo._history.get(prod_id, [])) == 0


def test_test_l_user_facing_response_never_says_tightened_by_zero(test_stack: dict[str, Any]) -> None:
    """Test L: user-facing response never says 'Tightened ... by 0.00s'."""
    client: TestClient = test_stack["client"]
    prod_id: str = test_stack["production_id"]

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
    assert resp.status_code == 200
    content = resp.json()["content"]

    assert "0.00s" not in content
    assert "tightened this section by 0.00" not in content.lower()
    assert "already" in content.lower() or "no long pauses" in content.lower()
