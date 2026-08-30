import { expect, test } from "@playwright/test";
import {
  deriveAudioRegions,
  deriveKeepSegments,
  type EditDecisionList,
  edlToTwickTimeline,
  findExecutableSkipInterval,
  formatCutLabel,
  formatDuration,
  formatTimecode,
  getExecutableCuts,
} from "./edl-adapter";

test.describe("EDL Adapter & Playback Logic", () => {
  const fairphoneEDL: EditDecisionList = {
    edl_id: "edl_6324ea33234a",
    production_id: "prod_f0b41bfd429e",
    source_duration_ms: 113824,
    cuts: [],
    coverage_markers: [
      {
        marker_id: "cov_147e604682b8",
        decision_id: "dec_002",
        source_start_ms: 26160,
        source_end_ms: 42340,
        coverage_type: "BROLL_CANDIDATE",
        reason: "Close-up macro demonstration of unscrewing plate",
      },
    ],
    created_at: "2026-08-26T00:00:00Z",
  };

  test("zero-cut Fairphone EDL derives full duration as single keep segment", () => {
    const keepSegments = deriveKeepSegments(fairphoneEDL);
    expect(keepSegments).toEqual([[0, 113824]]);
    expect(getExecutableCuts(fairphoneEDL)).toEqual([]);
  });

  test("zero-cut Fairphone EDL never triggers an edited preview skip", () => {
    // Check at start, during coverage, and near end
    expect(findExecutableSkipInterval(0, fairphoneEDL)).toBeNull();
    expect(findExecutableSkipInterval(26160, fairphoneEDL)).toBeNull();
    expect(findExecutableSkipInterval(35000, fairphoneEDL)).toBeNull();
    expect(findExecutableSkipInterval(100000, fairphoneEDL)).toBeNull();
  });

  test("EDL with SAFE and NEEDS_COVERAGE cuts derives complementary keep segments", () => {
    const edlWithCuts: EditDecisionList = {
      edl_id: "edl_with_cuts",
      production_id: "prod_cuts_01",
      source_duration_ms: 100000,
      cuts: [
        {
          cut_id: "cut_01",
          decision_id: "dec_01",
          decision_type: "REMOVE_FILLER",
          transcript_start_word: 10,
          transcript_end_word: 12,
          requested_start_ms: 10000,
          requested_end_ms: 15000,
          safe_start_ms: 9900,
          safe_end_ms: 15100,
          removed_duration_ms: 5200,
          left_anchor: "hello",
          right_anchor: "world",
          safety_status: "SAFE",
          safety_reason: "Clean silence boundary",
          confidence: 0.95,
        },
        {
          cut_id: "cut_02",
          decision_id: "dec_02",
          decision_type: "REMOVE_REPETITION",
          transcript_start_word: 40,
          transcript_end_word: 45,
          requested_start_ms: 40000,
          requested_end_ms: 45000,
          safe_start_ms: 39800,
          safe_end_ms: 45200,
          removed_duration_ms: 5400,
          left_anchor: "next",
          right_anchor: "step",
          safety_status: "NEEDS_COVERAGE",
          safety_reason: "Jump cut requires B-roll coverage",
          confidence: 0.92,
        },
        {
          cut_id: "cut_03_unsafe",
          decision_id: "dec_03",
          decision_type: "REMOVE_FILLER",
          transcript_start_word: 70,
          transcript_end_word: 72,
          requested_start_ms: 70000,
          requested_end_ms: 75000,
          safe_start_ms: 70000,
          safe_end_ms: 75000,
          removed_duration_ms: 5000,
          left_anchor: "bad",
          right_anchor: "cut",
          safety_status: "REJECTED_UNSAFE",
          safety_reason: "Boundary collides with spoken syllable",
          confidence: 0.45,
        },
      ],
      coverage_markers: [],
      created_at: "2026-08-26T00:00:00Z",
    };

    const keepSegments = deriveKeepSegments(edlWithCuts);
    expect(keepSegments).toEqual([
      [0, 9900],
      [15100, 39800],
      [45200, 100000],
    ]);

    // Test Edited Preview skip interval detection
    const skipAt10s = findExecutableSkipInterval(10000, edlWithCuts);
    expect(skipAt10s).toEqual({
      safe_start_ms: 9900,
      safe_end_ms: 15100,
      cut_id: "cut_01",
    });

    const skipAt40s = findExecutableSkipInterval(40000, edlWithCuts);
    expect(skipAt40s).toEqual({
      safe_start_ms: 39800,
      safe_end_ms: 45200,
      cut_id: "cut_02",
    });

    // Unsafe cut at 72000 must NOT be skipped
    const skipAt72s = findExecutableSkipInterval(72000, edlWithCuts);
    expect(skipAt72s).toBeNull();
  });

  test("edlToTwickTimeline builds canonical tracks and populates blocks truthfully", () => {
    const twickData = edlToTwickTimeline(fairphoneEDL);
    expect(twickData.tracks.length).toBe(8);
    expect(twickData.tracks[0].getName()).toBe("Video");
    expect(twickData.tracks[1].getName()).toBe("Audio");
    expect(twickData.tracks[2].getName()).toBe("Edits");
    expect(twickData.tracks[3].getName()).toBe("B-roll");
    expect(twickData.tracks[4].getName()).toBe("Voiceover");
    expect(twickData.tracks[5].getName()).toBe("Music");
    expect(twickData.tracks[6].getName()).toBe("Chapters");
    expect(twickData.tracks[7].getName()).toBe("Captions");
    expect(twickData.coverageMarkerCount).toBe(1);

    // Coverage block matches Fairphone fixture
    const covBlock = twickData.blocks.find(
      (b) => b.trackId === "broll" || b.trackId === "coverage",
    );
    expect(covBlock).toBeDefined();
    expect(covBlock?.startMs).toBe(26160);
    expect(covBlock?.endMs).toBe(42340);
    expect(covBlock?.type).toBe("coverage-broll");
  });
  test("deriveAudioRegions identifies speech and removed cut regions", () => {
    const audioRegions = deriveAudioRegions(fairphoneEDL);
    expect(audioRegions.length).toBeGreaterThanOrEqual(1);
    expect(audioRegions[0].type).toBe("speech");
  });

  test("formatCutLabel produces clean human-facing strings", () => {
    expect(formatCutLabel("REMOVE_SILENCE", 2100)).toBe("Silence removed 2.1s");
    expect(formatCutLabel("REMOVE_FALSE_START", 800)).toBe("False start removed 0.8s");
    expect(formatCutLabel("TIGHTEN_PAUSE", 1200)).toBe("Tightened pause 1.2s");
    expect(formatCutLabel("KEEP_FOR_CLARITY", 5000)).toBe("Walkthrough preserved");
  });

  test("time formatting helpers", () => {
    expect(formatTimecode(0)).toBe("00:00.00");
    expect(formatTimecode(65430)).toBe("01:05.43");
    expect(formatTimecode(113824)).toBe("01:53.82");

    expect(formatDuration(0)).toBe("0.0s");
    expect(formatDuration(26160)).toBe("26.2s");
    expect(formatDuration(113824)).toBe("1m 54s");
  });
});
