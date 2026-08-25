"""Authenticated principal representation and domain mapping."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from croviq_api.auth.exceptions import InvalidTokenError
from croviq_domain.user import User


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Internal authenticated principal extracted from verified Identity Platform claims."""

    uid: str
    email: str | None = None
    name: str | None = None
    picture: str | None = None
    auth_time: datetime | None = None

    @classmethod
    def from_claims(cls, claims: dict[str, Any]) -> "AuthenticatedPrincipal":
        """Construct principal from verified token claims.

        UID is extracted strictly from verified token claims (uid or sub).
        Client-supplied user IDs are never trusted.
        """
        uid = claims.get("uid") or claims.get("sub") or claims.get("user_id")
        if not uid or not isinstance(uid, str) or not uid.strip():
            raise InvalidTokenError("Missing or invalid user identifier in verified claims")

        email = claims.get("email")
        name = claims.get("name")
        picture = claims.get("picture")

        auth_time_raw = claims.get("auth_time") or claims.get("iat")
        auth_time: datetime | None = None
        if auth_time_raw is not None:
            try:
                auth_time = datetime.fromtimestamp(float(auth_time_raw), tz=timezone.utc)
            except Exception:
                auth_time = None

        return cls(
            uid=uid.strip(),
            email=email.strip() if isinstance(email, str) and email.strip() else None,
            name=name.strip() if isinstance(name, str) and name.strip() else None,
            picture=picture.strip() if isinstance(picture, str) and picture.strip() else None,
            auth_time=auth_time,
        )

    def to_domain_user(self) -> User:
        """Map authenticated principal to canonical User domain entity."""
        now = datetime.now(timezone.utc)
        created_at = self.auth_time if self.auth_time is not None else now
        email_str = self.email or f"{self.uid}@placeholder.croviq.app"
        display_name = self.name or (self.email.split("@")[0] if self.email else "User")

        return User(
            user_id=self.uid,
            email=email_str,
            display_name=display_name,
            avatar_url=self.picture,
            created_at=created_at,
            updated_at=now,
        )
