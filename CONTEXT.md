# Croviq

CI/CD for video creators: an autonomous, visible, and auditable production workflow that transforms raw footage into release-ready video.

## Language

**Workspace**:
The top-level tenant container representing a creator or production team, encapsulating brand kit, channel connections, persistent memory, and missions.
_Avoid_: Organization, Channel, Account, Tenant

**Mission**:
A single content production objective with creative intent and deliverables (e.g., turning raw recording into a release-ready YouTube video and derived assets).
_Avoid_: Project, Video, Episode, Campaign

**Workflow**:
A defined, reusable graph of jobs that orchestrates the transformation from raw input footage to verified release deliverables.
_Avoid_: Pipeline, DAG, Playbook, Recipe

**Run**:
A single, immutable execution instance of a Workflow for a Mission, producing an auditable sequence of job states, events, logs, and artifacts.
_Avoid_: Execution, Build, Job Run, Attempt

**Workflow Engine**:
The deterministic state machine that enforces job dependencies, state transitions, retry policies, idempotency, and approval gates.
_Avoid_: Orchestrator, Scheduler, Runner

**Director**:
The top-level coordinator agent that interprets creator intent, parameterizes department jobs, and routes context across the workflow within engine constraints.
_Avoid_: Master Agent, Manager, Orchestrator, Supervisor

**Department**:
A durable operational domain of responsibility within the creator studio with specialized agents, tools, and objectives.
_Avoid_: Module, Subsystem, Service, Plugin

**Editor**:
The department responsible for media analysis, timeline construction, video/audio transformations, silence removal, and cut decisions.
_Avoid_: Post-Production, Cutter, Video Processor

**Packaging**:
The department responsible for audience-facing presentation assets including title candidates, thumbnail concepts/generation, chapters, descriptions, and metadata.
_Avoid_: Marketing, Publisher, Metadata Generator

**QA**:
The department responsible for verifying release truthfulness, claim validation, technical integrity, caption synchronization, and compliance before human sign-off.
_Avoid_: Reviewer, Linter, Inspector, Fact Checker

**Research**:
The department responsible for pre-production topic discovery, audience demand signals, competitor benchmarking, and mission ideation.
_Avoid_: Ideation, Brainstorming, Search Agent

**Data Science / Growth**:
The department responsible for post-release performance analytics, retention curve diagnostics, CTR/traffic analysis, and updating Creator Memory with falsifiable production lessons.
_Avoid_: Analytics, Growth Hacking, Reporting

**Job**:
A bounded, executable unit of work inside a Run owned by a Department or the Workflow Engine (e.g. `understand_video`, `remove_excessive_silence`, `generate_titles`).
_Avoid_: Task, Step, Stage, Action

**Artifact**:
An immutable, versioned digital asset produced or consumed during a Run (e.g. source video, edit decision list, rendered master, thumbnail image, QA report).
_Avoid_: Output, File, Result, Asset

**Approval Gate**:
A deterministic pause in a Run where the Workflow Engine requires explicit human sign-off before proceeding to external side effects.
_Avoid_: Checkpoint, Human Review, Pause Step

**Publisher**:
A deterministic side-effect service managed by the Workflow Engine that executes authorized external mutations (e.g. YouTube upload) once QA passes and approval is given.
_Avoid_: Publishing Agent, Uploader, Distribution Service

**Creator Memory**:
Persistent cross-Mission intelligence, brand preferences, and performance-derived lessons stored at the Workspace level and applied to future Runs.
_Avoid_: Context Window, Long-term History, Session State


**Lesson**:
A structured, falsifiable production directive stored in Creator Memory (e.g. intro pacing, title framing) with an assigned target department and confidence score.
_Avoid_: Rule, Guideline, Recommendation, Insight

**Evidence**:
Quantitative analytics or factual media observations (e.g. retention percentage vs baseline, audio SNR) grounding a Lesson or QA verification.
_Avoid_: Metric, Data Point, Proof, Telemetry


**Timeline**:
The visual multi-track presentation in the browser representing media segments, audio tracks, cuts, captions, and agent annotations across playback time.
_Avoid_: Sequence, Composition, Track Layout

**Edit Decision List (EDL)**:
The canonical, typed JSON schema specifying media sources, cut intervals, transitions, caption alignments, and track operations.
_Avoid_: Cut List, Project File, Render Manifest

**Renderer**:
The deterministic backend engine (FFmpeg on Cloud Run) that executes an EDL against source media to generate output video/audio artifacts.
_Avoid_: Exporter, Compiler, Transcoder, Video Builder


**Transcript**:
A word-level timestamped text representation of the spoken dialogue in a Mission's video footage, synchronized with the Timeline.
_Avoid_: Subtitles, Script, Audio Text

**Dialogue Edit**:
A structured transformation removing fillers, false starts, excessive silence, and redundant takes while preserving natural speech cadence.
_Avoid_: Silence Trimming, Auto-Cut, Speech Cleaning

**Short**:
A standalone vertical (9:16) excerpt extracted from a Mission's primary video, packaged with burned-in captions for mobile viewing.
_Avoid_: Clip, Reel, Snippet, Highlight


**QA Report**:
An immutable structured assessment generated by QA verifying factual truthfulness, metadata alignment, timestamps, and compliance across Run artifacts.
_Avoid_: Test Result, Audit Log, Linter Output



