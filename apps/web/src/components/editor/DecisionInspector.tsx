import {
  Activity,
  Bookmark,
  Eye,
  type LucideIcon,
  MousePointer2,
  Pause,
  Play,
  Repeat2,
  ShieldAlert,
  X,
} from "lucide-react";
import React from "react";
import { type EditorDecision, formatTimecode, type TimelineBlock } from "../../lib/edl-adapter";

interface DecisionInspectorProps {
  decision: EditorDecision | null;
  selectedBlock?: TimelineBlock | null;
  onClose: () => void;
  onSeek: (targetMs: number) => void;
  className?: string;
}

const decisionLabel = (decisionType: string): string => {
  const labels: Record<string, string> = {
    BROLL_COVER_CANDIDATE: "B-Roll Coverage",
    BROLL_COVER: "B-Roll Coverage",
    SOURCE_COVER: "Use source-screen coverage",
    KEEP_FOR_CLARITY: "Preserve this explanation",
    KEEP: "Keep this section",
    REMOVE_SILENCE: "Remove dead air",
    TRIM_PAUSE: "Trim the pause",
    TIGHTEN_PAUSE: "Tighten the pause",
    TIGHTEN_EXPLANATION: "Tighten the explanation",
    REMOVE_FALSE_START: "Remove the false start",
    REMOVE_REPETITION: "Remove the repetition",
    REMOVE_FILLER: "Remove the filler",
    REMOVE_LOW_VALUE_SECTION: "Remove the low-value section",
    CHAPTER_MARKER: "Create a chapter boundary",
    CAPTION_EMPHASIS: "Emphasize the caption",
    NARRATION_REWRITE: "Rewrite the narration",
  };
  return (
    labels[decisionType] ||
    decisionType
      .toLowerCase()
      .replaceAll("_", " ")
      .replace(/^./u, (character) => character.toUpperCase())
  );
};

const resultLabel = (decision?: EditorDecision | null, block?: TimelineBlock | null): string => {
  if (block?.type === "cut-rejected") return "Not applied — continuity safety rejected the cut.";
  if (block?.type === "cut-needs-coverage") return "Applied only with visual coverage.";
  if (block?.type === "cut-safe") return "Removed from the edited timeline.";
  if (block?.type === "coverage-broll") return "Covered by a B-roll region on the timeline.";
  if (block?.type === "coverage-screen") return "Covered with source-screen footage.";
  if (decision?.action) {
    return decision.action
      .replaceAll("_", " ")
      .replace(/^./u, (character) => character.toUpperCase());
  }
  return "Recorded in the canonical edit proposal.";
};

interface EvidenceCardProps {
  icon: LucideIcon;
  label: string;
  value: string;
}

