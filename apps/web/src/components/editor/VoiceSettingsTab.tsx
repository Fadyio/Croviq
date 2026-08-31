import {
  AlertCircle,
  Check,
  CheckCircle2,
  Globe,
  Loader2,
  Mic,
  Play,
  RefreshCw,
  Square,
  User,
  Volume2,
  Zap,
} from "lucide-react";
import React, { useCallback, useEffect, useRef, useState } from "react";
import type { components } from "../../api/generated";

export type VoiceCatalogItem = components["schemas"]["VoiceCatalogItem"];

export const FIXED_VOICE_SAMPLE_TEXT =
  "Let's turn this recording into a clear, polished explanation.";

// Pre-seeded fallback voice catalog matching official Google Gemini TTS voices
export const FALLBACK_GEMINI_VOICES: VoiceCatalogItem[] = [
  {
    voice_id: "Puck",
    display_name: "Puck",
    gender: "male",
    language_code: "en-US",
    description: "Clear, engaging, and dynamic technical presentation voice",
  },
  {
    voice_id: "Charon",
    display_name: "Charon",
    gender: "male",
    language_code: "en-US",
    description: "Authoritative, natural, and steady conversational voice",
  },
  {
    voice_id: "Kore",
    display_name: "Kore",
    gender: "female",
    language_code: "en-US",
    description: "Crisp, friendly, and articulate instructional tone",
  },
  {
    voice_id: "Fenrir",
    display_name: "Fenrir",
    gender: "male",
    language_code: "en-US",
    description: "Deep, resonant, and confident delivery",
  },
  {
    voice_id: "Aoede",
    display_name: "Aoede",
    gender: "female",
    language_code: "en-US",
    description: "Warm, expressive, and natural technical presenter",
  },
  {
    voice_id: "Leda",
    display_name: "Leda",
    gender: "female",
    language_code: "en-US",
    description: "Polished, balanced, and articulate narration voice",
  },
  {
    voice_id: "Orus",
    display_name: "Orus",
    gender: "male",
    language_code: "en-US",
    description: "Direct, calm, and professional presenter",
  },
  {
    voice_id: "Zephyr",
    display_name: "Zephyr",
    gender: "male",
    language_code: "en-US",
    description: "Modern, smooth, and conversational tone",
  },
];

export interface VoiceSettingsTabProps {
  productionId: string;
  selectedVoice: string;
  currentVoiceoverVoiceId?: string | null;
  voiceoverStatus?: "ready" | "generating" | "incomplete" | "stale" | "failed" | "unavailable";
  voices?: VoiceCatalogItem[];
  getAuthToken?: () => Promise<string>;
  onSelectVoice: (voiceId: string) => Promise<void>;
  onGenerateVoiceover: () => Promise<void>;
  isGeneratingVoiceover?: boolean;
  className?: string;
}

