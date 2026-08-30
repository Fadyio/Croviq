"""Unit tests for BackgroundMusicMixer and EBU R128 loudness measurement."""

from pathlib import Path
import tempfile
import pytest
from croviq_media.audio import (
    AudioLoudnessMeasurement,
    BackgroundMusicMixer,
    measure_ebur128_loudness,
)


def test_audio_loudness_measurement_dataclass():
    meas = AudioLoudnessMeasurement(
        integrated_lufs=-16.2,
        loudness_range_lu=7.4,
        true_peak_dbtp=-1.5,
        threshold_lufs=-26.2,
    )
    assert meas.is_dialogue_compliant is True
    assert meas.is_true_peak_compliant is True


def test_audio_loudness_non_compliant():
    meas = AudioLoudnessMeasurement(
        integrated_lufs=-10.0,
        loudness_range_lu=3.0,
        true_peak_dbtp=-0.2,
    )
    assert meas.is_dialogue_compliant is False
    assert meas.is_true_peak_compliant is False


def test_background_music_filter_builder():
    mixer = BackgroundMusicMixer()
    speech_intervals = [(1000, 4000), (6000, 9000)]
    flt = mixer.build_music_filter(
        speech_intervals,
        volume_db=-24.0,
        ducking_db=-14.0,
        total_duration_ms=12000,
    )
    assert "afade=t=in:st=0:d=1.500" in flt
    assert "afade=t=out:st=9.500:d=2.500" in flt
    assert "volume=-24.00dB" in flt
    assert "between(t,1.000,4.000)+between(t,6.000,9.000)" in flt
