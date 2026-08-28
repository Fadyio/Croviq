import React, { useCallback, useEffect, useRef, useState } from "react";
import { BookOpen, Check, ExternalLink, Plus, RotateCcw, Save, Search, X } from "lucide-react";
import type { components } from "../../api/generated";
import { useAuth } from "../../auth/AuthContext";
import alexAvatar from "../../assets/agents/alex.webp";

type AgentSettings = components["schemas"]["AgentSettingsResponse"];
type MemorySummary = components["schemas"]["AgentMemorySummaryResponse"];
type ResearchConfig = components["schemas"]["ResearchConfig"];
type ResearchPrompt = components["schemas"]["ResearchPrompt"];
type ResearchCadence = components["schemas"]["ResearchCadence"];
type Tab = "prompt" | "memory" | "research";

const CADENCES: Array<{ value: ResearchCadence; label: string }> = [
  { value: "EVERY_HOUR", label: "Every hour" },
  { value: "EVERY_6_HOURS", label: "Every 6 hours" },
  { value: "EVERY_12_HOURS", label: "Every 12 hours" },
  { value: "EVERY_DAY", label: "Every day" },
  { value: "EVERY_3_DAYS", label: "Every 3 days" },
  { value: "EVERY_WEEK", label: "Every week" },
];

