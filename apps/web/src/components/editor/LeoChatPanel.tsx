import { Check, Loader2, MessageSquare, Send, Sparkles, User, X } from "lucide-react";
import React, { useCallback, useEffect, useRef, useState } from "react";
import leoAvatar from "../../assets/agents/leo.webp";
import { type EditDecisionList, type EditorSelection, formatTimecode } from "../../lib/edl-adapter";
import { MarkdownRenderer } from "../MarkdownRenderer";

export type LeoChatContext = EditorSelection;

interface ToolExecution {
  tool_name?: string;
  name?: string;
  tool?: string;
  goal?: string;
  status?: string;
  result?: string;
  output?: Record<string, unknown> | string;
  [key: string]: unknown;
}

interface ChatMessage {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  tool_executions?: ToolExecution[];
  created_at?: string;
}

export interface LeoChatResponse extends ChatMessage {
  edl?: EditDecisionList;
  timeline_updated?: boolean;
  voiceover_updated?: boolean;
  preview_updated?: boolean;
}

interface LeoChatPanelProps {
  productionId: string;
  currentPlayheadMs: number;
  activeEdlId?: string;
  context: LeoChatContext | null;
  getAuthToken: () => Promise<string>;
  onClearContext: () => void;
  onWorkspaceUpdated?: (response: LeoChatResponse) => void | Promise<void>;
  className?: string;
}

const QUICK_PROMPTS = [
  "Why did you remove this?",
  "Can we make this section faster?",
  "Tighten selected section",
  "Undo that edit",
];

const toolDisplayName = (tool: ToolExecution): string => {
  const raw = String(tool.tool_name || tool.name || tool.tool || "Edit applied");
  return raw.replaceAll("_", " ").replace(/\b\w/gu, (letter) => letter.toUpperCase());
};

