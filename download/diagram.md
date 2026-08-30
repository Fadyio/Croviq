# Croviq Production System Architecture

> **Architecture Status**: Active Production  
> **Cloud Provider**: Google Cloud Platform (`us-central1`)  
> **Authoritative Ingress**: `https://app.croviq.app` (Single-Origin Load Balancer)  
> **Visual Diagram Assets**:
> - High-Resolution PNG: `download/diagram.png`
> - Vector SVG: `download/diagram.svg`
> - Interactive Web Viewer: `download/diagram.html`

---

## 1. System Architecture Diagram

```mermaid
flowchart TB
    subgraph Clients["1. CREATOR WORKSTATION (FRONTEND SPA)"]
        User["👤 Creator / Video Editor<br/>Browser Client: https://app.croviq.app"]
        subgraph WebSPA["React 18 / Vite SPA (apps/web)"]
            Cockpit["🎬 Studio Cockpit (EditorPage.tsx)"]
            Timeline["📊 Timeline & Twick Sync (EditorTimeline.tsx)"]
            TranscriptUI["📝 Interactive Transcript (TranscriptPanel.tsx)"]
            AgentPresenceUI["🤖 Leo Presence (AgentPresence.tsx)"]
            InspectorUI["📋 Decision Inspector (DecisionInspector.tsx)"]
            MediaBinUI["🎙️ Studio Voice & B-Roll (MediaBin.tsx)"]
            StageUI["🎞️ Master & Short Stage (VideoStage.tsx)"]
            AuthUI["🔒 Firebase / ID Auth (AuthContext.tsx)"]
        end
        User --> WebSPA
    end

    subgraph Edge["2. GLOBAL EDGE & INGRESS TIER"]
        CF["☁️ Cloudflare DNS<br/>Authoritative DNS (A Record)"]
        IP["🌐 Global External Anycast IP<br/>croviq-app-ip (Static IPv4)"]
        CertMgr["🔐 Certificate Manager<br/>Google-Managed SSL (TLS 1.3)"]
        GLB["⚖️ Google Global Application LB<br/>External Managed (ADR-0013)"]
        URLMap["🗺️ URL Map (Single-Origin Routing)<br/>• croviq.app/* ➔ HTTP 308 Perm Redirect<br/>• app.croviq.app/* ➔ croviq-web (NEG)<br/>• app.croviq.app/api/* ➔ croviq-api (NEG)"]
        Armor["🛡️ Cloud Armor / Ingress Security<br/>Blocks direct *.run.app URLs"]
        WIF["🚀 GitHub Actions CI/CD<br/>Workload Identity Federation (WIF)"]
        
        CF --> IP --> GLB
        CertMgr -.-> GLB
        GLB --> URLMap
        Armor -.-> GLB
    end

    subgraph GCP["3. GOOGLE CLOUD REGION (us-central1)"]
        
        subgraph Compute["COMPUTE TIER — GOOGLE CLOUD RUN"]
            WebRun["🌐 croviq-web (Cloud Run)<br/>React/Vite SPA Container • Nginx<br/>SA: croviq-web-runtime • Port 8080"]
            ApiRun["⚡ croviq-api (Cloud Run)<br/>FastAPI / Python 3.12 Backend<br/>SA: croviq-api-runtime • Port 8080"]
            ObsExp["🪵 Observability Exporter<br/>Single-line JSON stdout"]
        end

        subgraph Agents["MULTI-AGENT REASONING LAYER (GOOGLE GenAI SDK / GEMINI 3.7 FLASH)"]
            Leo["✂️ Leo (Editor Agent)<br/>croviq_agents.editor<br/>• Dialogue Pass & Pacing<br/>• Redundancy & Filler Cleanup"]
            VoiceAgent["🎙️ Studio Voice Agent<br/>croviq_agents.voice<br/>• Iterative Duration-Fit Loop<br/>• Speech Synthesis Pacing"]
            DeptAgents["👥 Department Agents (Pydantic Models)<br/>• Alex: Data Scientist (Retention & Baselines)<br/>• Iris: QA Evaluator (Sync & Loudness)"]
        end

        subgraph MediaEngine["DETERMINISTIC MEDIA & AUDIO PIPELINE (FFMPEG & GEMINI TRANSCRIBE)"]
            Inspector["🔍 Media Inspector & Audio Extractor<br/>croviq_media.inspector / audio<br/>• FFprobe Metadata & Codecs<br/>• WAV Audio Extraction (16kHz PCM)"]
            Transcribe["📝 Transcription Service<br/>croviq_media.transcript<br/>• Word-Level Timestamp Anchors<br/>• Gemini 3.5 Transcribe Preview"]
            CutSafety["🛡️ Cut-Safety & EDL Assembler<br/>croviq_media.cut_safety<br/>• Audio Envelope & Syllable Padding<br/>• Micro-Crossfades (10–30ms)<br/>• Canonical EditDecisionList (JSON)"]
            Renderer["🎞️ FFmpeg Video Renderer<br/>croviq_media.render<br/>• Master 16:9 MP4 Render Engine<br/>• Vertical Short 9:16 Cropping<br/>• B-Roll Insertion & Captions"]
        end

        subgraph Data["DATA & PERSISTENCE TIER"]
            GCS["📦 Google Cloud Storage<br/>Bucket: croviq-media-raw<br/>• Raw Source Uploads (V4 Signed URLs)<br/>• Extracted WAV Audio Tracks<br/>• Rendered Master & Short MP4s<br/>• Private Access Prevention Enforced"]
            Firestore["🗄️ Cloud Firestore (Native Mode)<br/>• Workspaces & User Accounts<br/>• Productions & SourceMedia Metadata<br/>• Transcripts & Editorial Runs<br/>• Assembled EDLs & Render Artifacts"]
            MemoryBank["🧠 Google Agent Platform Memory Bank<br/>ID: croviq-channel-memory<br/>• ChannelProfile & Editorial Style<br/>• ChannelLessons & Evidence Log<br/>• ChannelExperiments (Zero Vector DB)"]
            Secrets["🔐 Identity Platform & Cloud KMS<br/>• Firebase Auth (Email/Password)<br/>• YouTube OAuth Envelope Encryption (Tink + KMS)"]
        end

        CloudLogging["📊 Google Cloud Logging<br/>Structured JSON Log Ingestion<br/>Unified Trace: request_id, job_id, user_id, model"]
    end

    %% Ingress connections
    WebSPA -->|DNS Lookup| CF
    WebSPA -->|HTTPS Traffic| GLB
    URLMap -->|/* Route| WebRun
    URLMap -->|/api/* Route| ApiRun

    %% Direct Upload connection
    WebSPA -.->|Direct V4 Signed PUT (No API Proxy)| GCS

    %% Internal API flows
    ApiRun --> Leo
    ApiRun --> VoiceAgent
    ApiRun --> DeptAgents
    Leo --> CutSafety
    
    ApiRun --> Inspector
    ApiRun --> Transcribe
    Inspector --> Transcribe
    Transcribe --> CutSafety
    CutSafety --> Renderer

    %% Storage connections
    ApiRun <--> Firestore
    ApiRun <--> GCS
    ApiRun <--> MemoryBank
    ApiRun <--> Secrets
    Renderer --> GCS
    Renderer --> Firestore

    %% Observability
    ApiRun --> ObsExp
    ObsExp --> CloudLogging
```

