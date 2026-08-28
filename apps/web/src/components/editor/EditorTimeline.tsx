import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ZoomIn,
  ZoomOut,
  Maximize,
  Scissors,
  Layers,
  Video,
  Volume2,
  Bookmark,
  Smartphone,
  Sparkles,
  FileText,
} from "lucide-react";
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

  // Auto-fit zoom to available container width
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

  // Group blocks by canonical track
  const dialogueCutBlocks = twickData.blocks.filter(
    (b) => b.trackId === "edits" || b.trackId === "dialogue-edits",
  );
  const coverageBlocks = twickData.blocks.filter(
    (b) => b.trackId === "broll" || b.trackId === "coverage",
  );
  const chapterBlocks = twickData.blocks.filter((b) => b.trackId === "chapters");
  const shortBlocks = twickData.blocks.filter((b) => b.trackId === "short");
  const narrationBlocks = twickData.blocks.filter((b) => b.trackId === "narration");
  const captionBlocks = twickData.blocks.filter((b) => b.trackId === "captions");

  return (
    <div
      ref={containerRef}
      className={`h-[180px] shrink-0 flex flex-col bg-surface-1 rounded-xl border border-border-subtle overflow-hidden select-none shadow-md ${className}`}
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
            {chapterBlocks.length > 0 && (
              <>
                <span>&middot;</span>
                <span>{chapterBlocks.length} chapters</span>
              </>
            )}
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
        {/* Left Track Headers Column (Fixed Width 90px) */}
        <div className="w-[90px] shrink-0 bg-surface-1 border-r border-border-subtle flex flex-col pt-5 z-10 overflow-y-auto divide-y divide-border-subtle/30">
          {/* Track 1 Header: Video */}
          <div className="h-5 px-2 flex items-center gap-1.5 text-[10px] font-medium text-text-muted">
            <Video className="w-3 h-3 text-text-muted/70 shrink-0" />
            <span className="truncate">Video</span>
          </div>

          {/* Track 2 Header: Audio */}
          <div className="h-5 px-2 flex items-center gap-1.5 text-[10px] font-medium text-text-muted">
            <Volume2 className="w-3 h-3 text-text-muted/70 shrink-0" />
            <span className="truncate">Audio</span>
          </div>

          {/* Track 3 Header: Edits */}
          <div className="h-8 px-2 flex items-center gap-1.5 text-[10px] font-semibold text-text-primary">
            <Scissors className="w-3 h-3 text-primary shrink-0" />
            <span className="truncate">Edits</span>
          </div>
          {/* Track 4 Header: B-roll */}
          {coverageBlocks.length > 0 && (
            <div className="h-6 px-2 flex items-center gap-1.5 text-[10px] font-medium text-text-muted">
              <Layers className="w-3 h-3 text-info shrink-0" />
              <span className="truncate">B-roll</span>
            </div>
          )}

          {/* Track 5 Header: Chapters */}
          {chapterBlocks.length > 0 && (
            <div className="h-6 px-2 flex items-center gap-1.5 text-[10px] font-medium text-amber-400/80">
              <Bookmark className="w-3 h-3 text-amber-400 shrink-0" />
              <span className="truncate">Chapters</span>
            </div>
          )}

          {/* Track 6 Header: Short */}
          {shortBlocks.length > 0 && (
            <div className="h-6 px-2 flex items-center gap-1.5 text-[10px] font-medium text-purple-400">
              <Smartphone className="w-3 h-3 text-purple-400 shrink-0" />
              <span className="truncate">Short</span>
            </div>
          )}

          {/* Track 7 Header: Narration */}
          {narrationBlocks.length > 0 && (
            <div className="h-6 px-2 flex items-center gap-1.5 text-[10px] font-medium text-blue-400">
              <Sparkles className="w-3 h-3 text-blue-400 shrink-0" />
              <span className="truncate">Narration</span>
            </div>
          )}

          {/* Track 8 Header: Captions */}
          {captionBlocks.length > 0 && (
            <div className="h-6 px-2 flex items-center gap-1.5 text-[10px] font-medium text-text-secondary">
              <FileText className="w-3 h-3 text-text-muted shrink-0" />
              <span className="truncate">Captions</span>
            </div>
          )}
        </div>

        {/* Right Scrollable Timeline Canvas */}
        <div
          ref={trackAreaRef}
          className={`flex-1 ${
            isOverflowing ? "overflow-x-auto" : "overflow-x-hidden"
          } overflow-y-auto relative bg-surface-1 cursor-crosshair focus:outline-none`}
          onMouseDown={handleScrubStart}
          role="region"
          aria-label="Timeline Tracks Canvas"
          tabIndex={0}
        >
          <div
            className="relative flex flex-col min-h-full"
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

            {/* 2. Track 1 Content: VIDEO (Continuous solid rail with cuts) */}
            <div className="h-5 border-b border-border-subtle/30 relative flex items-center px-1 shrink-0 bg-surface-1">
              <div className="absolute inset-x-1 h-2 rounded bg-surface-3/90 border border-border-subtle flex overflow-hidden">
                {twickData.keepSegments.map(([startMs, endMs], idx) => {
                  const segLeft = msToPixels(startMs);
                  const segWidth = Math.max(2, msToPixels(endMs) - segLeft);
                  return (
                    <div
                      key={`keep-${idx}`}
                      className="absolute top-0 bottom-0 bg-primary/40 border-r border-background/60"
                      style={{ left: `${segLeft}px`, width: `${segWidth}px` }}
                      title={`Keep segment ${formatTimecode(startMs)} → ${formatTimecode(endMs)}`}
                    />
                  );
                })}
              </div>
            </div>

            {/* 3. Track 2 Content: AUDIO (Media Analysis Grounded: Speech, Silence, Removed) */}
            <div className="h-5 border-b border-border-subtle/30 relative flex items-center px-1 shrink-0 bg-surface-2/10 overflow-hidden">
              <div className="absolute inset-x-1 h-0.5 bg-surface-3/40 rounded-full" />
              {twickData.audioRegions && twickData.audioRegions.length > 0 ? (
                twickData.audioRegions.map((region, idx) => {
                  const leftPx = msToPixels(region.startMs);
                  const widthPx = Math.max(2, msToPixels(region.endMs) - leftPx);
                  if (region.type === "speech") {
                    return (
                      <div
                        key={`aud-${idx}`}
                        className="absolute top-1 bottom-1 bg-emerald-500/50 border-t border-b border-emerald-400/80 rounded-xs"
                        style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
                        title={`Speech segment ${formatTimecode(region.startMs)} → ${formatTimecode(region.endMs)}`}
                      />
                    );
                  }
                  if (region.type === "removed") {
                    return (
                      <div
                        key={`aud-${idx}`}
                        className="absolute top-1 bottom-1 bg-danger/40 border border-danger/60 rounded-xs"
                        style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
                        title={`Cut removed region ${formatTimecode(region.startMs)} → ${formatTimecode(region.endMs)}`}
                      />
                    );
                  }
                  return null;
                })
              ) : (
                <div className="absolute inset-x-1 h-1.5 rounded-full bg-emerald-500/30 border border-emerald-500/40" />
              )}
            </div>
            {/* 4. Track 3 Content: EDITS (Clean Human Tooltips & Badges) */}
            <div className="h-8 border-b border-border-subtle/30 relative flex items-center px-1 bg-surface-2/20 shrink-0">
              {dialogueCutBlocks.length === 0 ? (
                <div className="absolute inset-0 flex items-center px-3 text-[10px] text-text-muted pointer-events-none">
                  <span>No dialogue cuts</span>
                </div>
              ) : (
                dialogueCutBlocks.map((cut) => {
                  const leftPx = msToPixels(cut.startMs);
                  const widthPx = Math.max(16, msToPixels(cut.endMs) - leftPx);
                  const isSelected = selectedBlockId === cut.id;

                  return (
                    <div
                      key={cut.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectBlock(cut);
                      }}
                      className={`absolute top-1 bottom-1 rounded cursor-pointer transition-all flex items-center justify-center px-1.5 text-[9px] font-mono font-medium truncate ${
                        cut.type === "cut-safe"
                          ? "bg-danger/20 border border-danger/60 text-danger hover:bg-danger/35 shadow-xs"
                          : cut.type === "cut-needs-coverage"
                            ? "bg-warning/20 border border-warning/60 text-warning hover:bg-warning/35 shadow-xs"
                            : "bg-surface-3 border border-border-strong text-text-muted line-through opacity-60"
                      } ${isSelected ? "ring-2 ring-primary shadow-md scale-[1.02] z-10" : ""}`}
                      style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
                      title={`${cut.label}: ${formatTimecode(cut.startMs)} → ${formatTimecode(cut.endMs)}`}
                    >
                      <span className="truncate font-sans font-semibold">{cut.label}</span>
                    </div>
                  );
                })
              )}
            </div>
            {/* 5. Track 4 Content: B-ROLL & COVERAGE */}
            {coverageBlocks.length > 0 && (
              <div className="h-6 border-b border-border-subtle/30 relative flex items-center px-1 shrink-0 bg-surface-1">
                {coverageBlocks.map((cov) => {
                  const leftPx = msToPixels(cov.startMs);
                  const widthPx = Math.max(16, msToPixels(cov.endMs) - leftPx);
                  const isSelected = selectedBlockId === cov.id;
                  const isCurrentActive =
                    currentTimeMs >= cov.startMs && currentTimeMs <= cov.endMs;

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
            )}

            {/* 6. Track 5 Content: CHAPTERS (Semantic Chapter Markers) */}
            {chapterBlocks.length > 0 && (
              <div className="h-6 border-b border-border-subtle/30 relative flex items-center px-1 shrink-0 bg-amber-500/5">
                {chapterBlocks.map((chap) => {
                  const leftPx = msToPixels(chap.startMs);
                  const widthPx = Math.max(20, msToPixels(chap.endMs) - leftPx);

                  return (
                    <div
                      key={chap.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSeek(chap.startMs);
                        onSelectBlock(chap);
                      }}
                      className="absolute top-0.5 bottom-0.5 rounded cursor-pointer transition-all flex items-center gap-1 px-1.5 text-[9px] font-medium bg-amber-500/15 border border-amber-500/40 text-amber-300 hover:bg-amber-500/30 truncate"
                      style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
                      title={`Chapter: ${chap.label} (${formatTimecode(chap.startMs)} → ${formatTimecode(chap.endMs)})`}
                    >
                      <Bookmark className="w-2.5 h-2.5 shrink-0 text-amber-400" />
                      <span className="truncate font-semibold">{chap.label}</span>
                    </div>
                  );
                })}
              </div>
            )}

            {/* 7. Track 6 Content: SHORT CANDIDATE */}
            {shortBlocks.length > 0 && (
              <div className="h-6 relative flex items-center px-1 shrink-0 bg-purple-500/5">
                {shortBlocks.map((sc) => {
                  const leftPx = msToPixels(sc.startMs);
                  const widthPx = Math.max(24, msToPixels(sc.endMs) - leftPx);

                  return (
                    <div
                      key={sc.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSeek(sc.startMs);
                        onSelectBlock(sc);
                      }}
                      className="absolute top-0.5 bottom-0.5 rounded cursor-pointer transition-all flex items-center gap-1 px-2 text-[9px] font-medium bg-purple-600/20 border border-purple-500/60 text-purple-200 hover:bg-purple-600/35 truncate"
                      style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
                      title={`${sc.label} (${formatTimecode(sc.startMs)} → ${formatTimecode(sc.endMs)})`}
                    >
                      <Smartphone className="w-2.5 h-2.5 shrink-0 text-purple-400" />
                      <span className="truncate font-semibold">{sc.label}</span>
                    </div>
                  );
                })}
              </div>
            )}
            {/* 8. Track 7 Content: NARRATION */}
            {narrationBlocks.length > 0 && (
              <div className="h-6 border-b border-border-subtle/30 relative flex items-center px-1 shrink-0 bg-blue-500/5">
                {narrationBlocks.map((narr) => {
                  const leftPx = msToPixels(narr.startMs);
                  const widthPx = Math.max(20, msToPixels(narr.endMs) - leftPx);
                  return (
                    <div
                      key={narr.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectBlock(narr);
                      }}
                      className="absolute top-0.5 bottom-0.5 rounded cursor-pointer transition-all flex items-center gap-1 px-2 text-[9px] font-medium bg-blue-500/20 border border-blue-500/60 text-blue-200 truncate"
                      style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
                      title={`${narr.label} (${formatTimecode(narr.startMs)} → ${formatTimecode(narr.endMs)})`}
                    >
                      <Sparkles className="w-2.5 h-2.5 shrink-0 text-blue-400" />
                      <span className="truncate font-semibold">{narr.label}</span>
                    </div>
                  );
                })}
              </div>
            )}

            {/* 9. Track 8 Content: CAPTIONS */}
            {captionBlocks.length > 0 && (
              <div className="h-6 border-b border-border-subtle/30 relative flex items-center px-1 shrink-0 bg-surface-2/10">
                {captionBlocks.map((cap) => {
                  const leftPx = msToPixels(cap.startMs);
                  const widthPx = Math.max(16, msToPixels(cap.endMs) - leftPx);
                  return (
                    <div
                      key={cap.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectBlock(cap);
                      }}
                      className="absolute top-0.5 bottom-0.5 rounded cursor-pointer transition-all flex items-center gap-1 px-1.5 text-[9px] font-medium bg-surface-3/80 border border-border-strong text-text-muted truncate"
                      style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
                      title={`${cap.label} (${formatTimecode(cap.startMs)} → ${formatTimecode(cap.endMs)})`}
                    >
                      <span className="truncate">{cap.label}</span>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Playhead Indicator Line across all tracks */}
            <div
              className="absolute top-0 bottom-0 w-0.5 bg-primary z-20 pointer-events-none transition-[left] duration-75 shadow-sm"
              style={{ left: `${playheadPx}px` }}
            >
              {/* Playhead Needle */}
              <div className="w-3 h-3 bg-primary text-white rounded-sm -translate-x-[5px] -translate-y-0.5 rotate-45 flex items-center justify-center shadow-md" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
