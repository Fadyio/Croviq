import React, { useState } from "react";

type AgentId = "leo" | "maya";

interface AgentPresenceProps {
  activeAgent?: AgentId | null;
}

const avatarModules = import.meta.glob("../../assets/agents/{leo,maya}.webp", {
  eager: true,
  query: "?url",
  import: "default",
}) as Record<string, string>;

const agents: Array<{ id: AgentId; name: string; role: string; initials: string }> = [
  { id: "leo", name: "Leo", role: "Dialogue Editor", initials: "L" },
  { id: "maya", name: "Maya", role: "Director", initials: "M" },
];

const AgentAvatar: React.FC<(typeof agents)[number]> = ({ id, name, initials }) => {
  const [imageFailed, setImageFailed] = useState(false);
  const src = avatarModules[`../../assets/agents/${id}.webp`];

  return (
    <span
      className="flex size-8 shrink-0 items-center justify-center overflow-hidden rounded-full border border-border-strong bg-surface-3 text-[10px] font-semibold text-text-secondary"
      aria-hidden="true"
    >
      {src && !imageFailed ? (
        <img
          src={src}
          alt=""
          className="size-full object-cover"
          onError={() => setImageFailed(true)}
        />
      ) : (
        <span aria-label={`${name} initials`}>{initials}</span>
      )}
    </span>
  );
};

export const AgentPresence: React.FC<AgentPresenceProps> = ({ activeAgent = null }) => (
  <div className="grid grid-cols-2 gap-x-3" data-testid="agent-presence">
    {agents.map((agent) => {
      const isActive = activeAgent === agent.id;
      return (
        <div
          key={agent.id}
          className={`flex min-w-0 items-center gap-2 rounded-lg px-2 py-1.5 transition-colors ${
            isActive ? "bg-primary/10" : "bg-transparent"
          }`}
          data-active={isActive}
          data-testid={`agent-presence-${agent.id}`}
        >
          <span className="relative">
            <AgentAvatar {...agent} />
            {isActive && (
              <span className="absolute -right-0.5 -bottom-0.5 size-2.5 rounded-full border-2 border-surface-1 bg-primary" />
            )}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-[11px] font-semibold text-text-primary">
              {agent.name}
            </span>
            <span className="block truncate text-[10px] text-text-muted">{agent.role}</span>
          </span>
        </div>
      );
    })}
  </div>
);
