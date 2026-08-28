from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import re
from statistics import mean
from typing import Any, Protocol

import httpx

from croviq_domain.channel import (
    Channel,
    ChannelAnalyticsPoint,
    ChannelAnalyticsTimeSeries,
    ChannelPrivateAnalytics,
    ChannelPublicMetadata,
    ChannelVideo,
    ContentPillar,
    DerivedChannelFeatures,
    DerivedVideoFeatures,
    TitleStyle,
    VideoFormat,
    VideoPrivateAnalytics,
    VideoPublicMetadata,
)
from croviq_domain.channel_provider import ChannelDataProvider


YOUTUBE_DATA_BASE = "https://www.googleapis.com/youtube/v3"
YOUTUBE_ANALYTICS_REPORTS = "https://youtubeanalytics.googleapis.com/v2/reports"
_DURATION_PATTERN = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


class YouTubeProviderError(RuntimeError):
    pass


class YouTubeRequester(Protocol):
    async def get_json(
        self, url: str, params: dict[str, str], access_token: str
    ) -> dict[str, Any]: ...


class HttpxYouTubeRequester:
    def __init__(self, timeout_seconds: float = 20) -> None:
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def get_json(
        self, url: str, params: dict[str, str], access_token: str
    ) -> dict[str, Any]:
        response = await self._client.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code >= 400:
            raise YouTubeProviderError(
                f"YouTube API request failed with status {response.status_code}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise YouTubeProviderError("YouTube API returned an invalid response")
        return payload

    async def close(self) -> None:
        await self._client.aclose()


def _parse_duration_seconds(value: str) -> int:
    match = _DURATION_PATTERN.match(value)
    if match is None:
        raise YouTubeProviderError("YouTube returned an unsupported video duration")
    parts = {name: int(raw or 0) for name, raw in match.groupdict().items()}
    return max(
        1,
        parts["days"] * 86400
        + parts["hours"] * 3600
        + parts["minutes"] * 60
        + parts["seconds"],
    )


def _rows_as_dicts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    headers = payload.get("columnHeaders", [])
    rows = payload.get("rows", [])
    if not isinstance(headers, list) or not isinstance(rows, list):
        raise YouTubeProviderError("YouTube Analytics returned an invalid report")
    names = [header.get("name") for header in headers if isinstance(header, dict)]
    if not names or any(not isinstance(name, str) for name in names):
        return []
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, list) and len(row) == len(names):
            normalized.append(dict(zip(names, row, strict=True)))
    return normalized


def _classify_video(title: str, tags: list[str]) -> DerivedVideoFeatures:
    text = f"{title} {' '.join(tags)}".lower()
    if "gemini" in text or "vertex" in text:
        pillar = ContentPillar.GEMINI_VERTEX
    elif "cloud run" in text or "devops" in text or "deploy" in text:
        pillar = ContentPillar.CLOUD_RUN_GCP
    elif "agent" in text:
        pillar = ContentPillar.AI_AGENTS
    else:
        pillar = ContentPillar.EMERGING_AI

    if "tutorial" in text or "guide" in text or "how to" in text:
        video_format = VideoFormat.TUTORIAL
    elif "architecture" in text:
        video_format = VideoFormat.ARCHITECTURE_DEEP_DIVE
    elif " vs " in text or "comparison" in text:
        video_format = VideoFormat.TOOL_COMPARISON
    else:
        video_format = VideoFormat.RELEASE_ANALYSIS

    return DerivedVideoFeatures(
        content_pillar=pillar,
        video_format=video_format,
        title_style=TitleStyle.OUTCOME_FOCUSED,
        first_demo_seconds=None,
        hook_length_seconds=None,
        setup_time_seconds=None,
        topic_cluster=tags[0] if tags else title,
        is_time_sensitive_topic=any(
            term in text for term in ("release", "launch", "new", "announced")
        ),
    )


