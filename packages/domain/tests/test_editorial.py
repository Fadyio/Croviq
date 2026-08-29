from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from croviq_domain.editorial import (
    AgentActivity,
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
    EditorialRun,
    EditorialRunStatus,
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
        overall_confidence=0.91,
    )
    assert proposal.production_id == "prod_test_123"
    assert len(proposal.decisions) == 1


def test_agent_activity_validation() -> None:
    activity = AgentActivity(
        activity_id="act_01",
        production_id="prod_123",
        run_id="run_456",
        agent="Leo",
        role="Video Editor",
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