export const AlexSettingsDrawer: React.FC<{ open: boolean; onClose: () => void }> = ({
  open,
  onClose,
}) => {
  const { firebaseUser } = useAuth();
  const closeRef = useRef<HTMLButtonElement>(null);
  const [tab, setTab] = useState<Tab>("prompt");
  const [settings, setSettings] = useState<AgentSettings | null>(null);
  const [memory, setMemory] = useState<MemorySummary | null>(null);
  const [research, setResearch] = useState<ResearchConfig | null>(null);
  const [promptText, setPromptText] = useState("");
  const [sourceDrafts, setSourceDrafts] = useState<Record<string, string>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const authHeaders = useCallback(async (): Promise<Record<string, string>> => {
    if (!firebaseUser) throw new Error("Authentication required");
    return {
      Authorization: `Bearer ${await firebaseUser.getIdToken()}`,
      "Content-Type": "application/json",
    };
  }, [firebaseUser]);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    let cancelled = false;
    void (async () => {
      setError(null);
      try {
        const headers = await authHeaders();
        const [settingsResponse, memoryResponse, researchResponse] = await Promise.all([
          fetch("/api/workspace/agent-settings", { headers }),
          fetch("/api/workspace/agent-settings/memory", { headers }),
          fetch("/api/channels/research/config", { headers }),
        ]);
        if (!settingsResponse.ok || !memoryResponse.ok || !researchResponse.ok) {
          throw new Error("Alex settings could not be loaded");
        }
        const nextSettings = (await settingsResponse.json()) as AgentSettings;
        if (cancelled) return;
        setSettings(nextSettings);
        setPromptText(nextSettings.alex_prompt.prompt_text);
        setMemory((await memoryResponse.json()) as MemorySummary);
        setResearch((await researchResponse.json()) as ResearchConfig);
      } catch (reason) {
        if (!cancelled)
          setError(reason instanceof Error ? reason.message : "Alex settings could not be loaded");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authHeaders, open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, open]);

  const savePrompt = async () => {
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch("/api/workspace/agent-settings/prompts/alex", {
        method: "PUT",
        headers: await authHeaders(),
        body: JSON.stringify({ prompt_text: promptText }),
      });
      if (!response.ok) throw new Error("Alex prompt could not be saved");
      const alexPrompt = (await response.json()) as AgentSettings["alex_prompt"];
      setSettings((current) => (current ? { ...current, alex_prompt: alexPrompt } : current));
      setNotice("Alex prompt saved");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Alex prompt could not be saved");
    } finally {
      setIsSaving(false);
    }
  };

  const resetPrompt = async () => {
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch("/api/workspace/agent-settings/prompts/alex/reset", {
        method: "POST",
        headers: await authHeaders(),
      });
      if (!response.ok) throw new Error("Alex prompt could not be reset");
      const alexPrompt = (await response.json()) as AgentSettings["alex_prompt"];
      setSettings((current) => (current ? { ...current, alex_prompt: alexPrompt } : current));
      setPromptText(alexPrompt.prompt_text);
      setNotice("Default Alex prompt restored");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Alex prompt could not be reset");
    } finally {
      setIsSaving(false);
    }
  };

  const updatePrompt = (promptId: string, change: Partial<ResearchPrompt>) => {
    setResearch((current) =>
      current
        ? {
            ...current,
            prompts: (current.prompts ?? []).map((prompt) =>
              prompt.prompt_id === promptId ? { ...prompt, ...change } : prompt,
            ),
          }
        : current,
    );
  };

  const addSource = (promptId: string) => {
    const source = sourceDrafts[promptId]?.trim();
    if (!source) return;
    const prompt = (research?.prompts ?? []).find((item) => item.prompt_id === promptId);
    const preferredSources = prompt?.preferred_sources ?? [];
    if (!prompt || preferredSources.includes(source)) return;
    updatePrompt(promptId, { preferred_sources: [...preferredSources, source] });
    setSourceDrafts((current) => ({ ...current, [promptId]: "" }));
  };

  const addResearchPrompt = () => {
    if (!research) return;
    const promptId = `research-${crypto.randomUUID()}`;
    setResearch({
      ...research,
      prompts: [
        ...(research.prompts ?? []),
        {
          prompt_id: promptId,
          text: "",
          enabled: true,
          use_broad_web_search: true,
          preferred_sources: [],
        },
      ],
    });
  };

  const saveResearch = async () => {
    if (!research) return;
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch("/api/channels/research/config", {
        method: "PUT",
        headers: await authHeaders(),
        body: JSON.stringify({
          enabled: research.enabled,
          cadence: research.cadence,
          prompts: research.prompts,
        }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
        throw new Error(
          payload?.detail
            ? "Check that every source is a public URL or domain"
            : "Research settings could not be saved",
        );
      }
      setResearch((await response.json()) as ResearchConfig);
      setNotice("Research schedule saved");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Research settings could not be saved");
    } finally {
      setIsSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/55"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <aside
        className="flex h-full w-full max-w-xl flex-col border-l border-border-strong bg-surface-1 shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="alex-settings-title"
      >
        <header className="flex items-center justify-between border-b border-border-subtle px-5 py-4">
          <div className="flex items-center gap-3">
            <img
              src={alexAvatar}
              alt=""
              className="h-10 w-10 rounded-md border border-border-strong object-cover"
            />
            <div>
              <h2 id="alex-settings-title" className="text-sm font-semibold">
                Alex settings
              </h2>
              <p className="text-xs text-text-muted">Data Scientist</p>
            </div>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close Alex settings"
            className="rounded-md p-2 text-text-muted hover:bg-surface-2 hover:text-text-primary"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <nav
          className="flex border-b border-border-subtle px-5"
          aria-label="Alex settings sections"
        >
          {(["prompt", "memory", "research"] as Tab[]).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setTab(item)}
              aria-current={tab === item ? "page" : undefined}
              className={`border-b-2 px-3 py-3 text-xs font-medium capitalize ${tab === item ? "border-primary text-text-primary" : "border-transparent text-text-muted hover:text-text-secondary"}`}
            >
              {item}
            </button>
          ))}
        </nav>

        <div className="flex-1 overflow-y-auto p-5">
          {error && (
            <div
              role="alert"
              className="mb-4 rounded-md border border-error/30 bg-error/10 p-3 text-xs text-error"
            >
              {error}
            </div>
          )}
          {notice && (
            <div
              role="status"
              className="mb-4 flex items-center gap-2 rounded-md border border-success/25 bg-success/10 p-3 text-xs text-success"
            >
              <Check className="h-3.5 w-3.5" />
              {notice}
            </div>
          )}

          {tab === "prompt" && (
            <section aria-labelledby="alex-prompt-heading">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <h3 id="alex-prompt-heading" className="text-sm font-semibold">
                    Working prompt
                  </h3>
                  <p className="mt-1 text-xs text-text-muted">
                    Fully editable. Internal analysis tools remain hidden.
                  </p>
                </div>
                <span className="rounded border border-border-subtle bg-background px-2 py-1 font-mono text-[10px] text-text-muted">
                  v{settings?.alex_prompt.version ?? 1}
                </span>
              </div>
              <textarea
                value={promptText}
                onChange={(event) => setPromptText(event.target.value)}
                rows={20}
                className="w-full resize-y rounded-md border border-border-strong bg-background p-3 font-mono text-xs leading-5 text-text-primary outline-none focus:border-primary"
                aria-label="Alex working prompt"
              />
              <div className="mt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={resetPrompt}
                  disabled={isSaving}
                  className="flex items-center gap-2 rounded-md border border-border-strong px-3 py-2 text-xs text-text-secondary hover:bg-surface-2 disabled:opacity-50"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Reset to default
                </button>
                <button
                  type="button"
                  onClick={savePrompt}
                  disabled={isSaving || !promptText.trim()}
                  className="flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-xs font-semibold text-background disabled:opacity-50"
                >
                  <Save className="h-3.5 w-3.5" />
                  Save
                </button>
              </div>
            </section>
          )}

          {tab === "memory" && (
            <section aria-labelledby="alex-memory-heading">
              <div className="mb-4">
                <h3 id="alex-memory-heading" className="text-sm font-semibold">
                  Channel knowledge
                </h3>
                <p className="mt-1 text-xs text-text-muted">
                  Read-only lessons from shared Channel Memory, including provenance when available.
                </p>
              </div>
              <div className="space-y-3">
                {(memory?.lessons ?? []).map((lesson) => (
                  <article
                    key={`${lesson.topic}-${lesson.content}`}
                    className="rounded-md border border-border-subtle bg-background p-3"
                  >
                    <div className="flex items-start gap-2">
                      <BookOpen className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                      <div>
                        <h4 className="text-xs font-semibold">{lesson.topic}</h4>
                        <p className="mt-1 text-xs leading-5 text-text-secondary">
                          {lesson.content}
                        </p>
                        {lesson.learned_from && (
                          <p className="mt-2 text-[10px] text-text-muted">
                            Provenance: {lesson.learned_from}
                          </p>
                        )}
                      </div>
                    </div>
                  </article>
                ))}
                {!(memory?.lessons ?? []).length && (
                  <p className="rounded-md border border-dashed border-border-subtle p-6 text-center text-xs text-text-muted">
                    No durable Channel Lessons retrieved.
                  </p>
                )}
              </div>
            </section>
          )}

          {tab === "research" && research && (
            <section aria-labelledby="alex-research-heading" className="space-y-5">
              <div>
                <h3 id="alex-research-heading" className="text-sm font-semibold">
                  Background research
                </h3>
                <p className="mt-1 text-xs text-text-muted">
                  Runs while you are away. Findings require public, grounded citations.
                </p>
              </div>
              <label className="block text-xs font-medium text-text-secondary">
                Schedule
                <select
                  value={research.cadence}
                  onChange={(event) =>
                    setResearch({ ...research, cadence: event.target.value as ResearchCadence })
                  }
                  className="mt-2 w-full rounded-md border border-border-strong bg-background px-3 py-2.5 text-xs text-text-primary outline-none focus:border-primary"
                >
                  {CADENCES.map((cadence) => (
                    <option key={cadence.value} value={cadence.value}>
                      {cadence.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="space-y-4">
                {(research.prompts ?? []).map((prompt) => (
                  <article
                    key={prompt.prompt_id}
                    className="rounded-md border border-border-subtle bg-background p-4"
                  >
                    <label className="flex items-center gap-2 text-xs font-medium">
                      <input
                        type="checkbox"
                        checked={prompt.enabled}
                        onChange={(event) =>
                          updatePrompt(prompt.prompt_id, { enabled: event.target.checked })
                        }
                      />
                      Enabled
                    </label>
                    <textarea
                      value={prompt.text}
                      onChange={(event) =>
                        updatePrompt(prompt.prompt_id, { text: event.target.value })
                      }
                      rows={4}
                      className="mt-3 w-full resize-y rounded-md border border-border-subtle bg-surface-1 p-3 text-xs leading-5 outline-none focus:border-primary"
                      aria-label="Research prompt"
                    />
                    <label className="mt-3 flex items-center gap-2 text-xs text-text-secondary">
                      <input
                        type="checkbox"
                        checked={prompt.use_broad_web_search}
                        onChange={(event) =>
                          updatePrompt(prompt.prompt_id, {
                            use_broad_web_search: event.target.checked,
                          })
                        }
                      />
                      Search broader web
                    </label>
                    <div className="mt-4">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-muted">
                        Preferred public sources
                      </p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {(prompt.preferred_sources ?? []).map((source) => (
                          <button
                            key={source}
                            type="button"
                            onClick={() =>
                              updatePrompt(prompt.prompt_id, {
                                preferred_sources: (prompt.preferred_sources ?? []).filter(
                                  (item) => item !== source,
                                ),
                              })
                            }
                            title="Remove source"
                            className="flex items-center gap-1 rounded border border-border-subtle bg-surface-1 px-2 py-1 text-[10px] text-text-secondary"
                          >
                            <ExternalLink className="h-3 w-3" />
                            {source}
                            <X className="h-3 w-3" />
                          </button>
                        ))}
                      </div>
                      <div className="mt-2 flex gap-2">
                        <input
                          value={sourceDrafts[prompt.prompt_id] ?? ""}
                          onChange={(event) =>
                            setSourceDrafts((current) => ({
                              ...current,
                              [prompt.prompt_id]: event.target.value,
                            }))
                          }
                          onKeyDown={(event) =>
                            event.key === "Enter" &&
                            (event.preventDefault(), addSource(prompt.prompt_id))
                          }
                          placeholder="domain or full public URL"
                          className="min-w-0 flex-1 rounded-md border border-border-subtle bg-surface-1 px-3 py-2 text-xs outline-none focus:border-primary"
                        />
                        <button
                          type="button"
                          onClick={() => addSource(prompt.prompt_id)}
                          className="rounded-md border border-border-strong p-2 text-text-secondary hover:bg-surface-2"
                          aria-label="Add preferred source"
                        >
                          <Plus className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      <p className="mt-2 text-[10px] leading-4 text-text-muted">
                        Public supported pages only. Paywalls, login-only pages, and private
                        networks may be unavailable.
                      </p>
                    </div>
                  </article>
                ))}
              </div>
              <button
                type="button"
                onClick={addResearchPrompt}
                className="flex items-center gap-2 text-xs font-medium text-primary"
              >
                <Search className="h-3.5 w-3.5" />
                Add research prompt
              </button>
              <div className="flex justify-end border-t border-border-subtle pt-4">
                <button
                  type="button"
                  onClick={saveResearch}
                  disabled={
                    isSaving || (research.prompts ?? []).some((prompt) => !prompt.text.trim())
                  }
                  className="flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-xs font-semibold text-background disabled:opacity-50"
                >
                  <Save className="h-3.5 w-3.5" />
                  Save research settings
                </button>
              </div>
            </section>
          )}
        </div>
      </aside>
    </div>
  );
};
