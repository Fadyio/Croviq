import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  LineChart,
  Loader2,
  MessageSquare,
  Send,
  Settings,
  Sparkles,
  User,
  Wrench,
} from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { AgentSettingsDrawer } from "../components/editor/AgentSettingsDrawer";
import { AGENT_IDENTITIES, AgentTeamSelector, type AgentId } from "../components/AgentTeamSelector";
import { CroviqLogo } from "../components/CroviqLogo";

interface AgentWorkspacePageProps {
  agentId: AgentId;
  onNavigate: (route: string) => void;
}

interface ToolExecution {
  tool_name: string;
  goal?: string;
  [key: string]: unknown;
}

interface ChatMessage {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  tool_executions?: ToolExecution[];
  structured_artifact?: Record<string, unknown> | null;
  created_at: string;
}

const STARTER_PROMPTS: Record<AgentId, string[]> = {
  alex: [
    "How did my last video perform?",
    "Calculate the correlation between demo timing and retention.",
    "What if I upload every week for the next 90 days?",
    "What should my next video be about and why?",
  ],
  leo: [
    "Where is the strongest hook in this footage?",
    "Can you make this dialogue tighter?",
    "Why did you flag the cut at 00:42?",
  ],
  iris: [
    "Is this video ready for release?",
    "Check audio loudness and continuity again.",
    "Why did you flag the captions in chapter 2?",
    "Audit technical accuracy against the transcript.",
  ],
};

