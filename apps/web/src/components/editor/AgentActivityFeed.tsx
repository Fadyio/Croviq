import React, { useMemo, useState } from "react";
import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { formatTimecode } from "../../lib/edl-adapter";
import type { AgentActivity, DirectorReview, EditorDecision } from "../../lib/edl-adapter";
import leoAvatar from "../../assets/agents/leo.webp";
import mayaAvatar from "../../assets/agents/maya.webp";

interface AgentActivityFeedProps {
  activities?: AgentActivity[];
  decisions?: EditorDecision[];
  review?: DirectorReview | null;
  statusMessage?: string | null;
  onSelectActivity?: (activity: AgentActivity) => void;
  className?: string;
}

const avatarMap: Record<"leo" | "maya", string> = {
  leo: leoAvatar,
  maya: mayaAvatar,
};

const leoMessages: Partial<Record<EditorDecision["decision_type"], string>> = {
  KEEP: "Preserved this section.",
  KEEP_FOR_CLARITY: "Kept this section for technical clarity.",
  BROLL_COVER_CANDIDATE: "Found a section that would benefit from visual coverage.",
  REMOVE_FILLER: "Removed a filler phrase.",
  REMOVE_FALSE_START: "Removed a false start.",
  REMOVE_REPETITION: "Removed a repeated point.",
  TRIM_PAUSE: "Tightened a pause.",
  TIGHTEN_EXPLANATION: "Tightened this explanation.",
  SHORT_CANDIDATE: "Selected a strong Short candidate.",
};

const mayaMessages = {
  APPROVE: "Approved Leo's edit.",
  REJECT: "Kept the original section.",
  MODIFY: "Adjusted Leo's proposed edit.",
} as const;

interface PresentedItem {
  activity: AgentActivity;
  isLeo: boolean;
  isSystem: boolean;
  agentName: string;
  message: string;
  decision?: EditorDecision;
  timecode?: string;
}

const presentActivity = (
  activity: AgentActivity,
  decisions: EditorDecision[],
  review: DirectorReview | null,
): PresentedItem => {
  const agentLower = activity.agent.toLowerCase();
  const isLeo = agentLower === "leo";
  const isSystem = agentLower === "system";
  const decision = activity.related_decision_id
    ? decisions.find((candidate) => candidate.decision_id === activity.related_decision_id)
    : undefined;

  let message = "";
  if (!isLeo && decision) {
    const verdict = review?.decisions?.find(
      (candidate) => candidate.editor_decision_id === decision.decision_id,
    )?.verdict;
    if (verdict) message = mayaMessages[verdict];
  }
  if (!message && decision) {
    message = leoMessages[decision.decision_type] || decision.concise_reason || "Reviewed this section.";
  }
  if (!message) {
    let raw = activity.message
      .replace(/^\[[A-Z_]+\]\s*/u, "")
      .replace(/^At \d{2}:\d{2}(?:\.\d+)?,?\s*/u, "")
      .trim();

    if (
      raw.includes("Proceed directly to EDL assembly") ||
      raw.includes("Approved for EDL: True") ||
      raw.includes("Approved for Edit Decision List") ||
      raw.toLowerCase().startsWith("feedback to leo: approved")
    ) {
      raw = "Edit plan approved.";
    } else if (raw.toLowerCase().startsWith("feedback to leo:")) {
      raw = raw.replace(/^feedback to leo:\s*/iu, "");
      if (raw.toLowerCase().includes("approved for edl")) {
        raw = "Edit plan approved.";
      }
    } else if (
      raw.includes("The dialogue flows naturally. Edit approved.") ||
      raw.includes("approved for Master render")
    ) {
      raw = "The dialogue flows naturally. Edit approved.";
    } else if (raw.includes("One cut feels too aggressive. Restoring context.")) {
      raw = "One cut feels too aggressive. Restoring context.";
    } else if (raw.includes("Adjusted the affected section.")) {
      raw = "Adjusted the affected section.";
    }

    message = raw || "Updated the production.";
  }
  const timecode = decision ? formatTimecode(decision.source_start_ms) : undefined;

  return {
    activity,
    isLeo,
    isSystem,
    agentName: isSystem ? "System" : isLeo ? "Leo" : "Maya",
    message,
    decision,
    timecode,
  };
};

