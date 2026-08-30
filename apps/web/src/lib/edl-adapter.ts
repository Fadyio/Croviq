/**
 * Croviq EDL to Twick Timeline Adapter & Playback Helpers.
 *
 * ADR-0012: Generated contracts from FastAPI OpenAPI provide the canonical types.
 * Twick is the visualization representation, NOT the edit truth. Canonical edit
 * truth is EditDecisionList.
 */

import { Track } from "@twick/timeline";
import type { components } from "../api/generated";

export type EditDecisionList = components["schemas"]["EditDecisionList"] & {
  voiceover_segments?: VoiceoverSegment[];
  background_music?: BackgroundMusicMix | null;
};
export type CutInstruction = components["schemas"]["CutInstruction"];
export type CoverageMarker = components["schemas"]["CoverageMarker"];
export type EditorProposal = components["schemas"]["EditorProposal"];
export type EditorDecision = components["schemas"]["EditorDecision"];
export type AgentActivity = components["schemas"]["AgentActivity"];
export type Transcript = components["schemas"]["Transcript"];
export type TranscriptWord = components["schemas"]["TranscriptWord"];
export type TranscriptSegment = components["schemas"]["TranscriptSegment"];
export type ChapterMarker = components["schemas"]["ChapterMarker"];

export type EditorSelectionType =
  "POINT" | "RANGE" | "TRANSCRIPT_WORD" | "TRANSCRIPT_SEGMENT" | "CUT" | "CHAPTER";

export type CoordinateSpace = "SOURCE" | "EDITED";

export type ActivePreviewMode = "ORIGINAL" | "EDITED" | "VOICEOVER" | "FINAL_MIX";

export interface EditorSelection {
  production_id: string;
  selection_type: EditorSelectionType;
  coordinate_space: CoordinateSpace;
  source_start_ms: number;
  source_end_ms: number;
  edited_start_ms: number | null;
  edited_end_ms: number | null;
  transcript_text: string | null;
  transcript_word_ids: number[] | null;
  cut_id: string | null;
  chapter_id: string | null;
  active_edl_id: string | null;
  active_preview_mode: ActivePreviewMode;
  label?: string | null;
  cut_reason?: string | null;
  removed_duration_ms?: number | null;
}

export function normalizePreviewModeToActive(mode: string): ActivePreviewMode {
  const m = mode.toLowerCase();
  if (m === "original") return "ORIGINAL";
  if (m === "edited") return "EDITED";
  if (m === "voiceover") return "VOICEOVER";
  return "FINAL_MIX";
}

export function findCutAtSourceTime(
  sourceMs: number,
  edl?: EditDecisionList | null,
): CutInstruction | null {
  if (!edl?.cuts) return null;
  return (
    edl.cuts.find(
      (c) =>
        c.safety_status !== "REJECTED_UNSAFE" &&
        sourceMs >= (c.safe_start_ms ?? c.requested_start_ms) &&
        sourceMs <= (c.safe_end_ms ?? c.requested_end_ms),
    ) || null
  );
}

export function findCutById(cutId: string, edl?: EditDecisionList | null): CutInstruction | null {
  if (!edl?.cuts) return null;
  return edl.cuts.find((c) => c.cut_id === cutId) || null;
}

export function getWordsInSourceRange(
  startMs: number,
  endMs: number,
  transcript?: Transcript | null,
): TranscriptWord[] {
  if (!transcript?.words) return [];
  return transcript.words.filter((w) => Math.max(w.start_ms, startMs) <= Math.min(w.end_ms, endMs));
}

