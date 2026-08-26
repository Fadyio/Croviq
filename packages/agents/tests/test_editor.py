from datetime import datetime, timezone
import pytest

from croviq_agents.client import FakeGenAIClient
from croviq_agents.editor import LeoDialogueEditor
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.production import SourceMedia, SourceMediaStatus
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord


def _sample_analysis_input() -> SourceVideoAnalysisInput:
    words = [
        TranscriptWord(index=0, text="Welcome", start_ms=0, end_ms=400),
        TranscriptWord(index=1, text="um", start_ms=410, end_ms=700),
        TranscriptWord(index=2, text="to", start_ms=710, end_ms=900),
        TranscriptWord(index=3, text="Croviq.", start_ms=910, end_ms=1300),
        TranscriptWord(index=4, text="GitHub", start_ms=1400, end_ms=1800),
        TranscriptWord(index=5, text="Actions", start_ms=1810, end_ms=2200),
        TranscriptWord(index=6, text="runs", start_ms=2210, end_ms=2500),
        TranscriptWord(index=7, text="the", start_ms=2510, end_ms=2700),
        TranscriptWord(index=8, text="workflow.", start_ms=2710, end_ms=3100),
    ]
    segments = [
        TranscriptSegment(
            segment_id="seg_001",
            start_ms=0,
            end_ms=1300,
            text="Welcome um to Croviq.",
            word_start_index=0,
            word_end_index=3,
        ),
        TranscriptSegment(
            segment_id="seg_002",
            start_ms=1400,
            end_ms=3100,
            text="GitHub Actions runs the workflow.",
            word_start_index=4,
            word_end_index=8,
        ),
    ]
    transcript = Transcript(
        transcript_id="tr_editor_test",
        production_id="prod_editor_test",
        language_code="en-US",
        duration_ms=3100,
        words=words,
        segments=segments,
        created_at=datetime.now(timezone.utc),
    )
    source_media = SourceMedia(
        upload_id="up_editor_test",
        original_filename="test.mp4",
        content_type="video/mp4",
        size_bytes=1048576,
        gcs_bucket="croviq-media-raw",
        gcs_object="workspaces/ws_01/productions/prod_editor_test/source/up_editor_test/test.mp4",
        status=SourceMediaStatus.UPLOADED,
        created_at=datetime.now(timezone.utc),
        uploaded_at=datetime.now(timezone.utc),
    )
    media_metadata = MediaMetadata(
        duration_ms=3100,
        width=1920,
        height=1080,
        frame_rate=30.0,
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
        rotation=0,
        size_bytes=1048576,
    )
    return SourceVideoAnalysisInput(
        production_id="prod_editor_test",
        source_media=source_media,
        media_metadata=media_metadata,
        transcript=transcript,
        channel_id="chan_ai_eng",
    )


@pytest.mark.asyncio
async def test_leo_dialogue_editor_generates_proposal_and_activities() -> None:
    fake_client = FakeGenAIClient()
    editor = LeoDialogueEditor(client=fake_client)
    analysis_input = _sample_analysis_input()

    proposal, usage, activities = await editor.analyze(
        analysis_input=analysis_input,
        channel_profile=None,
        lessons=None,
        run_id="run_test_01",
        request_id="req_test_01",
    )

    assert proposal.production_id == "prod_editor_test"
    assert proposal.agent == "leo"
    assert len(proposal.decisions) > 0
    assert usage.input_tokens > 0
    assert usage.output_tokens > 0

    # Verify truthful activities generated
    assert len(activities) >= 2
    summary_act = activities[0]
    assert summary_act.agent == "Leo"
    assert summary_act.role == "Dialogue Editor"
    assert summary_act.activity_type == "proposal"
    assert summary_act.production_id == "prod_editor_test"
    assert summary_act.run_id == "run_test_01"

    decision_acts = [a for a in activities if a.activity_type == "decision"]
    assert len(decision_acts) == len(proposal.decisions)
    assert all(a.related_decision_id is not None for a in decision_acts)
