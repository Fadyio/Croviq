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
    delete: {
      responses: {
        200: components["schemas"]["DeleteProductionResponse"];
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
  "/api/productions/{production_id}/package": {
    post: {
      responses: {
        200: components["schemas"]["PackagingDetailResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/packaging": {
    get: {
      responses: {
        200: components["schemas"]["PackagingDetailResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
    patch: {
      responses: {
        200: components["schemas"]["PackagingDetailResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/release-review": {
    post: {
      responses: {
        200: components["schemas"]["ReleaseReviewDetailResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
    get: {
      responses: {
        200: components["schemas"]["ReleaseReviewDetailResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/release-review/correct": {
    post: {
      responses: {
        200: components["schemas"]["AutoCorrectQAResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/publish/prep": {
    get: {
      responses: {
        200: components["schemas"]["PublishPreparationResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/publish": {
    post: {
      responses: {
        200: components["schemas"]["PublishJobDetailResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
    get: {
      responses: {
        200: components["schemas"]["PublishJobDetailResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/productions/{production_id}/publish/cancel": {
    post: {
      responses: {
        200: components["schemas"]["PublishJobDetailResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/channels/sample/dashboard": {
    get: {
      responses: {
        200: components["schemas"]["ChannelDashboard"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/channels/youtube/auth-url": {
    post: {
      responses: {
        200: components["schemas"]["YouTubeAuthUrlResponse"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/channels/youtube/callback": {
    post: {
      responses: {
        200: components["schemas"]["YouTubeConnectionPublicSummary"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/channels/youtube/connection": {
    get: {
      responses: {
        200: components["schemas"]["YouTubeConnectionPublicSummary"];
      };
    };
  };
  "/api/channels/youtube/disconnect": {
    post: {
      responses: {
        204: unknown;
      };
    };
  };
  "/api/channels/youtube/dashboard": {
    get: {
      responses: {
        200: components["schemas"]["ChannelDashboard"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/channels/research/config": {
    get: {
      responses: {
        200: components["schemas"]["ResearchConfig"];
      };
    };
    put: {
      responses: {
        200: components["schemas"]["ResearchConfig"];
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/channels/research/findings": {
    get: {
      responses: {
        200: unknown;
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/channels/research/run": {
    post: {
      responses: {
        200: unknown;
      };
    };
  };
  "/api/channels/research/tick": {
    post: {
      responses: {
        200: components["schemas"]["SchedulerTickResponse"];
      };
    };
  };
  "/api/channels/analysis/code-execution": {
    post: {
      responses: {
        200: unknown;
        422: components["schemas"]["HTTPValidationError"];
      };
    };
  };
  "/api/channels/research/findings/{finding_id}/distill": {
    post: {
      responses: {
        200: components["schemas"]["DistillFindingResponse"];
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
    AgentId: "leo" | "maya" | "alex" | "nina" | "iris";
    AgentMemorySummaryResponse: {
      channel_title: string;
      style_guide: string;
      creator_preferences?: string[];
      lessons?: components["schemas"]["MemoryItemResponse"][];
    };
    AgentPromptConfig: {
      /** Target agent identifier (alex, leo, maya, nina, or iris) */
      agent_id: components["schemas"]["AgentId"];
      /** Complete agent working prompt text */
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
      alex_prompt: components["schemas"]["AgentPromptConfig"];
      nina_prompt: components["schemas"]["AgentPromptConfig"];
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
    AutoCorrectQARequest: {
      /** Optional specific review ID to correct */
      review_id?: string | null;
    };
    AutoCorrectQAResponse: {
      /** Unique production identifier */
      production_id: string;
      /** Corrected Nina packaging proposal */
      revised_proposal?: components["schemas"]["PackagingProposal"] | null;
      /** Fresh Iris QA review after correction */
      new_review: components["schemas"]["ReleaseReview"];
      /** Whether output is now ready to publish */
      release_ready?: boolean;
      /** Summary of applied corrections */
      message: string;
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
      /** Target clip duration in ms (~2000-10000ms) */
      duration_ms: number;
      status?: components["schemas"]["BRollArtifactStatus"];
      /** Human summary of B-roll visual intent */
      prompt_summary?: string;
      /** Output resolution: 360p, 720p, 1080p, 4k */
      resolution?: string;
      /** Model ID */
      model?: string;
      /** True if generated at 360p draft resolution */
      is_draft?: boolean;
      /** Initial keyframe URI for transition interpolation */
      first_frame_uri?: string | null;
      /** Terminal keyframe URI for transition interpolation */
      last_frame_uri?: string | null;
      /** Optional video reference URI */
      reference_video_uri?: string | null;
      /** Scene extension prior context in ms */
      scene_extension_prior_context_ms?: number | null;
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
    ChannelDashboard: {
      channel: components["schemas"]["DashboardChannel"];
      period_days: number;
      period_end: string;
      kpis: components["schemas"]["DashboardKpi"][];
      trend: components["schemas"]["DashboardTrendPoint"][];
      latest_video: components["schemas"]["LatestVideoAnalysis"];
      video_performance: components["schemas"]["VideoPerformancePoint"][];
      topic_clusters: components["schemas"]["TopicClusterPerformance"][];
      traffic_sources: components["schemas"]["TrafficSourceMetric"][];
      insights: components["schemas"]["ChannelInsight"][];
      active_experiment: components["schemas"]["ChannelExperiment"] | null;
      proposed_experiment: components["schemas"]["ChannelExperiment"];
      is_sample_modeled_timeseries: boolean;
    };
    ChannelExperiment: {
      experiment_id: string;
      channel_id: string;
      hypothesis: string;
      primary_metric: string;
      baseline_value: number;
      expected_direction: string;
      status: components["schemas"]["ExperimentStatus"];
      started_at: string | null;
      completed_at: string | null;
      video_ids: string[];
      result: string | null;
      effect_size: number | null;
      confidence_summary: string;
      created_by: string;
    };
    ChannelInsight: {
      insight_id: string;
      channel_id: string;
      type: components["schemas"]["InsightType"];
      title: string;
      statement: string;
      evidence: components["schemas"]["InsightEvidence"][];
      confidence: number;
      recommended_action: string;
      created_at: string;
      expires_at?: string | null;
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
    ChapterMarker: {
      /** Concise descriptive chapter title */
      title: string;
      /** Start time in milliseconds on the source video timeline */
      source_start_ms: number;
      /** End time in milliseconds on the source video timeline */
      source_end_ms: number;
      /** Summary of narrative and visual content covered in this chapter */
      summary: string;
      /** Confidence score for this chapter boundary */
      confidence?: number;
    };
    ClaimSupportStatus:
      "SUPPORTED_BY_VIDEO" | "SUPPORTED_EXTERNALLY" | "UNSUPPORTED" | "MANUAL_REVIEW";
    ClaimVerification: {
      /** Specific factual claim examined */
      claim_text: string;
      /** Where the claim appears (title, description, video, chapter, short) */
      location?: string;
      /** Claim support status */
      status: components["schemas"]["ClaimSupportStatus"];
      /** Evidence or rationale supporting status */
      evidence: string;
      /** External reference URL if verified externally */
      source_url?: string | null;
    };
    ClientErrorEvent: {
      firebase_uid?: string | null;
      git_sha?: string | null;
      event_type: "client.error";
      error_code?: string | null;
      message?: string | null;
    };
    CodeExecutionRequest: {
      analysis_goal?: string;
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
    CreatorPackageOverrides: {
      /** Currently selected title (from candidates or custom) */
      selected_title?: string | null;
      /** Creator-edited custom title */
      custom_title?: string | null;
      /** Creator-edited custom description */
      custom_description?: string | null;
      /** Creator-edited chapter titles */
      custom_chapters?: components["schemas"]["PackagingChapter"][] | null;
      /** Creator-edited Short title */
      custom_short_title?: string | null;
      /** Creator-edited Short description */
      custom_short_description?: string | null;
      /** ID of creator-selected thumbnail concept */
      selected_thumbnail_concept_id?: string | null;
      /** Timestamp of last creator edit (UTC) */
      updated_at?: string;
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
    DashboardChannel: {
      channel_id: string;
      source_type: string;
      title: string;
      description: string;
      avatar_url: string | null;
      subscriber_count: number;
      video_count: number;
    };
    DashboardKpi: {
      metric: string;
      current_value: number;
      previous_value: number;
      change_percentage: number | null;
    };
    DashboardTrendPoint: {
      date: string;
      views: number;
      previous_views: number;
      watch_time_hours: number;
      previous_watch_time_hours: number;
      net_subscribers: number;
      previous_net_subscribers: number;
    };
    DeleteProductionResponse: {
      /** Operational status ('deleted') */
      status?: string;
      /** Unique production identifier */
      production_id: string;
      /** Count of GCS media storage objects deleted */
      deleted_storage_objects_count?: number;
      /** UTC timestamp of the deletion */
      deleted_at: string;
    };
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
    DistillFindingResponse: {
      lesson_id: string | null;
      directive: string | null;
      confidence: number | null;
      status: string;
    };
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
      | "REMOVE_SILENCE"
      | "REMOVE_FILLER"
      | "REMOVE_FALSE_START"
      | "REMOVE_REPETITION"
      | "TRIM_PAUSE"
      | "TIGHTEN_PAUSE"
      | "TIGHTEN_EXPLANATION"
      | "REMOVE_LOW_VALUE_SECTION"
      | "KEEP_FOR_CLARITY"
      | "BROLL_COVER"
      | "BROLL_COVER_CANDIDATE"
      | "SOURCE_COVER"
      | "CHAPTER_MARKER"
      | "SHORT_CANDIDATE"
      | "NARRATION_REWRITE"
      | "CAPTION_EMPHASIS";
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
      /** Multimodal semantic chapter markers across the video timeline */
      chapters?: components["schemas"]["ChapterMarker"][];
      /** Overall confidence in the proposal */
      overall_confidence: number;
    };
    EditorSelfReview: {
      /** Unique identifier for the self-review record */
      review_id: string;
      /** Associated Production entity identifier */
      production_id: string;
      /** Originating Edit Decision List identifier */
      edl_id: string;
      /** Associated RenderArtifact identifier of the rendered preview video */
      preview_artifact_id: string;
      /** Agent identifier (Leo) */
      agent?: string;
      /** Model identifier used for the multimodal video self-review */
      model: string;
      /** Self-review verdict: APPROVE_UNCHANGED or NEEDS_REVISION */
      verdict: components["schemas"]["EditorSelfReviewVerdict"];
      /** Concise editorial summary of the rendered preview inspection findings */
      summary: string;
      /** Assessment of narrative pacing and energy across the edit */
      narrative_pacing_assessment: string;
      /** Evaluation of whether each removal improved the overall edit */
      removals_assessment: string;
      /** Evaluation of visual continuity, jump cuts, and screen flow */
      visual_continuity_assessment: string;
      /** Evaluation of audio joins, room tone, and speech tails */
      audio_joins_assessment: string;
      /** Whether additional B-roll visual coverage is recommended */
      coverage_needed?: boolean;
      /** Evaluation of whether the vertical Short still works after editing */
      short_assessment: string;
      /** Concise findings without chain-of-thought */
      findings?: string[];
      /** Leo's confidence in the self-review assessment */
      confidence: number;
      /** Creation timestamp in UTC */
      created_at?: string;
    };
    EditorSelfReviewVerdict: "APPROVE_UNCHANGED" | "NEEDS_REVISION";
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
    EvidenceKind: "FACT" | "INFERENCE" | "RESEARCH" | "RECOMMENDATION";
    ExperimentStatus: "PROPOSED" | "ACTIVE" | "COMPLETED" | "INCONCLUSIVE";
    FindingLifecycle: "NEW" | "UPDATED" | "SEEN" | "EXPIRED";
    GeneratePackagingRequest: {
      /** Whether to bypass cached proposal and generate a fresh packaging proposal */
      force_regenerate?: boolean;
    };
    GenerateReleaseReviewRequest: {
      /** Whether to bypass cached review and execute a fresh Iris QA pass */
      force_regenerate?: boolean;
    };
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
    InsightEvidence: {
      kind: components["schemas"]["EvidenceKind"];
      statement: string;
      metric_refs?: string[];
      citation_urls?: string[];
    };
    InsightType: "PERFORMANCE" | "RETENTION" | "AUDIENCE" | "TRAFFIC" | "TOPIC" | "EXPERIMENT";
    LatestVideoAnalysis: {
      video_id: string;
      title: string;
      published_at: string;
      views: number;
      watch_time_hours: number;
      subscribers_gained: number;
      subscribers_lost: number;
      net_subscribers: number;
      view_delta_percentage: number;
      subscriber_conversion_delta_percentage: number;
      retention_percentage: number;
      retention_delta_points: number;
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
    NarrationMode: "original" | "enhanced_original" | "studio_voice" | "my_voice";
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
    PackagingChapter: {
      /** Polish chapter title */
      title: string;
      /** Start time in milliseconds on the Master timeline */
      start_ms: number;
      /** End time in milliseconds on the Master timeline */
      end_ms: number;
      /** Standard YouTube timecode string (e.g. 0:00, 1:23) */
      formatted_time: string;
      /** Optional brief description of the chapter content */
      summary?: string | null;
    };
    PackagingDetailResponse: {
      /** Unique production identifier */
      production_id: string;
      /** Latest Nina packaging proposal */
      proposal?: components["schemas"]["PackagingProposal"] | null;
      /** Creator-defined package overrides */
      overrides?: components["schemas"]["CreatorPackageOverrides"] | null;
      /** Active title to publish (overridden or primary recommendation) */
      effective_title: string;
      /** Active description to publish */
      effective_description: string;
      /** Active canonical video chapters */
      effective_chapters?: components["schemas"]["PackagingChapter"][];
      /** Active vertical Short packaging */
      effective_short_package?: components["schemas"]["ShortPackage"] | null;
      /** Active selected thumbnail concept ID */
      effective_thumbnail_concept_id?: string | null;
      /** Master video artifact details */
      master_artifact?: components["schemas"]["RenderArtifactResponse"] | null;
      /** Short video artifact details */
      short_artifact?: components["schemas"]["RenderArtifactResponse"] | null;
      /** Signed playback URL for master video */
      master_url?: string | null;
      /** Signed playback URL for short video */
      short_url?: string | null;
      /** Whether an approved master video artifact exists */
      has_master?: boolean;
      /** Whether a vertical Short video artifact exists */
      has_short?: boolean;
      /** Packaging readiness status ('completed' or 'needs_master') */
      status?: string;
      /** UTC timestamp of last proposal generation */
      generated_at?: string | null;
    };
    PackagingProposal: {
      /** Unique packaging proposal identifier (e.g. pkg_...) */
      proposal_id: string;
      /** Associated Production entity identifier */
      production_id: string;
      /** Agent identifier ('nina') */
      agent?: string;
      /** Model identifier used for packaging generation */
      model?: string;
      /** Recommended primary title */
      primary_title: string;
      /** List of distinct title candidates across strategic angles */
      title_candidates: components["schemas"]["TitleCandidate"][];
      /** Publish-ready YouTube description text with chapters */
      description: string;
      /** List of canonical video chapters */
      chapters?: components["schemas"]["PackagingChapter"][];
      /** Tags and keywords for search / discovery */
      keywords?: string[];
      /** Top thumbnail concepts with supporting frame references */
      thumbnail_concepts: components["schemas"]["ThumbnailConcept"][];
      /** Vertical Short packaging if Short exists */
      short_package?: components["schemas"]["ShortPackage"] | null;
      /** Concise product-facing packaging rationale */
      packaging_summary: string;
      /** Product-facing channel evidence supporting primary recommendation */
      channel_evidence?: string | null;
      /** Overall confidence in packaging proposal */
      confidence: number;
      /** Creation timestamp in UTC */
      created_at?: string;
      /** Referenced Master RenderArtifact identifier */
      master_artifact_id?: string | null;
      /** Nina prompt version used for this generation */
      prompt_version?: number;
    };
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
    ProductionStatus: "pending" | "uploading" | "uploaded" | "deleting" | "failed";
    PublishJobDetailResponse: {
      /** Current or latest YouTube publish job */
      job?: components["schemas"]["YouTubePublishJob"] | null;
      /** True if real YouTube channel is connected */
      can_publish?: boolean;
      /** True if youtube.upload OAuth scope is granted */
      has_upload_access?: boolean;
      /** Creator-facing status or restriction message */
      status_message?: string;
      /** True if synthetic sample channel is active */
      is_sample_channel?: boolean;
    };
    PublishJobStatus:
      | "pending"
      | "auth_required"
      | "uploading"
      | "processing"
      | "completed"
      | "failed"
      | "cancelled";
    PublishPreparationResponse: {
      /** Production identifier */
      production_id: string;
      /** Connected YouTube channel title or 'Croviq Sample Channel' */
      channel_title: string;
      /** Channel avatar icon URL */
      channel_avatar_url?: string;
      /** True if using synthetic sample channel that cannot publish */
      is_sample_channel?: boolean;
      /** True if a real YouTube channel is connected */
      can_publish?: boolean;
      /** True if youtube.upload OAuth scope is granted */
      has_upload_access?: boolean;
      /** Master video duration in milliseconds */
      master_duration_ms?: number | null;
      /** Master video title */
      master_title: string;
      /** Active Nina title candidate or creator override */
      suggested_title: string;
      /** Active description with embedded chapters */
      suggested_description: string;
      /** Verified YouTube chapters */
      suggested_chapters?: components["schemas"]["PackagingChapter"][];
      /** Keywords for YouTube tags */
      suggested_tags?: string[];
      /** Default category ID (28 = Science & Technology) */
      suggested_category_id?: string;
      /** Suggested synthetic media disclosure based on Studio Voice/BRoll */
      suggested_synthetic_media?: boolean;
      /** Nina verified thumbnail frame candidates */
      verified_thumbnail_frames?: Record<string, unknown>[];
      /** Whether an approved vertical Short artifact exists */
      has_short?: boolean;
      /** Short title candidate */
      short_title?: string | null;
      /** Short description candidate */
      short_description?: string | null;
      /** Whether Iris has approved the release (verdict PASS) */
      release_ready?: boolean;
    };
    PublishRequest: {
      /** Target privacy status (default private) */
      requested_privacy?: "private" | "unlisted" | "public";
      /** Creator-confirmed declaration: is content made for kids? (COPPA) */
      made_for_kids?: boolean;
      /** Creator-confirmed declaration: does content contain altered or synthetic media? */
      contains_synthetic_media?: boolean;
      /** Optional custom title override (validated <= 100 characters) */
      selected_title?: string | null;
      /** Optional custom description override (validated <= 5000 bytes) */
      selected_description?: string | null;
      /** Optional tags list override */
      selected_tags?: string[] | null;
      /** YouTube category ID (default 28) */
      category_id?: string;
      /** Selected timeline millisecond offset for extracting thumbnail still image */
      thumbnail_frame_ms?: number | null;
      /** Whether to also upload the approved vertical Short as a separate video */
      upload_short?: boolean;
    };
    ReleaseChecklist: {
      /** Master video continuity and encoding status */
      master_video?: boolean;
      /** Audio level, peak, and sync status */
      audio?: boolean;
      /** Caption accuracy, timing, and bounds status */
      captions?: boolean;
      /** Chapter timestamp ordering and topic accuracy */
      chapters?: boolean;
      /** Short framing, captions, and context status */
      short?: boolean;
      /** Packaging title, description, and thumbnail status */
      packaging?: boolean;
      /** Factual and packaging claims validity status */
      claims?: boolean;
    };
    ReleaseIssue: {
      /** Unique identifier for the issue */
      issue_id: string;
      /** Categorized issue type */
      issue_type: components["schemas"]["ReleaseIssueType"];
      /** Severity level */
      severity: components["schemas"]["ReleaseIssueSeverity"];
      /** Start timestamp in video ms if time-bound */
      source_start_ms?: number | null;
      /** End timestamp in video ms if time-bound */
      source_end_ms?: number | null;
      /** Affected artifact type (master, short, packaging, caption, chapter) */
      artifact_type?: string | null;
      /** Related editorial or packaging decision ID if applicable */
      related_decision_id?: string | null;
      /** Concise creator-facing description of defect */
      message: string;
      /** Concrete suggested fix or routing */
      suggested_action: string;
      /** Objective factual or media evidence observed */
      evidence: string;
    };
    ReleaseIssueSeverity: "LOW" | "MEDIUM" | "HIGH" | "BLOCKING";
    ReleaseIssueType:
      | "AUDIO_ARTIFACT"
      | "AUDIO_LEVEL"
      | "AUDIO_SYNC"
      | "BAD_CUT"
      | "VISUAL_JUMP"
      | "BLACK_FRAME"
      | "FRAME_GLITCH"
      | "ENCODE_ISSUE"
      | "CAPTION_MISMATCH"
      | "CAPTION_TIMING"
      | "CAPTION_OVERFLOW"
      | "CHAPTER_MISMATCH"
      | "CHAPTER_TIMING"
      | "UNSUPPORTED_CLAIM"
      | "FACTUAL_INCONSISTENCY"
      | "TITLE_MISMATCH"
      | "DESCRIPTION_MISMATCH"
      | "THUMBNAIL_MISMATCH"
      | "PACKAGING_INCONSISTENCY"
      | "SHORT_QUALITY"
      | "SHORT_CAPTION_QUALITY"
      | "SHORT_CROP"
      | "MISSING_CONTENT"
      | "CONTEXT_LOSS";
    ReleaseReview: {
      /** Unique review identifier */
      review_id: string;
      /** Parent production ID */
      production_id: string;
      /** Evaluating agent identifier (must be iris) */
      agent?: string;
      /** Underlying multimodal GenAI model ID */
      model?: string;
      /** Overall gate verdict (PASS, FIX_REQUIRED, MANUAL_REVIEW) */
      verdict: components["schemas"]["ReleaseVerdict"];
      /** Concise synthesis of evaluation findings */
      summary: string;
      /** List of identified issues */
      issues?: components["schemas"]["ReleaseIssue"][];
      /** True if output satisfies all quality thresholds */
      approved_for_release?: boolean;
      /** Iris assessment confidence score */
      confidence?: number;
      /** UTC timestamp of evaluation generation */
      created_at?: string;
      /** Evaluated Master RenderArtifact ID */
      master_artifact_id?: string | null;
      /** Evaluated Short RenderArtifact ID */
      short_artifact_id?: string | null;
      /** Evaluated PackagingProposal ID */
      packaging_proposal_id?: string | null;
      /** Compact component checklist summary */
      checklist?: components["schemas"]["ReleaseChecklist"];
      /** Itemized factual and packaging claim audits */
      claim_verifications?: components["schemas"]["ClaimVerification"][];
      /** Evaluations of thumbnail concepts */
      thumbnail_evaluations?: components["schemas"]["ThumbnailEvaluation"][];
    };
    ReleaseReviewDetailResponse: {
      /** Unique production identifier */
      production_id: string;
      /** Latest Iris QA release review */
      review?: components["schemas"]["ReleaseReview"] | null;
      /** Creator-facing release pipeline status */
      release_status: string;
      /** Whether output satisfies all release gate conditions */
      release_ready?: boolean;
      /** Compact release verification checklist */
      checklist?: components["schemas"]["ReleaseChecklist"] | null;
      /** Master video artifact details */
      master_artifact?: components["schemas"]["RenderArtifactResponse"] | null;
      /** Short video artifact details */
      short_artifact?: components["schemas"]["RenderArtifactResponse"] | null;
      /** Signed playback URL for master video */
      master_url?: string | null;
      /** Signed playback URL for short video */
      short_url?: string | null;
      /** Whether approved Master video artifact exists */
      has_master?: boolean;
      /** Whether vertical Short video artifact exists */
      has_short?: boolean;
      /** Whether Nina packaging proposal exists */
      has_packaging?: boolean;
      /** UTC timestamp of review generation */
      generated_at?: string | null;
    };
    ReleaseVerdict: "PASS" | "FIX_REQUIRED" | "MANUAL_REVIEW";
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
    ResearchCadence:
      | "EVERY_HOUR"
      | "EVERY_6_HOURS"
      | "EVERY_12_HOURS"
      | "EVERY_DAY"
      | "EVERY_3_DAYS"
      | "EVERY_WEEK";
    ResearchConfig: {
      workspace_id: string;
      channel_id: string;
      enabled?: boolean;
      cadence: components["schemas"]["ResearchCadence"];
      prompts?: components["schemas"]["ResearchPrompt"][];
      last_run_at?: string | null;
      next_run_at: string;
      updated_at: string;
    };
    ResearchFinding: {
      finding_id: string;
      run_id: string;
      channel_id: string;
      category: string;
      title: string;
      summary: string;
      why_it_matters: string;
      relevance_score: number;
      freshness_score: number;
      opportunity_score: number;
      source_citations: components["schemas"]["SourceCitation"][];
      topic_fingerprint: string;
      topic_cluster?: string | null;
      primary_entity?: string | null;
      novelty_score?: number | null;
      discovered_at: string;
      updated_at?: string | null;
      expires_at?: string | null;
      lifecycle?: components["schemas"]["FindingLifecycle"];
    };
    ResearchPrompt: {
      prompt_id: string;
      text: string;
      enabled?: boolean;
      use_broad_web_search?: boolean;
      preferred_sources?: string[];
    };
    ReviewPreviewResponse: {
      /** Canonical unique production identifier */
      production_id: string;
      /** Maya's post-render review record */
      review: components["schemas"]["RenderReview"];
      /** Leo's post-render self-review record */
      self_review?: components["schemas"]["EditorSelfReview"] | null;
      /** Master render artifact if approved and rendered */
      master_artifact?: components["schemas"]["RenderArtifactResponse"] | null;
      /** Second post-render review if bounded correction was performed */
      second_review?: components["schemas"]["RenderReview"] | null;
      /** Current workflow status (complete, needs_manual_review, correcting, approved) */
      status: string;
      /** Product-facing agent activity messages emitted during review and correction */
      activities?: components["schemas"]["AgentActivity"][];
    };
    SchedulerTickResponse: {
      runs_evaluated: number;
      runs_executed: number;
      findings_created: number;
      status: string;
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
    ShortPackage: {
      /** Vertical Short title */
      title: string;
      /** Short description / caption */
      description: string;
      /** Opening spoken / visual hook framing */
      hook: string;
      /** Useful hashtags (e.g. #shorts, #tech) */
      hashtags?: string[];
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
    SourceCitation: {
      url: string;
      title: string;
      domain: string;
      published_at?: string | null;
      grounding_metadata?: Record<string, unknown>;
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
    ThumbnailConcept: {
      /** Unique concept identifier */
      concept_id: string;
      /** Optional short thumbnail overlay headline / text (2-4 words) */
      headline: string;
      /** Description of the primary visual subject in the frame */
      visual_subject: string;
      /** Composition, framing, crop, and visual contrast direction */
      composition: string;
      /** Intended viewer emotion or intrigue (e.g. Curiosity, Disbelief) */
      emotion: string;
      /** Exact millisecond timestamp in the Master video where this frame exists */
      supporting_frame_ms: number;
      /** Rationale for why this visual frame attracts the target audience */
      reason: string;
      /** Confidence score for this thumbnail concept (0.0 - 1.0) */
      confidence: number;
      /** Whether the supporting frame was verified against the Master video */
      frame_verified?: boolean;
      /** Optional storage URI of extracted frame image */
      frame_artifact_uri?: string | null;
    };
    ThumbnailEvaluation: {
      /** Index of evaluated thumbnail concept */
      concept_index: number;
      /** Thumbnail headline text */
      headline: string;
      /** PASS or REJECT */
      verdict: string;
      /** Concise visual QA assessment */
      reason: string;
    };
    ThumbnailUploadStatus: "pending" | "uploading" | "completed" | "failed" | "skipped";
    TitleAngle:
      | "DIRECT_VALUE"
      | "CURIOSITY"
      | "PROBLEM_SOLUTION"
      | "CONTRARIAN"
      | "HOW_TO"
      | "COMPARISON"
      | "NEWS_RELEVANT";
    TitleCandidate: {
      /** YouTube title text */
      text: string;
      /** Strategic packaging angle (DIRECT_VALUE, CURIOSITY, etc.) */
      angle: components["schemas"]["TitleAngle"];
      /** Clear rationale for why this packaging angle fits channel audience */
      why_it_works: string;
      /** Confidence score for this candidate (0.0 - 1.0) */
      confidence: number;
    };
    TopicClusterPerformance: {
      topic_cluster: string;
      video_count: number;
      median_views: number;
      median_retention: number;
      median_ctr: number | null;
    };
    TrafficSourceMetric: {
      /** Traffic source name (e.g. youtube_search, suggested_videos, browse_features) */
      source: string;
      /** Views originating from this source */
      views: number;
      /** Percentage share of total views */
      percentage: number;
    };
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
    UpdatePackagingOverridesRequest: {
      /** Creator selected title */
      selected_title?: string | null;
      /** Creator custom title override */
      custom_title?: string | null;
      /** Creator custom description override */
      custom_description?: string | null;
      /** Creator custom chapters override */
      custom_chapters?: components["schemas"]["PackagingChapter"][] | null;
      /** Creator custom Short title override */
      custom_short_title?: string | null;
      /** Creator custom Short description override */
      custom_short_description?: string | null;
      /** Selected thumbnail concept ID */
      selected_thumbnail_concept_id?: string | null;
    };
    UpdatePromptRequest: {
      /** Updated editorial working prompt */
      prompt_text: string;
    };
    UpdateResearchConfigRequest: {
      enabled: boolean;
      cadence: components["schemas"]["ResearchCadence"];
      prompts: components["schemas"]["ResearchPrompt"][];
    };
    UpdateVoiceSettingsRequest: {
      /** Selected narration mode */
      narration_mode: components["schemas"]["NarrationMode"];
      selected_voice?: string;
      language?: string;
      /** Optional My Voice replication configuration */
      my_voice?: components["schemas"]["VoiceReplicationConfig"] | null;
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
    VideoPerformancePoint: {
      video_id: string;
      title: string;
      views: number;
      ctr_percentage: number | null;
      discovery_metric: string;
      discovery_value: number;
      average_retention: number;
      subscribers_gained: number;
      content_pillar: string;
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
      /** Summary of screen content, slides, demonstration, or camera visual moments */
      visual_summary?: string | null;
      /** Summary of spoken dialogue or audio in this section */
      speech_summary?: string | null;
      /** Leo's editorial rationale and narrative purpose for this section */
      editorial_intent?: string | null;
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
    VoiceReplicationConfig: {
      /** Replication access and lifecycle status */
      status?: components["schemas"]["VoiceReplicationStatus"];
      /** Encrypted/persisted Vertex Voices API voice key (expires in 7 days) */
      voice_key?: string | null;
      /** Expiration datetime for the replicated voice key (7-day maximum TTL) */
      key_expires_at?: string | null;
      /** Whether creator consent audio has been verified with exact required phrase */
      consent_recorded?: boolean;
      /** Start offset in source video of clean 10-30s speech sample */
      source_sample_start_ms?: number | null;
      /** End offset in source video of clean 10-30s speech sample */
      source_sample_end_ms?: number | null;
      /** Reason why voice replication is blocked (e.g. Google allowlist access required) */
      blocked_reason?: string | null;
      /** Suggested resolution action when blocked */
      suggested_action?: string | null;
    };
    VoiceReplicationStatus: "available" | "blocked" | "consent_required" | "expired";
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
      /** My Voice replication settings and consent status */
      my_voice?: components["schemas"]["VoiceReplicationConfig"] | null;
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
    YouTubeAuthUrlRequest: {
      redirect_uri: string;
      include_monetary?: boolean;
      include_upload?: boolean;
    };
    YouTubeAuthUrlResponse: {
      auth_url: string;
      state_token: string;
      scopes: string[];
    };
    YouTubeCallbackRequest: {
      code: string;
      state: string;
      redirect_uri: string;
    };
    YouTubeConnectionPublicSummary: {
      connected: boolean;
      channel_id?: string | null;
      channel_title?: string | null;
      avatar_url?: string | null;
      subscriber_count?: number | null;
      last_sync_at?: string | null;
      has_monetary_access?: boolean;
      has_upload_access?: boolean;
      scopes?: string[];
    };
    YouTubePublishJob: {
      /** Unique identifier for publish job (e.g. pub_...) */
      publish_job_id: string;
      /** Associated production ID */
      production_id: string;
      /** Workspace tenant ID */
      workspace_id: string;
      /** Initiating user ID */
      user_id: string;
      /** Connected channel integration identifier */
      connection_id: string;
      /** Target YouTube channel ID */
      channel_id: string;
      /** Approved Iris ReleaseReview ID */
      release_review_id: string;
      /** Frozen package version number */
      package_version?: number;
      /** Master RenderArtifact ID uploaded to YouTube */
      artifact_id: string;
      /** Artifact type (MASTER) */
      artifact_type?: string;
      /** Current lifecycle status */
      status?: components["schemas"]["PublishJobStatus"];
      /** Creator requested privacy (private, unlisted, public) */
      requested_privacy?: string;
      /** Actual privacy status confirmed by YouTube response */
      actual_privacy?: string | null;
      /** Remote YouTube video ID returned after videos.insert */
      youtube_video_id?: string | null;
      /** Canonical watch URL (https://youtu.be/{video_id}) */
      youtube_url?: string | null;
      /** Thumbnail upload status */
      thumbnail_status?: components["schemas"]["ThumbnailUploadStatus"];
      /** ThumbnailArtifact ID uploaded to thumbnails.set */
      thumbnail_artifact_id?: string | null;
      /** Actual bytes uploaded so far */
      bytes_uploaded?: number;
      /** Total media payload size in bytes */
      total_bytes?: number;
      /** Calculated upload progress percentage (0.0 - 100.0) */
      progress_percent?: number;
      /** Standardized error code if failed */
      error_code?: string | null;
      /** Creator-facing error explanation if failed */
      error_message?: string | null;
      /** Creator-confirmed synthetic media disclosure (status.containsSyntheticMedia) */
      is_synthetic_media?: boolean;
      /** Creator-confirmed COPPA declaration (status.selfDeclaredMadeForKids) */
      made_for_kids?: boolean;
      /** YouTube category ID (default 28 for Science & Technology) */
      category_id?: string;
      /** Final title for videos.insert (validated <= 100 characters) */
      selected_title: string;
      /** Final description with embedded chapters (validated <= 5000 bytes) */
      description: string;
      /** Tags for videos.insert */
      tags?: string[];
      /** True if YouTube restricted upload to private due to unverified API project audit status */
      audit_restriction_detected?: boolean;
      /** True if separate Short upload was also selected */
      short_requested?: boolean;
      /** Short RenderArtifact ID if short upload requested */
      short_artifact_id?: string | null;
      /** Child publish job ID for Short upload */
      short_publish_job_id?: string | null;
      /** Remote YouTube video ID of uploaded Short */
      short_youtube_video_id?: string | null;
      /** Canonical watch URL for Short */
      short_youtube_url?: string | null;
      /** Deterministic idempotency key preventing duplicate uploads */
      idempotency_key: string;
      /** UTC timestamp when remote upload started */
      started_at?: string | null;
      /** UTC timestamp when publication succeeded or failed */
      completed_at?: string | null;
      /** Creation timestamp */
      created_at?: string;
      /** Last state update timestamp */
      updated_at?: string;
    };
  };
}
