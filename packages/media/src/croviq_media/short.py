"""Deterministic Short candidate processing, caption timing rebasing, and ASS subtitle generation."""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from croviq_domain.editorial import ShortCandidate
from croviq_domain.transcript import Transcript, TranscriptWord


CROVIQ_BLUE_ASS_BGR = "&H00EB6325&"  # #2563EB (R:0x25, G:0x63, B:0xEB -> &H00BBGGRR&)
WHITE_ASS_BGR = "&H00FFFFFF&"
OUTLINE_BLACK_ASS_BGR = "&H00000000&"
SHADOW_TRANSPARENT_ASS_BGR = "&H80000000&"


@dataclass(frozen=True)
class CaptionWord:
    """Individual spoken word with output-rebased start and end timestamps."""

    index: int
    text: str
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


@dataclass(frozen=True)
class CaptionPhrase:
    """Deterministic phrase group consisting of 2 to 6 spoken words."""

    start_ms: int
    end_ms: int
    words: list[CaptionWord]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


def validate_and_snap_short_candidate(
    candidate: ShortCandidate,
    source_duration_ms: int,
    transcript: Transcript | None = None,
) -> tuple[int, int]:
    """Validate candidate boundaries and snap deterministically to canonical transcript word boundaries."""
    if candidate.start_ms < 0:
        raise ValueError(f"candidate.start_ms ({candidate.start_ms}) must be non-negative")
    if candidate.end_ms <= candidate.start_ms:
        raise ValueError(
            f"candidate.end_ms ({candidate.end_ms}) must be greater than start_ms ({candidate.start_ms})"
        )
    if candidate.end_ms > source_duration_ms + 500:  # Allow 500ms container rounding tolerance
        raise ValueError(
            f"candidate.end_ms ({candidate.end_ms}) exceeds source duration ({source_duration_ms})"
        )

    snapped_start = candidate.start_ms
    snapped_end = min(candidate.end_ms, source_duration_ms)

    if transcript and transcript.words:
        # 1. Try explicit word indices if valid
        start_idx = candidate.transcript_start_word
        end_idx = candidate.transcript_end_word

        if 0 <= start_idx < len(transcript.words) and 0 <= end_idx < len(transcript.words) and start_idx <= end_idx:
            snapped_start = transcript.words[start_idx].start_ms
            snapped_end = transcript.words[end_idx].end_ms
        else:
            # 2. Overlap search: find words covering [candidate.start_ms, candidate.end_ms]
            overlapping = [
                w for w in transcript.words
                if w.end_ms > candidate.start_ms and w.start_ms < candidate.end_ms
            ]
            if overlapping:
                snapped_start = overlapping[0].start_ms
                snapped_end = overlapping[-1].end_ms

    snapped_start = max(0, snapped_start)
    snapped_end = min(snapped_end, source_duration_ms)

    if snapped_end <= snapped_start:
        snapped_start = candidate.start_ms
        snapped_end = min(candidate.end_ms, source_duration_ms)

    return snapped_start, snapped_end


def extract_rebased_caption_words(
    transcript: Transcript,
    short_start_ms: int,
    short_end_ms: int,
    keep_segments: list[tuple[int, int]] | None = None,
) -> list[CaptionWord]:
    """Extract and rebase word timestamps relative to the Short's output timeline."""
    rebased: list[CaptionWord] = []

    # Map source timestamps to output timeline when keep_segments are provided
    for w in transcript.words:
        if w.end_ms <= short_start_ms or w.start_ms >= short_end_ms:
            continue

        if keep_segments is not None:
            # Map source word timing into the concatenated keep segment output timeline
            word_out_start = _map_source_time_to_output(w.start_ms, keep_segments)
            word_out_end = _map_source_time_to_output(w.end_ms, keep_segments)
            if word_out_start is None or word_out_end is None:
                continue
        else:
            word_out_start = max(0, w.start_ms - short_start_ms)
            word_out_end = max(word_out_start + 10, w.end_ms - short_start_ms)

        rebased.append(
            CaptionWord(
                index=len(rebased),
                text=w.text,
                start_ms=word_out_start,
                end_ms=max(word_out_start + 10, word_out_end),
            )
        )

    return rebased


