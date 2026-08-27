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

const login = async (page: Page) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("valid-password-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("/app");
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
    await login(page);

    // Verify minimal header
    await expect(page.getByRole("img", { name: "Croviq" })).toBeVisible();
    await expect(page.getByText(DEMO_EMAIL)).toBeVisible();
    await expect(page.getByRole("button", { name: "Logout" })).toBeVisible();

    // Verify main intro
    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();
    await expect(page.getByText("Your autonomous video production team.")).toBeVisible();

    // Verify upload dropzone
    await expect(page.getByRole("heading", { name: "Drop your raw video" })).toBeVisible();
    await expect(page.getByText(/MP4 · MOV · WebM · MKV · up to 1 GB/i).first()).toBeVisible();

    // Verify empty Recent productions section without 0 total badge
    await expect(page.getByRole("heading", { name: "Recent productions" })).toBeVisible();
    await expect(page.getByText("No productions yet.")).toBeVisible();
    await expect(page.getByText("Drop a video above to begin.")).toBeVisible();
    await expect(page.getByText("0 total")).toHaveCount(0);

    // Verify strictly NO engineering/debug clutter
    await expect(page.getByText("Croviq Demo Workspace")).toHaveCount(0);
    await expect(page.getByText("Synthetic AI Engineering")).toHaveCount(0);
    await expect(page.getByText("Modern AI Engineering")).toHaveCount(0);
    await expect(page.getByText("Day 1 testing")).toHaveCount(0);
    await expect(page.getByText("Memory Bank")).toHaveCount(0);
    await expect(page.getByText("Engine Online")).toHaveCount(0);
    await expect(page.getByText("Direct GCS")).toHaveCount(0);
    await expect(page.getByText("5 Agents Active")).toHaveCount(0);
    await expect(page.getByText("Production Studio")).toHaveCount(0);
    await expect(page.getByText("Use Sample Channel")).toHaveCount(0);
    await expect(page.getByText("Connect YouTube")).toHaveCount(0);
    await expect(page.getByText("Workspace ID")).toHaveCount(0);
    await expect(page.getByText("Owner User ID")).toHaveCount(0);
    await expect(page.getByText("Git SHA")).toHaveCount(0);

    await page.screenshot({ path: "e2e/screenshots/studio-cockpit-1440px.png", fullPage: true });
    expect(consoleErrors).toEqual([]);
  });

  test("automatically loads existing persisted productions and links to Editor", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const txt = msg.text();
        if (!txt.includes("401") && !txt.includes("404") && !txt.includes("500") && !txt.includes("Failed to load resource") && !txt.includes("net::ERR_")) {
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

    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();
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
});