---

## 2. Core Architectural Principles

1. **Decoupled Architecture**: Clear division between the frontend workstation UI (`apps/web`), the multi-agent creative reasoning team (`packages/agents`), and the deterministic media processing engine (`packages/media`).
2. **Deterministic Engine vs. Creative Reasoning**: 
   - **Gemini 3.7 Flash** decides *what* to cut and *why* (semantic redundancy, false starts, filler words).
   - **Gemini 3.5 Transcribe Preview** provides *word-level timestamp anchors*.
   - **Deterministic Cut-Safety Pipeline** computes *where* cuts occur safely (audio envelope analysis, zero-crossing, syllable padding, micro-crossfades).
   - **FFmpeg on Cloud Run** *executes* the final `EditDecisionList` (EDL) deterministically against source media.
3. **Single-Origin Public Ingress (ADR-0013)**: Single public entrypoint at `https://app.croviq.app` managed by Google Global External Application Load Balancer. Single-origin routing eliminates cross-origin CORS overhead in production:
   - `https://app.croviq.app/*` ➔ `croviq-web` (React SPA)
   - `https://app.croviq.app/api/*` ➔ `croviq-api` (FastAPI backend)
   - `https://croviq.app/*` ➔ HTTP 308 permanent redirect to `https://app.croviq.app/*`
4. **Direct Media Ingestion**: Client uploads raw multi-gigabyte video files directly to Google Cloud Storage via V4 signed upload URLs generated by FastAPI. Source video bytes never proxy through Cloud Run container memory.
5. **Zero External Vector Databases**: Creator memory (`ChannelProfile`, `ChannelLesson`, `ChannelExperiment`) is stored directly in **Google Agent Platform Memory Bank** in `us-central1` (ADR-0015).
6. **Structured Observability**: Python structured logger outputs single-line JSON to `stdout`, automatically ingested by Google Cloud Logging with unified correlation fields (`request_id`, `user_id`, `run_id`, `job_id`, `model`, `latency_ms`).

