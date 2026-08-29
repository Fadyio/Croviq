import React, { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import alexAvatar from "../assets/agents/alex.webp";
import leoAvatar from "../assets/agents/leo.webp";
import irisAvatar from "../assets/agents/Iris.png";

export type AgentId = "alex" | "leo" | "iris";

export const AGENT_IDENTITIES = {
  alex: {
    name: "Alex",
    role: "Data Scientist",
    focus: "Channel intelligence",
    avatar: alexAvatar,
  },
  leo: {
    name: "Leo",
    role: "Video Editor",
    focus: "Timeline editing",
    avatar: leoAvatar,
  },
  iris: {
    name: "Iris",
    role: "Quality Control",
    focus: "Release readiness",
    avatar: irisAvatar,
  },
} as const satisfies Record<AgentId, { name: string; role: string; focus: string; avatar: string }>;

interface AgentTeamSelectorProps {
  activeAgent?: AgentId;
  onSelect: (agent: AgentId) => void;
}

export const AgentTeamSelector: React.FC<AgentTeamSelectorProps> = ({ activeAgent, onSelect }) => {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, []);

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex items-center gap-2 rounded-lg border border-border-subtle bg-surface-2/60 px-2.5 py-1 text-left transition-colors hover:border-border-strong hover:bg-surface-2"
        aria-label="Select production agent"
        aria-expanded={open}
        title="Production Team: Alex, Leo, Iris"
        data-testid="btn-team-selector"
      >
        <div className="flex -space-x-1.5 overflow-hidden" aria-hidden="true">
          {(Object.keys(AGENT_IDENTITIES) as AgentId[]).map((agentId) => (
            <img
              key={agentId}
              src={AGENT_IDENTITIES[agentId].avatar}
              alt=""
              className="inline-block h-5 w-5 rounded-full object-cover ring-1 ring-surface-1"
            />
          ))}
        </div>
        <span className="hidden text-xs font-semibold leading-tight text-text-primary sm:block">
          Team
        </span>
        <ChevronDown className="h-3 w-3 text-text-muted" aria-hidden="true" />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1.5 w-64 rounded-xl border border-border-strong bg-surface-2 p-1.5 shadow-2xl">
          <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
            Autonomous Production Team
          </p>
          {(Object.keys(AGENT_IDENTITIES) as AgentId[]).map((agentId) => {
            const agent = AGENT_IDENTITIES[agentId];
            const isActive = agentId === activeAgent;
            return (
              <button
                key={agentId}
                type="button"
                onClick={() => {
                  setOpen(false);
                  onSelect(agentId);
                }}
                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs text-text-secondary transition-colors hover:bg-surface-3 hover:text-text-primary"
                aria-current={isActive ? "page" : undefined}
              >
                <img
                  src={agent.avatar}
                  alt=""
                  className="h-6 w-6 rounded-full object-cover ring-1 ring-border-subtle"
                />
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold text-text-primary">{agent.name}</span>
                  <span className="block truncate text-[10px] text-text-muted">
                    {agent.role} · {agent.focus}
                  </span>
                </span>
                {isActive && <span className="text-[10px] font-semibold text-primary">Active</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
