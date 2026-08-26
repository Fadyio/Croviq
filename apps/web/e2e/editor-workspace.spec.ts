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

const FAIRPHONE_PRODUCTION_ID = "prod_f0b41bfd429e";
const FAIRPHONE_TRANSCRIPT_ID = "tr_b9ab6b65d13e";
const FAIRPHONE_RUN_ID = "run_1787720797_fd429e";

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

const createMockWords = (count = 314) => {
  const sampleWords = [
    "The",
    "Fairphone",
    "6",
    "Plus",
    "is",
    "an",
    "even",
    "snazzier",
    "version",
    "of",
    "the",
    "original",
    "Fairphone",
    "6,",
    "with",
    "upgraded",
    "brains",
    "and",
    "actually",
    "more",
    "memory.",
    "Something",
    "other",
    "manufacturers",
    "are",
    "actively",
    "stripping",
    "out.",
    "However,",
    "you",
    "will",
    "have",
    "to",
    "undo",
    "a",
    "couple",
    "of",
    "teeny",
    "screws,",
    "so",
    "make",
    "sure",
    "you",
    "don't",
    "have",
    "too",
    "many",
    "Bacardi",
    "breezes",
    "before",
    "attempting",
    "this.",
    "That",
    "then",
    "slides",
    "off,",
    "bung",
    "the",
    "new",
    "one",
    "on,",
    "try",
    "and",
    "get",
    "those",
    "tiny",
    "bloody",
    "screws",
    "back",
    "in,",
    "and",
    "there",
    "you",
    "go,",
    "Fairphone",
    "now",
    "ready",
    "for",
    "my",
    "fingers.",
  ];

  const words = [];
  const totalMs = 113824;

  for (let i = 0; i < count; i++) {
    const text = sampleWords[i % sampleWords.length];
    let start_ms = Math.floor(i * (totalMs / count));
    let end_ms = Math.min(totalMs, Math.floor((i + 1) * (totalMs / count) - 20));

    if (i === 70) {
      start_ms = 26160;
      end_ms = 26500;
    } else if (i > 70 && i <= 121) {
      start_ms = 26160 + (i - 70) * 310;
      end_ms = start_ms + 280;
    }

    words.push({
      index: i,
      text,
      start_ms,
      end_ms,
      confidence: 0.98,
    });
  }
  return words;
};

interface MockEditorOptions {
  customEdl?: unknown;
  initialState?: Partial<Record<"transcript" | "editorialRun" | "edl", boolean>>;
  failStage?: "transcript" | "editorialRun" | "edl";
  editorialStatus?: "analyzing" | "reviewing" | "completed" | "failed";
  completeEditorialAfterGets?: number;
  analyzeDelayMs?: number;
  requests?: string[];
}