export const LeoChatPanel: React.FC<LeoChatPanelProps> = ({
  productionId,
  currentPlayheadMs,
  activeEdlId,
  context,
  getAuthToken,
  onClearContext,
  onWorkspaceUpdated,
  className = "",
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const authHeaders = useCallback(async (): Promise<Record<string, string>> => {
    const token = await getAuthToken();
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    };
  }, [getAuthToken]);

  useEffect(() => {
    let active = true;
    const loadHistory = async () => {
      setIsLoadingHistory(true);
      setError(null);
      try {
        const response = await fetch(`/api/productions/${productionId}/chat/history`, {
          headers: await authHeaders(),
        });
        if (!response.ok) throw new Error("Leo's conversation history could not be loaded.");
        const payload = (await response.json()) as { messages?: ChatMessage[] } | ChatMessage[];
        if (active) setMessages(Array.isArray(payload) ? payload : payload.messages || []);
      } catch (loadError) {
        if (active) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Leo's conversation history could not be loaded.",
          );
        }
      } finally {
        if (active) setIsLoadingHistory(false);
      }
    };

    void loadHistory();
    return () => {
      active = false;
    };
  }, [authHeaders, productionId]);

  useEffect(() => {
    if (messages.length > 0 || isSending) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages.length, isSending]);

  const sendMessage = async (message?: string) => {
    const content = (message ?? inputMessage).trim();
    if (!content || isSending) return;

    const optimisticMessage: ChatMessage = {
      message_id: `pending-${Date.now()}`,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((current) => [...current, optimisticMessage]);
    setInputMessage("");
    setIsSending(true);
    setError(null);

    try {
      const response = await fetch(`/api/productions/${productionId}/chat`, {
        method: "POST",
        headers: await authHeaders(),
        body: JSON.stringify({
          message: content,
          current_playhead_ms: Math.round(currentPlayheadMs),
          active_edl_id: activeEdlId || context?.active_edl_id,
          ...(context
            ? {
                editor_context: {
                  ...context,
                  active_edl_id: activeEdlId || context.active_edl_id,
                },
                selected_range_ms: [
                  Math.round(context.source_start_ms),
                  Math.round(context.source_end_ms),
                ],
                selected_element: {
                  type: context.selection_type.toLowerCase(),
                  id: context.cut_id || context.chapter_id || "selection",
                  label: context.label || "selection",
                  start_ms: Math.round(context.source_start_ms),
                  end_ms: Math.round(context.source_end_ms),
                },
              }
            : {}),
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(
          typeof payload?.detail === "string"
            ? payload.detail
            : "Leo could not complete that request.",
        );
      }
      const assistantMessage = (await response.json()) as LeoChatResponse;
      setMessages((current) => [...current, assistantMessage]);
      if (context) onClearContext();
      await onWorkspaceUpdated?.(assistantMessage);
    } catch (sendError) {
      setError(
        sendError instanceof Error ? sendError.message : "Leo could not complete that request.",
      );
    } finally {
      setIsSending(false);
    }
  };

  return (
    <section
      className={`flex min-h-0 flex-1 flex-col overflow-hidden bg-surface-1 font-sans ${className}`}
      aria-label="Chat with Leo"
      data-testid="leo-chat-panel"
    >
      {/* Scrollable Conversation History */}
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3 space-y-3" aria-live="polite">
        {isLoadingHistory ? (
          <div className="flex h-32 items-center justify-center gap-2 text-[11px] text-text-muted">
            <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
            Loading conversation…
          </div>
        ) : messages.length === 0 ? (
          <div className="flex h-full min-h-40 flex-col items-center justify-center px-5 text-center">
            <img
              src={leoAvatar}
              alt=""
              className="mb-3 size-10 rounded-full object-cover ring-1 ring-border-subtle shadow-xs"
            />
            <p className="text-xs font-semibold text-text-primary">Edit with Leo</p>
            <p className="mt-1 max-w-60 text-[10px] leading-relaxed text-text-muted">
              Ask about an editorial choice or request a change. Leo uses the selected timeline
              context and updates the canonical edit.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {messages.map((message) => (
              <article
                key={message.message_id}
                className={`flex items-start gap-2 ${message.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {message.role === "assistant" && (
                  <img
                    src={leoAvatar}
                    alt=""
                    className="mt-0.5 size-6 shrink-0 rounded-full object-cover ring-1 ring-border-subtle"
                  />
                )}
                <div className="max-w-[85%] space-y-1.5">
                  <div
                    className={`rounded-lg px-3 py-2 text-[11px] leading-relaxed shadow-xs ${
                      message.role === "user"
                        ? "bg-primary text-white"
                        : "border border-border-subtle bg-surface-2 text-text-primary"
                    }`}
                  >
                    {message.role === "assistant" ? (
                      <MarkdownRenderer content={message.content} />
                    ) : (
                      <p className="whitespace-pre-wrap">{message.content}</p>
                    )}
                  </div>

                  {/* Compact action / result row (Priority 7) */}
                  {message.tool_executions && message.tool_executions.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 pt-0.5" aria-label="Action status">
                      {message.tool_executions.map((tool, index) => {
                        const reasonText =
                          tool.output && typeof tool.output === "object" && (tool.output as Record<string, unknown>).reason
                            ? String((tool.output as Record<string, unknown>).reason)
                            : tool.goal || toolDisplayName(tool);

                        return (
                          <div
                            key={`${message.message_id}-tool-${index}`}
                            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-surface-2 border border-border-subtle text-[10px] text-text-secondary"
                          >
                            <Check className="size-3 text-emerald-400 shrink-0" />
                            <span className="font-medium text-text-primary truncate max-w-xs">{reasonText}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
                {message.role === "user" && (
                  <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-primary/10 text-primary">
                    <User className="size-3" aria-hidden="true" />
                  </span>
                )}
              </article>
            ))}
          </div>
        )}

        {isSending && (
          <div className="mt-2 flex items-start gap-2">
            <img
              src={leoAvatar}
              alt=""
              className="size-6 rounded-full object-cover ring-1 ring-border-subtle"
            />
            <div className="flex items-center gap-2 rounded-lg border border-border-subtle bg-surface-2 px-3 py-1.5 text-[10px] text-text-muted">
              <Loader2 className="size-3 animate-spin text-primary" aria-hidden="true" />
              Leo is editing…
            </div>
          </div>
        )}
        {error && (
          <div
            className="mt-2 rounded-md border border-danger/30 bg-danger/10 px-2.5 py-2 text-[10px] text-danger"
            role="alert"
          >
            {error}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Pinned Bottom Composer */}
      <footer className="shrink-0 border-t border-border-subtle bg-surface-1 p-3">
        {/* Quick starter prompts (shown before active conversation) */}
        {messages.length <= 1 && (
          <div className="mb-2 flex gap-1.5 overflow-x-auto pb-0.5" aria-label="Quick prompts">
            {QUICK_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => setInputMessage(prompt)}
                className="shrink-0 rounded-full border border-border-subtle bg-surface-2 px-2.5 py-1 text-[10px] font-medium text-text-secondary transition-colors hover:border-primary/40 hover:text-text-primary hover:bg-surface-3 cursor-pointer"
              >
                {prompt}
              </button>
            ))}
          </div>
        )}

        {/* Small Selection Context Chip (Priority 7) */}
        {context && (
          <div
            className="mb-2 flex items-center justify-between gap-2 px-2.5 py-1 rounded-md bg-primary/10 border border-primary/20 text-[11px] text-text-primary shadow-xs"
            data-testid="leo-chat-selection-attachment"
          >
            <div className="flex items-center gap-1.5 min-w-0 truncate">
              <Sparkles className="size-3 text-primary shrink-0" />
              <span className="font-semibold text-primary">Selected</span>
              <span className="text-text-muted">&middot;</span>
              <span className="font-mono tabular-nums text-text-secondary text-[10px]">
                {formatTimecode(context.source_start_ms)}–{formatTimecode(context.source_end_ms)}
              </span>
              {context.transcript_text && (
                <>
                  <span className="text-text-muted">&middot;</span>
                  <span className="truncate italic text-text-muted">
                    &ldquo;{context.transcript_text}&rdquo;
                  </span>
                </>
              )}
            </div>
            <button
              type="button"
              onClick={onClearContext}
              className="shrink-0 p-0.5 rounded hover:bg-surface-3 text-text-muted hover:text-text-primary transition-colors cursor-pointer"
              title="Clear selection"
              aria-label="Clear selection"
              data-testid="btn-clear-selection"
            >
              <X className="size-3" />
            </button>
          </div>
        )}

        <form
          className="flex items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            void sendMessage();
          }}
        >
          <label htmlFor="leo-chat-input" className="sr-only">
            Message Leo
          </label>
          <textarea
            id="leo-chat-input"
            value={inputMessage}
            onChange={(event) => setInputMessage(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void sendMessage();
              }
            }}
            placeholder="Ask Leo or request an edit…"
            rows={2}
            className="min-h-14 flex-1 resize-none rounded-md border border-border-subtle bg-surface-2 px-2.5 py-2 text-[11px] text-text-primary outline-none placeholder:text-text-muted focus:border-primary"
          />
          <button
            type="submit"
            disabled={!inputMessage.trim() || isSending}
            className="flex size-9 shrink-0 items-center justify-center rounded-md bg-primary text-white transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 cursor-pointer"
            aria-label="Send message to Leo"
          >
            {isSending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Send className="size-3.5" />
            )}
          </button>
        </form>
        <div className="mt-1.5 flex items-center gap-1 text-[9px] text-text-muted">
          <MessageSquare className="size-2.5" aria-hidden="true" />
          Enter to send · Shift+Enter for a new line
        </div>
      </footer>
    </section>
  );
};
