from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from croviq_domain.user import User


def test_valid_user_creation() -> None:
    now = datetime.now(timezone.utc)
    user = User(
        user_id="usr_abc123",
        email="creator@croviq.com",
        display_name="Alex River",
        avatar_url="https://croviq.com/avatars/alex.png",
        created_at=now,
        updated_at=now,
    )
    assert user.user_id == "usr_abc123"
    assert user.email == "creator@croviq.com"
    assert user.display_name == "Alex River"
    assert user.avatar_url == "https://croviq.com/avatars/alex.png"
    assert user.created_at == now
    assert user.updated_at == now


def test_valid_user_without_avatar() -> None:
    now = datetime.now(timezone.utc)
    user = User(
        user_id="usr_no_avatar",
        email="noavatar@croviq.com",
        display_name="Jordan",
        created_at=now,
        updated_at=now,
    )
    assert user.avatar_url is None


def test_user_requires_timezone_aware_timestamps() -> None:
    naive_dt = datetime(2026, 8, 25, 12, 0, 0)
    with pytest.raises(ValidationError) as exc_info:
        User(
            user_id="usr_naive",
            email="naive@croviq.com",
            display_name="Naive Timestamps",
            created_at=naive_dt,
            updated_at=datetime.now(timezone.utc),
        )
    assert "timezone-aware" in str(exc_info.value).lower()

    with pytest.raises(ValidationError) as exc_info:
        User(
            user_id="usr_naive2",
            email="naive2@croviq.com",
            display_name="Naive Timestamps 2",
            created_at=datetime.now(timezone.utc),
            updated_at=naive_dt,
        )
    assert "timezone-aware" in str(exc_info.value).lower()


def test_user_rejects_empty_id_or_display_name() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        User(
            user_id="",
            email="test@croviq.com",
            display_name="Valid Name",
            created_at=now,
            updated_at=now,
        )

    with pytest.raises(ValidationError):
        User(
            user_id="usr_123",
            email="test@croviq.com",
            display_name="",
            created_at=now,
            updated_at=now,
        )


def test_user_rejects_invalid_email() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        User(
            user_id="usr_123",
            email="not-an-email",
            display_name="Valid Name",
            created_at=now,
            updated_at=now,
        )


def test_user_rejects_extra_fields() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        User(
            user_id="usr_123",
            email="extra@croviq.com",
            display_name="Extra",
            created_at=now,
            updated_at=now,
            unauthorized_field="malicious",  # type: ignore[call-arg]
        )


def test_user_serialization_and_deserialization_roundtrip() -> None:
    now = datetime(2026, 8, 25, 14, 30, 0, tzinfo=timezone.utc)
    user = User(
        user_id="usr_roundtrip",
        email="roundtrip@croviq.com",
        display_name="Round Trip",
        avatar_url="https://images.croviq.com/avatar.jpg",
        created_at=now,
        updated_at=now,
    )

    dumped_dict = user.model_dump(mode="json")
    assert dumped_dict["user_id"] == "usr_roundtrip"
    assert dumped_dict["email"] == "roundtrip@croviq.com"
    assert dumped_dict["display_name"] == "Round Trip"
    assert dumped_dict["avatar_url"] == "https://images.croviq.com/avatar.jpg"
    assert dumped_dict["created_at"].startswith("2026-08-25T14:30:00")

    json_str = user.model_dump_json()
    reconstructed = User.model_validate_json(json_str)
    assert reconstructed == user
    assert reconstructed.created_at == now
