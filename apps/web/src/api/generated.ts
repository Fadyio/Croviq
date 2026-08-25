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
  "/api/auth/me": {
    get: {
      responses: {
        200: components["schemas"]["User"];
      };
    };
  };
}

export interface components {
  schemas: {
    HealthResponse: {
      /** Service health status */
      status?: string;
      /** Service identifier */
      service?: string;
      /** Current git commit SHA or environment identifier */
      git_sha: string;
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
  };
}
