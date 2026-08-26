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

const mockBackendApis = async (page: Page) => {
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
        name: "Croviq Demo Workspace",
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
          productions: [],
          total: 0,
        }),
      });
    } else {
      await route.continue();
    }
  });
};

const login = async (page: Page) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("valid-password-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("/app");
};

test.describe("Production Home and Raw Media Upload", () => {
  test("renders clean Production Home with Sample Channel and direct upload UI", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page);
    await login(page);

    // Verify main headings
    await expect(page.getByRole("heading", { name: "Croviq" })).toBeVisible();
    await expect(page.getByText(/DevOps for YouTube Creators/i)).toBeVisible();

    // Verify Channel Choice cards
    await expect(page.getByText("Synthetic AI Engineering", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Use Sample Channel" })).toBeVisible();

    // Verify honest Connect YouTube state
    await expect(page.getByText("Connect YouTube Channel")).toBeVisible();
    const connectYtButton = page.getByRole("button", {
      name: /Connect YouTube \(Requires OAuth\)/i,
    });
    await expect(connectYtButton).toBeVisible();
    await expect(connectYtButton).toBeDisabled();

    // Verify "What are we making?" upload dropzone
    await expect(page.getByRole("heading", { name: "What are we making?" })).toBeVisible();
    await expect(page.getByText(/Drop your raw video here/i)).toBeVisible();
    await expect(page.getByText(/Up to 2 GB/i)).toBeVisible();

    // Verify "Recent productions" section
    await expect(page.getByRole("heading", { name: "Recent productions" })).toBeVisible();
    await expect(page.getByText("No productions recorded yet")).toBeVisible();

    // Verify absence of engineering clutter
    await expect(page.getByText("Workspace ID")).toHaveCount(0);
    await expect(page.getByText("Owner User ID")).toHaveCount(0);
    await expect(page.getByText("Git SHA")).toHaveCount(0);

    expect(consoleErrors).toEqual([]);
  });

  test("executes end-to-end direct storage upload and records production", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page);

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

    // Verify uploaded state and production ID banner
    await expect(page.getByText("Uploaded")).toBeVisible();
    await expect(page.getByText("Production recorded and ready for analysis")).toBeVisible();
    await expect(page.getByText("Production ID: prod_test_001")).toBeVisible();

    expect(consoleErrors).toEqual([]);
  });

  test("rejects invalid media format with clear error", async ({ page }) => {
    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page);
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
