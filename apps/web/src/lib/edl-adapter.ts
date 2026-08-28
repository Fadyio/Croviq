/**
 * Croviq EDL to Twick Timeline Adapter & Playback Helpers.
 *
 * ADR-0012: Generated contracts from FastAPI OpenAPI provide the canonical types.
 * Twick is the visualization representation, NOT the edit truth. Canonical edit
 * truth is EditDecisionList.
 */

import { Track } from "@twick/timeline";
import type { components } from "../api/generated";

export type EditDecisionList = components["schemas"]["EditDecisionList"];
export type CutInstruction = components["schemas"]["CutInstruction"];
export type CoverageMarker = components["schemas"]["CoverageMarker"];
export type EditorProposal = components["schemas"]["EditorProposal"];
export type DirectorReview = components["schemas"]["DirectorReview"];
export type EditorDecision = components["schemas"]["EditorDecision"];
export type DirectorDecision = components["schemas"]["DirectorDecision"];
export type AgentActivity = components["schemas"]["AgentActivity"];
export type Transcript = components["schemas"]["Transcript"];
export type TranscriptWord = components["schemas"]["TranscriptWord"];
export type TranscriptSegment = components["schemas"]["TranscriptSegment"];
export type ShortCandidate = components["schemas"]["ShortCandidate"];
export type ChapterMarker = components["schemas"]["ChapterMarker"];

export type TimelineTrackId =
  | "video"
  | "audio"
  | "edits"
  | "broll"
  | "narration"
  | "captions"
  | "chapters"
  | "short"
  | "source-video"
  | "dialogue-edits"
  | "coverage";

export interface TimelineBlock {
  id: string;
  trackId: TimelineTrackId;
  label: string;
  startMs: number;
  endMs: number;
  durationMs: number;
  type:
    | "source"
    | "cut-safe"
    | "cut-needs-coverage"
    | "cut-rejected"
    | "coverage-broll"
    | "coverage-screen"
    | "narration"
    | "caption"
    | "chapter"
    | "short"
    | "keep";
  decisionId?: string;
  cutId?: string;
  markerId?: string;
  details?: {
    originalText?: string;
    conciseReason?: string;
    mayaVerdict?: string;
    mayaReason?: string;
    confidence?: number;
    safetyStatus?: string;
    coverageType?: string;
    summary?: string;
  };
}

export interface AudioTrackRegion {
  type: "speech" | "silence" | "removed";
  startMs: number;
  endMs: number;
  label?: string;
}

export interface TwickTimelineRepresentation {
  tracks: Track[];
  blocks: TimelineBlock[];
  totalDurationMs: number;
  activeCutCount: number;
  coverageMarkerCount: number;
  keepSegments: Array<[number, number]>;
  audioRegions: AudioTrackRegion[];
  chapters: ChapterMarker[];
  shortCandidate?: ShortCandidate | null;
}

/**
 * Filter executable cuts (SAFE and NEEDS_COVERAGE).
 * REJECTED_UNSAFE cuts are non-executable and must never be skipped.
 */
export function getExecutableCuts(edl?: EditDecisionList | null): CutInstruction[] {
  if (!edl || !edl.cuts) return [];
  return edl.cuts.filter((c) => c.safety_status === "SAFE" || c.safety_status === "NEEDS_COVERAGE");
}

/**
 * Format user-facing, human-friendly cut labels rather than raw enums.
 * Examples: "Silence removed 2.1s", "False start removed 0.8s", "Tightened pause 1.2s".
 */
export function formatCutLabel(decisionType: string, durationMs: number): string {
  const durS = (durationMs / 1000).toFixed(1);
  switch (decisionType) {
    case "REMOVE_SILENCE":
    case "TRIM_PAUSE":
      return `Silence removed ${durS}s`;
    case "REMOVE_FALSE_START":
      return `False start removed ${durS}s`;
    case "REMOVE_REPETITION":
      return `Repetition removed ${durS}s`;
    case "TIGHTEN_PAUSE":
    case "TIGHTEN_EXPLANATION":
      return `Tightened pause ${durS}s`;
    case "REMOVE_LOW_VALUE_SECTION":
    case "REMOVE_FILLER":
      return `Filler removed ${durS}s`;
    case "BROLL_COVER":
    case "BROLL_COVER_CANDIDATE":
      return `B-roll cover ${durS}s`;
    case "KEEP_FOR_CLARITY":
    case "KEEP":
      return `Walkthrough preserved`;
    default: {
      const clean = decisionType.replace(/_/g, " ").toLowerCase();
      return `${clean.charAt(0).toUpperCase() + clean.slice(1)} ${durS}s`;
    }
  }
}

