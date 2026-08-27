import React from "react";
import { Film, Video, Sparkles, Smartphone, CheckCircle2, Clock, Layers } from "lucide-react";
import { formatTimecode, formatDuration } from "../../lib/edl-adapter";
import type { PreviewMode } from "./PreviewToggle";

export type MediaAssetId = "original" | "edited" | "studio_voice" | "master" | "short" | string;

export interface MediaBinItem {
  id: MediaAssetId;
  name: string;
  category: "media" | "broll";
  mode: PreviewMode;
  durationMs: number;
  isAvailable: boolean;
  statusText?: string;
}

export interface BRollAssetItem {
  artifactId: string;
  sourceStartMs: number;
  sourceEndMs: number;
  durationMs: number;
  promptSummary: string;
}

interface MediaBinProps {
  currentMode: PreviewMode;
  sourceDurationMs: number;
  editedDurationMs: number;
  hasRenderedPreview: boolean;
  hasMaster: boolean;
  hasStudioVoice: boolean;
  hasShort: boolean;
  brollAssets?: BRollAssetItem[];
  onSelectMode: (mode: PreviewMode) => void;
  onSeek?: (timeMs: number) => void;
  className?: string;
}

export const MediaBin: React.FC<MediaBinProps> = ({
  currentMode,
  sourceDurationMs,
  editedDurationMs,
  hasRenderedPreview,
  hasMaster,
  hasStudioVoice,
  hasShort,
  brollAssets = [],
  onSelectMode,
  onSeek,
  className = "",
}) => {
  const mediaItems: MediaBinItem[] = [
    {
      id: "original",
      name: "Source Video",
      category: "media",
      mode: "original",
      durationMs: sourceDurationMs,
      isAvailable: sourceDurationMs > 0,
      statusText: "Raw",
    },
    {
      id: "edited",
      name: "Edited Preview",
      category: "media",
      mode: "edited",
      durationMs: editedDurationMs || sourceDurationMs,
      isAvailable: true,
      statusText: hasRenderedPreview ? "Rendered" : "Virtual",
    },
    ...(hasStudioVoice
      ? [
          {
            id: "studio_voice",
            name: "Studio Voice",
            category: "media" as const,
            mode: "studio_voice" as PreviewMode,
            durationMs: editedDurationMs || sourceDurationMs,
            isAvailable: true,
            statusText: "Narrated",
          },
        ]
      : []),
    ...(hasMaster
      ? [
          {
            id: "master",
            name: "Master Video",
            category: "media" as const,
            mode: "edited" as PreviewMode,
            durationMs: editedDurationMs || sourceDurationMs,
            isAvailable: true,
            statusText: "Approved",
          },
        ]
      : []),
    ...(hasShort
      ? [
          {
            id: "short",
            name: "Vertical Short",
            category: "media" as const,
            mode: "short" as PreviewMode,
            durationMs: Math.min(60000, Math.max(15000, editedDurationMs)),
            isAvailable: true,
            statusText: "9:16",
          },
        ]
      : []),
  ];

  const getIcon = (item: MediaBinItem) => {
    if (item.mode === "short") return Smartphone;
    if (item.id === "studio_voice") return Sparkles;
    if (item.id === "master") return CheckCircle2;
    if (item.mode === "edited") return Film;
    return Video;
  };

  return (
    <aside
      className={`flex flex-col bg-surface-1 border-r border-border-subtle select-none h-full overflow-hidden ${className}`}
      data-testid="media-bin"
    >
      {/* Panel Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-border-subtle bg-surface-2/40">
        <span className="text-[11px] font-bold tracking-wider text-text-muted uppercase">
          Project Bin
        </span>
        <span className="text-[10px] text-text-muted font-medium">
          {mediaItems.length + brollAssets.length} items
        </span>
      </div>

      {/* Scrollable Bin Rows */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-2 space-y-4">
        {/* Media Section */}
        <div>
          <div className="px-1.5 pb-1.5 text-[10px] font-semibold text-text-muted uppercase tracking-wider">
            Media
          </div>
          <div className="space-y-1">
            {mediaItems.map((item) => {
              const Icon = getIcon(item);
              const isSelected =
                (item.mode === currentMode && item.id !== "master") ||
                (item.id === "studio_voice" && currentMode === "studio_voice") ||
                (item.id === "short" && currentMode === "short");

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSelectMode(item.mode)}
                  className={`w-full flex items-center justify-between gap-2 px-2 py-1.5 rounded text-left transition-colors text-xs ${
                    isSelected
                      ? "bg-primary/15 text-text-primary font-medium border border-primary/30"
                      : "text-text-secondary hover:bg-surface-2 hover:text-text-primary border border-transparent"
                  }`}
                  data-testid={`media-bin-row-${item.id}`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className={`p-1 rounded ${
                        isSelected ? "bg-primary text-white" : "bg-surface-3 text-text-muted"
                      }`}
                    >
                      <Icon className="size-3.5" />
                    </span>
                    <div className="truncate">
                      <div className="truncate text-xs">{item.name}</div>
                      {item.statusText && (
                        <div className="text-[10px] text-text-muted">{item.statusText}</div>
                      )}
                    </div>
                  </div>
                  <div className="text-[10px] text-text-muted font-mono shrink-0">
                    {formatTimecode(item.durationMs)}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Generated B-roll Assets Section (only when B-roll exists) */}
        {brollAssets.length > 0 && (
          <div>
            <div className="px-1.5 pb-1.5 text-[10px] font-semibold text-text-muted uppercase tracking-wider flex items-center justify-between">
              <span>Generated B-Roll</span>
              <span className="text-[10px] text-primary">{brollAssets.length}</span>
            </div>
            <div className="space-y-1">
              {brollAssets.map((asset, idx) => (
                <button
                  key={asset.artifactId || `broll_${idx}`}
                  type="button"
                  onClick={() => onSeek?.(asset.sourceStartMs)}
                  className="w-full flex items-center justify-between gap-2 px-2 py-1.5 rounded text-left transition-colors text-xs text-text-secondary hover:bg-surface-2 hover:text-text-primary border border-transparent"
                  data-testid={`media-bin-broll-${idx}`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="p-1 rounded bg-surface-3 text-primary">
                      <Layers className="size-3.5" />
                    </span>
                    <div className="truncate">
                      <div className="truncate text-xs">
                        {asset.promptSummary || `Coverage #${idx + 1}`}
                      </div>
                      <div className="text-[10px] text-text-muted">
                        At {formatTimecode(asset.sourceStartMs)}
                      </div>
                    </div>
                  </div>
                  <div className="text-[10px] text-text-muted font-mono shrink-0">
                    {formatDuration(asset.durationMs)}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
