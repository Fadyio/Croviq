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

  const [zoomScale, setZoomScale] = useState<number | null>(null);
  const [isScrubbing, setIsScrubbing] = useState<boolean>(false);
  const [containerWidth, setContainerWidth] = useState<number>(0);
  const totalDurationSec = Math.max(1, durationMs / 1000);

  // Monitor available track width
  useEffect(() => {
    const updateWidth = () => {
      if (trackAreaRef.current) {
        const available = trackAreaRef.current.clientWidth;
        setContainerWidth(available);
      }
    };
    updateWidth();
    window.addEventListener("resize", updateWidth);
    return () => window.removeEventListener("resize", updateWidth);
  }, []);

  // Compute timeline width: auto-fit to container unless user zoomed beyond viewport
  const isOverflowing =
    zoomScale !== null &&
    containerWidth > 0 &&
    Math.round(totalDurationSec * zoomScale) > containerWidth;
  const timelineContentWidth = isOverflowing
    ? Math.round(totalDurationSec * zoomScale)
    : containerWidth || 600;

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

  // Auto-fit zoom to available container width (hides scrollbar)
  const handleZoomFit = () => {
    setZoomScale(null);
  };

  // Zoom In / Out
  const handleZoomIn = () => {
    const currentScale = zoomScale ?? (containerWidth || 600) / totalDurationSec;
    setZoomScale(Math.min(50, currentScale * 1.3));
  };
  const handleZoomOut = () => {
    const currentScale = zoomScale ?? (containerWidth || 600) / totalDurationSec;
    const nextScale = currentScale / 1.3;
    if (containerWidth > 0 && Math.round(totalDurationSec * nextScale) <= containerWidth) {
      setZoomScale(null);
    } else {
      setZoomScale(Math.max(2, nextScale));
    }
  };

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
  const effectiveZoomScale =
    zoomScale ?? (containerWidth > 0 ? containerWidth / totalDurationSec : 6);
  const rulerIntervalSec = effectiveZoomScale > 20 ? 5 : effectiveZoomScale > 10 ? 10 : 15;
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
      className={`h-[156px] shrink-0 flex flex-col bg-surface-1 rounded-xl border border-border-subtle overflow-hidden select-none shadow-md ${className}`}
      data-testid="editor-timeline"
    >
      {/* Timeline Header Bar with Track Labels & Zoom Toolbar */}
      <div className="h-7 px-3 bg-surface-2 border-b border-border-subtle flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold text-text-primary tracking-tight">
            Timeline
          </span>
          <div className="hidden sm:flex items-center gap-1.5 text-[10px] text-text-muted">
            <span>&middot;</span>
            <span className="font-medium text-text-secondary">{twickData.activeCutCount} cuts</span>
            <span>&middot;</span>
            <span>{twickData.coverageMarkerCount} coverage</span>
          </div>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-0.5">
          <button
            type="button"
            onClick={handleZoomOut}
            className="p-1 text-text-muted hover:text-text-primary hover:bg-surface-3 rounded transition-colors"
            title="Zoom Out"
            aria-label="Zoom Out"
          >
            <ZoomOut className="w-3 h-3" />
          </button>
          <button
            type="button"
            onClick={handleZoomIn}
            className="p-1 text-text-muted hover:text-text-primary hover:bg-surface-3 rounded transition-colors"
            title="Zoom In"
            aria-label="Zoom In"
          >
            <ZoomIn className="w-3 h-3" />
          </button>
          <button
            type="button"
            onClick={handleZoomFit}
            className="p-1 text-text-muted hover:text-text-primary hover:bg-surface-3 rounded transition-colors"
            title="Fit to Width"
            aria-label="Fit to Width"
          >
            <Maximize className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* Main Track Workspace Viewport (Left Track Headers + Right Scrollable Tracks) */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left Track Headers Column (Fixed Width 80px) */}
        <div className="w-20 shrink-0 bg-surface-1 border-r border-border-subtle flex flex-col pt-5 z-10">
          <div className="h-5 px-2 flex items-center gap-1 border-b border-border-subtle/30 text-[10px] font-medium text-text-muted">
            <Video className="w-3 h-3 text-text-muted/70 shrink-0" />
            <span className="truncate">Source</span>
          </div>

          <div className="h-9 px-2 flex items-center gap-1 border-b border-border-subtle/30 text-[10px] font-semibold text-text-primary">
            <Scissors className="w-3 h-3 text-primary shrink-0" />
            <span className="truncate">Edits</span>
          </div>

          <div className="h-6 px-2 flex items-center gap-1 text-[10px] font-medium text-text-muted">
            <Layers className="w-3 h-3 text-info shrink-0" />
            <span className="truncate">Coverage</span>
          </div>
        </div>
        {/* Right Scrollable Timeline Canvas */}
        <div
          ref={trackAreaRef}
          className={`flex-1 ${
            isOverflowing ? "overflow-x-auto" : "overflow-x-hidden"
          } overflow-y-hidden relative bg-surface-1 cursor-crosshair focus:outline-none`}
          onMouseDown={handleScrubStart}
          role="region"
          aria-label="Timeline Tracks Canvas"
          tabIndex={0}
        >
          <div
            className="relative h-full flex flex-col"
            style={{ width: `${timelineContentWidth}px` }}
          >
            {/* 1. Time Ruler Bar (Top 20px) */}
            <div className="h-5 border-b border-border-subtle bg-surface-2/70 relative shrink-0">
              {rulerTicks.map((tickSec) => {
                const tickPx = msToPixels(tickSec * 1000);
                return (
                  <div
                    key={`tick-${tickSec}`}
                    className="absolute top-0 bottom-0 flex flex-col justify-between pointer-events-none"
                    style={{ left: `${tickPx}px` }}
                  >
                    <span className="text-[9px] font-mono text-text-muted pl-1 select-none">
                      {formatTimecode(tickSec * 1000).substring(0, 5)}
                    </span>
                    <div className="w-px h-1 bg-border-strong" />
                  </div>
                );
              })}
            </div>

            {/* 2. Track 1 Content: SOURCE VIDEO (Thin Rail Line) */}
            <div className="h-5 border-b border-border-subtle/30 relative flex items-center px-1 shrink-0 bg-surface-1">
              <div className="absolute inset-x-1 h-1.5 rounded-full bg-surface-3/90 border border-border-subtle" />
            </div>

            {/* 3. Track 2 Content: EDITS (Primary Prominent Visible Markers) */}
            <div className="h-9 border-b border-border-subtle/30 relative flex items-center px-1 bg-surface-2/15 shrink-0">
              {dialogueCutBlocks.length === 0 ? (
                <div className="absolute inset-0 flex items-center px-3 text-[10px] text-text-muted pointer-events-none">
                  <span>No cuts applied</span>
                </div>
              ) : (
                dialogueCutBlocks.map((cut) => {
                  const leftPx = msToPixels(cut.startMs);
                  const widthPx = Math.max(14, msToPixels(cut.endMs) - leftPx);
                  const isSelected = selectedBlockId === cut.id;

                  return (
                    <div
                      key={cut.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectBlock(cut);
                      }}
                      className={`absolute top-1 bottom-1 rounded cursor-pointer transition-all flex items-center justify-center px-1 text-[10px] font-mono font-semibold truncate ${
                        cut.type === "cut-safe"
                          ? "bg-danger/25 border border-danger/70 text-danger hover:bg-danger/40 shadow-sm"
                          : cut.type === "cut-needs-coverage"
                            ? "bg-warning/25 border border-warning/70 text-warning hover:bg-warning/40 shadow-sm"
                            : "bg-surface-3 border border-border-strong text-text-muted line-through opacity-60"
                      } ${isSelected ? "ring-2 ring-primary shadow-md scale-[1.02] z-10" : ""}`}
                      style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
                      title={`${cut.label}: ${formatTimecode(cut.startMs)} → ${formatTimecode(cut.endMs)} (${((cut.endMs - cut.startMs) / 1000).toFixed(1)}s)`}
                    >
                      <span className="truncate">{cut.label}</span>
                    </div>
                  );
                })
              )}
            </div>

            {/* 4. Track 3 Content: COVERAGE (Thin Secondary Track) */}
            <div className="h-6 relative flex items-center px-1 shrink-0 bg-surface-1">
              {coverageBlocks.map((cov) => {
                const leftPx = msToPixels(cov.startMs);
                const widthPx = Math.max(14, msToPixels(cov.endMs) - leftPx);
                const isSelected = selectedBlockId === cov.id;
                const isCurrentActive = currentTimeMs >= cov.startMs && currentTimeMs <= cov.endMs;

                return (
                  <div
                    key={cov.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectBlock(cov);
                    }}
                    className={`absolute top-0.5 bottom-0.5 rounded cursor-pointer transition-all flex items-center gap-1 px-1.5 text-[9px] font-medium ${
                      cov.type === "coverage-broll"
                        ? "bg-info/25 border border-info/70 text-info hover:bg-info/35"
                        : "bg-surface-3 border border-border-strong text-text-secondary hover:bg-surface-3/80"
                    } ${isSelected ? "ring-2 ring-primary shadow-md" : ""} ${
                      isCurrentActive ? "ring-1 ring-info animate-pulse" : ""
                    }`}
                    style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
                    title={`Coverage: ${cov.label} (${formatTimecode(cov.startMs)} → ${formatTimecode(cov.endMs)})`}
                  >
                    <Layers className="w-2.5 h-2.5 shrink-0" />
                    <span className="truncate font-semibold">{cov.label}</span>
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
              <div className="w-3 h-3 bg-primary text-white rounded-sm -translate-x-[5px] -translate-y-0.5 rotate-45 flex items-center justify-center shadow-md" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