class YouTubeChannelDataProvider(ChannelDataProvider):
    def __init__(
        self,
        *,
        access_token: str,
        requester: YouTubeRequester | None = None,
        analytics_start_date: date | None = None,
        analytics_end_date: date | None = None,
    ) -> None:
        if not access_token:
            raise ValueError("access_token is required")
        self._access_token = access_token
        self._requester = requester or HttpxYouTubeRequester()
        self._analytics_end_date = analytics_end_date or datetime.now(UTC).date()
        self._analytics_start_date = analytics_start_date or (
            self._analytics_end_date - timedelta(days=365)
        )
        self._channel: Channel | None = None

    async def _request(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        return await self._requester.get_json(url, params, self._access_token)

    async def _load_channel_metadata(self) -> tuple[dict[str, Any], str]:
        payload = await self._request(
            f"{YOUTUBE_DATA_BASE}/channels",
            {"part": "snippet,statistics,contentDetails", "mine": "true"},
        )
        items = payload.get("items")
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            raise YouTubeProviderError("Authorized account has no YouTube channel")
        item = items[0]
        uploads = (
            item.get("contentDetails", {})
            .get("relatedPlaylists", {})
            .get("uploads")
        )
        if not isinstance(uploads, str) or not uploads:
            raise YouTubeProviderError("YouTube uploads playlist is unavailable")
        return item, uploads

    async def _load_video_ids(self, uploads_playlist_id: str) -> list[str]:
        video_ids: list[str] = []
        page_token: str | None = None
        while len(video_ids) < 100:
            params = {
                "part": "contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": "50",
            }
            if page_token:
                params["pageToken"] = page_token
            payload = await self._request(
                f"{YOUTUBE_DATA_BASE}/playlistItems", params
            )
            for item in payload.get("items", []):
                if isinstance(item, dict):
                    video_id = item.get("contentDetails", {}).get("videoId")
                    if isinstance(video_id, str):
                        video_ids.append(video_id)
            next_token = payload.get("nextPageToken")
            if not isinstance(next_token, str) or not next_token:
                break
            page_token = next_token
        return video_ids[:100]

    async def _load_public_videos(self, video_ids: list[str]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for offset in range(0, len(video_ids), 50):
            payload = await self._request(
                f"{YOUTUBE_DATA_BASE}/videos",
                {
                    "part": "snippet,contentDetails,statistics",
                    "id": ",".join(video_ids[offset : offset + 50]),
                    "maxResults": "50",
                },
            )
            items.extend(item for item in payload.get("items", []) if isinstance(item, dict))
        return items

    async def _load_video_analytics(self) -> dict[str, dict[str, Any]]:
        payload = await self._request(
            YOUTUBE_ANALYTICS_REPORTS,
            {
                "ids": "channel==MINE",
                "startDate": self._analytics_start_date.isoformat(),
                "endDate": self._analytics_end_date.isoformat(),
                "dimensions": "video",
                "metrics": (
                    "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,"
                    "subscribersGained,subscribersLost,likes,comments,shares"
                ),
                "maxResults": "200",
                "sort": "-views",
            },
        )
        return {
            str(row["video"]): row
            for row in _rows_as_dicts(payload)
            if row.get("video")
        }

    async def _ensure_loaded(self) -> Channel:
        if self._channel is not None:
            return self._channel
        channel_item, uploads_playlist = await self._load_channel_metadata()
        video_ids = await self._load_video_ids(uploads_playlist)
        public_video_items = await self._load_public_videos(video_ids)
        analytics_by_video = await self._load_video_analytics()

        videos: list[ChannelVideo] = []
        for item in public_video_items:
            video_id = str(item.get("id", ""))
            if not video_id:
                continue
            snippet = item.get("snippet", {})
            statistics = item.get("statistics", {})
            content_details = item.get("contentDetails", {})
            analytics = analytics_by_video.get(video_id, {})
            title = str(snippet.get("title", "Untitled video"))
            tags = [str(tag) for tag in snippet.get("tags", []) if isinstance(tag, str)]
            thumbnails = snippet.get("thumbnails", {})
            thumbnail_url = ""
            if isinstance(thumbnails, dict):
                for quality in ("maxres", "standard", "high", "medium", "default"):
                    candidate = thumbnails.get(quality)
                    if isinstance(candidate, dict) and candidate.get("url"):
                        thumbnail_url = str(candidate["url"])
                        break
            videos.append(
                ChannelVideo(
                    video_id=video_id,
                    public=VideoPublicMetadata(
                        video_id=video_id,
                        title=title,
                        description=str(snippet.get("description", "")),
                        tags=tags,
                        duration_seconds=_parse_duration_seconds(
                            str(content_details.get("duration", "PT1S"))
                        ),
                        published_at=datetime.fromisoformat(
                            str(snippet["publishedAt"]).replace("Z", "+00:00")
                        ),
                        view_count=int(statistics.get("viewCount", 0)),
                        like_count=int(statistics.get("likeCount", 0)),
                        comment_count=int(statistics.get("commentCount", 0)),
                        thumbnail_url=thumbnail_url,
                        category_id=str(snippet.get("categoryId", "28")),
                    ),
                    analytics=VideoPrivateAnalytics(
                        views=int(analytics.get("views", 0)),
                        watch_time_minutes=float(
                            analytics.get("estimatedMinutesWatched", 0)
                        ),
                        avg_view_duration_seconds=float(
                            analytics.get("averageViewDuration", 0)
                        ),
                        avg_view_percentage=float(
                            analytics.get("averageViewPercentage", 0)
                        ),
                        subscribers_gained=int(
                            analytics.get("subscribersGained", 0)
                        ),
                        subscribers_lost=int(
                            analytics.get("subscribersLost", 0)
                        ),
                        likes=int(analytics.get("likes", 0)),
                        comments=int(analytics.get("comments", 0)),
                        shares=int(analytics.get("shares", 0)),
                        impressions=None,
                        ctr_percentage=None,
                        estimated_revenue_usd=None,
                        retention_curve=[],
                        traffic_sources=[],
                        geography=[],
                        device_types=[],
                    ),
                    derived=_classify_video(title, tags),
                )
            )

        snippet = channel_item.get("snippet", {})
        statistics = channel_item.get("statistics", {})
        channel_id = str(channel_item.get("id", ""))
        total_views = sum(video.analytics.views for video in videos)
        total_watch_minutes = sum(
            video.analytics.watch_time_minutes for video in videos
        )
        total_gained = sum(video.analytics.subscribers_gained for video in videos)
        total_lost = sum(video.analytics.subscribers_lost for video in videos)
        avg_duration = (
            sum(
                video.analytics.avg_view_duration_seconds * video.analytics.views
                for video in videos
            )
            / total_views
            if total_views
            else 0
        )
        publish_dates = sorted(video.public.published_at for video in videos)
        intervals = [
            (current - previous).total_seconds() / 86400
            for previous, current in zip(publish_dates, publish_dates[1:])
        ]
        thumbnails = snippet.get("thumbnails", {})
        avatar = None
        if isinstance(thumbnails, dict):
            default_thumbnail = thumbnails.get("default")
            if isinstance(default_thumbnail, dict) and default_thumbnail.get("url"):
                avatar = str(default_thumbnail["url"])
        content_pillars = list(dict.fromkeys(video.derived.content_pillar for video in videos))
        self._channel = Channel(
            channel_id=channel_id,
            source_type="youtube",
            public=ChannelPublicMetadata(
                channel_id=channel_id,
                title=str(snippet.get("title", "YouTube channel")),
                description=str(snippet.get("description", "")),
                custom_url=str(snippet.get("customUrl", "")),
                subscriber_count=int(statistics.get("subscriberCount", 0)),
                video_count=int(statistics.get("videoCount", len(videos))),
                total_views=int(statistics.get("viewCount", 0)),
                joined_at=datetime.fromisoformat(
                    str(snippet["publishedAt"]).replace("Z", "+00:00")
                ),
                country=str(snippet.get("country", "US")),
                avatar_url=avatar,
                banner_url=None,
            ),
            analytics=ChannelPrivateAnalytics(
                total_views=total_views,
                total_watch_time_hours=total_watch_minutes / 60,
                current_subscribers=int(statistics.get("subscriberCount", 0)),
                total_subscribers_gained=total_gained,
                total_subscribers_lost=total_lost,
                avg_view_duration_seconds=avg_duration,
                avg_ctr_percentage=None,
                total_impressions=None,
                top_traffic_sources=[],
                top_geographies=[],
                device_distribution=[],
            ),
            derived=DerivedChannelFeatures(
                primary_niche=str(snippet.get("title", "YouTube channel")),
                content_pillars=content_pillars or [ContentPillar.EMERGING_AI],
                high_performing_formats=[],
                weak_formats=[],
                average_publish_interval_days=mean(intervals) if intervals else 0,
                inferred_audience_level="unknown",
            ),
            videos=videos,
        )
        return self._channel

    async def get_channel(self) -> Channel:
        return await self._ensure_loaded()

    async def get_videos(
        self, limit: int = 100, offset: int = 0
    ) -> list[ChannelVideo]:
        channel = await self._ensure_loaded()
        return channel.videos[offset : offset + limit]

    async def get_video(self, video_id: str) -> ChannelVideo | None:
        channel = await self._ensure_loaded()
        return next(
            (video for video in channel.videos if video.video_id == video_id), None
        )

    async def get_channel_analytics(self) -> ChannelPrivateAnalytics:
        return (await self._ensure_loaded()).analytics

    async def get_video_analytics(
        self, video_id: str
    ) -> VideoPrivateAnalytics | None:
        video = await self.get_video(video_id)
        return video.analytics if video else None

    async def get_channel_timeseries(
        self, *, start_date: date, end_date: date
    ) -> ChannelAnalyticsTimeSeries:
        if end_date < start_date:
            raise ValueError("end_date must not precede start_date")
        payload = await self._request(
            YOUTUBE_ANALYTICS_REPORTS,
            {
                "ids": "channel==MINE",
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": "day",
                "metrics": (
                    "views,estimatedMinutesWatched,averageViewPercentage,"
                    "subscribersGained,subscribersLost"
                ),
                "sort": "day",
            },
        )
        by_date = {str(row["day"]): row for row in _rows_as_dicts(payload)}
        points: list[ChannelAnalyticsPoint] = []
        cursor = start_date
        while cursor <= end_date:
            row = by_date.get(cursor.isoformat(), {})
            points.append(
                ChannelAnalyticsPoint(
                    date=cursor,
                    views=int(row.get("views", 0)),
                    watch_time_minutes=float(
                        row.get("estimatedMinutesWatched", 0)
                    ),
                    subscribers_gained=int(row.get("subscribersGained", 0)),
                    subscribers_lost=int(row.get("subscribersLost", 0)),
                    average_view_percentage=float(
                        row.get("averageViewPercentage", 0)
                    ),
                )
            )
            cursor += timedelta(days=1)
        return ChannelAnalyticsTimeSeries(
            start_date=start_date,
            end_date=end_date,
            points=points,
            is_modeled=False,
        )
