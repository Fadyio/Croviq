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

export interface TimelineBlock {
  id: string;
  trackId: "source-video" | "dialogue-edits" | "coverage";
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
  };
}

export interface TwickTimelineRepresentation {
  tracks: Track[];
  blocks: TimelineBlock[];
  totalDurationMs: number;
  activeCutCount: number;
  coverageMarkerCount: number;
  keepSegments: Array<[number, number]>;
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
    // If the playhead is right at or inside the cut range (with a small anticipation buffer)
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
): TwickTimelineRepresentation {
  const sourceDurationMs = edl.source_duration_ms || 113824;
  const blocks: TimelineBlock[] = [];

  // 1. SOURCE VIDEO track (continuous base footage)
  blocks.push({
    id: "block-source-video",
    trackId: "source-video",
    label: "Source Video Footage",
    startMs: 0,
    endMs: sourceDurationMs,
    durationMs: sourceDurationMs,
    type: "source",
    details: {
      originalText: "Full continuous source camera capture",
    },
  });

  // Index Leo decisions and Maya reviews by decision_id / editor_decision_id
  const leoDecisionMap = new Map<string, EditorDecision>();
  if (proposal?.decisions) {
    for (const d of proposal.decisions) {
      leoDecisionMap.set(d.decision_id, d);
    }
  }

  const mayaDecisionMap = new Map<string, DirectorDecision>();
  if (review?.decisions) {
    for (const d of review.decisions) {
      mayaDecisionMap.set(d.editor_decision_id, d);
    }
  }

  // 2. DIALOGUE EDITS track (cut instructions or proposed cuts)
  const cuts = edl.cuts || [];
  for (const cut of cuts) {
    const leoDec = leoDecisionMap.get(cut.decision_id);
    const mayaDec = mayaDecisionMap.get(cut.decision_id);

    let blockType: TimelineBlock["type"] = "cut-safe";
    if (cut.safety_status === "NEEDS_COVERAGE") {
      blockType = "cut-needs-coverage";
    } else if (cut.safety_status === "REJECTED_UNSAFE") {
      blockType = "cut-rejected";
    }

    const duration = cut.safe_end_ms - cut.safe_start_ms;
    blocks.push({
      id: `cut-${cut.cut_id}`,
      trackId: "dialogue-edits",
      label: cut.decision_type.replace(/_/g, " "),
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

  // 3. COVERAGE track (BROLL_CANDIDATE or SOURCE_SCREEN)
  const coverageMarkers = edl.coverage_markers || [];
  for (const marker of coverageMarkers) {
    const leoDec = leoDecisionMap.get(marker.decision_id);
    const mayaDec = mayaDecisionMap.get(marker.decision_id);

    const duration = marker.source_end_ms - marker.source_start_ms;
    blocks.push({
      id: `cov-${marker.marker_id}`,
      trackId: "coverage",
      label: marker.coverage_type === "BROLL_CANDIDATE" ? "B-Roll Candidate" : "Screen Coverage",
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

  // Construct Twick Track instances
  const sourceTrack = new Track("SOURCE VIDEO", "ELEMENT", "track-source-video");
  const editsTrack = new Track("DIALOGUE EDITS", "ELEMENT", "track-dialogue-edits");
  const coverageTrack = new Track("COVERAGE", "ELEMENT", "track-coverage");

  const tracks = [sourceTrack, editsTrack, coverageTrack];
  const keepSegments = deriveKeepSegments(edl);

  return {
    tracks,
    blocks,
    totalDurationMs: sourceDurationMs,
    activeCutCount: getExecutableCuts(edl).length,
    coverageMarkerCount: coverageMarkers.length,
    keepSegments,
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
