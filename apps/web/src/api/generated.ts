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
}

export interface components {
  schemas: {
    AuthLoginAttemptEvent: {
      event_type: "auth.login_attempt";
    };
    AuthLoginFailedEvent: {
      event_type: "auth.login_failed";
      error_code?: "invalid_credentials" | "demo_access_restricted" | null;
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
      event_type: "client.error";
      error_code?: string | null;
      message?: string | null;
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
    TargetAgent: {};
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
