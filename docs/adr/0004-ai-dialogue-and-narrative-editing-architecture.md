# 0004: AI Dialogue Editing, Director/Editor Batch Review, and Natural Cut Safety

## Context
Video editing requires both high-level semantic understanding (identifying rambling, false starts, repetitive explanations, filler words, narrative pacing) and frame/sample-accurate cut execution. Relying purely on raw multimodal LLM timestamp estimates causes jarring audio cutoffs, clipped words, and unnatural visual jump cuts. Conversely, asking creators to approve every single filler word removal creates overwhelming friction and defeats the autonomous production vision.

## Decision
We implement a hybrid AI Dialogue Editing and Batch Review architecture:

1. **Role Division (Maya & Leo)**:
   - **Maya (Director)**: Senior production lead agent who inspects raw video footage, queries long-term Channel Memory in Memory Bank, sets creative/editorial strategy, delegates the dialogue pass to Leo, reviews the complete edited candidate, requests corrections, and approves the master render.
   - **Leo (Editor)**: Narrative and dialogue editing agent who performs a comprehensive dialogue pass across the transcript and timeline, eliminating filler words (`um`, `uh`), false starts, repeated explanations, and dead air, while extracting one compelling vertical Short (9:16).

2. **Batch Review Workflow**:
   - Leo executes the entire dialogue pass autonomously across the timeline/transcript.
   - Leo generates a batch report summarizing total cuts, duration changes, and potential visual jump cuts covered.
   - Maya reviews the entire batch against Channel Memory and narrative coherence, issuing structured adjustments (e.g. "restore line at 01:34 to preserve premise") before approving the final render.
   - Rendering executes automatically upon Maya's approval without requiring creator micromanagement.

3. **Natural Cut Safety Pipeline**:
   ```text
   Semantic Edit Decision (Gemini 3.7 Flash)
     -> Word/Sentence Alignment (Phonetic/Word Timestamps)
     -> Natural Speech Boundary Detection
     -> Cut Safety & Discontinuity Inspection
     -> Transition Strategy Selection (Crossfade, Room Tone, Screen B-Roll Cover)
     -> Canonical Edit Decision List (EDL)
     -> Deterministic Cloud Run FFmpeg Rendering
   ```

4. **Live Workspace Synchronization**:
   - Left ~80%: Twick multi-track timeline and video player visualizing cut intervals and animated gap closure.
   - Right ~20%: Active agent summary card (top) and synchronized transcript (bottom) with color-coded edit states (removed `#B85454`, suggested `#A77A32`, preserved `#4F7F65`, processing `#5279B8`).

5. **Automatic One-Short Render**:
   - Following the master edit, Leo extracts the strongest self-contained 20–60s highlight, formats it as 9:16 vertical video with burned-in synchronized captions, and registers it as a standalone artifact.

## Consequences
- Eliminates mechanical word clipping and jarring jump cuts through deterministic safety boundaries and screen B-roll coverage.
- Provides a judge-visible agent collaboration moment where Maya and Leo interact credibly in front of the creator.
- Protects the creator from approving micro-cuts while keeping the master render fully automated and verifiable.
