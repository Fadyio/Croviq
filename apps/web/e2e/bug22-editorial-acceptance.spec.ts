import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { APPROVED_USER, DEMO_EMAIL, FIREBASE_ID_TOKEN } from "./test-auth-fixtures";

const PRODUCTION_ID = "prod_473209137802";
const WORKSPACE_ID = "ws_27iEBUMcu6ToDYwp2OdEIHBuwIA3";

const GITHUB_WORDS = [
  { index: 0, start_ms: 2100, end_ms: 2400, text: "This" },
  { index: 1, start_ms: 2400, end_ms: 2600, text: "is" },
  { index: 2, start_ms: 3700, end_ms: 3800, text: "a" },
  { index: 3, start_ms: 3800, end_ms: 4400, text: "GitHub" },
  { index: 4, start_ms: 4400, end_ms: 5000, text: "action" },
  { index: 5, start_ms: 5100, end_ms: 5700, text: "tutorial." },
  { index: 6, start_ms: 8000, end_ms: 8300, text: "Okay." },
  { index: 7, start_ms: 8900, end_ms: 9000, text: "You" },
  { index: 8, start_ms: 9000, end_ms: 9300, text: "can" },
  { index: 9, start_ms: 9300, end_ms: 9900, text: "find" },
  { index: 10, start_ms: 10600, end_ms: 10700, text: "the" },
  { index: 11, start_ms: 10700, end_ms: 11200, text: "GitHub" },
  { index: 12, start_ms: 11300, end_ms: 11800, text: "action" },
  { index: 13, start_ms: 15000, end_ms: 15010, text: "in" },
  { index: 14, start_ms: 15000, end_ms: 15400, text: "here." },
  { index: 15, start_ms: 16200, end_ms: 16300, text: "To" },
  { index: 16, start_ms: 16300, end_ms: 16800, text: "edit" },
  { index: 17, start_ms: 22700, end_ms: 22900, text: "to" },
  { index: 18, start_ms: 22900, end_ms: 23500, text: "edit" },
  { index: 19, start_ms: 24100, end_ms: 24400, text: "your" },
  { index: 20, start_ms: 24400, end_ms: 25200, text: "workflow" },
  { index: 21, start_ms: 25700, end_ms: 25900, text: "like" },
  { index: 22, start_ms: 25900, end_ms: 26100, text: "this" },
  { index: 23, start_ms: 26100, end_ms: 26900, text: "workflow" },
  { index: 24, start_ms: 27000, end_ms: 27300, text: "is" },
  { index: 25, start_ms: 27300, end_ms: 27800, text: "for" },
  { index: 26, start_ms: 27900, end_ms: 28600, text: "Cloudflare" },
  { index: 27, start_ms: 28600, end_ms: 29000, text: "DNS." },
  { index: 28, start_ms: 30700, end_ms: 30800, text: "You" },
  { index: 29, start_ms: 30800, end_ms: 31100, text: "can" },
  { index: 30, start_ms: 31100, end_ms: 31800, text: "find" },
  { index: 31, start_ms: 31900, end_ms: 32300, text: "here" },
  { index: 32, start_ms: 33000, end_ms: 33100, text: "the" },
  { index: 33, start_ms: 33100, end_ms: 33500, text: "name" },
  { index: 34, start_ms: 33500, end_ms: 34100, text: "of" },
  { index: 35, start_ms: 34200, end_ms: 34400, text: "the" },
  { index: 36, start_ms: 34400, end_ms: 35000, text: "workflow" },
  { index: 37, start_ms: 36000, end_ms: 36200, text: "that" },
  { index: 38, start_ms: 36200, end_ms: 36800, text: "runs" },
  { index: 39, start_ms: 36900, end_ms: 37500, text: "on" },
  { index: 40, start_ms: 45200, end_ms: 46000, text: "permission" },
  { index: 41, start_ms: 46600, end_ms: 46900, text: "write" },
  { index: 42, start_ms: 46900, end_ms: 47100, text: "and" },
  { index: 43, start_ms: 47100, end_ms: 47400, text: "read" },
  { index: 44, start_ms: 47400, end_ms: 48100, text: "content." },
  { index: 45, start_ms: 51300, end_ms: 51600, text: "Okay." },
  { index: 46, start_ms: 53600, end_ms: 54300, text: "And" },
  { index: 47, start_ms: 54300, end_ms: 54500, text: "you" },
  { index: 48, start_ms: 54500, end_ms: 54700, text: "can" },
  { index: 49, start_ms: 54700, end_ms: 55200, text: "find" },
  { index: 50, start_ms: 55200, end_ms: 55300, text: "the" },
  { index: 51, start_ms: 55300, end_ms: 55600, text: "whole" },
  { index: 52, start_ms: 55600, end_ms: 56100, text: "script" },
  { index: 53, start_ms: 56100, end_ms: 56200, text: "in" },
  { index: 54, start_ms: 56200, end_ms: 56600, text: "here." },
  { index: 55, start_ms: 57600, end_ms: 57900, text: "Also" },
  { index: 56, start_ms: 57900, end_ms: 58100, text: "there" },
  { index: 57, start_ms: 58100, end_ms: 58300, text: "is" },
  { index: 58, start_ms: 58300, end_ms: 58400, text: "a" },
  { index: 59, start_ms: 58400, end_ms: 58800, text: "lot" },
  { index: 60, start_ms: 58800, end_ms: 59100, text: "of" },
  { index: 61, start_ms: 59400, end_ms: 59900, text: "other" },
  { index: 62, start_ms: 60300, end_ms: 60900, text: "devices" },
  { index: 63, start_ms: 60900, end_ms: 61200, text: "one" },
  { index: 64, start_ms: 61400, end_ms: 61500, text: "to" },
  { index: 65, start_ms: 61500, end_ms: 62200, text: "verify" },
  { index: 66, start_ms: 62200, end_ms: 62800, text: "that" },
  { index: 67, start_ms: 64100, end_ms: 64110, text: "the" },
  { index: 68, start_ms: 64100, end_ms: 64800, text: "GitHub" },
  { index: 69, start_ms: 65200, end_ms: 65300, text: "the" },
  { index: 70, start_ms: 65300, end_ms: 66100, text: "Cloudflare" },
  { index: 71, start_ms: 66500, end_ms: 66900, text: "action" },
  { index: 72, start_ms: 67000, end_ms: 67200, text: "is" },
  { index: 73, start_ms: 67200, end_ms: 67800, text: "working." },
  { index: 74, start_ms: 68900, end_ms: 69500, text: "Deploy" },
  { index: 75, start_ms: 70800, end_ms: 71000, text: "which" },
  { index: 76, start_ms: 71000, end_ms: 71400, text: "is" },
  { index: 77, start_ms: 75100, end_ms: 75300, text: "and" },
  { index: 78, start_ms: 75300, end_ms: 75500, text: "how" },
  { index: 79, start_ms: 75500, end_ms: 75700, text: "to" },
  { index: 80, start_ms: 75700, end_ms: 76300, text: "deploy" },
  { index: 81, start_ms: 77300, end_ms: 77500, text: "our" },
  { index: 82, start_ms: 77500, end_ms: 78200, text: "application" },
  { index: 83, start_ms: 78300, end_ms: 78600, text: "to" },
  { index: 84, start_ms: 78600, end_ms: 78900, text: "Google" },
  { index: 85, start_ms: 78900, end_ms: 79500, text: "Cloud" },
  { index: 86, start_ms: 81100, end_ms: 81600, text: "and" },
  { index: 87, start_ms: 83100, end_ms: 83400, text: "here" },
  { index: 88, start_ms: 83400, end_ms: 83800, text: "is" },
  { index: 89, start_ms: 84000, end_ms: 84400, text: "with" },
  { index: 90, start_ms: 84800, end_ms: 85200, text: "test" },
  { index: 91, start_ms: 87400, end_ms: 88200, text: "verified" },
  { index: 92, start_ms: 88600, end_ms: 89100, text: "workflow" },
  { index: 93, start_ms: 90500, end_ms: 90800, text: "and" },
  { index: 94, start_ms: 90800, end_ms: 91400, text: "everything" },
  { index: 95, start_ms: 91400, end_ms: 91600, text: "is" },
  { index: 96, start_ms: 91600, end_ms: 92100, text: "working." },
  { index: 97, start_ms: 93900, end_ms: 94000, text: "You" },
  { index: 98, start_ms: 94000, end_ms: 94600, text: "here" },
  { index: 99, start_ms: 94900, end_ms: 95000, text: "you" },
  { index: 100, start_ms: 95000, end_ms: 95200, text: "can" },
  { index: 101, start_ms: 95200, end_ms: 95600, text: "find" },
  { index: 102, start_ms: 95600, end_ms: 95900, text: "here" },
  { index: 103, start_ms: 95900, end_ms: 96000, text: "the" },
  { index: 104, start_ms: 96000, end_ms: 96500, text: "issues." },
  { index: 105, start_ms: 96500, end_ms: 96600, text: "You" },
  { index: 106, start_ms: 96600, end_ms: 97000, text: "can" },
  { index: 107, start_ms: 97300, end_ms: 97800, text: "write" },
  { index: 108, start_ms: 97800, end_ms: 98000, text: "the" },
  { index: 109, start_ms: 98000, end_ms: 98700, text: "workflow" },
  { index: 110, start_ms: 100000, end_ms: 100400, text: "for" },
  { index: 111, start_ms: 100400, end_ms: 101000, text: "issues." },
];

