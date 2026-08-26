import React from "react";
import { X, Play, CheckCircle2, AlertCircle, Scissors, Layers, Sparkles } from "lucide-react";
import {
  formatTimecode,
  type EditorDecision,
  type DirectorDecision,
  type TimelineBlock,
} from "../../lib/edl-adapter";

interface DecisionInspectorProps {
  decision: EditorDecision | null;
  directorDecision?: DirectorDecision | null;
  selectedBlock?: TimelineBlock | null;
  onClose: () => void;
  onSeek: (targetMs: number) => void;
  className?: string;
}

export const DecisionInspector: React.FC<DecisionInspectorProps> = ({
  decision,
  directorDecision,
  selectedBlock,
  onClose,
  onSeek,
  className = "",
}) => {
  if (!decision && !selectedBlock) return null;

  // Resolve fields from decision or selectedBlock
  const action = decision?.action || selectedBlock?.details?.safetyStatus || "keep";
  const decisionType = decision?.decision_type || selectedBlock?.label || "EDITORIAL_DECISION";
  const startMs = decision?.source_start_ms ?? selectedBlock?.startMs ?? 0;
  const endMs = decision?.source_end_ms ?? selectedBlock?.endMs ?? 0;
  const originalText = decision?.original_text || selectedBlock?.details?.originalText;
  const leoReason = decision?.concise_reason || selectedBlock?.details?.conciseReason;
  const mayaVerdict = directorDecision?.verdict || selectedBlock?.details?.mayaVerdict || "APPROVE";
  const mayaReason = directorDecision?.concise_reason || selectedBlock?.details?.mayaReason;
  const confidence = decision?.confidence || selectedBlock?.details?.confidence;

  const durationSec = ((endMs - startMs) / 1000).toFixed(1);

  return (
    <div
      className={`p-3.5 bg-surface-1 rounded-xl border border-border-strong flex flex-col gap-3 shadow-lg ring-1 ring-primary/20 ${className}`}
      data-testid="decision-inspector"
    >
      {/* Header with Type, Verdict & Close button */}
      <div className="flex items-center justify-between gap-2 border-b border-border-subtle pb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-primary/15 text-primary border border-primary/25">
            {decisionType.replace(/_/g, " ")}
          </span>
          <span className="text-[11px] font-mono text-text-muted">
            {formatTimecode(startMs)} &rarr; {formatTimecode(endMs)} ({durationSec}s)
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => onSeek(startMs)}
            className="p-1 rounded text-text-muted hover:text-text-primary hover:bg-surface-2 transition-colors"
            title="Seek to decision start"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
          </button>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded text-text-muted hover:text-text-primary hover:bg-surface-2 transition-colors"
            title="Close inspector"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Spoken Transcript Excerpt */}
      {originalText && (
        <div className="flex flex-col gap-1 p-2 rounded-lg bg-surface-2/60 border border-border-subtle text-xs">
          <span className="text-[10px] uppercase tracking-wider font-semibold text-text-muted">
            Spoken Text
          </span>
          <p className="text-[12px] text-text-primary italic leading-relaxed">
            &ldquo;{originalText}&rdquo;
          </p>
        </div>
      )}

      {/* Editorial Recommendations & Director Verdict */}
      <div className="space-y-2 text-xs">
        {/* Leo's Proposal */}
        <div className="flex flex-col gap-1 p-2.5 rounded-lg bg-surface-2/40 border border-border-subtle">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-text-primary flex items-center gap-1.5">
              <span className="w-4 h-4 rounded-full bg-primary/20 text-primary flex items-center justify-center text-[9px] font-bold">
                L
              </span>
              <span>Leo &middot; Dialogue Proposal ({action.toUpperCase()})</span>
            </span>
            {confidence && (
              <span className="text-[10px] font-mono text-text-muted">
                {Math.round(confidence * 100)}% conf
              </span>
            )}
          </div>
          {leoReason && (
            <p className="text-[11px] text-text-secondary leading-snug pl-5">{leoReason}</p>
          )}
        </div>

        {/* Maya's Director Review */}
        <div className="flex flex-col gap-1 p-2.5 rounded-lg bg-surface-2/40 border border-border-subtle">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-text-primary flex items-center gap-1.5">
              <span className="w-4 h-4 rounded-full bg-info/20 text-info flex items-center justify-center text-[9px] font-bold">
                M
              </span>
              <span>Maya &middot; Director Verdict</span>
            </span>
            <span
              className={`px-1.5 py-0.2 rounded text-[10px] font-bold uppercase tracking-wider ${
                mayaVerdict === "APPROVE"
                  ? "bg-success/15 text-success border border-success/30"
                  : "bg-warning/15 text-warning border border-warning/30"
              }`}
            >
              {mayaVerdict}
            </span>
          </div>
          {mayaReason && (
            <p className="text-[11px] text-text-secondary leading-snug pl-5">{mayaReason}</p>
          )}
        </div>
      </div>
    </div>
  );
};
