import pytest
from croviq_domain import (
    Channel,
    ChannelDataProvider,
    SampleChannelDataProvider,
)


@pytest.mark.asyncio
async def test_api_sample_channel_provider_contract() -> None:
    """Verify apps/api can initialize and query SampleChannelDataProvider without network overhead."""
    provider: ChannelDataProvider = SampleChannelDataProvider()

    # Fast synchronous loading of static fixture
    channel = await provider.get_channel()
    assert isinstance(channel, Channel)
    assert channel.channel_id == "croviq_syn_ai_eng_01"
    assert channel.public.title == "Modern AI Engineering"
    assert channel.public.subscriber_count == 51317
    assert len(channel.videos) == 100

    # Paginated access
    first_five = await provider.get_videos(limit=5, offset=0)
    assert len(first_five) == 5
    assert first_five[0].video_id == "vid_syn_001"

    # Aggregated channel analytics
    analytics = await provider.get_channel_analytics()
    assert analytics.total_views > 3_000_000
    assert analytics.current_subscribers == 51317
