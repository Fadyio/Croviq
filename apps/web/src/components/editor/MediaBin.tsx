import React from "react";
import { Film, Video, Sparkles, CheckCircle2, Layers } from "lucide-react";
import { formatTimecode, formatDuration } from "../../lib/edl-adapter";
import type { PreviewMode } from "./PreviewToggle";

export type MediaAssetId = "original" | "edited" | "studio_voice" | "master" | string;

export interface MediaBinItem {
  id: MediaAssetId;
  name: string;
  category: "source" | "output" | "broll";
  mode: PreviewMode;
  durationMs: number;
  isAvailable: boolean;
  typeLabel: string;
}

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
  masterDurationMs?: number | null;
  hasRenderedPreview: boolean;
  hasMaster: boolean;
  hasStudioVoice: boolean;
  hasProposalOrEdl?: boolean;
  isRunFailed?: boolean;
  brollAssets?: BRollAssetItem[];
  onSelectMode: (mode: PreviewMode) => void;
  onSeek?: (timeMs: number) => void;
  className?: string;
}

export const MediaBin: React.FC<MediaBinProps> = ({
  currentMode,
  sourceDurationMs,
  editedDurationMs,
  studioVoiceDurationMs,
  masterDurationMs,
  hasRenderedPreview,
  hasMaster,
  hasStudioVoice,
  hasProposalOrEdl = false,
  isRunFailed = false,
  brollAssets = [],
  onSelectMode,
  onSeek,
  className = "",
}) => {
  const sourceItem: MediaBinItem = {
    id: "original",
    name: "Source Video",
    category: "source",
    mode: "original",
    durationMs: sourceDurationMs,
    isAvailable: sourceDurationMs > 0,
    typeLabel: "Raw",
  };

  const isEditedAvailable =
    !isRunFailed && (hasRenderedPreview || (Boolean(hasProposalOrEdl) && editedDurationMs > 0));

  const outputItems: MediaBinItem[] = [
    {
      id: "edited",
      name: "Edited Preview",
      category: "output",
      mode: "edited",
      durationMs: isEditedAvailable && editedDurationMs > 0 ? editedDurationMs : 0,
      isAvailable: isEditedAvailable,
      typeLabel: hasRenderedPreview ? "Rendered" : "EDL",
    },
    ...(hasStudioVoice && !isRunFailed
      ? [
          {
            id: "studio_voice",
            name: "Studio Voice",
            category: "output" as const,
            mode: "studio_voice" as PreviewMode,
            durationMs: studioVoiceDurationMs || 0,
            isAvailable: Boolean(studioVoiceDurationMs && studioVoiceDurationMs > 0),
            typeLabel: "Narrated",
          },
        ]
      : []),
    ...(hasMaster && !isRunFailed
      ? [
          {
            id: "master",
            name: "Master Video",
            category: "output" as const,
            mode: "edited" as PreviewMode,
            durationMs: masterDurationMs || 0,
            isAvailable: Boolean(masterDurationMs && masterDurationMs > 0),
            typeLabel: "Master",
          },
        ]
      : []),
  ];

  const totalItemCount = 1 + outputItems.length + brollAssets.length;

  const getIcon = (item: MediaBinItem) => {
    if (item.id === "studio_voice") return Sparkles;
    if (item.id === "master") return CheckCircle2;
    if (item.mode === "edited") return Film;
    return Video;
  };

  return (
    <aside
      className={`flex flex-col bg-surface-1 border-r border-border-subtle select-none h-full overflow-hidden ${className}`}
      data-testid="project-bin"
    >
      {/* Panel Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-border-subtle bg-surface-2/40">
        <span className="text-[11px] font-bold tracking-wider text-text-muted uppercase">
          PROJECT
        </span>
        <span className="text-[10px] text-text-muted font-medium font-mono">
          {totalItemCount} items
        </span>
      </div>

      {/* Asset Categories */}
      <div className="flex-1 overflow-y-auto divide-y divide-border-subtle/30">
        {/* SOURCE GROUP */}
        <div className="p-2">
          <p className="px-1.5 py-1 text-[10px] font-bold uppercase tracking-wider text-text-muted">
            SOURCE
          </p>
          <button
            type="button"
            onClick={() => onSelectMode("original")}
            className={`w-full flex items-center justify-between p-2 rounded-lg text-left transition-all ${
              currentMode === "original"
                ? "bg-primary/10 border border-primary/40 text-text-primary shadow-xs"
                : "hover:bg-surface-2 text-text-secondary hover:text-text-primary border border-transparent"
            }`}
            data-testid="asset-source-video"
          >
            <div className="flex items-center gap-2 min-w-0">
              <Video
                className={`w-3.5 h-3.5 shrink-0 ${
                  currentMode === "original" ? "text-primary" : "text-text-muted"
                }`}
              />
              <div className="flex flex-col min-w-0">
                <span className="text-xs font-semibold truncate leading-tight">
                  {sourceItem.name}
                </span>
                <span className="text-[10px] text-text-muted">{sourceItem.typeLabel}</span>
              </div>
            </div>
            <span className="text-[10px] font-mono text-text-muted tabular-nums shrink-0 ml-2">
              {formatDuration(sourceItem.durationMs)}
            </span>
          </button>
        </div>

        {/* OUTPUTS GROUP */}
        <div className="p-2">
          <p className="px-1.5 py-1 text-[10px] font-bold uppercase tracking-wider text-text-muted">
            OUTPUTS
          </p>
          <div className="flex flex-col gap-1">
            {outputItems.map((item) => {
              const Icon = getIcon(item);
              const isSelected =
                item.id === "studio_voice"
                  ? currentMode === "studio_voice"
                  : currentMode === "edited";

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    if (item.isAvailable) onSelectMode(item.mode);
                  }}
                  disabled={!item.isAvailable}
                  className={`w-full flex items-center justify-between p-2 rounded-lg text-left transition-all ${
                    !item.isAvailable
                      ? "opacity-40 cursor-not-allowed border border-transparent text-text-muted"
                      : isSelected
                        ? "bg-primary/10 border border-primary/40 text-text-primary shadow-xs"
                        : "hover:bg-surface-2 text-text-secondary hover:text-text-primary border border-transparent cursor-pointer"
                  }`}
                  data-testid={`asset-${item.id}`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <Icon
                      className={`w-3.5 h-3.5 shrink-0 ${
                        !item.isAvailable
                          ? "text-text-muted"
                          : isSelected
                            ? "text-primary"
                            : "text-text-muted"
                      }`}
                    />
                    <div className="flex flex-col min-w-0">
                      <span className="text-xs font-semibold truncate leading-tight">
                        {item.name}
                      </span>
                      <span className="text-[10px] text-text-muted">{item.typeLabel}</span>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono text-text-muted tabular-nums shrink-0 ml-2">
                    {item.isAvailable && item.durationMs > 0
                      ? formatDuration(item.durationMs)
                      : "--:--"}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* GENERATED B-ROLL GROUP (Rendered when actual video media artifacts exist) */}
        {brollAssets.filter((a) => a.status === "accepted" || a.isGenerated).length > 0 && (
          <div className="p-2">
            <p className="px-1.5 py-1 text-[10px] font-bold uppercase tracking-wider text-text-muted flex items-center justify-between">
              <span>GENERATED B-ROLL</span>
              <span className="text-[9px] px-1.5 py-0.2 bg-success/20 text-success rounded font-medium">
                Ready
              </span>
            </p>
            <div className="flex flex-col gap-1">
              {brollAssets
                .filter((a) => a.status === "accepted" || a.isGenerated)
                .map((asset, idx) => (
                  <div
                    key={asset.artifactId || idx}
                    onClick={() => onSeek?.(asset.sourceStartMs)}
                    className="p-2 rounded-lg border border-info/40 bg-info/10 hover:bg-info/20 cursor-pointer transition-colors flex flex-col gap-1"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-text-primary flex items-center gap-1.5 truncate">
                        <Video className="w-3.5 h-3.5 text-info shrink-0" />
                        <span className="truncate text-[11px]">Generated B-Roll {idx + 1}</span>
                      </span>
                      <span className="text-[10px] font-mono text-text-muted tabular-nums shrink-0">
                        {formatDuration(asset.durationMs)}
                      </span>
                    </div>
                    {asset.promptSummary && (
                      <p className="text-[10px] text-text-secondary line-clamp-2 italic">
                        "{asset.promptSummary}"
                      </p>
                    )}
                    <span className="text-[9px] font-mono text-text-muted">
                      At {formatTimecode(asset.sourceStartMs)}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* B-ROLL PLANS GROUP (Rendered when planning recommendations exist) */}
        {brollAssets.filter(
          (a) => a.status === "planned" || (!a.isGenerated && a.status !== "accepted"),
        ).length > 0 && (
          <div className="p-2">
            <p className="px-1.5 py-1 text-[10px] font-bold uppercase tracking-wider text-text-muted">
              B-ROLL PLANS
            </p>
            <div className="flex flex-col gap-1">
              {brollAssets
                .filter(
                  (a) => a.status === "planned" || (!a.isGenerated && a.status !== "accepted"),
                )
                .map((asset, idx) => (
                  <div
                    key={asset.artifactId || idx}
                    onClick={() => onSeek?.(asset.sourceStartMs)}
                    className="p-2 rounded-lg border border-border-subtle/50 bg-surface-2/30 hover:bg-surface-2 cursor-pointer transition-colors flex flex-col gap-1"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-text-primary flex items-center gap-1.5 truncate">
                        <Layers className="w-3 h-3 text-info shrink-0" />
                        <span className="truncate text-[11px]">B-Roll Plan {idx + 1}</span>
                      </span>
                      <span className="text-[10px] font-mono text-text-muted tabular-nums shrink-0">
                        {formatDuration(asset.durationMs)}
                      </span>
                    </div>
                    {asset.promptSummary && (
                      <p className="text-[10px] text-text-secondary line-clamp-2 italic">
                        "{asset.promptSummary}"
                      </p>
                    )}
                    <span className="text-[9px] font-mono text-text-muted">
                      At {formatTimecode(asset.sourceStartMs)}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
