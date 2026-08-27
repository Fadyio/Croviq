import React, { useEffect, useState } from "react";
import {
  X,
  Sparkles,
  RotateCcw,
  Save,
  Volume2,
  Play,
  Pause,
  Brain,
  FileText,
  Check,
  Loader2,
} from "lucide-react";
import leoAvatar from "../../assets/agents/leo.webp";
import mayaAvatar from "../../assets/agents/maya.webp";
import type { components } from "../../api/generated";
import { useAuth } from "../../auth/AuthContext";

type AgentPromptConfig = components["schemas"]["AgentPromptConfig"];
type VoiceSettingsConfig = components["schemas"]["VoiceSettingsConfig"];
type VoiceCatalogItem = components["schemas"]["VoiceCatalogItem"];
type AgentMemorySummaryResponse = components["schemas"]["AgentMemorySummaryResponse"];
type NarrationMode = "original" | "enhanced_original" | "studio_voice";

interface AgentSettingsDrawerProps {
  isOpen: boolean;
  agentId: "leo" | "maya";
  onClose: () => void;
}

const DEFAULT_SAMPLE_TEXT =
  "Welcome to Croviq. I'll make your video clear, concise, and easy to follow.";

export const AgentSettingsDrawer: React.FC<AgentSettingsDrawerProps> = ({
  isOpen,
  agentId,
  onClose,
}) => {
  const { firebaseUser } = useAuth();

  const getAuthHeaders = async (): Promise<Record<string, string>> => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (firebaseUser) {
      const token = await firebaseUser.getIdToken();
      headers.Authorization = `Bearer ${token}`;
    }
    return headers;
  };
  const [activeTab, setActiveTab] = useState<"prompt" | "memory" | "voice">("prompt");
  const [promptText, setPromptText] = useState<string>("");
  const [promptVersion, setPromptVersion] = useState<number>(1);
  const [promptUpdatedAt, setPromptUpdatedAt] = useState<string>("");
  const [isCustomPrompt, setIsCustomPrompt] = useState<boolean>(false);

  const [memorySummary, setMemorySummary] = useState<AgentMemorySummaryResponse | null>(null);
  const [voiceSettings, setVoiceSettings] = useState<VoiceSettingsConfig | null>(null);
  const [voices, setVoices] = useState<VoiceCatalogItem[]>([]);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState<boolean>(false);
  const [audioError, setAudioError] = useState<string | null>(null);

  const isLeo = agentId === "leo";
  const agentName = isLeo ? "Leo" : "Maya";
  const agentRole = isLeo ? "Video Editor" : "Director";
  const avatarSrc = isLeo ? leoAvatar : mayaAvatar;

  // If Maya is selected and tab is voice, reset to prompt tab
  useEffect(() => {
    if (!isLeo && activeTab === "voice") {
      setActiveTab("prompt");
    }
  }, [isLeo, activeTab]);

  // Load agent settings on open
  useEffect(() => {
    if (!isOpen) return;

    const loadSettings = async () => {
      setIsLoading(true);
      try {
        // 1. Load settings (prompts, voice config, voice catalog)
        const headers = await getAuthHeaders();
        const res = await fetch("/api/workspace/agent-settings", { headers });
        if (res.ok) {
          const data = await res.json();
          const p = isLeo ? data.leo_prompt : data.maya_prompt;
          if (p) {
            setPromptText(p.prompt_text);
            setPromptVersion(p.version);
            setPromptUpdatedAt(p.updated_at);
            setIsCustomPrompt(p.is_custom);
          }
          if (data.voice_settings) {
            setVoiceSettings(data.voice_settings);
          }
          if (data.voices) {
            setVoices(data.voices);
          }
        }

        // 2. Load memory
        const memRes = await fetch("/api/workspace/agent-settings/memory", { headers });
        if (memRes.ok) {
          const memData = await memRes.json();
          setMemorySummary(memData);
        }
      } catch (err) {
        console.error("Failed to load agent settings:", err);
      } finally {
        setIsLoading(false);
      }
    };

    loadSettings();
  }, [isOpen, isLeo]);

  const handleSavePrompt = async () => {
    setIsSaving(true);
    setSaveSuccess(false);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/workspace/agent-settings/prompts/${agentId}`, {
        method: "PUT",
        headers,
        body: JSON.stringify({ prompt_text: promptText }),
      });
      if (res.ok) {
        const updated = await res.json();
        setPromptVersion(updated.version);
        setPromptUpdatedAt(updated.updated_at);
        setIsCustomPrompt(true);
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 2500);
      }
    } catch (err) {
      console.error("Failed to save prompt:", err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleResetPrompt = async () => {
    setIsSaving(true);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/workspace/agent-settings/prompts/${agentId}/reset`, {
        method: "POST",
        headers,
      });
      if (res.ok) {
        const resetData = await res.json();
        setPromptText(resetData.prompt_text);
        setPromptVersion(resetData.version);
        setPromptUpdatedAt(resetData.updated_at);
        setIsCustomPrompt(false);
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 2500);
      }
    } catch (err) {
      console.error("Failed to reset prompt:", err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleUpdateVoiceMode = async (mode: NarrationMode) => {
    if (!voiceSettings) return;
    const updated = { ...voiceSettings, narration_mode: mode };
    setVoiceSettings(updated);
    try {
      const headers = await getAuthHeaders();
      await fetch("/api/workspace/agent-settings/voice", {
        method: "PUT",
        headers,
        body: JSON.stringify({
          narration_mode: mode,
          selected_voice: voiceSettings.selected_voice,
          language: voiceSettings.language,
        }),
      });
    } catch (err) {
      console.error("Failed to update voice mode:", err);
    }
  };

  const handleSelectVoice = async (voiceId: string) => {
    if (!voiceSettings) return;
    const updated = { ...voiceSettings, selected_voice: voiceId };
    setVoiceSettings(updated);
    try {
      const headers = await getAuthHeaders();
      await fetch("/api/workspace/agent-settings/voice", {
        method: "PUT",
        headers,
        body: JSON.stringify({
          narration_mode: voiceSettings.narration_mode,
          selected_voice: voiceId,
          language: voiceSettings.language,
        }),
      });
    } catch (err) {
      console.error("Failed to select voice:", err);
    }
  };

  const handlePlayVoiceSample = async () => {
    if (!voiceSettings) return;
    setIsPlayingAudio(true);
    setAudioError(null);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch("/api/workspace/agent-settings/voice/sample", {
        method: "POST",
        headers,
        body: JSON.stringify({
          voice_id: voiceSettings.selected_voice,
          sample_text: DEFAULT_SAMPLE_TEXT,
        }),
      });
      if (res.ok) {
        const sampleData = await res.json();
        // Play synthetic base64 audio
        const audio = new Audio(`data:audio/wav;base64,${sampleData.audio_base64}`);
        audio.onended = () => setIsPlayingAudio(false);
        audio.onerror = () => {
          setIsPlayingAudio(false);
          setAudioError("Audio playback error");
        };
        await audio.play();
      } else {
        setIsPlayingAudio(false);
      }
    } catch (err) {
      setIsPlayingAudio(false);
      setAudioError("Unable to play voice sample");
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-end bg-black/60 backdrop-blur-xs"
      onClick={onClose}
      data-testid="agent-settings-drawer"
    >
      <div
        className="relative flex flex-col w-full max-w-lg h-full bg-surface-1 border-l border-border-strong shadow-2xl text-text-primary overflow-hidden animate-in slide-in-from-right duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drawer Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle bg-surface-2/60">
          <div className="flex items-center gap-3">
            <img
              src={avatarSrc}
              alt={agentName}
              className="size-10 rounded-full object-cover border border-border-strong"
            />
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm tracking-wide text-text-primary">
                  {agentName}
                </span>
                <span className="text-[11px] px-2 py-0.5 rounded bg-surface-3 text-text-secondary font-medium">
                  {agentRole}
                </span>
              </div>
              <span className="text-xs text-text-muted">Agent Settings</span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-md text-text-muted hover:text-text-primary hover:bg-surface-3 transition-colors"
            aria-label="Close"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-border-subtle bg-surface-2/30 px-5">
          <button
            type="button"
            onClick={() => setActiveTab("prompt")}
            className={`flex items-center gap-2 py-3 px-3 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === "prompt"
                ? "border-primary text-text-primary"
                : "border-transparent text-text-muted hover:text-text-secondary"
            }`}
            data-testid="tab-prompt"
          >
            <FileText className="size-3.5" />
            Prompt
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("memory")}
            className={`flex items-center gap-2 py-3 px-3 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === "memory"
                ? "border-primary text-text-primary"
                : "border-transparent text-text-muted hover:text-text-secondary"
            }`}
            data-testid="tab-memory"
          >
            <Brain className="size-3.5" />
            Memory
          </button>
          {isLeo && (
            <button
              type="button"
              onClick={() => setActiveTab("voice")}
              className={`flex items-center gap-2 py-3 px-3 text-xs font-semibold border-b-2 transition-colors ${
                activeTab === "voice"
                  ? "border-primary text-text-primary"
                  : "border-transparent text-text-muted hover:text-text-secondary"
              }`}
              data-testid="tab-voice"
            >
              <Volume2 className="size-3.5" />
              Voice
            </button>
          )}
        </div>

        {/* Tab Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {isLoading ? (
            <div className="flex items-center justify-center h-48 text-text-muted gap-2 text-xs">
              <Loader2 className="size-4 animate-spin" />
              Loading configuration…
            </div>
          ) : activeTab === "prompt" ? (
            /* Prompt Settings Tab */
            <div className="space-y-4" data-testid="settings-prompt-view">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xs font-bold text-text-primary uppercase tracking-wider">
                    {agentName}&apos;s Working Prompt
                  </h3>
                  <p className="text-[11px] text-text-muted mt-0.5">
                    Complete editorial instructions controlling how {agentName} edits.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {isCustomPrompt && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/20 text-primary font-medium">
                      v{promptVersion} Custom
                    </span>
                  )}
                </div>
              </div>

              <textarea
                value={promptText}
                onChange={(e) => setPromptText(e.target.value)}
                rows={14}
                className="w-full rounded-md border border-border-strong bg-surface-2 p-3 text-xs font-mono text-text-primary leading-relaxed focus:border-primary focus:outline-hidden resize-none"
                placeholder="Enter editorial instructions..."
                data-testid="agent-prompt-textarea"
              />

              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={handleResetPrompt}
                  disabled={isSaving || !isCustomPrompt}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-text-muted hover:text-text-primary hover:bg-surface-2 disabled:opacity-40 transition-colors"
                  data-testid="btn-reset-prompt"
                >
                  <RotateCcw className="size-3.5" />
                  Reset to default
                </button>

                <div className="flex items-center gap-2">
                  {saveSuccess && (
                    <span className="flex items-center gap-1 text-[11px] text-emerald-400 font-medium animate-in fade-in duration-150">
                      <Check className="size-3.5" /> Saved
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={handleSavePrompt}
                    disabled={isSaving || !promptText.trim()}
                    className="flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-primary hover:bg-primary/90 text-white text-xs font-semibold disabled:opacity-40 shadow-xs transition-colors"
                    data-testid="btn-save-prompt"
                  >
                    {isSaving ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <Save className="size-3.5" />
                    )}
                    Save Prompt
                  </button>
                </div>
              </div>
            </div>
          ) : activeTab === "memory" ? (
            /* Memory Settings Tab (READ ONLY) */
            <div className="space-y-5" data-testid="settings-memory-view">
              <div>
                <h3 className="text-xs font-bold text-text-primary uppercase tracking-wider">
                  Channel Memory Bank
                </h3>
                <p className="text-[11px] text-text-muted mt-0.5">
                  Read-only lessons, style directives, and preferences learned from previous
                  productions.
                </p>
              </div>

              {memorySummary ? (
                <div className="space-y-4">
                  {/* Style Guidelines */}
                  <div className="p-3 rounded-lg border border-border-subtle bg-surface-2/40 space-y-1">
                    <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider block">
                      Style Guide
                    </span>
                    <p className="text-xs text-text-secondary leading-relaxed">
                      {memorySummary.style_guide}
                    </p>
                  </div>

                  {/* Creator Preferences */}
                  {memorySummary.creator_preferences &&
                    memorySummary.creator_preferences.length > 0 && (
                      <div className="p-3 rounded-lg border border-border-subtle bg-surface-2/40 space-y-2">
                        <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider block">
                          Creator Preferences
                        </span>
                        <ul className="space-y-1.5 text-xs text-text-secondary">
                          {memorySummary.creator_preferences.map((pref, i) => (
                            <li key={i} className="flex items-start gap-2">
                              <span className="size-1 rounded-full bg-primary mt-1.5 shrink-0" />
                              <span>{pref}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                  {/* Learned Lessons */}
                  <div className="space-y-2">
                    <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider block">
                      Learned Editorial Lessons ({memorySummary.lessons?.length || 0})
                    </span>
                    <div className="space-y-2">
                      {(memorySummary.lessons || []).map((item, idx) => (
                        <div
                          key={idx}
                          className="p-3 rounded-lg border border-border-subtle bg-surface-2/50 space-y-1.5"
                        >
                          <div className="text-xs font-semibold text-text-primary">
                            {item.topic}
                          </div>
                          <div className="text-xs text-text-secondary leading-relaxed">
                            {item.content}
                          </div>
                          {item.learned_from && (
                            <div className="text-[10px] text-text-muted">
                              Learned from:{" "}
                              <span className="font-mono text-text-secondary">
                                {item.learned_from}
                              </span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-xs text-text-muted py-6 text-center">
                  No memory bank entries found.
                </div>
              )}
            </div>
          ) : (
            /* Voice Settings Tab (Leo Only) */
            <div className="space-y-6" data-testid="settings-voice-view">
              <div>
                <h3 className="text-xs font-bold text-text-primary uppercase tracking-wider">
                  Narration & Studio Voice
                </h3>
                <p className="text-[11px] text-text-muted mt-0.5">
                  Configure spoken dialogue replacement and preview official Google voices.
                </p>
              </div>

              {/* Narration Mode Selector */}
              <div className="space-y-2.5">
                <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider block">
                  Narration Mode
                </span>
                <div className="space-y-2">
                  {[
                    {
                      id: "original" as NarrationMode,
                      label: "Original Voice",
                      desc: "Keep recorded raw creator microphone audio.",
                    },
                    {
                      id: "enhanced_original" as NarrationMode,
                      label: "Enhanced Original Voice",
                      desc: "Apply deterministic broadcast speech enhancement and loudness mastering.",
                    },
                    {
                      id: "studio_voice" as NarrationMode,
                      label: "Studio Voice",
                      desc: "Replace spoken narration with Studio Voice (Journey F), timed to original speech.",
                    },
                  ].map((mode) => (
                    <label
                      key={mode.id}
                      className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                        voiceSettings?.narration_mode === mode.id
                          ? "bg-primary/10 border-primary/40 ring-1 ring-primary/30"
                          : "bg-surface-2/40 border-border-subtle hover:bg-surface-2"
                      }`}
                    >
                      <input
                        type="radio"
                        name="narration_mode"
                        value={mode.id}
                        checked={voiceSettings?.narration_mode === mode.id}
                        onChange={() => handleUpdateVoiceMode(mode.id)}
                        className="mt-0.5 text-primary focus:ring-primary"
                      />
                      <div>
                        <div className="text-xs font-semibold text-text-primary">{mode.label}</div>
                        <div className="text-[11px] text-text-muted mt-0.5">{mode.desc}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Studio Voice Selection (Active when Studio Voice chosen) */}
              <div className="space-y-3 pt-2 border-t border-border-subtle">
                <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider block">
                  Studio Voice Catalog
                </span>

                <div className="space-y-2">
                  <label className="text-[11px] text-text-secondary block">Voice Selection</label>
                  <select
                    value={voiceSettings?.selected_voice || "en-US-Journey-F"}
                    onChange={(e) => handleSelectVoice(e.target.value)}
                    className="w-full px-3 py-2 rounded-md bg-surface-2 border border-border-strong text-xs text-text-primary focus:border-primary focus:outline-hidden"
                    data-testid="voice-selector-dropdown"
                  >
                    {voices.map((v) => (
                      <option key={v.voice_id} value={v.voice_id}>
                        {v.display_name} ({v.gender})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Audition Voice Sample */}
                <div className="p-3.5 rounded-lg border border-border-subtle bg-surface-2/50 flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <span className="text-xs font-medium text-text-primary block truncate">
                      Audition Voice
                    </span>
                    <span className="text-[11px] text-text-muted block truncate">
                      &quot;{DEFAULT_SAMPLE_TEXT}&quot;
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={handlePlayVoiceSample}
                    disabled={isPlayingAudio}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-surface-3 hover:bg-surface-4 text-text-primary text-xs font-semibold border border-border-strong shrink-0 transition-colors"
                    data-testid="btn-play-voice-sample"
                  >
                    {isPlayingAudio ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <Play className="size-3.5 fill-current" />
                    )}
                    Play Sample
                  </button>
                </div>
                {audioError && <p className="text-[11px] text-rose-400">{audioError}</p>}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