export function buildPointSelection({
  productionId,
  clickMs,
  previewMode,
  edl,
  transcript,
}: {
  productionId: string;
  clickMs: number;
  previewMode: string;
  edl?: EditDecisionList | null;
  transcript?: Transcript | null;
}): EditorSelection {
  const isOriginal = previewMode.toLowerCase() === "original";
  const coordinate_space: CoordinateSpace = isOriginal ? "SOURCE" : "EDITED";
  const active_preview_mode = normalizePreviewModeToActive(previewMode);

  let sourceMs = clickMs;
  let editedMs: number | null = null;

  if (isOriginal) {
    sourceMs = clickMs;
    editedMs = sourceToEditedTimeMs(sourceMs, edl);
  } else {
    editedMs = clickMs;
    sourceMs = editedToSourceTimeMs(editedMs, edl);
  }

  const cut = findCutAtSourceTime(sourceMs, edl);
  const words = getWordsInSourceRange(Math.max(0, sourceMs - 300), sourceMs + 300, transcript);
  const word =
    words.find((w) => sourceMs >= w.start_ms && sourceMs <= w.end_ms) || words[0] || null;

  return {
    production_id: productionId,
    selection_type: "POINT",
    coordinate_space,
    source_start_ms: sourceMs,
    source_end_ms: sourceMs,
    edited_start_ms: editedMs,
    edited_end_ms: editedMs,
    transcript_text: word ? word.text : null,
    transcript_word_ids: word ? [word.index] : null,
    cut_id: cut?.cut_id || null,
    chapter_id: null,
    active_edl_id: edl?.edl_id || null,
    active_preview_mode,
    label: `Point at ${formatTimecode(sourceMs)}`,
    cut_reason: cut?.safety_reason || cut?.decision_type || null,
    removed_duration_ms: cut
      ? (cut.removed_duration_ms ?? cut.safe_end_ms - cut.safe_start_ms)
      : null,
  };
}

export function buildRangeSelection({
  productionId,
  startMs,
  endMs,
  previewMode,
  edl,
  transcript,
}: {
  productionId: string;
  startMs: number;
  endMs: number;
  previewMode: string;
  edl?: EditDecisionList | null;
  transcript?: Transcript | null;
}): EditorSelection {
  const isOriginal = previewMode.toLowerCase() === "original";
  const coordinate_space: CoordinateSpace = isOriginal ? "SOURCE" : "EDITED";
  const active_preview_mode = normalizePreviewModeToActive(previewMode);

  const cleanStart = Math.min(startMs, endMs);
  const cleanEnd = Math.max(startMs, endMs);

  let sourceStart = cleanStart;
  let sourceEnd = cleanEnd;
  let editedStart: number | null = null;
  let editedEnd: number | null = null;

  if (isOriginal) {
    sourceStart = cleanStart;
    sourceEnd = cleanEnd;
    editedStart = sourceToEditedTimeMs(sourceStart, edl);
    editedEnd = sourceToEditedTimeMs(sourceEnd, edl);
  } else {
    editedStart = cleanStart;
    editedEnd = cleanEnd;
    sourceStart = editedToSourceTimeMs(cleanStart, edl);
    sourceEnd = editedToSourceTimeMs(cleanEnd, edl);
  }

  const words = getWordsInSourceRange(sourceStart, sourceEnd, transcript);
  const text = words.length > 0 ? words.map((w) => w.text).join(" ") : null;
  const wordIds = words.length > 0 ? words.map((w) => w.index) : null;

  return {
    production_id: productionId,
    selection_type: "RANGE",
    coordinate_space,
    source_start_ms: sourceStart,
    source_end_ms: sourceEnd,
    edited_start_ms: editedStart,
    edited_end_ms: editedEnd,
    transcript_text: text,
    transcript_word_ids: wordIds,
    cut_id: null,
    chapter_id: null,
    active_edl_id: edl?.edl_id || null,
    active_preview_mode,
    label: `Range: ${formatTimecode(sourceStart)} → ${formatTimecode(sourceEnd)}`,
    cut_reason: null,
    removed_duration_ms: null,
  };
}

