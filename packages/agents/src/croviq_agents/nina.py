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
from croviq_domain.packaging import PackagingChapter, PackagingProposal, TitleAngle, TitleCandidate
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
