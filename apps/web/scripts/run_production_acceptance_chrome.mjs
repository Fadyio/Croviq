import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const BASE_URL = "http://127.0.0.1:5173";
const SCREENSHOT_DIR = path.resolve("docs/screenshots/acceptance");
const PRODUCTION_ID = "prod_473209137802";

const DEMO_EMAIL = "demo@croviq.app";
const APPROVED_USER = {
  user_id: "27iEBUMcu6ToDYwp2OdEIHBuwIA3",
  email: DEMO_EMAIL,
  display_name: "Croviq Demo",
  avatar_url: null,
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

const FIREBASE_ID_TOKEN =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJpc3MiOiJodHRwczovL3NlY3VyZXRva2VuLmdvb2dsZS5jb20vY3JvdmlxLTUwNjYwMiIsImF1ZCI6ImNyb3ZpcS01MDY2MDIiLCJhdXRoX3RpbWUiOjEsInVzZXJfaWQiOiIyN2lFQlVNY3U2VG9EWXdwMk9kRUlIQnV3SUEzIiwic3ViIjoiMjdpRUJVTWN1NlRvRFl3cDJPZEVJSEJ1d0lBMyIsImlhdCI6MSwiZXhwIjo0MTAyNDQ0ODAwLCJlbWFpbCI6ImRlbW9AY3JvdmlxLmFwcCIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmaXJlYmFzZSI6eyJpZGVudGl0aWVzIjp7ImVtYWlsIjpbImRlbW9AY3JvdmlxLmFwcCJdfSwic2lnbl9pbl9wcm92aWRlciI6InBhc3N3b3JkIn19.signature";

const REAL_TRANSCRIPT = {
  transcript_id: "tr_real_github_01",
  production_id: PRODUCTION_ID,
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
  ],
  segments: [
    { segment_id: "seg_00", start_ms: 2100, end_ms: 5700, text: "This is a GitHub action tutorial.", word_start_index: 0, word_end_index: 5 },
    { segment_id: "seg_01", start_ms: 8000, end_ms: 8300, text: "Okay.", word_start_index: 6, word_end_index: 6 },
    { segment_id: "seg_02", start_ms: 8900, end_ms: 15400, text: "You can find the GitHub action in here.", word_start_index: 7, word_end_index: 14 },
    { segment_id: "seg_03", start_ms: 16200, end_ms: 29000, text: "To edit to edit your workflow like this workflow is for Cloudflare DNS.", word_start_index: 15, word_end_index: 27 },
    { segment_id: "seg_04", start_ms: 30700, end_ms: 48100, text: "You can find here the name of the workflow that runs on permission write and read content.", word_start_index: 28, word_end_index: 44 },
    { segment_id: "seg_05", start_ms: 51300, end_ms: 51600, text: "Okay.", word_start_index: 45, word_end_index: 45 },
    { segment_id: "seg_06", start_ms: 53600, end_ms: 56600, text: "And you can find the whole script in here.", word_start_index: 46, word_end_index: 54 },
    { segment_id: "seg_07", start_ms: 57600, end_ms: 67800, text: "Also there is a lot of other devices one to verify that the GitHub the Cloudflare action is working.", word_start_index: 55, word_end_index: 73 },
    { segment_id: "seg_08", start_ms: 68900, end_ms: 92100, text: "Deploy which is and how to deploy our application to Google Cloud and here is with test verified workflow and everything is working.", word_start_index: 74, word_end_index: 96 },
    { segment_id: "seg_09", start_ms: 93900, end_ms: 96500, text: "You here you can find here the issues.", word_start_index: 97, word_end_index: 104 },
    { segment_id: "seg_10", start_ms: 96500, end_ms: 101000, text: "You can write the workflow for issues.", word_start_index: 105, word_end_index: 111 },
  ],
  created_at: "2026-08-30T00:00:00Z",
};