export function buildCutSelection({
  productionId,
  cut,
  previewMode,
  edl,
  transcript,
}: {
  productionId: string;
  cut: CutInstruction;
  previewMode: string;
  edl?: EditDecisionList | null;
  transcript?: Transcript | null;
}): EditorSelection {
  const active_preview_mode = normalizePreviewModeToActive(previewMode);
  const sourceStart = cut.safe_start_ms ?? cut.requested_start_ms;
  const sourceEnd = cut.safe_end_ms ?? cut.requested_end_ms;
  const removedDuration = cut.removed_duration_ms ?? Math.max(0, sourceEnd - sourceStart);
  const editedAt = sourceToEditedTimeMs(sourceStart, edl);

  const words = getWordsInSourceRange(sourceStart, sourceEnd, transcript);
  const text = words.length > 0 ? words.map((w) => w.text).join(" ") : null;
  const wordIds = words.length > 0 ? words.map((w) => w.index) : null;

  return {
    production_id: productionId,
    selection_type: "CUT",
    coordinate_space: "SOURCE",
    source_start_ms: sourceStart,
    source_end_ms: sourceEnd,
    edited_start_ms: editedAt,
    edited_end_ms: editedAt,
    transcript_text: text,
    transcript_word_ids: wordIds,
    cut_id: cut.cut_id,
    chapter_id: null,
    active_edl_id: edl?.edl_id || null,
    active_preview_mode,
    label: `Cut: ${formatCutLabel(cut.decision_type, removedDuration)}`,
    cut_reason: cut.safety_reason || cut.decision_type,
    removed_duration_ms: removedDuration,
  };
}

export function buildTranscriptWordSelection({
  productionId,
  word,
  previewMode,
  edl,
  transcript,
}: {
  productionId: string;
  word: TranscriptWord;
  previewMode: string;
  edl?: EditDecisionList | null;
  transcript?: Transcript | null;
}): EditorSelection {
  const active_preview_mode = normalizePreviewModeToActive(previewMode);
  const cut = findCutAtSourceTime(word.start_ms, edl);
  const editedStart = sourceToEditedTimeMs(word.start_ms, edl);
  const editedEnd = sourceToEditedTimeMs(word.end_ms, edl);

  if (cut) {
    return buildCutSelection({
      productionId,
      cut,
      previewMode,
      edl,
      transcript,
    });
  }

  return {
    production_id: productionId,
    selection_type: "TRANSCRIPT_WORD",
    coordinate_space: "SOURCE",
    source_start_ms: word.start_ms,
    source_end_ms: word.end_ms,
    edited_start_ms: editedStart,
    edited_end_ms: editedEnd,
    transcript_text: word.text,
    transcript_word_ids: [word.index],
    cut_id: null,
    chapter_id: null,
    active_edl_id: edl?.edl_id || null,
    active_preview_mode,
    label: `Transcript word: ${word.text}`,
    cut_reason: null,
    removed_duration_ms: null,
  };
}

export function buildTranscriptSegmentSelection({
  productionId,
  segment,
  previewMode,
  edl,
  transcript,
}: {
  productionId: string;
  segment: TranscriptSegment;
  previewMode: string;
  edl?: EditDecisionList | null;
  transcript?: Transcript | null;
}): EditorSelection {
  const active_preview_mode = normalizePreviewModeToActive(previewMode);
  const editedStart = sourceToEditedTimeMs(segment.start_ms, edl);
  const editedEnd = sourceToEditedTimeMs(segment.end_ms, edl);
  const words = getWordsInSourceRange(segment.start_ms, segment.end_ms, transcript);
  const wordIds = words.length > 0 ? words.map((w) => w.index) : null;

  return {
    production_id: productionId,
    selection_type: "TRANSCRIPT_SEGMENT",
    coordinate_space: "SOURCE",
    source_start_ms: segment.start_ms,
    source_end_ms: segment.end_ms,
    edited_start_ms: editedStart,
    edited_end_ms: editedEnd,
    transcript_text: segment.text,
    transcript_word_ids: wordIds,
    cut_id: null,
    chapter_id: null,
    active_edl_id: edl?.edl_id || null,
    active_preview_mode,
    label: `Transcript: ${segment.text}`,
    cut_reason: null,
    removed_duration_ms: null,
  };
}

export type MediaOutputStatus = "ready" | "generating" | "failed" | "unavailable";

