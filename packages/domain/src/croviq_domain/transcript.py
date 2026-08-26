"""Canonical Transcript domain models for word-aligned speech recognition."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from croviq_domain.validators import validate_timezone_aware


class SilenceInterval(BaseModel):
    """Represents a silence or non-speech interval between spoken words."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    start_ms: int = Field(
        ...,
        ge=0,
        description="Silence interval start offset in milliseconds",
    )
    end_ms: int = Field(
        ...,
        gt=0,
        description="Silence interval end offset in milliseconds",
    )
    duration_ms: int = Field(
        ...,
        gt=0,
        description="Silence interval duration in milliseconds",
    )

    @model_validator(mode="after")
    def validate_bounds(self) -> "SilenceInterval":
        if self.end_ms <= self.start_ms:
            raise ValueError(
                f"end_ms ({self.end_ms}) must be strictly greater than start_ms ({self.start_ms})"
            )
        expected_duration = self.end_ms - self.start_ms
        if self.duration_ms != expected_duration:
            raise ValueError(
                f"duration_ms ({self.duration_ms}) must equal end_ms - start_ms ({expected_duration})"
            )
        return self


class TranscriptWord(BaseModel):
    """Canonical representation of a single spoken word with millisecond time alignment."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=True,
    )

    index: int = Field(
        ...,
        ge=0,
        description="Zero-based sequential index of the word in the transcript",
    )
    text: str = Field(
        ...,
        min_length=1,
        description="Spoken text of the word",
    )
    start_ms: int = Field(
        ...,
        ge=0,
        description="Start offset from beginning of audio stream in milliseconds",
    )
    end_ms: int = Field(
        ...,
        gt=0,
        description="End offset from beginning of audio stream in milliseconds",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score from speech recognizer (0.0 to 1.0)",
    )
    speaker_id: str | None = Field(
        default=None,
        description="Optional speaker identifier or diarization tag",
    )

    @property
    def duration_ms(self) -> int:
        """Word duration in milliseconds."""
        return self.end_ms - self.start_ms

    @model_validator(mode="after")
    def validate_timing(self) -> "TranscriptWord":
        if self.end_ms <= self.start_ms:
            raise ValueError(
                f"end_ms ({self.end_ms}) must be strictly greater than start_ms ({self.start_ms}) for word '{self.text}'"
            )
        return self


class TranscriptSegment(BaseModel):
    """Canonical representation of a spoken phrase or sentence segment."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=True,
    )

    segment_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for this segment",
    )
    start_ms: int = Field(
        ...,
        ge=0,
        description="Start offset of the segment in milliseconds",
    )
    end_ms: int = Field(
        ...,
        gt=0,
        description="End offset of the segment in milliseconds",
    )
    text: str = Field(
        ...,
        min_length=1,
        description="Aggregated text content of the segment",
    )
    word_start_index: int = Field(
        ...,
        ge=0,
        description="Inclusive start index in the transcript words list",
    )
    word_end_index: int = Field(
        ...,
        ge=0,
        description="Inclusive end index in the transcript words list",
    )

    @property
    def word_count(self) -> int:
        """Number of words in this segment."""
        return self.word_end_index - self.word_start_index + 1

    @model_validator(mode="after")
    def validate_bounds(self) -> "TranscriptSegment":
        if self.end_ms <= self.start_ms:
            raise ValueError(
                f"end_ms ({self.end_ms}) must be strictly greater than start_ms ({self.start_ms})"
            )
        if self.word_end_index < self.word_start_index:
            raise ValueError(
                f"word_end_index ({self.word_end_index}) cannot be less than word_start_index ({self.word_start_index})"
            )
        return self


class Transcript(BaseModel):
    """Canonical domain model for a word-aligned transcript."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    transcript_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the transcript entity",
    )
    production_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of the associated Production record",
    )
    language_code: str = Field(
        ...,
        min_length=2,
        description="Language tag of the transcription (e.g. 'en-US' or 'en')",
    )
    duration_ms: int = Field(
        ...,
        ge=0,
        description="Total duration of the audio/speech stream in milliseconds",
    )
    words: list[TranscriptWord] = Field(
        default_factory=list,
        description="Ordered list of word-level timestamped tokens",
    )
    segments: list[TranscriptSegment] = Field(
        default_factory=list,
        description="Ordered list of sentence/phrase segments",
    )
    silence_intervals: list[SilenceInterval] = Field(
        default_factory=list,
        description="Identified inter-word silence intervals",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the transcript was generated (UTC)",
    )

    @property
    def word_count(self) -> int:
        """Total number of spoken words in the transcript."""
        return len(self.words)

    @property
    def segment_count(self) -> int:
        """Total number of segments in the transcript."""
        return len(self.segments)

    @field_validator("created_at")
    @classmethod
    def check_created_at_timezone(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)

    @model_validator(mode="after")
    def validate_transcript_invariants(self) -> "Transcript":
        # 1. Monotonicity and contiguous index check
        for i, word in enumerate(self.words):
            if word.index != i:
                raise ValueError(
                    f"Word at position {i} must have contiguous index {i}, found {word.index}"
                )
            if i > 0:
                prev_word = self.words[i - 1]
                if word.start_ms < prev_word.start_ms:
                    raise ValueError(
                        f"Words must have monotonic start times: word '{word.text}' (start {word.start_ms}ms) "
                        f"starts before word '{prev_word.text}' (start {prev_word.start_ms}ms)"
                    )

        # 2. Duration consistency
        if self.words:
            last_word_end = self.words[-1].end_ms
            if self.duration_ms < last_word_end:
                raise ValueError(
                    f"Transcript duration_ms ({self.duration_ms}ms) cannot be less than last word end_ms ({last_word_end}ms)"
                )

        # 3. Populate silence intervals if not provided
        if self.words and not self.silence_intervals:
            computed = self.compute_silence_intervals(min_silence_ms=0)
            object.__setattr__(self, "silence_intervals", computed)

        return self

    def compute_silence_intervals(self, min_silence_ms: int = 100) -> list[SilenceInterval]:
        """Compute inter-word silence intervals greater than or equal to min_silence_ms."""
        silences: list[SilenceInterval] = []
        if len(self.words) < 2:
            return silences

        for i in range(len(self.words) - 1):
            curr_end = self.words[i].end_ms
            next_start = self.words[i + 1].start_ms
            if next_start > curr_end:
                gap = next_start - curr_end
                if gap >= min_silence_ms:
                    silences.append(
                        SilenceInterval(
                            start_ms=curr_end,
                            end_ms=next_start,
                            duration_ms=gap,
                        )
                    )
        return silences

    def get_silence_intervals(self, min_silence_ms: int = 100) -> list[SilenceInterval]:
        """Return silence intervals matching or exceeding min_silence_ms."""
        return [s for s in self.silence_intervals if s.duration_ms >= min_silence_ms]

    def get_words_in_range(self, start_ms: int, end_ms: int) -> list[TranscriptWord]:
        """Return words that fall entirely or substantially within the given millisecond interval."""
        return [
            w
            for w in self.words
            if w.start_ms >= start_ms and w.end_ms <= end_ms
        ]
