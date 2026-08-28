import { expect, test, type Page } from "@playwright/test";

const DEMO_EMAIL = "demo@croviq.app";
const FIREBASE_ID_TOKEN =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJpc3MiOiJodHRwczovL3NlY3VyZXRva2VuLmdvb2dsZS5jb20vY3JvdmlxLTUwNjYwMiIsImF1ZCI6ImNyb3ZpcS01MDY2MDIiLCJhdXRoX3RpbWUiOjEsInVzZXJfaWQiOiJkZW1vX3VzZXJfMTIzIiwic3ViIjoiZGVtb191c2VyXzEyMyIsImlhdCI6MSwiZXhwIjo0MTAyNDQ0ODAwLCJlbWFpbCI6ImRlbW9AY3JvdmlxLmFwcCIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmaXJlYmFzZSI6eyJpZGVudGl0aWVzIjp7ImVtYWlsIjpbImRlbW9AY3JvdmlxLmFwcCJdfSwic2lnbl9pbl9wcm92aWRlciI6InBhc3N3b3JkIn19.signature";

const APPROVED_USER = {
  user_id: "demo_user_123",
  email: DEMO_EMAIL,
  display_name: "Croviq Demo",
  avatar_url: null,
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

const mockFirebasePasswordSignIn = async (page: Page) => {
  await page.route("**/identitytoolkit.googleapis.com/**", async (route) => {
    const url = route.request().url();
    if (url.includes("accounts:signInWithPassword")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          idToken: FIREBASE_ID_TOKEN,
          email: DEMO_EMAIL,
          refreshToken: "fake-refresh-token",
          expiresIn: "3600",
          localId: "demo_user_123",
          registered: true,
        }),
      });
      return;
    }
    if (url.includes("accounts:lookup")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          users: [
            {
              localId: "demo_user_123",
              email: DEMO_EMAIL,
              emailVerified: true,
              displayName: "Croviq Demo",
            },
          ],
        }),
      });
      return;
    }
    await route.continue();
  });
};

