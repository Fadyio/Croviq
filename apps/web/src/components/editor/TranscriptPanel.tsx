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
  }, [selectedDecisionId]);

  useEffect(() => {
    const container = scrollRef.current;
    const activeWord = activeWordRef.current;
    if (!container || !activeWord || activeWordIndex < 0) return;
    if (Date.now() < manualScrollUntilRef.current) return;

    const containerRect = container.getBoundingClientRect();
    const wordRect = activeWord.getBoundingClientRect();
    const readingTop = containerRect.top + containerRect.height * 0.18;
    const readingBottom = containerRect.bottom - containerRect.height * 0.18;
    if (wordRect.top >= readingTop && wordRect.bottom <= readingBottom) return;

    programmaticScrollRef.current = true;
    activeWord.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => {
      programmaticScrollRef.current = false;
    }, 500);
  }, [activeWordIndex]);

  return (
    <section
      className={`flex min-h-0 flex-col border-t border-border-subtle pt-3 ${className}`}
      data-testid="transcript-panel"
    >
      <h2 className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-text-primary">
        <FileText className="size-3.5 text-text-muted" />
        Transcript
      </h2>

      <div
        ref={scrollRef}
        className="max-h-[44vh] min-h-40 overflow-y-auto pr-2 text-[13px] leading-[1.72] text-text-secondary selection:bg-primary/25"
        onScroll={() => {
          if (!programmaticScrollRef.current) {
            manualScrollUntilRef.current = Date.now() + 3000;
          }
        }}
      >
        {!transcript ? (
          <p className="py-5 text-[11px] text-text-muted">Preparing transcript…</p>
        ) : transcriptSegments.length === 0 ? (
          <p className="py-5 text-[11px] text-text-muted">No spoken transcript available.</p>
        ) : (
          <div className="space-y-4">
            {transcriptSegments.map((segment) => {
              const segmentWords = (transcript.words ?? []).filter(
                (word) =>
                  word.index >= segment.word_start_index && word.index <= segment.word_end_index,
              );
              return (
                <p key={segment.segment_id}>
                  <button
                    type="button"
                    className="mr-2 align-baseline text-[9px] tabular-nums text-text-muted transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
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
                    const isRemoved =
                      decision?.decision_type.startsWith("REMOVE_") ||
                      decision?.decision_type === "TRIM_PAUSE" ||
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
                        <button
                          ref={isActive ? activeWordRef : undefined}
                          type="button"
                          onClick={() => {
                            onSeek(word.start_ms);
                            if (decision) onSelectDecision(decision);
                          }}
                          className={`rounded-[3px] px-px text-left transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary ${
                            isActive
                              ? "bg-primary text-white"
                              : isSelected
                                ? "bg-primary/20 text-text-primary"
                                : isRemoved
                                  ? "text-danger/65 line-through decoration-danger/70"
                                  : isCoverage
                                    ? "text-text-primary underline decoration-info/55 decoration-1 underline-offset-4 hover:bg-info/10"
                                    : isProtected
                                      ? "text-text-primary underline decoration-success/45 decoration-dotted underline-offset-4 hover:bg-success/10"
                                      : "hover:bg-surface-3 hover:text-text-primary"
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
