"""Exceptions for Memory Bank operations."""


class MemoryStoreError(Exception):
    """Base exception for memory bank store failures."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class MemoryProfileNotFoundError(MemoryStoreError):
    """Raised when a requested channel memory profile does not exist."""

    def __init__(self, channel_id: str) -> None:
        super().__init__(f"Memory profile for channel '{channel_id}' not found.", status_code=404)
        self.channel_id = channel_id
