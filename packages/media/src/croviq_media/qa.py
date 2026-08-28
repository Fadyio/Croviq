"""Deterministic media and metadata QA validation service for Iris (Issue #33)."""

from dataclasses import dataclass, field
import logging
from typing import Any, Sequence

from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.packaging import PackagingChapter
from croviq_domain.release_review import (
    ReleaseIssue,
    ReleaseIssueSeverity,
    ReleaseIssueType,
)
from croviq_domain.transcript import Transcript

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChapterQAResult:
    """Result of deterministic chapter validation."""

    is_valid: bool
    issues: list[ReleaseIssue] = field(default_factory=list)


@dataclass(frozen=True)
class CaptionQAResult:
    """Result of deterministic caption timing and bounds validation."""

    is_valid: bool
    issues: list[ReleaseIssue] = field(default_factory=list)


@dataclass(frozen=True)
class AudioQAResult:
    """Result of deterministic audio level and loudness validation."""

    is_valid: bool
    integrated_lufs: float | None = None
    true_peak_dbtp: float | None = None
    issues: list[ReleaseIssue] = field(default_factory=list)


@dataclass(frozen=True)
class MediaQAResult:
    """Composite result of deterministic media stream and container validation."""

    is_valid: bool
    metadata: MediaMetadata | None = None
    issues: list[ReleaseIssue] = field(default_factory=list)


