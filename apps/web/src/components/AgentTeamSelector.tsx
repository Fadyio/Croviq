import { ChevronDown, MessageSquare, Settings } from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import alexAvatar from "../assets/agents/alex.webp";
import irisAvatar from "../assets/agents/Iris.png";
import leoAvatar from "../assets/agents/leo.webp";

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
  onSelect?: (agent: AgentId) => void;
  onChat?: (agent: AgentId) => void;
  onSettings?: (agent: AgentId) => void;
}

export const AgentTeamSelector: React.FC<AgentTeamSelectorProps> = ({
  activeAgent,
  onSelect,
  onChat,
  onSettings,
}) => {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const handleAgentAction = (agentId: AgentId, action: "chat" | "settings") => {
    setOpen(false);
    if (action === "chat") {
      if (onSelect) onSelect(agentId);
      else if (onChat) onChat(agentId);
    } else if (action === "settings") {
      if (onSettings) onSettings(agentId);
      else if (onSelect) onSelect(agentId);
    }
  };
  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex items-center gap-2 rounded-lg border border-border-subtle bg-surface-2/60 px-2.5 py-1 text-left transition-colors hover:border-border-strong hover:bg-surface-2 cursor-pointer"
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
        <div
          className="absolute right-0 top-full z-50 mt-1.5 w-72 rounded-xl border border-border-strong bg-surface-2 p-2 shadow-2xl space-y-1 animate-in fade-in zoom-in-95 duration-100"
          role="menu"
          data-testid="menu-team-selector"
        >
          <p className="px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
            Autonomous Production Team
          </p>
          {(Object.keys(AGENT_IDENTITIES) as AgentId[]).map((agentId) => {
            const agent = AGENT_IDENTITIES[agentId];
            const isActive = agentId === activeAgent;
            return (
              <div
                key={agentId}
                className={`rounded-lg p-2 transition-colors ${
                  isActive ? "bg-surface-3/90 ring-1 ring-primary/30" : "hover:bg-surface-3/50"
                }`}
              >
                <button
                  type="button"
                  onClick={() => handleAgentAction(agentId, "chat")}
                  className="flex w-full items-center gap-2.5 text-left cursor-pointer rounded p-1 hover:bg-surface-2/60 transition-colors"
                >
                  <img
                    src={agent.avatar}
                    alt=""
                    className="h-8 w-8 rounded-full object-cover ring-1 ring-border-subtle shrink-0"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="font-semibold text-xs text-text-primary">{agent.name} </span>
                      {isActive && (
                        <span className="text-[10px] font-semibold text-primary">Active</span>
                      )}
                    </div>
                    <span className="block truncate text-[11px] text-text-muted">
                      {agent.role} · {agent.focus}
                    </span>
                  </div>
                </button>

                <div className="mt-2 flex items-center gap-2 pt-1 border-t border-border-subtle/40">
                  <button
                    type="button"
                    onClick={() => handleAgentAction(agentId, "chat")}
                    className="flex flex-1 items-center justify-center gap-1.5 rounded-md bg-surface-1 py-1 text-[11px] font-medium text-text-primary hover:bg-primary/20 hover:text-primary transition-colors cursor-pointer"
                    data-testid={`btn-team-chat-${agentId}`}
                  >
                    <MessageSquare className="h-3 w-3 text-primary" />
                    <span>Chat with {agent.name}</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleAgentAction(agentId, "settings")}
                    className="flex items-center justify-center gap-1 rounded-md bg-surface-1 px-2.5 py-1 text-[11px] font-medium text-text-secondary hover:bg-surface-4 hover:text-text-primary transition-colors cursor-pointer"
                    title={`${agent.name} Settings`}
                    data-testid={`btn-team-settings-${agentId}`}
                  >
                    <Settings className="h-3 w-3" />
                    <span>Settings</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