export interface MediaOutputState {
  available: boolean;
  artifactId: string | null;
  edlId: string | null;
  url: string | null;
  durationMs: number;
  status: MediaOutputStatus;
}
export interface ApiMediaOutputState {
  available?: boolean;
  artifact_id?: string | null;
  edl_id?: string | null;
  url?: string | null;
  duration_ms?: number;
  status?: MediaOutputStatus;
}

export function apiMediaOutputToState(
  apiOutput?: ApiMediaOutputState | null,
): MediaOutputState | null {
  if (!apiOutput) return null;
  return {
    available: Boolean(apiOutput.available),
    artifactId: apiOutput.artifact_id || null,
    edlId: apiOutput.edl_id || null,
    url: apiOutput.url || null,
    durationMs: apiOutput.duration_ms || 0,
    status: apiOutput.status || (apiOutput.available ? "ready" : "unavailable"),
  };
}

export interface CanonicalMediaOutputs {
  original: MediaOutputState;
  edited: MediaOutputState;
  voiceover: MediaOutputState;
  final_mix: MediaOutputState;
}
export const createInitialMediaOutputs = (): CanonicalMediaOutputs => ({
  original: {
    available: false,
    artifactId: null,
    edlId: null,
    url: null,
    durationMs: 0,
    status: "unavailable",
  },
  edited: {
    available: false,
    artifactId: null,
    edlId: null,
    url: null,
    durationMs: 0,
    status: "unavailable",
  },
  voiceover: {
    available: false,
    artifactId: null,
    edlId: null,
    url: null,
    durationMs: 0,
    status: "unavailable",
  },
  final_mix: {
    available: false,
    artifactId: null,
    edlId: null,
    url: null,
    durationMs: 0,
    status: "unavailable",
  },
});
export type TimelineTrackId =
  | "video"
  | "audio"
  | "edits"
  | "broll"
  | "voiceover"
  | "music"
  | "chapters"
  | "captions"
  | "narration"
  | "source-video"
  | "dialogue-edits"
  | "coverage";

export type ScriptCorrectionChangeType =
  "GRAMMAR" | "TRANSCRIPTION_ERROR" | "FILLER" | "FALSE_START" | "REPETITION" | "KEEP";

export type EntailmentVerdict = "SUPPORTED" | "UNSUPPORTED" | "UNCERTAIN";

export interface CorrectedTranscriptSegment {
  segment_id: string;
  source_start_ms: number;
  source_end_ms: number;
  original_text: string;
  corrected_text: string;
  change_type: ScriptCorrectionChangeType;
  reason: string;
  visual_evidence: string;
  meaning_changed: boolean;
  target_duration_ms: number;
  confidence: number;
  entailment_verdict: EntailmentVerdict;
  is_voiceover_active?: boolean;
  voice_mode?: string;
  generated_audio_duration_ms?: number | null;
}

export interface CorrectedTranscript {
  transcript_id: string;
  production_id: string;
  segments: CorrectedTranscriptSegment[];
  created_at: string;
}

export interface BackgroundMusicMix {
  style: string;
  model_id?: string;
  prompt?: string | null;
  duration_ms?: number | null;
  volume_db: number;
  ducking_db: number;
  target_lufs: number;
  music_gcs_object: string;
  preview_artifact_id?: string | null;
  is_muted?: boolean;
}

export interface VoiceoverSegment {
  segment_id: string;
  source_start_ms: number;
  source_end_ms: number;
  text: string;
  original_text?: string | null;
  voice_mode: string;
  voice_id?: string | null;
  generated_duration_ms?: number | null;
  preview_artifact_id?: string | null;
}
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
    | "voiceover"
    | "music"
    | "narration"
    | "caption"
    | "chapter"
    | "keep";
  decisionId?: string;
  cutId?: string;
  markerId?: string;
  details?: {
    originalText?: string;
    correctedText?: string;
    conciseReason?: string;
    confidence?: number;
    safetyStatus?: string;
    coverageType?: string;
    summary?: string;
    voiceMode?: string;
    volumeDb?: number;
    duckingDb?: number;
    isMuted?: boolean;
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
}

