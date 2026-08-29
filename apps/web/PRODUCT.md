# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Primary Users**: Technical, educational, and independent YouTube video creators (software engineers, tutorial creators, technical educators) producing long-form video content from screencasts, talking-head takes, and live demonstrations.
- **Situation & Job**: Creators spend hours manually reviewing raw multi-take footage, cutting out filler words ("um", "so basically"), eliminating dead air, removing false starts, and tightening pacing. They want to upload raw takes and have an autonomous, visible production team handle dialogue editing, timeline assembly, natural cut safety, Shorts extraction, and channel retention optimization while retaining final editorial control and approval over all external releases.

## Product Purpose

Croviq is "DevOps for YouTube Creators": an autonomous, visible production workstation that transforms raw footage into release-ready video masters and derived vertical Shorts. It replaces manual post-production cutting with a collaborative AI team that reasons about narrative flow, enforces broadcast-grade cut safety, evaluates retention metrics, and accumulates long-term channel wisdom across successive productions.

## Positioning

Unlike generic auto-cutters, silence-strippers, or opaque black-box video generators:
- **Visible Autonomous Production Team**: Implemented visible team (Alex as Data Scientist, Leo as Video Editor, Iris as Quality Control) with distinct operational roles, explicit reasoning logs, and observable handoffs.
- **Deterministic Non-Destructive Editing**: All edits compile into typed Edit Decision Lists (EDLs) previewed via interactive multi-track timelines (Twick) and synchronized transcript overlays, rendered deterministically with FFmpeg.
- **Natural Cut Safety**: Automatic speech boundary detection, micro-crossfades, room-tone bridging, and screen coverage markers to eliminate jarring jump cuts.
- **Long-Term Channel Memory**: Falsifiable production lessons and retention change points stored in Google Agent Platform Memory Bank that dynamically guide future edits.
- **Human-in-the-Loop Governance**: Strict approval gates before any external side effects (e.g., YouTube publishing).

## Operating Context

- **Primary Interface**: High-density creative workstation browser application (`apps/web`) operating on desktop viewports.
- **Workflow Lifecycle**:
  1. *Sign In & Tenancy*: Email & Password auth via Firebase Authentication; studio workspace context.
  2. *Channel Selection & Ingestion*: Connect YouTube Channel (incremental OAuth) or select deterministic sample channel (`croviq_syn_ai_eng_01`); drag-and-drop raw video upload directly to GCS via signed URLs.
  3. *Production & Editorial Review*: 80/20 workspace split—video player canvas + Twick multi-track timeline on the left; active agent activity card + real-time synchronized transcript with strikethrough/amber/green states on the right.
  4. *Master Render & Derivative Export*: Full-length Master video and vertical (9:16) Shorts with burned-in captions.
  5. *Approval & Release*: Creator inspection and explicit sign-off at the Human Approval Gate before publishing.

## Capabilities and Constraints

- **Confirmed Capabilities**:
  - Direct resumable GCS video uploads up to 1GB per production.
  - Word-level timestamped transcript synchronization with bidirectional timeline seeking.
  - Visual transcript styling for semantic edit states (removed red strikethrough, suggested amber underline, preserved green tint, active blue processing).
  - Multi-track timeline (Video V1, Audio A1, Annotation TX) powered by `@twick/timeline`.
  - Live agent decision inspection (Leo's dialogue decisions, Alex's retention metrics, Iris's QA compliance report).
  - Fast preview toggle (Raw vs Edited EDL playback).
- **Technical Stack & Constraints**:
  - Frontend: React 19, TypeScript, Vite, Tailwind CSS, Motion for React (`motion/react`), Lucide icons.
  - Backend: Python 3.12, FastAPI, Pydantic v2 on Google Cloud Run.
  - Storage & Media: Google Cloud Storage (GCS), Firestore Native Mode, FFmpeg deterministic render pipelines.
  - Reasoning & Memory: Gemini 3.7 Flash via Google GenAI SDK, Google Agent Platform Memory Bank.
  - Domain Language: Strictly follow `CONTEXT.md` terms (`Workspace`, `Production`, `Run`, `Editor (Leo)`, `Data Scientist (Alex)`, `QA (Iris)`, `Timeline`, `Transcript`, `Edit Decision List (EDL)`, `Master`, `Short`, `Approval Gate`).
## Brand Commitments

- **Brand Name**: Croviq
- **Design Philosophy**: Professional Creative Media Workstation combining the density of Premiere/DaVinci, layout precision of Linear, and polish of Raycast.
- **Golden Rule**: Media is the most colorful element on screen; UI surfaces recede into neutral deep graphite (`#101214` base, `#16191C` / `#1C2024` panels).
- **Logos & Assets**: `brandkit/croviq-logo-horizontal.svg` (primary top bar), `brandkit/croviq-symbol.svg` (emblem/favicon), `brandkit/croviq-logo-stacked.svg` (sign-in screen).
- **Team Personas**:
  - Alex (`TrendingUp`): Statistical Intelligence & Data Scientist
  - Leo (`Scissors`): Video Editor
  - Iris (`ShieldCheck`): Quality Assurance & Compliance
## Evidence on Hand

- Deterministic synthetic sample channel (`croviq_syn_ai_eng_01`) with ~50k subscribers, 100 historical videos, and 18 months of realistic analytics curves (retention drops, CTR baselines).
- Real brandkit SVGs (`brandkit/croviq-logo-horizontal.svg`, `brandkit/croviq-symbol.svg`, `brandkit/croviq-logo-stacked.svg`, etc.).
- Complete typed API contracts (`apps/web/src/api/generated.ts`).
- Working frontend components with Twick timeline adapter, video stage, transcript panel, and decision inspector.
- Verified test suites and Playwright E2E specs.

## Product Principles

- **Media is the Hero**: Application chrome must be neutral, low-contrast, and quiet so creators can focus on footage without visual distraction or false color perception.
- **Visible, Accountable Intelligence**: AI agents must never act as opaque black boxes; every cut, suggestion, and retention hypothesis must display author attribution and falsifiable reasoning.
- **Deterministic & Non-Destructive**: Edits exist as transparent data structures (EDLs) that can be inspected, scrubbed, adjusted, and previewed before committing to immutable renders.
- **Frictionless Density over Decorative White Space**: Maximize information efficiency, keyboard ergonomics, and timeline precision over generic consumer padding.
- **Respect Creator Agency**: External distribution, publishing, and irreversible operations always pause at deterministic human approval gates.

## Accessibility & Inclusion

- Support `@media (prefers-reduced-motion: reduce)` across all Motion transitions.
- High-contrast transcript text (`#F2F4F5`) and distinct color + text styling (strikethrough, brackets, icons) so semantic states do not rely solely on color.
- Keyboard navigation and standard hotkeys for timeline playback (Space for Play/Pause, J/K/L scrubbing).
