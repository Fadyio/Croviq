import { ArrowRight, Layers, MessageSquare, Scissors, ShieldCheck } from "lucide-react";
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  type CorrectedTranscript,
  type EditDecisionList,
  type EditorDecision,
  formatCutLabel,
  formatTimecode,
  getExecutableCuts,
  isWordInExecutableCut,
  sourceToEditedTimeMs,
  type Transcript,
  type TranscriptSegment,
  type TranscriptWord,
} from "../../lib/edl-adapter";
import type { PreviewMode } from "./PreviewToggle";

export interface TranscriptRangeSelection {
  id: string;
  label: string;
  startMs: number;
  endMs: number;
}

interface RemovedWordNotice {
  wordText: string;
  startMs: number;
  reason?: string;
}

interface TranscriptPanelProps {
  transcript: Transcript | null;
  correctedTranscript?: CorrectedTranscript | null;
  edl?: EditDecisionList | null;
  mode: PreviewMode;
  currentTimeMs: number;
  decisions?: EditorDecision[];
  selectedDecisionId: string | null;
  onSelectDecision: (decision: EditorDecision | null) => void;
  onSeek: (targetMs: number) => void;
  onModeChange?: (mode: PreviewMode) => void;
  onRangeSelect?: (selection: TranscriptRangeSelection) => void;
  onSendRangeToChat?: (selection: TranscriptRangeSelection) => void;
  onSelectWord?: (word: TranscriptWord) => void;
  onSelectSegment?: (segment: TranscriptSegment) => void;
  className?: string;
}

const isPauseDecision = (decision: EditorDecision): boolean =>
  decision.decision_type === "TRIM_PAUSE" ||
  decision.decision_type === "REMOVE_SILENCE" ||
  decision.decision_type === "TIGHTEN_PAUSE" ||
  decision.decision_type === "DEAD_AIR" ||
  decision.decision_type === "PAUSE_TRIM";
const isRemovedSpeech = (decision: EditorDecision): boolean =>
  decision.decision_type === "FALSE_START" ||
  decision.decision_type === "WORD_REPETITION" ||
  decision.decision_type === "PHRASE_REPETITION" ||
  decision.decision_type === "REDUNDANT_EXPLANATION" ||
  decision.decision_type === "FILLER" ||
  decision.decision_type === "RAMBLING" ||
  decision.decision_type === "PACING" ||
  decision.decision_type === "REMOVE_FALSE_START" ||
  decision.decision_type === "REMOVE_REPETITION" ||
  decision.decision_type === "REMOVE_FILLER" ||
  decision.decision_type === "REMOVE_LOW_VALUE_SECTION" ||
  decision.decision_type === "TIGHTEN_EXPLANATION";

const decisionTitle = (decision: EditorDecision): string => {
  if (decision.decision_type === "FALSE_START" || decision.decision_type === "REMOVE_FALSE_START") return "False start removed";
  if (decision.decision_type === "WORD_REPETITION") return "Repeated word removed";
  if (decision.decision_type === "PHRASE_REPETITION" || decision.decision_type === "REMOVE_REPETITION") return "Repetition removed";
  if (decision.decision_type === "FILLER" || decision.decision_type === "REMOVE_FILLER") return "Filler removed";
  if (decision.decision_type === "REDUNDANT_EXPLANATION" || decision.decision_type === "RAMBLING" || decision.decision_type === "REMOVE_LOW_VALUE_SECTION") return "Redundant explanation removed";
  if (decision.decision_type === "PACING" || decision.decision_type === "TIGHTEN_EXPLANATION") return "Pacing tightened";
  if (decision.decision_type === "SOURCE_COVER") return "Source coverage";
  if (decision.decision_type === "KEEP_FOR_CLARITY" || decision.decision_type === "KEEP") return "Preserved for clarity";
  if (isPauseDecision(decision)) return "Pause trimmed";
  return "Editorial note";
};
const shouldInsertSpace = (text: string, wordPosition: number): boolean =>
  wordPosition > 0 && !/^[,.;:!?)}\]'"’]/u.test(text);