const mockBackendApis = async (page: Page, productions: unknown[] = []) => {
  const researchConfig = {
    workspace_id: "ws_demo",
    channel_id: "croviq_syn_ai_eng_01",
    enabled: true,
    cadence: "EVERY_DAY",
    prompts: [
      {
        prompt_id: "emerging-topics",
        text: "Find emerging AI engineering topics relevant to this channel",
        enabled: true,
        use_broad_web_search: true,
        preferred_sources: [],
      },
    ],
    last_run_at: null,
    next_run_at: "2026-08-29T00:00:00Z",
    updated_at: "2026-08-28T00:00:00Z",
  };
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(APPROVED_USER),
    });
  });

  await page.route("**/api/workspace", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        workspace_id: "ws_demo",
        owner_user_id: APPROVED_USER.user_id,
        name: "Croviq",
        created_at: "2026-08-26T00:00:00Z",
        updated_at: "2026-08-26T00:00:00Z",
      }),
    });
  });

  await page.route("**/api/channels/sample/dashboard?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        channel: {
          channel_id: "croviq_syn_ai_eng_01",
          source_type: "synthetic",
          title: "AI Engineering & Agent Systems",
          description: "Sample channel",
          avatar_url: null,
          subscriber_count: 51317,
          video_count: 100,
        },
        period_days: 28,
        period_end: "2026-08-26",
        kpis: [
          { metric: "views", current_value: 42100, previous_value: 35600, change_percentage: 18.3 },
          {
            metric: "watch_time_hours",
            current_value: 3180,
            previous_value: 2900,
            change_percentage: 9.7,
          },
          {
            metric: "net_subscribers",
            current_value: 184,
            previous_value: 128,
            change_percentage: 43.8,
          },
          {
            metric: "average_retention",
            current_value: 58.4,
            previous_value: 54.1,
            change_percentage: 7.9,
          },
        ],
        trend: [
          {
            date: "2026-08-25",
            views: 1800,
            previous_views: 1400,
            watch_time_hours: 110,
            previous_watch_time_hours: 90,
            net_subscribers: 8,
            previous_net_subscribers: 5,
          },
          {
            date: "2026-08-26",
            views: 2100,
            previous_views: 1600,
            watch_time_hours: 140,
            previous_watch_time_hours: 100,
            net_subscribers: 10,
            previous_net_subscribers: 7,
          },
        ],
        latest_video: {
          video_id: "vid_syn_100",
          title: "Google GenAI SDK Tutorial for Beginners (Part 5)",
          published_at: "2026-08-13T04:00:00Z",
          views: 23314,
          watch_time_hours: 1258.9,
          subscribers_gained: 334,
          subscribers_lost: 31,
          net_subscribers: 303,
          view_delta_percentage: 18,
          subscriber_conversion_delta_percentage: -2.84,
          retention_percentage: 33.4,
          retention_delta_points: -25.61,
        },
        video_performance: [
          {
            video_id: "vid_syn_100",
            title: "Google GenAI SDK Tutorial",
            views: 23314,
            ctr_percentage: 4.29,
            average_retention: 33.4,
            subscribers_gained: 334,
            content_pillar: "Gemini & Vertex AI",
          },
        ],
        topic_clusters: [],
        traffic_sources: [{ source: "youtube_search", views: 17000, percentage: 40.4 }],
        insights: [
          {
            insight_id: "insight-1",
            channel_id: "croviq_syn_ai_eng_01",
            type: "RETENTION",
            title: "First demonstration timing tracks retention",
            statement:
              "Across 100 videos, first-demo timing and average retention have a negative correlation.",
            evidence: [
              {
                kind: "FACT",
                statement: "Pearson correlation calculated across 100 videos.",
                metric_refs: ["video:firstDemoSeconds"],
                citation_urls: [],
              },
            ],
            confidence: 0.9,
            recommended_action: "Test the first practical demonstration before 00:30.",
            created_at: "2026-08-26T00:00:00Z",
            expires_at: null,
          },
        ],
        active_experiment: null,
        proposed_experiment: {
          experiment_id: "experiment-1",
          channel_id: "croviq_syn_ai_eng_01",
          hypothesis:
            "Showing the first practical demonstration before 00:30 improves average retention.",
          primary_metric: "averageViewPercentage",
          baseline_value: 59.01,
          expected_direction: "INCREASE",
          status: "PROPOSED",
          started_at: null,
          completed_at: null,
          video_ids: [],
          result: null,
          effect_size: null,
          confidence_summary:
            "Proposed from a historical correlation; causality is not established.",
          created_by: "alex",
        },
        is_sample_modeled_timeseries: true,
      }),
    });
  });

  await page.route("**/api/workspace/agent-settings", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        alex_prompt: {
          agent_id: "alex",
          prompt_text: "You are Alex. Separate facts, inferences, research, and recommendations.",
          version: 1,
          updated_at: "2026-08-28T00:00:00Z",
          is_custom: false,
        },
        leo_prompt: {
          agent_id: "leo",
          prompt_text: "Leo",
          version: 1,
          updated_at: "2026-08-28T00:00:00Z",
          is_custom: false,
        },
        maya_prompt: {
          agent_id: "maya",
          prompt_text: "Maya",
          version: 1,
          updated_at: "2026-08-28T00:00:00Z",
          is_custom: false,
        },
        voice_settings: {
          narration_mode: "original",
          selected_voice: "Puck",
          language: "en-US",
          updated_at: "2026-08-28T00:00:00Z",
        },
        voices: [],
      }),
    });
  });
  await page.route("**/api/workspace/agent-settings/memory", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        channel_title: "AI Engineering & Agent Systems",
        style_guide: "Evidence-backed technical tutorials",
        creator_preferences: [],
        lessons: [
          {
            topic: "Retention",
            content: "Earlier practical demonstrations correlate with stronger retention.",
            learned_from: "100-video sample analysis",
          },
        ],
      }),
    });
  });
  await page.route("**/api/channels/research/config", async (route) => {
    if (route.request().method() === "PUT") {
      Object.assign(researchConfig, JSON.parse(route.request().postData() ?? "{}"), {
        updated_at: "2026-08-28T00:05:00Z",
      });
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(researchConfig),
    });
  });

  await page.route("**/api/client-events", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
  });

  await page.route("**/api/productions", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          productions,
          total: productions.length,
        }),
      });
    } else {
      await route.continue();
    }
  });

  await page.route("**/api/productions/**", async (route) => {
    if (route.request().method() === "DELETE") {
      const url = route.request().url();
      const parts = url.split("/api/productions/");
      const prodId = parts[1]?.split("/")[0] || "prod_f0b41bfd429e";
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "deleted",
          production_id: prodId,
          deleted_storage_objects_count: 2,
          deleted_at: new Date().toISOString(),
        }),
      });
      return;
    }
    if (route.request().method() === "GET") {
      const url = route.request().url();
      if (url.endsWith("/renders")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            production_id: "prod_test_001",
            renders: [],
          }),
        });
        return;
      }
      if (url.endsWith("/playback")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            production_id: "prod_test_001",
            playback_url: "http://localhost:8080/mock-storage/source.mp4",
            expires_at: new Date(Date.now() + 3600000).toISOString(),
          }),
        });
        return;
      }
      if (url.endsWith("/transcript") || url.endsWith("/editorial-run") || url.endsWith("/edl")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(null),
        });
        return;
      }
      if (
        url.endsWith("/transcribe") ||
        url.endsWith("/analyze") ||
        url.endsWith("/renders/preview")
      ) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ status: "completed" }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        body: JSON.stringify({
          production_id: "prod_test_001",
          workspace_id: "ws_demo",
          channel_id: "croviq_syn_ai_eng_01",
          owner_user_id: "demo_user_123",
          status: "uploaded",
          source_media: {
            upload_id: "upl_test_001",
            original_filename: "raw_tutorial.mp4",
            content_type: "video/mp4",
            size_bytes: 1048576,
            gcs_bucket: "croviq-506602-croviq-media-raw",
            gcs_object:
              "workspaces/ws_demo/productions/prod_test_001/source/upl_test_001/raw_tutorial.mp4",
            status: "uploaded",
            created_at: new Date().toISOString(),
            uploaded_at: new Date().toISOString(),
          },
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
      return;
    }
    await route.continue();
  });
};