const RowAvatar: React.FC<{ isLeo: boolean; isSystem?: boolean; name: string }> = ({
  isLeo,
  isSystem = false,
  name,
}) => {
  const [failed, setFailed] = useState(false);
  const src = isSystem ? undefined : avatarMap[isLeo ? "leo" : "maya"];

  return (
    <span
      className={`relative z-10 flex size-7 shrink-0 items-center justify-center overflow-hidden rounded-full border bg-surface-2 text-[10px] font-semibold ${
        isSystem
          ? "border-border-strong text-text-secondary bg-surface-3"
          : isLeo
            ? "border-primary/40 text-primary"
            : "border-info/40 text-info"
      }`}
      aria-hidden="true"
    >
      {src && !failed ? (
        <img src={src} alt="" className="size-full object-cover" onError={() => setFailed(true)} />
      ) : (
        <span>{isSystem ? "S" : isLeo ? "L" : "M"}</span>
      )}
    </span>
  );
};

export const AgentActivityFeed: React.FC<AgentActivityFeedProps> = ({
  activities = [],
  decisions = [],
  review = null,
  statusMessage = null,
  onSelectActivity,
  className = "",
}) => {
  const [showFullHistory, setShowFullHistory] = useState(false);

  // Process and dedupe activities
  const presentedItems = useMemo<PresentedItem[]>(() => {
    const items: PresentedItem[] = [];
    for (const act of activities) {
      const presented = presentActivity(act, decisions, review);
      // Dedupe identical consecutive messages for the same agent
      const last = items.at(-1);
      if (
        last &&
        last.agentName === presented.agentName &&
        last.message === presented.message &&
        last.timecode === presented.timecode
      ) {
        continue;
      }
      items.push(presented);
    }
    return items;
  }, [activities, decisions, review]);

  // Display latest 4 items by default unless expanded
  const displayedItems = useMemo(() => {
    if (showFullHistory || presentedItems.length <= 4) {
      return presentedItems;
    }
    return presentedItems.slice(-4);
  }, [presentedItems, showFullHistory]);

  return (
    <div className={`overflow-x-hidden w-full ${className}`} data-testid="agent-activity-feed">
      {statusMessage && (
        <div
          className="mb-2 flex items-center gap-2 rounded-md bg-surface-2/80 px-2.5 py-1.5 text-[11px] text-text-secondary border border-border-subtle"
          role="status"
        >
          <Loader2 className="size-3.5 shrink-0 animate-spin text-primary motion-reduce:animate-none" />
          <span>{statusMessage}</span>
        </div>
      )}

      {presentedItems.length === 0 && !statusMessage ? (
        <p className="py-2 text-[11px] text-text-muted">Activity will appear as work completes.</p>
      ) : (
        <div className="flex flex-col">
          <ol className="relative flex flex-col gap-2">
            {displayedItems.map((item) => {
              const clickable = Boolean(item.decision && onSelectActivity);
              const content = (
                <>
                  <RowAvatar isLeo={item.isLeo} isSystem={item.isSystem} name={item.agentName} />
                  <span className="min-w-0 flex-1 overflow-hidden">
                    <span className="flex items-baseline justify-between gap-1.5 min-w-0">
                      <span className="text-[11px] font-semibold text-text-primary">
                        {item.agentName}
                      </span>
                      {item.timecode && (
                        <span className="font-mono text-[9px] tabular-nums text-text-muted">
                          {item.timecode}
                        </span>
                      )}
                    </span>
                    <span className="mt-0.5 block text-[11px] leading-4 text-text-secondary break-words whitespace-normal">
                      {item.message}
                    </span>
                  </span>
                </>
              );

              return (
                <li key={item.activity.activity_id} className="relative flex gap-2">
                  {clickable ? (
                    <button
                      type="button"
                      className="-mx-1 -my-0.5 flex w-full min-w-0 gap-2 rounded-md p-1 text-left transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary overflow-hidden"
                      onClick={() => onSelectActivity?.(item.activity)}
                      aria-label={`${item.message}${
                        item.timecode ? ` Seek to ${item.timecode}` : ""
                      }`}
                    >
                      {content}
                    </button>
                  ) : (
                    <div className="flex w-full min-w-0 gap-2 p-0.5 overflow-hidden">{content}</div>
                  )}
                </li>
              );
            })}
          </ol>

          {presentedItems.length > 4 && (
            <button
              type="button"
              onClick={() => setShowFullHistory((h) => !h)}
              className="mt-2 self-start text-[10px] font-medium text-text-muted hover:text-text-primary transition-colors flex items-center gap-1 py-0.5"
            >
              {showFullHistory ? (
                <>
                  <ChevronUp className="size-3" />
                  <span>Show recent only</span>
                </>
              ) : (
                <>
                  <ChevronDown className="size-3" />
                  <span>View run history ({presentedItems.length})</span>
                </>
              )}
            </button>
          )}
        </div>
      )}
    </div>
  );
};