/**
 * Deterministically derive contiguous KEEP intervals [start_ms, end_ms] from EDL.
 * Replicates backend `derive_keep_segments(edl)`.
 */
export function deriveKeepSegments(edl?: EditDecisionList | null): Array<[number, number]> {
  if (!edl) return [[0, 0]];
  const sourceDurationMs = edl.source_duration_ms || 0;
  if (sourceDurationMs <= 0) return [[0, 0]];

  const executableCuts = getExecutableCuts(edl);
  if (executableCuts.length === 0) {
    return [[0, sourceDurationMs]];
  }

  // Sort cuts chronologically by safe_start_ms
  const sortedCuts = [...executableCuts].sort((a, b) => a.safe_start_ms - b.safe_start_ms);

  const keepSegments: Array<[number, number]> = [];
  let currentHead = 0;

  for (const cut of sortedCuts) {
    const cutStart = Math.max(0, Math.min(cut.safe_start_ms, sourceDurationMs));
    const cutEnd = Math.max(cutStart, Math.min(cut.safe_end_ms, sourceDurationMs));

    if (cutStart > currentHead) {
      keepSegments.push([currentHead, cutStart]);
    }
    currentHead = Math.max(currentHead, cutEnd);
  }

  if (currentHead < sourceDurationMs) {
    keepSegments.push([currentHead, sourceDurationMs]);
  }

  return keepSegments.length > 0 ? keepSegments : [[0, sourceDurationMs]];
}
/**
 * Deterministically derive audio classification regions (speech, silence, removed) from transcript and EDL.
 */
export function deriveAudioRegions(
  edl: EditDecisionList,
  transcript?: Transcript | null,
): AudioTrackRegion[] {
  const totalMs = edl.source_duration_ms || 113824;
  if (totalMs <= 0) return [];

  const executableCuts = getExecutableCuts(edl);
  const cutIntervals = executableCuts.map(
    (c) => [c.safe_start_ms, c.safe_end_ms] as [number, number],
  );

  const speechIntervals: Array<[number, number]> = [];
  if (transcript?.segments && transcript.segments.length > 0) {
    for (const seg of transcript.segments) {
      if (seg.end_ms > seg.start_ms) {
        speechIntervals.push([seg.start_ms, seg.end_ms]);
      }
    }
  } else if (transcript?.words && transcript.words.length > 0) {
    let curStart = transcript.words[0].start_ms;
    let curEnd = transcript.words[0].end_ms;
    for (let i = 1; i < transcript.words.length; i++) {
      const w = transcript.words[i];
      if (w.start_ms - curEnd <= 300) {
        curEnd = Math.max(curEnd, w.end_ms);
      } else {
        speechIntervals.push([curStart, curEnd]);
        curStart = w.start_ms;
        curEnd = w.end_ms;
      }
    }
    speechIntervals.push([curStart, curEnd]);
  } else {
    speechIntervals.push([0, totalMs]);
  }

  const regions: AudioTrackRegion[] = [];

  for (const [spStart, spEnd] of speechIntervals) {
    let cursor = spStart;
    for (const [cStart, cEnd] of cutIntervals) {
      if (cStart >= cursor && cStart < spEnd) {
        if (cStart > cursor) {
          regions.push({ type: "speech", startMs: cursor, endMs: cStart });
        }
        cursor = Math.max(cursor, cEnd);
      } else if (cStart < cursor && cEnd > cursor) {
        cursor = Math.max(cursor, cEnd);
      }
    }
    if (cursor < spEnd) {
      regions.push({ type: "speech", startMs: cursor, endMs: spEnd });
    }
  }

  for (const cut of executableCuts) {
    regions.push({
      type: "removed",
      startMs: cut.safe_start_ms,
      endMs: cut.safe_end_ms,
      label: formatCutLabel(cut.decision_type, cut.safe_end_ms - cut.safe_start_ms),
    });
  }

  regions.sort((a, b) => a.startMs - b.startMs);
  return regions;
}

/**
 * Map source timeline timestamp in ms to edited timeline timestamp in ms based on EDL keep segments.
 */
export function sourceToEditedTimeMs(sourceMs: number, edl?: EditDecisionList | null): number {
  if (!edl) return sourceMs;
  const keepSegments = deriveKeepSegments(edl);
  if (keepSegments.length === 0) return sourceMs;

  let accumulatedEditedMs = 0;
  for (const [startMs, endMs] of keepSegments) {
    if (sourceMs < startMs) {
      return accumulatedEditedMs;
    }
    if (sourceMs >= startMs && sourceMs <= endMs) {
      return accumulatedEditedMs + (sourceMs - startMs);
    }
    accumulatedEditedMs += endMs - startMs;
  }
  return accumulatedEditedMs;
}

