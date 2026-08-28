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
  initialState?: Partial<Record<"transcript" | "editorialRun" | "edl" | "render", boolean>>;
  failStage?: "transcript" | "editorialRun" | "edl" | "render";
  failRendersList?: boolean;
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
  const initialTranscript = options.initialState?.transcript ?? true;
  const initialEditorial = initialTranscript && (options.initialState?.editorialRun ?? true);
  const initialEdl = initialEditorial && (options.initialState?.edl ?? true);
  const initialRender = initialEdl && (options.initialState?.render ?? true);

  const state = {
    transcript: initialTranscript,
    editorialRun: initialEditorial,
    edl: initialEdl,
    render: initialRender,
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
  await page.route("**/api/workspace/agent-settings**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    if (url.includes("/memory")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          channel_title: "AI Engineering & Agent Systems",
          style_guide: "Concise, highly technical, high-momentum tutorials without fluff.",
          creator_preferences: ["Prefers direct jump to terminal commands."],
          lessons: [
            {
              topic: "Reach the first concrete demonstration before 00:30.",
              content: "Videos with first demo <= 30s average higher retention.",
              learned_from: "github.mp4",
            },
          ],
        }),
      });
      return;
    }
    if (url.includes("/voice/sample")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          voice_id: "Puck",
          sample_text: "Welcome to Croviq.",
          audio_base64: "UklGRgAAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=",
          content_type: "audio/wav",
        }),
      });
      return;
    }
    if (url.includes("/voice") && method === "PUT") {
      const body = route.request().postDataJSON() || {};
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          narration_mode: body.narration_mode || "studio_voice",
          selected_voice: body.selected_voice || "Puck",
          language: body.language || "en-US",
          updated_at: "2026-08-28T00:00:00Z",
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        leo_prompt: {
          agent_id: "leo",
          prompt_text: "You are Leo, a professional video editor.",
          version: 1,
          updated_at: "2026-08-27T00:00:00Z",
          is_custom: false,
        },
        maya_prompt: {
          agent_id: "maya",
          prompt_text: "You are Maya, the Director.",
          version: 1,
          updated_at: "2026-08-27T00:00:00Z",
          is_custom: false,
        },
        voice_settings: {
          narration_mode: "original",
          selected_voice: "Puck",
          language: "en-US",
          updated_at: "2026-08-27T00:00:00Z",
        },
        voices: [
          {
            voice_id: "Puck",
            display_name: "Puck",
            gender: "male",
            language_code: "en-US",
          },
          {
            voice_id: "Charon",
            display_name: "Charon",
            gender: "male",
            language_code: "en-US",
          },
          {
            voice_id: "Aoede",
            display_name: "Aoede",
            gender: "female",
            language_code: "en-US",
          },
          {
            voice_id: "Kore",
            display_name: "Kore",
            gender: "female",
            language_code: "en-US",
          },
        ],
      }),
    });
  });

  await page.route("**/api/productions/*/broll", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        production_id: FAIRPHONE_PRODUCTION_ID,
        artifacts: [],
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
  await page.route("**/fake-preview.mp4*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "video/mp4",
      headers: {
        "access-control-allow-origin": "*",
      },
      body: Buffer.from(""),
    });
  });
  await page.route("**/fake-short.mp4*", async (route) => {
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
          chapters: [
            {
              title: "Introduction & Upgraded Specs",
              source_start_ms: 0,
              source_end_ms: 15000,
              summary: "Opening hook establishing Fairphone 6 Plus upgraded brains and memory.",
              confidence: 0.98,
            },
            {
              title: "Hardware Overview",
              source_start_ms: 15000,
              source_end_ms: 26160,
              summary: "Physical device tour, chassis comparison, and design.",
              confidence: 0.95,
            },
            {
              title: "Modular Teardown & Screws",
              source_start_ms: 26160,
              source_end_ms: 42340,
              summary: "Unscrewing and swapping rear plate accessory.",
              confidence: 0.96,
            },
            {
              title: "Repairability & Parts",
              source_start_ms: 42340,
              source_end_ms: 75520,
              summary: "Replaceable parts, display, and modularity breakdown.",
              confidence: 0.97,
            },
            {
              title: "Performance & Verdict",
              source_start_ms: 75520,
              source_end_ms: 113824,
              summary: "Snapdragon 7S Gen 4 chip, RAM, and final thoughts.",
              confidence: 0.95,
            },
          ],
          short_candidate: {
            start_ms: 22260,
            end_ms: 42340,
            transcript_start_word: 60,
            transcript_end_word: 121,
            hook_title: "Fairphone Teardown & Screws",
            concise_reason: "High energy, witty accessory swap and repairability demo.",
            confidence: 0.95,
          },
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

  // Mock Render List and Preview Render
  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/renders`, async (route) => {
    if (options.failRendersList) {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Internal server error: AttributeError" }),
      });
      return;
    }
    if (!state.render) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: FAIRPHONE_PRODUCTION_ID,
          renders: [],
        }),
      });
      return;
    }
    const activeEdlAny = activeEdl as any;
    const cuts = activeEdlAny.cuts || [];
    const removed = cuts.reduce(
      (acc: number, c: any) =>
        c.safety_status !== "REJECTED_UNSAFE"
          ? acc + (c.removed_duration_ms || Math.max(0, c.safe_end_ms - c.safe_start_ms))
          : acc,
      0,
    );
    const computedPreviewDur = Math.max(
      1000,
      (activeEdlAny.source_duration_ms || 113824) - removed,
    );

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        production_id: FAIRPHONE_PRODUCTION_ID,
        renders: [
          {
            artifact_id: "art_preview_001",
            production_id: FAIRPHONE_PRODUCTION_ID,
            edl_id: activeEdlAny.edl_id || defaultFairphoneEdl.edl_id,
            artifact_type: "PREVIEW",
            status: "completed",
            duration_ms: computedPreviewDur,
            size_bytes: 1542000,
            width: 1280,
            height: 720,
            frame_rate: 30.0,
            video_codec: "h264",
            audio_codec: "aac",
            playback_url: "https://storage.googleapis.com/fake-preview.mp4",
            playback_expires_at: "2026-08-27T00:00:00Z",
            created_at: "2026-08-26T00:02:45Z",
            completed_at: "2026-08-26T00:02:50Z",
          },
          {
            artifact_id: "art_short_001",
            production_id: FAIRPHONE_PRODUCTION_ID,
            edl_id: defaultFairphoneEdl.edl_id,
            artifact_type: "SHORT",
            status: "completed",
            duration_ms: 39800,
            size_bytes: 850000,
            width: 1080,
            height: 1920,
            frame_rate: 30.0,
            video_codec: "h264",
            audio_codec: "aac",
            playback_url: "https://storage.googleapis.com/fake-short.mp4",
            playback_expires_at: "2026-08-27T00:00:00Z",
            created_at: "2026-08-26T00:03:05Z",
            completed_at: "2026-08-26T00:03:10Z",
          },
        ],
      }),
    });
  });

  await page.route(
    `**/api/productions/${FAIRPHONE_PRODUCTION_ID}/renders/preview`,
    async (route) => {
      options.requests?.push("renders/preview");
      if (options.failStage === "render") {
        await route.fulfill({ status: 500, body: "render preview failed" });
        return;
      }
      state.render = true;
      const activeEdlAny = activeEdl as any;
      const prevCuts = activeEdlAny.cuts || [];
      const prevRemoved = prevCuts.reduce(
        (acc: number, c: any) =>
          c.safety_status !== "REJECTED_UNSAFE"
            ? acc + (c.removed_duration_ms || Math.max(0, c.safe_end_ms - c.safe_start_ms))
            : acc,
        0,
      );
      const computedPreviewDur = Math.max(
        1000,
        (activeEdlAny.source_duration_ms || 113824) - prevRemoved,
      );

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          artifact_id: "art_preview_001",
          production_id: FAIRPHONE_PRODUCTION_ID,
          edl_id: activeEdlAny.edl_id || defaultFairphoneEdl.edl_id,
          artifact_type: "PREVIEW",
          status: "completed",
          duration_ms: computedPreviewDur,
          size_bytes: 1542000,
          width: 1280,
          height: 720,
          frame_rate: 30.0,
          video_codec: "h264",
          audio_codec: "aac",
          playback_url: "https://storage.googleapis.com/fake-preview.mp4",
          playback_expires_at: "2026-08-27T00:00:00Z",
          created_at: "2026-08-26T00:02:45Z",
          completed_at: "2026-08-26T00:02:50Z",
        }),
      });
    },
  );

  // Mock Post-Render Review & Render Review listing (Issue #30)
  await page.route(
    `**/api/productions/${FAIRPHONE_PRODUCTION_ID}/render-reviews`,
    async (route) => {
      if (!state.render) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            production_id: FAIRPHONE_PRODUCTION_ID,
            review: null,
            reviews: [],
            needs_manual_review: false,
          }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: FAIRPHONE_PRODUCTION_ID,
          review: {
            review_id: "rrv_fairphone_01",
            production_id: FAIRPHONE_PRODUCTION_ID,
            edl_id: defaultFairphoneEdl.edl_id,
            preview_artifact_id: "art_preview_001",
            agent: "maya",
            model: "gemini-3.7-flash",
            verdict: "APPROVE",
            summary: "Dialogue flows naturally. Edit approved.",
            issues: [],
            approved_for_master: true,
            confidence: 0.98,
            created_at: "2026-08-26T00:02:55Z",
          },
          reviews: [],
          needs_manual_review: false,
        }),
      });
    },
  );

  await page.route(
    `**/api/productions/${FAIRPHONE_PRODUCTION_ID}/review-preview`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: FAIRPHONE_PRODUCTION_ID,
          review: {
            review_id: "rrv_fairphone_01",
            production_id: FAIRPHONE_PRODUCTION_ID,
            edl_id: defaultFairphoneEdl.edl_id,
            preview_artifact_id: "art_preview_001",
            agent: "maya",
            model: "gemini-3.7-flash",
            verdict: "APPROVE",
            summary: "Dialogue flows naturally. Edit approved.",
            issues: [],
            approved_for_master: true,
            confidence: 0.98,
            created_at: "2026-08-26T00:02:55Z",
          },
          master_artifact: {
            artifact_id: "art_master_001",
            production_id: FAIRPHONE_PRODUCTION_ID,
            edl_id: defaultFairphoneEdl.edl_id,
            artifact_type: "MASTER",
            status: "completed",
            duration_ms: 113824,
            playback_url: "https://storage.googleapis.com/fake-master.mp4",
            playback_expires_at: "2026-08-27T00:00:00Z",
            created_at: "2026-08-26T00:03:00Z",
            completed_at: "2026-08-26T00:03:05Z",
          },
          status: "complete",
          activities: [
            {
              activity_id: "act_003",
              production_id: FAIRPHONE_PRODUCTION_ID,
              run_id: FAIRPHONE_RUN_ID,
              agent: "maya",
              role: "Director",
              activity_type: "render_review",
              message: "The dialogue flows naturally. Edit approved.",
              created_at: "2026-08-26T00:03:00Z",
            },
          ],
        }),
      });
    },
  );
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
      name: "runs transcript, analysis, edit plan, and render for a new upload",
      initialState: { transcript: false, editorialRun: false, edl: false, render: false },
      expected: ["transcribe", "analyze", "edl", "renders/preview"],
    },
    {
      name: "resumes at analysis when transcript already exists",
      initialState: { transcript: true, editorialRun: false, edl: false, render: false },
      expected: ["analyze", "edl", "renders/preview"],
    },
    {
      name: "resumes at edit plan when editorial review already exists",
      initialState: { transcript: true, editorialRun: true, edl: false, render: false },
      expected: ["edl", "renders/preview"],
    },
    {
      name: "resumes at render when edit plan already exists",
      initialState: { transcript: true, editorialRun: true, edl: true, render: false },
      expected: ["renders/preview"],
    },
    {
      name: "makes no processing calls for a completed production",
      initialState: { transcript: true, editorialRun: true, edl: true, render: true },
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

    await expect(page.getByText("Maya is reviewing Leo's edit…").first()).toBeVisible();
    expect(requests).toEqual([]);
    await expect.poll(() => requests, { timeout: 4000 }).toEqual(["edl", "renders/preview"]);
  });

  test("shows Leo and Maya only while their persisted analysis stages are active", async ({
    page,
  }) => {
    await loginAndNavigateToEditor(page, {
      initialState: { transcript: true, editorialRun: false, edl: true },
      analyzeDelayMs: 1600,
    });

    await expect(page.getByText("Leo is reviewing the footage…").first()).toBeVisible();
    await expect(page.getByTestId("agent-presence-leo")).toHaveAttribute("data-active", "true");
    await expect(page.getByText("Maya is reviewing Leo's edit…").first()).toBeVisible({
      timeout: 3000,
    });
    await expect(page.getByTestId("agent-presence-maya")).toHaveAttribute("data-active", "true");
    await expect(page.getByTestId("compact-status-banner")).toBeVisible();
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
    {
      name: "preview render",
      initialState: { transcript: true, editorialRun: true, edl: true, render: false },
      failStage: "render",
      message: "Preview render failed",
      expectedRequests: ["renders/preview", "renders/preview"],
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
  test("degrades gracefully when renders endpoint returns 500 without failing Editor loading", async ({
    page,
  }) => {
    await loginAndNavigateToEditor(page, {
      initialState: { transcript: true, editorialRun: true, edl: true, render: true },
      failRendersList: true,
    });

    // 1. Verify editor workspace opens without fatal error screen
    await expect(page.getByTestId("editor-workspace")).toBeVisible();
    await expect(page.getByText("Unable to load production")).not.toBeVisible();
    await expect(page.getByText("Renders could not be loaded")).not.toBeVisible();

    // 2. Verify source playback is functional
    const video = page.locator("video");
    await expect(video).toBeVisible();
    await expect(video).toHaveAttribute("src", /mock-signed-video\.mp4/);
    // 3. Verify timeline, transcript, and agent presence are all loaded
    await expect(page.getByTestId("editor-timeline")).toBeVisible();
    await page.getByTestId("tab-transcript").click();
    await expect(page.getByTestId("transcript-panel")).toBeVisible();
    await expect(page.getByTestId("agent-presence-leo")).toBeVisible();
    await expect(page.getByTestId("agent-presence-maya")).toBeVisible();
    await expect(page.getByTestId("rendered-preview-badge")).not.toBeVisible();
    await expect(
      page
        .getByRole("group", { name: "Preview Mode Selection" })
        .getByRole("button", { name: /Edited Preview/i }),
    ).toBeVisible();
  });

  test("loads real Fairphone workspace with synchronized transcript, Twick timeline, and Leo/Maya activity", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const txt = msg.text();
        if (
          !txt.includes("401 (Unauthorized)") &&
          !txt.includes("502") &&
          !txt.includes("Failed to load resource")
        ) {
          consoleErrors.push(txt);
        }
      }
    });

    let geminiApiCalled = false;
    let transcribeApiCalled = false;
    page.on("request", (req) => {
      if (req.url().includes("/analyze")) geminiApiCalled = true;
      if (req.url().includes("/transcribe")) transcribeApiCalled = true;
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

    // 3. Compact timeline and single truthful header status (no duplicate status bar).
    await expect(page.locator("[data-testid='editor-timeline']")).toBeVisible();
    await expect(page.getByText("Video", { exact: true })).toBeVisible();
    await expect(page.getByText("Edits", { exact: true })).toBeVisible();
    await expect(page.getByText("B-roll", { exact: true })).toBeVisible();
    await expect(page.getByText("No dialogue cuts")).toBeVisible();
    await expect(page.getByText("Natural dialogue rhythm fully preserved")).toHaveCount(0);
    await expect(page.getByTestId("production-run-strip")).toHaveCount(0);
    await expect(page.getByTestId("compact-status-banner")).toBeVisible();
    await expect(page.getByTestId("project-bin")).toBeVisible();
    await expect(page.getByText("PROJECT", { exact: true })).toBeVisible();
    await expect(page.getByText("SOURCE", { exact: true })).toBeVisible();
    await expect(page.getByText("OUTPUTS", { exact: true })).toBeVisible();
    await page.getByTestId("tab-transcript").click();
    await expect(page.locator("[data-testid='transcript-panel']")).toBeVisible();
    await expect(page.getByText("314 words")).toHaveCount(0);
    await expect(page.getByPlaceholder("Search words...")).toHaveCount(0);
    await expect(page.locator("[data-testid='transcript-segment']")).toHaveCount(0);
    await expect(page.locator("[data-word-index='0']")).toHaveText("The");
    await expect(page.locator("[data-word-index='1']")).toHaveText("Fairphone");

    // 5. Compact agent presence and product-facing production activity.
    await page.getByTestId("tab-agents-feed").click();
    await expect(page.locator("[data-testid='production-team']")).toHaveCount(0);
    await expect(page.getByText("Autonomous Editorial Team")).toHaveCount(0);
    await expect(page.getByText("Review Completed")).toHaveCount(0);
    await expect(page.getByText(/editorial decisions|decisions approved/i)).toHaveCount(0);
    await expect(page.getByText(/use close-up visual coverage/i)).toBeVisible();
    await expect(page.getByText(/Approved Leo/i)).toBeVisible();
    await expect(page.getByText(/\[(KEEP|BROLL_COVER_CANDIDATE|APPROVE)\]/)).toHaveCount(0);

    // 6. Activity selection seeks the media and opens concise decision details.
    await page.getByTestId("bubble-seek-btn").first().click();
    await expect(page.locator("[data-testid='decision-inspector']")).toBeVisible();
    await expect(page.locator("[data-testid='active-coverage-overlay']")).toBeVisible();
    await expect(page.getByText("Leo · Video Editor")).toBeVisible();
    await expect(page.getByText("Maya · Director")).toBeVisible();
    await expect(
      page.locator("[data-testid='decision-inspector']").getByText("Approved", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText(/Covering the modular plate swap with detailed close-up B-roll/i),
    ).toBeVisible();

    // 7. Verify NO new Gemini or transcription calls on loading completed editor
    expect(geminiApiCalled).toBeFalsy();
    expect(transcribeApiCalled).toBeFalsy();
    expect(consoleErrors).toEqual([]);
  });

  test("transcript phrase click seeks playhead and activates coverage region indicator", async ({
    page,
  }) => {
    await loginAndNavigateToEditor(page);
    await page.getByTestId("tab-transcript").click();

    // Click on the B-Roll section word in transcript ("However,")
    const howeverWord = page.locator("[data-word-index='70']");
    await expect(howeverWord).toBeVisible();
    await howeverWord.click();
    // Verify Decision Inspector opens and Coverage Overlay appears
    await expect(page.locator("[data-testid='decision-inspector']")).toBeVisible();
    await expect(page.locator("[data-testid='active-coverage-overlay']")).toBeVisible();
    await expect(page.getByText("B-Roll Coverage")).toBeVisible();
    await expect(
      page.locator("[data-testid='decision-inspector']").getByText(/00:26\.16/),
    ).toBeVisible();
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

    // Verify human-facing cut block appears on EDITS track (no raw enums)
    await expect(page.getByText(/Filler removed/i)).toBeVisible();
    await expect(page.getByText("REMOVE FILLER")).toHaveCount(0);
    // Verify Edited Preview button has active cut count badge "1"
    await expect(page.getByRole("button", { name: /Edited Preview 1/i })).toBeVisible();
  });

  test("active 2-cut EDL calculates expected edited duration ~109.304s without fallback contradiction", async ({
    page,
  }) => {
    const twoCutEdl = {
      edl_id: "edl_2cut_acceptance",
      production_id: FAIRPHONE_PRODUCTION_ID,
      source_duration_ms: 113824,
      cuts: [
        {
          cut_id: "cut_acc_01",
          decision_id: "dec_acc_01",
          decision_type: "TRIM_PAUSE",
          transcript_start_word: 27,
          transcript_end_word: 28,
          requested_start_ms: 12540,
          requested_end_ms: 15000,
          safe_start_ms: 12540,
          safe_end_ms: 15000,
          removed_duration_ms: 2460,
          left_anchor: "out.",
          right_anchor: "Now",
          safety_status: "SAFE",
          safety_reason: "Clean pause boundary between sentences",
          confidence: 0.96,
        },
        {
          cut_id: "cut_acc_02",
          decision_id: "dec_acc_02",
          decision_type: "REMOVE_FALSE_START",
          transcript_start_word: 121,
          transcript_end_word: 125,
          requested_start_ms: 42340,
          requested_end_ms: 44400,
          safe_start_ms: 42340,
          safe_end_ms: 44400,
          removed_duration_ms: 2060,
          left_anchor: "fingers.",
          right_anchor: "And",
          safety_status: "SAFE",
          safety_reason: "Stumbled phrase restart cleanly excised",
          confidence: 0.94,
        },
      ],
      coverage_markers: [
        {
          marker_id: "cov_acc_01",
          decision_id: "dec_002",
          source_start_ms: 26160,
          source_end_ms: 42340,
          coverage_type: "BROLL_CANDIDATE",
          reason: "Close-up macro teardown insert",
        },
      ],
      created_at: "2026-08-26T00:02:40Z",
    };

    await loginAndNavigateToEditor(page, { customEdl: twoCutEdl });

    // 1. Verify 2 active cuts badge on Edited Preview toggle
    await expect(page.getByRole("button", { name: /Edited Preview 2/i })).toBeVisible();

    // 2. Verify human-readable cut labels (NO raw enum strings)
    await expect(page.getByText(/Silence removed 2.5s|Silence removed/i)).toBeVisible();
    await expect(page.getByText(/False start removed 2.1s|False start removed/i)).toBeVisible();
    await expect(page.getByText("TRIM_PAUSE")).toHaveCount(0);
    await expect(page.getByText("REMOVE_FALSE_START")).toHaveCount(0);

    // 3. Verify Media Bin displays truthful non-fallback duration
    const mediaBin = page.getByTestId("project-bin").or(page.getByTestId("media-bin"));
    await expect(mediaBin.getByText("1m 49s")).toBeVisible();

    // 4. Verify chapters, short, and b-roll appear on timeline
    await expect(page.getByText("Modular Teardown & Screws")).toBeVisible();
    await expect(page.getByText("Fairphone Teardown & Screws")).toBeVisible();
  });

  test("verifies bounded 100dvh desktop layout at 1440x900 without document scroll", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await loginAndNavigateToEditor(page);

    // Verify Editor container fills viewport and document does not vertically overflow
    const isDocumentScrollable = await page.evaluate(() => {
      return document.documentElement.scrollHeight > window.innerHeight;
    });
    expect(
      isDocumentScrollable,
      "Page must not have vertical document overflow at 1440x900",
    ).toBeFalsy();

    // Verify video stage and timeline are both visible without scrolling
    const videoStage = page.locator("[data-testid='video-stage']");
    const timeline = page.locator("[data-testid='editor-timeline']");
    await expect(videoStage).toBeVisible();
    // Verify right rail width is bounded (~340-400px)
    const rightRail = page.locator("[data-testid='production-room']");
    const railBox = await rightRail.boundingBox();
    expect(railBox?.width).toBeGreaterThanOrEqual(340);
    expect(railBox?.width).toBeLessThanOrEqual(400);
    // Verify transcript panel occupies majority of rail height
    await page.getByTestId("tab-transcript").click();
    const transcriptPanel = page.locator("[data-testid='transcript-panel']");
    const transcriptBox = await transcriptPanel.boundingBox();
    if (railBox && transcriptBox) {
      expect(transcriptBox.height / railBox.height).toBeGreaterThan(0.55);
    }
    await expect(page.getByTestId("agent-presence-leo").locator("img")).toBeVisible();
    await expect(page.getByTestId("agent-presence-maya").locator("img")).toBeVisible();

    // Capture screenshot at 1440x900
    await page.screenshot({ path: "e2e/screenshots/editor-1440x900.png" });
  });
  test("verifies bounded 100dvh desktop layout at 1600x900 without document scroll", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1600, height: 900 });
    await loginAndNavigateToEditor(page);

    const isDocumentScrollable = await page.evaluate(() => {
      return document.documentElement.scrollHeight > window.innerHeight;
    });
    expect(
      isDocumentScrollable,
      "Page must not have vertical document overflow at 1600x900",
    ).toBeFalsy();

    await expect(page.locator("[data-testid='video-stage']")).toBeVisible();
    await expect(page.locator("[data-testid='editor-timeline']")).toBeVisible();
    await expect(page.locator("[data-testid='project-bin']")).toBeVisible();
    await expect(page.locator("[data-testid='production-room']")).toBeVisible();

    // Capture screenshot at 1600x900
    await page.screenshot({ path: "e2e/screenshots/editor-1600x900.png" });
  });

  test("verifies bounded 100dvh desktop layout at 1280x800 without document scroll", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await loginAndNavigateToEditor(page);

    // Verify Editor container fills viewport and document does not vertically overflow
    const isDocumentScrollable = await page.evaluate(() => {
      return document.documentElement.scrollHeight > window.innerHeight;
    });
    expect(
      isDocumentScrollable,
      "Page must not have vertical document overflow at 1280x800",
    ).toBeFalsy();

    // Verify video stage and timeline are both visible without scrolling
    await expect(page.locator("[data-testid='video-stage']")).toBeVisible();
    // Verify right rail width is bounded (~340-400px)
    const rightRail = page.locator("[data-testid='production-room']");
    const railBox = await rightRail.boundingBox();
    expect(railBox?.width).toBeGreaterThanOrEqual(340);
    expect(railBox?.width).toBeLessThanOrEqual(400);
    // Capture screenshot at 1280x800
    await page.screenshot({ path: "e2e/screenshots/editor-1280x800.png" });
  });

  test("displays Short output option and switches to vertical Short preview", async ({ page }) => {
    await loginAndNavigateToEditor(page);

    // 1. Verify Short toggle option is visible in header controls
    const previewMode = page.getByRole("group", { name: "Preview Mode Selection" });
    await expect(previewMode.getByRole("button", { name: "Short", exact: true })).toBeVisible();

    // 2. Click Short toggle to activate vertical 9:16 Short playback
    await previewMode.getByRole("button", { name: "Short", exact: true }).click();

    // 3. Verify Short active state and badge
    await expect(previewMode.getByRole("button", { name: "Short", exact: true })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(
      page.getByTestId("short-mode-badge").or(page.getByTestId("rendered-short-badge")),
    ).toBeVisible();
  });

  test("clicking Leo avatar opens Agent Settings drawer with Prompt, Memory, Voice and NO Tools or Activity tabs", async ({
    page,
  }) => {
    await loginAndNavigateToEditor(page);

    // 1. Click Leo avatar
    await page.getByTestId("agent-presence-leo").click();

    // 2. Verify drawer opened
    const drawer = page.getByTestId("agent-settings-drawer");
    await expect(drawer.getByText(/Leo/i).first()).toBeVisible();
    await expect(drawer.getByText("Video Editor").first()).toBeVisible();
    // 3. Verify ONLY Prompt, Memory, Voice tabs exist
    await expect(drawer.getByTestId("tab-prompt")).toBeVisible();
    await expect(drawer.getByTestId("tab-memory")).toBeVisible();
    await expect(drawer.getByTestId("tab-voice")).toBeVisible();

    // 4. Verify NO Tools tab and NO Activity tab in settings
    await expect(drawer.getByRole("button", { name: "Tools" })).toHaveCount(0);
    await expect(drawer.getByRole("button", { name: "Activity" })).toHaveCount(0);

    // 5. Verify Prompt is editable with Save and Reset buttons
    await expect(drawer.getByTestId("agent-prompt-textarea")).toBeVisible();
    await expect(drawer.getByTestId("btn-save-prompt")).toBeVisible();
    await expect(drawer.getByTestId("btn-reset-prompt")).toBeVisible();

    // 6. Switch to Memory tab and verify read-only
    await drawer.getByTestId("tab-memory").click();
    await expect(drawer.getByTestId("settings-memory-view")).toBeVisible();
    await expect(drawer.getByText("Channel Memory Bank")).toBeVisible();
    await expect(drawer.getByRole("button", { name: "Edit" })).toHaveCount(0);
    await expect(drawer.getByRole("button", { name: "Delete" })).toHaveCount(0);

    // 7. Switch to Voice tab and verify voice catalog & Play sample
    await drawer.getByTestId("tab-voice").click();
    await expect(drawer.getByTestId("settings-voice-view")).toBeVisible();
    await drawer.getByTestId("voice-mode-studio_voice").click();
    await expect(drawer.getByTestId("voice-selector-dropdown")).toBeVisible();
    await expect(drawer.getByTestId("btn-play-voice-sample")).toBeVisible();
    await drawer.getByRole("button", { name: "Close" }).click();
    await expect(drawer).not.toBeVisible();
  });

  test("Media Bin displays project rows and allows selecting modes", async ({ page }) => {
    await loginAndNavigateToEditor(page);

    const mediaBin = page.getByTestId("project-bin").or(page.getByTestId("media-bin"));
    await expect(mediaBin).toBeVisible();
    await expect(mediaBin.getByText("PROJECT", { exact: true })).toBeVisible();

    // Verify Source Video and Edited Preview rows
    const originalRow = mediaBin
      .getByTestId("asset-original")
      .or(mediaBin.getByTestId("media-bin-row-original"))
      .or(mediaBin.getByTestId("asset-source-video"));
    const editedRow = mediaBin
      .getByTestId("asset-edited")
      .or(mediaBin.getByTestId("media-bin-row-edited"));
    await expect(originalRow).toBeVisible();
    await expect(editedRow).toBeVisible();

    // Click Source Video in Media Bin
    await originalRow.click();
    const previewMode = page.getByRole("group", { name: "Preview Mode Selection" });
    await expect(
      previewMode.getByRole("button", { name: "Original", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  test("Agent conversation displays speech bubbles with click-to-seek timestamp pills", async ({
    page,
  }) => {
    await loginAndNavigateToEditor(page);

    const feed = page.getByTestId("agent-activity-feed");
    await expect(feed).toBeVisible();

    // Verify conversation speech bubbles render with avatar and role
    await expect(feed.getByTestId("activity-message-leo").first()).toBeVisible();
    await expect(feed.getByText("· Video Editor").first()).toBeVisible();
  });
});