const REAL_CORRECTED_SCRIPT = {
  script_id: "cs_real_github_01",
  production_id: PRODUCTION_ID,
  segments: [
    {
      segment_id: "seg_00_transcription",
      source_start_ms: 2100,
      source_end_ms: 5700,
      original_text: "This is a GitHub action tutorial.",
      corrected_text: "This is a GitHub Actions tutorial.",
      change_type: "TRANSCRIPTION_ERROR",
      reason: "Corrected singular 'action' to official plural product name 'GitHub Actions'.",
      visual_evidence: "GitHub repository tab showing Actions workflow menu.",
      meaning_changed: false,
      target_duration_ms: 3600,
      confidence: 0.99,
      entailment_verdict: "SUPPORTED",
    },
    {
      segment_id: "seg_03_falsestart",
      source_start_ms: 16200,
      source_end_ms: 29000,
      original_text: "To edit to edit your workflow like this workflow is for Cloudflare DNS.",
      corrected_text: "To edit your workflow, this workflow is for Cloudflare DNS.",
      change_type: "FALSE_START",
      reason: "Removed repeated 'to edit' stutter and conversational filler 'like'.",
      visual_evidence: "Editor displaying Cloudflare DNS deploy workflow YAML.",
      meaning_changed: false,
      target_duration_ms: 12800,
      confidence: 0.98,
      entailment_verdict: "SUPPORTED",
    },
    {
      segment_id: "seg_08_grammar",
      source_start_ms: 68900,
      source_end_ms: 92100,
      original_text: "Deploy which is and how to deploy our application to Google Cloud and here is with test verified workflow and everything is working.",
      corrected_text: "And how to deploy our application to Google Cloud with a test-verified workflow.",
      change_type: "GRAMMAR",
      reason: "Cleaned up run-on grammar, stumbles, and non-native sentence construction into clear spoken tutorial English.",
      visual_evidence: "Google Cloud Run deploy step green checks visible on screen.",
      meaning_changed: false,
      target_duration_ms: 23200,
      confidence: 0.97,
      entailment_verdict: "SUPPORTED",
    },
  ],
  unsupported_additions_count: 0,
  entailment_overall: "PASS",
  created_at: "2026-08-30T00:00:00Z",
};

