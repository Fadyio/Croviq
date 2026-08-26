"""EDL assembly application service converting approved editorial decisions to deterministic EDL."""

from datetime import datetime, timezone
import logging
import time

from fastapi import HTTPException, status

from croviq_api.productions.edl_repository import EDLRepository
from croviq_api.productions.editorial_repository import EditorialRepository
from croviq_api.productions.repository import ProductionRepository
from croviq_api.productions.transcript_repository import TranscriptRepository
from croviq_domain.editorial import EditorialRunStatus
from croviq_domain.edl import EditDecisionList, derive_keep_segments
from croviq_domain.production import SourceMediaStatus
from croviq_domain.user import User
from croviq_media.cut_safety import CutSafetyAnalyzer, assemble_edl_from_review
from croviq_media.inspector import MediaInspector
from croviq_observability import (
    EventType,
    log_cut_safety_event,
    log_edl_event,
)

logger = logging.getLogger(__name__)


class EDLService:
    """Service for deterministic assembly and retrieval of Canonical Edit Decision Lists."""

    def __init__(
        self,
        production_repo: ProductionRepository,
        transcript_repo: TranscriptRepository,
        editorial_repo: EditorialRepository,
        edl_repo: EDLRepository,
        media_inspector: MediaInspector,
        cut_safety_analyzer: CutSafetyAnalyzer | None = None,
    ) -> None:
        self._production_repo = production_repo
        self._transcript_repo = transcript_repo
        self._editorial_repo = editorial_repo
        self._edl_repo = edl_repo
        self._media_inspector = media_inspector
        self._cut_safety_analyzer = cut_safety_analyzer or CutSafetyAnalyzer()

    async def assemble_edl(
        self,
        production_id: str,
        current_user: User,
        request_id: str = "unknown",
    ) -> EditDecisionList:
        """Deterministically assemble an EditDecisionList from Maya-approved editorial review."""
        start_time = time.monotonic()
        log_edl_event(
            event_type=EventType.EDL_ASSEMBLY_STARTED,
            production_id=production_id,
            status="started",
            request_id=request_id,
        )

        try:
            # 1. Verify Production & Ownership
            prod = await self._production_repo.get_production(production_id)
            if not prod:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Production '{production_id}' not found",
                )
            if prod.owner_user_id != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: You do not own this production",
                )
            # 2. Verify Source Media Status
            if prod.source_media.status != SourceMediaStatus.UPLOADED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Source media for production '{production_id}' must be uploaded before assembling EDL",
                )
            # 3. Resolve MediaMetadata
            metadata = self._media_inspector.inspect_media(prod.source_media.gcs_object)

            # 4. Fetch Transcript
            transcript = await self._transcript_repo.get_transcript_by_production_id(production_id)
            if not transcript:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Production '{production_id}' must be transcribed before assembling EDL",
                )

            # 5. Fetch Latest Completed EditorialRun
            run = await self._editorial_repo.get_latest_editorial_run(production_id)
            if not run:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No editorial run found for production '{production_id}'. Editorial analysis must be run before assembling EDL",
                )
            if run.status != EditorialRunStatus.COMPLETED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Editorial run '{run.run_id}' for production '{production_id}' is in status '{run.status}'. Must be completed before assembling EDL",
                )

            # 6. Fetch EditorProposal and DirectorReview
            proposal = None
            if run.editor_proposal_id:
                proposal = await self._editorial_repo.get_editor_proposal(production_id, run.editor_proposal_id)

            review = None
            if run.director_review_id:
                review = await self._editorial_repo.get_director_review(production_id, run.director_review_id)

            if not proposal or not review:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing editor proposal or director review for completed editorial run '{run.run_id}'",
                )

            # 7. Validate Director Approval
            if not review.approved_for_edl:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Editorial review has not been approved for EDL assembly by the Director (approved_for_edl is false)",
                )

            # 8. Idempotency Check
            existing_edl = await self._edl_repo.get_latest_edl(production_id)
            if existing_edl is not None:
                if (
                    existing_edl.editor_proposal_id == proposal.production_id
                    and existing_edl.director_review_id == review.production_id
                ):
                    latency_ms = (time.monotonic() - start_time) * 1000
                    log_edl_event(
                        event_type=EventType.EDL_ASSEMBLY_COMPLETED,
                        production_id=production_id,
                        edl_id=existing_edl.edl_id,
                        run_id=run.run_id,
                        status="cached",
                        request_id=request_id,
                        cut_count=existing_edl.active_cuts_count,
                        coverage_marker_count=len(existing_edl.coverage_markers),
                        removed_duration_ms=existing_edl.total_removed_duration_ms,
                        latency_ms=latency_ms,
                        message="Returned existing active EDL (idempotent)",
                    )
                    return existing_edl

            next_version = (existing_edl.version + 1) if existing_edl else 1

            # 9. Assemble Canonical EDL (Zero Model Calls)
            edl = assemble_edl_from_review(
                production_id=production_id,
                proposal=proposal,
                review=review,
                transcript=transcript,
                media_metadata=metadata,
                version=next_version,
                analyzer=self._cut_safety_analyzer,
            )

            # 10. Persist EDL in Firestore
            await self._edl_repo.save_edl(edl)

            # 11. Structured Logging
            for cut in edl.cuts:
                log_cut_safety_event(
                    production_id=production_id,
                    decision_id=cut.decision_id,
                    safety_status=cut.safety_status.value,
                    safety_reason=cut.safety_reason,
                    requested_start_ms=cut.requested_start_ms,
                    requested_end_ms=cut.requested_end_ms,
                    safe_start_ms=cut.safe_start_ms,
                    safe_end_ms=cut.safe_end_ms,
                    removed_duration_ms=cut.removed_duration_ms,
                    request_id=request_id,
                    confidence=cut.confidence,
                )

            latency_ms = (time.monotonic() - start_time) * 1000
            log_edl_event(
                event_type=EventType.EDL_ASSEMBLY_COMPLETED,
                production_id=production_id,
                edl_id=edl.edl_id,
                run_id=run.run_id,
                status="success",
                request_id=request_id,
                cut_count=edl.active_cuts_count,
                coverage_marker_count=len(edl.coverage_markers),
                removed_duration_ms=edl.total_removed_duration_ms,
                latency_ms=latency_ms,
            )

            return edl

        except HTTPException as exc:
            latency_ms = (time.monotonic() - start_time) * 1000
            log_edl_event(
                event_type=EventType.EDL_ASSEMBLY_FAILED,
                production_id=production_id,
                status=exc.status_code,
                request_id=request_id,
                message=exc.detail,
                latency_ms=latency_ms,
            )
            raise
        except Exception as exc:
            latency_ms = (time.monotonic() - start_time) * 1000
            log_edl_event(
                event_type=EventType.EDL_ASSEMBLY_FAILED,
                production_id=production_id,
                status="error",
                request_id=request_id,
                message=str(exc),
                exception=exc,
                latency_ms=latency_ms,
            )
            raise
    async def get_edl(
        self,
        production_id: str,
        current_user: User,
    ) -> tuple[EditDecisionList, list[tuple[int, int]]]:
        """Retrieve the active EDL and derived renderable keep segments for a production."""
        prod = await self._production_repo.get_production(production_id)
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Production '{production_id}' not found",
            )
        if prod.owner_user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not own this production",
            )
        edl = await self._edl_repo.get_latest_edl(production_id)
        if not edl:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No EDL found for production '{production_id}'",
            )

        keep_segments = derive_keep_segments(edl)
        return edl, keep_segments
