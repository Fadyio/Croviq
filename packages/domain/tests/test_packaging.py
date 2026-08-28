"""Unit tests for Nina Packaging domain models and schemas."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from croviq_domain.agent_config import AgentId
from croviq_domain.packaging import (
    PackagingChapter,
    PackagingProposal,
    ShortPackage,
    ThumbnailConcept,
    TitleAngle,
    TitleCandidate,
    format_ms_as_timestamp,
    get_title_angle_label,
)


def test_title_angle_labels():
    assert get_title_angle_label(TitleAngle.DIRECT_VALUE) == "Direct Value"
    assert get_title_angle_label(TitleAngle.CURIOSITY) == "Curiosity"
    assert get_title_angle_label(TitleAngle.PROBLEM_SOLUTION) == "Problem-Solution"
    assert get_title_angle_label(TitleAngle.CONTRARIAN) == "Contrarian"
    assert get_title_angle_label(TitleAngle.HOW_TO) == "How-To"
    assert get_title_angle_label(TitleAngle.COMPARISON) == "Comparison"
    assert get_title_angle_label(TitleAngle.NEWS_RELEVANT) == "News Relevant"


def test_format_ms_as_timestamp():
    assert format_ms_as_timestamp(0) == "0:00"
    assert format_ms_as_timestamp(65000) == "1:05"
    assert format_ms_as_timestamp(3665000) == "1:01:05"


def test_packaging_proposal_validation_success():
    now = datetime.now(timezone.utc)
    proposal = PackagingProposal(
        proposal_id="pkg_test_01",
        production_id="prod_01",
        agent="nina",
        model="gemini-3.7-flash",
        primary_title="Inside the Most Repairable Modern Smartphone",
        title_candidates=[
            TitleCandidate(
                text="Inside the Most Repairable Modern Smartphone",
                angle=TitleAngle.PROBLEM_SOLUTION,
                why_it_works="Focuses on the unique modular repairability value prop.",
                confidence=0.96,
            ),
            TitleCandidate(
                text="Fairphone 6 Plus: Is This What Everyone Actually Wants?",
                angle=TitleAngle.CURIOSITY,
                why_it_works="Poses a provocative hardware question.",
                confidence=0.92,
            ),
        ],
        description="A full teardown of the Fairphone 6 Plus.",
        chapters=[
            PackagingChapter(
                title="Introduction & Unboxing",
                start_ms=0,
                end_ms=25000,
                formatted_time="0:00",
            ),
            PackagingChapter(
                title="Modular Teardown",
                start_ms=25000,
                end_ms=90000,
                formatted_time="0:25",
            ),
        ],
        keywords=["fairphone", "repairable smartphone", "tech review"],
        thumbnail_concepts=[
            ThumbnailConcept(
                concept_id="th_01",
                headline="REPLACE EVERYTHING",
                visual_subject="Close up of phone module removal with screwdriver",
                composition="Rule of thirds, centered hardware with clear tool contrast",
                emotion="Curiosity / Satisfaction",
                supporting_frame_ms=35000,
                reason="High-contrast visual evidence of modular components",
                confidence=0.95,
                frame_verified=True,
            )
        ],
        short_package=ShortPackage(
            title="You Can Actually Repair This Phone Yourself!",
            description="The Fairphone 6 Plus teardown in 45 seconds.",
            hook="Tired of glued-together phones?",
            hashtags=["#fairphone", "#tech", "#shorts"],
        ),
        packaging_summary="Practical hardware repair framing tailored to tech enthusiast audience.",
        channel_evidence="Practical demonstration framing outperforms spec sheets by 34% on this channel.",
        confidence=0.94,
        created_at=now,
    )

    assert proposal.agent == "nina"
    assert len(proposal.title_candidates) == 2
    assert proposal.chapters[0].formatted_time == "0:00"
    assert proposal.thumbnail_concepts[0].frame_verified is True
    assert proposal.short_package is not None
    assert proposal.short_package.title == "You Can Actually Repair This Phone Yourself!"


def test_packaging_proposal_validation_errors():
    with pytest.raises(ValidationError):
        # Missing required fields
        PackagingProposal.model_validate({"agent": "nina"})

    with pytest.raises(ValidationError):
        # Negative confidence
        TitleCandidate(
            text="Invalid title",
            angle=TitleAngle.HOW_TO,
            why_it_works="Testing",
            confidence=-0.5,
        )

    with pytest.raises(ValidationError):
        # Negative chapter start_ms
        PackagingChapter(
            title="Invalid chapter",
            start_ms=-100,
            end_ms=5000,
            formatted_time="0:00",
        )


def test_agent_id_contains_nina():
    assert AgentId.NINA.value == "nina"
    assert AgentId("nina") == AgentId.NINA
