import React, { useMemo } from "react";
import { Clock, Loader2, Sparkles } from "lucide-react";
import { formatTimecode } from "../../lib/edl-adapter";
import type { AgentActivity, EditorDecision } from "../../lib/edl-adapter";
import leoAvatar from "../../assets/agents/leo.webp";

interface AgentActivityFeedProps {
  activities?: AgentActivity[];
  decisions?: EditorDecision[];
  statusMessage?: string | null;
  onSeek?: (timeMs: number) => void;
  onSelectActivity?: (activity: AgentActivity) => void;
  className?: string;
}

interface ChatBubbleItem {
  id: string;
  sender: "leo" | "system";
  name: string;
  role: string;
  avatar?: string;
  text: string;
  timestampMs?: number;
  timeRangeText?: string;
  activityType: string;
  rawActivity: AgentActivity;
  isCorrection?: boolean;
}

export const AgentActivityFeed: React.FC<AgentActivityFeedProps> = ({
  activities = [],
  decisions = [],
  statusMessage = null,
  onSeek,
  onSelectActivity,
  className = "",
}) => {
  // Convert activities and decisions into a natural conversational flow
  const chatMessages = useMemo<ChatBubbleItem[]>(() => {
    const items: ChatBubbleItem[] = [];

    // Process raw activities
    for (const act of activities) {
      const agent = act.agent.toLowerCase();
      const isLeo = agent.includes("leo");
      const isSystem = agent.includes("system") || agent.includes("croviq");
      if (!isLeo && !isSystem) continue;
      const sender = isLeo ? "leo" : "system";
      const name = isLeo ? "Leo" : "Studio System";
      const role = isLeo ? "Video Editor" : "Automated Pipeline";

      // Extract timecodes if present in the message
      let timestampMs: number | undefined;
      let timeRangeText: string | undefined;

      if (act.related_decision_id) {
        const matchingDec = decisions.find((d) => d.decision_id === act.related_decision_id);
        if (matchingDec) {
          timestampMs = matchingDec.source_start_ms;
          timeRangeText = `${formatTimecode(matchingDec.source_start_ms)} – ${formatTimecode(matchingDec.source_end_ms)}`;
        }
      }

      // Clean up any internal raw enums, decision IDs, or timecode prefixes
      let cleanText = act.message;
      // Strip bracketed enums (e.g. "[REMOVE_FALSE_START]", "[APPROVE]")
      cleanText = cleanText.replace(/^\[[A-Z0-9_]+\]\s*/, "");
      // Strip decision ID prefixes (e.g. "Decision dec_001_false_start_edit: ")
      cleanText = cleanText.replace(/^Decision\s+dec_[a-zA-Z0-9_-]+:\s*/i, "");
      cleanText = cleanText.replace(/^dec_[a-zA-Z0-9_-]+:\s*/i, "");
      // Strip "At MM:SS: " prefix if present
      cleanText = cleanText.replace(/^At\s+\d{2}:\d{2}(?:\.\d+)?:\s*/i, "");
      cleanText = cleanText.trim();

      items.push({
        id: act.activity_id,
        sender,
        name,
        role,
        avatar: isLeo ? leoAvatar : undefined,
        text: cleanText,
        timestampMs,
        timeRangeText,
        activityType: act.activity_type,
        rawActivity: act,
        isCorrection:
          act.message.toLowerCase().includes("revised") ||
          act.message.toLowerCase().includes("restored"),
      });
    }

    return items;
  }, [activities, decisions]);

  return (
    <div
      className={`flex flex-col h-full bg-surface-1 select-none overflow-hidden ${className}`}
      data-testid="agent-activity-feed"
    >
      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {chatMessages.length === 0 && !statusMessage && (
          <div className="flex flex-col items-center justify-center h-48 text-center p-4">
            <span className="text-xs text-text-muted">
              Leo&apos;s editorial choices and production notices will appear here.
            </span>
          </div>
        )}

        {chatMessages.map((item) => (
          <div
            key={item.id}
            className="flex flex-col items-start gap-1 transition-all duration-200 ease-out animate-in fade-in slide-in-from-bottom-2"
            data-testid={`activity-message-${item.sender}`}
          >
            <div className="flex items-center gap-2 px-1">
              {item.avatar ? (
                <img
                  src={item.avatar}
                  alt={item.name}
                  className="size-5 rounded-full object-cover border border-border-subtle"
                />
              ) : (
                <span className="flex size-5 items-center justify-center rounded-full border border-border-subtle bg-surface-3 text-primary">
                  <Sparkles className="size-3" aria-hidden="true" />
                </span>
              )}
              <span className="text-[11px] font-semibold text-text-primary">{item.name}</span>
              <span className="text-[10px] text-text-muted">· {item.role}</span>
            </div>

            <div
              className="max-w-[85%] rounded-2xl rounded-tl-xs bg-surface-2 border border-border-subtle px-3.5 py-2.5 text-xs leading-relaxed text-text-primary shadow-xs cursor-pointer transition-all hover:ring-1 hover:ring-primary/40"
              onClick={() => {
                if (item.timestampMs !== undefined) onSeek?.(item.timestampMs);
                onSelectActivity?.(item.rawActivity);
              }}
            >
              <p className="whitespace-pre-wrap">{item.text}</p>

              {item.timestampMs !== undefined && (
                <div className="mt-2 flex justify-start">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSeek?.(item.timestampMs!);
                      onSelectActivity?.(item.rawActivity);
                    }}
                    className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-surface-3/80 hover:bg-primary/20 hover:text-primary border border-border-subtle text-[10px] font-mono text-text-secondary transition-colors cursor-pointer"
                    title="Seek to video timestamp and inspect decision"
                    data-testid="bubble-seek-btn"
                  >
                    <Clock className="size-2.5" />
                    <span>{item.timeRangeText || formatTimecode(item.timestampMs)}</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Live Working Indicator */}
        {statusMessage && (
          <div
            className="flex flex-col items-start gap-1 animate-in fade-in slide-in-from-bottom-2"
            data-testid="agent-live-working-indicator"
          >
            <div className="flex items-center gap-2 px-1">
              <img
                src={leoAvatar}
                alt="Leo working"
                className="size-5 rounded-full object-cover border border-border-subtle"
              />
              <span className="text-[11px] font-semibold text-text-primary">Leo</span>
              <span className="text-[10px] text-text-muted">· Video Editor</span>
            </div>

            <div className="flex items-center gap-2 px-3.5 py-2 rounded-2xl bg-surface-2/60 border border-primary/30 text-xs text-text-secondary">
              <Loader2 className="size-3.5 text-primary animate-spin" />
              <span className="truncate">{statusMessage}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
