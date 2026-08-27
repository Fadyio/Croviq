/**
 * Auto-generated OpenAPI TypeScript contract interfaces for Croviq.
 * Generated from FastAPI OpenAPI 3.1 specification.
 *
 * DO NOT EDIT MANUALLY (ADR-0012: Python Pydantic v2 is the single source of truth).
 *
 * NOTE: Canonical domain models (User, Workspace, BrandKit) from packages/domain
 * will appear automatically in these contracts when real business endpoints are
 * attached in Milestone 2A (#15: /auth/me and #16: /workspaces).
 */

export interface paths {
  "/api/health": {
    get: {
      responses: {
        200: components["schemas"]["HealthResponse"];
      };
    };
  };
  "/api/client-events": {
    post: {
      responses: {
        200: unknown;
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/auth/me": {
    get: {
      responses: {
        200: components["schemas"]["User"];
      };
    };
  };
  "/api/auth/logout": {
    post: {
      responses: {
        200: unknown;
      };
    };
  };
  "/api/workspace": {
    get: {
      responses: {
        200: components["schemas"]["Workspace"];
      };
    };
  };
  "/api/workspace/agent-settings": {
    get: {
      responses: {
        200: components["schemas"]["AgentSettingsResponse"];
      };
    };
  };
  "/api/workspace/agent-settings/prompts/{agent_id}": {
    put: {
      responses: {
        200: components["schemas"]["AgentPromptConfig"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/workspace/agent-settings/prompts/{agent_id}/reset": {
    post: {
      responses: {
        200: components["schemas"]["AgentPromptConfig"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/workspace/agent-settings/memory": {
    get: {
      responses: {
        200: components["schemas"]["AgentMemorySummaryResponse"];
      };
    };
  };
  "/api/workspace/agent-settings/voice": {
    get: {
      responses: {
        200: components["schemas"]["VoiceSettingsConfig"];
      };
    };
    put: {
      responses: {
        200: components["schemas"]["VoiceSettingsConfig"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/workspace/agent-settings/voice/sample": {
    post: {
      responses: {
        200: components["schemas"]["VoiceSampleResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/channel/memory/profile": {
    get: {
      responses: {
        200: components["schemas"]["ChannelMemoryProfile"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/channel/memory/lessons": {
    get: {
      responses: {
        200: unknown;
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/uploads": {
    post: {
      responses: {
        201: components["schemas"]["CreateUploadResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/uploads/{upload_id}/complete": {
    post: {
      responses: {
        200: components["schemas"]["Production"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions": {
    get: {
      responses: {
        200: components["schemas"]["ProductionListResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}": {
    get: {
      responses: {
        200: components["schemas"]["Production"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/transcribe": {
    post: {
      responses: {
        200: components["schemas"]["TranscribeProductionResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/transcript": {
    get: {
      responses: {
        200: components["schemas"]["Transcript"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/source-analysis-input": {
    get: {
      responses: {
        200: components["schemas"]["SourceVideoAnalysisInput"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/analyze": {
    post: {
      responses: {
        200: components["schemas"]["AnalyzeProductionResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/editorial-run": {
    get: {
      responses: {
        200: components["schemas"]["EditorialRunDetailResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/edl": {
    post: {
      responses: {
        200: components["schemas"]["AssembleEDLResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
    get: {
      responses: {
        200: components["schemas"]["EDLDetailResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/renders/preview": {
    post: {
      responses: {
        200: components["schemas"]["RenderArtifactResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/renders/master": {
    post: {
      responses: {
        200: components["schemas"]["RenderArtifactResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/renders/short": {
    post: {
      responses: {
        200: components["schemas"]["RenderArtifactResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/renders": {
    get: {
      responses: {
        200: components["schemas"]["RenderListResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/review-preview": {
    post: {
      responses: {
        200: components["schemas"]["ReviewPreviewResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/render-review": {
    get: {
      responses: {
        200: components["schemas"]["RenderReviewDetailResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/render-reviews": {
    get: {
      responses: {
        200: components["schemas"]["RenderReviewDetailResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/playback": {
    get: {
      responses: {
        200: components["schemas"]["ProductionPlaybackResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/studio-voice": {
    post: {
      responses: {
        200: components["schemas"]["StudioVoiceGenerationResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
    get: {
      responses: {
        200: components["schemas"]["StudioVoiceResult"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/broll": {
    get: {
      responses: {
        200: components["schemas"]["BRollListResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
}

export interface components {
  schemas: {
    AgentActivity: {
      /** Unique identifier for the activity item */
      activity_id: string;
      /** Associated production identifier */
      production_id: string;
      /** Associated editorial run identifier */
      run_id: string;
      /** Agent name (e.g. Leo, Maya) */
      agent: string;
      /** Agent role (e.g. Video Editor, Director) */
      role: string;
      /** Activity category (e.g. proposal, review, note, decision) */
      activity_type: string;
      /** Clean product-facing message (no hidden chain-of-thought) */
      message: string;
      /** Referenced EditorDecision ID if applicable */
      related_decision_id?: string | null;
      /** Timestamp when the activity occurred */
      created_at?: string;
    };
    AgentId: "leo" | "maya";
    AgentMemorySummaryResponse: {
      channel_title: string;
      style_guide: string;
      creator_preferences?: string[];
      lessons?: components["schemas"]["MemoryItemResponse"][];
    };
    AgentPromptConfig: {
      /** Target agent identifier (leo or maya) */
      agent_id: components["schemas"]["AgentId"];
      /** Complete editorial working prompt text */
      prompt_text: string;
      /** Monotonically increasing version number */
      version?: number;
      /** Timestamp when the prompt was last updated */
      updated_at: string;
      /** Whether this prompt differs from system default */
      is_custom?: boolean;
    };
    AgentSettingsResponse: {
      leo_prompt: components["schemas"]["AgentPromptConfig"];
      maya_prompt: components["schemas"]["AgentPromptConfig"];
      voice_settings: components["schemas"]["VoiceSettingsConfig"];
      voices: components["schemas"]["VoiceCatalogItem"][];
    };
    AnalyzeProductionResponse: {
      /** Unique identifier for the editorial run */
      run_id: string;
      /** Associated production entity identifier */
      production_id: string;
      /** Operational status of the run */
      status: components["schemas"]["EditorialRunStatus"];
      /** Identifier of the generated EditorProposal record */
      editor_proposal_id?: string | null;
      /** Identifier of the generated DirectorReview record */
      director_review_id?: string | null;
      /** Run start timestamp in UTC */
      started_at: string;
      /** Run completion timestamp in UTC */
      completed_at?: string | null;
    };
    ArtifactStatus: "pending" | "rendering" | "completed" | "failed";
    ArtifactType: "PREVIEW" | "MASTER" | "SHORT" | "STUDIO_VOICE_PREVIEW" | "STUDIO_VOICE_MASTER";
    AssembleEDLResponse: {
      /** Unique identifier for the assembled Edit Decision List */
      edl_id: string;
      /** Associated Production entity identifier */
      production_id: string;
      /** Monotonically increasing version number for this production's EDL */
      version: number;
      /** Number of executable cut instructions (SAFE + NEEDS_COVERAGE) */
      cut_count: number;
      /** Number of visual coverage markers (B-roll + jump cut covers) */
      coverage_marker_count: number;
      /** Total duration of the source video in milliseconds */
      source_duration_ms: number;
      /** Total duration removed by safe cuts in milliseconds */
      total_removed_duration_ms: number;
      /** Estimated final master video duration in milliseconds */
      estimated_target_duration_ms: number;
      /** EDL readiness status for deterministic rendering */
      status?: string;
      /** Timestamp when the EDL was assembled in UTC */
      created_at: string;
    };
    AuthExplicitLogoutEvent: {
      firebase_uid?: string | null;
      git_sha?: string | null;
      event_type: "auth.explicit_logout";
    };
    AuthLoginAttemptEvent: {
      firebase_uid?: string | null;
      git_sha?: string | null;
      event_type: "auth.login_attempt";
    };
    AuthLoginFailedEvent: {
      firebase_uid?: string | null;
      git_sha?: string | null;
      event_type: "auth.login_failed";
      error_code?: "invalid_credentials" | "demo_access_restricted" | null;
    };
    AuthSessionLostEvent: {
      firebase_uid?: string | null;
      git_sha?: string | null;
      event_type: "auth.session_lost";
      error_code?: string | null;
    };
    AuthSessionRestoredEvent: {
      firebase_uid?: string | null;
      git_sha?: string | null;
      event_type: "auth.session.restored";
    };
    AuthTokenRefreshFailedEvent: {
      firebase_uid?: string | null;
      git_sha?: string | null;
      event_type: "auth.token_refresh_failed";
      error_code?: string | null;
    };
    AuthTokenRefreshedEvent: {
      firebase_uid?: string | null;
      git_sha?: string | null;
      event_type: "auth.token.refreshed";
    };
    BRollArtifact: {
      /** Unique artifact identifier */
      artifact_id: string;
      /** Associated production identifier */
      production_id: string;
      /** Optional associated editor decision id */
      decision_id?: string | null;
      /** Start time on source timeline in ms */
      source_start_ms: number;
      /** End time on source timeline in ms */
      source_end_ms: number;
      gcs_bucket: string;
      gcs_object: string;
      /** Target clip duration in ms (~2000-8000ms) */
      duration_ms: number;
      status?: components["schemas"]["BRollArtifactStatus"];
      /** Human summary of B-roll visual intent */
      prompt_summary?: string;
      created_at: string;
    };
    BRollArtifactStatus: "pending" | "accepted" | "rejected" | "failed";
    BRollListResponse: {
      /** Unique production identifier */
      production_id: string;
      /** List of generated B-roll clips */
      artifacts?: components["schemas"]["BRollArtifact"][];
    };
    BrandKit: {
      /** Tone adjectives or stylistic descriptors (e.g. ['concise', 'informative']) */
      tone?: string[];
      /** Description of the target audience and viewer demographic */
      target_audience?: string | null;
      /** Primary video content style or genre */
      content_style?: string | null;
      /** Custom production instructions and brand guidelines */
      custom_instructions?: string | null;
    };
    ChannelLesson: {
      /** Unique identifier for the lesson. */
      lesson_id: string;
      /** Channel identifier scope. */
      channel_id: string;
      /** Actionable instruction for the agent. */
      directive: string;
      /** Agent role this lesson directs (director, editor, packaging, qa). */
      target_agent: components["schemas"]["TargetAgent"];
      /** Statistical or qualitative summary of evidence supporting this directive. */
      evidence_summary: string;
      /** Confidence score for this lesson (0.0 to 1.0). */
      confidence: number;
      /** Lifecycle status of this lesson (active, deprecated, experimental). */
      status?: string;
      /** Timestamp when this lesson was recorded (UTC). */
      created_at?: string;
    };
    ChannelMemoryProfile: {
      /** Canonical channel identifier used as memory scope. */
      channel_id: string;
      /** Display name of the channel. */
      channel_name: string;
      /** Top subject-matter domains covered by the channel. */
      primary_topics?: string[];
      /** Core content themes and recurring series pillars. */
      content_pillars?: string[];
      /** Primary spoken and metadata language (ISO 639-1 code). */
      language?: string;
      /** Top audience geography ISO country codes ordered by viewership volume. */
      audience_geographies?: string[];
      /** Key audience behavioral and demographic attributes. */
      audience_characteristics?: string[];
      /** Baseline performance benchmarks (e.g. views, CTR, retention, duration). */
      historical_baselines?: Record<string, unknown>;
      /** Video formats demonstrating above-average performance. */
      high_performing_formats?: string[];
      /** Video formats demonstrating below-average performance. */
      weak_formats?: string[];
      /** Distilled retention observations from historical video performance. */
      recurring_retention_patterns?: string[];
      /** Distilled CTR and packaging observations (titles, topics, thumbnails). */
      packaging_patterns?: string[];
      /** Actionable editorial rules derived from channel evidence. */
      editorial_directives?: string[];
      /** Timestamp when this memory profile was generated or updated (UTC). */
      updated_at?: string;
    };
    ClientErrorEvent: {
      firebase_uid?: string | null;
      git_sha?: string | null;
      event_type: "client.error";
      error_code?: string | null;
      message?: string | null;
    };
    CoverageMarker: {
      /** Unique identifier for the coverage marker */
      marker_id: string;
      /** ID of the related editorial decision */
      decision_id: string;
      /** Start timestamp in source video milliseconds */
      source_start_ms: number;
      /** End timestamp in source video milliseconds */
      source_end_ms: number;
      /** Coverage category (e.g. SOURCE_SCREEN, BROLL_CANDIDATE) */
      coverage_type: components["schemas"]["CoverageType"];
      /** Editorial justification for the visual coverage */
      reason: string;
    };
    CoverageType: "SOURCE_SCREEN" | "BROLL_CANDIDATE";
    CreateUploadRequest: {
      /** Original name of the video file to upload */
      filename: string;
      /** MIME content type of the video file (e.g. video/mp4, video/quicktime, video/webm) */
      content_type: string;
      /** Declared size of the file in bytes (must be <= 1 GB) */
      size_bytes: number;
      /** Canonical channel identifier for this production (e.g. croviq_syn_ai_eng_01) */
      channel_id: string;
    };
    CreateUploadResponse: {
      /** Unique identifier of the created Production record */
      production_id: string;
      /** Unique identifier of the source media upload */
      upload_id: string;
      /** Pre-signed V4 Google Cloud Storage PUT URL for direct browser upload */
      upload_url: string;
      /** HTTP method to use when uploading media directly to storage */
      method?: string;
      /** Required HTTP headers (such as Content-Type) to send with the upload request */
      required_headers?: Record<string, unknown>;
      /** Timestamp when the pre-signed upload URL expires (UTC) */
      expires_at: string;
    };
    CutInstruction: {
      /** Unique identifier for the cut instruction */
      cut_id: string;
      /** Originating Editor/Director decision identifier */
      decision_id: string;
      /** Semantic decision type (e.g. REMOVE_FILLER, REMOVE_FALSE_START, etc.) */
      decision_type: components["schemas"]["EditorDecisionType"];
      /** 0-indexed start word boundary in canonical transcript */
      transcript_start_word: number;
      /** 0-indexed end word boundary in canonical transcript */
      transcript_end_word: number;
      /** Raw requested start timestamp from word anchor in ms */
      requested_start_ms: number;
      /** Raw requested end timestamp from word anchor in ms */
      requested_end_ms: number;
      /** Deterministic cut start timestamp snapped to inter-word silence in ms */
      safe_start_ms: number;
      /** Deterministic cut end timestamp snapped to inter-word silence in ms */
      safe_end_ms: number;
      /** Total duration removed by this cut in milliseconds */
      removed_duration_ms?: number;
      /** Spoken word or marker immediately preceding the cut boundary */
      left_anchor: string;
      /** Spoken word or marker immediately following the cut boundary */
      right_anchor: string;
      /** Micro-crossfade transition duration in milliseconds (canonical 20ms) */
      transition_ms?: number;
      /** Cut safety classification: SAFE, NEEDS_COVERAGE, or REJECTED_UNSAFE */
      safety_status: components["schemas"]["CutSafetyStatus"];
      /** Deterministic explanation for safety status determination */
      safety_reason: string;
      /** Confidence score for this cut instruction */
      confidence: number;
      /** Optional associated coverage marker ID when visual cut needs covering */
      coverage_marker_id?: string | null;
      /** Whether a room-tone bridge is recommended across the join */
      requires_room_tone?: boolean;
    };
    CutSafetyStatus: "SAFE" | "NEEDS_COVERAGE" | "REJECTED_UNSAFE";
    DirectorDecision: {
      /** ID of the EditorDecision being reviewed */
      editor_decision_id: string;
      /** Verdict: APPROVE, REJECT, or MODIFY */
      verdict: components["schemas"]["DirectorVerdict"];
      /** Short editorial reason for the verdict */
      concise_reason: string;
      /** Corrected action if verdict is MODIFY */
      modified_action?: string | null;
      /** Corrected start word index if verdict is MODIFY */
      modified_transcript_start_word?: number | null;
      /** Corrected end word index if verdict is MODIFY */
      modified_transcript_end_word?: number | null;
      /** Corrected start time in ms if verdict is MODIFY */
      modified_source_start_ms?: number | null;
      /** Corrected end time in ms if verdict is MODIFY */
      modified_source_end_ms?: number | null;
    };
    DirectorReview: {
      /** Associated Production entity identifier */
      production_id: string;
      /** Agent identifier */
      agent?: string;
      /** Model identifier used for review */
      model: string;
      /** Director's overall assessment of Leo's proposal */
      overall_assessment: string;
      /** Per-decision review verdicts */
      decisions?: components["schemas"]["DirectorDecision"][];
      /** Review verdicts on Leo's full-timeline section plan */
      section_decisions?: components["schemas"]["DirectorSectionDecision"][];
      /** Direct feedback to Leo for adjustments or approval */
      editor_feedback: string;
      /** Whether the proposal is approved to proceed to EDL assembly */
      approved_for_edl: boolean;
      /** Director's confidence in the review */
      confidence: number;
    };
    DirectorSectionDecision: {
      section_id: string;
      /** Verdict: APPROVE, REJECT, or MODIFY */
      verdict: components["schemas"]["DirectorVerdict"];
      reason: string;
    };
    DirectorVerdict: "APPROVE" | "REJECT" | "MODIFY";
    EDLDetailResponse: {
      /** Canonical EditDecisionList domain entity */
      edl: components["schemas"]["EditDecisionList"];
      /** Ordered list of contiguous (start_ms, end_ms) media intervals to KEEP for master video render */
      keep_segments: unknown[][];
    };
    EditDecisionList: {
      /** Unique identifier for the Edit Decision List */
      edl_id: string;
      /** Associated Production entity identifier */
      production_id: string;
      /** Total duration of the source media in milliseconds */
      source_duration_ms: number;
      /** Reference to the originating EditorProposal */
      editor_proposal_id?: string | null;
      /** Reference to the originating DirectorReview */
      director_review_id?: string | null;
      /** Monotonically increasing version number for this production's EDL */
      version?: number;
      /** Ordered list of deterministic cut instructions */
      cuts?: components["schemas"]["CutInstruction"][];
      /** Visual coverage markers for B-roll and screen recordings */
      coverage_markers?: components["schemas"]["CoverageMarker"][];
      /** Timestamp when the EDL was generated (UTC) */
      created_at: string;
    };
    EditorDecision: {
      /** Unique identifier for the decision within the proposal */
      decision_id: string;
      /** Semantic category of the editing decision */
      decision_type: components["schemas"]["EditorDecisionType"];
      /** Canonical 0-indexed transcript start word index */
      transcript_start_word: number;
      /** Canonical 0-indexed transcript end word index */
      transcript_end_word: number;
      /** Start time in milliseconds (derived from transcript timing) */
      source_start_ms: number;
      /** End time in milliseconds (derived from transcript timing) */
      source_end_ms: number;
      /** Exact spoken text corresponding to the word interval */
      original_text: string;
      /** Semantic action (e.g. remove, keep, trim, cover) */
      action: string;
      /** Short editorial rationale for the suggested action */
      concise_reason: string;
      /** Confidence score for this decision */
      confidence: number;
      /** Visual context on screen (e.g. talking head, terminal, slides) */
      visual_context?: string | null;
      /** Surrounding context that must be preserved */
      preserve_context?: string | null;
      /** Potential editorial or audio risk associated with the cut */
      risk?: string | null;
    };
    EditorDecisionType:
      | "KEEP"
      | "REMOVE_FILLER"
      | "REMOVE_FALSE_START"
      | "REMOVE_REPETITION"
      | "TRIM_PAUSE"
      | "TIGHTEN_EXPLANATION"
      | "KEEP_FOR_CLARITY"
      | "BROLL_COVER_CANDIDATE"
      | "SHORT_CANDIDATE";
    EditorProposal: {
      /** Associated Production entity identifier */
      production_id: string;
      /** Agent name identifier */
      agent?: string;
      /** Model identifier used for generation (e.g. gemini-3.7-flash) */
      model: string;
      /** High-level summary of dialogue pass findings and proposed improvements */
      summary: string;
      /** List of proposed editorial decisions */
      decisions?: components["schemas"]["EditorDecision"][];
      /** Optional Short candidate excerpt identified during analysis */
      short_candidate?: components["schemas"]["ShortCandidate"] | null;
      /** Full-timeline editorial section plan covering the whole production */
      section_plan?: components["schemas"]["VideoSectionDecision"][];
      /** Overall confidence in the proposal */
      overall_confidence: number;
    };
    EditorialRun: {
      /** Unique identifier for the editorial run */
      run_id: string;
      /** Associated production entity identifier */
      production_id: string;
      /** Current operational status of the run */
      status?: components["schemas"]["EditorialRunStatus"];
      /** Identifier of the generated EditorProposal record */
      editor_proposal_id?: string | null;
      /** Identifier of the generated DirectorReview record */
      director_review_id?: string | null;
      /** Run start timestamp in UTC */
      started_at?: string;
      /** Run completion timestamp in UTC */
      completed_at?: string | null;
      /** Sanitized failure code if run status is FAILED */
      failure_code?: string | null;
    };
    EditorialRunDetailResponse: {
      /** Operational record for the editorial run */
      run: components["schemas"]["EditorialRun"];
      /** Leo's structured dialogue proposal */
      proposal?: components["schemas"]["EditorProposal"] | null;
      /** Maya's structured director review */
      review?: components["schemas"]["DirectorReview"] | null;
      /** Product-facing agent activities generated during the run */
      activities?: components["schemas"]["AgentActivity"][];
    };
    EditorialRunStatus: "pending" | "analyzing" | "reviewing" | "completed" | "failed";
    HTTPValidationError: {
      detail?: components["schemas"]["ValidationError"][];
    };
    HealthResponse: {
      /** Service health status */
      status?: string;
      /** Service identifier */
      service?: string;
      /** Current git commit SHA or environment identifier */
      git_sha: string;
    };
    MediaMetadata: {
      /** Duration of the media in milliseconds */
      duration_ms: number;
      /** Video frame width in pixels (0 for audio-only) */
      width?: number;
      /** Video frame height in pixels (0 for audio-only) */
      height?: number;
      /** Video frame rate in frames per second (0.0 for audio-only) */
      frame_rate?: number;
      /** Video codec name (e.g. 'h264', 'hevc', 'vp9', or 'none') */
      video_codec?: string;
      /** Audio codec name (e.g. 'aac', 'opus', 'pcm_s16le') */
      audio_codec?: string | null;
      /** Audio sample rate in Hertz (e.g. 48000, 44100, 16000) */
      audio_sample_rate?: number | null;
      /** Audio channel count (e.g. 1 for mono, 2 for stereo) */
      audio_channels?: number | null;
      /** Video orientation rotation in degrees (0, 90, 180, 270) */
      rotation?: number;
      /** Total media file size in bytes */
      size_bytes: number;
    };
    MemoryItemResponse: {
      topic: string;
      content: string;
      learned_from?: string | null;
    };
    NarrationMode: "original" | "enhanced_original" | "studio_voice";
    NarrationSegment: {
      /** Unique segment identifier */
      segment_id: string;
      /** Associated production identifier */
      production_id: string;
      /** Start timestamp on source timeline in ms */
      source_start_ms: number;
      /** End timestamp on source timeline in ms */
      source_end_ms: number;
      /** Strict maximum duration budget in ms */
      available_duration_ms: number;
      /** Original spoken transcript text */
      original_text: string;
      /** Leo's editorial rewritten text */
      rewritten_text: string;
      /** Selected Studio Voice identifier */
      voice_id: string;
      /** Actual measured TTS audio duration in ms */
      generated_duration_ms?: number;
      status?: components["schemas"]["NarrationSegmentStatus"];
      /** GCS object or storage key */
      audio_artifact_reference?: string | null;
      /** Number of TTS synthesis/rewrite attempts */
      attempts?: number;
      /** Applied tempo multiplier (max 3-5%) */
      tempo_adjustment?: number;
    };
    NarrationSegmentStatus: "pending" | "accepted" | "rejected" | "failed";
    Production: {
      /** Unique production identifier */
      production_id: string;
      /** Workspace tenant identifier */
      workspace_id: string;
      /** Associated YouTube or Sample Channel identifier */
      channel_id: string;
      /** Identifier of the user who owns this production */
      owner_user_id: string;
      /** Raw source media metadata associated with this production */
      source_media?: components["schemas"]["SourceMedia"] | null;
      /** Current production status */
      status?: components["schemas"]["ProductionStatus"];
      /** Timestamp when the production was created (UTC) */
      created_at: string;
      /** Timestamp when the production was last updated (UTC) */
      updated_at: string;
    };
    ProductionListResponse: {
      /** List of recent Production records */
      productions?: components["schemas"]["Production"][];
      /** Total number of productions returned */
      total: number;
    };
    ProductionPlaybackResponse: {
      /** Unique production identifier */
      production_id: string;
      /** Original source media playback URL */
      playback_url?: string | null;
      /** Expiration timestamp for signed URLs */
      expires_at?: string | null;
      /** Edited preview video playback URL */
      rendered_preview_url?: string | null;
      /** Master video playback URL */
      master_url?: string | null;
      /** Studio Voice video playback URL */
      studio_voice_preview_url?: string | null;
      /** Social Short video playback URL */
      short_playback_url?: string | null;
    };
    ProductionStatus: "pending" | "uploading" | "uploaded" | "failed";
    RenderArtifactResponse: {
      /** Canonical unique render artifact identifier */
      artifact_id: string;
      /** Identifier of the associated production */
      production_id: string;
      /** Identifier of the source Edit Decision List */
      edl_id: string;
      /** Type of rendered artifact: PREVIEW or MASTER */
      artifact_type: components["schemas"]["ArtifactType"];
      /** Lifecycle status: pending, rendering, completed, failed */
      status: components["schemas"]["ArtifactStatus"];
      /** MIME content type of the rendered media file */
      content_type?: string;
      /** Verified file size in bytes */
      size_bytes?: number | null;
      /** Verified media duration in milliseconds */
      duration_ms?: number | null;
      /** Video stream width in pixels */
      width?: number | null;
      /** Video stream height in pixels */
      height?: number | null;
      /** Video stream frame rate (fps) */
      frame_rate?: number | null;
      /** Video codec name (e.g. h264) */
      video_codec?: string | null;
      /** Audio codec name (e.g. aac) */
      audio_codec?: string | null;
      /** Short-lived keyless signed GET URL for browser video playback if completed */
      playback_url?: string | null;
      /** UTC expiration timestamp of the signed playback URL if available */
      playback_expires_at?: string | null;
      /** Timestamp when the render record was initialized in UTC */
      created_at: string;
      /** Timestamp when rendering completed in UTC */
      completed_at?: string | null;
      /** Error code or failure reason if render failed */
      failure_code?: string | null;
    };
    RenderListResponse: {
      /** Canonical unique production identifier */
      production_id: string;
      /** List of all render artifacts associated with the production */
      renders: components["schemas"]["RenderArtifactResponse"][];
    };
    RenderReview: {
      /** Unique identifier for the post-render review record */
      review_id: string;
      /** Associated Production entity identifier */
      production_id: string;
      /** Associated EDL identifier that produced the preview */
      edl_id: string;
      /** Associated RenderArtifact identifier of the rendered preview */
      preview_artifact_id: string;
      /** Agent identifier (Maya) */
      agent?: string;
      /** Model identifier used for the post-render evaluation */
      model: string;
      /** Post-render verdict: APPROVE or CORRECT */
      verdict: components["schemas"]["RenderReviewVerdict"];
      /** Concise product-facing summary of the post-render review */
      summary: string;
      /** List of specific issues identified in the rendered preview */
      issues?: components["schemas"]["RenderReviewIssue"][];
      /** Whether the preview is approved to proceed to deterministic Master render */
      approved_for_master: boolean;
      /** Director's confidence in the review */
      confidence: number;
      /** Creation timestamp in UTC */
      created_at?: string;
    };
    RenderReviewDetailResponse: {
      /** Canonical unique production identifier */
      production_id: string;
      /** Most recent post-render review record */
      review?: components["schemas"]["RenderReview"] | null;
      /** All post-render review records for this production */
      reviews?: components["schemas"]["RenderReview"][];
      /** Whether production requires manual human review after exhausted bounded correction */
      needs_manual_review?: boolean;
    };
    RenderReviewIssue: {
      /** Unique identifier for the review issue */
      issue_id: string;
      /** Categorized issue type */
      issue_type: components["schemas"]["RenderReviewIssueType"];
      /** Start time of the affected region in source media milliseconds */
      source_start_ms: number;
      /** End time of the affected region in source media milliseconds */
      source_end_ms: number;
      /** Referenced EditorDecision ID if directly tied to an existing decision */
      related_decision_id?: string | null;
      /** Severity level of the issue (LOW, MEDIUM, HIGH) */
      severity: components["schemas"]["RenderReviewSeverity"];
      /** Concise product-facing explanation of the issue (no raw chain-of-thought) */
      message: string;
      /** Suggested editorial correction to resolve the issue */
      suggested_action: string;
    };
    RenderReviewIssueType:
      | "UNNATURAL_AUDIO_JOIN"
      | "VISUAL_JUMP"
      | "OVER_AGGRESSIVE_CUT"
      | "MISSED_EDIT"
      | "CONTEXT_LOSS"
      | "PACING"
      | "COVERAGE_NEEDED";
    RenderReviewSeverity: "LOW" | "MEDIUM" | "HIGH";
    RenderReviewVerdict: "APPROVE" | "CORRECT";
    ReviewPreviewResponse: {
      /** Canonical unique production identifier */
      production_id: string;
      /** Maya's post-render review record */
      review: components["schemas"]["RenderReview"];
      /** Master render artifact if approved and rendered */
      master_artifact?: components["schemas"]["RenderArtifactResponse"] | null;
      /** Second post-render review if bounded correction was performed */
      second_review?: components["schemas"]["RenderReview"] | null;
      /** Current workflow status (complete, needs_manual_review, correcting, approved) */
      status: string;
      /** Product-facing agent activity messages emitted during review and correction */
      activities?: components["schemas"]["AgentActivity"][];
    };
    SectionAction: "KEEP" | "TIGHTEN" | "REMOVE" | "COVERAGE";
    ShortCandidate: {
      /** Start timestamp in source video milliseconds */
      start_ms: number;
      /** End timestamp in source video milliseconds */
      end_ms: number;
      /** Canonical 0-indexed transcript word start boundary */
      transcript_start_word: number;
      /** Canonical 0-indexed transcript word end boundary */
      transcript_end_word: number;
      /** Short hook / title proposition */
      hook_title: string;
      /** Editorial justification for why this segment works as a standalone Short */
      concise_reason: string;
      /** Model confidence score for the candidate excerpt */
      confidence: number;
      /** Optional visual focus regions for 9:16 reframe */
      visual_plan?: components["schemas"]["ShortVisualPlan"] | null;
    };
    ShortVisualPlan: {
      /** List of chronological visual focus regions for the Short */
      regions?: components["schemas"]["ShortVisualRegion"][];
    };
    ShortVisualRegion: {
      /** Start timestamp in ms relative to Short timeline */
      start_ms: number;
      /** End timestamp in ms relative to Short timeline */
      end_ms: number;
      /** Normalized x coordinate (0.0 to 1.0) of crop top-left in source frame */
      x: number;
      /** Normalized y coordinate (0.0 to 1.0) of crop top-left in source frame */
      y: number;
      /** Normalized width (0.0 to 1.0) of focus region */
      width: number;
      /** Normalized height (0.0 to 1.0) of focus region */
      height: number;
      /** Optional zoom factor */
      zoom?: number;
      /** Visual description of focus area (e.g. YAML editor, status) */
      focus_label: string;
    };
    SilenceInterval: {
      /** Silence interval start offset in milliseconds */
      start_ms: number;
      /** Silence interval end offset in milliseconds */
      end_ms: number;
      /** Silence interval duration in milliseconds */
      duration_ms: number;
    };
    SourceMedia: {
      /** Unique upload identifier */
      upload_id: string;
      /** Original user-provided filename */
      original_filename: string;
      /** MIME content type of the media file */
      content_type: string;
      /** Declared or verified size of the media file in bytes */
      size_bytes: number;
      /** Target Google Cloud Storage bucket name */
      gcs_bucket: string;
      /** Target Google Cloud Storage object path */
      gcs_object: string;
      /** Upload lifecycle status */
      status?: components["schemas"]["SourceMediaStatus"];
      /** Timestamp when the upload record was created (UTC) */
      created_at: string;
      /** Timestamp when the media upload was verified and completed (UTC) */
      uploaded_at?: string | null;
    };
    SourceMediaStatus: "pending" | "uploading" | "uploaded" | "failed";
    SourceVideoAnalysisInput: {
      /** Associated Production entity identifier */
      production_id: string;
      /** Source media upload metadata and GCS reference */
      source_media: components["schemas"]["SourceMedia"];
      /** Deterministic FFprobe media technical parameters */
      media_metadata: components["schemas"]["MediaMetadata"];
      /** Word-aligned transcript with millisecond timestamps */
      transcript: components["schemas"]["Transcript"];
      /** Associated channel identifier */
      channel_id: string;
      /** Reference identifier to ChannelMemoryProfile in Memory Bank */
      channel_memory_reference?: string | null;
    };
    StudioVoiceGenerationResponse: {
      /** Unique production identifier */
      production_id: string;
      /** Aggregated Studio Voice result and segment details */
      result: components["schemas"]["StudioVoiceResult"];
      /** Signed playback URL for Studio Voice preview */
      studio_voice_preview_url?: string | null;
    };
    StudioVoiceResult: {
      production_id: string;
      voice_id: string;
      narration_mode?: string;
      segments?: components["schemas"]["NarrationSegment"][];
      total_segments?: number;
      accepted_segments?: number;
      all_within_budget?: boolean;
      gcs_bucket?: string | null;
      gcs_object?: string | null;
      status?: string;
      created_at: string;
      updated_at: string;
    };
    TargetAgent: "director" | "editor" | "packaging" | "qa";
    TranscribeProductionResponse: {
      /** Transcription status ('completed' or 'already_transcribed') */
      status: "completed" | "already_transcribed";
      /** Unique identifier of the generated or retrieved transcript */
      transcript_id: string;
      /** Identifier of the associated Production */
      production_id: string;
      /** Total duration of the transcript in milliseconds */
      duration_ms: number;
      /** Total number of word tokens in the transcript */
      word_count: number;
      /** Total number of phrase segments in the transcript */
      segment_count: number;
      /** Language code used for transcription */
      language_code: string;
      /** Full word-aligned transcript object */
      transcript: components["schemas"]["Transcript"];
    };
    Transcript: {
      /** Unique identifier for the transcript entity */
      transcript_id: string;
      /** Identifier of the associated Production record */
      production_id: string;
      /** Language tag of the transcription (e.g. 'en-US' or 'en') */
      language_code: string;
      /** Total duration of the audio/speech stream in milliseconds */
      duration_ms: number;
      /** Ordered list of word-level timestamped tokens */
      words?: components["schemas"]["TranscriptWord"][];
      /** Ordered list of sentence/phrase segments */
      segments?: components["schemas"]["TranscriptSegment"][];
      /** Identified inter-word silence intervals */
      silence_intervals?: components["schemas"]["SilenceInterval"][];
      /** Timestamp when the transcript was generated (UTC) */
      created_at: string;
    };
    TranscriptSegment: {
      /** Unique identifier for this segment */
      segment_id: string;
      /** Start offset of the segment in milliseconds */
      start_ms: number;
      /** End offset of the segment in milliseconds */
      end_ms: number;
      /** Aggregated text content of the segment */
      text: string;
      /** Inclusive start index in the transcript words list */
      word_start_index: number;
      /** Inclusive end index in the transcript words list */
      word_end_index: number;
    };
    TranscriptWord: {
      /** Zero-based sequential index of the word in the transcript */
      index: number;
      /** Spoken text of the word */
      text: string;
      /** Start offset from beginning of audio stream in milliseconds */
      start_ms: number;
      /** End offset from beginning of audio stream in milliseconds */
      end_ms: number;
      /** Confidence score from speech recognizer (0.0 to 1.0) */
      confidence?: number | null;
      /** Optional speaker identifier or diarization tag */
      speaker_id?: string | null;
    };
    UpdatePromptRequest: {
      /** Updated editorial working prompt */
      prompt_text: string;
    };
    UpdateVoiceSettingsRequest: {
      /** Selected narration mode */
      narration_mode: components["schemas"]["NarrationMode"];
      selected_voice?: string;
      language?: string;
    };
    User: {
      /** Unique user identifier (e.g. Firebase UID / Google sub) */
      user_id: string;
      /** Canonical user email address */
      email: string;
      /** User display name */
      display_name: string;
      /** Profile avatar image URL */
      avatar_url?: string | null;
      /** Timestamp when the user was created (UTC) */
      created_at: string;
      /** Timestamp when the user was last updated (UTC) */
      updated_at: string;
    };
    ValidationError: {
      loc: string | number[];
      msg: string;
      type: string;
      input?: unknown;
      ctx?: Record<string, unknown>;
    };
    VideoSectionDecision: {
      /** Unique identifier for the timeline section */
      section_id: string;
      /** Start time in milliseconds on the source video timeline */
      source_start_ms: number;
      /** End time in milliseconds on the source video timeline */
      source_end_ms: number;
      /** Canonical 0-indexed transcript start word index */
      transcript_start_word: number;
      /** Canonical 0-indexed transcript end word index */
      transcript_end_word: number;
      /** Editorial action: KEEP, TIGHTEN, REMOVE, or COVERAGE */
      action: components["schemas"]["SectionAction"];
      /** Editorial justification for why this section is kept, tightened, or removed */
      reason: string;
      /** Model confidence score for this section decision */
      confidence: number;
    };
    VoiceCatalogItem: {
      /** Voice identifier */
      voice_id: string;
      /** Human readable voice name */
      display_name: string;
      /** Voice characteristic (female, male, neutral) */
      gender?: string;
      /** Primary BCP-47 language code */
      language_code?: string;
      /** Brief tone or style description */
      description?: string | null;
    };
    VoiceSampleRequest: {
      /** Voice identifier to sample */
      voice_id: string;
      /** Neutral fixed sample script */
      sample_text?: string;
    };
    VoiceSampleResponse: {
      voice_id: string;
      sample_text: string;
      /** Base64-encoded audio payload */
      audio_base64: string;
      content_type?: string;
    };
    VoiceSettingsConfig: {
      /** Selected narration playback mode */
      narration_mode?: components["schemas"]["NarrationMode"];
      /** Selected Studio Voice catalog voice identifier (Gemini TTS prebuilt voice) */
      selected_voice?: string;
      /** Language code for synthesis */
      language?: string;
      /** Timestamp when settings were updated */
      updated_at: string;
    };
    Workspace: {
      /** Unique workspace identifier */
      workspace_id: string;
      /** Identifier of the user who owns this workspace */
      owner_user_id: string;
      /** Workspace / channel display name */
      name: string;
      /** Description of the YouTube channel or production context */
      channel_description?: string | null;
      /** Workspace brand kit configuration */
      brand_kit?: components["schemas"]["BrandKit"];
      /** Timestamp when the workspace was created (UTC) */
      created_at: string;
      /** Timestamp when the workspace was last updated (UTC) */
      updated_at: string;
    };
  };
}
