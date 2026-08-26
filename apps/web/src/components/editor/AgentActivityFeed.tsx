import React from "react";
import { Activity, MessageSquare } from "lucide-react";
import type { AgentActivity } from "../../lib/edl-adapter";

interface AgentActivityFeedProps {
  activities?: AgentActivity[];
  onSelectActivity?: (activity: AgentActivity) => void;
  className?: string;
}

export const AgentActivityFeed: React.FC<AgentActivityFeedProps> = ({
  activities = [],
  onSelectActivity,
  className = "",
}) => {
  return (
    <div
      className={`p-3 bg-surface-1 rounded-xl border border-border-subtle flex flex-col gap-2.5 shadow-sm ${className}`}
      data-testid="agent-activity-feed"
    >
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold text-text-primary flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5 text-primary" />
          <span>Agent Activity</span>
        </span>
        <span className="text-[10px] font-mono text-text-muted">{activities.length} events</span>
      </div>

      <div className="flex flex-col gap-2 max-h-[220px] overflow-y-auto pr-1">
        {activities.length === 0 ? (
          <div className="py-4 text-center text-xs text-text-muted italic">
            No agent activities recorded for this run.
          </div>
        ) : (
          activities.map((act) => {
            const isLeo = act.agent.toLowerCase() === "leo";
            const role = isLeo ? "Dialogue Editor" : "Director";

            return (
              <div
                key={act.activity_id}
                onClick={() => onSelectActivity && onSelectActivity(act)}
                className="p-2 rounded-lg bg-surface-2/60 hover:bg-surface-2 border border-border-subtle transition-colors flex items-start gap-2.5 text-xs"
              >
                {/* Agent Avatar Badge */}
                <div
                  className={`w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold shrink-0 mt-0.5 border ${
                    isLeo
                      ? "bg-primary/20 text-primary border-primary/30"
                      : "bg-info/20 text-info border-info/30"
                  }`}
                >
                  {isLeo ? "L" : "M"}
                </div>

                <div className="min-w-0 flex-1 flex flex-col gap-0.5">
                  <div className="flex items-center justify-between gap-1">
                    <span className="font-semibold text-text-primary text-[11px]">
                      {isLeo ? "Leo" : "Maya"}{" "}
                      <span className="font-normal text-text-muted text-[10px]">
                        &middot; {role}
                      </span>
                    </span>
                    <span className="text-[9px] font-mono text-text-muted">
                      {act.created_at
                        ? new Date(act.created_at).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                            second: "2-digit",
                          })
                        : ""}
                    </span>
                  </div>
                  <p className="text-[11px] text-text-secondary leading-snug">{act.message}</p>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