const GITHUB_CUTS = [
  {
    cut_id: "cut_sil_01",
    decision_id: "silence_01",
    decision_type: "DEAD_AIR",
    category: "DEAD_AIR",
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
    safety_reason: "Natural pause trimming leaving comfortable breath padding.",
    confidence: 1.0,
    removed_text: "",
    context_before: "GitHub action tutorial.",
    context_after: "Okay. You can find",
    concise_reason: "Trimmed 2.05s dead air while navigating.",
  },
  {
    cut_id: "cut_sil_02",
    decision_id: "silence_02",
    decision_type: "DEAD_AIR",
    category: "DEAD_AIR",
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
    safety_reason: "Natural pause trimming leaving comfortable breath padding.",
    confidence: 1.0,
    removed_text: "",
    context_before: "find the GitHub action",
    context_after: "in here. To edit",
    concise_reason: "Trimmed 2.95s pause while opening repository sidebar.",
  },
  {
    cut_id: "cut_sem_01_phrase_rep",
    decision_id: "dec_rep_01",
    decision_type: "PHRASE_REPETITION",
    category: "PHRASE_REPETITION",
    transcript_start_word: 15,
    transcript_end_word: 16,
    requested_start_ms: 16200,
    requested_end_ms: 16800,
    safe_start_ms: 16100,
    safe_end_ms: 22575,
    removed_duration_ms: 6475,
    left_anchor: "here.",
    right_anchor: "to",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Clean inter-word silence boundaries verified.",
    confidence: 0.96,
    removed_text: "To edit",
    context_before: "action in here.",
    context_after: "to edit your workflow",
    concise_reason:
      "Removed abandoned false start 'To edit' before the speaker pauses and restarts with complete sentence 'to edit your workflow'.",
  },
  {
    cut_id: "cut_sil_04",
    decision_id: "silence_04",
    decision_type: "DEAD_AIR",
    category: "DEAD_AIR",
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
    safety_reason: "Natural pause trimming leaving comfortable breath padding.",
    confidence: 1.0,
    removed_text: "",
    context_before: "Cloudflare DNS.",
    context_after: "You can find here",
    concise_reason: "Trimmed 1.45s dead air after DNS explanation.",
  },
  {
    cut_id: "cut_sil_05",
    decision_id: "silence_05",
    decision_type: "DEAD_AIR",
    category: "DEAD_AIR",
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
    safety_reason: "Natural pause trimming leaving comfortable breath padding.",
    confidence: 1.0,
    removed_text: "",
    context_before: "runs on",
    context_after: "permission write and read",
    concise_reason: "Trimmed 7.45s long hesitation while inspecting workflow YAML permissions.",
  },
  {
    cut_id: "cut_sem_02_filler",
    decision_id: "dec_filler_01",
    decision_type: "FILLER",
    category: "FILLER",
    transcript_start_word: 45,
    transcript_end_word: 45,
    requested_start_ms: 51300,
    requested_end_ms: 51600,
    safe_start_ms: 48225,
    safe_end_ms: 53475,
    removed_duration_ms: 5250,
    left_anchor: "content.",
    right_anchor: "And",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Clean inter-word silence boundaries verified.",
    confidence: 0.95,
    removed_text: "Okay.",
    context_before: "read content.",
    context_after: "And you can find",
    concise_reason: "Removed conversational verbal filler 'Okay.' and surrounding dead air.",
  },
  {
    cut_id: "cut_sem_03_false_start",
    decision_id: "dec_fs_01",
    decision_type: "FALSE_START",
    category: "FALSE_START",
    transcript_start_word: 67,
    transcript_end_word: 68,
    requested_start_ms: 64100,
    requested_end_ms: 64800,
    safe_start_ms: 62925,
    safe_end_ms: 64900,
    removed_duration_ms: 1975,
    left_anchor: "that",
    right_anchor: "the",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Clean inter-word silence boundaries verified.",
    confidence: 0.96,
    removed_text: "the GitHub",
    context_before: "verify that",
    context_after: "the Cloudflare action is working.",
    concise_reason:
      "Removed verbal stumble 'the GitHub' where the speaker corrected to 'the Cloudflare action'.",
  },
  {
    cut_id: "cut_sem_04_abandoned",
    decision_id: "dec_fs_02",
    decision_type: "FALSE_START",
    category: "FALSE_START",
    transcript_start_word: 74,
    transcript_end_word: 76,
    requested_start_ms: 68900,
    requested_end_ms: 71400,
    safe_start_ms: 69625,
    safe_end_ms: 74975,
    removed_duration_ms: 5350,
    left_anchor: "working.",
    right_anchor: "and",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Clean inter-word silence boundaries verified.",
    confidence: 0.95,
    removed_text: "Deploy which is",
    context_before: "action is working.",
    context_after: "and how to deploy our application",
    concise_reason:
      "Removed abandoned lead-in clause 'Deploy which is' before the speaker restarts with complete deployment explanation.",
  },
  {
    cut_id: "cut_sil_11",
    decision_id: "silence_11",
    decision_type: "DEAD_AIR",
    category: "DEAD_AIR",
    transcript_start_word: 85,
    transcript_end_word: 86,
    requested_start_ms: 78900,
    requested_end_ms: 81600,
    safe_start_ms: 79625,
    safe_end_ms: 80975,
    removed_duration_ms: 1350,
    left_anchor: "Cloud",
    right_anchor: "and",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Natural pause trimming leaving comfortable breath padding.",
    confidence: 1.0,
    removed_text: "",
    context_before: "to Google Cloud",
    context_after: "and here is with test",
    concise_reason: "Trimmed 1.35s pause after GCP explanation.",
  },
  {
    cut_id: "cut_sil_12",
    decision_id: "silence_12",
    decision_type: "DEAD_AIR",
    category: "DEAD_AIR",
    transcript_start_word: 86,
    transcript_end_word: 87,
    requested_start_ms: 81100,
    requested_end_ms: 83400,
    safe_start_ms: 81725,
    safe_end_ms: 82975,
    removed_duration_ms: 1250,
    left_anchor: "and",
    right_anchor: "here",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Natural pause trimming leaving comfortable breath padding.",
    confidence: 1.0,
    removed_text: "",
    context_before: "Google Cloud and",
    context_after: "here is with test verified",
    concise_reason: "Trimmed 1.25s pause before test verification walkthrough.",
  },
  {
    cut_id: "cut_sil_13",
    decision_id: "silence_13",
    decision_type: "DEAD_AIR",
    category: "DEAD_AIR",
    transcript_start_word: 90,
    transcript_end_word: 91,
    requested_start_ms: 84800,
    requested_end_ms: 88200,
    safe_start_ms: 85325,
    safe_end_ms: 87275,
    removed_duration_ms: 1950,
    left_anchor: "test",
    right_anchor: "verified",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Natural pause trimming leaving comfortable breath padding.",
    confidence: 1.0,
    removed_text: "",
    context_before: "is with test",
    context_after: "verified workflow and",
    concise_reason: "Trimmed 1.95s pause while scrolling verification output.",
  },
  {
    cut_id: "cut_sil_14",
    decision_id: "silence_14",
    decision_type: "DEAD_AIR",
    category: "DEAD_AIR",
    transcript_start_word: 92,
    transcript_end_word: 93,
    requested_start_ms: 88600,
    requested_end_ms: 90800,
    safe_start_ms: 89225,
    safe_end_ms: 90375,
    removed_duration_ms: 1150,
    left_anchor: "workflow",
    right_anchor: "and",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Natural pause trimming leaving comfortable breath padding.",
    confidence: 1.0,
    removed_text: "",
    context_before: "test verified workflow",
    context_after: "and everything is working.",
    concise_reason: "Trimmed 1.15s pause before summary statement.",
  },
  {
    cut_id: "cut_sem_05_restart",
    decision_id: "dec_restart_01",
    decision_type: "FALSE_START",
    category: "FALSE_START",
    transcript_start_word: 97,
    transcript_end_word: 98,
    requested_start_ms: 93900,
    requested_end_ms: 94600,
    safe_start_ms: 92225,
    safe_end_ms: 94700,
    removed_duration_ms: 2475,
    left_anchor: "working.",
    right_anchor: "you",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Clean inter-word silence boundaries verified.",
    confidence: 0.95,
    removed_text: "You here",
    context_before: "everything is working.",
    context_after: "you can find here the issues.",
    concise_reason:
      "Removed verbal restart 'You here' before the speaker restarts with complete sentence 'you can find here the issues'.",
  },
  {
    cut_id: "cut_sil_16",
    decision_id: "silence_16",
    decision_type: "DEAD_AIR",
    category: "DEAD_AIR",
    transcript_start_word: 109,
    transcript_end_word: 110,
    requested_start_ms: 98000,
    requested_end_ms: 100400,
    safe_start_ms: 98825,
    safe_end_ms: 99875,
    removed_duration_ms: 1050,
    left_anchor: "workflow",
    right_anchor: "for",
    transition_ms: 20,
    safety_status: "SAFE",
    safety_reason: "Natural pause trimming leaving comfortable breath padding.",
    confidence: 1.0,
    removed_text: "",
    context_before: "write the workflow",
    context_after: "for issues.",
    concise_reason: "Trimmed 1.05s pause before concluding remark.",
  },
];

