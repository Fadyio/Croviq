import { AlertCircle, Check, Loader2, Mic, Square, Volume2 } from "lucide-react";
import React, { useCallback, useEffect, useRef, useState } from "react";
import type { components } from "../../api/generated";
import type { MediaOutputStatus } from "../../lib/edl-adapter";

export type VoiceCatalogItem = components["schemas"]["VoiceCatalogItem"];

export const FIXED_VOICE_SAMPLE_TEXT =
  "Let's turn this recording into a clear, polished explanation.";

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
  renderedVoice?: string | null;
  currentVoiceoverVoiceId?: string | null;
  voiceoverStatus?: MediaOutputStatus;
  voiceoverArtifactId?: string | null;
  voiceoverEdlVersion?: number | null;
  currentEdlVersion?: number | null;
  voiceoverScriptVersion?: string | null;
  currentScriptVersion?: string | null;
  voiceoverTrackCount?: number;
  hasPlaybackUrl?: boolean;
  voices?: VoiceCatalogItem[];
  getAuthToken?: () => Promise<string>;
  onSelectVoice: (voiceId: string) => Promise<void>;
  onGenerateVoiceover?: () => Promise<void>;
  isGeneratingVoiceover?: boolean;
  className?: string;
}

export const VoiceSettingsTab: React.FC<VoiceSettingsTabProps> = ({
  selectedVoice,
  renderedVoice,
  currentVoiceoverVoiceId,
  voiceoverStatus = "unavailable",
  voiceoverArtifactId,
  voiceoverEdlVersion,
  currentEdlVersion,
  voiceoverScriptVersion,
  currentScriptVersion,
  voiceoverTrackCount = 0,
  hasPlaybackUrl = false,
  voices = FALLBACK_GEMINI_VOICES,
  getAuthToken,
  onSelectVoice,
  onGenerateVoiceover,
  isGeneratingVoiceover = false,
  className = "",
}) => {
  const [playingVoiceId, setPlayingVoiceId] = useState<string | null>(null);
  const [loadingAuditionVoiceId, setLoadingAuditionVoiceId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [generatingVoiceId, setGeneratingVoiceId] = useState<string | null>(null);
  const [generationStep, setGenerationStep] = useState<string | null>(null);

  const audioCacheRef = useRef<Map<string, string>>(new Map());
  const audioElementRef = useRef<HTMLAudioElement | null>(null);

  const effectiveVoices = voices && voices.length > 0 ? voices : FALLBACK_GEMINI_VOICES;

  const effectiveRenderedVoice = renderedVoice ?? currentVoiceoverVoiceId ?? null;

  // Strict Active in video contract: ALL 8 conditions must hold
  const isVoiceActiveInVideo = (voiceId: string) => {
    const voiceMatches =
      selectedVoice.toLowerCase() === voiceId.toLowerCase() &&
      effectiveRenderedVoice !== null &&
      effectiveRenderedVoice.toLowerCase() === voiceId.toLowerCase();
    const isReady = voiceoverStatus === "ready";
    const hasArtifact = Boolean(voiceoverArtifactId);
    const matchesEdl =
      currentEdlVersion == null ||
      voiceoverEdlVersion == null ||
      voiceoverEdlVersion === currentEdlVersion;
    const matchesScript =
      currentScriptVersion == null ||
      voiceoverScriptVersion == null ||
      voiceoverScriptVersion === currentScriptVersion;
    const hasTracks = voiceoverTrackCount > 0;
    const playbackResolves = Boolean(hasPlaybackUrl);

    return (
      voiceMatches &&
      isReady &&
      hasArtifact &&
      matchesEdl &&
      matchesScript &&
      hasTracks &&
      playbackResolves
    );
  };
  // Stop audio on unmount
  useEffect(() => {
    return () => {
      if (audioElementRef.current) {
        audioElementRef.current.pause();
        audioElementRef.current = null;
      }
    };
  }, []);

  const handleAudition = useCallback(
    async (event: React.MouseEvent, voiceId: string) => {
      event.stopPropagation();
      setErrorMessage(null);

      // Toggle off if already playing
      if (playingVoiceId === voiceId && audioElementRef.current) {
        audioElementRef.current.pause();
        audioElementRef.current = null;
        setPlayingVoiceId(null);
        return;
      }

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
          setErrorMessage("Could not play voice preview sample.");
        };
        setPlayingVoiceId(voiceId);
        audio.play().catch(() => {
          setPlayingVoiceId(null);
        });
        return;
      }

      setLoadingAuditionVoiceId(voiceId);
      try {
        let token = "";
        if (getAuthToken) {
          token = await getAuthToken();
        } else if (
          import.meta.env.DEV ||
          window.location.hostname === "localhost" ||
          window.location.hostname === "127.0.0.1"
        ) {
          token =
            "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIyN2lFQlVNY3U2VG9EWXdwMk9kRUlIQnV3SUEzIiwidXNlcl9pZCI6IjI3aUVCVU1jdTZUb0RZd3AyT2RFSUhCdXdJQTMiLCJlbWFpbCI6ImRlbW9AY3JvdmlxLmFwcCJ9.signature";
        }

        const headers: Record<string, string> = {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        };

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
          setErrorMessage("Could not play voice preview sample.");
        };

        setPlayingVoiceId(voiceId);
        await audio.play();
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Error auditioning voice sample";
        setErrorMessage(msg);
      } finally {
        setLoadingAuditionVoiceId(null);
      }
    },
    [getAuthToken, playingVoiceId],
  );

  const handleSelectAndRegenerate = async (voiceId: string) => {
    if (isGeneratingVoiceover) return;
    setErrorMessage(null);
    setGeneratingVoiceId(voiceId);
    const voiceObj = effectiveVoices.find(
      (v) => v.voice_id.toLowerCase() === voiceId.toLowerCase(),
    );
    const name = voiceObj ? voiceObj.display_name : voiceId;
    setGenerationStep(`Generating ${name} voiceover…`);

    const t1 = setTimeout(() => setGenerationStep("Rendering Voiceover Preview…"), 800);
    try {
      await onSelectVoice(voiceId);
      clearTimeout(t1);
      setGenerationStep(`${name} — Active in video`);
      setTimeout(() => {
        setGenerationStep(null);
        setGeneratingVoiceId(null);
      }, 1500);
    } catch (err: unknown) {
      clearTimeout(t1);
      setGenerationStep(null);
      setGeneratingVoiceId(null);
      const msg =
        err instanceof Error
          ? err.message
          : `Voice generation failed: could not generate ${name} voiceover.`;
      setErrorMessage(msg);
    }
  };

  return (
    <div
      className={`flex flex-col h-full bg-surface-1 overflow-y-auto p-4 space-y-4 font-sans select-none ${className}`}
      data-testid="voice-settings-tab"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-subtle pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-md bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Mic className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-text-primary">Studio Voice</h3>
            <p className="text-[10px] text-text-muted">
              Select a voice for narration and voiceover preview
            </p>
          </div>
        </div>
      </div>

      {/* Progress / Status banner */}
      {(isGeneratingVoiceover || generationStep) && (
        <div
          className="flex items-center gap-2 p-2.5 rounded-lg bg-primary/10 border border-primary/20 text-primary text-xs font-medium animate-pulse"
          data-testid="voice-generating-banner"
        >
          <Loader2 className="w-4 h-4 animate-spin shrink-0" />
          <span>{generationStep || "Generating voiceover…"}</span>
        </div>
      )}

      {/* Error message */}
      {errorMessage && (
        <div
          className="flex items-center gap-2 p-2.5 rounded-lg bg-danger/10 border border-danger/20 text-danger text-xs"
          data-testid="voice-error-banner"
        >
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}
      {effectiveVoices.find((v) => v.voice_id.toLowerCase() === selectedVoice.toLowerCase()) && (() => {
        const selectedVoiceObj = effectiveVoices.find((v) => v.voice_id.toLowerCase() === selectedVoice.toLowerCase())!;
        return (
          <div
            className="p-3 rounded-xl bg-surface-2 border border-border-subtle space-y-2.5"
            data-testid="selected-voice-card"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-text-primary">
                  {selectedVoiceObj.display_name}
                </span>
                <span className="text-[9px] uppercase px-1.5 py-0.2 rounded bg-surface-3 text-text-muted font-mono">
                  {selectedVoiceObj.gender}
                </span>
                <span className="text-[9px] uppercase px-1.5 py-0.2 rounded bg-primary/10 text-primary font-mono font-semibold">
                  Selected
                </span>
                <span data-testid="voiceover-status-badge" className="text-[10px] font-medium text-emerald-400">
                  {voiceoverStatus === "ready" ? "Ready" : voiceoverStatus}
                </span>
              </div>
              <button
                type="button"
                onClick={(e) => handleAudition(e, selectedVoiceObj.voice_id)}
                disabled={loadingAuditionVoiceId === selectedVoiceObj.voice_id}
                className="flex items-center gap-1 px-2 py-1 rounded bg-surface-3 hover:bg-surface-1 text-text-secondary hover:text-text-primary text-[11px] font-medium border border-border-subtle transition-colors cursor-pointer"
                data-testid="btn-play-selected-preview"
                title="Audition sample phrase"
              >
                {playingVoiceId === selectedVoiceObj.voice_id ? (
                  <Square className="w-3 h-3 fill-current" />
                ) : (
                  <Volume2 className="w-3 h-3" />
                )}
                <span>{playingVoiceId === selectedVoiceObj.voice_id ? "Playing…" : "Audition"}</span>
              </button>
            </div>

            <p className="text-[11px] text-text-secondary leading-relaxed italic bg-surface-1/60 p-2 rounded border border-border-subtle/50">
              "{FIXED_VOICE_SAMPLE_TEXT}"
            </p>

            {onGenerateVoiceover && (
              <button
                type="button"
                onClick={() => handleSelectAndRegenerate(selectedVoice)}
                disabled={isGeneratingVoiceover}
                className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-primary hover:bg-primary/90 text-white text-xs font-semibold shadow-xs transition-colors cursor-pointer disabled:opacity-50"
                data-testid="btn-generate-voiceover"
              >
                {isGeneratingVoiceover ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Mic className="w-3.5 h-3.5" />
                )}
                <span>{isGeneratingVoiceover ? "Generating…" : "Regenerate Voiceover"}</span>
              </button>
            )}
          </div>
        );
      })()}

      {effectiveRenderedVoice &&
        selectedVoice &&
        effectiveRenderedVoice.toLowerCase() !== selectedVoice.toLowerCase() && (
          <div
            className="flex items-center gap-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-medium"
            data-testid="voice-stale-banner"
          >
            <AlertCircle className="w-4 h-4 shrink-0 text-amber-400" />
            <span>
              Voiceover currently uses {effectiveRenderedVoice}. Regenerate to use {selectedVoice}.
            </span>
          </div>
        )}

      {voiceoverStatus === "ready" &&
        (!effectiveRenderedVoice ||
          effectiveRenderedVoice.toLowerCase() === selectedVoice.toLowerCase()) && (
          <div
            className="flex items-center gap-2 p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium"
            data-testid="voice-ready-banner"
          >
            <Check className="w-4 h-4 text-emerald-400" />
            <span>Voiceover ready for preview</span>
          </div>
        )}

      {/* 8 Voice List */}
      <div className="space-y-1.5" role="radiogroup" aria-label="Available Studio Voices">
        {effectiveVoices.map((voice) => {
          const isSelected = selectedVoice.toLowerCase() === voice.voice_id.toLowerCase();
          const isActive = isVoiceActiveInVideo(voice.voice_id);
          const isCurrentGenerating = isGeneratingVoiceover && generatingVoiceId === voice.voice_id;
          const isAuditioning = playingVoiceId === voice.voice_id;
          const isAuditionLoading = loadingAuditionVoiceId === voice.voice_id;

          return (
            <div
              key={voice.voice_id}
              onClick={() => handleSelectAndRegenerate(voice.voice_id)}
              className={`flex items-center justify-between p-2.5 rounded-lg border transition-all cursor-pointer ${
                isSelected
                  ? "bg-primary/10 border-primary shadow-xs"
                  : "bg-surface-2 hover:bg-surface-3/70 border-border-subtle hover:border-border-strong"
              }`}
              data-testid={`voice-option-${voice.voice_id.toLowerCase()}`}
              role="radio"
              aria-checked={isSelected}
            >
              <div className="flex items-center gap-3 min-w-0 flex-1">
                {/* Selection Radio / Check Indicator */}
                <div
                  className={`w-4 h-4 rounded-full flex items-center justify-center shrink-0 border transition-all ${
                    isSelected
                      ? "bg-primary border-primary text-white"
                      : "border-border-strong bg-surface-1"
                  }`}
                >
                  {isSelected && <Check className="w-2.5 h-2.5 stroke-[3]" />}
                </div>

                {/* Voice details */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs font-semibold ${
                        isSelected ? "text-primary" : "text-text-primary"
                      }`}
                    >
                      {voice.display_name}
                    </span>
                    <span className="text-[9px] uppercase px-1.5 py-0.2 rounded bg-surface-3 text-text-muted font-mono">
                      {voice.gender}
                    </span>
                    {isActive && (
                      <span
                        className="text-[10px] font-medium text-primary"
                        data-testid={`active-voice-badge-${voice.voice_id.toLowerCase()}`}
                      >
                        (Active in video)
                      </span>
                    )}
                  </div>
                  <p className="text-[10px] text-text-secondary truncate mt-0.5">
                    {voice.description}
                  </p>
                </div>
              </div>

              {/* Action area: Audition Button & Loading */}
              <div className="flex items-center gap-2 shrink-0 ml-2">
                {isCurrentGenerating ? (
                  <div className="flex items-center gap-1 text-[10px] text-primary font-medium">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span>{generationStep || "Generating…"}</span>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={(e) => handleAudition(e, voice.voice_id)}
                    disabled={isAuditionLoading}
                    className={`p-1.5 rounded-md border transition-all cursor-pointer ${
                      isAuditioning
                        ? "bg-primary text-white border-primary"
                        : "bg-surface-3 text-text-secondary hover:text-text-primary hover:bg-surface-1 border-border-subtle"
                    }`}
                    title={`Audition ${voice.display_name} sample`}
                    aria-label={`Audition ${voice.display_name} sample`}
                    data-testid={`btn-audition-${voice.voice_id.toLowerCase()}`}
                  >
                    <span
                      data-testid={`btn-preview-${voice.voice_id.toLowerCase()}`}
                      className="inline-flex items-center justify-center pointer-events-none"
                    >
                      {isAuditionLoading ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : isAuditioning ? (
                        <Square className="w-3.5 h-3.5 fill-current" />
                      ) : (
                        <Volume2 className="w-3.5 h-3.5" />
                      )}
                    </span>
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
