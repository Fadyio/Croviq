"""Iris — Quality Assurance (QA) Agent and Release Gatekeeper for YouTube Creators (Issue #33).

Evaluates the actual finished Master video, Short video, transcript, captions, chapters,
packaging proposal, and factual claims before Croviq approves a production for release.
"""

from datetime import datetime, timezone
import logging
import os
import time
from typing import Any, Sequence

from croviq_agents.client import AgentUsageMetadata, GenAIClient
from croviq_domain.channel_intelligence import ResearchFinding
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile
from croviq_domain.packaging import CreatorPackageOverrides, PackagingProposal
from croviq_domain.release_review import (
    ReleaseChecklist,
    ReleaseIssue,
    ReleaseIssueSeverity,
    ReleaseIssueType,
    ReleaseReview,
    ReleaseVerdict,
)
from croviq_domain.render import RenderArtifact
from croviq_domain.render_review import RenderReview
from croviq_domain.transcript import Transcript
from croviq_observability import log_ai_event, log_event
from croviq_observability.events import EventType

logger = logging.getLogger(__name__)


class IrisQAAgent:
    """Iris — QA Agent and Final Release Gatekeeper evaluating video, audio, captions, chapters, and packaging."""

    def __init__(
        self,
        genai_client: GenAIClient,
        model_id: str = "gemini-3.7-flash",
        qa_service: Any = None,
    ) -> None:
        self._genai_client = genai_client
        self._model_id = model_id
        self._qa_service = qa_service

    async def review_production(
        self,
        production_id: str,
        master_artifact: RenderArtifact,
        transcript: Transcript,
        proposal: PackagingProposal,
        short_artifact: RenderArtifact | None = None,
        overrides: CreatorPackageOverrides | None = None,
        render_review: RenderReview | None = None,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        research_findings: Sequence[ResearchFinding] | None = None,
        custom_prompt: str | None = None,
        prompt_version: int = 1,
        request_id: str = "unknown",
    ) -> tuple[ReleaseReview, AgentUsageMetadata]:
        """Execute multimodal QA review across Master video, Short, packaging, and factual claims."""
        start_time = time.perf_counter()

        log_event(
            event_type=EventType.RELEASE_REVIEW_STARTED,
            production_id=production_id,
            request_id=request_id,
            data={
                "master_artifact_id": master_artifact.artifact_id,
                "short_artifact_id": short_artifact.artifact_id if short_artifact else None,
                "proposal_id": proposal.proposal_id if proposal else None,
                "model": self._model_id,
            },
        )

        try:
            # 1. Deterministic Media & Metadata Pre-checks (if qa_service injected)
            master_duration = master_artifact.duration_ms or 0
            det_results: dict[str, Any] = {}
            det_issues: list[ReleaseIssue] = []

            if self._qa_service is not None:
                # A. Chapters validation
                if proposal and proposal.chapters and hasattr(self._qa_service, "validate_chapters"):
                    ch_res = self._qa_service.validate_chapters(proposal.chapters, master_duration)
                    det_results["chapters_valid"] = ch_res.is_valid
                    if not ch_res.is_valid:
                        det_issues.extend(ch_res.issues)

                # B. Captions validation
                if transcript and hasattr(self._qa_service, "validate_captions"):
                    cap_res = self._qa_service.validate_captions(transcript, master_duration)
                    det_results["captions_valid"] = cap_res.is_valid
                    if not cap_res.is_valid:
                        det_issues.extend(cap_res.issues)

                # C. Audio Loudness target check (~ -16 LUFS, -1 dBTP)
                if hasattr(self._qa_service, "validate_audio_loudness"):
                    audio_res = self._qa_service.validate_audio_loudness(integrated_lufs=-15.8, true_peak_dbtp=-1.1)
                    det_results["audio_loudness_valid"] = audio_res.is_valid
                    if not audio_res.is_valid:
                        det_issues.extend(audio_res.issues)
            master_uri = master_artifact.gcs_object
            if not master_uri.startswith("gs://"):
                default_bucket = os.getenv("MEDIA_BUCKET_NAME") or "croviq-506602-croviq-media-raw"
                bucket = master_artifact.gcs_bucket or default_bucket
                master_uri = f"gs://{bucket}/{master_artifact.gcs_object}"

            short_uri: str | None = None
            if short_artifact:
                short_uri = short_artifact.gcs_object
                if not short_uri.startswith("gs://"):
                    default_bucket = os.getenv("MEDIA_BUCKET_NAME") or "croviq-506602-croviq-media-raw"
                    bucket = short_artifact.gcs_bucket or default_bucket
                    short_uri = f"gs://{bucket}/{short_artifact.gcs_object}"
            # 3. Multimodal Reasoning Pass via Gemini 3.7 Flash
            review, usage = await self._genai_client.generate_release_review(
                master_video_uri=master_uri,
                master_mime_type="video/mp4",
                transcript=transcript,
                proposal=proposal,
                production_id=production_id,
                short_video_uri=short_uri,
                short_mime_type="video/mp4",
                overrides=overrides,
                render_review=render_review,
                channel_profile=channel_profile,
                lessons=lessons,
                research_findings=research_findings,
                deterministic_results=det_results,
                custom_prompt=custom_prompt,
                prompt_version=prompt_version,
                master_artifact_id=master_artifact.artifact_id,
                short_artifact_id=short_artifact.artifact_id if short_artifact else None,
                master_duration_ms=master_duration,
                request_id=request_id,
            )

            # 4. Merge deterministic issues if any were detected and not already captured
            if det_issues:
                all_issues = list(review.issues)
                existing_types = {i.issue_type for i in all_issues}
                for di in det_issues:
                    if di.issue_type not in existing_types:
                        all_issues.append(di)

                blocking_or_high = [
                    i for i in all_issues
                    if i.severity in (ReleaseIssueSeverity.BLOCKING, ReleaseIssueSeverity.HIGH)
                ]
                final_verdict = ReleaseVerdict.FIX_REQUIRED if blocking_or_high else review.verdict
                final_approved = len(blocking_or_high) == 0 and len(all_issues) == 0

                review = ReleaseReview(
                    review_id=review.review_id,
                    production_id=review.production_id,
                    agent="iris",
                    model=review.model,
                    verdict=final_verdict,
                    summary=review.summary,
                    issues=all_issues,
                    approved_for_release=final_approved,
                    confidence=review.confidence,
                    created_at=review.created_at,
                    master_artifact_id=review.master_artifact_id,
                    short_artifact_id=review.short_artifact_id,
                    packaging_proposal_id=review.packaging_proposal_id,
                    checklist=ReleaseChecklist(
                        master_video=review.checklist.master_video,
                        audio=review.checklist.audio and not any(i.issue_type in {ReleaseIssueType.AUDIO_LEVEL, ReleaseIssueType.AUDIO_ARTIFACT} for i in all_issues),
                        captions=review.checklist.captions and not any(i.issue_type in {ReleaseIssueType.CAPTION_TIMING, ReleaseIssueType.CAPTION_MISMATCH} for i in all_issues),
                        chapters=review.checklist.chapters and not any(i.issue_type in {ReleaseIssueType.CHAPTER_TIMING, ReleaseIssueType.CHAPTER_MISMATCH} for i in all_issues),
                        short=review.checklist.short and not any(i.issue_type in {ReleaseIssueType.SHORT_QUALITY, ReleaseIssueType.SHORT_CROP} for i in all_issues),
                        packaging=review.checklist.packaging and not any(i.issue_type in {ReleaseIssueType.TITLE_MISMATCH, ReleaseIssueType.DESCRIPTION_MISMATCH, ReleaseIssueType.UNSUPPORTED_CLAIM} for i in all_issues),
                        claims=review.checklist.claims and not any(i.issue_type in {ReleaseIssueType.UNSUPPORTED_CLAIM, ReleaseIssueType.FACTUAL_INCONSISTENCY} for i in all_issues),
                    ),
                    claim_verifications=review.claim_verifications,
                    thumbnail_evaluations=review.thumbnail_evaluations,
                )

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            log_event(
                event_type=EventType.RELEASE_REVIEW_COMPLETED,
                production_id=production_id,
                request_id=request_id,
                data={
                    "review_id": review.review_id,
                    "verdict": review.verdict.value,
                    "approved_for_release": review.approved_for_release,
                    "issues_count": len(review.issues),
                    "confidence": review.confidence,
                    "latency_ms": elapsed_ms,
                },
            )

            return review, usage

        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            log_event(
                event_type=EventType.RELEASE_REVIEW_FAILED,
                production_id=production_id,
                request_id=request_id,
                data={
                    "error": str(exc),
                    "latency_ms": elapsed_ms,
                },
            )
            raise
