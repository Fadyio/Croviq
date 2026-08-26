# 0017: Natural Cut Safety Pipeline and Deterministic FFmpeg Media Rendering

## Context
AI dialogue editing models often output cut intervals based on high-level semantic analysis. Executing cuts strictly on raw LLM timestamps results in clipped speech syllables, breath chopping, abrupt room tone changes, and jarring visual jump cuts. Furthermore, replacing deterministic video rendering with black-box generative video models is too slow, expensive, and unpredictable for core long-form video editing.

## Decision
We enforce a strict division of labor between AI reasoning, word-level alignment, and deterministic media rendering:

1. **Division of Labor**:
   - **Gemini 3.7 Flash**: Decides *what* dialogue/sections to cut and *why* (semantic redundancy, filler words, false starts, pacing).
   - **Groq Whisper Large v3**: Provides word-level timing anchors across the audio stream. The deterministic cut-safety layer decides final cut boundaries.
   - **FFmpeg & Cut Safety Pipeline**: Computes *where* cuts can occur safely without clipping words or creating acoustic artifacts, leveraging audio envelope analysis.
   - **Twick SDK**: *Visualizes* the cut decisions in the browser timeline and transcript.
   - **FFmpeg on Cloud Run**: *Executes* the final Edit Decision List (EDL) deterministically against source media.

2. **Cut Safety & Transition Pipeline**:
   - Word start/end anchors from Groq Whisper prevent naive mid-word slicing; the cut-safety layer decides actual media cut boundaries.
   - Micro-crossfades (10–30ms) on audio transitions eliminate click/pop artifacts.
   - Room-tone continuity checks bridge silent gaps.
   - Screen-recording / terminal B-roll footage is automatically prioritized to cover talking-head visual jump cuts.

3. **Vendor-Neutral Canonical EDL**:
   - The contract between Gemini reasoning, transcription alignment, and FFmpeg rendering is a typed, versioned JSON schema (`EditDecisionList`).
   - The backend renderer has zero proprietary dependencies on Twick or external cloud exporter APIs.

4. **Optional Generative Video Boundary**:
   - Google generative video models (e.g. Omni) may be used *only* as an optional shot-level creative tool (e.g. generated B-roll for cut coverage). The core edit pipeline operates 100% deterministically without generative video dependencies.

## Consequences
- Guarantees natural, broadcast-quality speech flow and video playback using Groq Whisper word-level timing anchors plus deterministic cut-safety checks.
- Decouples creative reasoning from deterministic media execution.
- Enables fast, reliable rendering on standard Google Cloud Run instances.
