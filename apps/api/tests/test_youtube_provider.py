import asyncio
from datetime import date
from typing import Any

from croviq_api.channels.youtube_provider import YouTubeChannelDataProvider


class FakeYouTubeRequester:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    async def get_json(
        self, url: str, params: dict[str, str], access_token: str
    ) -> dict[str, Any]:
        assert access_token == "access-token"
        self.calls.append((url, params))
        if url.endswith("/channels"):
            return {
                "items": [{
                    "id": "UC_real",
                    "snippet": {
                        "title": "Real Creator",
                        "description": "Technical videos",
                        "customUrl": "@realcreator",
                        "publishedAt": "2020-01-01T00:00:00Z",
                        "country": "US",
                        "thumbnails": {"default": {"url": "https://yt3.example/avatar.jpg"}},
                    },
                    "statistics": {
                        "subscriberCount": "1200",
                        "videoCount": "2",
                        "viewCount": "85000",
                    },
                    "contentDetails": {"relatedPlaylists": {"uploads": "UU_real"}},
                }]
            }
        if url.endswith("/playlistItems"):
            return {
                "items": [
                    {"contentDetails": {"videoId": "video-1"}},
                    {"contentDetails": {"videoId": "video-2"}},
                ]
            }
        if url.endswith("/videos"):
            return {
                "items": [
                    {
                        "id": "video-1",
                        "snippet": {
                            "title": "Build a Gemini agent",
                            "description": "Tutorial",
                            "publishedAt": "2026-08-01T00:00:00Z",
                            "tags": ["Gemini", "agents"],
                            "categoryId": "28",
                            "thumbnails": {"high": {"url": "https://i.ytimg.com/1.jpg"}},
                        },
                        "contentDetails": {"duration": "PT10M30S"},
                        "statistics": {"viewCount": "5000", "likeCount": "400", "commentCount": "35"},
                    },
                    {
                        "id": "video-2",
                        "snippet": {
                            "title": "Cloud Run deployment guide",
                            "description": "Guide",
                            "publishedAt": "2026-07-01T00:00:00Z",
                            "categoryId": "28",
                            "thumbnails": {"default": {"url": "https://i.ytimg.com/2.jpg"}},
                        },
                        "contentDetails": {"duration": "PT8M"},
                        "statistics": {"viewCount": "3000", "likeCount": "200", "commentCount": "20"},
                    },
                ]
            }
        if url.endswith("/reports") and params.get("dimensions") == "video":
            return {
                "columnHeaders": [
                    {"name": "video"}, {"name": "views"}, {"name": "estimatedMinutesWatched"},
                    {"name": "averageViewDuration"}, {"name": "averageViewPercentage"},
                    {"name": "subscribersGained"}, {"name": "subscribersLost"},
                    {"name": "likes"}, {"name": "comments"}, {"name": "shares"},
                ],
                "rows": [
                    ["video-1", 4900, 20000, 245, 38.9, 80, 5, 390, 33, 22],
                    ["video-2", 2900, 12000, 248, 51.7, 40, 4, 195, 19, 12],
                ],
            }
        if url.endswith("/reports") and params.get("dimensions") == "day":
            return {
                "columnHeaders": [
                    {"name": "day"}, {"name": "views"}, {"name": "estimatedMinutesWatched"},
                    {"name": "averageViewPercentage"}, {"name": "subscribersGained"},
                    {"name": "subscribersLost"},
                ],
                "rows": [
                    ["2026-08-27", 100, 400, 49.5, 3, 1],
                    ["2026-08-28", 120, 450, 50.2, 4, 0],
                ],
            }
        raise AssertionError(f"Unexpected YouTube request: {url} {params}")


def test_youtube_provider_normalizes_data_and_analytics() -> None:
    provider = YouTubeChannelDataProvider(
        access_token="access-token",
        requester=FakeYouTubeRequester(),
        analytics_start_date=date(2026, 1, 1),
        analytics_end_date=date(2026, 8, 28),
    )

    channel = asyncio.run(provider.get_channel())

    assert channel.channel_id == "UC_real"
    assert channel.source_type == "youtube"
    assert channel.public.subscriber_count == 1200
    assert len(channel.videos) == 2
    first = channel.videos[0]
    assert first.public.duration_seconds == 630
    assert first.analytics.views == 4900
    assert first.analytics.ctr_percentage is None
    assert first.analytics.impressions is None
    assert first.derived.first_demo_seconds is None


def test_youtube_provider_returns_real_daily_series_without_modeling() -> None:
    provider = YouTubeChannelDataProvider(
        access_token="access-token",
        requester=FakeYouTubeRequester(),
        analytics_start_date=date(2026, 1, 1),
        analytics_end_date=date(2026, 8, 28),
    )

    series = asyncio.run(
        provider.get_channel_timeseries(
            start_date=date(2026, 8, 27), end_date=date(2026, 8, 28)
        )
    )

    assert series.is_modeled is False
    assert [point.views for point in series.points] == [100, 120]
    assert series.points[-1].subscribers_gained == 4