export const TranscriptPanel: React.FC<TranscriptPanelProps> = ({
  transcript,
  correctedTranscript,
  edl,
  mode,
  currentTimeMs,
  decisions = [],
  selectedDecisionId,
  onSelectDecision,
  onSeek,
  onModeChange,
  onRangeSelect,
  onSendRangeToChat,
  onSelectWord,
  onSelectSegment,
  className = "",
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeWordRef = useRef<HTMLButtonElement>(null);
  const manualScrollUntilRef = useRef(0);
  const programmaticScrollRef = useRef(false);
  const [selectedRange, setSelectedRange] = useState<TranscriptRangeSelection | null>(null);
  const [removedWordNotice, setRemovedWordNotice] = useState<RemovedWordNotice | null>(null);
  const [transcriptViewMode, setTranscriptViewMode] = useState<"original" | "corrected">(
    "original",
  );

  const activeWordIndex = useMemo(() => {
    if (!transcript?.words || transcript.words.length === 0) return -1;
    const exact = transcript.words.find(
      (word) => currentTimeMs >= word.start_ms && currentTimeMs <= word.end_ms,
    );
    if (exact) return exact.index;

    // Nearest prior word within 400ms tolerance
    const prevWord = [...transcript.words].reverse().find((w) => w.start_ms <= currentTimeMs);
    if (prevWord && currentTimeMs <= prevWord.end_ms + 400) {
      return prevWord.index;
    }
    return -1;
  }, [currentTimeMs, transcript?.words]);

  const transcriptSegments = useMemo<TranscriptSegment[]>(() => {
    if (!transcript) return [];
    if (transcript.segments?.length) return transcript.segments;
    const words = transcript.words ?? [];
    if (words.length === 0) return [];
    return [
      {
        segment_id: "transcript",
        start_ms: words[0].start_ms,
        end_ms: words.at(-1)?.end_ms ?? words[0].end_ms,
        text: words.map((word) => word.text).join(" "),
        word_start_index: words[0].index,
        word_end_index: words.at(-1)?.index ?? words[0].index,
      },
    ];
  }, [transcript]);

  const executableCuts = useMemo(() => getExecutableCuts(edl), [edl]);
  const formatModeTimecode = (sourceMs: number, editedMs?: number | null): string => {
    if (mode === "original") return formatTimecode(sourceMs);
    if (editedMs !== undefined && editedMs !== null) return formatTimecode(editedMs);
    return formatTimecode(sourceToEditedTimeMs(sourceMs, edl));
  };

  const selectRange = (selection: TranscriptRangeSelection) => {
    setSelectedRange(selection);
    onSeek(selection.startMs);
    onRangeSelect?.(selection);
  };

  useEffect(() => {
    const container = scrollRef.current;
    const activeWord = activeWordRef.current;
    if (!container || !activeWord || activeWordIndex < 0) return;
    if (Date.now() < manualScrollUntilRef.current) return;

    const containerRect = container.getBoundingClientRect();
    const wordRect = activeWord.getBoundingClientRect();
    const readingTop = containerRect.top + containerRect.height * 0.2;
    const readingBottom = containerRect.bottom - containerRect.height * 0.2;
    if (wordRect.top >= readingTop && wordRect.bottom <= readingBottom) return;

    programmaticScrollRef.current = true;
    activeWord.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => {
      programmaticScrollRef.current = false;
    }, 500);
  }, [activeWordIndex]);

  return (
    <section
      className={`flex min-h-0 flex-1 flex-col overflow-hidden ${className}`}
      data-testid="transcript-panel"
    >
      <div className="flex shrink-0 items-center justify-between border-b border-border-subtle px-3 py-2">
        <div className="flex items-center gap-1 rounded-md border border-border-subtle bg-surface-2 p-0.5 text-[10px]">
          <button
            type="button"
            onClick={() => setTranscriptViewMode("original")}
            className={`rounded px-2 py-0.5 font-semibold transition-colors ${
              transcriptViewMode === "original"
                ? "bg-surface-1 text-text-primary shadow-xs"
                : "text-text-muted hover:text-text-secondary"
            }`}
          >
            Original Transcript
          </button>
          <button
            type="button"
            onClick={() => setTranscriptViewMode("corrected")}
            className={`rounded px-2 py-0.5 font-semibold transition-colors ${
              transcriptViewMode === "corrected"
                ? "bg-surface-1 text-text-primary shadow-xs"
                : "text-text-muted hover:text-text-secondary"
            }`}
          >
            Corrected Script
          </button>
        </div>
        <span className="rounded border border-border-subtle bg-surface-2 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-text-muted">
          {mode === "original" ? "Source time" : "Edited time"}
        </span>
      </div>

      {removedWordNotice && mode !== "original" && (
        <div
          className="flex shrink-0 items-center justify-between gap-2 border-b border-danger/30 bg-danger/10 px-3 py-2 text-[11px] text-danger"
          data-testid="removed-word-notice"
        >
          <div className="flex items-center gap-1.5">
            <Scissors className="size-3.5 shrink-0 text-danger" />
            <span>
              “{removedWordNotice.wordText}” was removed from the edited timeline
              {removedWordNotice.reason ? ` (${removedWordNotice.reason})` : ""}.
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            {onModeChange && (
              <button
                type="button"
                onClick={() => {
                  onModeChange("original");
                  onSeek(removedWordNotice.startMs);
                  setRemovedWordNotice(null);
                }}
                className="rounded bg-danger px-2 py-0.5 text-[10px] font-semibold text-white transition-colors hover:bg-danger/80"
              >
                Jump in Original
              </button>
            )}
            <button
              type="button"
              onClick={() => setRemovedWordNotice(null)}
              className="text-danger/70 hover:text-danger"
              aria-label="Dismiss notice"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      <div
        ref={scrollRef}
        className="min-h-0 flex-1 overflow-y-auto px-3 py-3 text-[13px] leading-[1.8] text-text-secondary selection:bg-primary/25"
        onScroll={() => {
          if (!programmaticScrollRef.current) {
            manualScrollUntilRef.current = Date.now() + 3000;
          }
        }}
      >
        {!transcript ? (
          <p className="py-4 text-[11px] text-text-muted">Preparing transcript…</p>
        ) : transcriptSegments.length === 0 ? (
          <p className="py-4 text-[11px] text-text-muted">No spoken transcript available.</p>
        ) : transcriptViewMode === "corrected" ? (
          <div className="space-y-4 pb-3">
            {(correctedTranscript?.segments || []).length === 0 ? (
              <p className="py-4 text-[11px] text-text-muted">
                No corrected script segments available yet. Leo will provide source-grounded
                corrections upon analysis.
              </p>
            ) : (
              (correctedTranscript?.segments || []).map((seg) => {
                const isModified = seg.change_type !== "KEEP";
                const segStartMs =
                  mode === "original"
                    ? seg.source_start_ms
                    : (seg.edited_start_ms ?? seg.source_start_ms);
                const segEndMs =
                  mode === "original"
                    ? seg.source_end_ms
                    : (seg.edited_end_ms ?? seg.source_end_ms);
                const segSelection: TranscriptRangeSelection = {
                  id: `corr-seg-${seg.segment_id}`,
                  label: `Corrected: ${seg.corrected_text}`,
                  startMs: segStartMs,
                  endMs: segEndMs,
                };
                const isSelected =
                  selectedRange &&
                  selectedRange.startMs >= segStartMs &&
                  selectedRange.endMs <= segEndMs;
                return (
                  <article
                    key={seg.segment_id}
                    className={`rounded-md border p-3 transition-colors ${
                      isSelected
                        ? "border-primary/40 bg-primary/5"
                        : isModified
                          ? "border-emerald-500/30 bg-emerald-500/5"
                          : "border-border-subtle/50 bg-surface-1/50"
                    }`}
                  >
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <button
                        type="button"
                        className="font-mono text-[10px] tabular-nums text-text-muted transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                        onClick={() => selectRange(segSelection)}
                        title={`Seek to ${formatModeTimecode(seg.source_start_ms, seg.edited_start_ms)}`}
                      >
                        {formatModeTimecode(seg.source_start_ms, seg.edited_start_ms)} →{" "}
                        {formatModeTimecode(seg.source_end_ms, seg.edited_end_ms)}
                      </button>
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`rounded border px-1.5 py-0.5 text-[9px] font-semibold ${
                            isModified
                              ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-400"
                              : "border-border-subtle bg-surface-3 text-text-muted"
                          }`}
                        >
                          {seg.change_type}
                        </span>
                        <span className="rounded border border-info/40 bg-info/10 px-1.5 py-0.5 text-[9px] font-semibold text-info">
                          {seg.entailment_verdict}
                        </span>
                        {onSendRangeToChat && (
                          <button
                            type="button"
                            onClick={() => onSendRangeToChat(segSelection)}
                            className="flex items-center gap-1 rounded bg-primary/10 px-1.5 py-0.5 text-[9px] font-semibold text-primary transition-colors hover:bg-primary/20"
                            title="Send range to Leo Chat"
                          >
                            <MessageSquare className="size-2.5" />
                            Ask Leo
                          </button>
                        )}
                      </div>
                    </div>

                    {isModified ? (
                      <div className="space-y-1.5">
                        <div className="text-[12px] leading-relaxed text-text-muted">
                          <span className="mr-1.5 font-mono text-[10px] uppercase font-bold text-danger/80">
                            Original:
                          </span>
                          <span className="line-through decoration-danger/70">
                            {seg.original_text}
                          </span>
                        </div>
                        <div className="text-[13px] font-medium leading-relaxed text-text-primary">
                          <span className="mr-1.5 font-mono text-[10px] uppercase font-bold text-emerald-400">
                            Corrected:
                          </span>
                          <span className="text-emerald-300 font-semibold">
                            {seg.corrected_text}
                          </span>
                        </div>
                        {seg.reason && (
                          <div className="pt-1 text-[11px] text-text-secondary">
                            <span className="font-semibold text-text-muted">Reason:</span>{" "}
                            {seg.reason}
                          </div>
                        )}
                        {seg.visual_evidence && (
                          <div className="text-[10px] italic text-text-muted">
                            <span className="font-semibold not-italic">Visual context:</span>{" "}
                            {seg.visual_evidence}
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-[13px] leading-relaxed text-text-primary/90">
                        {seg.corrected_text}
                      </p>
                    )}
                  </article>
                );
              })
            )}
          </div>
        ) : (
          <div className="space-y-5 pb-3">
            {transcriptSegments.map((segment) => {
              const segmentWords = (transcript.words ?? []).filter(
                (word) =>
                  word.index >= segment.word_start_index && word.index <= segment.word_end_index,
              );
              const segmentDecisions = decisions.filter(
                (decision) =>
                  decision.transcript_end_word >= segment.word_start_index &&
                  decision.transcript_start_word <= segment.word_end_index,
              );
              const segmentSelection: TranscriptRangeSelection = {
                id: `transcript-segment-${segment.segment_id}`,
                label: `Transcript: ${segment.text}`,
                startMs: segment.start_ms,
                endMs: segment.end_ms,
              };
              const isRangeInSegment =
                selectedRange &&
                selectedRange.startMs >= segment.start_ms &&
                selectedRange.endMs <= segment.end_ms;

              return (
                <article
                  key={segment.segment_id}
                  className={`rounded-md border px-2.5 py-2.5 transition-colors ${
                    isRangeInSegment
                      ? "border-primary/30 bg-primary/5"
                      : "border-transparent bg-transparent"
                  }`}
                >
                  <div className="mb-1.5 flex items-center justify-between gap-2">
                    <button
                      type="button"
                      className="font-mono text-[10px] tabular-nums text-text-muted transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                      onClick={() => {
                        selectRange(segmentSelection);
                        onSelectSegment?.(segment);
                      }}
                      title={`Select sentence at ${formatModeTimecode(segment.start_ms)}`}
                    >
                      {formatModeTimecode(segment.start_ms)}
                    </button>
                    {isRangeInSegment && selectedRange && onSendRangeToChat && (
                      <button
                        type="button"
                        onClick={() => {
                          onSendRangeToChat?.(selectedRange);
                          onSelectSegment?.(segment);
                        }}
                        className="flex items-center gap-1 rounded bg-primary/10 px-1.5 py-1 text-[9px] font-semibold text-primary transition-colors hover:bg-primary/20 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                      >
                        <MessageSquare className="size-2.5" aria-hidden="true" />
                        Send range to Leo Chat
                      </button>
                    )}
                  </div>

                  <p className="select-text text-[13px] leading-7 text-text-primary/90">
                    {segmentWords.length > 0
                      ? segmentWords.map((word, wordPosition) => {
                          const isActive = word.index === activeWordIndex;
                          const decisionsAtWord = segmentDecisions.filter(
                            (decision) =>
                              word.index >= decision.transcript_start_word &&
                              word.index <= decision.transcript_end_word,
                          );
                          const wordDecision = decisionsAtWord[0];
                          const isSelectedDecision = decisionsAtWord.some(
                            (decision) => decision.decision_id === selectedDecisionId,
                          );
                          const { isCut, cut } = isWordInExecutableCut(word, edl);
                          const isEditedMode = mode !== "original";
                          const isRemovedInEdited = isCut && isEditedMode;
                          // Check if there is an inter-word pause cut immediately preceding this word
                          const prevWord = wordPosition > 0 ? segmentWords[wordPosition - 1] : null;
                          const precedingCut = prevWord
                            ? executableCuts.find(
                                (c) =>
                                  c.safe_start_ms >= prevWord.end_ms - 200 &&
                                  c.safe_end_ms <= word.start_ms + 200 &&
                                  c.cut_id !== cut?.cut_id,
                              )
                            : null;

                          const wordSelection: TranscriptRangeSelection = {
                            id: `transcript-word-${word.index}`,
                            label: `Transcript word: ${word.text}`,
                            startMs: word.start_ms,
                            endMs: word.end_ms,
                          };

                          const handleWordClick = () => {
                            if (isRemovedInEdited) {
                              setRemovedWordNotice({
                                wordText: word.text,
                                startMs: word.start_ms,
                                reason: cut?.decision_type
                                  ? formatCutLabel(
                                      cut.decision_type,
                                      cut.removed_duration_ms ??
                                        cut.safe_end_ms - cut.safe_start_ms,
                                    )
                                  : "Removed by edit decision",
                              });
                              onSelectWord?.(word);
                              onRangeSelect?.(wordSelection);
                              return;
                            }
                            setRemovedWordNotice(null);
                            selectRange(wordSelection);
                            onSelectWord?.(word);
                            if (wordDecision) onSelectDecision(wordDecision);
                          };

                          return (
                            <React.Fragment key={word.index}>
                              {precedingCut && (
                                <span
                                  className="mx-1 inline-flex select-none items-center rounded border border-danger/30 bg-danger/10 px-1 py-0 text-[9px] font-mono text-danger/80 align-baseline"
                                  title={formatCutLabel(
                                    precedingCut.decision_type,
                                    precedingCut.removed_duration_ms ??
                                      precedingCut.safe_end_ms - precedingCut.safe_start_ms,
                                  )}
                                >
                                  {(
                                    (precedingCut.removed_duration_ms ??
                                      precedingCut.safe_end_ms - precedingCut.safe_start_ms) / 1000
                                  ).toFixed(1)}
                                  s cut
                                </span>
                              )}
                              {shouldInsertSpace(word.text, wordPosition) ? " " : null}
                              <button
                                ref={isActive ? activeWordRef : undefined}
                                type="button"
                                onClick={handleWordClick}
                                className={`rounded-[3px] px-0.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary ${
                                  isActive
                                    ? "bg-primary font-medium text-white shadow-xs"
                                    : isRemovedInEdited
                                      ? "line-through decoration-danger/70 text-danger/80 bg-danger/10 hover:bg-danger/15 border border-danger/30"
                                      : isCut && mode === "original"
                                        ? "text-text-primary hover:bg-surface-3 border-b border-dotted border-danger/50"
                                        : selectedRange?.id === wordSelection.id
                                          ? "bg-primary/20 text-text-primary"
                                          : isSelectedDecision
                                            ? "bg-surface-3 text-text-primary"
                                            : "hover:bg-surface-3 hover:text-text-primary"
                                }`}
                                aria-label={`${word.text}, ${formatModeTimecode(word.start_ms)}`}
                                aria-pressed={selectedRange?.id === wordSelection.id}
                                data-word-index={word.index}
                                data-removed={isRemovedInEdited ? "true" : undefined}
                                title={
                                  isRemovedInEdited
                                    ? `[Cut] "${word.text}" removed from edited version`
                                    : `Seek to ${formatModeTimecode(word.start_ms)}`
                                }
                              >
                                {word.text}
                              </button>
                            </React.Fragment>
                          );
                        })
                      : segment.text}
                  </p>

                  {segmentDecisions.length > 0 && (
                    <div
                      className="mt-2.5 space-y-1.5 border-l border-border-subtle pl-2"
                      aria-label="Edit annotations"
                    >
                      {segmentDecisions.map((decision) => {
                        const durationSeconds = Math.max(
                          0,
                          (decision.source_end_ms - decision.source_start_ms) / 1000,
                        ).toFixed(2);
                        const previousWord = (transcript.words ?? [])
                          .filter((word) => word.index < decision.transcript_start_word)
                          .at(-1)?.text;
                        const isCoverage = decision.decision_type === "SOURCE_COVER";
                        const isProtected = decision.decision_type === "KEEP_FOR_CLARITY";
                        const AnnotationIcon = isCoverage
                          ? Layers
                          : isProtected
                            ? ShieldCheck
                            : Scissors;

                        return (
                          <button
                            key={decision.decision_id}
                            type="button"
                            onClick={() => {
                              const decisionRange: TranscriptRangeSelection = {
                                id: `transcript-decision-${decision.decision_id}`,
                                label: `${decisionTitle(decision)}: ${decision.concise_reason}`,
                                startMs: decision.source_start_ms,
                                endMs: decision.source_end_ms,
                              };
                              selectRange(decisionRange);
                              onSelectDecision(decision);
                            }}
                            className={`flex w-full items-start gap-1.5 rounded px-1.5 py-1 text-left text-[10px] leading-relaxed transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary ${
                              selectedDecisionId === decision.decision_id
                                ? "bg-surface-2 text-text-primary"
                                : "text-text-muted"
                            }`}
                          >
                            <AnnotationIcon
                              className={`mt-0.5 size-3 shrink-0 ${
                                isCoverage
                                  ? "text-info"
                                  : isProtected
                                    ? "text-success"
                                    : "text-danger"
                              }`}
                              aria-hidden="true"
                            />
                            <span>
                              {isPauseDecision(decision) ? (
                                <>
                                  [ {durationSeconds}s pause removed
                                  {previousWord ? ` after “${previousWord}”` : ""} ] ·{" "}
                                  {decision.concise_reason}
                                </>
                              ) : isRemovedSpeech(decision) ? (
                                <>
                                  <span className="line-through decoration-danger/70">
                                    {decision.original_text}
                                  </span>
                                  <ArrowRight className="mx-1 inline size-2.5" aria-hidden="true" />
                                  {decisionTitle(decision)} · {durationSeconds}s ·{" "}
                                  {decision.concise_reason}
                                </>
                              ) : isCoverage ? (
                                <>
                                  [ {decisionTitle(decision)}: {decision.concise_reason} ]
                                </>
                              ) : (
                                <>
                                  [ {decisionTitle(decision)}: {decision.concise_reason} ]
                                </>
                              )}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
};
