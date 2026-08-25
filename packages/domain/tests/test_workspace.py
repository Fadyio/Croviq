from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from croviq_domain.brand_kit import BrandKit
from croviq_domain.user import User
from croviq_domain.workspace import Workspace


def test_valid_workspace_with_default_brand_kit() -> None:
    now = datetime.now(timezone.utc)
    workspace = Workspace(
        workspace_id="ws_main123",
        owner_user_id="usr_owner456",
        name="Alex River Studio",
        created_at=now,
        updated_at=now,
    )
    assert workspace.workspace_id == "ws_main123"
    assert workspace.owner_user_id == "usr_owner456"
    assert workspace.name == "Alex River Studio"
    assert workspace.channel_description is None
    assert isinstance(workspace.brand_kit, BrandKit)
    assert workspace.brand_kit.tone == []
    assert workspace.created_at == now
    assert workspace.updated_at == now


def test_valid_workspace_with_custom_brand_kit() -> None:
    now = datetime.now(timezone.utc)
    brand_kit = BrandKit(
        tone=["educational", "inspiring"],
        target_audience="Aspiring video creators",
        content_style="Tutorial with screen capture",
        custom_instructions="Include hook in first 5 seconds",
    )
    workspace = Workspace(
        workspace_id="ws_creator99",
        owner_user_id="usr_creator11",
        name="Creator Academy",
        channel_description="Daily tutorials on editing and production",
        brand_kit=brand_kit,
        created_at=now,
        updated_at=now,
    )
    assert workspace.channel_description == "Daily tutorials on editing and production"
    assert workspace.brand_kit.tone == ["educational", "inspiring"]
    assert workspace.brand_kit.target_audience == "Aspiring video creators"


def test_workspace_owner_relationship() -> None:
    now = datetime.now(timezone.utc)
    user = User(
        user_id="usr_sarah_100",
        email="sarah@croviq.com",
        display_name="Sarah Jenkins",
        created_at=now,
        updated_at=now,
    )
    workspace = Workspace(
        workspace_id="ws_sarah_primary",
        owner_user_id=user.user_id,
        name="Sarah's Channel",
        created_at=now,
        updated_at=now,
    )
    assert workspace.owner_user_id == user.user_id


def test_workspace_requires_timezone_aware_timestamps() -> None:
    naive_dt = datetime(2026, 8, 25, 12, 0, 0)
    with pytest.raises(ValidationError) as exc_info:
        Workspace(
            workspace_id="ws_naive",
            owner_user_id="usr_123",
            name="Studio",
            created_at=naive_dt,
            updated_at=datetime.now(timezone.utc),
        )
    assert "timezone-aware" in str(exc_info.value).lower()


def test_workspace_rejects_empty_ids_or_name() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        Workspace(
            workspace_id="",
            owner_user_id="usr_123",
            name="Studio",
            created_at=now,
            updated_at=now,
        )

    with pytest.raises(ValidationError):
        Workspace(
            workspace_id="ws_123",
            owner_user_id="",
            name="Studio",
            created_at=now,
            updated_at=now,
        )

    with pytest.raises(ValidationError):
        Workspace(
            workspace_id="ws_123",
            owner_user_id="usr_123",
            name="",
            created_at=now,
            updated_at=now,
        )


def test_workspace_rejects_extra_fields() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        Workspace(
            workspace_id="ws_123",
            owner_user_id="usr_123",
            name="Studio",
            created_at=now,
            updated_at=now,
            random_field="disallowed",  # type: ignore[call-arg]
        )


def test_workspace_serialization_and_deserialization_roundtrip() -> None:
    now = datetime(2026, 8, 25, 16, 0, 0, tzinfo=timezone.utc)
    workspace = Workspace(
        workspace_id="ws_roundtrip",
        owner_user_id="usr_roundtrip_owner",
        name="Roundtrip Productions",
        channel_description="Full test channel description",
        brand_kit=BrandKit(
            tone=["dynamic"],
            target_audience="General audience",
        ),
        created_at=now,
        updated_at=now,
    )

    dumped = workspace.model_dump(mode="json")
    assert dumped["workspace_id"] == "ws_roundtrip"
    assert dumped["owner_user_id"] == "usr_roundtrip_owner"
    assert dumped["name"] == "Roundtrip Productions"
    assert dumped["channel_description"] == "Full test channel description"
    assert dumped["brand_kit"]["tone"] == ["dynamic"]

    json_str = workspace.model_dump_json()
    reconstructed = Workspace.model_validate_json(json_str)
    assert reconstructed == workspace
    assert reconstructed.brand_kit.tone == ["dynamic"]
