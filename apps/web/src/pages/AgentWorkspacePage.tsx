import React, { useState } from "react";
import { ArrowLeft, MessageSquare, Settings } from "lucide-react";
import { AgentSettingsDrawer } from "../components/editor/AgentSettingsDrawer";
import { AGENT_IDENTITIES, AgentTeamSelector, type AgentId } from "../components/AgentTeamSelector";
import { CroviqLogo } from "../components/CroviqLogo";

interface AgentWorkspacePageProps {
  agentId: AgentId;
  onNavigate: (route: string) => void;
}

const AGENT_CHAT_GUIDANCE: Record<AgentId, string> = {
  alex: "Ask about channel performance, evidence, forecasts, and what to test next.",
  leo: "Ask about the current edit, transcript, strongest hook, or a potential Short.",
  iris: "Ask about release readiness, captions, audio, and quality findings.",
};

export const AgentWorkspacePage: React.FC<AgentWorkspacePageProps> = ({ agentId, onNavigate }) => {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const agent = AGENT_IDENTITIES[agentId];

  return (
    <div className="min-h-screen bg-background text-text-primary">
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-border-subtle bg-surface-1 px-4 sm:px-6">
        <button
          type="button"
          onClick={() => onNavigate("/app")}
          className="transition-opacity hover:opacity-80"
          aria-label="Croviq Home"
        >
          <CroviqLogo height={24} className="h-6 w-auto" />
        </button>
        <AgentTeamSelector
          activeAgent={agentId}
          onSelect={(selectedAgent) => onNavigate(`/app/agents/${selectedAgent}`)}
        />
      </header>

      <main className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
        <button
          type="button"
          onClick={() => onNavigate("/app")}
          className="mb-5 flex items-center gap-1.5 text-xs font-medium text-text-muted transition-colors hover:text-text-primary"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          Channel Intelligence
        </button>

        <section className="overflow-hidden rounded-xl border border-border-subtle bg-surface-1">
          <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border-subtle px-5 py-4">
            <div className="flex items-center gap-3">
              <img
                src={agent.avatar}
                alt=""
                className="h-11 w-11 rounded-full object-cover ring-1 ring-border-strong"
              />
              <div>
                <h1 className="text-xl font-bold tracking-tight">{agent.name}</h1>
                <p className="text-sm text-text-secondary">{agent.role}</p>
              </div>
            </div>
            <div
              className="flex items-center gap-1"
              role="tablist"
              aria-label={`${agent.name} workspace`}
            >
              <button
                type="button"
                role="tab"
                aria-selected="true"
                className="flex items-center gap-1.5 rounded-lg bg-surface-3 px-3 py-1.5 text-xs font-semibold text-text-primary"
              >
                <MessageSquare className="h-3.5 w-3.5" aria-hidden="true" />
                Chat
              </button>
              <button
                type="button"
                role="tab"
                aria-selected="false"
                onClick={() => setSettingsOpen(true)}
                className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-text-muted transition-colors hover:bg-surface-2 hover:text-text-primary"
              >
                <Settings className="h-3.5 w-3.5" aria-hidden="true" />
                Settings
              </button>
            </div>
          </header>

          <div className="flex min-h-[520px] items-center justify-center px-6 py-12 text-center">
            <div className="max-w-md">
              <img
                src={agent.avatar}
                alt=""
                className="mx-auto h-14 w-14 rounded-full object-cover ring-1 ring-border-strong"
              />
              <h2 className="mt-4 text-lg font-semibold">Start with {agent.name}</h2>
              <p className="mt-2 text-sm leading-6 text-text-secondary">
                {AGENT_CHAT_GUIDANCE[agentId]}
              </p>
            </div>
          </div>
        </section>
      </main>

      <AgentSettingsDrawer
        isOpen={settingsOpen}
        agentId={agentId}
        onClose={() => setSettingsOpen(false)}
      />
    </div>
  );
};
