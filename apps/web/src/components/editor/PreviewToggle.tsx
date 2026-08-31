import { Film, Loader2, Mic2, Music, Scissors } from "lucide-react";
import React from "react";
import type { CanonicalMediaOutputs } from "../../lib/edl-adapter";

export type PreviewMode = "original" | "edited" | "studio_voice" | "final_mix";

interface PreviewToggleProps {
  mode: PreviewMode;
  onModeChange: (mode: PreviewMode) => void;
  activeCutCount: number;
  hasStudioVoice?: boolean;
  hasFinalMix?: boolean;
  mediaOutputs?: CanonicalMediaOutputs;
  className?: string;
}

export const PreviewToggle: React.FC<PreviewToggleProps> = ({
  mode,
  onModeChange,
  activeCutCount,
  mediaOutputs,
  className = "",
}) => {
  const isEditedGenerating = mediaOutputs?.edited.status === "generating";
  const isVoiceoverGenerating = mediaOutputs?.voiceover.status === "generating";
  const isFinalMixGenerating = mediaOutputs?.final_mix.status === "generating";

  return (
    <div
      className={`inline-flex items-center p-0.5 rounded-lg bg-surface-2 border border-border-subtle ${className}`}
      role="group"
      aria-label="Preview Mode Selection"
    >
      <button
        type="button"
        onClick={() => onModeChange("original")}
        className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
          mode === "original"
            ? "bg-surface-3 text-text-primary shadow-sm border border-border-strong font-semibold"
            : "text-text-secondary hover:text-text-primary hover:bg-surface-3/50 border border-transparent"
        }`}
        aria-pressed={mode === "original"}
        title="Play raw source video continuously without applying cuts"
        data-testid="preview-toggle-original"
      >
        <Film className="w-3.5 h-3.5 text-text-muted" />
        <span>Original</span>
      </button>

      <button
        type="button"
        onClick={() => onModeChange("edited")}
        className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
          mode === "edited"
            ? "bg-primary text-white shadow-sm font-semibold"
            : "text-text-secondary hover:text-text-primary hover:bg-surface-3/50"
        }`}
        aria-pressed={mode === "edited"}
        title="Play with executable dialogue cuts skipped in real time"
        data-testid="preview-toggle-edited"
      >
        {isEditedGenerating ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
        ) : (
          <Scissors
            className={`w-3.5 h-3.5 ${mode === "edited" ? "text-white" : "text-primary"}`}
          />
        )}
        <span>{isEditedGenerating ? "Generating…" : "Edited Preview"}</span>
        {!isEditedGenerating && activeCutCount > 0 && (
          <span
            className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
              mode === "edited"
                ? "bg-white/20 text-white"
                : "bg-primary/10 text-primary border border-primary/20"
            }`}
          >
            {activeCutCount}
          </span>
        )}
      </button>

      <button
        type="button"
        onClick={() => onModeChange("studio_voice")}
        className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
          mode === "studio_voice"
            ? "bg-primary text-white shadow-xs font-semibold"
            : "text-text-secondary hover:text-text-primary hover:bg-surface-3/50"
        }`}
        aria-pressed={mode === "studio_voice"}
        title="Play Voiceover Preview with voice corrections included"
        data-testid="preview-toggle-studio-voice"
      >
        {isVoiceoverGenerating ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
        ) : (
          <Mic2
            className={`w-3.5 h-3.5 ${mode === "studio_voice" ? "text-white" : "text-primary"}`}
          />
        )}
        <span>{isVoiceoverGenerating ? "Generating Voiceover…" : "Voiceover Preview"}</span>
      </button>

      <button
        type="button"
        onClick={() => onModeChange("final_mix")}
        className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
          mode === "final_mix"
            ? "bg-purple-600 text-white shadow-xs font-semibold"
            : "text-text-secondary hover:text-text-primary hover:bg-surface-3/50"
        }`}
        aria-pressed={mode === "final_mix"}
        title="Play Final Mix with voice corrections and background music"
        data-testid="preview-toggle-final-mix"
      >
        {isFinalMixGenerating ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400" />
        ) : (
          <Music
            className={`w-3.5 h-3.5 ${mode === "final_mix" ? "text-white" : "text-purple-400"}`}
          />
        )}
        <span>{isFinalMixGenerating ? "Generating Mix…" : "Final Mix"}</span>
      </button>
    </div>
  );
};