export const VoiceSettingsTab: React.FC<VoiceSettingsTabProps> = ({
  selectedVoice,
  currentVoiceoverVoiceId,
  voiceoverStatus = "unavailable",
  voices = FALLBACK_GEMINI_VOICES,
  getAuthToken,
  onSelectVoice,
  onGenerateVoiceover,
  isGeneratingVoiceover = false,
  className = "",
}) => {
  const [playingVoiceId, setPlayingVoiceId] = useState<string | null>(null);
  const [loadingVoiceId, setLoadingVoiceId] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [isSavingVoice, setIsSavingVoice] = useState(false);
  const [generationStage, setGenerationStage] = useState<string | null>(null);

  const audioCacheRef = useRef<Map<string, string>>(new Map());
  const audioElementRef = useRef<HTMLAudioElement | null>(null);

  const effectiveVoices = voices && voices.length > 0 ? voices : FALLBACK_GEMINI_VOICES;
  const currentVoiceMeta =
    effectiveVoices.find((v) => v.voice_id === selectedVoice) || effectiveVoices[0];
  const renderedVoiceMeta = currentVoiceoverVoiceId
    ? effectiveVoices.find((v) => v.voice_id === currentVoiceoverVoiceId) || {
        voice_id: currentVoiceoverVoiceId,
        display_name: currentVoiceoverVoiceId,
        gender: "neutral",
        language_code: "en-US",
        description: "Rendered studio voice",
      }
    : null;

  // Stop audio on unmount
  useEffect(() => {
    return () => {
      if (audioElementRef.current) {
        audioElementRef.current.pause();
        audioElementRef.current = null;
      }
    };
  }, []);

  // Check if current voiceover is stale compared to selected voice
  const isVoiceStale =
    Boolean(currentVoiceoverVoiceId && currentVoiceoverVoiceId !== selectedVoice) ||
    voiceoverStatus === "stale";
  const handlePlayPreview = useCallback(
    async (voiceId: string) => {
      setPreviewError(null);

      // If already playing this voice, stop it
      if (playingVoiceId === voiceId && audioElementRef.current) {
        audioElementRef.current.pause();
        audioElementRef.current = null;
        setPlayingVoiceId(null);
        return;
      }

      // Stop any other active audio
      if (audioElementRef.current) {
        audioElementRef.current.pause();
        audioElementRef.current = null;
        setPlayingVoiceId(null);
      }

      const cachedUrl = audioCacheRef.current.get(voiceId);
      if (cachedUrl) {
        const audio = new Audio(cachedUrl);
        audioElementRef.current = audio;
        audio.onended = () => {
          setPlayingVoiceId(null);
          audioElementRef.current = null;
        };
        audio.onerror = () => {
          setPlayingVoiceId(null);
          audioElementRef.current = null;
          setPreviewError("Could not play cached voice preview.");
        };
        setPlayingVoiceId(voiceId);
        audio.play().catch(() => {
          setPlayingVoiceId(null);
        });
        return;
      }

      setLoadingVoiceId(voiceId);
      try {
        let token = "";
        if (getAuthToken) {
          token = await getAuthToken();
        } else if (import.meta.env.DEV || window.location.hostname === "localhost") {
          token =
            "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIyN2lFQlVNY3U2VG9EWXdwMk9kRUlIQnV3SUEzIiwidXNlcl9pZCI6IjI3aUVCVU1jdTZUb0RZd3AyT2RFSUhCdXdJQTMiLCJlbWFpbCI6ImRlbW9AY3JvdmlxLmFwcCJ9.signature";
        }

        const headers: Record<string, string> = {
          "Content-Type": "application/json",
        };
        if (token) {
          headers.Authorization = `Bearer ${token}`;
        }

        const res = await fetch("/api/workspace/agent-settings/voice/sample", {
          method: "POST",
          headers,
          body: JSON.stringify({
            voice_id: voiceId,
            sample_text: FIXED_VOICE_SAMPLE_TEXT,
          }),
        });

        if (!res.ok) {
          throw new Error(`Failed to load voice audition sample (${res.status})`);
        }

        const data = await res.json();
        const base64Audio = data.audio_base64;
        const contentType = data.content_type || "audio/wav";
        const dataUrl = `data:${contentType};base64,${base64Audio}`;

        audioCacheRef.current.set(voiceId, dataUrl);

        const audio = new Audio(dataUrl);
        audioElementRef.current = audio;
        audio.onended = () => {
          setPlayingVoiceId(null);
          audioElementRef.current = null;
        };
        audio.onerror = () => {
          setPlayingVoiceId(null);
          audioElementRef.current = null;
          setPreviewError("Audio playback error occurred.");
        };

        setPlayingVoiceId(voiceId);
        await audio.play();
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Error auditioning voice sample";
        setPreviewError(msg);
      } finally {
        setLoadingVoiceId(null);
      }
    },
    [getAuthToken, playingVoiceId],
  );

  const handleVoiceChange = async (newVoiceId: string) => {
    if (newVoiceId === selectedVoice || isSavingVoice) return;
    setIsSavingVoice(true);
    try {
      await onSelectVoice(newVoiceId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to persist voice selection";
      setPreviewError(msg);
    } finally {
      setIsSavingVoice(false);
    }
  };

  const handleTriggerGenerate = async () => {
    if (isGeneratingVoiceover) return;
    setGenerationStage("Preparing script…");
    try {
      setTimeout(() => setGenerationStage("Generating narration…"), 600);
      setTimeout(() => setGenerationStage("Aligning narration…"), 1400);
      setTimeout(() => setGenerationStage("Rendering preview…"), 2200);
      await onGenerateVoiceover();
      setGenerationStage("Ready");
      setTimeout(() => setGenerationStage(null), 2500);
    } catch {
      setGenerationStage(null);
    }
  };

  return (
    <div
      className={`flex flex-col h-full bg-surface-1 overflow-y-auto p-4 space-y-5 select-none font-sans ${className}`}
      data-testid="voice-settings-tab"
    >
      {/* Header Banner */}
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-md bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <Mic className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-xs font-semibold text-text-primary tracking-tight">
                Voiceover Narration
              </h2>
              <p className="text-[11px] text-text-muted">
                Official Google Gemini 3.1 Flash TTS prebuilt voices
              </p>
            </div>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-surface-2 border border-border-subtle text-text-muted">
            Gemini TTS
          </span>
        </div>
      </div>

      {/* Selected Voice Detail Card */}
      <div
        className="p-3.5 rounded-xl bg-surface-2/60 border border-border-subtle space-y-3 shadow-xs"
        data-testid="selected-voice-card"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="size-7 rounded-full bg-primary/15 text-primary flex items-center justify-center font-bold text-xs">
              {currentVoiceMeta.display_name.charAt(0)}
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-semibold text-text-primary">
                  {currentVoiceMeta.display_name}
                </span>
                <span className="text-[10px] px-1.5 py-0.2 bg-primary/20 text-primary rounded font-mono font-medium">
                  Selected
                </span>
              </div>
              <p className="text-[11px] text-text-secondary line-clamp-1">
                {currentVoiceMeta.description}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => handlePlayPreview(currentVoiceMeta.voice_id)}
            disabled={loadingVoiceId === currentVoiceMeta.voice_id}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all shadow-xs ${
              playingVoiceId === currentVoiceMeta.voice_id
                ? "bg-danger text-white hover:bg-danger/90"
                : "bg-surface-3 hover:bg-surface-2 text-text-primary border border-border-subtle"
            }`}
            data-testid="btn-play-selected-preview"
            title={`Audition sample with ${currentVoiceMeta.display_name}`}
            aria-label={`Audition sample with ${currentVoiceMeta.display_name}`}
          >
            {loadingVoiceId === currentVoiceMeta.voice_id ? (
              <Loader2 className="w-3 h-3 animate-spin text-primary" />
            ) : playingVoiceId === currentVoiceMeta.voice_id ? (
              <>
                <Square className="w-3 h-3 fill-current" />
                <span>Stop</span>
              </>
            ) : (
              <>
                <Play className="w-3 h-3 fill-current" />
                <span>Audition</span>
              </>
            )}
          </button>
        </div>

        {/* Metadata badges */}
        <div className="flex flex-wrap gap-2 text-[10px] text-text-muted pt-1 border-t border-border-subtle/50">
          <div className="flex items-center gap-1">
            <Globe className="w-3 h-3 text-text-muted/70" />
            <span>{currentVoiceMeta.language_code || "en-US"} (English)</span>
          </div>
          <span>&middot;</span>
          <div className="flex items-center gap-1">
            <User className="w-3 h-3 text-text-muted/70" />
            <span className="capitalize">{currentVoiceMeta.gender || "Neutral"}</span>
          </div>
          <span>&middot;</span>
          <div className="flex items-center gap-1">
            <Zap className="w-3 h-3 text-text-muted/70" />
            <span>Provider: Google Cloud</span>
          </div>
        </div>

        {/* Stale Voiceover Warning if voice changed or stale */}
        {isVoiceStale && (
          <div
            className="flex items-start gap-2 p-2.5 rounded-lg bg-warning/10 border border-warning/30 text-warning text-[11px]"
            data-testid="voice-stale-banner"
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <p className="font-semibold">
                Voiceover currently uses{" "}
                {renderedVoiceMeta
                  ? renderedVoiceMeta.display_name
                  : currentVoiceoverVoiceId || "previous voice"}
                .
              </p>
              <p className="text-[10px] text-warning/90">
                Regenerate to use {currentVoiceMeta.display_name}.
              </p>
            </div>
          </div>
        )}

        {/* Ready Voiceover info when voice is in sync */}
        {!isVoiceStale && voiceoverStatus === "ready" && (
          <div
            className="flex items-center gap-2 p-2 rounded-lg bg-success/10 border border-success/30 text-success text-[11px]"
            data-testid="voice-ready-banner"
          >
            <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
            <span>Current voiceover uses {currentVoiceMeta.display_name}</span>
          </div>
        )}

        {/* Failed Generation Warning */}
        {voiceoverStatus === "failed" && (
          <div
            className="flex items-center gap-2 p-2 rounded-lg bg-danger/10 border border-danger/20 text-danger text-[11px]"
            data-testid="voice-failed-banner"
          >
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            <span>Voiceover generation failed. Please retry.</span>
          </div>
        )}
      </div>

      {/* Voice Selection Grid */}
      <div className="space-y-2">
        <label className="block text-[11px] font-semibold text-text-primary uppercase tracking-wider">
          Available Voices ({effectiveVoices.length})
        </label>

        <div className="grid grid-cols-1 gap-2" data-testid="voice-options-list">
          {effectiveVoices.map((v) => {
            const isSelected = v.voice_id === selectedVoice;
            const isRendered = v.voice_id === currentVoiceoverVoiceId;
            const isPlaying = playingVoiceId === v.voice_id;
            const isLoading = loadingVoiceId === v.voice_id;

            return (
              <div
                key={v.voice_id}
                onClick={() => handleVoiceChange(v.voice_id)}
                className={`p-2.5 rounded-lg border transition-all cursor-pointer flex items-center justify-between gap-2.5 ${
                  isSelected
                    ? "bg-primary/10 border-primary/60 shadow-xs ring-1 ring-primary/30"
                    : "bg-surface-2/40 border-border-subtle hover:bg-surface-2/80 hover:border-border-strong"
                }`}
                data-testid={`voice-option-${v.voice_id.toLowerCase()}`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <div
                    className={`size-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 ${
                      isSelected ? "bg-primary text-white" : "bg-surface-3 text-text-secondary"
                    }`}
                  >
                    {isSelected ? <Check className="w-3 h-3" /> : v.display_name.charAt(0)}
                  </div>

                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span
                        className={`text-xs font-semibold truncate ${
                          isSelected ? "text-text-primary" : "text-text-secondary"
                        }`}
                      >
                        {v.display_name}
                      </span>
                      <span className="text-[10px] text-text-muted capitalize">({v.gender})</span>
                      {isSelected && (
                        <span className="text-[9px] px-1.5 py-0.2 bg-primary/20 text-primary rounded font-mono font-medium">
                          Selected
                        </span>
                      )}
                      {isRendered && !isSelected && (
                        <span className="text-[9px] px-1.5 py-0.2 bg-surface-3 text-text-muted rounded font-mono font-medium border border-border-subtle">
                          In Video
                        </span>
                      )}
                    </div>
                    <p className="text-[10px] text-text-muted truncate max-w-[210px]">
                      {v.description}
                    </p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handlePlayPreview(v.voice_id);
                  }}
                  disabled={isLoading}
                  className={`p-1.5 rounded-md text-[10px] transition-colors shrink-0 ${
                    isPlaying
                      ? "bg-danger text-white hover:bg-danger/90"
                      : "bg-surface-3 hover:bg-surface-1 text-text-muted hover:text-text-primary border border-border-subtle"
                  }`}
                  data-testid={`btn-preview-${v.voice_id.toLowerCase()}`}
                  title={`Audition sample with ${v.display_name}`}
                  aria-label={`Audition sample with ${v.display_name}`}
                >
                  {isLoading ? (
                    <Loader2 className="w-3 h-3 animate-spin text-primary" />
                  ) : isPlaying ? (
                    <Square className="w-3 h-3 fill-current" />
                  ) : (
                    <Volume2 className="w-3 h-3" />
                  )}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Preview Sample Sentence Box */}
      <div className="p-2.5 rounded-lg bg-surface-2/30 border border-border-subtle/70 space-y-1">
        <span className="text-[10px] font-mono text-text-muted uppercase tracking-wide">
          Fixed Audition Phrase:
        </span>
        <p className="text-[11px] text-text-secondary italic">"{FIXED_VOICE_SAMPLE_TEXT}"</p>
      </div>

      {/* Preview Error Message */}
      {previewError && (
        <div className="flex items-center gap-2 p-2 rounded-lg bg-danger/10 border border-danger/20 text-danger text-[11px]">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          <span>{previewError}</span>
        </div>
      )}

      {/* Generation Action Box */}
      <div className="pt-2 border-t border-border-subtle space-y-3">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-text-muted">Voiceover Status:</span>
          <span
            className={`font-semibold capitalize ${
              voiceoverStatus === "ready" && !isVoiceStale
                ? "text-success"
                : voiceoverStatus === "generating"
                  ? "text-primary"
                  : voiceoverStatus === "failed"
                    ? "text-danger"
                    : isVoiceStale
                      ? "text-warning"
                      : "text-text-muted"
            }`}
            data-testid="voiceover-status-badge"
          >
            {voiceoverStatus === "generating"
              ? "Generating…"
              : voiceoverStatus === "failed"
                ? "Failed"
                : voiceoverStatus === "incomplete"
                  ? "Incomplete"
                  : isVoiceStale
                    ? "Stale (Regenerate)"
                    : voiceoverStatus === "ready"
                      ? "Ready"
                      : "Unavailable"}
          </span>
        </div>

        {generationStage && (
          <div className="flex items-center gap-2 p-2 rounded-lg bg-primary/10 border border-primary/20 text-primary text-[11px]">
            <Loader2 className="w-3 h-3 animate-spin shrink-0" />
            <span className="font-medium">{generationStage}</span>
          </div>
        )}

        <button
          type="button"
          onClick={handleTriggerGenerate}
          disabled={isGeneratingVoiceover || isSavingVoice}
          className="w-full py-2.5 px-4 rounded-lg bg-primary hover:bg-primary/90 disabled:opacity-50 text-white font-semibold text-xs transition-all shadow-sm flex items-center justify-center gap-2 cursor-pointer"
          data-testid="btn-generate-voiceover"
        >
          {isGeneratingVoiceover ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>{generationStage || "Generating Full Voiceover…"}</span>
            </>
          ) : voiceoverStatus === "failed" ? (
            <>
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry Voiceover Generation</span>
            </>
          ) : isVoiceStale || voiceoverStatus === "ready" ? (
            <>
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Regenerate Voiceover</span>
            </>
          ) : (
            <>
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Generate Voiceover</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
