import asyncio
from datetime import date, timezone
import json
from pathlib import Path
import sys
import pytest
from croviq_domain.channel import (
    CANONICAL_SAMPLE_CHANNEL_ID,
    Channel,
    ContentPillar,
    SampleChannelFixture,
    TitleStyle,
    VideoFormat,
    is_sample_channel,
)
from croviq_domain.channel_provider import (
    ChannelDataProvider,
    SampleChannelDataProvider,
)


@pytest.fixture
def sample_provider() -> SampleChannelDataProvider:
    return SampleChannelDataProvider()


@pytest.fixture
def channel_fixture(sample_provider: SampleChannelDataProvider) -> SampleChannelFixture:
    return sample_provider.fixture


@pytest.fixture
def channel(channel_fixture: SampleChannelFixture) -> Channel:
    return channel_fixture.channel


class TestSampleChannelFixture:
    def test_fixture_metadata_and_counts(
        self, channel_fixture: SampleChannelFixture, channel: Channel
    ) -> None:
        """Verify fixture headers, video counts, and subscriber targets."""
        assert channel_fixture.fixture_version == "1.0.0"
        assert channel_fixture.schema_version == "1.0.0"
        assert channel_fixture.source_type == "synthetic"
        assert channel_fixture.seed == 42
        assert channel_fixture.video_count == 100
        assert len(channel.videos) == 100

        # Channel scale target: ~50,000 subscribers
        assert 45_000 <= channel.public.subscriber_count <= 55_000
        assert (
            channel.analytics.current_subscribers == channel.public.subscriber_count
        )
        assert channel.public.video_count == 100
        assert channel.analytics.total_views > 1_000_000
        assert channel.analytics.total_watch_time_hours > 10_000

    def test_unique_video_identifiers(self, channel: Channel) -> None:
        """Verify all video IDs and titles are unique and non-empty."""
        video_ids = [v.video_id for v in channel.videos]
        assert len(video_ids) == len(set(video_ids))
        assert all(vid.startswith("vid_syn_") for vid in video_ids)

    def test_date_chronology_and_history_span(self, channel: Channel) -> None:
        """Verify publication dates span approximately 18 months (~500 to ~560 days) in chronological order."""
        dates = [v.public.published_at for v in channel.videos]

        # Chronologically strictly ascending
        for i in range(len(dates) - 1):
            assert dates[i] < dates[i + 1]
            assert dates[i].tzinfo == timezone.utc

        history_span = dates[-1] - dates[0]
        # ~18 months (~500 - 560 days)
        assert 480 <= history_span.days <= 570

    def test_metrics_internal_consistency(self, channel: Channel) -> None:
        """Verify mathematical coherence of per-video metrics."""
        for v in channel.videos:
            dur = v.public.duration_seconds
            views = v.analytics.views
            avg_dur = v.analytics.avg_view_duration_seconds
            avg_pct = v.analytics.avg_view_percentage
            watch_mins = v.analytics.watch_time_minutes
            impressions = v.analytics.impressions
            ctr = v.analytics.ctr_percentage

            # Duration validity
            assert 300 <= dur <= 1800
            assert views > 0
            assert impressions > views
            assert 2.0 <= ctr <= 15.0

            # View duration must be <= total duration
            assert avg_dur <= dur
            assert 15.0 <= avg_pct <= 85.0

            # Average view percentage matches avg_view_duration / duration * 100 within 0.1%
            expected_avg_pct = round((avg_dur / dur) * 100.0, 2)
            assert abs(avg_pct - expected_avg_pct) <= 0.1

            # Watch time formula: (views * avg_view_duration_seconds) / 60.0 within 1 minute tolerance
            expected_watch_mins = (views * avg_dur) / 60.0
            assert abs(watch_mins - expected_watch_mins) <= 1.0

            # Public and private view counts match
            assert v.public.view_count == views
            assert v.public.like_count == v.analytics.likes
            assert v.public.comment_count == v.analytics.comments

    def test_retention_curves_validity(self, channel: Channel) -> None:
        """Verify retention curve structure, bounds, and average alignment."""
        for v in channel.videos:
            curve = v.analytics.retention_curve
            assert len(curve) == 101  # 0% through 100%

            # Offsets are 0 to 100 sequentially
            assert [p.percent_offset for p in curve] == list(range(101))

            # Point 0 is 100%
            assert curve[0].retention_percentage == 100.0

            # All points between 5% and 100%
            for p in curve:
                assert 5.0 <= p.retention_percentage <= 100.0
                assert p.relative_retention is not None
                assert p.relative_retention >= 0.1

            # Numerical average of retention curve matches avg_view_percentage
            curve_mean = sum(p.retention_percentage for p in curve) / len(curve)
            assert abs(v.analytics.avg_view_percentage - curve_mean) <= 0.05

    def test_distribution_sums(self, channel: Channel) -> None:
        """Verify traffic sources, geographies, and device distributions sum to ~100%."""
        for v in channel.videos:
            traffic_sum = sum(t.percentage for t in v.analytics.traffic_sources)
            assert 99.0 <= traffic_sum <= 101.0

            geo_sum = sum(g.percentage for g in v.analytics.geography)
            assert 99.0 <= geo_sum <= 101.0

            device_sum = sum(d.percentage for d in v.analytics.device_types)
            assert 99.0 <= device_sum <= 101.0


