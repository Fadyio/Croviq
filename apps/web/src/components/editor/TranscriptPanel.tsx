import React, { useEffect, useMemo, useRef } from "react";
import { FileText, Layers, ShieldCheck } from "lucide-react";
import {
  formatTimecode,
  type EditorDecision,
  type Transcript,
  type TranscriptSegment,
} from "../../lib/edl-adapter";

interface TranscriptPanelProps {
  transcript: Transcript | null;
  currentTimeMs: number;
  decisions?: EditorDecision[];
  selectedDecisionId: string | null;
  onSelectDecision: (decision: EditorDecision | null) => void;
  onSeek: (targetMs: number) => void;
  className?: string;
}

export const TranscriptPanel: React.FC<TranscriptPanelProps> = ({
  transcript,
  currentTimeMs,
  decisions = [],
  selectedDecisionId,
  onSelectDecision,
  onSeek,
  className = "",
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeWordRef = useRef<HTMLButtonElement>(null);
  const manualScrollUntilRef = useRef(0);
  const programmaticScrollRef = useRef(false);

  const wordDecisionMap = useMemo(() => {
    const map = new Map<number, EditorDecision>();
    for (const decision of decisions) {
      for (
        let wordIndex = decision.transcript_start_word;
        wordIndex <= decision.transcript_end_word;
        wordIndex += 1
      ) {
        map.set(wordIndex, decision);
      }
    }
    return map;
  }, [decisions]);

  const activeWordIndex = useMemo(() => {
    if (!transcript?.words) return -1;
    return (
      transcript.words.find(
        (word) => currentTimeMs >= word.start_ms && currentTimeMs <= word.end_ms,
      )?.index ?? -1
    );
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

  useEffect(() => {
    manualScrollUntilRef.current = 0;
  }, []);

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
      className={`flex flex-1 min-h-0 flex-col border-t border-border-subtle pt-2.5 overflow-hidden ${className}`}
      data-testid="transcript-panel"
    >
      <div className="mb-2 flex items-center justify-between shrink-0">
        <h2 className="flex items-center gap-1.5 text-xs font-semibold text-text-primary">
          <FileText className="size-3.5 text-text-muted" />
          Transcript
        </h2>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 min-h-0 overflow-y-auto pr-2 text-[13px] leading-[1.8] text-text-secondary selection:bg-primary/25"
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
        ) : (
          <div className="space-y-3.5 pb-2">
            {transcriptSegments.map((segment) => {
              const segmentWords = (transcript.words ?? []).filter(
                (word) =>
                  word.index >= segment.word_start_index && word.index <= segment.word_end_index,
              );
              return (
                <p key={segment.segment_id} className="text-text-secondary">
                  <button
                    type="button"
                    className="mr-2.5 inline-block select-none font-mono text-[10px] tabular-nums text-text-muted/80 transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                    onClick={() => onSeek(segment.start_ms)}
                    title="Seek to paragraph"
                  >
                    {formatTimecode(segment.start_ms)}
                  </button>
                  {segmentWords.map((word) => {
                    const decision = wordDecisionMap.get(word.index);
                    const isActive = word.index === activeWordIndex;
                    const isSelected = decision?.decision_id === selectedDecisionId;
                    const isDecisionStart = decision?.transcript_start_word === word.index;
                    const isCoverage = decision?.decision_type === "BROLL_COVER_CANDIDATE";
                    const isProtected = decision?.decision_type === "KEEP_FOR_CLARITY";
                    const isSilenceCut = decision?.decision_type === "TRIM_PAUSE";
                    const isWordRemoved =
                      decision?.decision_type.startsWith("REMOVE_") ||
                      decision?.decision_type === "TIGHTEN_EXPLANATION";
                    return (
                      <React.Fragment key={word.index}>
                        {isDecisionStart && isCoverage && (
                          <Layers
                            className="mr-0.5 inline size-3 align-[-0.12em] text-info/75"
                            aria-label="Visual coverage"
                          />
                        )}
                        {isDecisionStart && isProtected && (
                          <ShieldCheck
                            className="mr-0.5 inline size-3 align-[-0.12em] text-success/75"
                            aria-label="Preserved for clarity"
                          />
                        )}
                        {isSilenceCut && isDecisionStart && (
                          <span
                            onClick={() => {
                              onSeek(decision.source_start_ms);
                              onSelectDecision(decision);
                            }}
                            className="mx-1 inline-flex items-center gap-0.5 cursor-pointer text-[9px] text-danger/85 bg-danger/10 px-1 py-0.5 rounded border border-danger/20 font-mono select-none hover:bg-danger/20 transition-colors"
                            title={decision.concise_reason}
                          >
                            ✂ -
                            {((decision.source_end_ms - decision.source_start_ms) / 1000).toFixed(
                              1,
                            )}
                            s
                          </span>
                        )}
                        <button
                          ref={isActive ? activeWordRef : undefined}
                          type="button"
                          onClick={() => {
                            onSeek(word.start_ms);
                            if (decision) onSelectDecision(decision);
                          }}
                          className={`rounded-[3px] px-0.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary ${
                            isActive
                              ? "bg-primary font-medium text-white shadow-sm"
                              : isSelected
                                ? "bg-primary/20 text-text-primary"
                                : isWordRemoved
                                  ? "text-danger/70 line-through decoration-danger/60 decoration-1"
                                  : isCoverage
                                    ? "text-text-primary underline decoration-info/60 decoration-1 underline-offset-4 hover:bg-info/10"
                                    : isProtected
                                      ? "text-text-primary underline decoration-success/60 decoration-dotted decoration-1 underline-offset-4 hover:bg-success/10"
                                      : "text-text-primary/90 hover:bg-surface-3 hover:text-text-primary"
                          }`}
                          data-word-index={word.index}
                          title={`${formatTimecode(word.start_ms)}${decision ? ` · ${decision.concise_reason}` : ""}`}
                        >
                          {word.text}
                        </button>{" "}
                      </React.Fragment>
                    );
                  })}
                </p>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
};
