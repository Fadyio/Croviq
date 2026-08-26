from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.production import SourceMedia, SourceMediaStatus
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord


def test_source_video_analysis_input_valid():
    now = datetime.now(timezone.utc)
    source_media = SourceMedia(
        upload_id="upl_123",
        original_filename="demo.mp4",
        content_type="video/mp4",
        size_bytes=10485760,
        gcs_bucket="croviq-media-raw",
        gcs_object="workspaces/ws_1/productions/prod_1/source/upl_123/demo.mp4",
        status=SourceMediaStatus.UPLOADED,
        created_at=now,
        uploaded_at=now,
    )
    media_metadata = MediaMetadata(
        duration_ms=120000,
        width=1920,
        height=1080,
        frame_rate=30.0,
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
        size_bytes=10485760,
    )
    transcript = Transcript(
        transcript_id="tr_1",
        production_id="prod_1",
        language_code="en-US",
        duration_ms=120000,
        words=[
            TranscriptWord(index=0, text="Hello", start_ms=100, end_ms=500),
        ],
        segments=[
            TranscriptSegment(
                segment_id="seg_1",
                start_ms=100,
                end_ms=500,
                text="Hello",
                word_start_index=0,
                word_end_index=0,
            )
        ],
        created_at=now,
    )

    analysis_input = SourceVideoAnalysisInput(
        production_id="prod_1",
        source_media=source_media,
        media_metadata=media_metadata,
        transcript=transcript,
        channel_id="channel_123",
        channel_memory_reference="mem_profile_456",
    )

    assert analysis_input.production_id == "prod_1"
    assert analysis_input.source_media.original_filename == "demo.mp4"
    assert analysis_input.media_metadata.duration_ms == 120000
    assert analysis_input.transcript.word_count == 1
    assert analysis_input.channel_id == "channel_123"
    assert analysis_input.channel_memory_reference == "mem_profile_456"


def test_source_video_analysis_input_mismatched_production_id():
    now = datetime.now(timezone.utc)
    source_media = SourceMedia(
        upload_id="upl_123",
        original_filename="demo.mp4",
        content_type="video/mp4",
        size_bytes=10485760,
        gcs_bucket="croviq-media-raw",
        gcs_object="workspaces/ws_1/productions/prod_1/source/upl_123/demo.mp4",
        status=SourceMediaStatus.UPLOADED,
        created_at=now,
    )
    media_metadata = MediaMetadata(
        duration_ms=120000,
        width=1920,
        height=1080,
        frame_rate=30.0,
        video_codec="h264",
        size_bytes=10485760,
    )
    transcript = Transcript(
        transcript_id="tr_1",
        production_id="prod_DIFFERENT",
        language_code="en-US",
        duration_ms=120000,
        words=[],
        segments=[],
        created_at=now,
    )

    with pytest.raises(ValidationError, match="production_id"):
        SourceVideoAnalysisInput(
            production_id="prod_1",
            source_media=source_media,
            media_metadata=media_metadata,
            transcript=transcript,
            channel_id="channel_123",
        )
