from pydantic import BaseModel, ConfigDict, Field


class BrandKit(BaseModel):
    """Canonical BrandKit configuration model for a Croviq Workspace."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    tone: list[str] = Field(
        default_factory=list,
        description="Tone adjectives or stylistic descriptors (e.g. ['concise', 'informative'])",
    )
    target_audience: str | None = Field(
        default=None,
        description="Description of the target audience and viewer demographic",
    )
    content_style: str | None = Field(
        default=None,
        description="Primary video content style or genre",
    )
    custom_instructions: str | None = Field(
        default=None,
        description="Custom production instructions and brand guidelines",
    )
