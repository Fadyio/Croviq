import React from "react";
import { Loader2 } from "lucide-react";
import { formatTimecode } from "../../lib/edl-adapter";
import type { AgentActivity, DirectorReview, EditorDecision } from "../../lib/edl-adapter";

interface AgentActivityFeedProps {
  activities?: AgentActivity[];
  decisions?: EditorDecision[];
  review?: DirectorReview | null;
  statusMessage?: string | null;
  onSelectActivity?: (activity: AgentActivity) => void;
  className?: string;
}

const leoMessages: Partial<Record<EditorDecision["decision_type"], string>> = {
  KEEP: "Preserved this section.",
  KEEP_FOR_CLARITY: "Kept this section for technical clarity.",
  BROLL_COVER_CANDIDATE: "Found a section that would benefit from visual coverage.",
  REMOVE_FILLER: "Removed a filler phrase.",
  REMOVE_FALSE_START: "Removed a false start.",
  REMOVE_REPETITION: "Removed a repeated point.",
  TRIM_PAUSE: "Tightened a pause.",
  TIGHTEN_EXPLANATION: "Tightened this explanation.",
  SHORT_CANDIDATE: "Marked a strong standalone moment.",
};

const mayaMessages = {
  APPROVE: "Approved Leo's edit.",
  REJECT: "Kept the original section.",
  MODIFY: "Adjusted Leo's proposed edit.",
} as const;

const presentActivity = (
  activity: AgentActivity,
  decisions: EditorDecision[],
  review: DirectorReview | null,
): { message: string; decision?: EditorDecision } => {
  const decision = activity.related_decision_id
    ? decisions.find((candidate) => candidate.decision_id === activity.related_decision_id)
    : undefined;

  if (activity.agent.toLowerCase() === "maya" && decision) {
    const verdict = review?.decisions?.find(
      (candidate) => candidate.editor_decision_id === decision.decision_id,
    )?.verdict;
    if (verdict) return { message: mayaMessages[verdict], decision };
  }
  if (decision) {
    return {
      message: leoMessages[decision.decision_type] ?? "Reviewed this section.",
      decision,
    };
  }

  const sanitized = activity.message
    .replace(/^\[[A-Z_]+\]\s*/u, "")
    .replace(/^At \d{2}:\d{2}(?:\.\d+)?,?\s*/u, "")
    .trim();
  return { message: sanitized || "Updated the production." };
};

export const AgentActivityFeed: React.FC<AgentActivityFeedProps> = ({
  activities = [],
  decisions = [],
  review = null,
  statusMessage = null,
  onSelectActivity,
  className = "",
}) => (
  <div className={className} data-testid="agent-activity-feed">
    {statusMessage && (
      <div
        className="mb-2 flex items-center gap-2 rounded-md bg-surface-2/70 px-2.5 py-2 text-[11px] text-text-secondary"
        role="status"
      >
        <Loader2 className="size-3.5 shrink-0 animate-spin text-primary motion-reduce:animate-none" />
        <span>{statusMessage}</span>
      </div>
    )}

    {activities.length === 0 && !statusMessage ? (
      <p className="py-3 text-[11px] text-text-muted">Activity will appear as work completes.</p>
    ) : (
      <ol className="relative">
        {activities.map((activity, index) => {
          const isLeo = activity.agent.toLowerCase() === "leo";
          const presented = presentActivity(activity, decisions, review);
          const clickable = Boolean(presented.decision && onSelectActivity);
          const content = (
            <>
              <span
                className={`relative z-10 mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full border bg-surface-2 text-[9px] font-semibold ${
                  isLeo ? "border-primary/30 text-primary" : "border-info/30 text-info"
                }`}
                aria-hidden="true"
              >
                {isLeo ? "L" : "M"}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-baseline justify-between gap-2">
                  <span className="text-[11px] font-semibold text-text-primary">
                    {isLeo ? "Leo" : "Maya"}
                  </span>
                  {activity.created_at && (
                    <time
                      className="shrink-0 text-[9px] tabular-nums text-text-muted"
                      dateTime={activity.created_at}
                    >
                      {new Date(activity.created_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </time>
                  )}
                </span>
                <span className="mt-0.5 block text-[11px] leading-4 text-text-secondary">
                  {presented.message}
                </span>
                {presented.decision && (
                  <span className="mt-1 block text-[9px] tabular-nums text-text-muted">
                    {formatTimecode(presented.decision.source_start_ms)}
                  </span>
                )}
              </span>
            </>
          );

          return (
            <li key={activity.activity_id} className="relative flex gap-2.5 pb-3 last:pb-0">
              {index < activities.length - 1 && (
                <span
                  aria-hidden="true"
                  className="absolute top-5 bottom-0 left-[11px] w-px bg-border-subtle"
                />
              )}
              {clickable ? (
                <button
                  type="button"
                  className="-m-1 flex w-[calc(100%+0.5rem)] gap-2.5 rounded-md p-1 text-left transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                  onClick={() => onSelectActivity?.(activity)}
                  aria-label={`${presented.message} Seek to ${formatTimecode(
                    presented.decision!.source_start_ms,
                  )}`}
                >
                  {content}
                </button>
              ) : (
                <div className="flex w-full gap-2.5">{content}</div>
              )}
            </li>
          );
        })}
      </ol>
    )}
  </div>
);
