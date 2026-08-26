# Specification: Director + Editor Vertical Slice

**Status:** Canonical Working Specification for Day 1 Implementation  
**Frozen Baseline:** `Croviq — Product & Architecture Freeze (2026-08-26)`  
**Target Milestone:** Director + Editor Hero Experience  

---

## 1. Product Objective & Hero Narrative

Croviq is **DevOps for YouTube creators**: an autonomous, visible production team that learns the channel, transforms raw footage into a release, validates the work, learns from performance, and feeds those lessons into the next production.

### The Judged Hero Journey
1. **Sign in** at `https://app.croviq.app` using `demo@croviq.app`.
2. **First-use choice**: Select **Use Sample Channel** (~50k subs AI engineering channel loaded).
3. **Channel Memory initialized**: Google Agent Platform Memory Bank loads the `ChannelProfile` and active `ChannelLesson` rules.
4. **Drop raw video**: Creator uploads a 3–8 minute raw recording (the owner's real GitHub Actions tutorial with false starts, filler words, dead air, and screen demos).
5. **Editor workspace opens** (80/20 split):
   - **Maya (Director)** inspects source video + Memory Bank and announces editorial strategy ("The hook starts at 00:31; handing dialogue pass to Leo").
   - **Leo (Editor)** performs the full dialogue pass using Gemini 3.7 Flash semantic decisions anchored to Google Cloud Speech-to-Text v2 word timestamps.
   - **Live workspace updates**: Twick timeline and synchronized transcript visibly update (red strikethrough for removals, amber for review, green for preserved key takes).
   - **Natural cut safety**: Speech boundaries are respected, micro-crossfades are inserted, and talking-head jump cuts are covered with screen demonstration footage.
   - **Leo reports batch**: Summary of cuts, duration saved, and edits applied.
   - **Maya reviews batch**: Maya evaluates the result, requests one correction (e.g. "Keep phrase at 01:34"), and Leo adjusts.
   - **Maya approves**: Automatic master video render begins via FFmpeg on Cloud Run.
   - **One Short extracted**: Automatic extraction of one vertical 9:16 Short (20–60s) with synchronized burned-in captions.

---

## 2. Technical Architecture & Component Contracts

### 2.1 Channel Data Provider Boundary
```text
scripts/generate_sample_channel.py (Deterministic Seed / Math)
                    ↓
packages/domain/src/croviq_domain/fixtures/sample_channel_ai_engineering_v1.json
                    ↓
SampleChannelDataProvider (FastAPI / Domain Service)
```

- **Production/Sample Mode**: Reads the pre-computed static JSON fixture for zero runtime latency and 100% test reproducibility.
- **Canonical Schema (`packages/domain/src/croviq_domain/channel.py`)**:
  - `ChannelMetadata`: `channel_id`, `title`, `description`, `subscriber_count`, `video_count`, `total_views`, `content_pillars[]`.
  - `VideoAnalyticsSummary`: `video_id`, `views`, `watch_time_minutes`, `avg_view_duration_seconds`, `avg_view_percentage`, `ctr_percentage`, `retention_curve[]`.

### 2.2 Shared Channel Memory (Memory Bank)
- Backed by **Google Agent Platform Memory Bank**.
- Direct FastAPI integration in `apps/api/src/croviq_api/memory/`.
- Schema:
  - `ChannelProfile`: Primary niche, audience demographics, content pillars, baseline performance metrics, recurring retention patterns.
  - `ChannelLesson`: `lesson_id`, `directive`, `target_agent` (`director`, `editor`, `packaging`, `qa`), `evidence_summary`, `confidence`, `status` (`ACTIVE`, `TESTING`, `RETIRED`).

### 2.3 Raw Media Upload & Production Record
- **Endpoint**: `POST /api/productions` → creates `Production` record in Firestore (`status: "DRAFT"`).
- **Upload Negotiation**: `POST /api/productions/{id}/upload-url` → returns pre-signed GCS PUT URL for raw media.
- **Client Direct Upload**: Frontend uploads raw video directly to private GCS bucket (`croviq-media-raw`).
- **Completion Hook**: `POST /api/productions/{id}/upload-complete` → transitions `Production` to `PROCESSING`, registers raw `Artifact`, and kicks off analysis.

### 2.4 Multimodal Agents & Audio Word Alignment
- **Division of Labor**:
  - **Gemini 3.7 Flash** (via Google GenAI SDK `google-genai`): Understands video/audio narrative, identifies semantic redundancy, filler words, false starts, and Short candidate range.
  - **Google Cloud Speech-to-Text v2 API**: Provides frame-accurate word-level start/end time offsets.
  - **FFmpeg**: Silence envelope detection and deterministic cut rendering.
- **Maya (Director Agent)**:
  - Input: Raw video artifact, transcript, `ChannelProfile`, relevant `ChannelLesson` records.
  - Output (`DirectorStrategy`): `summary`, `editorial_notes[]`, `suggested_pacing`, `hand_off_instructions`.
  - Review Output (`DirectorReview`): `approved: bool`, `feedback: str`, `adjustments: list[EditAdjustment]`.
- **Leo (Editor Agent)**:
  - Input: Raw video, word-timed transcript from STT v2, `DirectorStrategy`.
  - Output (`DialoguePassReport`): `edits: list[EditDecision]`, `cuts_count`, `duration_saved_ms`, `short_candidate_range`, `batch_notes`.

### 2.5 Canonical Edit Decision List (EDL) Schema
```json
{
  "edl_version": "1.0",
  "source_video_artifact_id": "art_raw_123",
  "original_duration_ms": 384000,
  "target_duration_ms": 329000,
  "edits": [
    {
      "edit_id": "edit_01",
      "action": "remove",
      "start_ms": 4200,
      "end_ms": 8500,
      "transcript_start_word": 8,
      "transcript_end_word": 16,
      "reason": "False start and filler words",
      "confidence": 0.94,
      "transition_strategy": "audio_crossfade",
      "status": "applied"
    },
    {
      "edit_id": "edit_02",
      "action": "cover",
      "start_ms": 134000,
      "end_ms": 142000,
      "reason": "Talking-head jump cut covered with terminal footage",
      "cover_source": "screen_recording_01",
      "status": "applied"
    }
  ],
  "short_excerpt": {
    "start_ms": 31000,
    "end_ms": 68000,
    "hook_title": "Custom CI/CD with Cloud Run",
    "caption_track_id": "cap_short_01"
  }
}
```

### 2.6 Natural Cut Safety Pipeline
1. **Word-Level Timing (STT v2)**: Extract millisecond start/end timestamps for each spoken word.
2. **Boundary Padding & Silence Envelope**: Ensure cutpoints snap to inter-word silence intervals rather than mid-phoneme.
3. **Audio Smoothing**: Apply 20ms audio micro-crossfades to prevent clicks.
4. **Visual Discontinuity Mitigation**: When speech cuts cause a jarring talking-head jump, prioritize screen demo / terminal B-roll footage as an overlay.

### 2.7 Twick Editor Workspace (80/20 Split)
- **Left 80%**:
  - HTML5 video player canvas with synchronized timecode.
  - Twick multi-track timeline (Video V1, Audio A1, Edit Markers TX).
  - Animated gap closures as edits are applied.
- **Right 20%**:
  - **Top Panel**: Active agent avatar chip (Maya / Leo), role badge, and concise action/reason summaries.
  - **Bottom Panel**: Real-time synchronized transcript with click-to-playhead navigation and semantic color treatments:
    - Removed: Red strikethrough (`#B85454` at 15% bg).
    - Review / Suggested: Muted amber underline (`#A77A32` at 15% bg).
    - Preserved: Muted green tint (`#4F7F65` at 15% bg).
    - Processing: Muted blue pulse (`#5279B8`).

### 2.8 Deterministic FFmpeg Rendering Engine
- Executes headless FFmpeg commands in Cloud Run (`croviq-api`).
- **Master Video Render**: Applies cut intervals from canonical EDL against raw video from GCS, producing `master_video.mp4`.
- **One Short Render**: Cuts the designated 20–60s range, crops/scales to 9:16 vertical (1080x1920), burns in synchronized captions, and produces `short_master.mp4`.

---

## 3. Testing Seams & Verification Gates

### Seam 1: Judge / Browser Seam (Highest Priority)
- Real Chrome automated test (`apps/web/e2e/hero-editor.spec.ts`):
  1. Sign in with `demo@croviq.app`.
  2. Select sample channel.
  3. Upload raw GitHub Actions demo video.
  4. Verify Maya handoff to Leo.
  5. Verify synchronized timeline and transcript updates.
  6. Verify batch review correction and approval.
  7. Verify master render completion and playable Short.

### Seam 2: Agent Contract Seam
- Pytest suite in `packages/agents/tests/`:
  - Validate structured Pydantic outputs from Gemini 3.7 Flash.
  - Validate model ID configuration.
  - Validate Maya review logic and bounded correction loops.
  - Validate rejection of malformed agent responses.

### Seam 3: Media & EDL Seam
- Pytest suite in `packages/media/tests/`:
  - Validate EDL execution against real source video.
  - Validate duration math and natural cut safety padding.
  - Validate 9:16 vertical aspect ratio and caption burn-in for Short.

### Seam 4: Production & Observability Seam
- Verify Cloud Logging structured entries for `ai.call.started`, `ai.call.completed` with exact model ID, input/output tokens, and latency metrics.

---

## 4. Acceptance Criteria Checklist

- [ ] Deterministic sample AI engineering channel loaded without external credentials.
- [ ] Raw video upload to GCS succeeds with signed URLs.
- [ ] Speech-to-Text v2 generates word-timed transcript offsets.
- [ ] Maya reviews source footage + Channel Memory and hands off to Leo.
- [ ] Leo performs dialogue pass with live transcript and timeline synchronization.
- [ ] Natural speech boundaries respected with zero mid-word audio clipping.
- [ ] Maya reviews batch report, requests one correction, and approves.
- [ ] Deterministic FFmpeg render produces playable master video in GCS.
- [ ] Automatic vertical 9:16 Short rendered with synchronized captions.
- [ ] Structured AI logs emitted to Cloud Logging with exact model identifier.