const delay = (milliseconds: number): Promise<void> => {
  const { promise, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, milliseconds);
  return promise;
};
const mockEditorApis = async (page: Page, options: MockEditorOptions = {}) => {
  const state = {
    transcript: options.initialState?.transcript ?? true,
    editorialRun: options.initialState?.editorialRun ?? true,
    edl: options.initialState?.edl ?? true,
    editorialStatus: options.editorialStatus ?? "completed",
    editorialGetCount: 0,
  };
  const allWords = createMockWords(314);
  const segments = [
    {
      segment_id: "seg_01",
      start_ms: 0,
      end_ms: 12540,
      text: "The Fairphone 6 Plus is an even snazzier version of the original Fairphone 6, with upgraded brains and actually more memory. Something other manufacturers are actively stripping out.",
      word_start_index: 0,
      word_end_index: 27,
    },
    {
      segment_id: "seg_02",
      start_ms: 26160,
      end_ms: 42340,
      text: "However, you will have to undo a couple of teeny screws, so make sure you don't have too many Bacardi breezes before attempting this. That then slides off, bung the new one on, try and get those tiny bloody screws back in, and there you go, Fairphone now ready for my fingers.",
      word_start_index: 70,
      word_end_index: 121,
    },
  ];

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
        name: "Workspace",
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
    if (route.request().url().endsWith("/api/productions")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          productions: [],
          total: 0,
        }),
      });
    } else {
      await route.fallback();
    }
  });

  // Mock Production
  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        production_id: FAIRPHONE_PRODUCTION_ID,
        workspace_id: "ws_demo",
        channel_id: "croviq_syn_ai_eng_01",
        status: "uploaded",
        source_media: {
          upload_id: "upl_fairphone_01",
          original_filename: "Fairphone 6 Plus teardown.mp4",
          content_type: "video/mp4",
          size_bytes: 45_000_000,
          gcs_bucket: "croviq-media-raw",
          gcs_object: `workspaces/ws_demo/productions/${FAIRPHONE_PRODUCTION_ID}/source/upl_fairphone_01/Fairphone 6 Plus teardown.mp4`,
          status: "uploaded",
          created_at: "2026-08-26T00:00:00Z",
          uploaded_at: "2026-08-26T00:01:00Z",
        },
        created_at: "2026-08-26T00:00:00Z",
        updated_at: "2026-08-26T00:01:00Z",
      }),
    });
  });

  // Mock Playback Signed GET URL
  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/playback`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        production_id: FAIRPHONE_PRODUCTION_ID,
        playback_url:
          "https://storage.googleapis.com/croviq-media-raw/mock-signed-video.mp4?token=mock_v4_signature",
        expires_at: "2026-08-26T01:00:00Z",
      }),
    });
  });
  // Mock signed media video playback stream
  await page.route("**/mock-signed-video.mp4*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "video/mp4",
      headers: {
        "access-control-allow-origin": "*",
      },
      body: Buffer.from(""),
    });
  });

  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/transcribe`, async (route) => {
    options.requests?.push("transcribe");
    if (options.failStage === "transcript") {
      await route.fulfill({ status: 500, body: "transcription failed" });
      return;
    }
    state.transcript = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "completed",
        transcript_id: FAIRPHONE_TRANSCRIPT_ID,
        production_id: FAIRPHONE_PRODUCTION_ID,
        duration_ms: 113824,
        word_count: 314,
        segment_count: 2,
        language_code: "en",
      }),
    });
  });

  // Mock Transcript (314 words, 18 segments)
  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/transcript`, async (route) => {
    if (!state.transcript) {
      await route.fulfill({ status: 404, body: "not found" });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        transcript_id: FAIRPHONE_TRANSCRIPT_ID,
        production_id: FAIRPHONE_PRODUCTION_ID,
        language_code: "en",
        duration_ms: 113824,
        words: allWords,
        segments: segments,
        silence_intervals: [],
        created_at: "2026-08-26T00:01:30Z",
      }),
    });
  });

  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/analyze`, async (route) => {
    options.requests?.push("analyze");
    if (options.failStage === "editorialRun") {
      await route.fulfill({ status: 500, body: "analysis failed" });
      return;
    }
    state.editorialRun = true;
    state.editorialStatus = "analyzing";
    if (options.analyzeDelayMs) {
      await delay(options.analyzeDelayMs / 4);
      state.editorialStatus = "reviewing";
      await delay((options.analyzeDelayMs * 3) / 4);
    }
    state.editorialStatus = "completed";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: FAIRPHONE_RUN_ID,
        production_id: FAIRPHONE_PRODUCTION_ID,
        status: "completed",
        started_at: "2026-08-26T00:02:00Z",
        completed_at: "2026-08-26T00:02:35Z",
      }),
    });
  });

  // Mock Editorial Run (Leo proposals, Maya reviews, AgentActivities)
  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/editorial-run`, async (route) => {
    if (!state.editorialRun) {
      await route.fulfill({ status: 404, body: "not found" });
      return;
    }
    state.editorialGetCount += 1;
    if (
      options.completeEditorialAfterGets &&
      state.editorialGetCount >= options.completeEditorialAfterGets
    ) {
      state.editorialStatus = "completed";
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run: {
          run_id: FAIRPHONE_RUN_ID,
          production_id: FAIRPHONE_PRODUCTION_ID,
          transcript_id: FAIRPHONE_TRANSCRIPT_ID,
          status: state.editorialStatus,
          started_at: "2026-08-26T00:02:00Z",
          completed_at: "2026-08-26T00:02:35Z",
        },
        proposal: {
          production_id: FAIRPHONE_PRODUCTION_ID,
          agent: "leo",
          model: "gemini-3.7-flash",
          summary:
            "The dialogue is punchy, well-paced, and humor-infused with clear technical specs.",
          decisions: [
            {
              decision_id: "dec_001",
              decision_type: "KEEP",
              transcript_start_word: 0,
              transcript_end_word: 27,
              source_start_ms: 0,
              source_end_ms: 12540,
              original_text:
                "The Fairphone 6 Plus is an even snazzier version of the original Fairphone 6, with upgraded brains and actually more memory. Something other manufacturers are actively stripping out.",
              action: "keep",
              concise_reason:
                "Strong opening hook establishing the product and its primary value proposition against competitors.",
              confidence: 0.98,
            },
            {
              decision_id: "dec_002",
              decision_type: "BROLL_COVER_CANDIDATE",
              transcript_start_word: 70,
              transcript_end_word: 121,
              source_start_ms: 26160,
              source_end_ms: 42340,
              original_text:
                "However, you will have to undo a couple of teeny screws, so make sure you don't have too many Bacardi breezes before attempting this. That then slides off, bung the new one on, try and get those tiny bloody screws back in, and there you go, Fairphone now ready for my fingers.",
              action: "cover",
              concise_reason:
                "Close-up macro demonstration of unscrewing and swapping the rear plate accessory works best with focused insert B-roll over the commentary.",
              confidence: 0.94,
            },
            {
              decision_id: "dec_003",
              decision_type: "KEEP_FOR_CLARITY",
              transcript_start_word: 149,
              transcript_end_word: 177,
              source_start_ms: 51020,
              source_end_ms: 60000,
              original_text:
                "And if you don't mind all that screwing action, you can also replace up to 12 parts of this smartphone yourself, including the cameras, the display and the battery.",
              action: "keep",
              concise_reason:
                "Core differentiator for Fairphone brand detailing user repairability and replaceable components.",
              confidence: 0.99,
            },
            {
              decision_id: "dec_004",
              decision_type: "KEEP",
              transcript_start_word: 220,
              transcript_end_word: 267,
              source_start_ms: 75520,
              source_end_ms: 97180,
              original_text:
                "And the Fairphone 6 Plus is powered by the Snapdragon 7S Gen 4, backed by 12GB of RAM, pretty generous in this climate.",
              action: "keep",
              concise_reason:
                "Essential performance and memory specifications delivered with high energy.",
              confidence: 0.96,
            },
          ],
        },
        review: {
          production_id: FAIRPHONE_PRODUCTION_ID,
          agent: "maya",
          model: "director-maya-v2",
          overall_assessment:
            "Leo's editorial decisions effectively preserve the video's high energy, wit, and core product value proposition.",
          decisions: [
            {
              editor_decision_id: "dec_001",
              verdict: "APPROVE",
              concise_reason:
                "Strong opening hook clearly stating product differentiation within critical first 15s.",
            },
            {
              editor_decision_id: "dec_002",
              verdict: "APPROVE",
              concise_reason:
                "Covering the modular plate swap with detailed close-up B-roll enhances viewer comprehension while maintaining comedic commentary pacing.",
            },
            {
              editor_decision_id: "dec_003",
              verdict: "APPROVE",
              concise_reason: "Preserves key repairability explanation without altering pacing.",
            },
            {
              editor_decision_id: "dec_004",
              verdict: "APPROVE",
              concise_reason: "Essential silicon specification delivered concisely.",
            },
          ],
        },
        activities: [
          {
            activity_id: "act_001",
            production_id: FAIRPHONE_PRODUCTION_ID,
            run_id: FAIRPHONE_RUN_ID,
            agent: "leo",
            activity_type: "editorial_proposal",
            message: "[BROLL_COVER_CANDIDATE] At 00:26.2, use close-up visual coverage.",
            related_decision_id: "dec_002",
            created_at: "2026-08-26T00:02:15Z",
          },
          {
            activity_id: "act_002",
            production_id: FAIRPHONE_PRODUCTION_ID,
            run_id: FAIRPHONE_RUN_ID,
            agent: "maya",
            activity_type: "director_review",
            message: "[APPROVE] Approved Leo's coverage decision.",
            related_decision_id: "dec_002",
            created_at: "2026-08-26T00:02:30Z",
          },
        ],
      }),
    });
  });

  // Mock Canonical EDL (Fairphone 0 cuts, 1 B-Roll coverage marker)
  const defaultFairphoneEdl = {
    edl_id: "edl_6324ea33234a",
    production_id: FAIRPHONE_PRODUCTION_ID,
    source_duration_ms: 113824,
    cuts: [],
    coverage_markers: [
      {
        marker_id: "cov_147e604682b8",
        decision_id: "dec_002",
        source_start_ms: 26160,
        source_end_ms: 42340,
        coverage_type: "BROLL_CANDIDATE",
        reason:
          "Close-up macro demonstration of unscrewing and swapping the rear plate accessory works best with focused insert B-roll over the commentary.",
      },
    ],
    created_at: "2026-08-26T00:02:40Z",
  };

  const activeEdl = options?.customEdl || defaultFairphoneEdl;

  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/edl`, async (route) => {
    if (route.request().method() === "POST") {
      options.requests?.push("edl");
      if (options.failStage === "edl") {
        await route.fulfill({ status: 500, body: "edit plan failed" });
        return;
      }
      state.edl = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          edl_id: defaultFairphoneEdl.edl_id,
          production_id: FAIRPHONE_PRODUCTION_ID,
          version: 1,
          cut_count: 0,
          coverage_marker_count: 1,
          source_duration_ms: 113824,
          total_removed_duration_ms: 0,
          estimated_target_duration_ms: 113824,
          status: "ready",
          created_at: defaultFairphoneEdl.created_at,
        }),
      });
      return;
    }
    if (!state.edl) {
      await route.fulfill({ status: 404, body: "not found" });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        edl: activeEdl,
        keep_segments: [[0, 113824]],
      }),
    });
  });
};

