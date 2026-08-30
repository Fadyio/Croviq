import {
  AlertCircle,
  LineChart,
  Loader2,
  Send,
  Settings,
  Trash2,
  User,
  Wrench,
  X,
} from "lucide-react";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { AGENT_IDENTITIES, type AgentId } from "./AgentTeamSelector";
import { MarkdownRenderer } from "./MarkdownRenderer";
import type { ToolExecution } from "./ToolDisclosure";

interface ChatMessage {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  tool_executions?: ToolExecution[];
  structured_artifact?: Record<string, unknown> | null;
  created_at: string;
}

interface AgentChatDrawerProps {
  isOpen: boolean;
  agentId: AgentId;
  onClose: () => void;
  onOpenSettings?: () => void;
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
  ],
};

export const AgentChatDrawer: React.FC<AgentChatDrawerProps> = ({
  isOpen,
  agentId,
  onClose,
  onOpenSettings,
}) => {
  const { firebaseUser } = useAuth();
  const agent = AGENT_IDENTITIES[agentId];
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const getAuthHeaders = useCallback(async () => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (firebaseUser) {
      const token = await firebaseUser.getIdToken();
      headers.Authorization = `Bearer ${token}`;
    }
    return headers;
  }, [firebaseUser]);

  const loadHistory = useCallback(async () => {
    if (!isOpen || !firebaseUser) return;
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
  }, [agentId, firebaseUser, getAuthHeaders, isOpen]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [isOpen]);

  // Escape key handler
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

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
  const handleClearChat = async () => {
    if (!firebaseUser || isClearing) return;
    setIsClearing(true);
    setError(null);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/workspace/agents/${agentId}/chat`, {
        method: "DELETE",
        headers,
      });
      if (!res.ok) {
        throw new Error("Failed to clear conversation");
      }
      setMessages([]);
      setShowClearConfirm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clear conversation");
    } finally {
      setIsClearing(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm transition-opacity animate-in fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="agent-chat-title"
      data-testid="agent-chat-drawer"
    >
      <div className="flex h-full w-full max-w-2xl flex-col border-l border-border-subtle bg-surface-1 shadow-2xl text-text-primary">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border-subtle px-6 py-4">
          <div className="flex items-center gap-3">
            <img
              src={agent.avatar}
              alt={agent.name}
              className="h-10 w-10 rounded-full object-cover ring-2 ring-primary/20"
            />
            <div>
              <h2 id="agent-chat-title" className="text-base font-semibold text-text-primary">
                Chat with {agent.name}
              </h2>
              <p className="text-xs text-text-muted">{agent.role}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {messages.length > 0 && !showClearConfirm && (
              <button
                type="button"
                onClick={() => setShowClearConfirm(true)}
                className="flex items-center gap-1.5 rounded-lg border border-border-subtle bg-surface-2 px-2.5 py-1.5 text-xs font-medium text-text-muted hover:border-danger/40 hover:bg-danger/10 hover:text-danger transition-colors cursor-pointer"
                title="Clear conversation"
                data-testid="btn-clear-chat"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span>Clear chat</span>
              </button>
            )}

            {showClearConfirm && (
              <div className="flex items-center gap-1.5 rounded-lg border border-danger/40 bg-danger/10 px-2 py-1 text-xs">
                <span className="text-[11px] font-medium text-danger">Clear conversation?</span>
                <button
                  type="button"
                  onClick={() => void handleClearChat()}
                  disabled={isClearing}
                  className="rounded bg-danger px-2 py-0.5 text-[11px] font-semibold text-white hover:bg-danger/90 disabled:opacity-50 transition-colors cursor-pointer"
                  data-testid="btn-confirm-clear-chat"
                >
                  {isClearing ? "Clearing..." : "Yes, clear"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowClearConfirm(false)}
                  disabled={isClearing}
                  className="rounded px-1.5 py-0.5 text-[11px] text-text-muted hover:text-text-primary transition-colors cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            )}

            {onOpenSettings && (
              <button
                type="button"
                onClick={onOpenSettings}
                className="flex items-center gap-1.5 rounded-lg border border-border-subtle bg-surface-2 px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-surface-3 hover:text-text-primary transition-colors cursor-pointer"
                title="Open settings"
                data-testid="btn-chat-settings-shortcut"
              >
                <Settings className="h-3.5 w-3.5" />
                <span>Settings</span>
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-2 text-text-muted transition-colors hover:bg-surface-2 hover:text-text-primary cursor-pointer"
              aria-label="Close chat"
              data-testid="btn-close-chat"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Messages Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {isLoadingHistory ? (
            <div className="flex h-48 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center space-y-4 py-8">
              <img
                src={agent.avatar}
                alt={agent.name}
                className="h-16 w-16 rounded-full object-cover ring-4 ring-surface-2 shadow-lg"
              />
              <div>
                <h3 className="text-sm font-semibold text-text-primary">{agent.name}</h3>
                <p className="text-xs text-text-muted mt-1 max-w-sm">
                  {agentId === "alex"
                    ? "Ask quantitative questions, analyze channel retention baselines, or evaluate video opportunities."
                    : agentId === "leo"
                      ? "Leo is active in the Editor workspace. Direct conversational chat will activate in the Editor development phase."
                      : "Iris is active at the Release QA gate. Direct conversational chat will activate in the QA development phase."}
                </p>
              </div>

              {/* Suggested Prompts (Active for Alex) */}
              {agentId === "alex" && (
                <div className="w-full max-w-md space-y-2 pt-2">
                  <p className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">
                    Suggested Prompts
                  </p>
                  {STARTER_PROMPTS.alex.map((starter, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => void sendMessage(starter)}
                      className="w-full rounded-xl border border-border-subtle bg-surface-2/80 p-3 text-left text-xs text-text-secondary hover:border-primary/50 hover:bg-surface-2 hover:text-text-primary transition-all cursor-pointer"
                    >
                      {starter}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.message_id}
                className={`flex gap-3 text-xs ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                {msg.role === "assistant" && (
                  <img
                    src={agent.avatar}
                    alt={agent.name}
                    className="h-7 w-7 rounded-full object-cover ring-1 ring-border-subtle shrink-0 mt-0.5"
                  />
                )}

                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 space-y-2 ${
                    msg.role === "user"
                      ? "bg-primary text-white"
                      : "bg-surface-2 border border-border-subtle text-text-primary"
                  }`}
                >
                  {msg.role === "assistant" ? (
                    <MarkdownRenderer content={msg.content} />
                  ) : (
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                  )}

                  {/* Tool Execution Badges */}
                  {msg.tool_executions && msg.tool_executions.length > 0 && (
                    <div className="space-y-1.5 pt-2 border-t border-border-subtle/40">
                      {msg.tool_executions.map((tool, idx) => (
                        <div
                          key={idx}
                          className="flex items-center gap-1.5 rounded-md bg-surface-3/80 px-2 py-1 text-[11px] font-mono text-text-secondary"
                        >
                          <Wrench className="h-3 w-3 text-primary shrink-0" />
                          <span className="font-semibold">{tool.tool_name}</span>
                          {tool.goal && (
                            <span className="text-text-muted truncate">· {tool.goal}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Structured Analytical Artifact (if present) */}
                  {msg.structured_artifact && (
                    <div className="rounded-lg border border-primary/20 bg-primary/5 p-2.5 text-xs space-y-1">
                      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
                        <LineChart className="h-3 w-3" />
                        <span>
                          Analytical Artifact: {String(msg.structured_artifact.type || "Analysis")}
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                {msg.role === "user" && (
                  <div className="h-7 w-7 rounded-full bg-surface-3 flex items-center justify-center text-text-muted shrink-0 mt-0.5">
                    <User className="h-4 w-4" />
                  </div>
                )}
              </div>
            ))
          )}

          {isSending && (
            <div className="flex gap-3 text-xs justify-start items-center">
              <img
                src={agent.avatar}
                alt={agent.name}
                className="h-7 w-7 rounded-full object-cover ring-1 ring-border-subtle shrink-0"
              />
              <div className="flex items-center gap-2 rounded-2xl bg-surface-2 border border-border-subtle px-4 py-2.5 text-text-muted">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                <span>{agent.name} is analyzing...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mx-6 mb-2 flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-3.5 py-2 text-xs text-red-400">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Input Footer */}
        <div className="border-t border-border-subtle p-4 bg-surface-1">
          {agentId === "alex" ? (
            <div className="relative flex items-end rounded-xl border border-border-subtle bg-surface-2 focus-within:border-primary transition-colors">
              <textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={2}
                placeholder={`Ask ${agent.name} a question... (Enter to send, Shift+Enter for new line)`}
                className="w-full resize-none bg-transparent p-3 pr-12 text-xs text-text-primary outline-none placeholder:text-text-muted"
                data-testid="input-chat-message"
              />
              <button
                type="button"
                onClick={() => void sendMessage()}
                disabled={!inputMessage.trim() || isSending}
                className="absolute bottom-2.5 right-2.5 rounded-lg bg-primary p-2 text-white hover:bg-primary-hover transition-colors disabled:opacity-40 cursor-pointer"
                aria-label="Send message"
                data-testid="btn-send-chat"
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : (
            <div className="rounded-xl border border-border-subtle bg-surface-2/60 p-3 text-center text-xs text-text-muted">
              <span>
                {agent.name} direct chat activates in the {agentId === "leo" ? "Editor" : "QA"}{" "}
                development phase.
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
