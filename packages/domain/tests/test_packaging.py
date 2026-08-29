"""Unit tests for Packaging domain models and schemas."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from croviq_domain.agent_config import AgentId
from croviq_domain.packaging import (
    PackagingChapter,
    PackagingProposal,
    PublishMetadata,
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
        packaging_summary="Practical hardware repair framing tailored to tech enthusiast audience.",
        channel_evidence="Practical demonstration framing outperforms spec sheets by 34% on this channel.",
        confidence=0.94,
        created_at=now,
    )

    assert len(proposal.title_candidates) == 2
    assert proposal.chapters[0].formatted_time == "0:00"
    assert proposal.thumbnail_concepts[0].frame_verified is True


def test_packaging_proposal_validation_errors():
    with pytest.raises(ValidationError):
        # Missing required fields
        PackagingProposal.model_validate({"production_id": "p1"})

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


def test_publish_metadata_creation():
    meta = PublishMetadata(
        title="Fairphone 6 Plus Teardown",
        description="A full teardown of the Fairphone 6 Plus.",
        privacy="private",
        thumbnail_frame_ms=15000,
    )
    assert meta.title == "Fairphone 6 Plus Teardown"
    assert meta.privacy == "private"
    assert meta.thumbnail_frame_ms == 15000


def test_agent_id_contains_supported_agents():
    assert AgentId.LEO.value == "leo"
    assert AgentId.ALEX.value == "alex"
    assert AgentId.IRIS.value == "iris"
    assert "maya" not in [a.value for a in AgentId]
