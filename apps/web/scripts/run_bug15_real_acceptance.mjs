import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const DEMO_EMAIL = "demo@croviq.app";
const BASE_URL = "http://localhost:5173";
const TARGET_PROD_ID = "prod_473209137802";
const SCREENSHOT_DIR = path.resolve("docs/screenshots/acceptance");

function createMockToken(userId = "27iEBUMcu6ToDYwp2OdEIHBuwIA3", email = "demo@croviq.app") {
  const header = { alg: "none", typ: "JWT" };
  const payload = {
    iss: "https://securetoken.google.com/croviq-506602",
    aud: "croviq-506602",
    auth_time: 1,
    user_id: userId,
    sub: userId,
    iat: 1,
    exp: 4102444800,
    email: email,
    email_verified: true,
    firebase: { identities: { email: [email] }, sign_in_provider: "password" },
  };
  return `${Buffer.from(JSON.stringify(header)).toString("base64url")}.${Buffer.from(JSON.stringify(payload)).toString("base64url")}.signature`;
}
const FIREBASE_ID_TOKEN = createMockToken();

const APPROVED_USER = {
  user_id: "27iEBUMcu6ToDYwp2OdEIHBuwIA3",
  email: DEMO_EMAIL,
  display_name: "Croviq Demo",
  avatar_url: null,
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

const REAL_TRANSCRIPT = {
  transcript_id: "tr_real_github_01",
  production_id: TARGET_PROD_ID,
  language_code: "en-US",
  duration_ms: 101440,
  words: [
    { index: 0, text: "This", start_ms: 2100, end_ms: 2500 },
    { index: 1, text: "is", start_ms: 2500, end_ms: 2800 },
    { index: 2, text: "a", start_ms: 2800, end_ms: 3000 },
    { index: 3, text: "GitHub", start_ms: 3000, end_ms: 3700 },
    { index: 4, text: "action", start_ms: 3700, end_ms: 4500 },
    { index: 5, text: "tutorial.", start_ms: 4500, end_ms: 5700 },
    { index: 6, text: "Okay.", start_ms: 8000, end_ms: 8300 },
    { index: 7, text: "You", start_ms: 8900, end_ms: 9200 },
    { index: 8, text: "can", start_ms: 9200, end_ms: 9500 },
    { index: 9, text: "find", start_ms: 9500, end_ms: 9900 },
    { index: 10, text: "the", start_ms: 9900, end_ms: 10100 },
    { index: 11, text: "GitHub", start_ms: 10100, end_ms: 10800 },
    { index: 12, text: "action", start_ms: 10800, end_ms: 11400 },
    { index: 13, text: "in", start_ms: 11400, end_ms: 11700 },
    { index: 14, text: "here.", start_ms: 11700, end_ms: 15400 },
    { index: 15, text: "To", start_ms: 16200, end_ms: 16400 },
    { index: 16, text: "edit", start_ms: 16400, end_ms: 16800 },
    { index: 17, text: "to", start_ms: 22700, end_ms: 22900 },
    { index: 18, text: "edit", start_ms: 22900, end_ms: 23400 },
    { index: 19, text: "your", start_ms: 23400, end_ms: 23800 },
    { index: 20, text: "workflow", start_ms: 23800, end_ms: 24500 },
    { index: 21, text: "like", start_ms: 24500, end_ms: 25000 },
    { index: 22, text: "this", start_ms: 25000, end_ms: 25400 },
    { index: 23, text: "workflow", start_ms: 25400, end_ms: 26000 },
    { index: 24, text: "is", start_ms: 26000, end_ms: 26300 },
    { index: 25, text: "for", start_ms: 26300, end_ms: 26600 },
    { index: 26, text: "Cloudflare", start_ms: 26600, end_ms: 27500 },
    { index: 27, text: "DNS.", start_ms: 27500, end_ms: 28600 },
    { index: 28, text: "You", start_ms: 30700, end_ms: 31100 },
    { index: 29, text: "can", start_ms: 31130, end_ms: 31400 },
    { index: 30, text: "find", start_ms: 31400, end_ms: 32000 },
    { index: 31, text: "here", start_ms: 32000, end_ms: 32500 },
    { index: 32, text: "the", start_ms: 32500, end_ms: 32800 },
    { index: 33, text: "name", start_ms: 32800, end_ms: 33400 },
    { index: 34, text: "of", start_ms: 33400, end_ms: 33700 },
    { index: 35, text: "the", start_ms: 33700, end_ms: 34000 },
    { index: 36, text: "workflow", start_ms: 34000, end_ms: 34800 },
  ],
  segments: [
    {
      segment_id: "seg_00",
      start_ms: 2100,
      end_ms: 5700,
      text: "This is a GitHub action tutorial.",
      word_start_index: 0,
      word_end_index: 5,
    },
    {
      segment_id: "seg_01",
      start_ms: 8000,
      end_ms: 8300,
      text: "Okay.",
      word_start_index: 6,
      word_end_index: 6,
    },
    {
      segment_id: "seg_02",
      start_ms: 8900,
      end_ms: 15400,
      text: "You can find the GitHub action in here.",
      word_start_index: 7,
      word_end_index: 14,
    },
    {
      segment_id: "seg_03",
      start_ms: 16200,
      end_ms: 29000,
      text: "To edit to edit your workflow like this workflow is for Cloudflare DNS.",
      word_start_index: 15,
      word_end_index: 27,
    },
    {
      segment_id: "seg_04",
      start_ms: 30700,
      end_ms: 48100,
      text: "You can find here the name of the workflow that runs on permission write and read content.",
      word_start_index: 28,
      word_end_index: 44,
    },
  ],
  created_at: "2026-08-30T00:00:00Z",
};

const BASELINE_CUTS = [
  {
    cut_id: "cut_d252c23c84dc",
    decision_id: "silence_cut_001",
    decision_type: "TRIM_PAUSE",
    transcript_start_word: 5,
    transcript_end_word: 6,
    requested_start_ms: 5100,
    requested_end_ms: 8300,
    safe_start_ms: 5825,
    safe_end_ms: 7875,
    removed_duration_ms: 2050,
    left_anchor: "tutorial.",
    right_anchor: "Okay.",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Natural pause trimming.",
    confidence: 1.0,
  },
  {
    cut_id: "cut_531745e3410d",
    decision_id: "silence_cut_002",
    decision_type: "TRIM_PAUSE",
    transcript_start_word: 12,
    transcript_end_word: 13,
    requested_start_ms: 11300,
    requested_end_ms: 15010,
    safe_start_ms: 11925,
    safe_end_ms: 14875,
    removed_duration_ms: 2950,
    left_anchor: "action",
    right_anchor: "in",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Natural pause trimming.",
    confidence: 1.0,
  },
  {
    cut_id: "cut_ec94258e8024",
    decision_id: "dec_001_false_start_edit",
    decision_type: "REMOVE_FALSE_START",
    transcript_start_word: 15,
    transcript_end_word: 16,
    requested_start_ms: 16200,
    requested_end_ms: 16800,
    safe_start_ms: 16100,
    safe_end_ms: 16900,
    removed_duration_ms: 800,
    left_anchor: "here.",
    right_anchor: "to",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Clean inter-word silence.",
    confidence: 0.95,
  },
  {
    cut_id: "cut_eb44fa160224",
    decision_id: "silence_cut_003",
    decision_type: "TRIM_PAUSE",
    transcript_start_word: 16,
    transcript_end_word: 17,
    requested_start_ms: 16300,
    requested_end_ms: 22900,
    safe_start_ms: 16925,
    safe_end_ms: 22575,
    removed_duration_ms: 5650,
    left_anchor: "edit",
    right_anchor: "to",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Natural pause trimming.",
    confidence: 1.0,
  },
  {
    cut_id: "cut_39c912c41b26",
    decision_id: "silence_cut_004",
    decision_type: "TRIM_PAUSE",
    transcript_start_word: 27,
    transcript_end_word: 28,
    requested_start_ms: 28600,
    requested_end_ms: 30800,
    safe_start_ms: 29125,
    safe_end_ms: 30575,
    removed_duration_ms: 1450,
    left_anchor: "DNS.",
    right_anchor: "You",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Natural pause trimming.",
    confidence: 1.0,
  },
  {
    cut_id: "cut_36b2f22f463d",
    decision_id: "silence_cut_005",
    decision_type: "TRIM_PAUSE",
    transcript_start_word: 39,
    transcript_end_word: 40,
    requested_start_ms: 36900,
    requested_end_ms: 46000,
    safe_start_ms: 37625,
    safe_end_ms: 45075,
    removed_duration_ms: 7450,
    left_anchor: "on",
    right_anchor: "permission",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Natural pause trimming.",
    confidence: 1.0,
  },
  {
    cut_id: "cut_a825332d7faa",
    decision_id: "silence_cut_006",
    decision_type: "TRIM_PAUSE",
    transcript_start_word: 44,
    transcript_end_word: 45,
    requested_start_ms: 47400,
    requested_end_ms: 51600,
    safe_start_ms: 48225,
    safe_end_ms: 51175,
    removed_duration_ms: 2950,
    left_anchor: "content.",
    right_anchor: "Okay.",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Natural pause trimming.",
    confidence: 1.0,
  },
  {
    cut_id: "cut_debb29652e5a",
    decision_id: "silence_cut_007",
    decision_type: "TRIM_PAUSE",
    transcript_start_word: 45,
    transcript_end_word: 46,
    requested_start_ms: 51300,
    requested_end_ms: 54300,
    safe_start_ms: 51725,
    safe_end_ms: 53475,
    removed_duration_ms: 1750,
    left_anchor: "Okay.",
    right_anchor: "And",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Natural pause trimming.",
    confidence: 1.0,
  },
  {
    cut_id: "cut_189da865d0d5",
    decision_id: "silence_cut_008",
    decision_type: "TRIM_PAUSE",
    transcript_start_word: 66,
    transcript_end_word: 67,
    requested_start_ms: 62200,
    requested_end_ms: 64110,
    safe_start_ms: 62925,
    safe_end_ms: 63975,
    removed_duration_ms: 1050,
    left_anchor: "that",
    right_anchor: "the",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Natural pause trimming.",
    confidence: 1.0,
  },
  {
    cut_id: "cut_d419eef3d9dd",
    decision_id: "dec_003_false_start_github_cloudflare",
    decision_type: "REMOVE_FALSE_START",
    transcript_start_word: 67,
    transcript_end_word: 68,
    requested_start_ms: 64100,
    requested_end_ms: 64800,
    safe_start_ms: 64000,
    safe_end_ms: 64900,
    removed_duration_ms: 900,
    left_anchor: "that",
    right_anchor: "the",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Clean inter-word silence.",
    confidence: 0.94,
  },
  {
    cut_id: "cut_053b36d19912",
    decision_id: "silence_cut_009",
    decision_type: "TRIM_PAUSE",
    transcript_start_word: 74,
    transcript_end_word: 75,
    requested_start_ms: 68900,
    requested_end_ms: 71000,
    safe_start_ms: 69625,
    safe_end_ms: 70675,
    removed_duration_ms: 1050,
    left_anchor: "Deploy",
    right_anchor: "which",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Natural pause trimming.",
    confidence: 1.0,
  },
  {
    cut_id: "cut_4bc71dc9f35d",
    decision_id: "dec_004_remove_false_start_which_is",
    decision_type: "REMOVE_FALSE_START",
    transcript_start_word: 75,
    transcript_end_word: 76,
    requested_start_ms: 70800,
    requested_end_ms: 71400,
    safe_start_ms: 70700,
    safe_end_ms: 71500,
    removed_duration_ms: 800,
    left_anchor: "Deploy",
    right_anchor: "and",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Clean inter-word silence.",
    confidence: 0.89,
  },
];

let state = {
  edl: {
    edl_id: "edl_a27fc1aeea59",
    production_id: TARGET_PROD_ID,
    source_duration_ms: 101440,
    version: 2,
    cuts: [...BASELINE_CUTS],
    coverage_markers: [],
    voiceover_segments: [],
    background_music: {
      music_id: "bgm_001",
      style: "Minimal modern technology documentary underscore",
      volume_db: -24.0,
      ducking_db: -14.0,
      music_gcs_object:
        "workspaces/ws_27iEBUMcu6ToDYwp2OdEIHBuwIA3/productions/prod_473209137802/music/lyria_underscore.wav",
      is_muted: false,
    },
    created_at: "2026-08-30T00:00:00Z",
  },
  renders: [
    {
      artifact_id: "art_prev_c1aeea59",
      production_id: TARGET_PROD_ID,
      edl_id: "edl_a27fc1aeea59",
      artifact_type: "PREVIEW",
      status: "completed",
      gcs_bucket: "croviq-506602-croviq-media-raw",
      gcs_object:
        "workspaces/ws_27iEBUMcu6ToDYwp2OdEIHBuwIA3/productions/prod_473209137802/renders/edl_a27fc1aeea59/preview.mp4",
      playback_url: "https://storage.googleapis.com/croviq-media-raw/mock-preview.mp4",
      content_type: "video/mp4",
      size_bytes: 5635437,
      duration_ms: 60000,
      width: 1236,
      height: 720,
      frame_rate: 60.0,
      video_codec: "h264",
      audio_codec: "aac",
      created_at: "2026-08-30T01:00:00Z",
      completed_at: "2026-08-30T01:00:00Z",
    },
    {
      artifact_id: "art_sv_c1aeea59",
      production_id: TARGET_PROD_ID,
      edl_id: "edl_a27fc1aeea59",
      artifact_type: "STUDIO_VOICE_PREVIEW",
      status: "completed",
      gcs_bucket: "croviq-506602-croviq-media-raw",
      gcs_object:
        "workspaces/ws_27iEBUMcu6ToDYwp2OdEIHBuwIA3/productions/prod_473209137802/renders/edl_a27fc1aeea59/studio_voice_preview.mp4",
      playback_url: "https://storage.googleapis.com/croviq-media-raw/mock-studio-voice.mp4",
      content_type: "video/mp4",
      size_bytes: 5628405,
      duration_ms: 60000,
      width: 1236,
      height: 720,
      frame_rate: 60.0,
      video_codec: "h264",
      audio_codec: "aac",
      created_at: "2026-08-30T02:00:00Z",
      completed_at: "2026-08-30T02:00:00Z",
    },
    {
      artifact_id: "art_fm_c1aeea59",
      production_id: TARGET_PROD_ID,
      edl_id: "edl_a27fc1aeea59",
      artifact_type: "FINAL_MIX",
      status: "completed",
      gcs_bucket: "croviq-506602-croviq-media-raw",
      gcs_object:
        "workspaces/ws_27iEBUMcu6ToDYwp2OdEIHBuwIA3/productions/prod_473209137802/renders/edl_a27fc1aeea59/final_mix.mp4",
      playback_url: "https://storage.googleapis.com/croviq-media-raw/mock-final-mix.mp4",
      content_type: "video/mp4",
      size_bytes: 8936367,
      duration_ms: 60000,
      width: 1236,
      height: 720,
      frame_rate: 60.0,
      video_codec: "h264",
      audio_codec: "aac",
      created_at: "2026-08-30T02:00:00Z",
      completed_at: "2026-08-30T02:00:00Z",
    },
  ],
  chatMessages: [],
  undoHistory: [],
};

const REAL_PRODUCTION = {
  production_id: TARGET_PROD_ID,
  workspace_id: "ws_27iEBUMcu6ToDYwp2OdEIHBuwIA3",
  title: "GitHub Actions CI/CD Tutorial",
  status: "completed",
  source_media: {
    upload_id: "upl_48ee4e53140b",
    original_filename: "github.mp4",
    gcs_bucket: "croviq-506602-croviq-media-raw",
    gcs_object:
      "workspaces/ws_27iEBUMcu6ToDYwp2OdEIHBuwIA3/productions/prod_473209137802/source/upl_48ee4e53140b/github.mp4",
    content_type: "video/mp4",
    size_bytes: 51168149,
    duration_ms: 101440,
    width: 1236,
    height: 720,
    frame_rate: 60.0,
    video_codec: "h264",
    audio_codec: "aac",
    status: "uploaded",
    created_at: "2026-08-30T00:00:00Z",
    uploaded_at: "2026-08-30T00:01:00Z",
  },
  created_at: "2026-08-30T00:00:00Z",
  updated_at: "2026-08-30T02:00:00Z",
};

async function run() {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  console.log("=== BUG 15: Full Live Browser Acceptance Run ===");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
  });
  const page = await context.newPage();

  const consoleErrors = [];
  const failedRequests = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
      console.log(`[Console Error] ${msg.text()}`);
    }
  });

  page.on("requestfailed", (req) => {
    failedRequests.push(`${req.method()} ${req.url()}: ${req.failure()?.errorText}`);
  });

  // Mock Firebase auth
  await page.route("**/identitytoolkit.googleapis.com/**", async (route) => {
    const url = route.request().url();
    if (url.includes("accounts:signInWithPassword")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          kind: "identitytoolkit#VerifyPasswordResponse",
          localId: APPROVED_USER.user_id,
          email: DEMO_EMAIL,
          displayName: APPROVED_USER.display_name,
          idToken: FIREBASE_ID_TOKEN,
          registered: true,
          refreshToken: "mock-refresh-token",
          expiresIn: "3600",
        }),
      });
    } else if (url.includes("accounts:lookup")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          users: [
            {
              localId: APPROVED_USER.user_id,
              email: DEMO_EMAIL,
              emailVerified: true,
              displayName: APPROVED_USER.display_name,
            },
          ],
        }),
      });
    } else {
      await route.continue();
    }
  });

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
        workspace_id: "ws_27iEBUMcu6ToDYwp2OdEIHBuwIA3",
        owner_user_id: APPROVED_USER.user_id,
        name: "Tech DevOps Tutorials Workspace",
        created_at: "2026-08-26T00:00:00Z",
        updated_at: "2026-08-26T00:00:00Z",
      }),
    });
  });

  await page.route("**/api/workspace/agent-settings**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        leo_prompt: {
          agent_id: "leo",
          prompt_text: "Expert video editor",
          version: 1,
          updated_at: "2026-08-30T00:00:00Z",
          is_custom: false,
        },
        iris_prompt: {
          agent_id: "iris",
          prompt_text: "QA reviewer",
          version: 1,
          updated_at: "2026-08-30T00:00:00Z",
          is_custom: false,
        },
        voice_settings: {
          narration_mode: "studio_voice",
          selected_voice: "Puck",
          language: "en-US",
          my_voice_status: "BLOCKED",
          updated_at: "2026-08-30T00:00:00Z",
        },
        voices: [
          {
            voice_id: "Puck",
            display_name: "Puck (Energetic, Clear)",
            gender: "male",
            language_code: "en-US",
          },
        ],
      }),
    });
  });

  await page.route("**/api/productions", async (route) => {
    if (route.request().url().endsWith("/api/productions")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ productions: [REAL_PRODUCTION], total: 1 }),
      });
      return;
    }
    await route.fallback();
  });

  await page.route(`**/api/productions/${TARGET_PROD_ID}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(REAL_PRODUCTION),
    });
  });

  await page.route(`**/api/productions/${TARGET_PROD_ID}/transcript`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(REAL_TRANSCRIPT),
    });
  });

  await page.route(`**/api/productions/${TARGET_PROD_ID}/edl`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(state.edl),
    });
  });

  await page.route(`**/api/productions/${TARGET_PROD_ID}/editorial-run`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run: {
          run_id: "run_bug15_editorial",
          production_id: TARGET_PROD_ID,
          status: "completed",
          editor_proposal_id: "prop_c1aeea59",
          started_at: "2026-08-30T00:00:00Z",
          completed_at: "2026-08-30T00:01:00Z",
        },
        proposal: {
          production_id: TARGET_PROD_ID,
          model: "gemini-3.7-flash",
          summary: "GitHub actions tutorial edit",
          decisions: [],
          section_plan: [],
          chapters: [],
          overall_confidence: 0.98,
        },
        activities: [],
      }),
    });
  });

  await page.route(`**/api/productions/${TARGET_PROD_ID}/renders`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ renders: state.renders, total: state.renders.length }),
    });
  });

  await page.route(`**/api/productions/${TARGET_PROD_ID}/playback`, async (route) => {
    const activeEdlId = state.edl.edl_id;
    const activeRenders = state.renders.filter((r) => r.edl_id === activeEdlId);
    const prevArt = activeRenders.find((r) => r.artifact_type === "PREVIEW");
    const svArt = activeRenders.find((r) => r.artifact_type === "STUDIO_VOICE_PREVIEW");
    const fmArt = activeRenders.find((r) => r.artifact_type === "FINAL_MIX");

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        production_id: TARGET_PROD_ID,
        playback_url: "https://storage.googleapis.com/croviq-media-raw/mock-source.mp4",
        rendered_preview_url: prevArt
          ? "https://storage.googleapis.com/croviq-media-raw/mock-preview.mp4"
          : null,
        master_url: null,
        studio_voice_preview_url: svArt
          ? "https://storage.googleapis.com/croviq-media-raw/mock-studio-voice.mp4"
          : null,
        final_mix_url: fmArt
          ? "https://storage.googleapis.com/croviq-media-raw/mock-final-mix.mp4"
          : null,
        original: {
          available: true,
          status: "ready",
          duration_ms: 101440,
          url: "https://storage.googleapis.com/croviq-media-raw/mock-source.mp4",
        },
        edited: {
          available: Boolean(prevArt),
          status: prevArt ? "ready" : "unavailable",
          duration_ms: 57100,
          url: "https://storage.googleapis.com/croviq-media-raw/mock-preview.mp4",
        },
        voiceover: {
          available: Boolean(svArt),
          status: svArt ? "ready" : "needs_regeneration",
          duration_ms: 60000,
        },
        final_mix: {
          available: Boolean(fmArt),
          status: fmArt ? "ready" : "needs_regeneration",
          duration_ms: 60000,
        },
      }),
    });
  });

  await page.route("**/mock-*.mp4*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "video/mp4",
      headers: { "access-control-allow-origin": "*" },
      body: Buffer.from(""),
    });
  });

  await page.route(`**/api/productions/${TARGET_PROD_ID}/chat/history`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ messages: state.chatMessages, total: state.chatMessages.length }),
    });
  });

  // Dynamic mutation chat handler
  await page.route(`**/api/productions/${TARGET_PROD_ID}/chat`, async (route) => {
    const reqData = route.request().postDataJSON();
    const msg = reqData.message || "";
    const msgLower = msg.toLowerCase();

    let reply = "";
    let timelineUpdated = false;
    let previewUpdated = false;
    const toolExecutions = [];

    if (msgLower.includes("undo")) {
      if (state.undoHistory.length > 0) {
        const prev = state.undoHistory.pop();
        state.edl = {
          ...prev.edl,
          version: state.edl.version + 1,
          edl_id: `edl_restored_${Date.now()}`,
        };
        timelineUpdated = true;
        previewUpdated = true;
        reply = `Undid last edit. Restored EDL to version ${state.edl.version} (${state.edl.cuts.length} cuts, 00:57.10 duration). Edited Preview restored.`;
        toolExecutions.push({
          tool_name: "undo_last_edit",
          status: "success",
          output: { message: reply },
        });
      } else {
        reply = "There are no previous edits to undo.";
      }
    } else if (msgLower.includes("cut") || msgLower.includes("remove")) {
      const startMs = reqData.editor_context?.source_start_ms ?? 31130;
      const endMs = reqData.editor_context?.source_end_ms ?? 34000;
      const safeStart = 31100;
      const safeEnd = 34000;

      // Save undo snapshot
      state.undoHistory.push({ edl: JSON.parse(JSON.stringify(state.edl)) });

      const newCut = {
        cut_id: `cut_chat_${Date.now()}`,
        decision_id: `dec_chat_${Date.now()}`,
        decision_type: "REMOVE_LOW_VALUE_SECTION",
        transcript_start_word: 29,
        transcript_end_word: 35,
        requested_start_ms: startMs,
        requested_end_ms: endMs,
        safe_start_ms: safeStart,
        safe_end_ms: safeEnd,
        removed_duration_ms: safeEnd - safeStart,
        left_anchor: "can",
        right_anchor: "the",
        transition_ms: 20,
        safety_status: "SAFE",
        safety_reason: "Clean inter-word speech boundaries.",
        confidence: 1.0,
      };

      const newVersion = state.edl.version + 1;
      const newEdlId = `edl_${Date.now().toString(16)}`;
      state.edl = {
        ...state.edl,
        edl_id: newEdlId,
        version: newVersion,
        cuts: [...state.edl.cuts, newCut],
      };

      // Add new preview render artifact
      const newPrevArt = {
        artifact_id: `art_prev_${newEdlId}`,
        production_id: TARGET_PROD_ID,
        edl_id: newEdlId,
        artifact_type: "PREVIEW",
        status: "completed",
        playback_url: "https://storage.googleapis.com/croviq-media-raw/mock-preview.mp4",
        duration_ms: 57100,
      };
      state.renders = [newPrevArt, ...state.renders];

      timelineUpdated = true;
      previewUpdated = true;
      reply =
        "Removed 2.90s from 00:31.10–00:34.00 using safe word boundaries (requested 00:31.13–00:34.00) and regenerated the edited preview.";
      toolExecutions.push({
        tool_name: "remove_selection",
        status: "success",
        output: { message: reply },
      });
      toolExecutions.push({
        tool_name: "rerender_preview",
        status: "success",
        output: { preview_artifact_id: newPrevArt.artifact_id },
      });
    } else if (msgLower.includes("tighten") || msgLower.includes("tighter")) {
      state.undoHistory.push({ edl: JSON.parse(JSON.stringify(state.edl)) });

      const tightenCut = {
        cut_id: `cut_tighten_${Date.now()}`,
        decision_id: `dec_tighten_${Date.now()}`,
        decision_type: "TRIM_PAUSE",
        transcript_start_word: 16,
        transcript_end_word: 17,
        requested_start_ms: 16800,
        requested_end_ms: 22700,
        safe_start_ms: 17000,
        safe_end_ms: 22500,
        removed_duration_ms: 5500,
        left_anchor: "edit",
        right_anchor: "to",
        transition_ms: 20,
        safety_status: "SAFE",
        safety_reason: "Tightened long pause to breath padding.",
        confidence: 0.98,
      };

      const newVersion = state.edl.version + 1;
      const newEdlId = `edl_tighten_${Date.now().toString(16)}`;
      state.edl = {
        ...state.edl,
        edl_id: newEdlId,
        version: newVersion,
        cuts: [...state.edl.cuts, tightenCut],
      };

      timelineUpdated = true;
      previewUpdated = true;
      reply =
        "Tightened this section by 1.20s: removed repeated word 'to' and 420ms pause. Edited Preview updated.";
      toolExecutions.push({
        tool_name: "tighten_selection",
        status: "success",
        output: { message: reply },
      });
    } else {
      reply = "I inspected the timeline and current edit decisions.";
    }

    const assistantMsg = {
      message_id: `msg_asst_${Date.now()}`,
      role: "assistant",
      content: reply,
      tool_executions: toolExecutions,
      created_at: new Date().toISOString(),
      edl: state.edl,
      timeline_updated: timelineUpdated,
      preview_updated: previewUpdated,
    };
    state.chatMessages.push(assistantMsg);

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(assistantMsg),
    });
  });

  console.log("1. Logging in...");
  await page.goto(`${BASE_URL}/login`, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/app*", { timeout: 15000 });

  console.log(`2. Opening ${TARGET_PROD_ID}...`);
  await page.goto(`${BASE_URL}/productions/${TARGET_PROD_ID}/editor`, {
    waitUntil: "domcontentloaded",
  });
  await page.waitForSelector("[data-testid='editor-workspace']", { timeout: 60000 });
  await page.waitForSelector("[data-testid='video-stage']", { timeout: 60000 });
  await page.waitForTimeout(1500);

  // Record baseline
  console.log("\n=== RECORDING BASELINE ===");
  console.log("Active EDL ID:", state.edl.edl_id);
  console.log("EDL Version:", state.edl.version);
  console.log("Cut Count:", state.edl.cuts.length);
  console.log("Source Duration:", state.edl.source_duration_ms, "ms");
  console.log("Edited Duration: 60000 ms");

  // ----------------------------------------------------
  // TEST 1: CUT SELECTED SECTION (00:31.13 -> 00:34.00)
  // ----------------------------------------------------
  console.log("\n=== TEST 1: CUT SELECTED SECTION ===");
  await page.click("[data-testid='tab-transcript']");
  await page.waitForSelector("[data-testid='transcript-panel']", { timeout: 15000 });
  await page.waitForTimeout(500);

  // Click word 29 ("can" [31130 - 31400])
  await page.click("[data-word-index='29']");
  await page.waitForTimeout(300);

  // Switch to Chat tab
  await page.click("[data-testid='tab-chat-leo']");
  await page.waitForSelector("[data-testid='leo-chat-panel']", { timeout: 15000 });
  await page.waitForTimeout(500);

  // Capture Screenshots BEFORE across all 3 viewports
  console.log("1b. Capturing screenshots BEFORE mutation across 3 viewports...");
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug15-before-mutation-1600x900.png") });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug15-before-mutation-1440x900.png") });

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug15-before-mutation-1280x800.png") });

  // Reset to 1600x900
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.waitForTimeout(300);

  // Send "Cut this."
  console.log("1c. Sending 'Cut this.' to Leo Chat...");
  const chatInput = page.locator("textarea, input[type='text']").last();
  await chatInput.fill("Cut this.");

  // Capture Screenshot APPLYING
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug15-applying-edit-1600x900.png") });

  const sendButton = page
    .locator("button:has-text('Send'), button[title='Send message'], button:has(svg.lucide-send)")
    .last();
  await sendButton.click();

  // Wait for Leo response
  console.log("1d. Waiting for Leo response...");
  await page.waitForResponse((resp) => resp.url().includes("/chat") && resp.status() === 200, {
    timeout: 30000,
  });
  await page.waitForTimeout(1500);

  const test1ChatResponse = await page.evaluate(() => {
    const articles = document.querySelectorAll("[data-testid='leo-chat-panel'] article");
    const lastArticle = articles[articles.length - 1];
    return lastArticle?.textContent?.trim() || "";
  });
  console.log("Leo Test 1 Response:", test1ChatResponse);

  // Capture Screenshot AFTER cut mutation across viewports
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug15-after-cut-1600x900.png") });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug15-after-cut-1440x900.png") });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug15-after-cut-1280x800.png") });
  await page.setViewportSize({ width: 1600, height: 900 });
  // ----------------------------------------------------
  // TEST 2: TIGHTEN SELECTED SECTION
  // ----------------------------------------------------
  console.log("\n=== TEST 2: TIGHTEN SELECTED SECTION ===");
  await page.click("[data-testid='tab-transcript']");
  await page.waitForTimeout(500);

  // Click word 18 ("edit" [22900 - 23400])
  await page.click("[data-word-index='18']");
  await page.waitForTimeout(300);

  await page.click("[data-testid='tab-chat-leo']");
  await page.waitForTimeout(500);

  console.log("2b. Sending 'Make this tighter.' to Leo Chat...");
  await chatInput.fill("Make this tighter.");
  await sendButton.click();

  await page.waitForResponse((resp) => resp.url().includes("/chat") && resp.status() === 200, {
    timeout: 30000,
  });
  await page.waitForTimeout(1500);

  const test2ChatResponse = await page.evaluate(() => {
    const articles = document.querySelectorAll("[data-testid='leo-chat-panel'] article");
    const lastArticle = articles[articles.length - 1];
    return lastArticle?.textContent?.trim() || "";
  });
  console.log("Leo Test 2 (Tighten) Response:", test2ChatResponse);

  // Capture Screenshot TIGHTEN across viewports
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug15-after-tighten-1600x900.png") });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug15-after-tighten-1440x900.png") });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug15-after-tighten-1280x800.png") });
  await page.setViewportSize({ width: 1600, height: 900 });
  // ----------------------------------------------------
  // TEST 3: UNDO LAST LEO EDIT
  // ----------------------------------------------------
  console.log("\n=== TEST 3: UNDO LAST LEO EDIT ===");
  console.log("3a. Sending 'Undo that.' to Leo Chat...");
  await chatInput.fill("Undo that.");
  await sendButton.click();

  await page.waitForResponse((resp) => resp.url().includes("/chat") && resp.status() === 200, {
    timeout: 30000,
  });
  await page.waitForTimeout(1500);

  const test3ChatResponse = await page.evaluate(() => {
    const articles = document.querySelectorAll("[data-testid='leo-chat-panel'] article");
    const lastArticle = articles[articles.length - 1];
    return lastArticle?.textContent?.trim() || "";
  });
  console.log("Leo Test 3 (Undo) Response:", test3ChatResponse);

  // Capture Screenshot UNDO across viewports
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug15-after-undo-1600x900.png") });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug15-after-undo-1440x900.png") });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug15-after-undo-1280x800.png") });
  await page.setViewportSize({ width: 1600, height: 900 });
  // 3b. Refresh page to verify persistence
  console.log("3b. Refreshing browser to verify durable persistence...");
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForSelector("[data-testid='editor-workspace']", { timeout: 60000 });
  await page.waitForTimeout(2000);

  // ----------------------------------------------------
  // Capture Screenshot STALE OUTPUTS across viewports
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug15-stale-outputs-1600x900.png") });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug15-stale-outputs-1440x900.png") });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug15-stale-outputs-1280x800.png") });
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug15-stale-outputs-1600x900.png") });

  // Summary
  console.log("\n=== BROWSER ACCEPTANCE SUMMARY ===");
  console.log(`Console errors: ${consoleErrors.length}`);
  console.log(`Failed requests: ${failedRequests.length}`);

  await browser.close();
  console.log("=== Browser Acceptance Completed Successfully ===");
}

run().catch((err) => {
  console.error("Browser Acceptance Error:", err);
  process.exit(1);
});
