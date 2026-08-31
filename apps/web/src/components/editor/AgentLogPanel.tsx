import {
  CheckCircle2,
  Clock3,
  Film,
  Layers,
  Scissors,
  ShieldAlert,
  Sparkles,
  Wrench,
} from "lucide-react";
import React, { useMemo } from "react";
import { type AgentActivity, type EditorDecision, formatTimecode } from "../../lib/edl-adapter";

interface AgentLogPanelProps {
  activities?: AgentActivity[];
  decisions?: EditorDecision[];
  statusMessage?: string | null;
  onSeek?: (timeMs: number) => void;
  onSelectActivity?: (activity: AgentActivity) => void;
  className?: string;
}

interface ExecutionEntry {
  activity: AgentActivity;
  action: string;
  reason: string;
  status: "In progress" | "Accepted" | "Rejected" | "Completed" | "Review";
  tool: string;
  decision?: EditorDecision;
}

const includesAny = (value: string, candidates: string[]): boolean =>
  candidates.some((candidate) => value.includes(candidate));

const cleanReason = (raw: string, decision?: EditorDecision): string => {
  if (decision?.concise_reason) return decision.concise_reason;
  return raw.replace(/^\[[A-Z_]+\]\s*/u, "");
};

const describeActivity = (
  activity: AgentActivity,
  decision?: EditorDecision,
): Omit<ExecutionEntry, "activity" | "decision"> => {
  const key = `${activity.activity_type} ${activity.message}`.toLowerCase();
  const reasonText = cleanReason(activity.message, decision);

  if (includesAny(key, ["analyz", "inspect", "reviewing footage", "media"])) {
    return {
      action: includesAny(key, ["inspect", "media"])
        ? "Inspected source media"
        : "Analyzed the full video",
      reason: reasonText,
      status: includesAny(key, ["reviewing", "progress", "started"]) ? "In progress" : "Completed",
      tool: "Gemini video analysis",
    };
  }
  if (includesAny(key, ["reject", "unsafe"])) {
    return {
      action: "Rejected an unsafe cut",
      reason: reasonText,
      status: "Rejected",
      tool: "Cut safety evaluator",
    };
  }
  if (includesAny(key, ["accept", "approved cut", "cut safe"])) {
    return {
      action: "Accepted a safe cut",
      reason: reasonText,
      status: "Accepted",
      tool: "Cut safety evaluator",
    };
  }
  if (includesAny(key, ["propos", "decision", "edit plan", "edl"])) {
    return {
      action: "Proposed an editorial change",
      reason: reasonText,
      status: "Review",
      tool: "Editorial decision tools",
    };
  }
  if (includesAny(key, ["coverage"])) {
    return {
      action: "Identified visual coverage",
      reason: reasonText,
      status: "Completed",
      tool: "Visual coverage analyzer",
    };
  }
  if (includesAny(key, ["voiceover", "voice over", "narration", "tts"])) {
    return {
      action: "Generated voiceover",
      reason: reasonText,
      status: "Completed",
      tool: "Gemini 3.1 Flash TTS",
    };
  }
  if (includesAny(key, ["music", "mix", "loudness"])) {
    return {
      action: "Mixed background music",
      reason: reasonText,
      status: "Completed",
      tool: "Audio mixer",
    };
  }
  if (includesAny(key, ["render", "preview"])) {
    return {
      action: includesAny(key, ["review", "inspect"])
        ? "Reviewed the rendered preview"
        : "Rendered the edited preview",
      reason: reasonText,
      status: "Completed",
      tool: includesAny(key, ["review", "inspect"]) ? "Leo preview review" : "FFmpeg renderer",
    };
  }
  if (includesAny(key, ["issue", "problem", "flag"])) {
    return {
      action: "Detected an issue",
      reason: reasonText,
      status: "In progress",
      tool: "Quality guard",
    };
  }
  return {
    action: "Recorded an editorial action",
    reason: reasonText,
    status: "Completed",
    tool: "Leo editor",
  };
};

const formatClockTime = (createdAt?: string): string => {
  if (!createdAt) return "Run event";
  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) return "Run event";
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
};

const statusClasses: Record<ExecutionEntry["status"], string> = {
  "In progress": "border-primary/30 bg-primary/10 text-primary",
  Accepted: "border-success/30 bg-success/10 text-success",
  Rejected: "border-danger/30 bg-danger/10 text-danger",
  Completed: "border-border-subtle bg-surface-3 text-text-secondary",
  Review: "border-warning/30 bg-warning/10 text-warning",
};

