import { Film, type LucideIcon, Mic2, Music, Video } from "lucide-react";
import React from "react";
import { formatDuration } from "../../lib/edl-adapter";
import type { PreviewMode } from "./PreviewToggle";
export interface BRollAssetItem {
  artifactId: string;
  sourceStartMs: number;
  sourceEndMs: number;
  durationMs: number;
  promptSummary: string;
  status?: string;
  isGenerated?: boolean;
}

interface MediaBinProps {
  currentMode: PreviewMode;
  sourceDurationMs: number;
  editedDurationMs: number;
  studioVoiceDurationMs?: number | null;
  finalMixDurationMs?: number | null;
  masterDurationMs?: number | null;
  hasRenderedPreview: boolean;
  hasStudioVoice: boolean;
  hasFinalMix?: boolean;
  hasMaster?: boolean;
  hasProposalOrEdl?: boolean;
  isRunFailed?: boolean;
  brollAssets?: BRollAssetItem[];
  onSeek?: (timeMs: number) => void;
  onSelectMode: (mode: PreviewMode) => void;
  className?: string;
}

interface ProjectArtifact {
  id: "original" | "edited" | "studio_voice" | "final_mix";
  name: string;
  mode: PreviewMode;
  durationMs: number;
  description: string;
  icon: LucideIcon;
}

const ProjectItem: React.FC<{
  item: ProjectArtifact;
  selected: boolean;
  onSelect: () => void;
}> = ({ item, selected, onSelect }) => {
  const Icon = item.icon;
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full rounded-md border px-2 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary ${
        selected
          ? "border-primary/40 bg-primary/10 text-text-primary"
          : "border-transparent text-text-secondary hover:border-border-subtle hover:bg-surface-2 hover:text-text-primary"
      }`}
      data-testid={`asset-${item.id}`}
      data-asset-type={item.id}
    >
      <div className="flex min-w-0 items-start gap-2">
        <Icon
          className={`mt-0.5 size-3.5 shrink-0 ${selected ? "text-primary" : "text-text-muted"}`}
          aria-hidden="true"
        />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[11px] font-semibold leading-tight">{item.name}</p>
          <p className="mt-0.5 truncate text-[9px] text-text-muted">{item.description}</p>
        </div>
      </div>
      <p className="mt-1.5 pl-5.5 font-mono text-[9px] tabular-nums text-text-muted">
        {item.durationMs > 0 ? formatDuration(item.durationMs) : "Preparing…"}
      </p>
    </button>
  );
};

export const MediaBin: React.FC<MediaBinProps> = ({
  currentMode,
  sourceDurationMs,
  editedDurationMs,
  studioVoiceDurationMs,
  finalMixDurationMs,
  hasRenderedPreview,
  hasStudioVoice,
  hasFinalMix = false,
  onSelectMode,
  className = "",
}) => {
  const source: ProjectArtifact = {
    id: "original",
    name: "Source Video",
    mode: "original",
    durationMs: sourceDurationMs,
    description: "Original recording",
    icon: Video,
  };
  const outputs: ProjectArtifact[] = [
    ...(hasRenderedPreview
      ? [
          {
            id: "edited" as const,
            name: "Edited Preview",
            mode: "edited" as PreviewMode,
            durationMs: editedDurationMs,
            description: "Cuts and visual B-roll",
            icon: Film,
          },
        ]
      : []),
    ...(hasStudioVoice
      ? [
          {
            id: "studio_voice" as const,
            name: "Voiceover Preview",
            mode: "studio_voice" as PreviewMode,
            durationMs: studioVoiceDurationMs || editedDurationMs,
            description: "Voice corrections included",
            icon: Mic2,
          },
        ]
      : []),
    ...(hasFinalMix
      ? [
          {
            id: "final_mix" as const,
            name: "Final Mix",
            mode: "final_mix" as PreviewMode,
            durationMs: finalMixDurationMs || studioVoiceDurationMs || editedDurationMs,
            description: "Voice corrections + B-roll + background music",
            icon: Music,
          },
        ]
      : []),
  ];
  return (
    <aside
      className={`flex h-full flex-col overflow-hidden border-r border-border-subtle bg-surface-1 select-none ${className}`}
      data-testid="project-bin"
    >
      <div className="flex items-center justify-between border-b border-border-subtle bg-surface-2/40 px-3 py-2.5">
        <span className="text-[10px] font-bold tracking-wider text-text-muted">PROJECT</span>
        <span className="font-mono text-[9px] text-text-muted">{1 + outputs.length}</span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
        <section aria-labelledby="source-assets-heading">
          <h2
            id="source-assets-heading"
            className="px-1 pb-1 pt-0.5 text-[9px] font-bold tracking-wider text-text-muted"
          >
            SOURCE
          </h2>
          <ProjectItem
            item={source}
            selected={currentMode === "original"}
            onSelect={() => onSelectMode("original")}
          />
        </section>

        {outputs.length > 0 && (
          <section className="mt-3" aria-labelledby="outputs-heading">
            <h2
              id="outputs-heading"
              className="px-1 pb-1 pt-0.5 text-[9px] font-bold tracking-wider text-text-muted"
            >
              OUTPUTS
            </h2>
            <div className="space-y-1">
              {outputs.map((item) => (
                <ProjectItem
                  key={item.id}
                  item={item}
                  selected={currentMode === item.mode}
                  onSelect={() => onSelectMode(item.mode)}
                />
              ))}
            </div>
          </section>
        )}
      </div>
    </aside>
  );
};
