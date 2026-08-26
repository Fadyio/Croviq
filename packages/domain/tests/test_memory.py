from datetime import datetime, timezone
import pytest
from croviq_domain.channel_provider import SampleChannelDataProvider
from croviq_domain.memory import (
    ChannelLesson,
    ChannelMemoryProfile,
    ChannelProfileBuilder,
    TargetAgent,
)


@pytest.fixture
def sample_provider() -> SampleChannelDataProvider:
    return SampleChannelDataProvider()


@pytest.fixture
def sample_channel(sample_provider: SampleChannelDataProvider):
    return sample_provider.fixture.channel


class TestChannelMemoryProfileSchema:
    def test_profile_creation_and_fields(self) -> None:
        now = datetime.now(timezone.utc)
        profile = ChannelMemoryProfile(
            channel_id="croviq_syn_ai_eng_01",
            channel_name="AI Engineering & Agent Systems",
            primary_topics=["AI Agents", "LLM Systems"],
            content_pillars=["Agent Architecture", "Production Deployment"],
            language="en",
            audience_geographies=["US", "IN", "GB"],
            audience_characteristics=["AI Engineers", "DevOps Practitioners"],
            historical_baselines={"mean_views": 18450.0, "avg_ctr_percentage": 7.4},
            high_performing_formats=["agent_build", "deep_dive"],
            weak_formats=["tutorial"],
            recurring_retention_patterns=["Early demo <=30s improves retention."],
            packaging_patterns=["Outcome-focused titles yield higher CTR."],
            editorial_directives=["Demonstrate code within 30s."],
            updated_at=now,
        )

        assert profile.channel_id == "croviq_syn_ai_eng_01"
        assert profile.channel_name == "AI Engineering & Agent Systems"
        assert len(profile.primary_topics) == 2
        assert profile.historical_baselines["mean_views"] == 18450.0
        assert profile.updated_at.tzinfo is not None

    def test_profile_serialization_roundtrip(self) -> None:
        profile = ChannelMemoryProfile(
            channel_id="test_chan_01",
            channel_name="Test Channel",
            primary_topics=["Topic A"],
            content_pillars=["Pillar A"],
            language="en",
            audience_geographies=["US"],
            audience_characteristics=["Engineers"],
            historical_baselines={"mean_views": 1000.0},
            high_performing_formats=["deep_dive"],
            weak_formats=["tutorial"],
            recurring_retention_patterns=["Pattern A"],
            packaging_patterns=["Pattern B"],
            editorial_directives=["Directive A"],
        )

        data = profile.model_dump(mode="json")
        deserialized = ChannelMemoryProfile.model_validate(data)

        assert deserialized.channel_id == profile.channel_id
        assert deserialized.historical_baselines == profile.historical_baselines
        assert deserialized.high_performing_formats == ["deep_dive"]

    def test_timezone_validation_rejects_naive(self) -> None:
        naive_dt = datetime(2026, 8, 26, 12, 0, 0)
        with pytest.raises(ValueError, match="timezone-aware"):
            ChannelMemoryProfile(
                channel_id="test_chan",
                channel_name="Test",
                updated_at=naive_dt,
            )


class TestChannelLessonSchema:
    def test_lesson_creation(self) -> None:
        now = datetime.now(timezone.utc)
        lesson = ChannelLesson(
            lesson_id="lsn_01",
            channel_id="croviq_syn_ai_eng_01",
            directive="Show terminal demo within 30 seconds.",
            target_agent=TargetAgent.DIRECTOR,
            evidence_summary="Early demo videos average 58.4% retention vs 44.1% late demos.",
            confidence=0.92,
            status="active",
            created_at=now,
        )

        assert lesson.lesson_id == "lsn_01"
        assert lesson.target_agent == TargetAgent.DIRECTOR
        assert lesson.confidence == 0.92

    def test_lesson_confidence_bounds(self) -> None:
        with pytest.raises(ValueError):
            ChannelLesson(
                lesson_id="lsn_bad",
                channel_id="c_01",
                directive="Test",
                target_agent=TargetAgent.EDITOR,
                evidence_summary="Summary",
                confidence=1.5,
            )


class TestChannelProfileBuilder:
    def test_deterministic_profile_derivation(self, sample_channel) -> None:
        profile1 = ChannelProfileBuilder.build_profile(sample_channel)
        profile2 = ChannelProfileBuilder.build_profile(sample_channel)

        assert profile1.channel_id == "croviq_syn_ai_eng_01"
        assert profile1.channel_name == sample_channel.public.title
        assert profile1.language == "en"

        # Deterministic content matches
        assert profile1.primary_topics == profile2.primary_topics
        assert profile1.content_pillars == profile2.content_pillars
        assert profile1.audience_geographies == profile2.audience_geographies
        assert profile1.historical_baselines == profile2.historical_baselines
        assert profile1.high_performing_formats == profile2.high_performing_formats
        assert profile1.weak_formats == profile2.weak_formats
        assert profile1.recurring_retention_patterns == profile2.recurring_retention_patterns
        assert profile1.editorial_directives == profile2.editorial_directives

    def test_baselines_match_channel_analytics(self, sample_channel) -> None:
        profile = ChannelProfileBuilder.build_profile(sample_channel)
        baselines = profile.historical_baselines

        assert baselines["total_views"] == float(sample_channel.analytics.total_views)
        assert baselines["avg_ctr_percentage"] == round(float(sample_channel.analytics.avg_ctr_percentage), 2)
        assert baselines["total_published_videos"] == float(sample_channel.public.video_count)

    def test_format_derivations(self, sample_channel) -> None:
        profile = ChannelProfileBuilder.build_profile(sample_channel)

        assert "agent_build" in profile.high_performing_formats or "deep_dive" in profile.high_performing_formats
        assert "tutorial" in profile.weak_formats or len(profile.weak_formats) > 0

    def test_retention_and_editorial_directives_supported_by_evidence(self, sample_channel) -> None:
        profile = ChannelProfileBuilder.build_profile(sample_channel)

        # Directives contain early demo guidance
        assert any("00:30" in d for d in profile.editorial_directives)
        # Retention patterns capture early demo correlation
        assert any("Earlier practical demonstrations" in p for p in profile.recurring_retention_patterns)

    def test_build_lessons(self, sample_channel) -> None:
        lessons = ChannelProfileBuilder.build_lessons(sample_channel)

        assert len(lessons) >= 4
        target_agents = {l.target_agent for l in lessons}
        assert TargetAgent.DIRECTOR in target_agents
        assert TargetAgent.EDITOR in target_agents
        assert TargetAgent.PACKAGING in target_agents
        assert TargetAgent.QA in target_agents

        director_lesson = next(l for l in lessons if l.target_agent == TargetAgent.DIRECTOR)
        assert "30 seconds" in director_lesson.directive
        assert director_lesson.confidence >= 0.8
        assert director_lesson.channel_id == sample_channel.channel_id
