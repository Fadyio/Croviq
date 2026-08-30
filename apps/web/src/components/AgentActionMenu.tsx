import { MessageSquare, Settings } from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import { AGENT_IDENTITIES, type AgentId } from "./AgentTeamSelector";

interface AgentActionMenuProps {
  agentId: AgentId;
  onChat: () => void;
  onSettings: () => void;
  className?: string;
  align?: "left" | "right";
  children?: React.ReactNode;
}

export const AgentActionMenu: React.FC<AgentActionMenuProps> = ({
  agentId,
  onChat,
  onSettings,
  className = "",
  align = "right",
  children,
}) => {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const agent = AGENT_IDENTITIES[agentId];

  useEffect(() => {
    if (!open) return;
    const handleOutsideClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handleOutsideClick);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  return (
    <div className={`relative inline-block ${className}`} ref={menuRef}>
      {children ? (
        <div onClick={() => setOpen((prev) => !prev)} role="button" tabIndex={0}>
          {children}
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          className="flex items-center gap-3 text-left transition-opacity hover:opacity-85 cursor-pointer rounded-lg p-1 hover:bg-surface-2/60"
          aria-expanded={open}
          aria-label={`Open ${agent.name} menu`}
          data-testid={`btn-agent-menu-${agentId}`}
        >
          <img
            src={agent.avatar}
            alt={agent.name}
            className="h-10 w-10 rounded-full object-cover ring-2 ring-primary/20"
          />
          <div>
            <h2 className="text-sm font-semibold text-text-primary hover:text-primary transition-colors">
              {agent.name}
            </h2>
            <p className="text-xs text-text-muted">{agent.role}</p>
          </div>
        </button>
      )}

      {open && (
        <div
          className={`absolute ${
            align === "right" ? "right-0" : "left-0"
          } top-full z-50 mt-1.5 w-60 rounded-xl border border-border-strong bg-surface-2 p-2 shadow-2xl space-y-1.5 animate-in fade-in zoom-in-95 duration-100`}
          role="menu"
          data-testid={`menu-agent-actions-${agentId}`}
        >
          {/* Agent Header */}
          <div className="flex items-center gap-2.5 px-2 py-1.5 border-b border-border-subtle/80 pb-2">
            <img
              src={agent.avatar}
              alt={agent.name}
              className="h-7 w-7 rounded-full object-cover ring-1 ring-border-subtle"
            />
            <div className="min-w-0 flex-1">
              <span className="block text-xs font-semibold text-text-primary leading-tight">
                {agent.name}
              </span>
              <span className="block text-[11px] text-text-muted truncate">{agent.role}</span>
            </div>
          </div>

          {/* Actions */}
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              onChat();
            }}
            className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-text-primary transition-colors hover:bg-primary/15 hover:text-primary cursor-pointer"
            role="menuitem"
            data-testid={`action-chat-${agentId}`}
          >
            <MessageSquare className="h-4 w-4 text-primary" />
            <span>Chat with {agent.name}</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setOpen(false);
              onSettings();
            }}
            className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-text-secondary transition-colors hover:bg-surface-3 hover:text-text-primary cursor-pointer"
            role="menuitem"
            data-testid={`action-settings-${agentId}`}
          >
            <Settings className="h-4 w-4 text-text-muted" />
            <span>Settings</span>
          </button>
        </div>
      )}
    </div>
  );
};
