import React, { useEffect, useState } from "react";
import {
  X,
  RotateCcw,
  Save,
  Volume2,
  Play,
  Brain,
  Check,
  Loader2,
  AlertCircle,
  Mic,
  ShieldCheck,
} from "lucide-react";
import leoAvatar from "../../assets/agents/leo.webp";
import mayaAvatar from "../../assets/agents/maya.webp";
import ninaAvatar from "../../assets/agents/Nina.png";
import irisAvatar from "../../assets/agents/Iris.png";
import type { components } from "../../api/generated";
import { useAuth } from "../../auth/AuthContext";

type AgentPromptConfig = components["schemas"]["AgentPromptConfig"];
type VoiceSettingsConfig = components["schemas"]["VoiceSettingsConfig"];
type VoiceCatalogItem = components["schemas"]["VoiceCatalogItem"];
type AgentMemorySummaryResponse = components["schemas"]["AgentMemorySummaryResponse"];
type NarrationMode = "original" | "enhanced_original" | "studio_voice" | "my_voice";

interface AgentSettingsDrawerProps {
  isOpen: boolean;
  agentId: "leo" | "maya" | "nina" | "iris";
  onClose: () => void;
}

const DEFAULT_SAMPLE_TEXT =
  "Welcome to Croviq. I'll make your video clear, concise, and easy to follow.";

