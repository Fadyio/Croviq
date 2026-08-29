"""Dependency injection for ChannelMemoryStore."""

from functools import lru_cache
from typing import Annotated
from fastapi import Depends

from croviq_api.config import Settings, get_settings
from croviq_api.memory.fake import FakeChannelMemoryStore
from croviq_api.memory.google import GoogleMemoryBankStore
from croviq_api.memory.store import ChannelMemoryStore
from croviq_domain.channel_provider import SampleChannelDataProvider
from croviq_domain.memory import ChannelProfileBuilder

_memory_store_override: ChannelMemoryStore | None = None
_default_store: ChannelMemoryStore | None = None


def set_memory_store(store: ChannelMemoryStore | None) -> None:
    """Override memory store for unit testing or test isolation."""
    global _memory_store_override
    _memory_store_override = store


async def initialize_sample_channel_memory(store: ChannelMemoryStore) -> None:
    """Ensure the canonical sample channel has a deterministic profile and lessons in the store."""
    sample_channel_id = "croviq_syn_ai_eng_01"
    provider = None
    channel = None

    if not await store.profile_exists(sample_channel_id):
        provider = SampleChannelDataProvider()
        channel = await provider.get_channel()
        profile = ChannelProfileBuilder.build_profile(channel)
        await store.upsert_profile(profile)

    existing_lessons = await store.get_lessons(sample_channel_id)
    if not existing_lessons:
        if channel is None:
            if provider is None:
                provider = SampleChannelDataProvider()
            channel = await provider.get_channel()
        lessons = ChannelProfileBuilder.build_lessons(channel)
        for lesson in lessons:
            await store.add_lesson(lesson)


def get_memory_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChannelMemoryStore:
    """Retrieve active ChannelMemoryStore dependency."""
    global _default_store, _memory_store_override
    if _memory_store_override is not None:
        return _memory_store_override

    if _default_store is None:
        if settings.is_production and settings.memory_store_provider != "google":
            raise RuntimeError("Fake memory store provider is strictly forbidden in production.")
        if settings.memory_store_provider == "google" and settings.gcp_project_id:
            _default_store = GoogleMemoryBankStore(
                project_id=settings.gcp_project_id,
                location=settings.memory_bank_location,
                memory_bank_id=settings.memory_bank_id,
            )
        elif settings.is_production:
            raise RuntimeError(
                "Google Cloud Project ID is required for Google Memory Bank in production."
            )
        else:
            _default_store = FakeChannelMemoryStore()

    return _default_store