def _map_source_time_to_output(source_ms: int, keep_segments: list[tuple[int, int]]) -> int | None:
    """Map source media timestamp into concatenated keep segments timeline."""
    accumulated_ms = 0
    for seg_start, seg_end in keep_segments:
        if source_ms < seg_start:
            return accumulated_ms
        if seg_start <= source_ms <= seg_end:
            return accumulated_ms + (source_ms - seg_start)
        accumulated_ms += (seg_end - seg_start)
    return accumulated_ms


def group_words_into_phrases(
    words: list[CaptionWord],
    min_words: int = 2,
    max_words: int = 6,
    max_pause_ms: int = 300,
) -> list[CaptionPhrase]:
    """Deterministically group rebased words into readable caption phrases."""
    if not words:
        return []

    phrases: list[CaptionPhrase] = []
    current_words: list[CaptionWord] = []

    for i, word in enumerate(words):
        current_words.append(word)

        is_last_word = (i == len(words) - 1)
        next_word = words[i + 1] if not is_last_word else None

        # Check pause boundary
        pause_exceeded = False
        if next_word:
            pause_ms = next_word.start_ms - word.end_ms
            if pause_ms > max_pause_ms:
                pause_exceeded = True

        # Check punctuation ending
        ends_with_punct = bool(re.search(r"[.?!,;:]$", word.text))

        # Decision to finalize current phrase
        should_split = False
        if len(current_words) >= max_words:
            should_split = True
        elif len(current_words) >= min_words and (ends_with_punct or pause_exceeded):
            should_split = True
        elif pause_exceeded and len(current_words) >= 1:
            should_split = True
        elif is_last_word:
            should_split = True

        if should_split and current_words:
            phrase_start = current_words[0].start_ms
            phrase_end = current_words[-1].end_ms
            phrases.append(
                CaptionPhrase(
                    start_ms=phrase_start,
                    end_ms=phrase_end,
                    words=list(current_words),
                )
            )
            current_words = []

    return phrases


def format_ass_timecode(ms: int) -> str:
    """Format milliseconds into ASS subtitle timecode H:MM:SS.cs."""
    total_sec = max(0, ms) / 1000.0
    hours = int(total_sec // 3600)
    minutes = int((total_sec % 3600) // 60)
    seconds = int(total_sec % 60)
    centiseconds = int(round((total_sec - int(total_sec)) * 100))
    if centiseconds >= 100:
        centiseconds = 0
        seconds += 1
        if seconds >= 60:
            seconds = 0
            minutes += 1
            if minutes >= 60:
                minutes = 0
                hours += 1
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def generate_ass_subtitles(
    phrases: list[CaptionPhrase],
    font_name: str = "Arial",
    font_size: int = 64,
    highlight_color_bgr: str = CROVIQ_BLUE_ASS_BGR,
    base_color_bgr: str = WHITE_ASS_BGR,
    outline_color_bgr: str = OUTLINE_BLACK_ASS_BGR,
    shadow_color_bgr: str = SHADOW_TRANSPARENT_ASS_BGR,
    margin_v: int = 320,
    play_res_x: int = 1080,
    play_res_y: int = 1920,
) -> str:
    """Generate professional ASS subtitle script with synchronized active word emphasis."""
    lines: list[str] = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {play_res_x}",
        f"PlayResY: {play_res_y}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font_name},{font_size},{base_color_bgr},&H000000FF,{outline_color_bgr},{shadow_color_bgr},-1,0,0,0,100,100,0,0,1,4,2,2,60,60,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for phrase in phrases:
        num_words = len(phrase.words)
        if num_words == 0:
            continue

        for i, current_word in enumerate(phrase.words):
            word_start_tc = format_ass_timecode(current_word.start_ms)
            # Active word duration extends to next word start or phrase end
            next_word_start = phrase.words[i + 1].start_ms if i + 1 < num_words else phrase.end_ms
            active_end_ms = max(current_word.end_ms, next_word_start)
            word_end_tc = format_ass_timecode(active_end_ms)

            # Build line text with active word highlighted in highlight_color_bgr
            rendered_words: list[str] = []
            for j, w in enumerate(phrase.words):
                if j == i:
                    rendered_words.append(f"{{\\c{highlight_color_bgr}}}{w.text}{{\\c{base_color_bgr}}}")
                else:
                    rendered_words.append(w.text)

            line_text = " ".join(rendered_words)
            lines.append(
                f"Dialogue: 0,{word_start_tc},{word_end_tc},Default,,0,0,0,,{line_text}"
            )

    return "\n".join(lines) + "\n"
