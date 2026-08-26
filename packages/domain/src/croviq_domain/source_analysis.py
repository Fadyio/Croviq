"""SourceVideoAnalysisInput contract for Gemini 3.7 Flash editorial reasoning."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.production import SourceMedia
from croviq_domain.transcript import Transcript


class SourceVideoAnalysisInput(BaseModel):
    """Canonical provider-neutral input contract consumed by Gemini agents in Issue #26."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=True,
    )

    production_id: str = Field(
        ...,
        min_length=1,
        description="Associated Production entity identifier",
    )
    source_media: SourceMedia = Field(
        ...,
        description="Source media upload metadata and GCS reference",
    )
    media_metadata: MediaMetadata = Field(
        ...,
        description="Deterministic FFprobe media technical parameters",
    )
    transcript: Transcript = Field(
        ...,
        description="Word-aligned transcript with millisecond timestamps",
    )
    channel_id: str = Field(
        ...,
        min_length=1,
        description="Associated channel identifier",
    )
    channel_memory_reference: str | None = Field(
        default=None,
        description="Reference identifier to ChannelMemoryProfile in Memory Bank",
    )

    @model_validator(mode="after")
    def validate_production_consistency(self) -> "SourceVideoAnalysisInput":
        if self.transcript.production_id != self.production_id:
            raise ValueError(
                f"transcript.production_id ({self.transcript.production_id}) does not match "
                f"SourceVideoAnalysisInput.production_id ({self.production_id})"
            )
        return self
