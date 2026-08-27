import React, { useState } from "react";
import leoAvatar from "../../assets/agents/leo.webp";
import mayaAvatar from "../../assets/agents/maya.webp";

type AgentId = "leo" | "maya" | "system";

interface AgentPresenceProps {
  activeAgent?: AgentId | null;
  statusMessage?: string | null;
}

const avatarMap: Record<"leo" | "maya", string> = {
  leo: leoAvatar,
  maya: mayaAvatar,
};

const agents: Array<{ id: "leo" | "maya"; name: string; role: string; initials: string }> = [
  { id: "leo", name: "Leo", role: "Video Editor", initials: "L" },
  { id: "maya", name: "Maya", role: "Director", initials: "M" },
];

const AgentAvatar: React.FC<(typeof agents)[number]> = ({ id, name, initials }) => {
  const [imageFailed, setImageFailed] = useState(false);
  const src = avatarMap[id];

  return (
    <span
      className="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-full border border-border-strong bg-surface-3 text-xs font-semibold text-text-secondary shadow-sm"
      aria-hidden="true"
    >
      {src && !imageFailed ? (
        <img
          src={src}
          alt={name}
          className="size-full object-cover"
          onError={() => setImageFailed(true)}
        />
      ) : (
        <span aria-label={`${name} initials`}>{initials}</span>
      )}
    </span>
  );
};

export const AgentPresence: React.FC<AgentPresenceProps> = ({
  activeAgent = null,
  statusMessage = null,
}) => (
  <div className="flex flex-col gap-2" data-testid="agent-presence">
    <div className="grid grid-cols-2 gap-2">
      {agents.map((agent) => {
        const isActive = activeAgent === agent.id;
        return (
          <div
            key={agent.id}
            className={`flex min-w-0 items-center gap-2 rounded-lg p-1.5 transition-all ${
              isActive
                ? "bg-primary/10 ring-1 ring-primary/40 shadow-sm"
                : "bg-surface-2/40 border border-border-subtle/50"
            }`}
            data-active={isActive}
            data-testid={`agent-presence-${agent.id}`}
          >
            <span className="relative shrink-0">
              <AgentAvatar {...agent} />
              {isActive && (
                <span className="absolute -right-0.5 -bottom-0.5 size-2 rounded-full border-2 border-surface-1 bg-primary animate-pulse" />
              )}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs font-semibold text-text-primary">
                {agent.name}
              </span>
              <span className="block truncate text-[10px] text-text-muted font-medium">
                {agent.role}
              </span>
            </span>
          </div>
        );
      })}
    </div>

    {statusMessage && (
      <div
        className="flex items-center gap-2 rounded-md bg-surface-2/70 px-2.5 py-1.5 border border-border-subtle/40 text-[11px] text-text-secondary"
        data-testid="agent-active-status"
      >
        <span className="size-1.5 rounded-full bg-primary animate-pulse shrink-0" />
        <span className="truncate font-medium">{statusMessage}</span>
      </div>
    )}
  </div>
);