---

## 3. Component Breakdown & Codebase Location Guide

### Tier 1: Ingress, Network & Infrastructure

| Component | Responsibility | Tech / Cloud Resource | Exact Codebase Path |
| :--- | :--- | :--- | :--- |
| **Authoritative DNS** | Routes `app.croviq.app` to GCP Static IP | Cloudflare DNS (DNS-only) | Managed via Cloudflare Dashboard |
| **Static Global IP** | Global anycast external IPv4 address | `google_compute_global_address.app_ip` | `infra/main.tf:690` |
| **SSL / TLS Certificates** | Google-managed SSL with DNS authorization | `google_certificate_manager_certificate` | `infra/main.tf:854-936` |
| **Global Load Balancer** | Target HTTPS Proxy & Global Forwarding Rule | `google_compute_global_forwarding_rule` | `infra/main.tf:939-998` |
| **URL Map & NEGs** | Path-based single-origin routing to Cloud Run | `google_compute_url_map.app` | `infra/main.tf:775-848` |
| **Security / Cloud Armor** | Restricts ingress to Load Balancer only | `google_cloud_run_v2_service` ingress settings | `infra/main.tf:302,593` |
| **CI/CD Deployment** | Automated GitHub Actions with OIDC WIF | Workload Identity Pool + Deployer SA | `infra/main.tf:92,256`, `.github/workflows/ci.yml` |

---

### Tier 2: Compute & Web Presentation Layer

#### 🌐 Frontend SPA (`apps/web`)

| Component | Role / Functionality | Exact File Path |
| :--- | :--- | :--- |
| **Editor Cockpit** | Master workspace state, media playback, agent loop coordination | `apps/web/src/pages/EditorPage.tsx` |
| **App & Workspaces** | Workspace selection, project dashboard, production listing | `apps/web/src/pages/AppPage.tsx` |
| **Authentication UI** | Firebase / Identity Platform email/password login & session | `apps/web/src/pages/LoginPage.tsx` |
| **Interactive Timeline** | Multi-track timeline visualizing raw clips, cuts, and transitions | `apps/web/src/components/editor/EditorTimeline.tsx` |
| **Interactive Transcript** | Word-synchronized transcript with playback seek and cut indicators | `apps/web/src/components/editor/TranscriptPanel.tsx` |
| **Video Preview Stage** | Master 16:9, Studio Voice, and Edited preview video player | `apps/web/src/components/editor/VideoStage.tsx` |
| **Agent Presence** | Real-time status card for Leo (Editor) | `apps/web/src/components/editor/AgentPresence.tsx` |
| **Decision Inspector** | Detailed audit drawer displaying cut reasons, timestamps, and confidence | `apps/web/src/components/editor/DecisionInspector.tsx` |
| **Media Bin & B-Roll** | Source footage management, B-roll overlays, Studio Voice trigger | `apps/web/src/components/editor/MediaBin.tsx` |
| **Agent Log Panel** | Real-time log stream showing active agent tasks, decisions, and reasoning | `apps/web/src/components/editor/AgentLogPanel.tsx` |
| **Agent Settings** | Personality, pacing aggressiveness, and voice style configuration | `apps/web/src/components/editor/AgentSettingsDrawer.tsx` |
| **Auth Context** | Global authentication state and JWT Bearer token management | `apps/web/src/auth/AuthContext.tsx` |
| **Generated API Client** | TypeScript API client generated from FastAPI OpenAPI contract | `apps/web/src/api/generated.ts` |
| **EDL Adapter** | Converts backend `EditDecisionList` to Twick/Timeline format | `apps/web/src/lib/edl-adapter.ts` |

#### ⚡ Backend API (`apps/api`)

