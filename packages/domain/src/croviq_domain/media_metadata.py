"""Canonical MediaMetadata domain model representing deterministic FFprobe media parameters."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MediaMetadata(BaseModel):
    """Canonical metadata extracted from source video/audio via FFprobe."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=True,
    )

    duration_ms: int = Field(
        ...,
        gt=0,
        description="Duration of the media in milliseconds",
    )
    width: int = Field(
        default=0,
        ge=0,
        description="Video frame width in pixels (0 for audio-only)",
    )
    height: int = Field(
        default=0,
        ge=0,
        description="Video frame height in pixels (0 for audio-only)",
    )
    frame_rate: float = Field(
        default=0.0,
        ge=0.0,
        description="Video frame rate in frames per second (0.0 for audio-only)",
    )
    video_codec: str = Field(
        default="none",
        description="Video codec name (e.g. 'h264', 'hevc', 'vp9', or 'none')",
    )
    audio_codec: str | None = Field(
        default=None,
        description="Audio codec name (e.g. 'aac', 'opus', 'pcm_s16le')",
    )
    audio_sample_rate: int | None = Field(
        default=None,
        gt=0,
        description="Audio sample rate in Hertz (e.g. 48000, 44100, 16000)",
    )
    audio_channels: int | None = Field(
        default=None,
        gt=0,
        description="Audio channel count (e.g. 1 for mono, 2 for stereo)",
    )
    rotation: int = Field(
        default=0,
        description="Video orientation rotation in degrees (0, 90, 180, 270)",
    )
    size_bytes: int = Field(
        ...,
        gt=0,
        description="Total media file size in bytes",
    )

    @field_validator("rotation")
    @classmethod
    def validate_rotation(cls, v: int) -> int:
        if v not in (0, 90, 180, 270):
            raise ValueError(f"Rotation must be one of [0, 90, 180, 270], got {v}")
        return v

    @property
    def is_audio_only(self) -> bool:
        """Return True if media contains no valid video stream."""
        return self.width == 0 or self.height == 0 or self.video_codec in ("none", "", "null")
