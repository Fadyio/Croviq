import { expect, test } from "@playwright/test";
import {
  deriveAudioRegions,
  deriveKeepSegments,
  type EditDecisionList,
  edlToTwickTimeline,
  editedToSourceTimeMs,
  findExecutableSkipInterval,
  formatCutLabel,
  formatDuration,
  formatTimecode,
  getExecutableCuts,
  isSourceTimeInCut,
  isWordInExecutableCut,
  sourceToEditedTimeMs,
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

  test.describe("BUG 13 — Target Regression Test Suite (Cases A-H)", () => {
    // CASE A: No cuts. Transcript source timing == playback timing.
    test("Case A: No cuts - source timing strictly equals playback timing", () => {
      const noCutsEdl: EditDecisionList = {
        edl_id: "edl_no_cuts",
        production_id: "prod_no_cuts",
        source_duration_ms: 60000,
        cuts: [],
        created_at: "2026-08-26T00:00:00Z",
      };

      for (let ms = 0; ms <= 60000; ms += 5000) {
        expect(sourceToEditedTimeMs(ms, noCutsEdl)).toBe(ms);
        expect(editedToSourceTimeMs(ms, noCutsEdl)).toBe(ms);
        expect(isSourceTimeInCut(ms, noCutsEdl)).toBe(false);
      }

      const testWord = { index: 0, text: "hello", start_ms: 5000, end_ms: 5500 };
      expect(isWordInExecutableCut(testWord, noCutsEdl).isCut).toBe(false);
    });

    // CASE B: One middle cut. Words inside cut marked removed. Post-cut transcript maps correctly.
    test("Case B: One middle cut - words inside marked removed, post-cut maps accurately", () => {
      const singleCutEdl: EditDecisionList = {
        edl_id: "edl_single_cut",
        production_id: "prod_single_cut",
        source_duration_ms: 100000,
        cuts: [
          {
            cut_id: "cut_middle",
            decision_id: "dec_01",
            decision_type: "REMOVE_FALSE_START",
            transcript_start_word: 2,
            transcript_end_word: 3,
            requested_start_ms: 20000,
            requested_end_ms: 30000,
            safe_start_ms: 20000,
            safe_end_ms: 30000,
            removed_duration_ms: 10000,
            left_anchor: "start",
            right_anchor: "continue",
            safety_status: "SAFE",
            safety_reason: "Clean cut",
            confidence: 0.99,
          },
        ],
        created_at: "2026-08-26T00:00:00Z",
      };

      const wordBefore = { index: 1, text: "start", start_ms: 15000, end_ms: 18000 };
      const wordInside = { index: 2, text: "uh", start_ms: 22000, end_ms: 25000 };
      const wordAfter = { index: 4, text: "continue", start_ms: 35000, end_ms: 38000 };

      expect(isWordInExecutableCut(wordBefore, singleCutEdl).isCut).toBe(false);
      expect(isWordInExecutableCut(wordInside, singleCutEdl).isCut).toBe(true);
      expect(isWordInExecutableCut(wordAfter, singleCutEdl).isCut).toBe(false);

      // Pre-cut maps 1:1
      expect(sourceToEditedTimeMs(15000, singleCutEdl)).toBe(15000);
      expect(editedToSourceTimeMs(15000, singleCutEdl)).toBe(15000);

      // Post-cut subtracts 10,000ms
      expect(sourceToEditedTimeMs(35000, singleCutEdl)).toBe(25000);
      expect(editedToSourceTimeMs(25000, singleCutEdl)).toBe(35000);
    });

    // CASE C: Multiple cuts. No cumulative offset drift.
    test("Case C: Multiple cuts - exact cumulative offsets without drift", () => {
      const multiCutEdl: EditDecisionList = {
        edl_id: "edl_multi",
        production_id: "prod_multi",
        source_duration_ms: 100000,
        cuts: [
          {
            cut_id: "c1",
            decision_id: "d1",
            decision_type: "TRIM_PAUSE",
            transcript_start_word: 1,
            transcript_end_word: 2,
            requested_start_ms: 10000,
            requested_end_ms: 12000,
            safe_start_ms: 10000,
            safe_end_ms: 12000,
            removed_duration_ms: 2000,
            left_anchor: "a",
            right_anchor: "b",
            safety_status: "SAFE",
            safety_reason: "silence",
            confidence: 0.95,
          },
          {
            cut_id: "c2",
            decision_id: "d2",
            decision_type: "TRIM_PAUSE",
            transcript_start_word: 4,
            transcript_end_word: 5,
            requested_start_ms: 30000,
            requested_end_ms: 35000,
            safe_start_ms: 30000,
            safe_end_ms: 35000,
            removed_duration_ms: 5000,
            left_anchor: "c",
            right_anchor: "d",
            safety_status: "SAFE",
            safety_reason: "silence",
            confidence: 0.95,
          },
          {
            cut_id: "c3",
            decision_id: "d3",
            decision_type: "TRIM_PAUSE",
            transcript_start_word: 7,
            transcript_end_word: 8,
            requested_start_ms: 60000,
            requested_end_ms: 63000,
            safe_start_ms: 60000,
            safe_end_ms: 63000,
            removed_duration_ms: 3000,
            left_anchor: "e",
            right_anchor: "f",
            safety_status: "SAFE",
            safety_reason: "silence",
            confidence: 0.95,
          },
        ],
        created_at: "2026-08-26T00:00:00Z",
      };

      // Before any cuts (source 5000 -> edited 5000)
      expect(sourceToEditedTimeMs(5000, multiCutEdl)).toBe(5000);
      // After cut 1 (source 20000 -> edited 20000 - 2000 = 18000)
      expect(sourceToEditedTimeMs(20000, multiCutEdl)).toBe(18000);
      expect(editedToSourceTimeMs(18000, multiCutEdl)).toBe(20000);
      // After cut 2 (source 45000 -> edited 45000 - 7000 = 38000)
      expect(sourceToEditedTimeMs(45000, multiCutEdl)).toBe(38000);
      expect(editedToSourceTimeMs(38000, multiCutEdl)).toBe(45000);
      // After cut 3 (source 80000 -> edited 80000 - 10000 = 70000)
      expect(sourceToEditedTimeMs(80000, multiCutEdl)).toBe(70000);
      expect(editedToSourceTimeMs(70000, multiCutEdl)).toBe(80000);
    });

    // CASE D: Word overlaps cut boundary. Handle deterministically. Do not duplicate word.
    test("Case D: Word overlaps cut boundary - handles deterministically by midpoint", () => {
      const cutEdl: EditDecisionList = {
        edl_id: "edl_overlap",
        production_id: "prod_overlap",
        source_duration_ms: 50000,
        cuts: [
          {
            cut_id: "c_boundary",
            decision_id: "d1",
            decision_type: "REMOVE_FILLER",
            transcript_start_word: 2,
            transcript_end_word: 2,
            requested_start_ms: 10000,
            requested_end_ms: 12000,
            safe_start_ms: 10000,
            safe_end_ms: 12000,
            removed_duration_ms: 2000,
            left_anchor: "left",
            right_anchor: "right",
            safety_status: "SAFE",
            safety_reason: "filler",
            confidence: 0.95,
          },
        ],
        created_at: "2026-08-26T00:00:00Z",
      };

      // Word with midpoint inside cut
      const wordInside = { index: 2, text: "um", start_ms: 9900, end_ms: 11000 };
      expect(isWordInExecutableCut(wordInside, cutEdl).isCut).toBe(true);

      // Word with midpoint outside cut
      const wordOutside = { index: 3, text: "right", start_ms: 11900, end_ms: 13000 };
      expect(isWordInExecutableCut(wordOutside, cutEdl).isCut).toBe(false);
    });

    // CASE E: Seek from transcript in Edited mode. Correct mapped media time.
    test("Case E: Seek from transcript in Edited mode maps to exact edited time", () => {
      const cutEdl: EditDecisionList = {
        edl_id: "edl_seek",
        production_id: "prod_seek",
        source_duration_ms: 60000,
        cuts: [
          {
            cut_id: "c_seek",
            decision_id: "d1",
            decision_type: "TRIM_PAUSE",
            transcript_start_word: 2,
            transcript_end_word: 3,
            requested_start_ms: 10000,
            requested_end_ms: 15000,
            safe_start_ms: 10000,
            safe_end_ms: 15000,
            removed_duration_ms: 5000,
            left_anchor: "a",
            right_anchor: "b",
            safety_status: "SAFE",
            safety_reason: "pause",
            confidence: 0.95,
          },
        ],
        created_at: "2026-08-26T00:00:00Z",
      };

      const wordPostCut = { index: 3, text: "b", start_ms: 16000, end_ms: 17000 };
      const expectedEditedMs = sourceToEditedTimeMs(wordPostCut.start_ms, cutEdl);
      expect(expectedEditedMs).toBe(11000); // 16000 - 5000
    });

    // CASE F: Seek from player in Edited mode. Correct source transcript highlight.
    test("Case F: Seek from player in Edited mode converts to true source time", () => {
      const cutEdl: EditDecisionList = {
        edl_id: "edl_player_seek",
        production_id: "prod_player_seek",
        source_duration_ms: 60000,
        cuts: [
          {
            cut_id: "c_p",
            decision_id: "d1",
            decision_type: "TRIM_PAUSE",
            transcript_start_word: 2,
            transcript_end_word: 3,
            requested_start_ms: 10000,
            requested_end_ms: 15000,
            safe_start_ms: 10000,
            safe_end_ms: 15000,
            removed_duration_ms: 5000,
            left_anchor: "a",
            right_anchor: "b",
            safety_status: "SAFE",
            safety_reason: "pause",
            confidence: 0.95,
          },
        ],
        created_at: "2026-08-26T00:00:00Z",
      };

      const playerEditedMs = 12000;
      const sourceMs = editedToSourceTimeMs(playerEditedMs, cutEdl);
      expect(sourceMs).toBe(17000); // 12000 + 5000
    });

    // CASE G: Switch Original -> Edited -> Original. No transcript state corruption.
    test("Case G: Switching modes preserves exact coordinate parity", () => {
      const cutEdl: EditDecisionList = {
        edl_id: "edl_mode_switch",
        production_id: "prod_mode_switch",
        source_duration_ms: 80000,
        cuts: [
          {
            cut_id: "c_sw",
            decision_id: "d1",
            decision_type: "TRIM_PAUSE",
            transcript_start_word: 2,
            transcript_end_word: 3,
            requested_start_ms: 20000,
            requested_end_ms: 25000,
            safe_start_ms: 20000,
            safe_end_ms: 25000,
            removed_duration_ms: 5000,
            left_anchor: "a",
            right_anchor: "b",
            safety_status: "SAFE",
            safety_reason: "pause",
            confidence: 0.95,
          },
        ],
        created_at: "2026-08-26T00:00:00Z",
      };

      const sourceTime = 30000;
      const editedTime = sourceToEditedTimeMs(sourceTime, cutEdl); // 25000
      const backToSource = editedToSourceTimeMs(editedTime, cutEdl); // 30000
      expect(backToSource).toBe(sourceTime);
    });

    // CASE H: Last transcript word. Maps correctly to final retained media region.
    test("Case H: Last transcript word maps accurately to final media range", () => {
      const cutEdl: EditDecisionList = {
        edl_id: "edl_last_word",
        production_id: "prod_last_word",
        source_duration_ms: 100000,
        cuts: [
          {
            cut_id: "c_end",
            decision_id: "d1",
            decision_type: "TRIM_PAUSE",
            transcript_start_word: 50,
            transcript_end_word: 51,
            requested_start_ms: 90000,
            requested_end_ms: 95000,
            safe_start_ms: 90000,
            safe_end_ms: 95000,
            removed_duration_ms: 5000,
            left_anchor: "a",
            right_anchor: "b",
            safety_status: "SAFE",
            safety_reason: "pause",
            confidence: 0.95,
          },
        ],
        created_at: "2026-08-26T00:00:00Z",
      };

      const lastWord = { index: 52, text: "done", start_ms: 96000, end_ms: 99000 };
      expect(sourceToEditedTimeMs(lastWord.start_ms, cutEdl)).toBe(91000); // 96000 - 5000
      expect(editedToSourceTimeMs(91000, cutEdl)).toBe(96000);
    });
  });
});