const EvidenceCard: React.FC<EvidenceCardProps> = ({ icon: Icon, label, value }) => (
  <div className="rounded-md border border-border-subtle bg-surface-2/60 p-2">
    <div className="flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-wide text-text-muted">
      <Icon className="size-3" aria-hidden="true" />
      {label}
    </div>
    <p className="mt-1 text-[10px] leading-relaxed text-text-secondary">{value}</p>
  </div>
);

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
  const durationMs = Math.max(0, endMs - startMs);
  const originalText = decision?.original_text || selectedBlock?.details?.originalText;
  const leoReason =
    decision?.concise_reason ||
    selectedBlock?.details?.conciseReason ||
    selectedBlock?.details?.summary ||
    "This element is part of the current edit.";
  const visualContext =
    decision?.visual_context ||
    (selectedBlock?.details?.coverageType
      ? `Coverage signal: ${selectedBlock.details.coverageType.replaceAll("_", " ").toLowerCase()}`
      : null);
  const isPause = type === "REMOVE_SILENCE" || type === "TRIM_PAUSE" || type === "TIGHTEN_PAUSE";
  const isRepetition = type === "REMOVE_REPETITION" || /repeat/iu.test(leoReason);
  const hasScreenInteraction = /screen|terminal|browser|cursor|click|workflow|demo/iu.test(
    `${visualContext || ""} ${leoReason}`,
  );
  const continuityRisk =
    decision?.risk ||
    selectedBlock?.details?.safetyStatus ||
    (selectedBlock?.type === "cut-rejected"
      ? "The cut would create an unsafe continuity break."
      : "No elevated continuity risk was attached to this decision.");

  return (
    <section
      className={`rounded-md border border-border-subtle bg-surface-1 ${className}`}
      aria-label="Decision inspector"
      data-testid="decision-inspector"
    >
      <div className="flex items-center justify-between border-b border-border-subtle px-3 py-2">
        <div>
          <p className="text-[9px] font-semibold uppercase tracking-wider text-text-muted">
            Decision inspector
          </p>
          <h2 className="mt-0.5 text-xs font-semibold text-text-primary">{decisionLabel(type)}</h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-1 text-text-muted hover:bg-surface-2 hover:text-text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
          aria-label="Close decision inspector"
        >
          <X className="size-3.5" />
        </button>
      </div>

      <dl className="grid grid-cols-[72px_1fr] gap-x-2 gap-y-2 border-b border-border-subtle px-3 py-3 text-[10px]">
        <dt className="font-semibold uppercase tracking-wide text-text-muted">What</dt>
        <dd className="text-text-primary">{decisionLabel(type)}</dd>

        <dt className="font-semibold uppercase tracking-wide text-text-muted">Why</dt>
        <dd className="leading-relaxed text-text-secondary">{leoReason}</dd>

        <dt className="font-semibold uppercase tracking-wide text-text-muted">Source range</dt>
        <dd>
          <button
            type="button"
            onClick={() => onSeek(startMs)}
            className="inline-flex items-center gap-1 font-mono tabular-nums text-primary hover:underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
          >
            <Play className="size-2.5 fill-current" aria-hidden="true" />
            {formatTimecode(startMs)} – {formatTimecode(endMs)}
          </button>
        </dd>

        <dt className="font-semibold uppercase tracking-wide text-text-muted">Result</dt>
        <dd className="leading-relaxed text-text-primary">
          {resultLabel(decision, selectedBlock)}
        </dd>
      </dl>

      {originalText && (
        <blockquote className="mx-3 mt-3 border-l-2 border-border-strong pl-2 text-[10px] italic leading-relaxed text-text-secondary">
          “{originalText}”
        </blockquote>
      )}

      <div className="px-3 pb-3 pt-3">
        <h3 className="mb-2 text-[9px] font-semibold uppercase tracking-wider text-text-muted">
          Evidence breakdown
        </h3>
        <div className="grid grid-cols-2 gap-2">
          <EvidenceCard
            icon={Activity}
            label="Speech activity"
            value={
              originalText
                ? `Speech is present across this ${Math.max(0.1, durationMs / 1000).toFixed(1)}s range.`
                : "No dialogue evidence is attached to this timeline element."
            }
          />
          <EvidenceCard
            icon={Eye}
            label="Visual activity"
            value={visualContext || "No specific visual change was attached to this decision."}
          />
          <EvidenceCard
            icon={Pause}
            label="Pause duration"
            value={
              isPause
                ? `${(durationMs / 1000).toFixed(2)}s pause identified in the source.`
                : "No pause edit was proposed for this range."
            }
          />
          <EvidenceCard
            icon={Repeat2}
            label="Repetition"
            value={
              isRepetition
                ? "Repeated phrasing was detected in this range."
                : "No repetition signal was attached to this decision."
            }
          />
          <EvidenceCard
            icon={MousePointer2}
            label="Screen interaction"
            value={
              hasScreenInteraction
                ? "A screen or workflow interaction is part of the visual context."
                : "No screen interaction was detected in the attached evidence."
            }
          />
          <EvidenceCard
            icon={Bookmark}
            label="Chapter context"
            value={
              decision?.preserve_context ||
              selectedBlock?.details?.summary ||
              "No chapter-specific preservation note was attached."
            }
          />
          <div className="col-span-2">
            <EvidenceCard icon={ShieldAlert} label="Continuity risk" value={continuityRisk} />
          </div>
        </div>
      </div>
    </section>
  );
};