| Route / Module | Role / Functionality | Exact File Path |
| :--- | :--- | :--- |
| **FastAPI App Root** | Application lifecycle, middleware, route registration, CORS config | `apps/api/src/croviq_api/main.py` |
| **Config & Settings** | Centralized environment variables, model IDs, bucket names, GCP project | `apps/api/src/croviq_api/config.py` |
| **Workspaces Routes** | Workspace CRUD, member access, agent configuration management | `apps/api/src/croviq_api/workspaces/routes.py` |
| **Productions Routes** | Complete production lifecycle endpoints (upload, transcribe, edit, render) | `apps/api/src/croviq_api/productions/routes.py` |
| **Editorial Service** | Coordinates Leo Editor dialogue and narrative editing | `apps/api/src/croviq_api/productions/editorial_service.py` |
| **EDL Service** | Assembles frame-safe, acoustic-safe Edit Decision Lists | `apps/api/src/croviq_api/productions/edl_service.py` |
| **Media Storage** | GCS V4 Signed URL generator and object verification adapter | `apps/api/src/croviq_api/media/storage.py`, `google.py` |
| **Memory Routes** | Creator memory profile, lessons, and experiments endpoints | `apps/api/src/croviq_api/memory/routes.py`, `google.py` |
| **Auth Verifier** | Firebase / Google Identity Platform JWT token validation | `apps/api/src/croviq_api/auth/verifier.py`, `dependencies.py` |

---

### Tier 3: Multi-Agent Reasoning Layer (`packages/agents` / `croviq_agents`)

| Agent / Module | Responsibility | Key Prompts / Schemas | Exact File Path |
| :--- | :--- | :--- | :--- |
| **Leo (Editor Agent)** | Identifies semantic redundancy, filler words, speech pauses | `EDITOR_DIALOGUE_PASS_PROMPT`<br/>`DialoguePassReport` | `packages/agents/src/croviq_agents/editor.py` |
| **Studio Voice Agent** | Generates synthesized voiceover with bounded duration-fit pacing loop | `StudioVoiceSynthesizer`<br/>`StudioVoiceResult` | `packages/agents/src/croviq_agents/voice.py` |
| **GenAI SDK Client** | Google GenAI SDK client wrapper with Vertex AI / Gemini API backend | Model: `gemini-3.7-flash`<br/>Location: `global` | `packages/agents/src/croviq_agents/client.py` |
| **Agent Prompts** | Canonical, battle-tested system prompts for Leo, Alex, and Iris | Typed prompt builders | `packages/agents/src/croviq_agents/prompts.py` |
| **Tool Registry & Sandbox** | Tool execution environment and terminal sandbox for agents | `AgentToolRegistry`<br/>`TerminalSandbox` | `packages/agents/src/croviq_agents/tools.py`, `terminal.py` |

---

### Tier 4: Deterministic Media & Audio Pipeline (`packages/media` / `croviq_media`)

| Component | Responsibility | Tools / Algorithms | Exact File Path |
| :--- | :--- | :--- | :--- |
| **Media Inspector** | Extracts container, video stream, and audio stream metadata | `ffprobe -v quiet -print_format json -show_format -show_streams` | `packages/media/src/croviq_media/inspector.py` |
| **Audio Extractor** | Demuxes pristine 16kHz mono PCM WAV audio from source video | `ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 output.wav` | `packages/media/src/croviq_media/audio.py` |
| **Transcription Service** | Canonical word-level speech-to-text transcription | **Gemini 3.5 Transcribe Preview** | `packages/media/src/croviq_media/transcript.py` |
| **Cut-Safety Pipeline** | Prevents syllable clipping via audio envelope & zero-crossing analysis | RMS envelope analysis, syllable padding, micro-crossfades (10–30ms) | `packages/media/src/croviq_media/cut_safety.py` |
| **Silence Detector** | Detects acoustic gaps, breaths, and natural pauses | Audio thresholding and energy contour mapping | `packages/media/src/croviq_media/silence.py` |
| **FFmpeg Renderer** | Deterministic multi-clip video concatenation and filter-graph rendering | `ffmpeg -filter_complex` with crossfades, overlays, and color normalization | `packages/media/src/croviq_media/render.py` |

---

### Tier 5: Canonical Domain Models (`packages/domain` / `croviq_domain`)