export const AgentWorkspacePage: React.FC<AgentWorkspacePageProps> = ({ agentId, onNavigate }) => {
  const { firebaseUser } = useAuth();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const agent = AGENT_IDENTITIES[agentId];

  const getAuthHeaders = useCallback(async () => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (firebaseUser) {
      const token = await firebaseUser.getIdToken();
      headers.Authorization = `Bearer ${token}`;
    }
    return headers;
  }, [firebaseUser]);

  const loadHistory = useCallback(async () => {
    if (!firebaseUser) return;
    setIsLoadingHistory(true);
    setError(null);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/workspace/agents/${agentId}/chat`, { headers });
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
      }
    } catch {
      // Non-blocking history load
    } finally {
      setIsLoadingHistory(false);
    }
  }, [agentId, firebaseUser, getAuthHeaders]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  const sendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputMessage).trim();
    if (!text || isSending || !firebaseUser) return;

    setInputMessage("");
    setIsSending(true);
    setError(null);

    const tempUserMsg: ChatMessage = {
      message_id: `temp_${Date.now()}`,
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/workspace/agents/${agentId}/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify({ message: text }),
      });
      if (!res.ok) {
        throw new Error("Agent message failed to send");
      }
      const assistantMsg: ChatMessage = await res.json();
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to communicate with agent");
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendMessage();
    }
  };

  return (
    <div className="min-h-screen bg-background text-text-primary flex flex-col">
      {/* Top Bar */}
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-border-subtle bg-surface-1 px-4 sm:px-6 shrink-0">
        <button
          type="button"
          onClick={() => onNavigate("/app")}
          className="transition-opacity hover:opacity-80 cursor-pointer"
          aria-label="Croviq Home"
        >
          <CroviqLogo height={24} className="h-6 w-auto" />
        </button>
        <AgentTeamSelector
          activeAgent={agentId}
          onSelect={(selectedAgent) => onNavigate(`/app/agents/${selectedAgent}`)}
        />
      </header>

      {/* Main Content Area */}
      <main className="mx-auto w-full max-w-4xl px-4 py-4 sm:px-6 flex-1 flex flex-col min-h-0">
        <button
          type="button"
          onClick={() => onNavigate("/app")}
          className="mb-3 inline-flex items-center gap-1.5 text-xs font-medium text-text-muted transition-colors hover:text-text-primary self-start cursor-pointer"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          Channel Intelligence
        </button>

        {/* Workspace Card */}
        <section className="flex-1 flex flex-col overflow-hidden rounded-xl border border-border-subtle bg-surface-1 shadow-sm">
          {/* Header */}
          <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border-subtle px-5 py-3.5 shrink-0">
            <div className="flex items-center gap-3">
              <img
                src={agent.avatar}
                alt=""
                className="h-10 w-10 rounded-full object-cover ring-2 ring-primary/20"
              />
              <div>
                <h1 className="text-lg font-bold tracking-tight text-text-primary">{agent.name}</h1>
                <p className="text-xs text-text-muted">
                  {agent.role} · Autonomous Production Partner
                </p>
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
                <MessageSquare className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
                Chat
              </button>
              <button
                type="button"
                role="tab"
                aria-selected="false"
                onClick={() => setSettingsOpen(true)}
                className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-text-muted transition-colors hover:bg-surface-2 hover:text-text-primary cursor-pointer"
              >
                <Settings className="h-3.5 w-3.5" aria-hidden="true" />
                Settings & Memory
              </button>
            </div>
          </header>

          {/* Messages Feed */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5">
            {isLoadingHistory ? (
              <div className="flex h-64 items-center justify-center text-xs text-text-muted">
                <Loader2 className="h-5 w-5 animate-spin mr-2 text-primary" />
                Loading conversation history...
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <img
                  src={agent.avatar}
                  alt=""
                  className="h-16 w-16 rounded-full object-cover ring-2 ring-primary/30 mb-4"
                />
                <h2 className="text-base font-semibold text-text-primary">
                  Chat with {agent.name}
                </h2>
                <p className="mt-1 text-xs text-text-secondary max-w-md">
                  {agentId === "alex"
                    ? "Alex analyzes your channel dataset, runs statistical Python calculations, and evaluates scenario projections."
                    : agentId === "leo"
                      ? "Leo inspects your footage timeline, identifies filler words, and builds a precise edit proposal."
                      : "Iris audits caption alignment, audio loudness standards, and release gatekeeper verification."}
                </p>

                {/* Starter Prompt Chips */}
                <div className="mt-6 flex flex-wrap justify-center gap-2 max-w-lg">
                  {STARTER_PROMPTS[agentId].map((promptText) => (
                    <button
                      key={promptText}
                      type="button"
                      onClick={() => void sendMessage(promptText)}
                      className="rounded-lg border border-border-subtle bg-surface-2/60 px-3 py-2 text-left text-xs text-text-secondary hover:border-primary/50 hover:bg-surface-2 hover:text-text-primary transition-all cursor-pointer shadow-sm"
                    >
                      <span className="flex items-center gap-1.5">
                        <Sparkles className="h-3 w-3 text-primary shrink-0" />
                        {promptText}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.message_id}
                  className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  {msg.role === "assistant" && (
                    <img
                      src={agent.avatar}
                      alt=""
                      className="h-8 w-8 rounded-full object-cover ring-1 ring-border-subtle shrink-0 mt-0.5"
                    />
                  )}

                  <div className={`space-y-2.5 max-w-[85%] sm:max-w-[75%]`}>
                    <div
                      className={`rounded-xl p-4 text-xs leading-relaxed ${
                        msg.role === "user"
                          ? "bg-primary text-white font-medium ml-auto shadow-sm"
                          : "bg-surface-2 text-text-primary border border-border-subtle shadow-sm"
                      }`}
                    >
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>

                    {/* Internal Tool Telemetry Badge */}
                    {msg.tool_executions && msg.tool_executions.length > 0 && (
                      <div className="space-y-1.5 pl-1">
                        {msg.tool_executions.map((tool, idx) => (
                          <div
                            key={idx}
                            className="flex items-center gap-2 rounded-md bg-surface-3/60 px-2.5 py-1 text-[10px] font-mono text-text-muted border border-border-subtle/50"
                          >
                            <Wrench className="h-3 w-3 text-primary shrink-0" />
                            <span className="font-semibold text-text-secondary">
                              {tool.tool_name}
                            </span>
                            {tool.goal && <span className="truncate">· {tool.goal}</span>}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Structured Analytical Artifact (if present) */}
                    {msg.structured_artifact && (
                      <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 text-xs space-y-1.5 pl-3">
                        <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
                          <LineChart className="h-3 w-3" />
                          <span>
                            Analytical Artifact:{" "}
                            {String(msg.structured_artifact.type || "Analysis")}
                          </span>
                        </div>
                        {msg.structured_artifact.metrics &&
                        typeof msg.structured_artifact.metrics === "object" &&
                        !Array.isArray(msg.structured_artifact.metrics) ? (
                          <div className="grid grid-cols-2 gap-2 pt-1">
                            {Object.entries(
                              msg.structured_artifact.metrics as Record<string, unknown>,
                            ).map(([key, val]) => (
                              <div
                                key={key}
                                className="rounded bg-surface-1 p-1.5 border border-border-subtle"
                              >
                                <span className="block text-[9px] text-text-muted uppercase tracking-wider">
                                  {key.replace(/_/g, " ")}
                                </span>
                                <span className="block font-mono font-bold text-xs text-text-primary">
                                  {String(val)}
                                </span>
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    )}
                  </div>

                  {msg.role === "user" && (
                    <div className="h-8 w-8 rounded-full bg-primary/20 border border-primary/30 flex items-center justify-center text-primary text-xs shrink-0 mt-0.5">
                      <User className="h-4 w-4" />
                    </div>
                  )}
                </div>
              ))
            )}

            {isSending && (
              <div className="flex gap-3 justify-start">
                <img
                  src={agent.avatar}
                  alt=""
                  className="h-8 w-8 rounded-full object-cover ring-1 ring-border-subtle shrink-0 mt-0.5 animate-pulse"
                />
                <div className="rounded-xl p-3.5 bg-surface-2 text-xs text-text-muted border border-border-subtle flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  <span>{agent.name} is inspecting data and reasoning...</span>
                </div>
              </div>
            )}

            {error && (
              <div className="rounded-lg bg-danger/10 border border-danger/30 p-3 text-xs text-danger">
                {error}
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Chat Composer */}
          <footer className="border-t border-border-subtle p-3 sm:p-4 bg-surface-1/90 backdrop-blur-sm shrink-0">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void sendMessage();
              }}
              className="flex items-end gap-2"
            >
              <textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={`Ask ${agent.name} a question... (Enter to send)`}
                rows={1}
                className="flex-1 max-h-32 min-h-[42px] rounded-xl border border-border-subtle bg-surface-2 px-3.5 py-2.5 text-xs text-text-primary placeholder:text-text-muted outline-none focus:border-primary transition-colors resize-none"
              />
              <button
                type="submit"
                disabled={!inputMessage.trim() || isSending}
                className="h-[42px] px-4 rounded-xl bg-primary text-white text-xs font-semibold flex items-center gap-1.5 hover:bg-primary-hover disabled:opacity-50 transition-all cursor-pointer active:scale-95 shrink-0"
                aria-label="Send message"
              >
                <span>Send</span>
                <Send className="h-3.5 w-3.5" />
              </button>
            </form>
          </footer>
        </section>
      </main>

      {/* Settings Drawer */}
      <AgentSettingsDrawer
        isOpen={settingsOpen}
        agentId={agentId}
        onClose={() => setSettingsOpen(false)}
      />
    </div>
  );
};
