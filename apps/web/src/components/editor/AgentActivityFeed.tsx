import React, { useMemo } from "react";
import { Clock, Loader2, Sparkles, AlertCircle } from "lucide-react";
import { formatTimecode } from "../../lib/edl-adapter";
import type { AgentActivity, DirectorReview, EditorDecision } from "../../lib/edl-adapter";
import leoAvatar from "../../assets/agents/leo.webp";
import mayaAvatar from "../../assets/agents/maya.webp";

interface AgentActivityFeedProps {
  activities?: AgentActivity[];
  decisions?: EditorDecision[];
  review?: DirectorReview | null;
  statusMessage?: string | null;
  activeAgent?: "leo" | "maya" | null;
  onSeek?: (timeMs: number) => void;
  onSelectActivity?: (activity: AgentActivity) => void;
  className?: string;
}

interface ChatBubbleItem {
  id: string;
  sender: "leo" | "maya" | "system";
  name: string;
  role: string;
  avatar: string;
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
  review = null,
  statusMessage = null,
  activeAgent = null,
  onSeek,
  onSelectActivity,
  className = "",
}) => {
  // Convert activities and decisions into a natural conversational flow
  const chatMessages = useMemo<ChatBubbleItem[]>(() => {
    const items: ChatBubbleItem[] = [];

    // Process raw activities
    for (const act of activities) {
      const isLeo = act.agent.toLowerCase().includes("leo");
      const isMaya = act.agent.toLowerCase().includes("maya");
      const sender = isLeo ? "leo" : isMaya ? "maya" : "system";
      const name = isLeo ? "Leo" : isMaya ? "Maya" : "Studio System";
      const role = isLeo ? "Video Editor" : isMaya ? "Director" : "Automated Pipeline";
      const avatar = isLeo ? leoAvatar : mayaAvatar;

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

      // Clean up bracketed enum prefixes from message text (e.g. "[TRIM_DEAD_AIR] At 00:15: ...")
      let cleanText = act.message;
      if (cleanText.startsWith("[") && cleanText.includes("]")) {
        const bracketEnd = cleanText.indexOf("]");
        cleanText = cleanText.substring(bracketEnd + 1).trim();
        if (cleanText.startsWith("At ") && cleanText.includes(":")) {
          const colonIdx = cleanText.indexOf(":");
          cleanText = cleanText.substring(colonIdx + 1).trim();
        }
      }

      items.push({
        id: act.activity_id,
        sender,
        name,
        role,
        avatar,
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
              Leo and Maya will discuss their editorial choices here during production.
            </span>
          </div>
        )}

        {chatMessages.map((item) => {
          const isMaya = item.sender === "maya";

          return (
            <div
              key={item.id}
              className={`flex flex-col gap-1 transition-all duration-200 ease-out animate-in fade-in slide-in-from-bottom-2 ${
                isMaya ? "items-end" : "items-start"
              }`}
              data-testid={`activity-message-${item.sender}`}
            >
              {/* Agent Header */}
              <div
                className={`flex items-center gap-2 px-1 ${
                  isMaya ? "flex-row-reverse" : "flex-row"
                }`}
              >
                <img
                  src={item.avatar}
                  alt={item.name}
                  className="size-5 rounded-full object-cover border border-border-subtle"
                />
                <span className="text-[11px] font-semibold text-text-primary">{item.name}</span>
                <span className="text-[10px] text-text-muted">· {item.role}</span>
              </div>

              {/* Speech Bubble */}
              <div
                className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed shadow-xs cursor-pointer transition-all hover:ring-1 hover:ring-primary/40 ${
                  isMaya
                    ? "bg-purple-950/40 border border-purple-800/40 text-purple-100 rounded-tr-xs"
                    : "bg-surface-2 border border-border-subtle text-text-primary rounded-tl-xs"
                }`}
                onClick={() => {
                  if (item.timestampMs !== undefined) onSeek?.(item.timestampMs);
                  onSelectActivity?.(item.rawActivity);
                }}
              >
                <p className="whitespace-pre-wrap">{item.text}</p>

                {/* Interactive Timecode Pill if available */}
                {item.timestampMs !== undefined && (
                  <div className={`mt-2 flex ${isMaya ? "justify-end" : "justify-start"}`}>
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
          );
        })}

        {/* Live Working Indicator */}
        {statusMessage && (
          <div
            className={`flex flex-col gap-1 animate-in fade-in slide-in-from-bottom-2 ${
              activeAgent === "maya" ? "items-end" : "items-start"
            }`}
            data-testid="agent-live-working-indicator"
          >
            <div
              className={`flex items-center gap-2 px-1 ${
                activeAgent === "maya" ? "flex-row-reverse" : "flex-row"
              }`}
            >
              <img
                src={activeAgent === "maya" ? mayaAvatar : leoAvatar}
                alt="Working"
                className="size-5 rounded-full object-cover border border-border-subtle"
              />
              <span className="text-[11px] font-semibold text-text-primary">
                {activeAgent === "maya" ? "Maya" : "Leo"}
              </span>
              <span className="text-[10px] text-text-muted">
                · {activeAgent === "maya" ? "Director" : "Video Editor"}
              </span>
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