/**
 * Filter executable cuts (SAFE and NEEDS_COVERAGE).
 * REJECTED_UNSAFE cuts are non-executable and must never be skipped.
 */
export function getExecutableCuts(edl?: EditDecisionList | null): CutInstruction[] {
  if (!edl?.cuts) return [];
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
  const totalMs = edl.source_duration_ms || (transcript?.duration_ms ?? 0);
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
  if (!edl?.cuts) return null;

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
 * Check if a source timestamp (in ms) falls strictly inside an active executable cut.
 */
export function isSourceTimeInCut(sourceMs: number, edl?: EditDecisionList | null): boolean {
  if (!edl?.cuts) return false;
  const executableCuts = getExecutableCuts(edl);
  return executableCuts.some((cut) => sourceMs >= cut.safe_start_ms && sourceMs < cut.safe_end_ms);
}

/**
 * Retrieve the active cut (if any) covering a given source timestamp in ms.
 */
export function getCutAtSourceTime(
  sourceMs: number,
  edl?: EditDecisionList | null,
): CutInstruction | null {
  if (!edl?.cuts) return null;
  const executableCuts = getExecutableCuts(edl);
  return (
    executableCuts.find((cut) => sourceMs >= cut.safe_start_ms && sourceMs <= cut.safe_end_ms) ||
    null
  );
}

/**
 * Deterministically determine whether a transcript word was removed by an active EDL cut.
 * A word is considered removed if its midpoint or time bounds fall inside an active cut.
 */
export function isWordInExecutableCut(
  word: { start_ms: number; end_ms: number; index?: number },
  edl?: EditDecisionList | null,
): { isCut: boolean; cut: CutInstruction | null } {
  if (!edl?.cuts) return { isCut: false, cut: null };
  const executableCuts = getExecutableCuts(edl);
  const midMs = Math.round((word.start_ms + word.end_ms) / 2);
  for (const cut of executableCuts) {
    if (
      (midMs >= cut.safe_start_ms && midMs <= cut.safe_end_ms) ||
      (word.start_ms >= cut.safe_start_ms && word.end_ms <= cut.safe_end_ms)
    ) {
      return { isCut: true, cut };
    }
  }
  return { isCut: false, cut: null };
}

/**
 * Convert canonical Croviq EDL and Leo's editorial proposal into Twick tracks and timeline blocks.
 */
export function edlToTwickTimeline(
  edl: EditDecisionList,
  proposal?: EditorProposal | null,
  transcript?: Transcript | null,
): TwickTimelineRepresentation {
  const sourceDurationMs = edl.source_duration_ms || (transcript?.duration_ms ?? 0);
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

  // Index Leo decisions by decision_id.
  const leoDecisionMap: Record<string, EditorDecision> = {};
  if (proposal?.decisions) {
    for (const d of proposal.decisions) {
      leoDecisionMap[d.decision_id] = d;
    }
  }

  // 2. EDITS track (cut instructions or proposed cuts)
  const cuts = edl.cuts || [];
  for (const cut of cuts) {
    const leoDec = leoDecisionMap[cut.decision_id];

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
        confidence: leoDec?.confidence,
        safetyStatus: cut.safety_status,
      },
    });
  }

  // 3. B-ROLL / COVERAGE track
  const coverageMarkers = edl.coverage_markers || [];
  const coverageDecisionIds = new Set(coverageMarkers.map((marker) => marker.decision_id));
  let coverageBlockCount = 0;
  for (const marker of coverageMarkers) {
    const leoDec = leoDecisionMap[marker.decision_id];

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
        confidence: leoDec?.confidence,
        coverageType: marker.coverage_type,
      },
    });
    coverageBlockCount += 1;
  }

  // Persisted proposal candidates can precede EDL marker assembly. Keep them visible
  // on the canonical B-roll track without duplicating assembled coverage markers.
  for (const candidate of proposal?.decisions || []) {
    if (
      (candidate.decision_type !== "BROLL_COVER_CANDIDATE" &&
        candidate.decision_type !== "BROLL_COVER") ||
      coverageDecisionIds.has(candidate.decision_id)
    ) {
      continue;
    }

    const duration = Math.max(0, candidate.source_end_ms - candidate.source_start_ms);
    blocks.push({
      id: `cov-decision-${candidate.decision_id}`,
      trackId: "broll",
      label: "B-roll candidate",
      startMs: candidate.source_start_ms,
      endMs: candidate.source_end_ms,
      durationMs: duration,
      type: "coverage-broll",
      decisionId: candidate.decision_id,
      details: {
        originalText: candidate.original_text,
        conciseReason: candidate.concise_reason,
        confidence: candidate.confidence,
        coverageType: "BROLL_CANDIDATE",
      },
    });
    coverageBlockCount += 1;
  }

  // 4. VOICEOVER track (persisted replacement voiceover segments)
  const voiceovers = edl.voiceover_segments || [];
  for (const vo of voiceovers) {
    const duration = vo.source_end_ms - vo.source_start_ms;
    blocks.push({
      id: `vo-${vo.segment_id}`,
      trackId: "voiceover",
      label: vo.voice_mode === "REPLICATED_MY_VOICE" ? "My Voice Voiceover" : "Studio Voiceover",
      startMs: vo.source_start_ms,
      endMs: vo.source_end_ms,
      durationMs: duration,
      type: "voiceover",
      details: {
        originalText: vo.original_text || undefined,
        correctedText: vo.text,
        conciseReason: `Narration replacement (${vo.voice_mode})`,
        voiceMode: vo.voice_mode,
      },
    });
  }

  // 5. MUSIC track (Google Lyria background music bed)
  if (edl.background_music) {
    const bg = edl.background_music;
    blocks.push({
      id: "bg-music-bed",
      trackId: "music",
      label: bg.is_muted
        ? "Background Music (Muted)"
        : `${bg.style || "Subtle Technology Underscore"} (${bg.volume_db}dB)`,
      startMs: 0,
      endMs: sourceDurationMs,
      durationMs: sourceDurationMs,
      type: "music",
      details: {
        conciseReason: `Google Lyria 3 Pro (${bg.volume_db}dB, ducking ${bg.ducking_db}dB)`,
        volumeDb: bg.volume_db,
        duckingDb: bg.ducking_db,
        isMuted: bg.is_muted,
      },
    });
  }

  // 6. CHAPTERS track
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

  // 7. CAPTIONS track (from canonical transcript segments)
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

  // Construct Twick Track instances in canonical order:
  // VIDEO, AUDIO, EDITS, B-ROLL, VOICEOVER, MUSIC, CHAPTERS, CAPTIONS
  const tracks = [
    new Track("Video", "ELEMENT", "track-video"),
    new Track("Audio", "ELEMENT", "track-audio"),
    new Track("Edits", "ELEMENT", "track-edits"),
    new Track("B-roll", "ELEMENT", "track-broll"),
    new Track("Voiceover", "ELEMENT", "track-voiceover"),
    new Track("Music", "ELEMENT", "track-music"),
    new Track("Chapters", "ELEMENT", "track-chapters"),
    new Track("Captions", "ELEMENT", "track-captions"),
  ];
  const keepSegments = deriveKeepSegments(edl);
  const audioRegions = deriveAudioRegions(edl, transcript);

  return {
    tracks,
    blocks,
    totalDurationMs: sourceDurationMs,
    activeCutCount: getExecutableCuts(edl).length,
    coverageMarkerCount: coverageBlockCount,
    keepSegments,
    audioRegions,
    chapters: rawChapters,
  };
}

/**
 * Format milliseconds to MM:SS.mmm timecode string.
 */
export function formatTimecode(ms: number): string {
  if (Number.isNaN(ms) || ms < 0) return "00:00.00";
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
  if (Number.isNaN(ms) || ms < 0) return "0s";
  const totalSeconds = ms / 1000;
  if (totalSeconds < 60) {
    return `${totalSeconds.toFixed(1)}s`;
  }
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSecs = Math.round(totalSeconds % 60);
  return `${minutes}m ${remainingSecs}s`;
}
