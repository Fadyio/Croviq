import React, { useEffect, useRef, useState, useMemo } from "react";
import { FileText, Search, Layers, CheckCircle, Scissors, Sparkles } from "lucide-react";
import {
  formatTimecode,
  type Transcript,
  type TranscriptWord,
  type TranscriptSegment,
  type EditorDecision,
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
  const containerRef = useRef<HTMLDivElement>(null);
  const activeWordRef = useRef<HTMLSpanElement>(null);

  const [searchQuery, setSearchQuery] = useState<string>("");
  const [autoScroll, setAutoScroll] = useState<boolean>(true);

  // Map each word index to its associated editorial decision (if any)
  const wordDecisionMap = useMemo(() => {
    const map = new Map<number, EditorDecision>();
    for (const dec of decisions) {
      for (let w = dec.transcript_start_word; w <= dec.transcript_end_word; w++) {
        map.set(w, dec);
      }
    }
    return map;
  }, [decisions]);

  // Find active word index based on currentTimeMs
  const activeWordIndex = useMemo(() => {
    if (!transcript?.words) return -1;
    const word = transcript.words.find(
      (w) => currentTimeMs >= w.start_ms && currentTimeMs <= w.end_ms,
    );
    return word ? word.index : -1;
  }, [currentTimeMs, transcript?.words]);

  // Smoothly auto-scroll active word into view during playback
  useEffect(() => {
    if (!autoScroll || activeWordIndex === -1 || !activeWordRef.current) return;
    activeWordRef.current.scrollIntoView({
      block: "nearest",
      behavior: "smooth",
    });
  }, [activeWordIndex, autoScroll]);

  // Filter words/segments if user searches
  const filteredSegments = useMemo(() => {
    if (!transcript?.segments) return [];
    if (!searchQuery.trim()) return transcript.segments;

    const q = searchQuery.toLowerCase();
    return transcript.segments.filter((s) => s.text.toLowerCase().includes(q));
  }, [searchQuery, transcript?.segments]);

  return (
    <div
      ref={containerRef}
      className={`flex flex-col bg-surface-1 rounded-xl border border-border-subtle overflow-hidden shadow-md ${className}`}
      data-testid="transcript-panel"
    >
      {/* Transcript Header Bar with Word Count & Search */}
      <div className="p-3 bg-surface-2 border-b border-border-subtle flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <FileText className="w-3.5 h-3.5 text-primary shrink-0" />
          <span className="text-xs font-semibold text-text-primary tracking-tight">Transcript</span>
          {transcript?.words && (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono text-text-muted bg-surface-3 border border-border-subtle">
              {transcript.words.length} words
            </span>
          )}
        </div>

        {/* Search & Auto-scroll Toggle */}
        <div className="flex items-center gap-2">
          <div className="relative flex items-center">
            <Search className="w-3 h-3 text-text-muted absolute left-2 pointer-events-none" />
            <input
              type="text"
              placeholder="Search words..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-6 pr-2 py-0.5 text-[11px] rounded bg-surface-3 text-text-primary placeholder:text-text-muted border border-border-subtle focus:border-primary focus:outline-none w-28 sm:w-36"
            />
          </div>

          <button
            type="button"
            onClick={() => setAutoScroll(!autoScroll)}
            className={`px-2 py-0.5 text-[10px] rounded border transition-colors ${
              autoScroll
                ? "bg-primary/10 text-primary border-primary/20"
                : "bg-surface-3 text-text-muted border-border-subtle"
            }`}
            title="Auto-scroll transcript with playhead"
          >
            Auto-scroll
          </button>
        </div>
      </div>

      {/* Transcript Content Area */}
      <div className="flex-1 p-3.5 overflow-y-auto max-h-[380px] space-y-3.5 text-xs leading-relaxed selection:bg-primary/25">
        {!transcript ? (
          <div className="p-8 text-center text-text-muted text-xs">Loading transcript...</div>
        ) : filteredSegments.length === 0 ? (
          <div className="p-8 text-center text-text-muted text-xs">
            No matching phrases found for &ldquo;{searchQuery}&rdquo;
          </div>
        ) : (
          filteredSegments.map((segment) => {
            const segmentWords = (transcript.words || []).filter(
              (w) => w.index >= segment.word_start_index && w.index <= segment.word_end_index,
            );

            return (
              <div
                key={segment.segment_id}
                className="flex flex-col gap-1 p-2 rounded-lg bg-surface-2/40 hover:bg-surface-2/70 transition-colors border border-border-subtle/50"
              >
                {/* Segment Timestamp Header */}
                <div className="flex items-center justify-between text-[10px] font-mono text-text-muted">
                  <button
                    type="button"
                    onClick={() => onSeek(segment.start_ms)}
                    className="hover:text-primary transition-colors flex items-center gap-1 font-medium"
                    title="Seek to sentence start"
                  >
                    <span>{formatTimecode(segment.start_ms)}</span>
                  </button>
                </div>

                {/* Spoken Words Flow */}
                <div className="flex flex-wrap items-center gap-x-1 gap-y-1 text-text-primary text-[12px] leading-relaxed">
                  {segmentWords.map((word) => {
                    const isActive = word.index === activeWordIndex;
                    const dec = wordDecisionMap.get(word.index);
                    const isSelectedDec = dec && selectedDecisionId === dec.decision_id;
                    const isDecisionStart = dec && dec.transcript_start_word === word.index;

                    let wordBadge = null;
                    if (isDecisionStart) {
                      if (dec.decision_type === "BROLL_COVER_CANDIDATE") {
                        wordBadge = (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onSelectDecision(dec);
                            }}
                            className="inline-flex items-center gap-1 px-1.5 py-0.2 rounded text-[9px] font-medium uppercase tracking-wider bg-info/15 text-info border border-info/30 hover:bg-info/25 transition-all mr-1 align-middle"
                            title="B-Roll Coverage Region"
                          >
                            <Layers className="w-2.5 h-2.5" />
                            <span>B-Roll</span>
                          </button>
                        );
                      } else if (dec.decision_type === "KEEP_FOR_CLARITY") {
                        wordBadge = (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onSelectDecision(dec);
                            }}
                            className="inline-flex items-center gap-1 px-1.5 py-0.2 rounded text-[9px] font-medium uppercase tracking-wider bg-success/15 text-success border border-success/30 hover:bg-success/25 transition-all mr-1 align-middle"
                            title="Preserved for clarity"
                          >
                            <CheckCircle className="w-2.5 h-2.5" />
                            <span>Preserved</span>
                          </button>
                        );
                      } else if (dec.decision_type.startsWith("REMOVE_")) {
                        wordBadge = (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onSelectDecision(dec);
                            }}
                            className="inline-flex items-center gap-1 px-1.5 py-0.2 rounded text-[9px] font-medium uppercase tracking-wider bg-danger/15 text-danger border border-danger/30 hover:bg-danger/25 transition-all mr-1 align-middle"
                            title="Proposed removal"
                          >
                            <Scissors className="w-2.5 h-2.5" />
                            <span>Cut</span>
                          </button>
                        );
                      }
                    }

                    // Word styling based on active playback state and decision annotation
                    let wordClass = "cursor-pointer rounded px-0.5 py-0.2 transition-all ";
                    if (isActive) {
                      wordClass += "bg-primary text-white font-semibold shadow-sm ";
                    } else if (isSelectedDec) {
                      wordClass += "bg-primary/20 text-text-primary ring-1 ring-primary/40 ";
                    } else if (dec?.decision_type === "BROLL_COVER_CANDIDATE") {
                      wordClass += "bg-info/10 text-info/90 hover:bg-info/20 ";
                    } else if (dec?.decision_type.startsWith("REMOVE_")) {
                      wordClass += "line-through opacity-60 text-danger/80 hover:opacity-100 ";
                    } else {
                      wordClass += "hover:bg-surface-3 hover:text-text-primary ";
                    }

                    return (
                      <React.Fragment key={`word-${word.index}`}>
                        {wordBadge}
                        <span
                          ref={isActive ? activeWordRef : undefined}
                          onClick={() => {
                            onSeek(word.start_ms);
                            if (dec) onSelectDecision(dec);
                          }}
                          className={wordClass}
                          title={`${word.text} (${formatTimecode(word.start_ms)})`}
                          data-word-index={word.index}
                        >
                          {word.text}
                        </span>
                      </React.Fragment>
                    );
                  })}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
