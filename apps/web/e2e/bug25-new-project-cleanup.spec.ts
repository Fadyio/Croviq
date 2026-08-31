import { expect, test, type Page } from "@playwright/test";
import { APPROVED_USER, DEMO_EMAIL, FIREBASE_ID_TOKEN, WORKSPACE } from "./test-auth-fixtures";

const MOCK_PRODUCTIONS = [
  {
    production_id: "prod_demo_01",
    workspace_id: "ws_demo",
    channel_id: "croviq_syn_ai_eng_01",
    owner_user_id: APPROVED_USER.user_id,
    source_media: {
      upload_id: "upl_01",
      original_filename: "github.mp4",
      content_type: "video/mp4",
      size_bytes: 48800000,
      gcs_bucket: "croviq-media-raw",
      gcs_object: "upl_01.mp4",
      status: "uploaded",
      created_at: "2026-08-27T10:00:00Z",
    },
    status: "UPLOADED",
    created_at: "2026-08-27T10:00:00Z",
    updated_at: "2026-08-27T10:05:00Z",
  },
  {
    production_id: "prod_demo_02",
    workspace_id: "ws_demo",
    channel_id: "croviq_syn_ai_eng_01",
    owner_user_id: APPROVED_USER.user_id,
    source_media: {
      upload_id: "upl_02",
      original_filename: "gemini_37_agent_demo_raw.mp4",
      content_type: "video/mp4",
      size_bytes: 256000000,
      gcs_bucket: "croviq-media-raw",
      gcs_object: "upl_02.mp4",
      status: "uploaded",
      created_at: "2026-08-26T14:30:00Z",
    },
    status: "UPLOADED",
    created_at: "2026-08-26T14:30:00Z",
    updated_at: "2026-08-26T14:35:00Z",
  },
];

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

const mockBackendApis = async (page: Page, productions = MOCK_PRODUCTIONS) => {
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
      body: JSON.stringify(WORKSPACE),
    });
  });

  await page.route("**/api/productions", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        productions,
        total: productions.length,
      }),
    });
  });

  await page.route("**/api/channels/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        channel_id: "croviq_syn_ai_eng_01",
        title: "Croviq Sample Channel",
        subscribers: 51317,
        video_count: 100,
      }),
    });
  });
};

const signInAndGoToNewProject = async (page: Page) => {
  await mockFirebasePasswordSignIn(page);
  await mockBackendApis(page);
  await page.goto("/login");
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("valid-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/app*");
  await page.goto("/projects/new");
  await page.waitForURL("**/projects/new");
};

test.describe("BUG 25 — New Project Quick UX Cleanup", () => {
  test("verifies layout hierarchy, subtitle removal, duplicate link removal, and row structure across viewports", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    const viewports = [
      { width: 1600, height: 900, name: "1600x900" },
      { width: 1440, height: 900, name: "1440x900" },
      { width: 1280, height: 800, name: "1280x800" },
    ];

    await signInAndGoToNewProject(page);

    for (const vp of viewports) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      // 1. Check Subtitle is removed
      await expect(
        page.getByText("Croviq will analyze, edit, review and render it automatically"),
      ).toHaveCount(0);

      // 2. Check duplicate Channel Intelligence link is removed
      // There should only be the top nav button "Back to Channel Intelligence"
      const backNavBtn = page
        .getByRole("button", { name: "Back to Channel Intelligence" })
        .filter({ hasText: "Back to Channel Intelligence" });
      await expect(backNavBtn).toBeVisible();
      // Ensure no secondary standalone link exists in the header div
      const mainHeader = page.locator("main > div").first();
      await expect(mainHeader.getByRole("button", { name: "Channel Intelligence" })).toHaveCount(0);

      // 3. Check Header title
      await expect(page.getByRole("heading", { name: "New Project", level: 1 })).toBeVisible();

      // 4. Check Upload Area & Recent Projects placement
      const uploadAreaHeading = page.getByText("Start with raw footage").first();
      await expect(uploadAreaHeading).toBeVisible();
      await expect(page.getByText("Click to browse or drag and drop video")).toBeVisible();

      const recentProjectsHeading = page.getByRole("heading", { name: "Recent projects" });
      await expect(recentProjectsHeading).toBeVisible();

      // Verify Recent Projects is positioned below the upload area (bounding box y comparison)
      const uploadBox = await page.locator("main > div > div.bg-surface-1").first().boundingBox();
      const recentBox = await page
        .locator("section[aria-labelledby='recent-projects-heading']")
        .boundingBox();

      expect(uploadBox).not.toBeNull();
      expect(recentBox).not.toBeNull();
      if (uploadBox && recentBox) {
        expect(recentBox.y).toBeGreaterThan(uploadBox.y);
        // Verify both span the same width
        expect(Math.abs(recentBox.width - uploadBox.width)).toBeLessThanOrEqual(2);
      }

      // 5. Check Project Row contents
      const firstRow = page
        .getByText("github.mp4")
        .locator("xpath=ancestor::div[contains(@class, 'group')]");
      await expect(firstRow).toBeVisible();
      await expect(firstRow.getByText("46.5 MB")).toBeVisible();
      await expect(firstRow.getByText("Aug 27")).toBeVisible();
      await expect(firstRow.getByText("UPLOADED")).toBeVisible();
      await expect(firstRow.getByRole("button", { name: /Open/ })).toBeVisible();
      await expect(firstRow.getByTestId("btn-delete-prod_demo_01")).toBeVisible();

      // Screenshot for verification
      await page.screenshot({
        path: `e2e/screenshots/bug25-new-project-${vp.name}.png`,
        fullPage: true,
      });
    }

    // 6. Test Hard Refresh
    await page.reload();
    await expect(page.getByRole("heading", { name: "New Project" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Recent projects" })).toBeVisible();
    await expect(page.getByText("github.mp4")).toBeVisible();

    // 7. Verify no console errors
    expect(consoleErrors).toEqual([]);
  });

  test("verifies Open and Delete project interactions", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await signInAndGoToNewProject(page);

    // 1. Delete button opens modal
    const deleteBtn = page.getByTestId("btn-delete-prod_demo_01");
    await deleteBtn.click();

    const deleteModal = page.getByTestId("modal-delete-confirmation");
    await expect(deleteModal).toBeVisible();
    await expect(deleteModal.getByText("Delete “github.mp4”?")).toBeVisible();

    // Cancel modal
    await deleteModal.getByRole("button", { name: "Cancel" }).click();
    await expect(deleteModal).toHaveCount(0);

    // 2. Open project triggers navigation
    const openBtn = page.getByRole("button", { name: /Open/ }).first();
    await openBtn.click();
    await expect(page).toHaveURL(/\/productions\/prod_demo_01\/editor(?:\?.*)?$/);
  });

  test("verifies Back to Channel Intelligence top button returns to /app", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await signInAndGoToNewProject(page);

    const backBtn = page.getByRole("button", { name: "Back to Channel Intelligence" }).first();
    await backBtn.click();
    await expect(page).toHaveURL(/\/app$/);
  });
});
