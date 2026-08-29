import React from "react";
import { Play, X } from "lucide-react";
import { formatTimecode, type EditorDecision, type TimelineBlock } from "../../lib/edl-adapter";

interface DecisionInspectorProps {
  decision: EditorDecision | null;
  selectedBlock?: TimelineBlock | null;
  onClose: () => void;
  onSeek: (targetMs: number) => void;
  className?: string;
}

const decisionLabel = (decisionType: string): string => {
  if (decisionType === "BROLL_COVER_CANDIDATE" || decisionType === "BROLL_COVER")
    return "Visual coverage";
  if (decisionType === "KEEP_FOR_CLARITY" || decisionType === "KEEP")
    return "Preserved for clarity";
  if (decisionType === "REMOVE_SILENCE" || decisionType === "TRIM_PAUSE") return "Silence removed";
  if (decisionType === "TIGHTEN_PAUSE" || decisionType === "TIGHTEN_EXPLANATION")
    return "Pause tightened";
  if (decisionType === "REMOVE_FALSE_START") return "False start removed";
  if (decisionType === "REMOVE_REPETITION") return "Repetition removed";
  if (decisionType === "REMOVE_FILLER") return "Filler removed";
  if (decisionType.startsWith("REMOVE_")) return "Dialogue removal";
  return decisionType
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./u, (character) => character.toUpperCase());
};

export const DecisionInspector: React.FC<DecisionInspectorProps> = ({
  decision,
  selectedBlock,
  onClose,
  onSeek,
  className = "",
}) => {
  if (!decision && !selectedBlock) return null;

  const type = decision?.decision_type || selectedBlock?.label || "Editorial note";
  const startMs = decision?.source_start_ms ?? selectedBlock?.startMs ?? 0;
  const endMs = decision?.source_end_ms ?? selectedBlock?.endMs ?? 0;
  const originalText = decision?.original_text || selectedBlock?.details?.originalText;
  const leoReason = decision?.concise_reason || selectedBlock?.details?.conciseReason;
  const confidence = decision?.confidence ?? selectedBlock?.details?.confidence;

  return (
    <div
      className={`rounded-lg border border-border-strong bg-surface-1 p-3 ${className}`}
      data-testid="decision-inspector"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold text-text-primary">{decisionLabel(type)}</p>
          <p className="mt-0.5 text-[9px] tabular-nums text-text-muted">
            {formatTimecode(startMs)}–{formatTimecode(endMs)}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onSeek(startMs)}
            className="rounded p-1 text-text-muted transition-colors hover:bg-surface-2 hover:text-text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
            title="Seek to decision start"
          >
            <Play className="size-3.5 fill-current" />
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-text-muted transition-colors hover:bg-surface-2 hover:text-text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
            title="Close details"
          >
            <X className="size-3.5" />
          </button>
        </div>
      </div>

      {originalText && (
        <blockquote className="mt-3 border-l border-border-strong pl-2.5 text-[11px] leading-4 text-text-secondary">
          “{originalText}”
        </blockquote>
      )}

      <dl className="mt-3 space-y-3 border-t border-border-subtle pt-3">
        <div>
          <dt className="flex items-center justify-between gap-2 text-[10px] font-semibold text-text-primary">
            <span>Leo · Video Editor</span>
            {confidence !== undefined && (
              <span className="text-primary">{Math.round(confidence * 100)}% confidence</span>
            )}
          </dt>
          {leoReason && (
            <dd className="mt-1 text-[11px] leading-4 text-text-secondary">{leoReason}</dd>
          )}
        </div>
      </dl>
    </div>
  );
};
