# 0004: AI Dialogue and Narrative Editing Architecture

## Context
Video editing requires both high-level semantic understanding (identifying rambling, false starts, repetitive ideas, filler words, pacing) and sample/frame-accurate cut execution. Relying purely on LLM-generated timestamp estimates can cause jarring audio cutoffs or clipped words. Conversely, basic audio-amplitude silence removal lacks editorial intelligence and cannot understand semantic redundancy or narrative structure.

## Decision
We implement a hybrid AI Dialogue & Narrative Editing architecture:
1. **Semantic Video Understanding (Gemini 3.7 Flash)**: The model processes native video and audio to identify editorial improvements: excessive silence, filler words (`um`, `uh`, `you know`), false starts/bad takes, repeated sentences/ideas, rambling or low-value dialogue, awkward pauses, weak intros, and candidate ranges for Shorts.
2. **Deterministic Alignment**: Word and timestamp boundaries from word-level audio alignment anchor Gemini's semantic decisions into frame-accurate cut intervals within a canonical Edit Decision List (EDL).
3. **Interactive Visual Feedback**: The browser UI synchronizes a text transcript alongside the Twick timeline and video player. Cuts and proposals are visually color-coded:
   - Red strikethrough: removed segments
   - Amber: suggested removals / review items
   - Green: preserved key moments / highlights
   Clicking transcript phrases jumps the timeline playhead, and timeline gaps close dynamically as cuts are applied.
4. **Deterministic Rendering**: FFmpeg on Cloud Run renders the final cut master, generates synchronized captions, and extracts the designated Short from the EDL.
5. **Scope Boundary**: Generative B-roll, AI music generation (Lyria), and automated dubbing are explicitly deferred to post-MVP.

## Consequences
- Produces professional-grade dialogue cuts that respect narrative context without clipping words.
- Provides an undeniable visual demo where the creator watches the agent reason and edit the timeline.
- Decouples semantic editorial reasoning from media processing.