const REAL_PRODUCTION = {
  production_id: PRODUCTION_ID,
  workspace_id: "ws_27iEBUMcu6ToDYwp2OdEIHBuwIA3",
  title: "GitHub Actions CI/CD Tutorial",
  status: "completed",
  source_media: {
    upload_id: "upl_48ee4e53140b",
    original_filename: "github.mp4",
    gcs_bucket: "croviq-506602-croviq-media-raw",
    gcs_object: "workspaces/ws_27iEBUMcu6ToDYwp2OdEIHBuwIA3/productions/prod_473209137802/source/upl_48ee4e53140b/github.mp4",
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

const REAL_RENDERS = [
  {
    artifact_id: "art_prev_c1aeea59",
    production_id: PRODUCTION_ID,
    edl_id: "edl_a27fc1aeea59",
    artifact_type: "PREVIEW",
    status: "completed",
    gcs_bucket: "croviq-506602-croviq-media-raw",
    gcs_object: "workspaces/ws_27iEBUMcu6ToDYwp2OdEIHBuwIA3/productions/prod_473209137802/renders/edl_a27fc1aeea59/preview.mp4",
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
    production_id: PRODUCTION_ID,
    edl_id: "edl_a27fc1aeea59",
    artifact_type: "STUDIO_VOICE_PREVIEW",
    status: "completed",
    gcs_bucket: "croviq-506602-croviq-media-raw",
    gcs_object: "workspaces/ws_27iEBUMcu6ToDYwp2OdEIHBuwIA3/productions/prod_473209137802/renders/edl_a27fc1aeea59/studio_voice_preview.mp4",
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
    production_id: PRODUCTION_ID,
    edl_id: "edl_a27fc1aeea59",
    artifact_type: "FINAL_MIX",
    status: "completed",
    gcs_bucket: "croviq-506602-croviq-media-raw",
    gcs_object: "workspaces/ws_27iEBUMcu6ToDYwp2OdEIHBuwIA3/productions/prod_473209137802/renders/edl_a27fc1aeea59/final_mix.mp4",
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
];

const REAL_EDL = {
  edl_id: "edl_a27fc1aeea59",
  production_id: PRODUCTION_ID,
  source_duration_ms: 101440,
  version: 2,
  cuts: [
    { cut_id: "cut_d252c23c84dc", decision_id: "silence_cut_001", decision_type: "TRIM_PAUSE", transcript_start_word: 5, transcript_end_word: 6, requested_start_ms: 5100, requested_end_ms: 8300, safe_start_ms: 5825, safe_end_ms: 7875, removed_duration_ms: 2050, left_anchor: "tutorial.", right_anchor: "Okay.", transition_ms: 20, safety_status: "SAFE", safety_reason: "Natural pause trimming.", confidence: 1.0 },
    { cut_id: "cut_531745e3410d", decision_id: "silence_cut_002", decision_type: "TRIM_PAUSE", transcript_start_word: 12, transcript_end_word: 13, requested_start_ms: 11300, requested_end_ms: 15010, safe_start_ms: 11925, safe_end_ms: 14875, removed_duration_ms: 2950, left_anchor: "action", right_anchor: "in", transition_ms: 20, safety_status: "SAFE", safety_reason: "Natural pause trimming.", confidence: 1.0 },
    { cut_id: "cut_ec94258e8024", decision_id: "dec_001_false_start_edit", decision_type: "REMOVE_FALSE_START", transcript_start_word: 15, transcript_end_word: 16, requested_start_ms: 16200, requested_end_ms: 16800, safe_start_ms: 16100, safe_end_ms: 16900, removed_duration_ms: 800, left_anchor: "here.", right_anchor: "to", transition_ms: 20, safety_status: "SAFE", safety_reason: "Clean inter-word silence.", confidence: 0.95 },
    { cut_id: "cut_eb44fa160224", decision_id: "silence_cut_003", decision_type: "TRIM_PAUSE", transcript_start_word: 16, transcript_end_word: 17, requested_start_ms: 16300, requested_end_ms: 22900, safe_start_ms: 16925, safe_end_ms: 22575, removed_duration_ms: 5650, left_anchor: "edit", right_anchor: "to", transition_ms: 20, safety_status: "SAFE", safety_reason: "Natural pause trimming.", confidence: 1.0 },
    { cut_id: "cut_39c912c41b26", decision_id: "silence_cut_004", decision_type: "TRIM_PAUSE", transcript_start_word: 27, transcript_end_word: 28, requested_start_ms: 28600, requested_end_ms: 30800, safe_start_ms: 29125, safe_end_ms: 30575, removed_duration_ms: 1450, left_anchor: "DNS.", right_anchor: "You", transition_ms: 20, safety_status: "SAFE", safety_reason: "Natural pause trimming.", confidence: 1.0 },
    { cut_id: "cut_36b2f22f463d", decision_id: "silence_cut_005", decision_type: "TRIM_PAUSE", transcript_start_word: 39, transcript_end_word: 40, requested_start_ms: 36900, requested_end_ms: 46000, safe_start_ms: 37625, safe_end_ms: 45075, removed_duration_ms: 7450, left_anchor: "on", right_anchor: "permission", transition_ms: 20, safety_status: "SAFE", safety_reason: "Natural pause trimming.", confidence: 1.0 },
    { cut_id: "cut_a825332d7faa", decision_id: "silence_cut_006", decision_type: "TRIM_PAUSE", transcript_start_word: 44, transcript_end_word: 45, requested_start_ms: 47400, requested_end_ms: 51600, safe_start_ms: 48225, safe_end_ms: 51175, removed_duration_ms: 2950, left_anchor: "content.", right_anchor: "Okay.", transition_ms: 20, safety_status: "SAFE", safety_reason: "Natural pause trimming.", confidence: 1.0 },
    { cut_id: "cut_debb29652e5a", decision_id: "silence_cut_007", decision_type: "TRIM_PAUSE", transcript_start_word: 45, transcript_end_word: 46, requested_start_ms: 51300, requested_end_ms: 54300, safe_start_ms: 51725, safe_end_ms: 53475, removed_duration_ms: 1750, left_anchor: "Okay.", right_anchor: "And", transition_ms: 20, safety_status: "SAFE", safety_reason: "Natural pause trimming.", confidence: 1.0 },
    { cut_id: "cut_189da865d0d5", decision_id: "silence_cut_008", decision_type: "TRIM_PAUSE", transcript_start_word: 66, transcript_end_word: 67, requested_start_ms: 62200, requested_end_ms: 64110, safe_start_ms: 62925, safe_end_ms: 63975, removed_duration_ms: 1050, left_anchor: "that", right_anchor: "the", transition_ms: 20, safety_status: "SAFE", safety_reason: "Natural pause trimming.", confidence: 1.0 },
    { cut_id: "cut_d419eef3d9dd", decision_id: "dec_003_false_start_github_cloudflare", decision_type: "REMOVE_FALSE_START", transcript_start_word: 67, transcript_end_word: 68, requested_start_ms: 64100, requested_end_ms: 64800, safe_start_ms: 64000, safe_end_ms: 64900, removed_duration_ms: 900, left_anchor: "that", right_anchor: "the", transition_ms: 20, safety_status: "SAFE", safety_reason: "Clean inter-word silence.", confidence: 0.94 },
    { cut_id: "cut_053b36d19912", decision_id: "silence_cut_009", decision_type: "TRIM_PAUSE", transcript_start_word: 74, transcript_end_word: 75, requested_start_ms: 68900, requested_end_ms: 71000, safe_start_ms: 69625, safe_end_ms: 70675, removed_duration_ms: 1050, left_anchor: "Deploy", right_anchor: "which", transition_ms: 20, safety_status: "SAFE", safety_reason: "Natural pause trimming.", confidence: 1.0 },
    { cut_id: "cut_4bc71dc9f35d", decision_id: "dec_004_remove_false_start_which_is", decision_type: "REMOVE_FALSE_START", transcript_start_word: 75, transcript_end_word: 76, requested_start_ms: 70800, requested_end_ms: 71400, safe_start_ms: 70700, safe_end_ms: 71500, removed_duration_ms: 800, left_anchor: "Deploy", right_anchor: "and", transition_ms: 20, safety_status: "SAFE", safety_reason: "Clean inter-word silence.", confidence: 0.89 },
    { cut_id: "cut_e5cf9c237463", decision_id: "silence_cut_010", decision_type: "TRIM_PAUSE", transcript_start_word: 76, transcript_end_word: 77, requested_start_ms: 71000, requested_end_ms: 75300, safe_start_ms: 71525, safe_end_ms: 74975, removed_duration_ms: 3450, left_anchor: "is", right_anchor: "and", transition_ms: 20, safety_status: "SAFE", safety_reason: "Natural pause trimming.", confidence: 1.0 },
    { cut_id: "cut_39793c045b2d", decision_id: "silence_cut_011", decision_type: "TRIM_PAUSE", transcript_start_word: 85, transcript_end_word: 86, requested_start_ms: 78900, requested_end_ms: 81600, safe_start_ms: 79625, safe_end_ms: 80975, removed_duration_ms: 1350, left_anchor: "Cloud", right_anchor: "and", transition_ms: 20, safety_status: "SAFE", safety_reason: "Natural pause trimming.", confidence: 1.0 },
    { cut_id: "cut_d08a0b9684ad", decision_id: "silence_cut_012", decision_type: "TRIM_PAUSE", transcript_start_word: 86, transcript_end_word: 87, requested_start_ms: 81100, requested_end_ms: 83400, safe_start_ms: 81725, safe_end_ms: 82975, removed_duration_ms: 1250, left_anchor: "and", right_anchor: "here", transition_ms: 20, safety_status: "SAFE", safety_reason: "Natural pause trimming.", confidence: 1.0 },
    { cut_id: "cut_dd63b718328c", decision_id: "silence_cut_013", decision_type: "TRIM_PAUSE", transcript_start_word: 90, transcript_end_word: 91, requested_start_ms: 84800, requested_end_ms: 88200, safe_start_ms: 85325, safe_end_ms: 87275, removed_duration_ms: 1950, left_anchor: "test", right_anchor: "verified", transition_ms: 20, safety_status: "SAFE", safety_reason: "Natural pause trimming.", confidence: 1.0 },
    { cut_id: "cut_ca2db9d2fcf8", decision_id: "silence_cut_014", decision_type: "TRIM_PAUSE", transcript_start_word: 92, transcript_end_word: 93, requested_start_ms: 88600, requested_end_ms: 90800, safe_start_ms: 89225, safe_end_ms: 90375, removed_duration_ms: 1150, left_anchor: "workflow", right_anchor: "and", transition_ms: 20, safety_status: "SAFE", safety_reason: "Natural pause trimming.", confidence: 1.0 },
    { cut_id: "cut_9089aabf5cc3", decision_id: "silence_cut_015", decision_type: "TRIM_PAUSE", transcript_start_word: 96, transcript_end_word: 97, requested_start_ms: 91600, requested_end_ms: 94000, safe_start_ms: 92225, safe_end_ms: 93775, removed_duration_ms: 1550, left_anchor: "working.", right_anchor: "You", transition_ms: 20, safety_status: "SAFE", safety_reason: "Natural pause trimming.", confidence: 1.0 },
    { cut_id: "cut_13bcc2b7e2b0", decision_id: "dec_005_remove_repetition_issues", decision_type: "REMOVE_FALSE_START", transcript_start_word: 97, transcript_end_word: 98, requested_start_ms: 93900, requested_end_ms: 94600, safe_start_ms: 93800, safe_end_ms: 94700, removed_duration_ms: 900, left_anchor: "working.", right_anchor: "you", transition_ms: 20, safety_status: "SAFE", safety_reason: "Clean inter-word silence.", confidence: 0.93 },
    { cut_id: "cut_55f5d5950182", decision_id: "silence_cut_016", decision_type: "TRIM_PAUSE", transcript_start_word: 109, transcript_end_word: 110, requested_start_ms: 98000, requested_end_ms: 100400, safe_start_ms: 98825, safe_end_ms: 99875, removed_duration_ms: 1050, left_anchor: "workflow", right_anchor: "for", transition_ms: 20, safety_status: "SAFE", safety_reason: "Natural pause trimming.", confidence: 1.0 },
  ],
  coverage_markers: [],
  voiceover_segments: [
    {
      segment_id: "seg_00_transcription",
      source_start_ms: 2100,
      source_end_ms: 5700,
      text: "This is a GitHub Actions tutorial.",
      original_text: "This is a GitHub action tutorial.",
      voice_mode: "PREBUILT_STUDIO_VOICE",
      voice_id: "Puck",
      generated_duration_ms: 3040,
    },
    {
      segment_id: "seg_03_falsestart",
      source_start_ms: 16200,
      source_end_ms: 29000,
      text: "To edit your workflow, this workflow is for Cloudflare DNS.",
      original_text: "To edit to edit your workflow like this workflow is for Cloudflare DNS.",
      voice_mode: "PREBUILT_STUDIO_VOICE",
      voice_id: "Puck",
      generated_duration_ms: 4800,
    },
    {
      segment_id: "seg_08_grammar",
      source_start_ms: 68900,
      source_end_ms: 92100,
      text: "And how to deploy our application to Google Cloud with a test-verified workflow.",
      original_text: "Deploy which is and how to deploy our application to Google Cloud and here is with test verified workflow and everything is working.",
      voice_mode: "PREBUILT_STUDIO_VOICE",
      voice_id: "Puck",
      generated_duration_ms: 5680,
    },
  ],
  background_music: {
    style: "Minimal modern technology documentary underscore",
    model_id: "lyria-3-pro-preview",
    volume_db: -24.0,
    ducking_db: -14.0,
    target_lufs: -32.0,
    music_gcs_object: "workspaces/ws_27iEBUMcu6ToDYwp2OdEIHBuwIA3/productions/prod_473209137802/music/lyria_underscore.wav",
    is_muted: false,
  },
  created_at: "2026-08-30T00:00:00Z",
};

const REAL_EDITORIAL_RUN = {
  run_id: "run_real_github_01",
  production_id: PRODUCTION_ID,
  agent: "leo",
  model: "gemini-3.7-flash",
  summary: "Cleaned up stumbles, false starts, and aligned product terminology with GitHub Actions tutorial footage.",
  decisions: [
    {
      decision_id: "dec_01",
      decision_type: "REMOVE_FILLER",
      transcript_start_word: 0,
      transcript_end_word: 5,
      source_start_ms: 2100,
      source_end_ms: 5700,
      original_text: "This is a GitHub action tutorial.",
      action: "modify",
      concise_reason: "Corrected singular product name to official plural 'GitHub Actions'.",
      confidence: 0.99,
    },
    {
      decision_id: "dec_02",
      decision_type: "REMOVE_FILLER",
      transcript_start_word: 15,
      transcript_end_word: 27,
      source_start_ms: 16200,
      source_end_ms: 29000,
      original_text: "To edit to edit your workflow like this workflow is for Cloudflare DNS.",
      action: "remove_filler",
      concise_reason: "Removed stuttered false start 'to edit to edit' and filler 'like'.",
      confidence: 0.98,
    },
    {
      decision_id: "dec_03",
      decision_type: "REMOVE_FILLER",
      transcript_start_word: 74,
      transcript_end_word: 96,
      source_start_ms: 68900,
      source_end_ms: 92100,
      original_text: "Deploy which is and how to deploy our application to Google Cloud and here is with test verified workflow and everything is working.",
      action: "rephrase",
      concise_reason: "Polished grammar and non-native run-on construction into clean tutorial narration.",
      confidence: 0.97,
    },
  ],
  overall_confidence: 0.98,
  created_at: "2026-08-30T00:00:00Z",
};

async function main() {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  console.log("=== Launching Chrome with Real Production Data for prod_473209137802 ===");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  const consoleErrors = [];
  const failedRequests = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(`${msg.text()} (${msg.location()?.url})`);
      console.log(`[Browser Console Error] ${msg.text()} @ ${msg.location()?.url}`);
    }
  });

  page.on("requestfailed", (req) => {
    if (!req.url().includes("favicon")) {
      failedRequests.push(`${req.method()} ${req.url()} (${req.failure()?.errorText})`);
      console.log(`[Browser Request Failed] ${req.method()} ${req.url()}`);
    }
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
    const url = route.request().url();
    if (url.includes("/memory")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          channel_title: "Tech DevOps Tutorials",
          style_guide: "Clear, step-by-step CI/CD automation instructions.",
          creator_preferences: ["Focus on GitHub Actions YAML."],
          lessons: [],
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
          prompt_text: "You are Leo, an expert video editor.",
          version: 1,
          updated_at: "2026-08-30T00:00:00Z",
          is_custom: false,
        },
        iris_prompt: {
          agent_id: "iris",
          prompt_text: "You are Iris, quality assurance reviewer.",
          version: 1,
          updated_at: "2026-08-30T00:00:00Z",
          is_custom: false,
        },
        voice_settings: {
          narration_mode: "studio_voice",
          selected_voice: "Puck",
          language: "en-US",
          my_voice_status: "BLOCKED",
          my_voice_blocked_reason: "Google voice replication capability is currently BLOCKED pending project allowlist enablement.",
          updated_at: "2026-08-30T00:00:00Z",
        },
        voices: [
          { voice_id: "Puck", display_name: "Puck (Energetic, Clear)", gender: "male", language_code: "en-US" },
          { voice_id: "Charon", display_name: "Charon (Authoritative, Deep)", gender: "male", language_code: "en-US" },
          { voice_id: "Kore", display_name: "Kore (Warm, Conversational)", gender: "female", language_code: "en-US" },
          { voice_id: "Fenrir", display_name: "Fenrir (Direct, Confident)", gender: "male", language_code: "en-US" },
          { voice_id: "Aoede", display_name: "Aoede (Articulate, Polished)", gender: "female", language_code: "en-US" },
        ],
      }),
    });
  });

  await page.route("**/api/productions", async (route) => {
    if (route.request().url().endsWith("/api/productions")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          productions: [REAL_PRODUCTION],
          total: 1,
        }),
      });
      return;
    }
    await route.fallback();
  });

  // Serve real production records
  await page.route(`**/api/productions/${PRODUCTION_ID}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(REAL_PRODUCTION),
    });
  });
  await page.route(`**/api/productions/${PRODUCTION_ID}/analyze`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "completed",
        summary: "Tutorial covering GitHub Actions deployment to Google Cloud with Cloudflare DNS.",
        key_topics: ["GitHub Actions", "Cloudflare DNS", "Google Cloud Run"],
      }),
    });
  });


  await page.route(`**/api/productions/${PRODUCTION_ID}/playback`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        production_id: PRODUCTION_ID,
        playback_url: "https://storage.googleapis.com/croviq-media-raw/mock-source.mp4",
        expires_at: "2026-08-30T04:00:00Z",
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

  await page.route(`**/api/productions/${PRODUCTION_ID}/transcript`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(REAL_TRANSCRIPT),
    });
  });

  await page.route(`**/api/productions/${PRODUCTION_ID}/editorial-run`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(REAL_EDITORIAL_RUN),
    });
  });

  await page.route(`**/api/productions/${PRODUCTION_ID}/edl`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(REAL_EDL),
    });
  });

  await page.route(`**/api/productions/${PRODUCTION_ID}/renders`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ renders: REAL_RENDERS, total: REAL_RENDERS.length }),
    });
  });

  await page.route(`**/api/productions/${PRODUCTION_ID}/corrected-script`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        production_id: PRODUCTION_ID,
        corrected_transcript: REAL_CORRECTED_SCRIPT,
      }),
    });
  });

  await page.route(`**/api/productions/${PRODUCTION_ID}/broll`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ production_id: PRODUCTION_ID, artifacts: [] }),
    });
  });

  await page.route("**/api/client-events", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
  });

  console.log("Navigating to login...");
  await page.goto(`${BASE_URL}/login`, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/app*", { timeout: 15000 });

  console.log("Navigating to Editor for:", PRODUCTION_ID);
  await page.goto(`${BASE_URL}/productions/${PRODUCTION_ID}/editor`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);

  // 1. Capture full editor default view
  const shotEditorDefault = path.join(SCREENSHOT_DIR, "chrome-editor-prod-default.png");
  await page.screenshot({ path: shotEditorDefault, fullPage: true });
  console.log("Saved default view screenshot:", shotEditorDefault);

  // 2. Verify Media Bin Artifacts
  console.log("\n--- Verifying Media Bin Outputs ---");
  const mediaBin = page.getByTestId("project-bin").or(page.getByTestId("media-bin"));
  await page.waitForTimeout(500);
  const hasOriginal = await mediaBin.getByText("Source Video").isVisible();
  const hasEdited = await mediaBin.getByText("Edited Preview").isVisible();
  const hasStudioVoice = await mediaBin.getByText("Voiceover Preview").isVisible();
  const hasFinalMix = await mediaBin.getByText("Final Mix").isVisible();
  console.log("Media Bin Source Video present:", hasOriginal);
  console.log("Media Bin Edited Preview present:", hasEdited);
  console.log("Media Bin Voiceover Preview present:", hasStudioVoice);
  console.log("Media Bin Final Mix present:", hasFinalMix);

  // 3. Test Preview Modes & Playback
  const previewModes = [
    { name: "Original", assetId: "original", mode: "original" },
    { name: "Edited Preview", assetId: "edited", mode: "edited" },
    { name: "Voiceover Preview", assetId: "studio_voice", mode: "studio_voice" },
    { name: "Final Mix", assetId: "final_mix", mode: "final_mix" },
  ];

  for (const pm of previewModes) {
    console.log(`\n--- Testing Preview Mode: ${pm.name} ---`);
    const assetRow = mediaBin.getByTestId(`asset-${pm.assetId}`).first();
    if (await assetRow.isVisible()) {
      await assetRow.click();
      await page.waitForTimeout(800);
      const shot = path.join(SCREENSHOT_DIR, `chrome-mode-${pm.mode}.png`);
      await page.screenshot({ path: shot });
      console.log(`Switched to ${pm.name}, saved screenshot: ${shot}`);
    }
  }

  // 4. Seek through the 3 corrected segments in Final Mix mode
  console.log("\n--- Seeking through the 3 Corrected Segments in Final Mix ---");
  const finalMixAsset = mediaBin.getByTestId("asset-final_mix").first();
  if (await finalMixAsset.isVisible()) {
    await finalMixAsset.click();
    await page.waitForTimeout(800);
  }

  const testSegments = [
    { id: "removed_region_cut_06", timeS: 24.7, label: "Removed Cut Region 6 (source pause 37.6s - 45.1s absent)" },
    { id: "seg_00_transcription", timeS: 3.5, label: "Corrected Segment 1 (GitHub Actions, edited 2.1s - 5.7s)" },
    { id: "seg_03_falsestart", timeS: 14.0, label: "Corrected Segment 2 (Cloudflare DNS, edited 11.1s - 17.55s)" },
    { id: "seg_08_grammar", timeS: 48.0, label: "Corrected Segment 3 (Google Cloud Deploy, edited 41.9s - 54.1s)" },
    { id: "end_of_video", timeS: 58.5, label: "End of Video (58.5s of 60.0s timeline)" },
  ];
  for (const seg of testSegments) {
    console.log(`Seeking to ${seg.label} at ${seg.timeS}s...`);
    const videoState = await page.evaluate((targetTime) => {
      const video = document.querySelector("video");
      if (!video) return { found: false };
      video.currentTime = targetTime;
      return {
        found: true,
        currentTime: video.currentTime,
        duration: video.duration,
        paused: video.paused,
      };
    }, seg.timeS);

    await page.waitForTimeout(1000);
    const segShot = path.join(SCREENSHOT_DIR, `chrome-final-mix-${seg.id}.png`);
    await page.screenshot({ path: segShot });
    console.log(`Segment ${seg.id} video state:`, videoState);
    console.log(`Saved screenshot: ${segShot}`);
  }

  // 5. Check Transcript Corrected Script View
  console.log("\n--- Checking Corrected Script View in Transcript Panel ---");
  const transcriptTab = page.getByTestId("tab-transcript").or(page.getByRole("tab", { name: /Transcript/i })).first();
  if (await transcriptTab.isVisible()) {
    await transcriptTab.click();
    await page.waitForTimeout(800);
    
    const correctedToggle = page.getByRole("button", { name: "Corrected Script" }).first();
    if (await correctedToggle.isVisible()) {
      await correctedToggle.click();
      await page.waitForTimeout(800);
    }
    const scriptShot = path.join(SCREENSHOT_DIR, "chrome-corrected-script-tab.png");
    await page.screenshot({ path: scriptShot });
    console.log("Saved script tab screenshot:", scriptShot);
  }

  // 6. Check Voice Settings / My Voice BLOCKED Status in Settings Drawer
  console.log("\n--- Checking Voice Settings / My Voice BLOCKED Status ---");
  const leoAvatar = page.getByTestId("leo-avatar-btn").first();
  if (await leoAvatar.isVisible()) {
    await leoAvatar.click();
    await page.waitForTimeout(1000);
    
    const drawer = page.getByTestId("agent-settings-drawer");
    const voiceTab = drawer.getByRole("button", { name: "Voice" }).first();
    if (await voiceTab.isVisible()) {
      await voiceTab.click();
      await page.waitForTimeout(800);
    }
    const voiceShot = path.join(SCREENSHOT_DIR, "chrome-voice-settings-drawer.png");
    await page.screenshot({ path: voiceShot });
    console.log("Saved voice settings screenshot:", voiceShot);
  }

  console.log("\n========================================");
  console.log("CHROME ACCEPTANCE SUMMARY:");
  console.log(`  Console Errors: ${consoleErrors.length}`);
  console.log(`  Failed Requests: ${failedRequests.length}`);
  console.log("========================================");

  await browser.close();
}

main().catch((err) => {
  console.error("Chrome acceptance run failed:", err);
  process.exit(1);
});