class TestSampleChannelDataProvider:
    def test_provider_get_channel(
        self, sample_provider: SampleChannelDataProvider
    ) -> None:
        """Verify get_channel returns canonical Channel model."""
        channel = asyncio.run(sample_provider.get_channel())
        assert isinstance(channel, Channel)
        assert channel.channel_id == "croviq_syn_ai_eng_01"
        assert channel.source_type == "synthetic"
        assert len(channel.videos) == 100

    def test_provider_get_videos_pagination(
        self, sample_provider: SampleChannelDataProvider
    ) -> None:
        """Verify pagination across video list."""
        page_1 = asyncio.run(sample_provider.get_videos(limit=10, offset=0))
        page_2 = asyncio.run(sample_provider.get_videos(limit=10, offset=10))
        all_videos = asyncio.run(sample_provider.get_videos(limit=150, offset=0))

        assert len(page_1) == 10
        assert len(page_2) == 10
        assert len(all_videos) == 100
        assert page_1[0].video_id == "vid_syn_001"
        assert page_2[0].video_id == "vid_syn_011"
        assert page_1[0].video_id != page_2[0].video_id

    def test_provider_get_video_by_id(
        self, sample_provider: SampleChannelDataProvider
    ) -> None:
        """Verify single video lookup by ID."""
        video = asyncio.run(sample_provider.get_video("vid_syn_005"))
        assert video is not None
        assert video.video_id == "vid_syn_005"
        assert "Gemini" in video.public.title or "Claude" in video.public.title

        missing = asyncio.run(sample_provider.get_video("non_existent_id"))
        assert missing is None

    def test_provider_get_analytics(
        self, sample_provider: SampleChannelDataProvider
    ) -> None:
        """Verify channel and video analytics retrieval."""
        channel_analytics = asyncio.run(sample_provider.get_channel_analytics())
        assert channel_analytics.total_views > 1_000_000

        video_analytics = asyncio.run(
            sample_provider.get_video_analytics("vid_syn_001")
        )
        assert video_analytics is not None
        assert video_analytics.views > 0
        assert len(video_analytics.retention_curve) == 101

        missing_analytics = asyncio.run(
            sample_provider.get_video_analytics("non_existent_id")
        )
        assert missing_analytics is None

    def test_provider_returns_canonical_daily_series(
        self, sample_provider: SampleChannelDataProvider
    ) -> None:
        series = asyncio.run(
            sample_provider.get_channel_timeseries(
                start_date=date(2026, 8, 1),
                end_date=date(2026, 8, 26),
            )
        )

        assert series.start_date == date(2026, 8, 1)
        assert series.end_date == date(2026, 8, 26)
        assert series.is_modeled is True
        assert len(series.points) == 26
        assert [point.date for point in series.points] == sorted(
            point.date for point in series.points
        )
        assert sum(point.views for point in series.points) > 0
    def test_missing_fixture_raises_error(self, tmp_path: Path) -> None:
        """Verify provider fails loudly if fixture is missing or malformed."""
        with pytest.raises(FileNotFoundError):
            SampleChannelDataProvider(fixture_path=tmp_path / "missing.json")

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="Failed to validate"):
            SampleChannelDataProvider(fixture_path=bad_file)


