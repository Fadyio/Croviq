"""Global test configuration and fixtures for croviq_api tests."""

import pytest
from croviq_observability import clear_request_context


@pytest.fixture(autouse=True)
def clean_request_context():
    """Ensure contextvars never leak between tests."""
    clear_request_context()
    yield
    clear_request_context()