/**
 * Map edited timeline timestamp in ms back to source timeline timestamp in ms based on EDL keep segments.
 */
export function editedToSourceTimeMs(editedMs: number, edl?: EditDecisionList | null): number {
  if (!edl) return editedMs;
  const keepSegments = deriveKeepSegments(edl);
  if (keepSegments.length === 0) return editedMs;

  let accumulatedEditedMs = 0;
  for (const [startMs, endMs] of keepSegments) {
    const segDuration = endMs - startMs;
    if (editedMs <= accumulatedEditedMs + segDuration) {
      const offset = Math.max(0, editedMs - accumulatedEditedMs);
      return startMs + offset;
    }
    accumulatedEditedMs += segDuration;
  }
  const lastSeg = keepSegments[keepSegments.length - 1];
  return lastSeg ? lastSeg[1] : edl.source_duration_ms || editedMs;
}

/**
 * Check if the given playback time (in ms) falls into an executable cut range.
 * Returns the cut interval if it should be skipped in Edited Preview mode.
 */
export function findExecutableSkipInterval(
  currentTimeMs: number,
  edl?: EditDecisionList | null,
  leadThresholdMs = 80,
): { safe_start_ms: number; safe_end_ms: number; cut_id: string } | null {
  if (!edl || !edl.cuts) return null;

  const executableCuts = getExecutableCuts(edl);
  for (const cut of executableCuts) {
    if (
      currentTimeMs >= cut.safe_start_ms - leadThresholdMs &&
      currentTimeMs < cut.safe_end_ms - 20
    ) {
      return {
        safe_start_ms: cut.safe_start_ms,
        safe_end_ms: cut.safe_end_ms,
        cut_id: cut.cut_id,
      };
    }
  }
  return null;
}

/**
 * Convert canonical Croviq EDL and editorial records into Twick Tracks and TimelineBlocks.
 */
