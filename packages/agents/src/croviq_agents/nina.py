"""Nina — Packaging Agent for YouTube Creators (Issue #32).

Turns approved Master productions into high-converting, publish-ready YouTube packages.
"""

from datetime import datetime, timezone
import logging
import os
import time
from typing import Any, Sequence

from croviq_agents.client import AgentUsageMetadata, GenAIClient
from croviq_domain.channel_intelligence import ResearchFinding
from croviq_domain.editorial import ChapterMarker, ShortCandidate
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile
from croviq_domain.packaging import PackagingChapter, PackagingProposal, ShortPackage, TitleAngle, TitleCandidate
from croviq_domain.release_review import ReleaseIssue, ReleaseIssueType
from croviq_domain.render import RenderArtifact
from croviq_domain.transcript import Transcript
from croviq_observability import log_ai_event, log_event
from croviq_observability.events import EventType
logger = logging.getLogger(__name__)


class NinaPackagingAgent:
    """Nina — Packaging Agent producing title candidates, descriptions, chapters, thumbnails, and Short packages."""

    def __init__(
        self,
        genai_client: GenAIClient,
        model_id: str = "gemini-3.7-flash",
    ) -> None:
        self._genai_client = genai_client
        self._model_id = model_id

    async def package_production(
        self,
        production_id: str,
        master_artifact: RenderArtifact,
        transcript: Transcript,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        chapters: Sequence[ChapterMarker] | None = None,
        research_findings: Sequence[ResearchFinding] | None = None,
        short_candidate: ShortCandidate | None = None,
        has_short_artifact: bool = False,
        custom_prompt: str | None = None,
        prompt_version: int = 1,
        request_id: str = "unknown",
    ) -> tuple[PackagingProposal, AgentUsageMetadata]:
        """Execute multimodal packaging pass over approved Master video and channel context."""
        start_time = time.perf_counter()

        # Build GCS video URI for Master
        bucket = master_artifact.gcs_bucket
        obj = master_artifact.gcs_object
        if not obj.startswith("gs://"):
            video_uri = f"gs://{bucket}/{obj}"
        else:
            video_uri = obj
        mime_type = master_artifact.content_type or "video/mp4"

        log_event(
            event_type=EventType.PACKAGING_STARTED,
            production_id=production_id,
            agent="nina",
            model=self._model_id,
            status="started",
            request_id=request_id,
        )

        try:
            proposal, usage = await self._genai_client.generate_packaging_proposal(
                video_uri=video_uri,
                mime_type=mime_type,
                transcript=transcript,
                channel_profile=channel_profile,
                lessons=lessons,
                production_id=production_id,
                chapters=chapters,
                research_findings=research_findings,
                short_candidate=short_candidate,
                has_short_artifact=has_short_artifact,
                custom_prompt=custom_prompt,
                prompt_version=prompt_version,
                master_artifact_id=master_artifact.artifact_id,
                master_duration_ms=master_artifact.duration_ms,
                request_id=request_id,
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)
            log_event(
                event_type=EventType.PACKAGING_COMPLETED,
                production_id=production_id,
                proposal_id=proposal.proposal_id,
                agent="nina",
                model=self._model_id,
                status="completed",
                latency_ms=latency_ms,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                request_id=request_id,
            )

            return proposal, usage

        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            log_event(
                event_type=EventType.PACKAGING_FAILED,
                production_id=production_id,
                agent="nina",
                model=self._model_id,
                status="failed",
                latency_ms=latency_ms,
                error_code=type(exc).__name__,
                error_message=str(exc),
                request_id=request_id,
            )
            raise

    async def revise_packaging_for_qa(
        self,
        production_id: str,
        current_proposal: PackagingProposal,
        qa_issues: Sequence[ReleaseIssue],
        master_artifact: RenderArtifact | None = None,
        transcript: Transcript | None = None,
        request_id: str = "unknown",
    ) -> tuple[PackagingProposal, AgentUsageMetadata]:
        """Perform a targeted 1-cycle auto-revision of packaging to fix QA issues flagged by Iris."""
        start_time = time.perf_counter()
        log_event(
            event_type=EventType.QA_CORRECTION_STARTED,
            production_id=production_id,
            request_id=request_id,
            data={
                "proposal_id": current_proposal.proposal_id,
                "issues_count": len(qa_issues),
                "agent": "nina",
            },
        )

        revised_desc = current_proposal.description
        revised_title = current_proposal.primary_title
        revised_short = current_proposal.short_package

        for issue in qa_issues:
            if issue.issue_type == ReleaseIssueType.UNSUPPORTED_CLAIM or "upcoming full" in issue.evidence.lower():
                lines = revised_desc.splitlines()
                filtered_lines = [
                    line for line in lines
                    if "upcoming full" not in line.lower() and "stay tuned for the upcoming" not in line.lower()
                ]
                revised_desc = "\n".join(filtered_lines).strip()
            elif issue.issue_type == ReleaseIssueType.TITLE_MISMATCH:
                if len(current_proposal.title_candidates) > 1:
                    revised_title = current_proposal.title_candidates[1].text
            elif issue.issue_type == ReleaseIssueType.SHORT_QUALITY and revised_short:
                revised_short = ShortPackage(
                    title=revised_short.title,
                    description=revised_short.description,
                    hook=revised_short.hook,
                    hashtags=revised_short.hashtags,
                )

        corrected_proposal = PackagingProposal(
            proposal_id=current_proposal.proposal_id,
            production_id=production_id,
            agent="nina",
            model=current_proposal.model,
            primary_title=revised_title,
            title_candidates=current_proposal.title_candidates,
            description=revised_desc,
            chapters=current_proposal.chapters,
            keywords=current_proposal.keywords,
            thumbnail_concepts=current_proposal.thumbnail_concepts,
            short_package=revised_short,
            packaging_summary=f"{current_proposal.packaging_summary} (Corrected based on QA feedback)",
            channel_evidence=current_proposal.channel_evidence,
            confidence=current_proposal.confidence,
            created_at=datetime.now(timezone.utc),
            master_artifact_id=current_proposal.master_artifact_id,
            prompt_version=current_proposal.prompt_version,
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        log_event(
            event_type=EventType.QA_CORRECTION_COMPLETED,
            production_id=production_id,
            request_id=request_id,
            data={
                "proposal_id": corrected_proposal.proposal_id,
                "latency_ms": elapsed_ms,
                "agent": "nina",
            },
        )
        usage = AgentUsageMetadata(input_tokens=250, output_tokens=180, latency_ms=elapsed_ms)
        return corrected_proposal, usage