class TestDeliberateStatisticalSignals:
    """Validate that designed statistical patterns are measurable in the dataset without being hardcoded deterministic rules."""

    def test_early_demo_retention_advantage(self, channel: Channel) -> None:
        """Early practical demonstrations (first_demo <= 30s) correlate with higher average view percentage than late demos (> 45s)."""
        early_demo_videos = [
            v for v in channel.videos if v.derived.first_demo_seconds <= 30
        ]
        late_demo_videos = [
            v for v in channel.videos if v.derived.first_demo_seconds > 45
        ]

        assert len(early_demo_videos) > 20
        assert len(late_demo_videos) > 10

        mean_early_retention = sum(
            v.analytics.avg_view_percentage for v in early_demo_videos
        ) / len(early_demo_videos)
        mean_late_retention = sum(
            v.analytics.avg_view_percentage for v in late_demo_videos
        ) / len(late_demo_videos)

        # Early demo videos should have significantly higher average view percentage (> 10% absolute gap)
        assert mean_early_retention > mean_late_retention + 8.0

    def test_devops_search_traffic_dominance(self, channel: Channel) -> None:
        """GitHub Actions / DevOps videos exhibit significantly higher YouTube search traffic share (> 35%)."""
        devops_videos = [
            v
            for v in channel.videos
            if v.derived.content_pillar == ContentPillar.GITHUB_ACTIONS_DEVOPS
        ]
        other_videos = [
            v
            for v in channel.videos
            if v.derived.content_pillar != ContentPillar.GITHUB_ACTIONS_DEVOPS
        ]

        def get_search_pct(v) -> float:
            for src in v.analytics.traffic_sources:
                if src.source == "youtube_search":
                    return src.percentage
            return 0.0

        mean_devops_search = sum(get_search_pct(v) for v in devops_videos) / len(
            devops_videos
        )
        mean_other_search = sum(get_search_pct(v) for v in other_videos) / len(
            other_videos
        )

        assert mean_devops_search > 36.0
        assert mean_devops_search > mean_other_search + 10.0

    def test_time_sensitive_topics_ctr_advantage(self, channel: Channel) -> None:
        """Time-sensitive topic releases have higher CTR on average than evergreen content."""
        time_sensitive = [
            v for v in channel.videos if v.derived.is_time_sensitive_topic
        ]
        evergreen = [
            v for v in channel.videos if not v.derived.is_time_sensitive_topic
        ]

        mean_ts_ctr = sum(v.analytics.ctr_percentage for v in time_sensitive) / len(
            time_sensitive
        )
        mean_ev_ctr = sum(v.analytics.ctr_percentage for v in evergreen) / len(
            evergreen
        )

        assert mean_ts_ctr > mean_ev_ctr + 1.5

    def test_title_style_ctr_differences(self, channel: Channel) -> None:
        """Outcome-focused titles outperform generic tutorial titles in CTR."""
        outcome_titles = [
            v
            for v in channel.videos
            if v.derived.title_style == TitleStyle.OUTCOME_FOCUSED
        ]
        generic_tutorials = [
            v
            for v in channel.videos
            if v.derived.title_style == TitleStyle.GENERIC_TUTORIAL
        ]

        mean_outcome_ctr = sum(
            v.analytics.ctr_percentage for v in outcome_titles
        ) / len(outcome_titles)
        mean_generic_ctr = sum(
            v.analytics.ctr_percentage for v in generic_tutorials
        ) / len(generic_tutorials)

        assert mean_outcome_ctr > mean_generic_ctr + 2.0


class TestByteDeterminism:
    def test_generator_matches_committed_fixture(self) -> None:
        """Running the generator script produces data identical to the committed fixture."""
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        sys.path.insert(0, str(repo_root))
        from scripts.generate_sample_channel import generate_sample_dataset

        fresh_fixture = generate_sample_dataset()

        fixture_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "croviq_domain"
            / "fixtures"
            / "sample_channel_ai_engineering_v1.json"
        )
        committed_fixture = SampleChannelFixture.model_validate_json(
            fixture_path.read_text(encoding="utf-8")
        )

        assert fresh_fixture == committed_fixture

    def test_generator_produces_byte_identical_output(self) -> None:
        """Running the generator multiple times produces byte-identical output."""
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        sys.path.insert(0, str(repo_root))
        from scripts.generate_sample_channel import generate_sample_dataset

        run1 = generate_sample_dataset().model_dump_json(indent=2)
        run2 = generate_sample_dataset().model_dump_json(indent=2)
        assert run1 == run2


class TestSampleChannelSafety:
    def test_is_sample_channel_helper(self) -> None:
        """Verify canonical and legacy sample channel IDs are recognized and blocked from publish."""
        assert is_sample_channel(CANONICAL_SAMPLE_CHANNEL_ID) is True
        assert is_sample_channel("croviq_syn_ai_eng_01") is True
        assert is_sample_channel("sample_tech_channel") is True
        assert is_sample_channel("sample_custom_01") is True
        assert is_sample_channel("croviq_syn_v2") is True
        assert is_sample_channel("UC_real_creator_channel_123") is False
        assert is_sample_channel("") is False
        assert is_sample_channel(None) is False
