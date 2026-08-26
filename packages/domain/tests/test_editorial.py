from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from croviq_domain.editorial import (
    AgentActivity,
    DirectorDecision,
    DirectorReview,
    DirectorVerdict,
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
    EditorialRun,
    EditorialRunStatus,
    ShortCandidate,
)


def test_editor_decision_valid() -> None:
    decision = EditorDecision(
        decision_id="dec_01",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=5,
        transcript_end_word=7,
        source_start_ms=1500,
        source_end_ms=2100,
        original_text="um you know",
        action="remove",
        concise_reason="Remove filler hesitation",
        confidence=0.95,
        visual_context="talking head",
    )
    assert decision.decision_id == "dec_01"
    assert decision.decision_type == EditorDecisionType.REMOVE_FILLER
    assert decision.transcript_start_word == 5
    assert decision.transcript_end_word == 7
    assert decision.source_start_ms == 1500
    assert decision.source_end_ms == 2100


def test_editor_decision_rejects_inverted_indexes() -> None:
    with pytest.raises(ValidationError, match="transcript_end_word"):
        EditorDecision(
            decision_id="dec_01",
            decision_type=EditorDecisionType.REMOVE_FILLER,
            transcript_start_word=10,
            transcript_end_word=5,
            source_start_ms=1500,
            source_end_ms=2100,
            original_text="um",
            action="remove",
            concise_reason="Invalid indexes",
            confidence=0.9,
        )


def test_editor_decision_rejects_inverted_times() -> None:
    with pytest.raises(ValidationError, match="source_end_ms"):
        EditorDecision(
            decision_id="dec_01",
            decision_type=EditorDecisionType.REMOVE_FILLER,
            transcript_start_word=5,
            transcript_end_word=7,
            source_start_ms=2500,
            source_end_ms=2100,
            original_text="um",
            action="remove",
            concise_reason="Invalid times",
            confidence=0.9,
        )


def test_short_candidate_valid() -> None:
    candidate = ShortCandidate(
        start_ms=10000,
        end_ms=45000,
        transcript_start_word=25,
        transcript_end_word=120,
        hook_title="Amazing Trick with GitHub Actions",
        concise_reason="High energy demonstration and punchy delivery",
        confidence=0.88,
    )
    assert candidate.start_ms == 10000
    assert candidate.end_ms == 45000


def test_short_candidate_rejects_invalid_bounds() -> None:
    with pytest.raises(ValidationError, match="end_ms"):
        ShortCandidate(
            start_ms=45000,
            end_ms=10000,
            transcript_start_word=25,
            transcript_end_word=120,
            hook_title="Invalid",
            concise_reason="Invalid bounds",
            confidence=0.88,
        )


def test_editor_proposal_valid() -> None:
    proposal = EditorProposal(
        production_id="prod_test_123",
        agent="leo",
        model="gemini-3.7-flash",
        summary="Found 3 filler word cuts and 1 false start",
        decisions=[
            EditorDecision(
                decision_id="dec_01",
                decision_type=EditorDecisionType.REMOVE_FILLER,
                transcript_start_word=5,
                transcript_end_word=6,
                source_start_ms=1000,
                source_end_ms=1500,
                original_text="um",
                action="remove",
                concise_reason="Remove filler",
                confidence=0.9,
            )
        ],
        short_candidate=ShortCandidate(
            start_ms=5000,
            end_ms=30000,
            transcript_start_word=15,
            transcript_end_word=80,
            hook_title="Quick Tip",
            concise_reason="Concise practical takeaway",
            confidence=0.92,
        ),
        overall_confidence=0.91,
    )
    assert proposal.production_id == "prod_test_123"
    assert len(proposal.decisions) == 1
    assert proposal.short_candidate is not None


def test_director_decision_verdicts() -> None:
    approve = DirectorDecision(
        editor_decision_id="dec_01",
        verdict=DirectorVerdict.APPROVE,
        concise_reason="Clean cut with no loss of meaning",
    )
    assert approve.verdict == DirectorVerdict.APPROVE

    reject = DirectorDecision(
        editor_decision_id="dec_02",
        verdict=DirectorVerdict.REJECT,
        concise_reason="Keep this sentence because it explains the security boundary",
    )
    assert reject.verdict == DirectorVerdict.REJECT

    modify = DirectorDecision(
        editor_decision_id="dec_03",
        verdict=DirectorVerdict.MODIFY,
        concise_reason="Tighten boundary to avoid clipping the opening consonant",
        modified_action="remove",
        modified_transcript_start_word=12,
        modified_transcript_end_word=14,
        modified_source_start_ms=3200,
        modified_source_end_ms=3800,
    )
    assert modify.verdict == DirectorVerdict.MODIFY
    assert modify.modified_transcript_start_word == 12


def test_director_review_valid() -> None:
    review = DirectorReview(
        production_id="prod_test_123",
        agent="maya",
        model="gemini-3.7-flash",
        overall_assessment="Strong dialogue pass, approved with 1 preservation note",
        decisions=[
            DirectorDecision(
                editor_decision_id="dec_01",
                verdict=DirectorVerdict.APPROVE,
                concise_reason="Approved",
            )
        ],
        editor_feedback="Proceed to EDL assembly",
        approved_for_edl=True,
        confidence=0.94,
    )
    assert review.approved_for_edl is True
    assert review.agent == "maya"


def test_agent_activity_validation() -> None:
    activity = AgentActivity(
        activity_id="act_01",
        production_id="prod_123",
        run_id="run_456",
        agent="Leo",
        role="Dialogue Editor",
        activity_type="proposal",
        message="Found a repeated explanation around 00:42.",
        related_decision_id="dec_01",
        created_at=datetime.now(timezone.utc),
    )
    assert activity.agent == "Leo"
    assert activity.related_decision_id == "dec_01"


def test_editorial_run_lifecycle() -> None:
    run = EditorialRun(
        run_id="run_abc123",
        production_id="prod_123",
        status=EditorialRunStatus.ANALYZING,
        started_at=datetime.now(timezone.utc),
    )
    assert run.status == EditorialRunStatus.ANALYZING
    assert run.completed_at is None
