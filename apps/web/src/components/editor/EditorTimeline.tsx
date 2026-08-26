import React, { useCallback, useEffect, useRef, useState } from "react";
import { ZoomIn, ZoomOut, Maximize, Scissors, Layers, Video } from "lucide-react";
import {
  formatTimecode,
  type TwickTimelineRepresentation,
  type TimelineBlock,
} from "../../lib/edl-adapter";

interface EditorTimelineProps {
  twickData: TwickTimelineRepresentation;
  currentTimeMs: number;
  durationMs: number;
  selectedBlockId: string | null;
  onSelectBlock: (block: TimelineBlock | null) => void;
  onSeek: (targetMs: number) => void;
  isPlaying?: boolean;
  className?: string;
}

export const EditorTimeline: React.FC<EditorTimelineProps> = ({
  twickData,
  currentTimeMs,
  durationMs,
  selectedBlockId,
  onSelectBlock,
  onSeek,
  className = "",
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const trackAreaRef = useRef<HTMLDivElement>(null);

  // Zoom scale: pixels per second (default 8 px/sec for ~120s video in ~1000px, min 4, max 50)
  const [zoomScale, setZoomScale] = useState<number>(10);
  const [isScrubbing, setIsScrubbing] = useState<boolean>(false);

  const totalDurationSec = Math.max(1, durationMs / 1000);
  const timelineContentWidth = Math.max(800, Math.round(totalDurationSec * zoomScale));

  // Calculate pixel position for a given millisecond time
  const msToPixels = useCallback(
    (ms: number) => {
      const sec = ms / 1000;
      return (sec / totalDurationSec) * timelineContentWidth;
    },
    [timelineContentWidth, totalDurationSec],
  );

  // Calculate millisecond time from pixel position
  const pixelsToMs = useCallback(
    (px: number) => {
      const clampedPx = Math.max(0, Math.min(timelineContentWidth, px));
      const ratio = clampedPx / timelineContentWidth;
      return Math.round(ratio * durationMs);
    },
    [durationMs, timelineContentWidth],
  );

  // Auto-fit zoom to available container width
  const handleZoomFit = () => {
    if (trackAreaRef.current) {
      const availableWidth = trackAreaRef.current.clientWidth - 32;
      const fitScale = Math.max(4, Math.min(40, availableWidth / totalDurationSec));
      setZoomScale(fitScale);
    }
  };

  // Zoom In / Out
  const handleZoomIn = () => setZoomScale((z) => Math.min(50, z * 1.3));
  const handleZoomOut = () => setZoomScale((z) => Math.max(4, z / 1.3));

  // Scrubbing & seeking interaction
  const handleScrubStart = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!trackAreaRef.current) return;
    setIsScrubbing(true);
    const rect = trackAreaRef.current.getBoundingClientRect();
    const scrollLeft = trackAreaRef.current.scrollLeft;
    const clickX = e.clientX - rect.left + scrollLeft;
    const targetMs = pixelsToMs(clickX);
    onSeek(targetMs);
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isScrubbing || !trackAreaRef.current) return;
      const rect = trackAreaRef.current.getBoundingClientRect();
      const scrollLeft = trackAreaRef.current.scrollLeft;
      const moveX = e.clientX - rect.left + scrollLeft;
      const targetMs = pixelsToMs(moveX);
      onSeek(targetMs);
    };

    const handleMouseUp = () => {
      if (isScrubbing) {
        setIsScrubbing(false);
      }
    };

    if (isScrubbing) {
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
    }
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isScrubbing, onSeek, pixelsToMs]);

  // Generate ruler tick marks based on zoom level
  const rulerIntervalSec = zoomScale > 20 ? 5 : zoomScale > 10 ? 10 : 15;
  const rulerTicks: number[] = [];
  for (let sec = 0; sec <= totalDurationSec; sec += rulerIntervalSec) {
    rulerTicks.push(sec);
  }

  const playheadPx = msToPixels(currentTimeMs);

  // Group blocks by track
  const sourceBlocks = twickData.blocks.filter((b) => b.trackId === "source-video");
  const dialogueCutBlocks = twickData.blocks.filter((b) => b.trackId === "dialogue-edits");
  const coverageBlocks = twickData.blocks.filter((b) => b.trackId === "coverage");

  return (
    <div
      ref={containerRef}
      className={`flex flex-col bg-surface-1 rounded-xl border border-border-subtle overflow-hidden select-none shadow-md ${className}`}
      data-testid="editor-timeline"
    >
      {/* Timeline Header Bar with Track Labels & Zoom Toolbar */}
      <div className="h-10 px-4 bg-surface-2 border-b border-border-subtle flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-text-primary tracking-tight">Timeline</span>
          <div className="hidden sm:flex items-center gap-2 text-[11px] text-text-muted">
            <span>&middot;</span>
            <span>{twickData.activeCutCount} cuts</span>
            <span>&middot;</span>
            <span>{twickData.coverageMarkerCount} coverage region</span>
          </div>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handleZoomOut}
            className="p-1 text-text-muted hover:text-text-primary hover:bg-surface-3 rounded transition-colors"
            title="Zoom Out"
            aria-label="Zoom Out"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={handleZoomIn}
            className="p-1 text-text-muted hover:text-text-primary hover:bg-surface-3 rounded transition-colors"
            title="Zoom In"
            aria-label="Zoom In"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={handleZoomFit}
            className="p-1 text-text-muted hover:text-text-primary hover:bg-surface-3 rounded transition-colors"
            title="Fit to Width"
            aria-label="Fit to Width"
          >
            <Maximize className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Track Workspace Viewport (Left Track Headers + Right Scrollable Tracks) */}
      <div className="flex flex-1 overflow-hidden min-h-[190px]">
        {/* Left Track Headers Column (Fixed Width 140px) */}
        <div className="w-28 shrink-0 bg-surface-1 border-r border-border-subtle flex flex-col pt-7 z-10">
          <div className="h-12 px-3 flex items-center gap-2 border-b border-border-subtle/40 text-[11px] font-medium text-text-secondary">
            <Video className="w-3.5 h-3.5 text-text-muted shrink-0" />
            <span className="truncate">Source</span>
          </div>

          <div className="h-12 px-3 flex items-center gap-2 border-b border-border-subtle/40 text-[11px] font-medium text-text-secondary">
            <Scissors className="w-3.5 h-3.5 text-primary shrink-0" />
            <span className="truncate">Edits</span>
          </div>

          <div className="h-12 px-3 flex items-center gap-2 text-[11px] font-medium text-text-secondary">
            <Layers className="w-3.5 h-3.5 text-info shrink-0" />
            <span className="truncate">Coverage</span>
          </div>
        </div>

        {/* Right Scrollable Timeline Canvas */}
        <div
          ref={trackAreaRef}
          className="flex-1 overflow-x-auto overflow-y-hidden relative bg-surface-1 cursor-crosshair focus:outline-none"
          onMouseDown={handleScrubStart}
          role="region"
          aria-label="Timeline Tracks Canvas"
          tabIndex={0}
        >
          <div
            className="relative h-full flex flex-col"
            style={{ width: `${timelineContentWidth}px` }}
          >
            {/* 1. Time Ruler Bar (Top 28px) */}
            <div className="h-7 border-b border-border-subtle bg-surface-2/60 relative">
              {rulerTicks.map((tickSec) => {
                const tickPx = msToPixels(tickSec * 1000);
                return (
                  <div
                    key={`tick-${tickSec}`}
                    className="absolute top-0 bottom-0 flex flex-col justify-between pointer-events-none"
                    style={{ left: `${tickPx}px` }}
                  >
                    <span className="text-[10px] font-mono text-text-muted pl-1 select-none">
                      {formatTimecode(tickSec * 1000).substring(0, 5)}
                    </span>
                    <div className="w-px h-1.5 bg-border-strong" />
                  </div>
                );
              })}
            </div>

            {/* 2. Track 1 Content: SOURCE VIDEO (Continuous Bar) */}
            <div className="h-12 border-b border-border-subtle/40 relative flex items-center px-1">
              {sourceBlocks.map((block) => (
                <div
                  key={block.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectBlock(block);
                  }}
                  className="absolute top-1.5 bottom-1.5 left-1 right-1 rounded bg-surface-3 border border-border-strong/60 flex items-center px-3 text-[11px] text-text-muted font-medium cursor-pointer hover:border-primary/40 transition-colors"
                >
                  <span>Continuous Source Recording</span>
                </div>
              ))}
            </div>

            {/* 3. Track 2 Content: DIALOGUE EDITS */}
            <div className="h-12 border-b border-border-subtle/40 relative flex items-center px-1 bg-surface-2/20">
              {dialogueCutBlocks.length === 0 ? (
                <div className="absolute inset-0 flex items-center px-4 text-[11px] text-text-muted pointer-events-none">
                  <span>No dialogue cuts</span>
                </div>
              ) : (
                dialogueCutBlocks.map((cut) => {
                  const leftPx = msToPixels(cut.startMs);
                  const widthPx = Math.max(12, msToPixels(cut.endMs) - leftPx);
                  const isSelected = selectedBlockId === cut.id;

                  return (
                    <div
                      key={cut.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectBlock(cut);
                      }}
                      className={`absolute top-1.5 bottom-1.5 rounded cursor-pointer transition-all flex items-center justify-center px-2 text-[10px] font-mono font-medium truncate ${
                        cut.type === "cut-safe"
                          ? "bg-danger/25 border border-danger/60 text-danger hover:bg-danger/35"
                          : cut.type === "cut-needs-coverage"
                            ? "bg-warning/25 border border-warning/60 text-warning hover:bg-warning/35"
                            : "bg-surface-3 border border-border-strong text-text-muted line-through opacity-60"
                      } ${isSelected ? "ring-2 ring-primary shadow-lg" : ""}`}
                      style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
                      title={`${cut.label}: ${formatTimecode(cut.startMs)} → ${formatTimecode(cut.endMs)}`}
                    >
                      <span className="truncate">{cut.label}</span>
                    </div>
                  );
                })
              )}
            </div>

            {/* 4. Track 3 Content: COVERAGE */}
            <div className="h-12 relative flex items-center px-1">
              {coverageBlocks.map((cov) => {
                const leftPx = msToPixels(cov.startMs);
                const widthPx = Math.max(16, msToPixels(cov.endMs) - leftPx);
                const isSelected = selectedBlockId === cov.id;
                const isCurrentActive = currentTimeMs >= cov.startMs && currentTimeMs <= cov.endMs;

                return (
                  <div
                    key={cov.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectBlock(cov);
                    }}
                    className={`absolute top-1.5 bottom-1.5 rounded cursor-pointer transition-all flex items-center gap-1.5 px-2.5 text-[11px] font-medium ${
                      cov.type === "coverage-broll"
                        ? "bg-info/20 border border-info/60 text-info hover:bg-info/30"
                        : "bg-surface-3 border border-border-strong text-text-secondary hover:bg-surface-3/80"
                    } ${isSelected ? "ring-2 ring-primary shadow-lg" : ""} ${
                      isCurrentActive ? "ring-1 ring-info animate-pulse" : ""
                    }`}
                    style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
                    title={`Coverage: ${cov.label} (${formatTimecode(cov.startMs)} → ${formatTimecode(cov.endMs)})`}
                  >
                    <Layers className="w-3 h-3 shrink-0" />
                    <span className="truncate font-semibold">{cov.label}</span>
                    <span className="hidden md:inline text-[10px] text-text-muted font-mono shrink-0">
                      ({((cov.endMs - cov.startMs) / 1000).toFixed(1)}s)
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Canonical Playhead Line across all tracks */}
            <div
              className="absolute top-0 bottom-0 w-0.5 bg-primary z-20 pointer-events-none transition-[left] duration-75 shadow-sm"
              style={{ left: `${playheadPx}px` }}
            >
              {/* Playhead Handle Needle */}
              <div className="w-3.5 h-3.5 bg-primary text-white rounded-sm -translate-x-[6px] -translate-y-1 rotate-45 flex items-center justify-center shadow-md" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