export const AgentLogPanel: React.FC<AgentLogPanelProps> = ({
  activities = [],
  decisions = [],
  statusMessage = null,
  onSeek,
  onSelectActivity,
  className = "",
}) => {
  const entries = useMemo<ExecutionEntry[]>(() => {
    const decisionMap = new Map(decisions.map((decision) => [decision.decision_id, decision]));
    return [...activities]
      .sort((left, right) => {
        const leftTime = left.created_at ? Date.parse(left.created_at) : 0;
        const rightTime = right.created_at ? Date.parse(right.created_at) : 0;
        return leftTime - rightTime;
      })
      .map((activity) => {
        const dec = activity.related_decision_id
          ? decisionMap.get(activity.related_decision_id)
          : undefined;
        return {
          activity,
          decision: dec,
          ...describeActivity(activity, dec),
        };
      });
  }, [activities, decisions]);
  return (
    <section
      className={`flex min-h-0 flex-1 flex-col overflow-hidden ${className}`}
      aria-label="Leo execution history"
      data-testid="agent-log-panel"
      id="agent-activity-feed"
    >
      {statusMessage && (
        <div
          className="flex items-center gap-2 border-b border-border-subtle bg-primary/5 px-3 py-2 text-[11px] text-text-secondary"
          role="status"
        >
          <Clock3 className="size-3.5 animate-pulse text-primary" aria-hidden="true" />
          <span>{statusMessage}</span>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
        {entries.length === 0 ? (
          <div className="flex h-40 flex-col items-center justify-center gap-2 text-center">
            <Film className="size-5 text-text-muted" aria-hidden="true" />
            <p className="max-w-52 text-[11px] leading-relaxed text-text-muted">
              Leo&apos;s execution history will appear here as the edit runs.
            </p>
          </div>
        ) : (
          <ol className="relative space-y-3 before:absolute before:bottom-2 before:left-[7px] before:top-2 before:w-px before:bg-border-subtle">
            {entries.map((entry) => {
              const startMs = entry.decision?.source_start_ms;
              const endMs = entry.decision?.source_end_ms;
              const clickable = typeof startMs === "number";
              const Icon =
                entry.status === "Rejected"
                  ? ShieldAlert
                  : entry.tool.includes("coverage") || entry.tool.includes("Coverage")
                    ? Layers
                    : entry.tool.includes("cut") || entry.tool.includes("Cut")
                      ? Scissors
                      : entry.status === "Completed" || entry.status === "Accepted"
                        ? CheckCircle2
                        : Sparkles;

              return (
                <li key={entry.activity.activity_id} className="relative pl-5">
                  <span className="absolute left-0 top-1.5 z-10 flex size-3.5 items-center justify-center rounded-full border border-border-strong bg-surface-1">
                    <Icon className="size-2.5 text-text-muted" aria-hidden="true" />
                  </span>
                  <button
                    type="button"
                    disabled={!clickable}
                    onClick={() => {
                      if (typeof startMs === "number") onSeek?.(startMs);
                      onSelectActivity?.(entry.activity);
                    }}
                    className="w-full rounded-md border border-border-subtle bg-surface-2/50 p-2.5 text-left transition-colors enabled:hover:border-border-strong enabled:hover:bg-surface-2 disabled:cursor-default"
                    data-testid="activity-message-leo"
                    data-seek-btn="bubble-seek-btn"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-[11px] font-semibold leading-snug text-text-primary">
                          {entry.action}
                        </p>
                        <p className="mt-0.5 font-mono text-[9px] tabular-nums text-text-muted">
                          {typeof startMs === "number" && typeof endMs === "number"
                            ? `${formatTimecode(startMs)} – ${formatTimecode(endMs)}`
                            : formatClockTime(entry.activity.created_at)}
                        </p>
                      </div>
                      <span
                        className={`shrink-0 rounded border px-1.5 py-0.5 text-[9px] font-semibold ${statusClasses[entry.status]}`}
                      >
                        {entry.status}
                      </span>
                    </div>
                    <p className="mt-2 text-[10px] leading-relaxed text-text-secondary">
                      {entry.reason}
                    </p>
                    <div className="mt-2 flex items-center gap-1.5 text-[9px] text-text-muted">
                      <Wrench className="size-2.5" aria-hidden="true" />
                      <span>Tool: {entry.tool}</span>
                    </div>
                  </button>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </section>
  );
};