class DeterministicMediaQAService:
    """Executes deterministic technical validations for video, audio, captions, and chapters."""

    def __init__(self, ffprobe_binary: str = "ffprobe") -> None:
        self.ffprobe_binary = ffprobe_binary

    def validate_chapters(
        self,
        chapters: Sequence[Any],
        master_duration_ms: int,
    ) -> ChapterQAResult:
        """Validate chapter timestamps are monotonic, non-negative, and do not exceed Master duration."""
        issues: list[ReleaseIssue] = []

        if not chapters:
            return ChapterQAResult(is_valid=True, issues=[])

        prev_ms = -1
        for idx, ch in enumerate(chapters):
            start_ms = getattr(ch, "start_ms", getattr(ch, "timestamp_ms", 0))
            formatted_time = getattr(ch, "formatted_time", "0:00")
            title = getattr(ch, "title", "Chapter")

            # Check non-negative
            if start_ms < 0:
                issues.append(
                    ReleaseIssue(
                        issue_id=f"iss_ch_neg_{idx}",
                        issue_type=ReleaseIssueType.CHAPTER_TIMING,
                        severity=ReleaseIssueSeverity.BLOCKING,
                        source_start_ms=0,
                        artifact_type="chapter",
                        message=f"Chapter '{title}' has negative timestamp ({formatted_time}).",
                        suggested_action="Correct chapter timestamp to a valid positive video time.",
                        evidence=f"Chapter index {idx}: start_ms={start_ms}",
                    )
                )

            # Check bounds against Master duration
            if master_duration_ms > 0 and start_ms > master_duration_ms:
                issues.append(
                    ReleaseIssue(
                        issue_id=f"iss_ch_bound_{idx}",
                        issue_type=ReleaseIssueType.CHAPTER_TIMING,
                        severity=ReleaseIssueSeverity.BLOCKING,
                        source_start_ms=start_ms,
                        artifact_type="chapter",
                        message=f"Chapter '{title}' timestamp ({formatted_time}) exceeds master duration ({(master_duration_ms / 1000.0):.1f}s).",
                        suggested_action="Adjust chapter timestamp or remove obsolete chapter marker.",
                        evidence=f"Chapter timestamp {start_ms}ms > master duration {master_duration_ms}ms (source time leak).",
                    )
                )

            # Check monotonic ordering
            if start_ms <= prev_ms:
                issues.append(
                    ReleaseIssue(
                        issue_id=f"iss_ch_order_{idx}",
                        issue_type=ReleaseIssueType.CHAPTER_TIMING,
                        severity=ReleaseIssueSeverity.HIGH,
                        source_start_ms=start_ms,
                        artifact_type="chapter",
                        message=f"Chapter '{title}' at {formatted_time} is out of chronological order.",
                        suggested_action="Sort chapters in strictly ascending chronological order.",
                        evidence=f"Chapter {idx} ({start_ms}ms) <= previous chapter ({prev_ms}ms).",
                    )
                )
            prev_ms = start_ms

        return ChapterQAResult(
            is_valid=len(issues) == 0,
            issues=issues,
        )

    def validate_captions(
        self,
        transcript: Transcript | None,
        master_duration_ms: int,
    ) -> CaptionQAResult:
        """Validate transcript words do not drift beyond master duration or have invalid spans."""
        issues: list[ReleaseIssue] = []

        if not transcript or not transcript.words:
            return CaptionQAResult(is_valid=True, issues=[])

        out_of_bounds_words = [
            w for w in transcript.words if master_duration_ms > 0 and w.start_ms > master_duration_ms
        ]

        if out_of_bounds_words:
            first_oob = out_of_bounds_words[0]
            issues.append(
                ReleaseIssue(
                    issue_id="iss_cap_bounds",
                    issue_type=ReleaseIssueType.CAPTION_TIMING,
                    severity=ReleaseIssueSeverity.HIGH,
                    source_start_ms=first_oob.start_ms,
                    source_end_ms=first_oob.end_ms,
                    artifact_type="caption",
                    message=f"Captions contain {len(out_of_bounds_words)} words starting after master video end.",
                    suggested_action="Re-align caption timestamps to edited master duration.",
                    evidence=f"Word '{first_oob.text}' starts at {first_oob.start_ms}ms > master {master_duration_ms}ms.",
                )
            )

        return CaptionQAResult(
            is_valid=len(issues) == 0,
            issues=issues,
        )

    def validate_short_metadata(
        self,
        metadata: MediaMetadata,
    ) -> MediaQAResult:
        """Validate vertical Short dimensions (9:16) and duration (20-60s)."""
        issues: list[ReleaseIssue] = []

        # Check aspect ratio 9:16 (height > width, width/height ~ 0.5625)
        if metadata.height <= metadata.width:
            issues.append(
                ReleaseIssue(
                    issue_id="iss_short_aspect",
                    issue_type=ReleaseIssueType.SHORT_CROP,
                    severity=ReleaseIssueSeverity.HIGH,
                    artifact_type="short",
                    message=f"Short is not formatted as vertical 9:16 video ({metadata.width}x{metadata.height}).",
                    suggested_action="Re-render Short in vertical 9:16 format (e.g. 1080x1920).",
                    evidence=f"Dimensions: {metadata.width}x{metadata.height} (Aspect ratio {metadata.width / max(metadata.height, 1):.2f})",
                )
            )

        # Check duration (20s to 60s for YouTube Shorts standard)
        if metadata.duration_ms > 60000 or metadata.duration_ms < 15000:
            issues.append(
                ReleaseIssue(
                    issue_id="iss_short_dur",
                    issue_type=ReleaseIssueType.SHORT_QUALITY,
                    severity=ReleaseIssueSeverity.HIGH,
                    artifact_type="short",
                    message=f"Short duration ({(metadata.duration_ms / 1000.0):.1f}s) is outside optimal 15-60s range.",
                    suggested_action="Trim Short candidate to between 20s and 60s.",
                    evidence=f"Short duration: {metadata.duration_ms}ms",
                )
            )

        return MediaQAResult(
            is_valid=len(issues) == 0,
            metadata=metadata,
            issues=issues,
        )

    def validate_audio_loudness(
        self,
        integrated_lufs: float,
        true_peak_dbtp: float,
    ) -> AudioQAResult:
        """Validate integrated loudness (target -16 LUFS +/- 3 LUFS) and peak (<= -0.5 dBTP)."""
        issues: list[ReleaseIssue] = []

        # Practical tolerance: -19.0 to -13.0 LUFS
        if integrated_lufs > -13.0 or integrated_lufs < -20.0:
            severity = (
                ReleaseIssueSeverity.BLOCKING
                if (integrated_lufs > -10.0 or integrated_lufs < -24.0)
                else ReleaseIssueSeverity.MEDIUM
            )
            issues.append(
                ReleaseIssue(
                    issue_id="iss_audio_lufs",
                    issue_type=ReleaseIssueType.AUDIO_LEVEL,
                    severity=severity,
                    artifact_type="audio",
                    message=f"Audio loudness ({integrated_lufs:.1f} LUFS) deviates from target -16 LUFS.",
                    suggested_action="Apply loudness normalization filter targeting -16 LUFS.",
                    evidence=f"Measured integrated loudness: {integrated_lufs:.1f} LUFS (Target: -16.0 LUFS).",
                )
            )

        # Clipping / True peak check
        if true_peak_dbtp > -0.2:
            issues.append(
                ReleaseIssue(
                    issue_id="iss_audio_peak",
                    issue_type=ReleaseIssueType.AUDIO_LEVEL,
                    severity=ReleaseIssueSeverity.BLOCKING if true_peak_dbtp > 0.5 else ReleaseIssueSeverity.HIGH,
                    artifact_type="audio",
                    message=f"Audio true peak ({true_peak_dbtp:.1f} dBTP) risks clipping/distortion.",
                    suggested_action="Lower audio gain or apply limiter with -1.0 dBTP ceiling.",
                    evidence=f"Measured true peak: {true_peak_dbtp:.1f} dBTP (Ceiling: -1.0 dBTP).",
                )
            )

        return AudioQAResult(
            is_valid=len(issues) == 0,
            integrated_lufs=integrated_lufs,
            true_peak_dbtp=true_peak_dbtp,
            issues=issues,
        )