export function edlToTwickTimeline(
  edl: EditDecisionList,
  proposal?: EditorProposal | null,
  review?: DirectorReview | null,
  transcript?: Transcript | null,
): TwickTimelineRepresentation {
  const sourceDurationMs = edl.source_duration_ms || 113824;
  const blocks: TimelineBlock[] = [];

  // 1. VIDEO track (continuous base footage)
  blocks.push({
    id: "block-video",
    trackId: "video",
    label: "Continuous Video Footage",
    startMs: 0,
    endMs: sourceDurationMs,
    durationMs: sourceDurationMs,
    type: "source",
    details: {
      originalText: "Full continuous source camera capture",
    },
  });

  // Index Leo decisions and Maya reviews by decision_id / editor_decision_id
  const leoDecisionMap: Record<string, EditorDecision> = {};
  if (proposal?.decisions) {
    for (const d of proposal.decisions) {
      leoDecisionMap[d.decision_id] = d;
    }
  }

  const mayaDecisionMap: Record<string, DirectorDecision> = {};
  if (review?.decisions) {
    for (const d of review.decisions) {
      mayaDecisionMap[d.editor_decision_id] = d;
    }
  }

  // 2. EDITS track (cut instructions or proposed cuts)
  const cuts = edl.cuts || [];
  for (const cut of cuts) {
    const leoDec = leoDecisionMap[cut.decision_id];
    const mayaDec = mayaDecisionMap[cut.decision_id];

    let blockType: TimelineBlock["type"] = "cut-safe";
    if (cut.safety_status === "NEEDS_COVERAGE") {
      blockType = "cut-needs-coverage";
    } else if (cut.safety_status === "REJECTED_UNSAFE") {
      blockType = "cut-rejected";
    }

    const duration = cut.safe_end_ms - cut.safe_start_ms;
    const humanLabel = formatCutLabel(cut.decision_type, duration);

    blocks.push({
      id: `cut-${cut.cut_id}`,
      trackId: "edits",
      label: humanLabel,
      startMs: cut.safe_start_ms,
      endMs: cut.safe_end_ms,
      durationMs: duration,
      type: blockType,
      decisionId: cut.decision_id,
      cutId: cut.cut_id,
      details: {
        originalText: leoDec?.original_text,
        conciseReason: leoDec?.concise_reason,
        mayaVerdict: mayaDec?.verdict,
        mayaReason: mayaDec?.concise_reason,
        confidence: leoDec?.confidence,
        safetyStatus: cut.safety_status,
      },
    });
  }

  // 3. B-ROLL / COVERAGE track
  const coverageMarkers = edl.coverage_markers || [];
  for (const marker of coverageMarkers) {
    const leoDec = leoDecisionMap[marker.decision_id];
    const mayaDec = mayaDecisionMap[marker.decision_id];

    const duration = marker.source_end_ms - marker.source_start_ms;
    blocks.push({
      id: `cov-${marker.marker_id}`,
      trackId: "broll",
      label: marker.coverage_type === "BROLL_CANDIDATE" ? "B-Roll Visual" : "Source Coverage",
      startMs: marker.source_start_ms,
      endMs: marker.source_end_ms,
      durationMs: duration,
      type: marker.coverage_type === "BROLL_CANDIDATE" ? "coverage-broll" : "coverage-screen",
      decisionId: marker.decision_id,
      markerId: marker.marker_id,
      details: {
        originalText: leoDec?.original_text,
        conciseReason: marker.reason || leoDec?.concise_reason,
        mayaVerdict: mayaDec?.verdict,
        mayaReason: mayaDec?.concise_reason,
        confidence: leoDec?.confidence,
        coverageType: marker.coverage_type,
      },
    });
  }

  // 4. CHAPTERS track
  const rawChapters = proposal?.chapters || [];
  for (let i = 0; i < rawChapters.length; i++) {
    const chap = rawChapters[i];
    const duration = chap.source_end_ms - chap.source_start_ms;
    blocks.push({
      id: `chapter-${i}`,
      trackId: "chapters",
      label: chap.title,
      startMs: chap.source_start_ms,
      endMs: chap.source_end_ms,
      durationMs: duration,
      type: "chapter",
      details: {
        summary: chap.summary,
        confidence: chap.confidence,
      },
    });
  }

  // 5. SHORT CANDIDATE track
  if (proposal?.short_candidate) {
    const sc = proposal.short_candidate;
    const duration = sc.end_ms - sc.start_ms;
    blocks.push({
      id: "block-short-candidate",
      trackId: "short",
      label: `Short: ${sc.hook_title}`,
      startMs: sc.start_ms,
      endMs: sc.end_ms,
      durationMs: duration,
      type: "short",
      details: {
        conciseReason: sc.concise_reason,
        confidence: sc.confidence,
      },
    });
  }

  // 6. CAPTIONS track (from canonical transcript segments)
  if (transcript?.segments) {
    for (const seg of transcript.segments) {
      blocks.push({
        id: `caption-${seg.segment_id}`,
        trackId: "captions",
        label: seg.text,
        startMs: seg.start_ms,
        endMs: seg.end_ms,
        durationMs: seg.end_ms - seg.start_ms,
        type: "caption",
        details: {
          originalText: seg.text,
        },
      });
    }
  }

  // Construct Twick Track instances
  const tracks = [
    new Track("Video", "ELEMENT", "track-video"),
    new Track("Audio", "ELEMENT", "track-audio"),
    new Track("Edits", "ELEMENT", "track-edits"),
    new Track("B-roll", "ELEMENT", "track-broll"),
    new Track("Narration", "ELEMENT", "track-narration"),
    new Track("Captions", "ELEMENT", "track-captions"),
    new Track("Chapters", "ELEMENT", "track-chapters"),
    new Track("Short", "ELEMENT", "track-short"),
  ];

  const keepSegments = deriveKeepSegments(edl);
  const audioRegions = deriveAudioRegions(edl, transcript);

  return {
    tracks,
    blocks,
    totalDurationMs: sourceDurationMs,
    activeCutCount: getExecutableCuts(edl).length,
    coverageMarkerCount: coverageMarkers.length,
    keepSegments,
    audioRegions,
    chapters: rawChapters,
    shortCandidate: proposal?.short_candidate,
  };
}

/**
 * Format milliseconds to MM:SS.mmm timecode string.
 */
export function formatTimecode(ms: number): string {
  if (isNaN(ms) || ms < 0) return "00:00.00";
  const totalSeconds = ms / 1000;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.floor(totalSeconds % 60);
  const millis = Math.floor((ms % 1000) / 10);
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${String(millis).padStart(2, "0")}`;
}

/**
 * Format milliseconds to human readable duration string (e.g. "1m 53s" or "42.3s").
 */
export function formatDuration(ms: number): string {
  if (isNaN(ms) || ms < 0) return "0s";
  const totalSeconds = ms / 1000;
  if (totalSeconds < 60) {
    return `${totalSeconds.toFixed(1)}s`;
  }
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSecs = Math.round(totalSeconds % 60);
  return `${minutes}m ${remainingSecs}s`;
}