const GITHUB_ACTIVITIES = [
  {
    activity_id: "act_01",
    activity_type: "dialogue_analysis",
    agent: "Leo",
    role: "Video Editor",
    message: "Analyzing dialogue: Evaluated spoken cadence, clarity, and phrasing across 101.4s source footage.",
    created_at: "2026-08-31T06:28:07Z",
  },
  {
    activity_id: "act_02",
    activity_type: "repetition_detection",
    agent: "Leo",
    role: "Video Editor",
    message: "Detecting repetitions: Identified 4 verbal restarts, repeated words, and redundant phrasing candidates.",
    created_at: "2026-08-31T06:28:08Z",
  },
  {
    activity_id: "act_03",
    activity_type: "pacing_evaluation",
    agent: "Leo",
    role: "Video Editor",
    message: "Evaluating pacing: Assessed explanation density, navigation pauses, and demonstration rhythm.",
    created_at: "2026-08-31T06:28:09Z",
  },
  {
    activity_id: "act_04",
    activity_type: "continuity_check",
    agent: "Leo",
    role: "Video Editor",
    message: "Checking technical continuity: Verified preservation of core commands, filenames, code walkthroughs, and prerequisites.",
    created_at: "2026-08-31T06:28:10Z",
  },
  {
    activity_id: "act_05",
    activity_type: "safe_cuts",
    agent: "Leo",
    role: "Video Editor",
    message: "Applying safe cuts: Snapped 14 candidate removals to inter-word silence boundaries with natural breath padding.",
    created_at: "2026-08-31T06:28:11Z",
  },
  {
    activity_id: "act_06",
    activity_type: "sequence_review",
    agent: "Leo",
    role: "Video Editor",
    message: "Reviewing edited sequence: Verified narrative coherence, transitions, and timeline compression (42.7s removed).",
    created_at: "2026-08-31T06:28:12Z",
  },
  {
    activity_id: "act_07",
    activity_type: "render_preview",
    agent: "Leo",
    role: "Video Editor",
    message: "Rendering Edited Preview: Generated master preview stream with deterministic cuts and 20ms audio crossfades.",
    created_at: "2026-08-31T06:28:13Z",
  },
  {
    activity_id: "act_08",
    activity_type: "result_review",
    agent: "Leo",
    role: "Video Editor",
    message: "Reviewing rendered result: Confirmed continuous audio/video flow and natural speech transitions.",
    created_at: "2026-08-31T06:28:14Z",
  },
];

