import React from "react";
import { Scissors, Film } from "lucide-react";

export type PreviewMode = "original" | "edited" | "studio_voice";

interface PreviewToggleProps {
  mode: PreviewMode;
  onModeChange: (mode: PreviewMode) => void;
  activeCutCount: number;
  hasStudioVoice?: boolean;
  className?: string;
}

export const PreviewToggle: React.FC<PreviewToggleProps> = ({
  mode,
  onModeChange,
  activeCutCount,
  hasStudioVoice = false,
  className = "",
}) => {
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
            ? "bg-surface-3 text-text-primary shadow-sm border border-border-strong"
            : "text-text-secondary hover:text-text-primary hover:bg-surface-3/50 border border-transparent"
        }`}
        aria-pressed={mode === "original"}
        title="Play raw source video continuously without applying cuts"
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
      >
        <Scissors className={`w-3.5 h-3.5 ${mode === "edited" ? "text-white" : "text-primary"}`} />
        <span>Edited Preview</span>
        {activeCutCount > 0 && (
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
      {hasStudioVoice && (
        <button
          type="button"
          onClick={() => onModeChange("studio_voice")}
          className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
            mode === "studio_voice"
              ? "bg-primary text-white shadow-xs font-semibold"
              : "text-text-secondary hover:text-text-primary hover:bg-surface-3/50"
          }`}
          aria-pressed={mode === "studio_voice"}
          title="Play Studio Voice narration with ducked ambient audio"
          data-testid="preview-toggle-studio-voice"
        >
          <Film
            className={`w-3.5 h-3.5 ${mode === "studio_voice" ? "text-white" : "text-primary"}`}
          />
          <span>Studio Voice</span>
        </button>
      )}
    </div>
  );
};
