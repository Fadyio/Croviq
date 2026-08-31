import {
  AlertCircle,
  CheckCircle2,
  Info,
  Loader2,
  Music,
  Play,
  RefreshCw,
  Sliders,
  Square,
  Trash2,
  Volume2,
  VolumeX,
  Zap,
} from "lucide-react";
import React, { useCallback, useEffect, useRef, useState } from "react";
import type { BackgroundMusicMix } from "../../lib/edl-adapter";

export interface MusicTabProps {
  productionId: string;
  backgroundMusic?: BackgroundMusicMix | null;
  musicPlaybackUrl?: string | null;
  onGenerateMusic: (prompt: string, modelId?: string) => Promise<void>;
  onUpdateMusicSettings: (settings: {
    volume_db?: number;
    ducking_db?: number;
    is_muted?: boolean;
    style?: string;
  }) => Promise<void>;
  onRemoveMusic: () => Promise<void>;
  isGenerating?: boolean;
  className?: string;
}

export const DEFAULT_MUSIC_PROMPT =
  "Minimal modern technology documentary underscore, calm, focused, no vocals.";

export const MusicTab: React.FC<MusicTabProps> = ({
  backgroundMusic,
  musicPlaybackUrl,
  onGenerateMusic,
  onUpdateMusicSettings,
  onRemoveMusic,
  isGenerating = false,
  className = "",
}) => {
  const [promptText, setPromptText] = useState<string>(
    backgroundMusic?.prompt || DEFAULT_MUSIC_PROMPT,
  );
  const [modelId, setModelId] = useState<string>(
    backgroundMusic?.model_id || "lyria-3-pro-preview",
  );
  const [isPlayingPreview, setIsPlayingPreview] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isUpdatingSettings, setIsUpdatingSettings] = useState(false);
  const [isRemoving, setIsRemoving] = useState(false);

  const audioElementRef = useRef<HTMLAudioElement | null>(null);

  // Sync prompt when backgroundMusic changes externally
  useEffect(() => {
    if (backgroundMusic?.prompt) {
      setPromptText(backgroundMusic.prompt);
    }
    if (backgroundMusic?.model_id) {
      setModelId(backgroundMusic.model_id);
    }
  }, [backgroundMusic?.prompt, backgroundMusic?.model_id]);

  // Teardown audio on unmount
  useEffect(() => {
    return () => {
      if (audioElementRef.current) {
        audioElementRef.current.pause();
        audioElementRef.current = null;
      }
    };
  }, []);

  const handleTogglePlayPreview = useCallback(() => {
    setErrorMessage(null);

    if (isPlayingPreview && audioElementRef.current) {
      audioElementRef.current.pause();
      setIsPlayingPreview(false);
      return;
    }

    if (!musicPlaybackUrl) {
      setErrorMessage("No music audio playback stream is available for auditioning.");
      return;
    }

    if (!audioElementRef.current) {
      const audio = new Audio(musicPlaybackUrl);
      audioElementRef.current = audio;
      audio.onended = () => {
        setIsPlayingPreview(false);
      };
      audio.onerror = () => {
        setIsPlayingPreview(false);
        setErrorMessage("Playback failed for background music stream.");
      };
    }

    audioElementRef.current.play().then(() => {
      setIsPlayingPreview(true);
    }).catch(() => {
      setIsPlayingPreview(false);
      setErrorMessage("Could not start background music playback.");
    });
  }, [isPlayingPreview, musicPlaybackUrl]);

  const handleGenerate = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (isGenerating || !promptText.trim()) return;
    setErrorMessage(null);

    try {
      await onGenerateMusic(promptText.trim(), modelId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error generating music";
      setErrorMessage(msg);
    }
  };

  const handleVolumeChange = async (val: number) => {
    if (isUpdatingSettings || !backgroundMusic) return;
    setIsUpdatingSettings(true);
    try {
      await onUpdateMusicSettings({ volume_db: val });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error updating volume";
      setErrorMessage(msg);
    } finally {
      setIsUpdatingSettings(false);
    }
  };

  const handleDuckingChange = async (val: number) => {
    if (isUpdatingSettings || !backgroundMusic) return;
    setIsUpdatingSettings(true);
    try {
      await onUpdateMusicSettings({ ducking_db: val });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error updating speech ducking";
      setErrorMessage(msg);
    } finally {
      setIsUpdatingSettings(false);
    }
  };

  const handleToggleMute = async () => {
    if (isUpdatingSettings || !backgroundMusic) return;
    setIsUpdatingSettings(true);
    try {
      await onUpdateMusicSettings({ is_muted: !backgroundMusic.is_muted });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error toggling mute";
      setErrorMessage(msg);
    } finally {
      setIsUpdatingSettings(false);
    }
  };

  const handleRemove = async () => {
    if (isRemoving || !backgroundMusic) return;
    setIsRemoving(true);
    try {
      if (audioElementRef.current) {
        audioElementRef.current.pause();
        audioElementRef.current = null;
        setIsPlayingPreview(false);
      }
      await onRemoveMusic();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error removing music";
      setErrorMessage(msg);
    } finally {
      setIsRemoving(false);
    }
  };

  const hasMusic = Boolean(backgroundMusic);

  return (
    <div
      className={`flex flex-col h-full bg-surface-1 overflow-y-auto p-4 space-y-5 select-none font-sans ${className}`}
      data-testid="music-settings-tab"
    >
      {/* Header */}
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-md bg-purple-500/10 text-purple-400 border border-purple-500/20">
              <Music className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-xs font-semibold text-text-primary tracking-tight">
                Background Music
              </h2>
              <p className="text-[11px] text-text-muted">
                AI instrumental score generated by Google Lyria
              </p>
            </div>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-surface-2 border border-border-subtle text-text-muted">
            Google Lyria
          </span>
        </div>
      </div>

      {/* Mode Truth Informational Callout */}
      <div className="p-3 rounded-lg bg-surface-2/40 border border-border-subtle/80 flex items-start gap-2 text-[11px] text-text-secondary">
        <Info className="w-3.5 h-3.5 text-primary shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <p className="font-semibold text-text-primary">Preview Mode Policy</p>
          <p className="text-[10px] text-text-muted leading-relaxed">
            Background music is only rendered in the <strong>Final Mix</strong> preview. It is
            never audible in Original, Edited, or Voiceover previews.
          </p>
        </div>
      </div>

      {/* Music Prompt Input Form */}
      <form onSubmit={handleGenerate} className="space-y-3">
        <div className="space-y-1.5">
          <label
            htmlFor="music-prompt-input"
            className="block text-[11px] font-semibold text-text-primary uppercase tracking-wider"
          >
            Describe the music you want
          </label>
          <textarea
            id="music-prompt-input"
            rows={3}
            value={promptText}
            onChange={(e) => setPromptText(e.target.value)}
            placeholder={DEFAULT_MUSIC_PROMPT}
            className="w-full px-3 py-2 text-xs bg-surface-2/70 text-text-primary border border-border-subtle rounded-lg focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary resize-none placeholder:text-text-muted/60"
            data-testid="music-prompt-textarea"
          />
        </div>

        {/* Model Selection */}
        <div className="flex items-center justify-between text-xs">
          <label htmlFor="music-model-select" className="text-[11px] text-text-muted">Model:</label>
          <select
            id="music-model-select"
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
            className="bg-surface-2 text-text-primary text-xs px-2.5 py-1 rounded-md border border-border-subtle focus:outline-none focus:ring-1 focus:ring-primary"
            data-testid="music-model-select"
          >
            <option value="lyria-3-pro-preview">Google Lyria 3 Pro (Full Score)</option>
            <option value="lyria-3-clip-preview">Google Lyria 3 Clip (Short Underscore)</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={isGenerating || !promptText.trim()}
          className="w-full py-2 px-3 rounded-lg bg-primary hover:bg-primary/90 disabled:opacity-50 text-white font-semibold text-xs transition-all shadow-xs flex items-center justify-center gap-1.5 cursor-pointer"
          data-testid="btn-generate-music"
        >
          {isGenerating ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Generating Google Lyria Score…</span>
            </>
          ) : hasMusic ? (
            <>
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Regenerate Music</span>
            </>
          ) : (
            <>
              <Zap className="w-3.5 h-3.5" />
              <span>Generate Music</span>
            </>
          )}
        </button>
      </form>

      {/* Error Message */}
      {errorMessage && (
        <div className="flex items-center gap-2 p-2 rounded-lg bg-danger/10 border border-danger/20 text-danger text-[11px]">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Active Music Track Controls */}
      {hasMusic && backgroundMusic && (
        <div
          className="p-3.5 rounded-xl bg-surface-2/60 border border-border-subtle space-y-4 shadow-xs"
          data-testid="active-music-card"
        >
          <div className="flex items-center justify-between border-b border-border-subtle/50 pb-2.5">
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-semibold text-text-primary truncate">
                  {backgroundMusic.style || "AI Underscore"}
                </span>
                {backgroundMusic.is_muted && (
                  <span className="text-[10px] px-1.5 py-0.2 bg-danger/20 text-danger rounded font-mono">
                    Muted
                  </span>
                )}
              </div>
              <p className="text-[10px] text-text-muted truncate">
                Model: {backgroundMusic.model_id || "lyria-3-pro-preview"}
              </p>
            </div>

            {/* Play Preview Audition Control */}
            {musicPlaybackUrl && (
              <button
                type="button"
                onClick={handleTogglePlayPreview}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all shadow-xs ${
                  isPlayingPreview
                    ? "bg-danger text-white hover:bg-danger/90"
                    : "bg-surface-3 hover:bg-surface-2 text-text-primary border border-border-subtle"
                }`}
                data-testid="btn-preview-music"
                title="Audition music track"
              >
                {isPlayingPreview ? (
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
            )}
          </div>

          {/* Volume and Ducking Sliders */}
          <div className="space-y-3">
            {/* Music Bed Volume Slider */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-[11px]">
                <div className="flex items-center gap-1.5 text-text-secondary">
                  <Volume2 className="w-3 h-3 text-text-muted" />
                  <span>Music Bed Volume</span>
                </div>
                <span className="font-mono font-semibold text-text-primary text-[11px]">
                  {backgroundMusic.volume_db.toFixed(1)} dB
                </span>
              </div>
              <input
                type="range"
                min="-40"
                max="0"
                step="0.5"
                value={backgroundMusic.volume_db}
                onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
                disabled={isUpdatingSettings}
                className="w-full h-1.5 bg-surface-3 rounded-lg appearance-none cursor-pointer accent-primary"
                data-testid="slider-music-volume"
              />
            </div>

            {/* Speech Ducking Attenuation Slider */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-[11px]">
                <div className="flex items-center gap-1.5 text-text-secondary">
                  <Sliders className="w-3 h-3 text-text-muted" />
                  <span>Speech Ducking</span>
                </div>
                <span className="font-mono font-semibold text-text-primary text-[11px]">
                  {backgroundMusic.ducking_db.toFixed(1)} dB
                </span>
              </div>
              <input
                type="range"
                min="-24"
                max="0"
                step="0.5"
                value={backgroundMusic.ducking_db}
                onChange={(e) => handleDuckingChange(parseFloat(e.target.value))}
                disabled={isUpdatingSettings}
                className="w-full h-1.5 bg-surface-3 rounded-lg appearance-none cursor-pointer accent-primary"
                data-testid="slider-music-ducking"
              />
            </div>
          </div>

          {/* Action Row: Mute Toggle & Remove Music */}
          <div className="flex items-center justify-between pt-2 border-t border-border-subtle/50">
            <button
              type="button"
              onClick={handleToggleMute}
              disabled={isUpdatingSettings}
              className={`flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md border font-medium transition-colors ${
                backgroundMusic.is_muted
                  ? "bg-danger/15 text-danger border-danger/40 hover:bg-danger/25"
                  : "bg-surface-3 text-text-secondary border-border-subtle hover:text-text-primary hover:bg-surface-2"
              }`}
              data-testid="btn-toggle-music-mute"
            >
              {backgroundMusic.is_muted ? (
                <>
                  <VolumeX className="w-3.5 h-3.5" />
                  <span>Muted</span>
                </>
              ) : (
                <>
                  <Volume2 className="w-3.5 h-3.5" />
                  <span>Mute</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={handleRemove}
              disabled={isRemoving}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md text-danger hover:bg-danger/10 border border-transparent hover:border-danger/30 font-medium transition-colors cursor-pointer"
              data-testid="btn-remove-music"
            >
              {isRemoving ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Trash2 className="w-3.5 h-3.5" />
              )}
              <span>Remove Music</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