const loginAndNavigateToEditor = async (page: Page, options: MockEditorOptions = {}) => {
  await mockFirebasePasswordSignIn(page);
  await mockEditorApis(page, options);

  await page.goto("/login");
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("valid-password-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("/app");

  // Client-side navigate to editor
  await page.evaluate((id) => {
    window.history.pushState(null, "", `/productions/${id}/editor`);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, FAIRPHONE_PRODUCTION_ID);

  await page.waitForSelector("[data-testid='editor-workspace']");
};
test.describe("Editor Workspace (Issue #28)", () => {
  test("unauthenticated visitor navigating to editor route is redirected to login", async ({
    page,
  }) => {
    await page.goto(`/productions/${FAIRPHONE_PRODUCTION_ID}/editor`);
    await page.waitForURL("/login");
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  const resumeCases = [
    {
      name: "runs transcript, analysis, and edit plan for a new upload",
      initialState: { transcript: false, editorialRun: false, edl: false },
      expected: ["transcribe", "analyze", "edl"],
    },
    {
      name: "resumes at analysis when transcript already exists",
      initialState: { transcript: true, editorialRun: false, edl: false },
      expected: ["analyze", "edl"],
    },
    {
      name: "resumes at edit plan when editorial review already exists",
      initialState: { transcript: true, editorialRun: true, edl: false },
      expected: ["edl"],
    },
    {
      name: "makes no processing calls for a completed production",
      initialState: { transcript: true, editorialRun: true, edl: true },
      expected: [],
    },
  ] as const;

  for (const resumeCase of resumeCases) {
    test(resumeCase.name, async ({ page }) => {
      const requests: string[] = [];
      await loginAndNavigateToEditor(page, {
        initialState: resumeCase.initialState,
        requests,
      });

      if (resumeCase.expected.length > 0) {
        await expect.poll(() => requests).toEqual(resumeCase.expected);
      } else {
        await page.waitForTimeout(250);
        expect(requests).toEqual([]);
      }
    });
  }

  test("polls a persisted in-progress review without starting duplicate analysis", async ({
    page,
  }) => {
    const requests: string[] = [];
    await loginAndNavigateToEditor(page, {
      initialState: { transcript: true, editorialRun: true, edl: false },
      editorialStatus: "reviewing",
      completeEditorialAfterGets: 3,
      requests,
    });

    await expect(page.getByText("Maya is reviewing Leo's edit…")).toBeVisible();
    expect(requests).toEqual([]);
    await expect.poll(() => requests, { timeout: 4000 }).toEqual(["edl"]);
  });

  test("shows Leo and Maya only while their persisted analysis stages are active", async ({
    page,
  }) => {
    await loginAndNavigateToEditor(page, {
      initialState: { transcript: true, editorialRun: false, edl: true },
      analyzeDelayMs: 1600,
    });

    await expect(page.getByText("Leo is reviewing the footage…")).toBeVisible();
    await expect(page.getByTestId("agent-presence-leo")).toHaveAttribute("data-active", "true");
    await expect(page.getByText("Maya is reviewing Leo's edit…")).toBeVisible({ timeout: 2500 });
    await expect(page.getByTestId("agent-presence-maya")).toHaveAttribute("data-active", "true");
    await expect(page.getByTestId("run-stage-maya-review")).toHaveAttribute(
      "data-status",
      "active",
    );
    await expect(page.getByTestId("run-stage-maya-review")).toHaveAttribute(
      "data-status",
      "completed",
      { timeout: 3000 },
    );
  });

  const failureCases = [
    {
      name: "transcription",
      initialState: { transcript: false, editorialRun: false, edl: false },
      failStage: "transcript",
      message: "Transcription failed",
      expectedRequests: ["transcribe", "transcribe"],
    },
    {
      name: "Leo analysis",
      initialState: { transcript: true, editorialRun: false, edl: false },
      failStage: "editorialRun",
      message: "Leo analysis failed",
      expectedRequests: ["analyze", "analyze"],
    },
    {
      name: "director review",
      initialState: { transcript: true, editorialRun: true, edl: false },
      editorialStatus: "failed",
      failStage: "editorialRun",
      message: "Director review failed",
      expectedRequests: ["analyze"],
    },
    {
      name: "edit plan",
      initialState: { transcript: true, editorialRun: true, edl: false },
      failStage: "edl",
      message: "Edit plan failed",
      expectedRequests: ["edl", "edl"],
    },
  ] as const;

  for (const failureCase of failureCases) {
    test(`${failureCase.name} failure stays in Editor and Retry invokes only that stage`, async ({
      page,
    }) => {
      const requests: string[] = [];
      await loginAndNavigateToEditor(page, {
        initialState: failureCase.initialState,
        editorialStatus: "editorialStatus" in failureCase ? failureCase.editorialStatus : undefined,
        failStage: failureCase.failStage,
        requests,
      });

      await expect(page.getByText(failureCase.message)).toBeVisible();
      await expect(page).toHaveURL(new RegExp(`/productions/${FAIRPHONE_PRODUCTION_ID}/editor`));
      await page.getByRole("button", { name: "Retry" }).click();
      await expect.poll(() => requests).toEqual(failureCase.expectedRequests);
    });
  }

  test("loads real Fairphone workspace with synchronized transcript, Twick timeline, and Leo/Maya activity", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const txt = msg.text();
        if (!txt.includes("401 (Unauthorized)")) {
          consoleErrors.push(txt);
        }
      }
    });

    let geminiApiCalled = false;
    let groqApiCalled = false;
    page.on("request", (req) => {
      if (req.url().includes("/analyze")) geminiApiCalled = true;
      if (req.url().includes("/transcribe")) groqApiCalled = true;
    });

    await loginAndNavigateToEditor(page);

    // 1. Header Verification
    await expect(page.getByText("Fairphone 6 Plus teardown.mp4")).toBeVisible();
    await expect(page.getByRole("group", { name: "Preview Mode Selection" })).toBeVisible();
    const previewMode = page.getByRole("group", { name: "Preview Mode Selection" });
    await expect(previewMode.getByRole("button", { name: "Original", exact: true })).toBeVisible();
    await expect(previewMode.getByRole("button", { name: /Edited Preview/i })).toBeVisible();

    // 2. Video Stage Verification
    await expect(page.locator("[data-testid='video-stage']")).toBeVisible();
    await expect(page.locator("[data-testid='video-stage']").getByText("00:00.00")).toBeVisible();
    await expect(page.locator("[data-testid='video-stage']").getByText("01:53.82")).toBeVisible();

    // 3. Compact timeline and truthful production execution strip.
    await expect(page.locator("[data-testid='editor-timeline']")).toBeVisible();
    await expect(page.getByText("Source", { exact: true })).toBeVisible();
    await expect(page.getByText("Edits", { exact: true })).toBeVisible();
    await expect(page.getByText("Coverage", { exact: true })).toBeVisible();
    await expect(page.getByText("No dialogue cuts")).toBeVisible();
    await expect(page.getByText("Natural dialogue rhythm fully preserved")).toHaveCount(0);
    await expect(page.getByTestId("production-run-strip")).toBeVisible();
    for (const stage of ["Uploaded", "Transcript", "Leo Edit", "Maya Review", "Edit Plan"]) {
      await expect(
        page.getByTestId(`run-stage-${stage.toLowerCase().replaceAll(" ", "-")}`),
      ).toHaveAttribute("data-status", "completed");
    }
    await expect(page.getByTestId("run-stage-render")).toHaveAttribute("data-status", "pending");
    await expect(page.getByTestId("run-stage-transcript")).toHaveAttribute(
      "title",
      "Transcript 30.0s",
    );
    await expect(page.getByTestId("run-stage-leo-edit")).toHaveAttribute("title", "Leo Edit 15.0s");
    await expect(page.getByTestId("run-stage-maya-review")).toHaveAttribute(
      "title",
      "Maya Review 5.0s",
    );

    // 4. Continuous transcript: no search, count badge, or segment cards.
    await expect(page.locator("[data-testid='transcript-panel']")).toBeVisible();
    await expect(page.getByText("314 words")).toHaveCount(0);
    await expect(page.getByPlaceholder("Search words...")).toHaveCount(0);
    await expect(page.locator("[data-testid='transcript-segment']")).toHaveCount(0);
    await expect(page.locator("[data-word-index='0']")).toHaveText("The");
    await expect(page.locator("[data-word-index='1']")).toHaveText("Fairphone");

    // 5. Compact agent presence and product-facing production activity.
    await expect(page.locator("[data-testid='production-team']")).toHaveCount(0);
    await expect(page.getByText("Autonomous Editorial Team")).toHaveCount(0);
    await expect(page.getByText("Review Completed")).toHaveCount(0);
    await expect(page.getByText(/editorial decisions|decisions approved/i)).toHaveCount(0);
    await expect(page.getByTestId("agent-presence-leo")).toBeVisible();
    await expect(page.getByTestId("agent-presence-maya")).toBeVisible();
    await expect(page.locator("[data-testid='agent-activity-feed']")).toBeVisible();
    await expect(
      page.getByText("Found a section that would benefit from visual coverage."),
    ).toBeVisible();
    await expect(page.getByText("Approved Leo's edit.")).toBeVisible();
    await expect(page.getByText(/\[(KEEP|BROLL_COVER_CANDIDATE|APPROVE)\]/)).toHaveCount(0);
    // 6. Activity selection seeks the media and opens concise decision details.
    await page
      .getByRole("button", {
        name: /Found a section that would benefit from visual coverage\. Seek to 00:26\.16/,
      })
      .click();
    await expect(page.locator("[data-testid='decision-inspector']")).toBeVisible();
    await expect(page.locator("[data-testid='active-coverage-overlay']")).toBeVisible();
    await expect(page.getByText("Leo · Dialogue Editor")).toBeVisible();
    await expect(page.getByText("Maya · Director")).toBeVisible();
    await expect(
      page.locator("[data-testid='decision-inspector']").getByText("Approved", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText(/Covering the modular plate swap with detailed close-up B-roll/i),
    ).toBeVisible();

    // 7. Verify NO new Gemini or Groq calls on loading completed editor
    expect(geminiApiCalled).toBeFalsy();
    expect(groqApiCalled).toBeFalsy();
    expect(consoleErrors).toEqual([]);
  });

  test("transcript phrase click seeks playhead and activates coverage region indicator", async ({
    page,
  }) => {
    await loginAndNavigateToEditor(page);

    // Click on the B-Roll section word in transcript ("However,")
    const howeverWord = page.locator("[data-word-index='70']");
    await expect(howeverWord).toBeVisible();
    await howeverWord.click();

    // Verify Decision Inspector opens and Coverage Overlay appears
    await expect(page.locator("[data-testid='decision-inspector']")).toBeVisible();
    await expect(page.locator("[data-testid='active-coverage-overlay']")).toBeVisible();
    await expect(page.getByText(/B-Roll Coverage Active · 00:26.16 → 00:42.34/i)).toBeVisible();
  });

  test("Edited Preview skips executable cuts on fixture with safe cut", async ({ page }) => {
    const fixtureWithCutEdl = {
      edl_id: "edl_with_cut_01",
      production_id: FAIRPHONE_PRODUCTION_ID,
      source_duration_ms: 113824,
      cuts: [
        {
          cut_id: "cut_demo_01",
          decision_id: "dec_demo_01",
          decision_type: "REMOVE_FILLER",
          transcript_start_word: 10,
          transcript_end_word: 15,
          requested_start_ms: 5000,
          requested_end_ms: 10000,
          safe_start_ms: 4800,
          safe_end_ms: 10200,
          removed_duration_ms: 5400,
          left_anchor: "original",
          right_anchor: "with",
          safety_status: "SAFE",
          safety_reason: "Clean silence boundary between phrases",
          confidence: 0.95,
        },
      ],
      coverage_markers: [],
      created_at: "2026-08-26T00:02:40Z",
    };

    await loginAndNavigateToEditor(page, { customEdl: fixtureWithCutEdl });

    // Verify cut block appears on DIALOGUE EDITS track
    await expect(page.getByText("REMOVE FILLER")).toBeVisible();

    // Verify Edited Preview button has active cut count badge "1"
    await expect(page.getByRole("button", { name: /Edited Preview 1/i })).toBeVisible();
  });
});