| Domain Model | Description & Contained Entities | Exact File Path |
| :--- | :--- | :--- |
| **`production.py`** | `Production`, `SourceMedia`, `ProductionStatus`, upload validation helpers | `packages/domain/src/croviq_domain/production.py` |
| **`editorial.py`** | `EditorialRun`, `DialoguePassReport`, `EditorialCut`, `CutReason`, `DirectorReviewDecision` | `packages/domain/src/croviq_domain/editorial.py` |
| **`edl.py`** | `EditDecisionList`, `EDLClip`, `EDLTransition`, `CaptionSegment`, `EDLMetadata` | `packages/domain/src/croviq_domain/edl.py` |
| **`render.py`** | `RenderArtifact`, `RenderJob`, `RenderType` (`MASTER_16_9`, `SHORT_9_16`), `ArtifactStatus` | `packages/domain/src/croviq_domain/render.py` |
| **`render_review.py`** | `RenderReview`, `ReviewVerdict` (`APPROVED`, `REVISE`), `QualityScores` | `packages/domain/src/croviq_domain/render_review.py` |
| **`transcript.py`** | `Transcript`, `TranscriptSegment`, `TranscriptWord` (word-level start/end/confidence) | `packages/domain/src/croviq_domain/transcript.py` |
| **`agent_config.py`** | `AgentConfig`, `PersonaSettings` (Leo, Alex, Iris prompt and voice settings) | `packages/domain/src/croviq_domain/agent_config.py` |
| **`narration.py`** | `NarrationSegment`, `StudioVoiceResult`, `BRollArtifact` | `packages/domain/src/croviq_domain/narration.py` |
| **`user.py`** | `User`, `Workspace`, `WorkspaceMembership`, `AuthPrincipal` | `packages/domain/src/croviq_domain/user.py` |

---

### Tier 6: Observability & Logging (`packages/observability` / `croviq_observability`)

| Module | Responsibility | Output Format & Destinations | Exact File Path |
| :--- | :--- | :--- | :--- |
| **Structured Logger** | Single-line JSON logger emitting structured event payloads to stdout | Cloud Run stdout ➔ Google Cloud Logging | `packages/observability/src/croviq_observability/logger.py` |
| **Event Types** | Strongly typed event catalog (`auth.*`, `media.*`, `ai.*`, `render.*`, `edl.*`) | Standardized `event_type` strings | `packages/observability/src/croviq_observability/events.py` |

---

## 4. End-to-End Execution Flow (The Production Lifecycle)

```
[1. Upload]
  Creator selects video in Web SPA
  ➔ POST /api/uploads (Request V4 Signed GCS URL)
  ➔ Web SPA uploads raw MP4 directly to GCS bucket (croviq-media-raw)
  ➔ POST /api/uploads/{upload_id}/complete (Verify GCS object)
  ➔ Firestore records SourceMedia(status=READY)

[2. Analyze & Transcribe]
  POST /api/productions/{id}/analyze
  ➔ Audio demuxed to 16kHz PCM WAV
  ➔ Gemini 3.5 Transcribe generates word-level timestamps
  ➔ Leo (Editor) analyzes transcript + video via Gemini 3.7 Flash
  ➔ CutSafetyPipeline applies zero-crossing padding & micro-crossfades
  ➔ Generates canonical EditDecisionList (EDL) JSON & Preview MP4

[3. Studio Voice & B-Roll]
  POST /api/productions/{id}/studio-voice (Synthesizes voiceover with duration-fit loop)
  ➔ POST /api/productions/{id}/broll/generate (Leo plans context-aware B-roll coverage)
  ➔ POST /api/productions/{id}/renders/final-mix (Assembles cuts, voiceover, and music)

[4. Deterministic FFmpeg Master Render]
  POST /api/productions/{id}/renders/master
  ➔ RenderService executes FFmpeg filtergraph from EDL
  ➔ Output 1080p Master MP4 stored in GCS media bucket
  ➔ Firestore records RenderArtifact(status=COMPLETED)

[5. Multimodal QA Verification & Release Review]
  POST /api/productions/{id}/release-review
  ➔ Iris verifies rendered video against sync and loudness benchmarks (-16 LUFS)
  ➔ GET /api/productions/{id}/playback (Returns signed GCS playback URLs to Web SPA)
```
---

## 5. Canonical Cloud Logging Filters for Agents & Engineers

When debugging in **Google Cloud Logs Explorer** (Project: `croviq-506602`), use these filter queries:

- **All API Logs**:
  ```text
  resource.type="cloud_run_revision"
  resource.labels.service_name="croviq-api"
  ```
- **Error & Failure Logs**:
  ```text
  resource.type="cloud_run_revision"
  resource.labels.service_name="croviq-api"
  (severity>=ERROR OR jsonPayload.status>=500)
  ```
- **Render Lifecycle Logs**:
  ```text
  resource.type="cloud_run_revision"
  resource.labels.service_name="croviq-api"
  (jsonPayload.event_type=~"^render\\." OR jsonPayload.route=~"/renders")
  ```
- **AI Agent Call Logs**:
  ```text
  resource.type="cloud_run_revision"
  resource.labels.service_name="croviq-api"
  jsonPayload.event_type=~"^ai\\.call\\."
  ```
- **Correlated Request Tracing**:
  ```text
  resource.type="cloud_run_revision"
  resource.labels.service_name="croviq-api"
  jsonPayload.request_id="<REQUEST_ID>"
  ```
