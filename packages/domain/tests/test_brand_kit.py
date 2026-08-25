import pytest
from pydantic import ValidationError

from croviq_domain.brand_kit import BrandKit


def test_brand_kit_defaults() -> None:
    brand_kit = BrandKit()
    assert brand_kit.tone == []
    assert brand_kit.target_audience is None
    assert brand_kit.content_style is None
    assert brand_kit.custom_instructions is None


def test_brand_kit_custom_values() -> None:
    brand_kit = BrandKit(
        tone=["informative", "engaging", "analytical"],
        target_audience="Software engineers and tech entrepreneurs",
        content_style="Technical deep-dive with animated visual diagrams",
        custom_instructions="Maintain fast pacing and trim silences aggressively",
    )
    assert len(brand_kit.tone) == 3
    assert "analytical" in brand_kit.tone
    assert brand_kit.target_audience == "Software engineers and tech entrepreneurs"
    assert brand_kit.content_style == "Technical deep-dive with animated visual diagrams"
    assert brand_kit.custom_instructions == "Maintain fast pacing and trim silences aggressively"


def test_brand_kit_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        BrandKit(
            tone=["humorous"],
            unknown_setting="prohibited",  # type: ignore[call-arg]
        )


def test_brand_kit_serialization_roundtrip() -> None:
    brand_kit = BrandKit(
        tone=["calm", "thoughtful"],
        target_audience="Creative professionals",
        content_style="Documentary style",
        custom_instructions="Focus on authentic narrative",
    )
    dumped = brand_kit.model_dump(mode="json")
    assert dumped["tone"] == ["calm", "thoughtful"]
    assert dumped["target_audience"] == "Creative professionals"

    json_str = brand_kit.model_dump_json()
    reconstructed = BrandKit.model_validate_json(json_str)
    assert reconstructed == brand_kit
