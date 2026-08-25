"""Authentication exception classes for Croviq API."""


class AuthError(Exception):
    """Base exception for authentication errors."""

    def __init__(self, message: str, error_code: str = "authentication_failed") -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class MissingTokenError(AuthError):
    """Raised when Authorization header or token is missing."""

    def __init__(self, message: str = "Missing authorization header") -> None:
        super().__init__(message, error_code="missing_authorization_header")


class MalformedHeaderError(AuthError):
    """Raised when Authorization header is malformed."""

    def __init__(self, message: str = "Malformed authorization header") -> None:
        super().__init__(message, error_code="malformed_authorization_header")


class InvalidTokenError(AuthError):
    """Raised when token signature or claims validation fails."""

    def __init__(self, message: str = "Invalid token") -> None:
        super().__init__(message, error_code="invalid_token")


class ExpiredTokenError(AuthError):
    """Raised when token has expired."""

    def __init__(self, message: str = "Token has expired") -> None:
        super().__init__(message, error_code="expired_token")