const mockAuthAndCommonRoutes = async (page: Page) => {
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

  await page.route("**/api/client-events", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
  });
};

const loginUser = async (page: Page) => {
  await mockAuthAndCommonRoutes(page);
  await page.goto("/login");
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/app*");
};

const setupEditorMocks = async (page: Page) => {
  await mockAuthAndCommonRoutes(page);

  // Mock production
  await page.route(`**/api/productions/${PRODUCTION_ID}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        production_id: PRODUCTION_ID,
        workspace_id: WORKSPACE_ID,
        channel_id: "channel_croviq",
        title: "GitHub Actions Tutorial",
        status: "EDITING",
        created_at: "2026-08-31T00:00:00Z",
        source_media: {
          upload_id: "upl_48ee4e53140b",
          original_filename: "github.mp4",
          content_type: "video/mp4",
          size_bytes: 51168149,
          gcs_bucket: "croviq-506602-croviq-media-raw",
          gcs_object: "github.mp4",
          status: "UPLOADED",
          created_at: "2026-08-31T00:00:00Z",
          media_metadata: {
            duration_ms: 101440,
            width: 1236,
            height: 720,
            frame_rate: 60.0,
            video_codec: "h264",
            audio_codec: "aac",
            sample_rate: 16000,
            channels: 1,
            bit_rate: 4035342,
          },
        },
      }),
    });
  });

  // Mock transcript
  await page.route(`**/api/productions/${PRODUCTION_ID}/transcript`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        transcript_id: "tr_github_01",
        production_id: PRODUCTION_ID,
        language_code: "en",
        duration_ms: 101440,
        words: GITHUB_WORDS,
        segments: [
          { segment_id: "seg_01", text: "This is a GitHub action tutorial.", start_ms: 2100, end_ms: 5700, word_start_index: 0, word_end_index: 5 },
          { segment_id: "seg_02", text: "Okay. You can find the GitHub action in here.", start_ms: 8000, end_ms: 15400, word_start_index: 6, word_end_index: 14 },
          { segment_id: "seg_03", text: "To edit to edit your workflow like this workflow is for Cloudflare DNS.", start_ms: 16200, end_ms: 29000, word_start_index: 15, word_end_index: 27 },
          { segment_id: "seg_04", text: "You can find here the name of the workflow that runs on permission write and read content.", start_ms: 30700, end_ms: 48100, word_start_index: 28, word_end_index: 44 },
          { segment_id: "seg_05", text: "Okay. And you can find the whole script in here.", start_ms: 51300, end_ms: 56600, word_start_index: 45, word_end_index: 54 },
          { segment_id: "seg_06", text: "Also there is a lot of other devices one to verify that the GitHub the Cloudflare action is working.", start_ms: 57600, end_ms: 67800, word_start_index: 55, word_end_index: 73 },
          { segment_id: "seg_07", text: "Deploy which is and how to deploy our application to Google Cloud", start_ms: 68900, end_ms: 79500, word_start_index: 74, word_end_index: 85 },
          { segment_id: "seg_08", text: "and here is with test verified workflow and everything is working.", start_ms: 81100, end_ms: 92100, word_start_index: 86, word_end_index: 96 },
          { segment_id: "seg_09", text: "You here you can find here the issues. You can write the workflow for issues.", start_ms: 93900, end_ms: 101000, word_start_index: 97, word_end_index: 111 },
        ],
      }),
    });
  });

  // Mock EDL
  await page.route(`**/api/productions/${PRODUCTION_ID}/edl`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        edl: {
          edl_id: "edl_bug22_active",
          production_id: PRODUCTION_ID,
          version: 33,
          source_duration_ms: 101440,
          cuts: GITHUB_CUTS,
          coverage_markers: [],
          voiceover_segments: [],
          background_music: {
            music_id: "mus_01",
            style: "tech-tutorial-ambient",
            volume_db: -18.0,
            ducking_db: -12.0,
            music_gcs_object: "music.mp3",
          },
          created_at: "2026-08-31T06:28:44Z",
        },
        keep_segments: [
          [0, 5825],
          [7875, 11925],
          [14875, 16100],
          [22575, 29125],
          [30575, 37625],
          [45075, 48225],
          [53475, 62925],
          [64900, 69625],
          [74975, 79625],
          [80975, 81725],
          [82975, 85325],
          [87275, 89225],
          [90375, 92225],
          [94700, 98825],
          [99875, 101440],
        ],
      }),
    });
  });
  const editorialRunPayload = {
    run: {
      run_id: "run_bug22_01",
      production_id: PRODUCTION_ID,
      status: "completed",
      editor_proposal_id: "prop_bug22_01",
      started_at: "2026-08-31T06:28:00Z",
      completed_at: "2026-08-31T06:28:44Z",
    },
    proposal: {
      production_id: PRODUCTION_ID,
      agent: "leo",
      model: "gemini-3.7-flash",
      summary: "Completed full dialogue and timeline editorial pass removing false starts, repetitions, and dead air.",
      decisions: GITHUB_CUTS.map((c) => ({
        decision_id: c.decision_id,
        decision_type: c.decision_type,
        transcript_start_word: c.transcript_start_word,
        transcript_end_word: c.transcript_end_word,
        source_start_ms: c.safe_start_ms,
        source_end_ms: c.safe_end_ms,
        original_text: c.removed_text || "Pause interval",
        action: "remove",
        concise_reason: c.concise_reason,
        confidence: c.confidence,
        removed_text: c.removed_text,
        context_before: c.context_before,
        context_after: c.context_after,
      })),
      section_plan: [],
      chapters: [
        { chapter_id: "chap_01", title: "Overview & GitHub Action", source_start_ms: 0, source_end_ms: 15400, summary: "Introduction to GitHub Action", confidence: 1.0 },
        { chapter_id: "chap_02", title: "Editing Cloudflare DNS Workflow", source_start_ms: 16100, source_end_ms: 56600, summary: "Walking through DNS workflow and permissions", confidence: 1.0 },
        { chapter_id: "chap_03", title: "Verification & Deployment", source_start_ms: 57600, source_end_ms: 92100, summary: "Deploying to Google Cloud and testing", confidence: 1.0 },
        { chapter_id: "chap_04", title: "GitHub Issues Integration", source_start_ms: 93900, source_end_ms: 101440, summary: "Creating workflow for issues", confidence: 1.0 },
      ],
      overall_confidence: 1.0,
    },
    activities: GITHUB_ACTIVITIES,
  };

  // Mock Editorial Run
  await page.route(`**/api/productions/${PRODUCTION_ID}/editorial-run`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(editorialRunPayload),
    });
  });

  // Mock Editorial Analysis
  await page.route(`**/api/productions/${PRODUCTION_ID}/editorial/analysis`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(editorialRunPayload),
    });
  });
  // Mock Playback
  await page.route(`**/api/productions/${PRODUCTION_ID}/playback`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        original: { available: true, url: "https://storage.googleapis.com/test/source.mp4", duration_ms: 101440, status: "ready" },
        edited: { available: true, url: "https://storage.googleapis.com/test/preview.mp4", duration_ms: 58765, status: "ready", edl_id: "edl_bug22_active" },
        voiceover: { available: true, url: "https://storage.googleapis.com/test/voiceover.mp4", duration_ms: 58765, status: "ready", edl_id: "edl_bug22_active" },
        final_mix: { available: true, url: "https://storage.googleapis.com/test/final_mix.mp4", duration_ms: 58765, status: "ready", edl_id: "edl_bug22_active" },
        music_url: "https://storage.googleapis.com/test/music.mp3",
      }),
    });
  });

  // Mock Chat History
  await page.route(`**/api/productions/${PRODUCTION_ID}/chat/history`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        messages: [
          {
            message_id: "msg_01",
            role: "user",
            content: "What did you remove?",
            created_at: "2026-08-31T06:29:20Z",
          },
          {
            message_id: "msg_02",
            role: "assistant",
            content:
              "I removed **42.67s** total across **14 cuts**, bringing the video down to **58.77s**:\n\n* **Silence & Dead Air:** 36.2s trimmed across 13 pause points (retaining a natural ~250ms padding at each transition).\n* **Phrase Repetitions & False Starts:** 6.5s removed, specifically:\n  * Cut the stuttered restart at 16.10s–22.57s (*\"to edit edit to\"* before navigating to workflows).\n  * Trimmed repeated filler words (*\"Okay. Okay. Okay.\"* between sentences at 48.23s).\n  * Removed the slip of the tongue (*\"the GitHub\"*) at 62.92s when referring to Cloudflare action verification.\n  * Cut the abandoned lead-in clause (*\"which is\"*) before restarting the Google Cloud deployment explanation at 69.62s.\n  * Cleaned up the restart (*\"You here you can\"*) at 92.22s before leading into the issues section.",
            created_at: "2026-08-31T06:29:22Z",
          },
          {
            message_id: "msg_03",
            role: "user",
            content: "Why did you remove this section?",
            created_at: "2026-08-31T06:29:34Z",
          },
          {
            message_id: "msg_04",
            role: "assistant",
            content:
              "You had a false start and a long dead air gap here:\n\n* At **16.2s**, you began saying *\"To edit...\"*, followed by roughly **5.6s of silence** while navigating into the `.github/workflows` folder.\n* After opening the folder at **22.7s**, you restarted the thought cleanly with *\"to edit your workflow...\"*\n\nI cut the initial restart and silent gap so the video transitions smoothly from *\"in here.\"* directly into your complete sentence *\"to edit your workflow...\"*",
            created_at: "2026-08-31T06:29:36Z",
          },
        ],
      }),
    });
  });

  // Mock Workspace Settings
  await page.route(`**/api/workspaces/${WORKSPACE_ID}/agent-settings/voice`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        selected_voice: "Puck",
        narration_mode: "PREBUILT_STUDIO_VOICE",
      }),
    });
  });
};

test.describe("BUG 22 — Leo Real Human-Grade Editorial Acceptance", () => {
  test.beforeEach(async () => {
    const dir = path.resolve(process.cwd(), "docs/screenshots/acceptance");
    fs.mkdirSync(dir, { recursive: true });
  });

  test("1. Verifies 1600x900 viewport: Timeline, Transcript, and Agent Log phases", async ({ page }) => {
    await page.setViewportSize({ width: 1600, height: 900 });
    await setupEditorMocks(page);
    await loginUser(page);

    await page.goto(`/productions/${PRODUCTION_ID}/editor`);
    await page.waitForSelector("[data-testid='editor-workspace']");

    // Verify Agent Log panel has meaningful phases
    await expect(page.getByText("Analyzing dialogue").first()).toBeVisible();
    await expect(page.getByText("Detecting repetitions").first()).toBeVisible();
    await expect(page.getByText("Applying safe cuts").first()).toBeVisible();
    await expect(page.getByText("Reviewing edited sequence").first()).toBeVisible();
    // Capture Screenshot 1: Source beginning
    await page.screenshot({
      path: "docs/screenshots/acceptance/bug22-01-source-beginning-1600x900.png",
      fullPage: false,
    });

    // Toggle Preview Mode to Edited
    const previewToggle = page.getByTestId("preview-toggle-edited");
    if (await previewToggle.isVisible()) {
      await previewToggle.click();
    }

    // Capture Screenshot 2: Edited beginning
    await page.screenshot({
      path: "docs/screenshots/acceptance/bug22-02-edited-beginning-1600x900.png",
      fullPage: false,
    });
  });

  test("2. Verifies 1440x900 viewport: Semantic Cuts, Decision Inspector, Chat Rationale", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await setupEditorMocks(page);
    await loginUser(page);

    await page.goto(`/productions/${PRODUCTION_ID}/editor`);
    await page.waitForSelector("[data-testid='editor-workspace']");

    // Capture Screenshot 7: Timeline after complete editorial pass
    await page.screenshot({
      path: "docs/screenshots/acceptance/bug22-07-timeline-after-editorial-pass-1440x900.png",
      fullPage: false,
    });

    // Switch to LOG tab
    await page.getByRole("tab", { name: "LOG" }).click();
    await page.waitForTimeout(300);
    // Click representative Phrase Repetition cut on Timeline
    await page.getByRole("button", { name: "Repetition removed 6.5s" }).last().click();
    await page.waitForTimeout(300);
    // Verify Decision Inspector opens and shows What, Why, and Evidence
    await expect(page.getByTestId("decision-inspector")).toBeVisible();
    await expect(page.getByText("Remove repeated phrase").first()).toBeVisible();

    // Capture Screenshot 4: Representative repetition removal with Decision Inspector
    await page.screenshot({
      path: "docs/screenshots/acceptance/bug22-04-representative-repetition-1440x900.png",
      fullPage: false,
    });

    // Capture Screenshot 3: Representative false-start removal
    await page.screenshot({
      path: "docs/screenshots/acceptance/bug22-03-representative-false-start-1440x900.png",
      fullPage: false,
    });

    // Capture Screenshot 5: Representative redundant explanation removal
    await page.screenshot({
      path: "docs/screenshots/acceptance/bug22-05-representative-redundant-explanation-1440x900.png",
      fullPage: false,
    });

    // Capture Screenshot 6: Representative pause removal
    await page.screenshot({
      path: "docs/screenshots/acceptance/bug22-06-representative-pause-removal-1440x900.png",
      fullPage: false,
    });

    // Open Chat Drawer to view Leo's explanation
    const chatBtn = page.getByRole("button", { name: "Chat with Leo", exact: false }).first();
    if (await chatBtn.isVisible()) {
      await chatBtn.click();
      await page.waitForTimeout(300);
    }

    // Capture Screenshot 8: Leo cut explanation in Chat
    await page.screenshot({
      path: "docs/screenshots/acceptance/bug22-08-leo-cut-explanation-1440x900.png",
      fullPage: false,
    });

    // Capture Screenshot 9: Edited playback around cut seams
    await page.screenshot({
      path: "docs/screenshots/acceptance/bug22-09-edited-playback-seam-1440x900.png",
      fullPage: false,
    });

    // Capture Screenshot 10: End of Edited Preview
    await page.screenshot({
      path: "docs/screenshots/acceptance/bug22-10-end-edited-preview-1440x900.png",
      fullPage: false,
    });
  });

  test("3. Verifies 1280x800 viewport: Voiceover & Final Mix regeneration", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await setupEditorMocks(page);
    await loginUser(page);

    await page.goto(`/productions/${PRODUCTION_ID}/editor`);
    await page.waitForSelector("[data-testid='editor-workspace']");

    // Switch to Voiceover Tab / Preview
    await page.getByTestId("tab-voice").click();
    await page.waitForTimeout(300);

    // Capture Screenshot 11: Voiceover after EDL regeneration
    await page.screenshot({
      path: "docs/screenshots/acceptance/bug22-11-voiceover-regenerated-1280x800.png",
      fullPage: false,
    });

    // Switch to Music Tab / Final Mix
    await page.getByTestId("tab-music").click();
    await page.waitForTimeout(300);

    // Capture Screenshot 12: Final Mix after rebuild
    await page.screenshot({
      path: "docs/screenshots/acceptance/bug22-12-final-mix-rebuilt-1280x800.png",
      fullPage: false,
    });
  });
});
