import {
  AlertCircle,
  ExternalLink,
  Loader2,
  Play,
  Plus,
  RotateCcw,
  Save,
  Search,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import React, { useCallback, useEffect, useRef, useState } from "react";
import type { components } from "../../api/generated";
import { useAuth } from "../../auth/AuthContext";
import { AGENT_IDENTITIES, type AgentId } from "../AgentTeamSelector";

type AgentPromptConfig = components["schemas"]["AgentPromptConfig"];
type VoiceSettingsConfig = components["schemas"]["VoiceSettingsConfig"];
type AgentMemorySummary = components["schemas"]["AgentMemorySummaryResponse"] & {
  memories?: MemoryRecordItem[];
};
type VoiceCatalogItem = components["schemas"]["VoiceCatalogItem"];
type ResearchConfig = components["schemas"]["ResearchConfig"];
type ResearchCadence = components["schemas"]["ResearchCadence"];

interface MemoryRecordItem {
  name: string;
  memory_id: string;
  fact: string;
  scope?: Record<string, string>;
  provenance?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

interface AgentSettingsDrawerProps {
  isOpen: boolean;
  agentId: AgentId;
  onClose: () => void;
  onSaved?: () => void;
}

const CADENCES: Array<{ value: ResearchCadence; label: string }> = [
  { value: "EVERY_HOUR", label: "Every hour" },
  { value: "EVERY_6_HOURS", label: "Every 6 hours" },
  { value: "EVERY_12_HOURS", label: "Every 12 hours" },
  { value: "EVERY_DAY", label: "Every day" },
  { value: "EVERY_3_DAYS", label: "Every 3 days" },
  { value: "EVERY_WEEK", label: "Every week" },
];

export const AgentSettingsDrawer: React.FC<AgentSettingsDrawerProps> = ({
  isOpen,
  agentId,
  onClose,
  onSaved,
}) => {
  const { firebaseUser } = useAuth();
  const agent = AGENT_IDENTITIES[agentId];

  // Available tabs depending on agent
  type Tab = "prompt" | "memory" | "research" | "voice";
  const [activeTab, setActiveTab] = useState<Tab>("prompt");

  // Prompt state
  const [promptText, setPromptText] = useState<string>("");
  const [isPromptSaving, setIsPromptSaving] = useState<boolean>(false);
  const [promptNotice, setPromptNotice] = useState<string | null>(null);

  // Memory state (Canonical Google Memory Bank)
  const [memories, setMemories] = useState<MemoryRecordItem[]>([]);
  const [memorySearchQuery, setMemorySearchQuery] = useState<string>("");
  const [isAddingMemory, setIsAddingMemory] = useState<boolean>(false);
  const [newMemoryText, setNewMemoryText] = useState<string>("");
  const [newMemoryProvenance, setNewMemoryProvenance] = useState<string>("");
  const [memoryNotice, setMemoryNotice] = useState<string | null>(null);
  const [deletingMemoryId, setDeletingMemoryId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  // Research state (Alex)
  const [research, setResearch] = useState<ResearchConfig | null>(null);
  const [isResearchSaving, setIsResearchSaving] = useState<boolean>(false);
  const [researchNotice, setResearchNotice] = useState<string | null>(null);
  const [newSourceDraft, setNewSourceDraft] = useState<string>("");
  // Voice state (Leo)
  const [voiceSettings, setVoiceSettings] = useState<VoiceSettingsConfig | null>(null);
  const [voices, setVoices] = useState<VoiceCatalogItem[]>([]);
  const [isVoiceSaving, setIsVoiceSaving] = useState<boolean>(false);
  const [voiceNotice, setVoiceNotice] = useState<string | null>(null);
  const [isPlayingAudio, setIsPlayingAudio] = useState<boolean>(false);

  const activeAudioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    return () => {
      if (activeAudioRef.current) {
        activeAudioRef.current.pause();
        activeAudioRef.current = null;
      }
    };
  }, []);
  // General loading & error
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const getAuthHeaders = useCallback(async (): Promise<Record<string, string>> => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (firebaseUser) {
      const token = await firebaseUser.getIdToken();
      headers.Authorization = `Bearer ${token}`;
    } else if (import.meta.env.DEV || window.location.hostname === "localhost") {
      headers.Authorization =
        "Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIyN2lFQlVNY3U2VG9EWXdwMk9kRUlIQnV3SUEzIiwidXNlcl9pZCI6IjI3aUVCVU1jdTZUb0RZd3AyT2RFSUhCdXdJQTMiLCJlbWFpbCI6ImRlbW9AY3JvdmlxLmFwcCJ9.signature";
    }
    return headers;
  }, [firebaseUser]);

  // Adjust active tab when switching agents
  useEffect(() => {
    if (agentId !== "alex" && activeTab === "research") {
      setActiveTab("prompt");
    }
    if (agentId !== "leo" && activeTab === "voice") {
      setActiveTab("prompt");
    }
  }, [agentId, activeTab]);

  // Escape key handler
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Load all settings data on open or agentId change
  const loadData = useCallback(async () => {
    if (!isOpen) return;
    setIsLoading(true);
    setError(null);
    try {
      const headers = await getAuthHeaders();

      // 1. Load agent settings (prompts & voices)
      const settingsRes = await fetch("/api/workspace/agent-settings", { headers });
      if (settingsRes.ok) {
        const data = await settingsRes.json();
        const p: AgentPromptConfig =
          agentId === "leo"
            ? data.leo_prompt
            : agentId === "iris"
              ? data.iris_prompt
              : data.alex_prompt;
        if (p) {
          setPromptText(p.prompt_text || "");
        }
        if (data.voice_settings) {
          setVoiceSettings(data.voice_settings);
        }
        if (data.voices) {
          setVoices(data.voices);
        }
      }

      // 2. Load canonical Memory Bank records
      const memoryRes = await fetch(`/api/workspace/agent-settings/memory?agent_id=${agentId}`, {
        headers,
      });
      if (memoryRes.ok) {
        const memData = (await memoryRes.json()) as AgentMemorySummary;
        // Parse canonical memories or fallback lessons if any
        if (memData.memories && memData.memories.length > 0) {
          setMemories(memData.memories as MemoryRecordItem[]);
        } else if (memData.lessons && memData.lessons.length > 0) {
          setMemories(
            memData.lessons.map((l, idx) => ({
              name: `lesson_${idx}`,
              memory_id: `lsn_${idx}`,
              fact: l.topic + (l.content ? `\n${l.content}` : ""),
              provenance: l.learned_from || "Channel analytics",
            })),
          );
        } else {
          setMemories([]);
        }
      }

      // 3. If Alex, load research config
      if (agentId === "alex") {
        const researchRes = await fetch("/api/channels/research/config", { headers });
        if (researchRes.ok) {
          const rData = (await researchRes.json()) as ResearchConfig;
          setResearch(rData);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load agent configuration");
    } finally {
      setIsLoading(false);
    }
  }, [agentId, getAuthHeaders, isOpen]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  // Prompt actions
  const handleSavePrompt = async () => {
    setIsPromptSaving(true);
    setPromptNotice(null);
    setError(null);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/workspace/agent-settings/prompt/${agentId}`, {
        method: "PUT",
        headers,
        body: JSON.stringify({ prompt_text: promptText }),
      });
      if (!res.ok) throw new Error(`Failed to save ${agent.name} prompt`);
      const updated: AgentPromptConfig = await res.json();
      setPromptText(updated.prompt_text);
      setPromptNotice("Saved");
      setTimeout(() => setPromptNotice(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save prompt");
    } finally {
      setIsPromptSaving(false);
    }
  };
  const handleResetPrompt = async () => {
    setIsPromptSaving(true);
    setPromptNotice(null);
    setError(null);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/workspace/agent-settings/prompt/${agentId}/reset`, {
        method: "POST",
        headers,
      });
      if (!res.ok) throw new Error(`Failed to restore default ${agent.name} prompt`);
      const restored: AgentPromptConfig = await res.json();
      setPromptText(restored.prompt_text);
      setPromptNotice("Default prompt restored");
      setTimeout(() => setPromptNotice(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reset prompt");
    } finally {
      setIsPromptSaving(false);
    }
  };

  // Memory actions (Google Memory Bank CRUD)
  const handleAddMemory = async () => {
    if (!newMemoryText.trim()) return;
    setIsLoading(true);
    setMemoryNotice(null);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/workspace/agent-settings/memory?agent_id=${agentId}`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          fact: newMemoryText.trim(),
          provenance: newMemoryProvenance.trim() || "Creator instruction",
        }),
      });
      if (!res.ok) throw new Error("Failed to create memory in Memory Bank");
      const createdRecord: MemoryRecordItem = await res.json();
      setMemories((prev) => [createdRecord, ...prev]);
      setNewMemoryText("");
      setNewMemoryProvenance("");
      setIsAddingMemory(false);
      setMemoryNotice("Memory saved to Memory Bank");
      setTimeout(() => setMemoryNotice(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add memory");
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteMemory = async (memoryIdOrName: string) => {
    setIsDeleting(true);
    setMemoryNotice(null);
    try {
      const headers = await getAuthHeaders();
      const cleanId = encodeURIComponent(memoryIdOrName);
      const res = await fetch(`/api/workspace/agent-settings/memory/${cleanId}`, {
        method: "DELETE",
        headers,
      });
      if (!res.ok) throw new Error("Failed to delete memory from Memory Bank");
      setMemories((prev) =>
        prev.filter((m) => m.memory_id !== memoryIdOrName && m.name !== memoryIdOrName),
      );
      setDeletingMemoryId(null);
      setMemoryNotice("Memory deleted from Memory Bank");
      setTimeout(() => setMemoryNotice(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete memory");
    } finally {
      setIsDeleting(false);
    }
  };

  // Research actions (Alex)
  const handleSaveResearch = async () => {
    if (!research) return;
    setIsResearchSaving(true);
    setResearchNotice(null);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch("/api/channels/research/config", {
        method: "PUT",
        headers,
        body: JSON.stringify({
          enabled: research.enabled,
          cadence: research.cadence,
          prompts: research.prompts,
        }),
      });
      if (!res.ok) throw new Error("Failed to save research configuration");
      const updated: ResearchConfig = await res.json();
      setResearch(updated);
      setResearchNotice("Research settings saved");
      onSaved?.();
      setTimeout(() => setResearchNotice(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save research settings");
    } finally {
      setIsResearchSaving(false);
    }
  };

  // Voice actions (Leo)
  const handleSaveVoice = async () => {
    if (!voiceSettings) return;
    setIsVoiceSaving(true);
    setVoiceNotice(null);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch("/api/workspace/agent-settings/voice", {
        method: "PUT",
        headers,
        body: JSON.stringify({
          narration_mode: voiceSettings.narration_mode,
          selected_voice: voiceSettings.selected_voice,
          language: voiceSettings.language,
          my_voice: voiceSettings.my_voice,
        }),
      });
      if (!res.ok) throw new Error("Failed to save voice configuration");
      const updated: VoiceSettingsConfig = await res.json();
      setVoiceSettings(updated);
      setVoiceNotice("Voice settings saved");
      setTimeout(() => setVoiceNotice(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save voice settings");
    } finally {
      setIsVoiceSaving(false);
    }
  };

  const handlePreviewVoice = async (voiceName: string) => {
    if (activeAudioRef.current) {
      activeAudioRef.current.pause();
      activeAudioRef.current = null;
    }
    setIsPlayingAudio(true);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch("/api/workspace/agent-settings/voice/sample", {
        method: "POST",
        headers,
        body: JSON.stringify({
          voice_id: voiceName,
          sample_text: `Hi, I'm ${voiceName}. I can narrate your video with clean pacing and emphasis.`,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.audio_base64) {
          const audio = new Audio(`data:audio/mp3;base64,${data.audio_base64}`);
          activeAudioRef.current = audio;
          audio.onended = () => {
            setIsPlayingAudio(false);
            activeAudioRef.current = null;
          };
          audio.onerror = () => {
            setIsPlayingAudio(false);
            activeAudioRef.current = null;
          };
          await audio.play();
          return;
        }
      }
      setIsPlayingAudio(false);
    } catch {
      setIsPlayingAudio(false);
    }
  };

  if (!isOpen) return null;

  // Filter memories by search query
  const filteredMemories = memories.filter((m) => {
    if (!memorySearchQuery.trim()) return true;
    const q = memorySearchQuery.toLowerCase();
    return (
      m.fact.toLowerCase().includes(q) ||
      m.provenance?.toLowerCase().includes(q) ||
      (m.scope && Object.values(m.scope).some((v) => v.toLowerCase().includes(q)))
    );
  });

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm transition-opacity animate-in fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="agent-settings-title"
      data-testid="agent-settings-drawer"
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
              <h2 id="agent-settings-title" className="text-base font-semibold text-text-primary">
                {agent.name} settings
              </h2>
              <p className="text-xs text-text-muted">{agent.role}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-text-muted transition-colors hover:bg-surface-2 hover:text-text-primary cursor-pointer"
            aria-label="Close"
            data-testid="btn-close-settings"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-border-subtle px-6 pt-2">
          <button
            type="button"
            onClick={() => setActiveTab("prompt")}
            className={`border-b-2 px-4 py-2.5 text-xs font-semibold transition-colors cursor-pointer ${
              activeTab === "prompt"
                ? "border-primary text-text-primary"
                : "border-transparent text-text-muted hover:text-text-secondary"
            }`}
            data-testid="tab-prompt"
          >
            Prompt
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("memory")}
            className={`border-b-2 px-4 py-2.5 text-xs font-semibold transition-colors cursor-pointer ${
              activeTab === "memory"
                ? "border-primary text-text-primary"
                : "border-transparent text-text-muted hover:text-text-secondary"
            }`}
            data-testid="tab-memory"
          >
            Memory
          </button>

          {agentId === "alex" && (
            <button
              type="button"
              onClick={() => setActiveTab("research")}
              className={`border-b-2 px-4 py-2.5 text-xs font-semibold transition-colors cursor-pointer ${
                activeTab === "research"
                  ? "border-primary text-text-primary"
                  : "border-transparent text-text-muted hover:text-text-secondary"
              }`}
              data-testid="tab-research"
            >
              Research
            </button>
          )}

          {agentId === "leo" && (
            <button
              type="button"
              onClick={() => setActiveTab("voice")}
              className={`border-b-2 px-4 py-2.5 text-xs font-semibold transition-colors cursor-pointer ${
                activeTab === "voice"
                  ? "border-primary text-text-primary"
                  : "border-transparent text-text-muted hover:text-text-secondary"
              }`}
              data-testid="tab-voice"
            >
              Voice
            </button>
          )}
        </div>

        {/* Error / Notice Banners */}
        {error && (
          <div className="mx-6 mt-4 flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2.5 text-xs text-red-400">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {isLoading && memories.length === 0 && !promptText ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : (
            <>
              {/* TAB 1: PROMPT */}
              {activeTab === "prompt" && (
                <div className="space-y-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-text-primary">Working prompt</h3>
                      <p className="text-xs text-text-muted">
                        Fully editable. Internal analysis tools remain hidden.
                      </p>
                    </div>
                    {promptNotice && (
                      <span className="text-xs font-medium text-emerald-400 animate-in fade-in">
                        {promptNotice}
                      </span>
                    )}
                  </div>

                  <textarea
                    value={promptText}
                    onChange={(e) => setPromptText(e.target.value)}
                    rows={15}
                    className="w-full rounded-xl border border-border-subtle bg-surface-2 p-4 font-mono text-xs text-text-primary outline-none focus:border-primary transition-colors resize-y leading-relaxed"
                    placeholder="Enter agent working prompt..."
                    data-testid="agent-prompt-textarea"
                  />

                  <div className="flex items-center justify-between pt-2">
                    <button
                      type="button"
                      onClick={handleResetPrompt}
                      disabled={isPromptSaving}
                      className="flex items-center gap-2 rounded-lg border border-border-subtle bg-surface-2 px-3.5 py-2 text-xs font-medium text-text-secondary hover:bg-surface-3 hover:text-text-primary transition-colors cursor-pointer disabled:opacity-50"
                      data-testid="btn-reset-prompt"
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                      <span>Reset to default</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleSavePrompt}
                      disabled={isPromptSaving}
                      className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-white hover:bg-primary-hover transition-colors cursor-pointer disabled:opacity-50"
                      data-testid="btn-save-prompt"
                    >
                      {isPromptSaving ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Save className="h-3.5 w-3.5" />
                      )}
                      <span>Save</span>
                    </button>
                  </div>
                </div>
              )}

              {/* TAB 2: MEMORY (Google Agent Platform Memory Bank) */}
              {activeTab === "memory" && (
                <div className="space-y-5" data-testid="settings-memory-view">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-text-primary">Memory Bank</h3>
                      <p className="text-xs text-text-muted">
                        Canonical long-term knowledge and lessons retrieved during {agent.name}{" "}
                        runtime.
                      </p>
                    </div>
                    {memoryNotice && (
                      <span className="text-xs font-medium text-emerald-400 animate-in fade-in">
                        {memoryNotice}
                      </span>
                    )}
                  </div>

                  {/* Search and Add Bar */}
                  <div className="flex items-center gap-3">
                    <div className="relative flex-1">
                      <Search className="absolute left-3 top-2.5 h-4 w-4 text-text-muted" />
                      <input
                        type="text"
                        value={memorySearchQuery}
                        onChange={(e) => setMemorySearchQuery(e.target.value)}
                        placeholder="Search Memory Bank..."
                        className="w-full rounded-lg border border-border-subtle bg-surface-2 py-2 pl-9 pr-3 text-xs text-text-primary outline-none focus:border-primary transition-colors"
                        data-testid="input-memory-search"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => setIsAddingMemory((prev) => !prev)}
                      className="flex items-center gap-1.5 rounded-lg bg-surface-2 px-3 py-2 text-xs font-medium text-text-primary hover:bg-surface-3 border border-border-subtle transition-colors cursor-pointer"
                      data-testid="btn-add-memory-toggle"
                    >
                      <Plus className="h-3.5 w-3.5 text-primary" />
                      <span>Add memory</span>
                    </button>
                  </div>

                  {/* Inline Add Memory Form */}
                  {isAddingMemory && (
                    <div className="rounded-xl border border-primary/30 bg-surface-2/80 p-4 space-y-3 animate-in fade-in">
                      <h4 className="text-xs font-semibold text-text-primary">
                        Add New Memory Fact
                      </h4>
                      <textarea
                        value={newMemoryText}
                        onChange={(e) => setNewMemoryText(e.target.value)}
                        rows={3}
                        placeholder="e.g. Use subtle background music during technical walkthroughs."
                        className="w-full rounded-lg border border-border-subtle bg-surface-1 p-3 text-xs text-text-primary outline-none focus:border-primary transition-colors"
                        data-testid="textarea-new-memory"
                      />
                      <input
                        type="text"
                        value={newMemoryProvenance}
                        onChange={(e) => setNewMemoryProvenance(e.target.value)}
                        placeholder="Provenance (optional, e.g. Creator instruction, cohort test)"
                        className="w-full rounded-lg border border-border-subtle bg-surface-1 px-3 py-2 text-xs text-text-primary outline-none focus:border-primary transition-colors"
                        data-testid="input-new-memory-provenance"
                      />
                      <div className="flex items-center justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setIsAddingMemory(false)}
                          className="rounded-lg px-3 py-1.5 text-xs text-text-muted hover:text-text-primary transition-colors cursor-pointer"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={handleAddMemory}
                          disabled={!newMemoryText.trim()}
                          className="rounded-lg bg-primary px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-primary-hover transition-colors cursor-pointer disabled:opacity-50"
                          data-testid="btn-save-new-memory"
                        >
                          Save Memory
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Memory Cards */}
                  <div className="space-y-3 pt-2">
                    {filteredMemories.length === 0 ? (
                      <div className="rounded-xl border border-border-subtle bg-surface-2/40 p-8 text-center text-xs text-text-muted">
                        {memorySearchQuery
                          ? "No matching memories found in Memory Bank."
                          : "No memories recorded yet."}
                      </div>
                    ) : (
                      filteredMemories.map((mem) => {
                        const isConfirmingDelete =
                          deletingMemoryId === mem.memory_id || deletingMemoryId === mem.name;
                        return (
                          <div
                            key={mem.memory_id || mem.name}
                            className="group relative rounded-xl border border-border-subtle bg-surface-2/60 p-4 text-xs space-y-2.5 transition-colors hover:border-border-strong hover:bg-surface-2"
                            data-testid="memory-card"
                          >
                            <div className="flex items-start justify-between gap-4">
                              <p className="font-medium leading-relaxed text-text-primary whitespace-pre-wrap flex-1">
                                {mem.fact}
                              </p>
                              {!isConfirmingDelete && (
                                <button
                                  type="button"
                                  onClick={() => setDeletingMemoryId(mem.memory_id || mem.name)}
                                  className="rounded-lg p-1 text-text-muted hover:bg-surface-3 hover:text-red-400 transition-colors cursor-pointer opacity-0 group-hover:opacity-100 focus:opacity-100"
                                  title="Delete memory"
                                  aria-label="Delete memory"
                                  data-testid="btn-delete-memory"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              )}
                            </div>

                            {/* Metadata and Provenance */}
                            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-text-muted pt-1 border-t border-border-subtle/50">
                              {mem.provenance && (
                                <span>
                                  <span className="text-text-secondary">Source: </span>
                                  {mem.provenance}
                                </span>
                              )}
                              {mem.updated_at && (
                                <span>
                                  Updated{" "}
                                  {new Date(mem.updated_at).toLocaleDateString(undefined, {
                                    month: "short",
                                    day: "numeric",
                                    year: "numeric",
                                  })}
                                </span>
                              )}
                              {mem.scope?.channel_id && (
                                <span className="rounded bg-surface-3 px-1.5 py-0.5 text-[10px] font-mono text-text-secondary">
                                  {mem.scope.channel_id}
                                </span>
                              )}
                            </div>

                            {/* Delete Confirmation Prompt */}
                            {isConfirmingDelete && (
                              <div className="mt-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs space-y-2 animate-in fade-in">
                                <p className="font-semibold text-red-300">
                                  Delete this memory from Google Memory Bank?
                                </p>
                                <div className="flex items-center gap-2">
                                  <button
                                    type="button"
                                    onClick={() => handleDeleteMemory(mem.name || mem.memory_id)}
                                    disabled={isDeleting}
                                    className="rounded bg-red-600 px-3 py-1 text-xs font-semibold text-white hover:bg-red-500 transition-colors cursor-pointer disabled:opacity-50"
                                    data-testid="btn-confirm-delete-memory"
                                  >
                                    {isDeleting ? "Deleting..." : "Delete"}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => setDeletingMemoryId(null)}
                                    className="rounded bg-surface-3 px-3 py-1 text-xs font-medium text-text-primary hover:bg-elevated transition-colors cursor-pointer"
                                  >
                                    Cancel
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              )}

              {/* TAB 3: RESEARCH (Alex only) */}
              {activeTab === "research" && research && (
                <div className="space-y-6">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-text-primary">
                        Background research
                      </h3>
                      <p className="text-xs text-text-muted">
                        Runs while you are away. Findings require public, grounded citations.
                      </p>
                    </div>
                    {researchNotice && (
                      <span className="text-xs font-medium text-emerald-400 animate-in fade-in">
                        {researchNotice}
                      </span>
                    )}
                  </div>

                  {/* Schedule */}
                  <div className="space-y-2">
                    <label className="block text-xs font-semibold text-text-primary">
                      Schedule
                    </label>
                    <select
                      value={research.cadence}
                      onChange={(e) =>
                        setResearch((cur) =>
                          cur ? { ...cur, cadence: e.target.value as ResearchCadence } : cur,
                        )
                      }
                      className="w-full rounded-xl border border-border-subtle bg-surface-2 px-4 py-2.5 text-xs text-text-primary outline-none focus:border-primary transition-colors cursor-pointer"
                      data-testid="select-research-cadence"
                    >
                      {CADENCES.map((c) => (
                        <option key={c.value} value={c.value}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Enabled Toggle & Autonomous Intelligence Policy */}
                  <div className="space-y-4">
                    <label className="flex items-center gap-2.5 text-xs font-semibold text-text-primary cursor-pointer">
                      <input
                        type="checkbox"
                        checked={research.enabled}
                        onChange={(e) =>
                          setResearch((cur) => (cur ? { ...cur, enabled: e.target.checked } : cur))
                        }
                        className="rounded border-border-subtle bg-surface-2 text-primary focus:ring-primary"
                        data-testid="checkbox-research-enabled"
                      />
                      <span>Enable autonomous research runs</span>
                    </label>
                    {/* How Alex Researches explanation */}
                    <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 text-xs space-y-2">
                      <div className="font-semibold text-text-primary flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-primary" />
                        <span>Channel-Driven Autonomous Intelligence</span>
                      </div>
                      <p className="text-text-secondary leading-relaxed">
                        Alex does not require manual search prompts. Alex dynamically constructs
                        deep research plans from your canonical Working Prompt, Channel Memory Bank,
                        recent video catalog, and retention baselines, grounded with Gemini 3.7
                        Flash and real Google Search.
                      </p>
                    </div>

                    {/* Broad Web Search Option */}
                    <label className="flex items-center gap-2 text-xs text-text-secondary cursor-pointer">
                      <input
                        type="checkbox"
                        checked={research.prompts?.[0]?.use_broad_web_search ?? true}
                        onChange={(e) => {
                          const currentSources = research.prompts?.[0]?.preferred_sources || [];
                          const updatedPrompts = [
                            {
                              prompt_id:
                                research.prompts?.[0]?.prompt_id || "autonomous_channel_research",
                              text:
                                research.prompts?.[0]?.text ||
                                "Autonomous channel grounded research",
                              enabled: research.enabled,
                              use_broad_web_search: e.target.checked,
                              preferred_sources: currentSources,
                            },
                          ];
                          setResearch((cur) => (cur ? { ...cur, prompts: updatedPrompts } : cur));
                        }}
                        className="rounded border-border-subtle bg-surface-1 text-primary focus:ring-primary"
                      />
                      <span>Search broader public web (Google Search Grounding)</span>
                    </label>

                    {/* Preferred Sources Policy */}
                    <div className="space-y-2 pt-1">
                      <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">
                        Preferred Public Sources
                      </span>
                      <div className="flex flex-wrap gap-2">
                        {(research.prompts?.[0]?.preferred_sources || []).map((src) => (
                          <span
                            key={src}
                            className="flex items-center gap-1.5 rounded-lg border border-border-subtle bg-surface-1 px-2.5 py-1 text-xs text-text-primary"
                            data-testid={`source-chip-${src}`}
                          >
                            <ExternalLink className="h-3 w-3 text-text-muted shrink-0" />
                            <span className="truncate max-w-[200px]">{src}</span>
                            <button
                              type="button"
                              onClick={() => {
                                const currentSources =
                                  research.prompts?.[0]?.preferred_sources || [];
                                const nextSources = currentSources.filter((s) => s !== src);
                                const updatedPrompts = [
                                  {
                                    prompt_id:
                                      research.prompts?.[0]?.prompt_id ||
                                      "autonomous_channel_research",
                                    text:
                                      research.prompts?.[0]?.text ||
                                      "Autonomous channel grounded research",
                                    enabled: research.enabled,
                                    use_broad_web_search:
                                      research.prompts?.[0]?.use_broad_web_search ?? true,
                                    preferred_sources: nextSources,
                                  },
                                ];
                                setResearch((cur) =>
                                  cur ? { ...cur, prompts: updatedPrompts } : cur,
                                );
                              }}
                              className="text-text-muted hover:text-text-primary transition-colors cursor-pointer"
                              aria-label={`Remove source ${src}`}
                              data-testid={`btn-remove-source-${src}`}
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </span>
                        ))}
                      </div>

                      {/* Add Source Input */}
                      <div className="flex items-center gap-2 pt-1">
                        <input
                          type="text"
                          value={newSourceDraft}
                          onChange={(e) => setNewSourceDraft(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              const draft = newSourceDraft.trim();
                              if (!draft) return;
                              const currentSources = research.prompts?.[0]?.preferred_sources || [];
                              if (currentSources.includes(draft)) {
                                setNewSourceDraft("");
                                return;
                              }
                              const nextSources = [...currentSources, draft];
                              const updatedPrompts = [
                                {
                                  prompt_id:
                                    research.prompts?.[0]?.prompt_id ||
                                    "autonomous_channel_research",
                                  text:
                                    research.prompts?.[0]?.text ||
                                    "Autonomous channel grounded research",
                                  enabled: research.enabled,
                                  use_broad_web_search:
                                    research.prompts?.[0]?.use_broad_web_search ?? true,
                                  preferred_sources: nextSources,
                                },
                              ];
                              setResearch((cur) =>
                                cur ? { ...cur, prompts: updatedPrompts } : cur,
                              );
                              setNewSourceDraft("");
                            }
                          }}
                          placeholder="domain or full public URL (e.g. news.ycombinator.com)"
                          className="flex-1 rounded-lg border border-border-subtle bg-surface-1 px-3 py-1.5 text-xs text-text-primary outline-none focus:border-primary transition-colors"
                          data-testid="input-new-source"
                        />
                        <button
                          type="button"
                          onClick={() => {
                            const draft = newSourceDraft.trim();
                            if (!draft) return;
                            const currentSources = research.prompts?.[0]?.preferred_sources || [];
                            if (currentSources.includes(draft)) {
                              setNewSourceDraft("");
                              return;
                            }
                            const nextSources = [...currentSources, draft];
                            const updatedPrompts = [
                              {
                                prompt_id:
                                  research.prompts?.[0]?.prompt_id || "autonomous_channel_research",
                                text:
                                  research.prompts?.[0]?.text ||
                                  "Autonomous channel grounded research",
                                enabled: research.enabled,
                                use_broad_web_search:
                                  research.prompts?.[0]?.use_broad_web_search ?? true,
                                preferred_sources: nextSources,
                              },
                            ];
                            setResearch((cur) => (cur ? { ...cur, prompts: updatedPrompts } : cur));
                            setNewSourceDraft("");
                          }}
                          className="rounded-lg bg-surface-3 p-2 text-text-primary hover:bg-elevated transition-colors cursor-pointer"
                          data-testid="btn-add-source"
                          aria-label="Add source"
                        >
                          <Plus className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="flex justify-end pt-2">
                    <button
                      type="button"
                      onClick={handleSaveResearch}
                      disabled={isResearchSaving}
                      className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-white hover:bg-primary-hover transition-colors cursor-pointer disabled:opacity-50"
                      data-testid="btn-save-research"
                    >
                      {isResearchSaving ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Save className="h-3.5 w-3.5" />
                      )}
                      <span>Save research settings</span>
                    </button>
                  </div>
                </div>
              )}

              {activeTab === "voice" && voiceSettings && (
                <div className="space-y-6" data-testid="settings-voice-view">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-text-primary">
                        Narration & Studio Voice
                      </h3>
                      <p className="text-xs text-text-muted">
                        Configure synthetic voice narration and pacing for dialogue edits.
                      </p>
                    </div>
                    {voiceNotice && (
                      <span className="text-xs font-medium text-emerald-400 animate-in fade-in">
                        {voiceNotice}
                      </span>
                    )}
                  </div>

                  {/* Mode Select */}
                  <div className="space-y-3">
                    <label className="block text-xs font-semibold text-text-primary">
                      Narration Mode
                    </label>
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        {
                          id: "original",
                          label: "Original Audio",
                          desc: "Keep creator's raw vocal track",
                        },
                        {
                          id: "enhanced_original",
                          label: "Enhanced Original",
                          desc: "Denoised and leveled voice",
                        },
                        {
                          id: "studio_voice",
                          label: "Studio Voice",
                          desc: "High-clarity synthetic narration",
                        },
                        {
                          id: "my_voice",
                          label: "My Voice Model",
                          desc: "Custom consented voice clone",
                        },
                      ].map((m) => (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() =>
                            setVoiceSettings((cur: VoiceSettingsConfig | null) =>
                              cur ? { ...cur, narration_mode: m.id as any } : cur,
                            )
                          }
                          data-testid={`voice-mode-${m.id}`}
                          className={`rounded-xl border p-3 text-left transition-colors cursor-pointer ${
                            voiceSettings.narration_mode === m.id
                              ? "border-primary bg-primary/10"
                              : "border-border-subtle bg-surface-2 hover:bg-surface-3"
                          }`}
                        >
                          <span className="block text-xs font-semibold text-text-primary">
                            {m.label}
                          </span>
                          <span className="block text-[11px] text-text-muted mt-0.5">{m.desc}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Voice Picker */}
                  {voiceSettings.narration_mode === "studio_voice" && (
                    <div className="space-y-3" data-testid="voice-selector-dropdown">
                      <label className="block text-xs font-semibold text-text-primary">
                        Select Studio Voice
                      </label>
                      <div className="grid grid-cols-2 gap-2.5">
                        {voices.map((v) => (
                          <div
                            key={v.voice_id}
                            className={`flex items-center justify-between rounded-xl border p-3 transition-colors ${
                              voiceSettings.selected_voice === v.voice_id
                                ? "border-primary bg-primary/10"
                                : "border-border-subtle bg-surface-2"
                            }`}
                          >
                            <div>
                              <span className="block text-xs font-semibold text-text-primary">
                                {v.display_name}
                              </span>
                              <span className="block text-[10px] text-text-muted">
                                {v.gender || "Studio"} · {v.language_code || "en-US"}
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => handlePreviewVoice(v.voice_id)}
                                disabled={isPlayingAudio}
                                data-testid="btn-play-voice-sample"
                                className="rounded-lg p-1.5 text-text-muted hover:bg-surface-3 hover:text-text-primary transition-colors cursor-pointer"
                                title="Preview voice sample"
                              >
                                <Play className="h-3.5 w-3.5" />
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  setVoiceSettings((cur: VoiceSettingsConfig | null) =>
                                    cur ? { ...cur, selected_voice: v.voice_id } : cur,
                                  )
                                }
                                className={`rounded-lg px-2 py-1 text-[11px] font-medium transition-colors cursor-pointer ${
                                  voiceSettings.selected_voice === v.voice_id
                                    ? "bg-primary text-white"
                                    : "bg-surface-3 text-text-secondary hover:text-text-primary"
                                }`}
                              >
                                Select
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex justify-end pt-2">
                    <button
                      type="button"
                      onClick={handleSaveVoice}
                      disabled={isVoiceSaving}
                      className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-white hover:bg-primary-hover transition-colors cursor-pointer disabled:opacity-50"
                      data-testid="btn-save-voice"
                    >
                      {isVoiceSaving ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Save className="h-3.5 w-3.5" />
                      )}
                      <span>Save voice settings</span>
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
