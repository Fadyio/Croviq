"""Tests for Canonical Model Registry & Capability Status Contract."""

import pytest
from croviq_domain.model_registry import (
    CANONICAL_MODEL_REGISTRY,
    ModelCapabilityEntry,
    ModelImplementationStatus,
    UpstreamVerificationStatus,
    get_model_capability,
)


def test_canonical_model_registry_contains_all_core_models():
    models = {entry.model_id: entry for entry in CANONICAL_MODEL_REGISTRY}
    assert "gemini-3.7-flash" in models
    assert "gemini-3.5-transcribe-preview" in models
    assert "gemini-3.1-flash-tts-preview" in models
    assert "gemini-omni-1.1-flash-preview" in models


def test_gemini_37_reasoning_capability_is_implemented_and_proven():
    entry = get_model_capability("gemini-3.7-flash")
    assert entry is not None
    assert entry.implemented == ModelImplementationStatus.IMPLEMENTED
    assert entry.live_upstream_proven == UpstreamVerificationStatus.YES
    assert "GoogleGenAIClient" in entry.code_path


def test_gemini_35_transcribe_capability_is_implemented_and_proven():
    entry = get_model_capability("gemini-3.5-transcribe-preview")
    assert entry is not None
    assert entry.implemented == ModelImplementationStatus.IMPLEMENTED
    assert entry.live_upstream_proven == UpstreamVerificationStatus.YES
    assert "GeminiTranscriptionService" in entry.code_path


def test_gemini_31_tts_capability_is_implemented_and_proven():
    entry = get_model_capability("gemini-3.1-flash-tts-preview")
    assert entry is not None
    assert entry.implemented == ModelImplementationStatus.IMPLEMENTED
    assert entry.live_upstream_proven == UpstreamVerificationStatus.YES
    assert "synthesize_studio_voice" in entry.code_path


def test_gemini_omni_capability_is_implemented_and_proven():
    entry = get_model_capability("gemini-omni-1.1-flash-preview")
    assert entry is not None
    assert entry.implemented == ModelImplementationStatus.IMPLEMENTED
    assert entry.live_upstream_proven == UpstreamVerificationStatus.YES
    assert entry.draft_360p_verified is True
    assert entry.duration_control_verified is True
    assert entry.audio_isolation_verified is True
    assert "generate_broll_clip" in entry.code_path


def test_unknown_model_returns_none():
    assert get_model_capability("non-existent-model") is None
