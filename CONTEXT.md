# Croviq Domain Model

DevOps for YouTube creators: an autonomous, visible production team that learns the channel, transforms raw footage into a release, validates the work, learns from performance, and feeds those lessons into the next production.

## Core Language

### Studio & Tenancy

**Workspace**:
The top-level tenant container representing a creator studio, encapsulating channel connections, brand preferences, persistent channel memory, and productions.
_Avoid_: Organization, Channel, Account, Tenant

**Production**:
A single end-to-end content production lifecycle starting from raw footage to master release and derived assets. User-facing creator term.
_Avoid_: Mission, Project, Video, Episode, Campaign

**Mission**:
Internal engine representation of a production objective and workflow execution graph.
_Avoid_: Task, Ticket, Pipeline

**Run**:
An immutable, auditable execution instance of an engine workflow for a Production, recording state transitions, agent events, logs, and artifacts.
_Avoid_: Execution, Build, Job Run, Attempt

---

### Production Team (Agents)

**Data Scientist (Alex)**:
The statistical intelligence agent who evaluates channel baselines, detects retention change points, analyzes CTR/traffic, designs experiments, and writes evidence-backed lessons into Channel Memory.
_Avoid_: Analytics Narrator, Reporting Bot, Dashboard Summarizer

**Editor (Leo)**:
The dialogue and narrative editing agent who performs semantic dialogue passes, cleans transcript/timeline segments, eliminates filler/dead air/redundancy, applies natural cut safety, reports batch edits, synthesizes Studio Voice audio, and renders the master video.
_Avoid_: Post-Production, Cutter, Video Processor

**Quality Control / QA (Iris)**:
The independent verification agent responsible for factual consistency, caption accuracy, audio loudness/sync, video continuity, and publishing readiness on the rendered output.
_Avoid_: Reviewer, Linter, Inspector, Fact Checker

---

### Channel Intelligence & Memory

**Channel Memory**:
Persistent long-term channel intelligence, creator preferences, and performance-derived lessons stored in Google Agent Platform Memory Bank and queried by production agents.
_Avoid_: Creator Memory, Context Window, Session State

**Channel Profile**:
Structured memory model capturing inferred channel niche, topics, audience characteristics, historical performance baselines, recurring retention patterns, and content pillars.
_Avoid_: Brand Summary, Channel Settings, Creator Bio

**Channel Lesson**:
An evidence-backed, falsifiable production directive stored in Channel Memory with an assigned target agent and confidence score.
_Avoid_: Rule, Guideline, Recommendation, Insight

**Channel Experiment**:
A structured hypothesis, treatment, baseline, and evaluation metric designed by Alex to test production variants and learn new lessons.
_Avoid_: A/B Test, Trial, Guess

**Evidence**:
Quantitative analytics (e.g. 30s retention %, CTR vs baseline) or factual media observations grounding a Lesson or QA finding.
_Avoid_: Metric, Data Point, Proof, Telemetry

**Channel Data Provider**:
The unified interface boundary for channel data, implemented via `YouTubeChannelDataProvider` (real Google YouTube APIs) and `SampleChannelDataProvider` (deterministic synthetic AI engineering dataset).
_Avoid_: Mock Data, Fake Provider, Hardcoded Fixtures

---

### Media, Timeline & Editing

**Timeline**:
The interactive multi-track representation in the browser (powered by Twick) visualizing video, audio tracks, cut intervals, playhead, and live agent annotations.
_Avoid_: Sequence, Composition, Track Layout

**Transcript**:
A word-level timestamped text representation of spoken dialogue synchronized with the video player and timeline, displaying real-time agent edit states (strike-through removals, review amber, preserved green).
_Avoid_: Subtitles, Script, Audio Text

**Edit Decision List (EDL)**:
The canonical, typed JSON specification defining cut intervals, actions (remove, preserve, reorder, cover), transitions, and media sources.
_Avoid_: Cut List, Project File, Render Manifest

**Dialogue Edit**:
A structured pass removing filler words, false starts, excessive pauses, repeated explanations, and weak preamble while preserving natural speech cadence.
_Avoid_: Silence Trimming, Auto-Cut, Speech Cleaning

**Natural Cut Safety**:
The deterministic verification pipeline ensuring audio cutpoints fall on natural speech boundaries, applying micro-crossfades, room-tone bridges, and visual screen coverage to prevent jarring jump cuts.
_Avoid_: Hard Cut, Blind Slice, Frame Chop

**Transition Strategy**:
The specific technique applied to smooth a cut (clean dialogue boundary, audio crossfade, room-tone bridge, J/L cut, screen B-roll coverage).
_Avoid_: Blend, Fade Effect

**Master**:
The full-length, high-resolution rendered video output produced deterministically by FFmpeg from the approved EDL.
_Avoid_: Final Video, Export, Rendered File


---

### Deterministic Engine & Governance

**Job**:
A bounded, executable unit of work within a Run owned by an Agent or the deterministic engine.
_Avoid_: Task, Step, Stage, Action

**Artifact**:
An immutable, versioned digital asset produced or consumed during a Run (source video, EDL, master render, Studio Voice narration, B-roll overlay, QA report).
_Avoid_: Output, File, Result, Asset

**Approval Gate**:
A deterministic pause in a Run where the engine requires explicit creator confirmation before executing external side effects (e.g. YouTube release).
_Avoid_: Checkpoint, Human Review, Pause Step

**Publisher**:
A deterministic service managed by the engine that executes authorized external mutations (such as uploading private YouTube releases) once QA passes and human approval is given.
_Avoid_: Publishing Agent, Uploader, Distribution Service

**QA Report**:
An immutable structured evaluation generated by Iris with one of four states: `PASS`, `REVISE`, `CREATOR_REQUIRED`, or `FAIL`.
_Avoid_: Test Result, Audit Log, Linter Output