const login = async (page: Page, openNewProject = true) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("valid-password-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("/app");
  if (openNewProject) {
    await page.getByRole("button", { name: "New Project" }).click();
    await page.waitForURL("/projects/new");
  }
};

test.describe("Product Home and Creator Flow", () => {
  test("renders clean creator-facing Product Home with minimal header and no debug/engineering clutter", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page, []);
    await login(page, false);

    await expect(page.getByRole("banner").getByRole("img", { name: "Croviq" })).toBeVisible();
    await expect(page.getByText(DEMO_EMAIL)).toBeVisible();
    await expect(page.getByRole("button", { name: "Logout" })).toBeVisible();
    await expect(page.getByRole("button", { name: "New Project" })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "AI Engineering & Agent Systems" }),
    ).toBeVisible();
    await expect(page.getByText("Sample channel", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Channel trend")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Video performance map" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Traffic sources" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Alex Briefing" })).toBeVisible();
    await expect(page.getByText("No grounded research findings yet.")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Upload raw footage" })).toHaveCount(0);
    await expect(page.getByText("Owner User ID")).toHaveCount(0);
    await expect(page.getByText("Git SHA")).toHaveCount(0);

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.screenshot({ path: "e2e/screenshots/channel-intelligence-1440x900.png" });
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.screenshot({ path: "e2e/screenshots/channel-intelligence-1280x800.png" });
    expect(consoleErrors).toEqual([]);
  });

  test("persists Alex research schedule and custom public sources", async ({ page }) => {
    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page, []);
    await login(page, false);

    await page.getByRole("button", { name: "Open Alex settings" }).click();
    await expect(page.getByRole("dialog", { name: "Alex settings" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Tools" })).toHaveCount(0);
    await page.getByRole("button", { name: "research", exact: true }).click();
    await page.getByLabel("Schedule").selectOption("EVERY_6_HOURS");
    await page.getByPlaceholder("domain or full public URL").fill("ai.google.dev");
    await page.getByRole("button", { name: "Add preferred source" }).click();
    await page.getByRole("button", { name: "Save research settings" }).click();
    await expect(page.getByText("Research schedule saved")).toBeVisible();
    await page.getByRole("button", { name: "Close Alex settings" }).click();

    await page.getByRole("button", { name: "Open Alex settings" }).click();
    await page.getByRole("button", { name: "research", exact: true }).click();
    await expect(page.getByLabel("Schedule")).toHaveValue("EVERY_6_HOURS");
    await expect(page.getByRole("button", { name: /ai\.google\.dev/ })).toBeVisible();
  });

  test("automatically loads existing persisted productions and links to Editor", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const txt = msg.text();
        if (
          !txt.includes("401") &&
          !txt.includes("404") &&
          !txt.includes("500") &&
          !txt.includes("Failed to load resource") &&
          !txt.includes("net::ERR_")
        ) {
          consoleErrors.push(txt);
        }
      }
    });
    const mockProduction = {
      production_id: "prod_f0b41bfd429e",
      workspace_id: "ws_demo",
      channel_id: "croviq_syn_ai_eng_01",
      owner_user_id: "demo_user_123",
      status: "uploaded",
      source_media: {
        upload_id: "upl_0c191e28f1ee",
        original_filename: "Fairphone 6+ Has Surprising Features! #shorts.mp4",
        content_type: "video/mp4",
        size_bytes: 3227778,
        gcs_bucket: "croviq-506602-croviq-media-raw",
        gcs_object:
          "workspaces/ws_demo/productions/prod_f0b41bfd429e/source/upl_0c191e28f1ee/Fairphone.mp4",
        status: "uploaded",
        created_at: "2026-08-26T04:33:44.963857Z",
        uploaded_at: "2026-08-26T04:33:44.963857Z",
      },
      created_at: "2026-08-26T04:33:44.963857Z",
      updated_at: "2026-08-26T04:33:44.963857Z",
    };

    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page, [mockProduction]);
    await login(page);

    // Verify production appears automatically without clicking "Use Sample Channel"
    const prodRow = page.getByTestId("production-row-prod_f0b41bfd429e");
    await expect(prodRow).toBeVisible();
    await expect(page.getByText("Fairphone 6+ Has Surprising Features! #shorts.mp4")).toBeVisible();
    await expect(page.getByText("3.1 MB")).toBeVisible();
    await expect(page.getByText("UPLOADED")).toHaveCount(0);
    await expect(page.getByText("0 total")).toHaveCount(0);
    // Verify Open Editor action is visible
    const openEditorBtn = prodRow.getByRole("button", { name: "Open Editor" });
    await expect(openEditorBtn).toBeVisible();

    // Capture Home screenshot at 1440x900
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.screenshot({ path: "e2e/screenshots/home-1440x900.png" });

    // Verify clicking Open Editor navigates to the Editor URL
    await openEditorBtn.click();
    await expect(page).toHaveURL(/\/productions\/prod_f0b41bfd429e\/editor/);
    expect(consoleErrors).toEqual([]);
  });
  test("supports deleting a production with confirmation dialog", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    const mockProduction = {
      production_id: "prod_delete_test_01",
      workspace_id: "ws_demo",
      channel_id: "croviq_syn_ai_eng_01",
      owner_user_id: "demo_user_123",
      status: "uploaded",
      source_media: {
        upload_id: "upl_delete_01",
        original_filename: "Test Video To Delete.mp4",
        content_type: "video/mp4",
        size_bytes: 5242880,
        gcs_bucket: "croviq-506602-croviq-media-raw",
        gcs_object: "workspaces/ws_demo/productions/prod_delete_test_01/source/video.mp4",
        status: "uploaded",
        created_at: "2026-08-26T04:33:44.963857Z",
        uploaded_at: "2026-08-26T04:33:44.963857Z",
      },
      created_at: "2026-08-26T04:33:44.963857Z",
      updated_at: "2026-08-26T04:33:44.963857Z",
    };

    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page, [mockProduction]);
    await login(page);

    // Production row is visible initially
    const prodRow = page.getByTestId("production-row-prod_delete_test_01");
    await expect(prodRow).toBeVisible();
    await expect(page.getByText("Test Video To Delete.mp4")).toBeVisible();

    // Click delete action on the row
    const deleteBtn = page.getByTestId("delete-production-prod_delete_test_01");
    await expect(deleteBtn).toBeVisible();
    await deleteBtn.click();

    // Confirmation modal opens
    const modalTitle = page.getByRole("heading", { name: "Delete production?" });
    await expect(modalTitle).toBeVisible();
    await expect(page.getByText(/Are you sure you want to delete/i)).toBeVisible();

    // Clicking Cancel closes modal without deleting
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(modalTitle).toHaveCount(0);
    await expect(prodRow).toBeVisible();

    // Click delete action again and confirm
    await deleteBtn.click();
    await expect(modalTitle).toBeVisible();
    const confirmBtn = page.getByTestId("confirm-delete-button");
    await expect(confirmBtn).toBeVisible();
    await confirmBtn.click();

    // Production row is removed from DOM and success toast appears
    await expect(prodRow).toHaveCount(0);
    await expect(page.getByText(/deleted successfully/i)).toBeVisible();
    expect(consoleErrors).toEqual([]);
  });
  test("executes end-to-end direct storage upload and records production", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const txt = msg.text();
        if (!txt.includes("401") && !txt.includes("404")) {
          consoleErrors.push(txt);
        }
      }
    });

    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page, []);

    // Mock upload negotiation endpoint
    await page.route("**/api/uploads", async (route) => {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: "prod_test_001",
          upload_id: "upl_test_001",
          upload_url: "http://localhost:8080/mock-storage/test.mp4?signed=1",
          method: "PUT",
          required_headers: { "Content-Type": "video/mp4" },
          expires_at: new Date(Date.now() + 1800000).toISOString(),
        }),
      });
    });

    // Mock direct-to-storage PUT
    await page.route("http://localhost:8080/mock-storage/**", async (route) => {
      await route.fulfill({
        status: 200,
        body: "",
      });
    });

    // Mock upload completion endpoint
    await page.route("**/api/uploads/upl_test_001/complete", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: "prod_test_001",
          workspace_id: "ws_demo",
          channel_id: "croviq_syn_ai_eng_01",
          owner_user_id: "demo_user_123",
          status: "uploaded",
          source_media: {
            upload_id: "upl_test_001",
            original_filename: "raw_tutorial.mp4",
            content_type: "video/mp4",
            size_bytes: 1048576,
            gcs_bucket: "croviq-506602-croviq-media-raw",
            status: "uploaded",
            created_at: new Date().toISOString(),
            uploaded_at: new Date().toISOString(),
          },
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
    });

    await page.route("**/api/productions/prod_test_001**", async (route) => {
      const url = route.request().url();
      if (
        url.endsWith("/transcribe") ||
        url.endsWith("/analyze") ||
        url.endsWith("/edl") ||
        url.endsWith("/renders/preview")
      ) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ status: "completed" }),
        });
        return;
      }
      if (
        url.endsWith("/transcript") ||
        url.endsWith("/editorial-run") ||
        url.endsWith("/renders")
      ) {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Not found" }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: "prod_test_001",
          workspace_id: "ws_demo",
          channel_id: "croviq_syn_ai_eng_01",
          owner_user_id: "demo_user_123",
          status: "uploaded",
          source_media: {
            upload_id: "upl_test_001",
            original_filename: "raw_tutorial.mp4",
            content_type: "video/mp4",
            size_bytes: 1048576,
            status: "uploaded",
            created_at: new Date().toISOString(),
            uploaded_at: new Date().toISOString(),
          },
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
    });

    await login(page);

    // Create a mock video file buffer and trigger upload
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: "raw_tutorial.mp4",
      mimeType: "video/mp4",
      buffer: Buffer.from("mock-video-bytes-for-test"),
    });

    // File selected state
    await expect(page.getByText("raw_tutorial.mp4")).toBeVisible();
    const uploadBtn = page.getByRole("button", { name: "Upload video" });
    await expect(uploadBtn).toBeVisible();

    // Click upload
    await uploadBtn.click();

    // Upload completion takes the creator straight into the production Editor.
    await expect(page).toHaveURL(/\/productions\/prod_test_001\/editor/);
    await expect(page.getByText("Upload complete")).toHaveCount(0);
    expect(consoleErrors).toEqual([]);
  });

  test("renders responsive Product Home at mobile viewport (390px)", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page, []);
    await login(page);

    await expect(page.getByRole("main").getByRole("img", { name: "Croviq" })).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/studio-cockpit-390px.png", fullPage: true });
  });

  test("rejects invalid media format with clear error", async ({ page }) => {
    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page, []);
    await login(page);

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: "document.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("pdf-data"),
    });

    await expect(
      page.getByText("Please select a valid video file (.mp4, .mov, or .webm)"),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Upload video" })).toHaveCount(0);
  });

  test("allows vertical page scrolling when content exceeds viewport", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 600 });
    const sampleProductions = Array.from({ length: 8 }, (_, i) => ({
      production_id: `prod_${i + 1}`,
      workspace_id: "ws_demo",
      channel_id: "croviq_syn_ai_eng_01",
      owner_user_id: "demo_user_123",
      status: "uploaded",
      source_media: {
        upload_id: `upl_${i + 1}`,
        original_filename: `Project ${i + 1}.mp4`,
        content_type: "video/mp4",
        size_bytes: 10485760,
        gcs_bucket: "croviq-506602-croviq-media-raw",
        gcs_object: `workspaces/ws_demo/productions/prod_${i + 1}/source/upl_${i + 1}/project.mp4`,
      },
      created_at: "2026-08-26T00:00:00Z",
    }));
    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page, sampleProductions);
    await login(page);

    await expect(page.getByText("Project 1.mp4")).toBeVisible();
    const initialScrollY = await page.evaluate(
      () => window.scrollY || document.documentElement.scrollTop,
    );
    expect(initialScrollY).toBe(0);

    // Scroll down
    await page.evaluate(() => window.scrollTo(0, 400));
    const scrolledY = await page.evaluate(
      () => window.scrollY || document.documentElement.scrollTop,
    );
    expect(scrolledY).toBeGreaterThan(0);
  });
});