const GOOGLE_CONSENT_PHRASE =
  "I am the owner of this voice and have consented to the creation of a synthetic model of my voice through the use of Google Cloud.";

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
  const isMaya = agentId === "maya";
  const isNina = agentId === "nina";
  const isIris = agentId === "iris";
  const agentName = isLeo ? "Leo" : isMaya ? "Maya" : isNina ? "Nina" : "Iris";
  const agentRole = isLeo
    ? "Video Editor"
    : isMaya
      ? "Director"
      : isNina
        ? "Packaging Agent"
        : "Quality Assurance Gate";
  const avatarSrc = isLeo ? leoAvatar : isMaya ? mayaAvatar : isNina ? ninaAvatar : irisAvatar;

  // If non-Leo is selected and tab is voice, reset to prompt tab
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
        const headers = await getAuthHeaders();
        const res = await fetch("/api/workspace/agent-settings", { headers });
        if (res.ok) {
          const data = await res.json();
          const p = isLeo ? data.leo_prompt : isMaya ? data.maya_prompt : data.nina_prompt;
          if (p) {
            setPromptText(p.prompt_text || "");
            setPromptVersion(p.version ?? 1);
            setPromptUpdatedAt(p.updated_at || "");
            setIsCustomPrompt(Boolean(p.is_custom));
          }
          if (data.voice_settings) {
            setVoiceSettings(data.voice_settings);
          }
          if (data.voices) {
            setVoices(data.voices);
          }
        }
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
  }, [isOpen, agentId]);

  const handleSavePrompt = async () => {
    setIsSaving(true);
    setSaveSuccess(false);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/workspace/agent-settings/prompt/${agentId}`, {
        method: "PUT",
        headers,
        body: JSON.stringify({ prompt_text: promptText }),
      });
      if (res.ok) {
        const updated: AgentPromptConfig = await res.json();
        setPromptVersion(updated.version ?? 1);
        setPromptUpdatedAt(updated.updated_at);
        setIsCustomPrompt(Boolean(updated.is_custom));
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 2500);
      }
    } catch (err) {
      console.error("Failed to save agent prompt:", err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleResetPrompt = async () => {
    setIsSaving(true);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/workspace/agent-settings/prompt/${agentId}/reset`, {
        method: "POST",
        headers,
      });
      if (res.ok) {
        const updated: AgentPromptConfig = await res.json();
        setPromptVersion(updated.version ?? 1);
        setPromptUpdatedAt(updated.updated_at);
        setIsCustomPrompt(Boolean(updated.is_custom));
        setTimeout(() => setSaveSuccess(false), 2500);
      }
    } catch (err) {
      console.error("Failed to reset agent prompt:", err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleUpdateVoiceMode = async (mode: NarrationMode) => {
    if (!voiceSettings) return;
    setVoiceSettings((prev) => (prev ? { ...prev, narration_mode: mode } : null));
    try {
      const headers = await getAuthHeaders();
      const updated = {
        narration_mode: mode,
        selected_voice: voiceSettings.selected_voice,
        language: voiceSettings.language,
      };
      const res = await fetch("/api/workspace/agent-settings/voice", {
        method: "PUT",
        headers,
        body: JSON.stringify(updated),
      });
      if (res.ok) {
        const data = await res.json();
        if (data && data.narration_mode) {
          setVoiceSettings(data);
        }
      }
    } catch (err) {
      console.error("Failed to update voice mode:", err);
    }
  };

  const handleSelectVoice = async (voiceId: string) => {
    if (!voiceSettings) return;
    setVoiceSettings((prev) => (prev ? { ...prev, selected_voice: voiceId } : null));
    try {
      const headers = await getAuthHeaders();
      const updated = {
        narration_mode: voiceSettings.narration_mode,
        selected_voice: voiceId,
        language: voiceSettings.language,
      };
      const res = await fetch("/api/workspace/agent-settings/voice", {
        method: "PUT",
        headers,
        body: JSON.stringify(updated),
      });
      if (res.ok) {
        const data = await res.json();
        if (data && data.selected_voice) {
          setVoiceSettings(data);
        }
      }
    } catch (err) {
      console.error("Failed to update selected voice:", err);
    }
  };

  const handlePlayVoiceSample = async () => {
    if (!voiceSettings?.selected_voice) return;
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
        const audio = new Audio(`data:audio/wav;base64,${sampleData.audio_base64}`);
        audio.onended = () => setIsPlayingAudio(false);
        audio.onerror = () => {
          setIsPlayingAudio(false);
          setAudioError("Unable to play synthetic preview audio.");
        };
        await audio.play();
      } else {
        throw new Error("Voice sample generation failed");
      }
    } catch (err) {
      setAudioError("Unable to preview voice sample.");
      setIsPlayingAudio(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-xs select-none"
      data-testid="agent-settings-drawer"
    >
      <div className="w-full max-w-xl bg-surface-1 border-l border-border-subtle h-full flex flex-col shadow-2xl overflow-hidden animate-in slide-in-from-right duration-200">
        {/* Drawer Header */}
        <div className="p-4 border-b border-border-subtle bg-surface-2/40 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img
              src={avatarSrc}
              alt={agentName}
              className="size-10 rounded-full object-cover border border-border-strong shadow-xs"
            />
            <div>
              <h2 className="text-sm font-bold text-text-primary tracking-tight">
                {agentName}&apos;s Settings
              </h2>
              <p className="text-xs text-text-muted">{agentRole} &middot; Croviq Core Agent</p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-text-muted hover:text-text-primary hover:bg-surface-3 rounded-md transition-colors"
            title="Close Settings"
            aria-label="Close"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-border-subtle px-4 bg-surface-2/20">
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
            Working Prompt
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
                value={promptText || ""}
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
                    disabled={isSaving || !promptText?.trim()}
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
                          className="p-2.5 rounded-md border border-border-subtle/50 bg-surface-2/30 space-y-1 text-xs"
                        >
                          <span className="font-semibold text-text-primary block">
                            {item.topic}
                          </span>
                          <p className="text-text-secondary">{item.content}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-text-muted">No channel memory profile loaded.</p>
              )}
            </div>
          ) : (
            /* Voice Settings Tab (Leo Only) */
            <div className="space-y-6" data-testid="settings-voice-view">
              <div>
                <h3 className="text-xs font-bold text-text-primary uppercase tracking-wider">
                  Narration & Voice Modes
                </h3>
                <p className="text-[11px] text-text-muted mt-0.5">
                  Configure spoken dialogue replacement, prebuilt Studio Voice, or creator My Voice
                  replication.
                </p>
              </div>

              {/* Narration Mode Selector */}
              <div className="space-y-2.5">
                <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider block">
                  Voice Mode
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
                      label: "Enhanced Original",
                      desc: "Apply broadcast speech enhancement and loudness mastering.",
                    },
                    {
                      id: "studio_voice" as NarrationMode,
                      label: "Studio Voice",
                      desc: "Synthesize clear, paced narration using Google Gemini 3.1 Flash TTS.",
                    },
                    {
                      id: "my_voice" as NarrationMode,
                      label: "My Voice (Preview)",
                      desc: "Replicate your own voice using Gemini 3.1 Flash TTS voice replication (Pre-GA / Allowlist).",
                    },
                  ].map((mode) => (
                    <label
                      key={mode.id}
                      data-testid={`voice-mode-${mode.id}`}
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
                        <div className="text-xs font-semibold text-text-primary flex items-center gap-2">
                          <span>{mode.label}</span>
                          {mode.id === "my_voice" && (
                            <span className="text-[9px] px-1.5 py-0.2 rounded bg-purple-500/20 text-purple-300 font-medium">
                              Vertex Voices Pre-GA
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-text-muted mt-0.5">{mode.desc}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* My Voice Replication Details (When My Voice is selected) */}
              {voiceSettings?.narration_mode === "my_voice" && (
                <div className="space-y-4 pt-3 border-t border-border-subtle bg-purple-950/20 p-4 rounded-xl border border-purple-800/30">
                  <div className="flex items-center gap-2 text-purple-300 text-xs font-bold uppercase tracking-wider">
                    <ShieldCheck className="size-4 text-purple-400" />
                    <span>My Voice Setup & Consent</span>
                  </div>

                  <div className="space-y-3 text-xs text-text-secondary leading-relaxed">
                    <div className="p-3 bg-surface-2/80 rounded-lg border border-border-subtle space-y-1">
                      <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider block">
                        1. Suggested Voice Sample
                      </span>
                      <p className="text-[11px] text-text-muted">
                        Croviq automatically extracts a clean 10–30s speech segment from your
                        uploaded video (LINEAR16, 24 kHz, mono WAV).
                      </p>
                    </div>

                    <div className="p-3 bg-surface-2/80 rounded-lg border border-border-subtle space-y-2">
                      <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider block flex items-center gap-1.5">
                        <Mic className="size-3 text-purple-400" />
                        2. Required Google Consent Recording
                      </span>
                      <p className="text-[11px] text-text-muted">
                        Google requires a separate verified consent recording with the exact phrase:
                      </p>
                      <blockquote className="p-2 rounded bg-surface-3 text-[11px] font-mono text-purple-200 border-l-2 border-purple-500">
                        &quot;{GOOGLE_CONSENT_PHRASE}&quot;
                      </blockquote>
                    </div>

                    <div className="p-2.5 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-center gap-2 text-[11px] text-amber-300">
                      <AlertCircle className="size-4 shrink-0 text-amber-400" />
                      <span>
                        Access Status: Google Gemini-TTS Voice Replication requires project
                        allowlist access. Replicated keys expire after 7 days.
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Studio Voice Selection (Active when Studio Voice chosen) */}
              {voiceSettings?.narration_mode === "studio_voice" && (
                <div className="space-y-3 pt-2 border-t border-border-subtle">
                  <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider block">
                    Studio Voice Catalog
                  </span>

                  <div className="space-y-2">
                    <label className="text-[11px] text-text-secondary block">Voice Selection</label>
                    <select
                      value={voiceSettings?.selected_voice || "Puck"}
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
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
