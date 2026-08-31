import {
  Bookmark,
  FileText,
  Layers,
  Maximize,
  Mic,
  Music,
  Scissors,
  Video,
  Volume2,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  formatTimecode,
  type PreviewMode,
  type TimelineBlock,
  type TwickTimelineRepresentation,
} from "../../lib/edl-adapter";
export const TIMELINE_ROW_HEIGHTS = {
  ruler: 20,
  video: 20,
  audio: 20,
  edits: 32,
  coverage: 24,
  voiceover: 24,
  music: 24,
  chapters: 24,
  captions: 24,
} as const;

interface EditorTimelineProps {
  twickData: TwickTimelineRepresentation;
  currentTimeMs: number;
  durationMs: number;
  selectedBlockId: string | null;
  onSelectBlock: (block: TimelineBlock | null) => void;
  onSeek: (targetMs: number) => void;
  onSelectRange?: (startMs: number, endMs: number) => void;
  onSelectPoint?: (targetMs: number) => void;
  isPlaying?: boolean;
  previewMode?: PreviewMode;
  className?: string;
}
export const EditorTimeline: React.FC<EditorTimelineProps> = ({
  twickData,
  currentTimeMs,
  durationMs,
  selectedBlockId,
  onSelectBlock,
  onSeek,
  onSelectRange,
  onSelectPoint,
  previewMode = "final_mix",
  className = "",
}) => {
  const trackAreaRef = useRef<HTMLDivElement>(null);
  const scrubStartMsRef = useRef<number | null>(null);
  const latestScrubMsRef = useRef<number | null>(null);

  const [zoomScale, setZoomScale] = useState<number | null>(null);
  const [isScrubbing, setIsScrubbing] = useState<boolean>(false);
  const [selectedTimeRange, setSelectedTimeRange] = useState<[number, number] | null>(null);
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
    scrubStartMsRef.current = targetMs;
    latestScrubMsRef.current = targetMs;
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isScrubbing || !trackAreaRef.current) return;
      const rect = trackAreaRef.current.getBoundingClientRect();
      const scrollLeft = trackAreaRef.current.scrollLeft;
      const moveX = e.clientX - rect.left + scrollLeft;
      const targetMs = pixelsToMs(moveX);
      onSeek(targetMs);
      latestScrubMsRef.current = targetMs;
    };

    const handleMouseUp = () => {
      if (!isScrubbing) return;
      setIsScrubbing(false);
      const startMs = scrubStartMsRef.current;
      const endMs = latestScrubMsRef.current;
      scrubStartMsRef.current = null;
      latestScrubMsRef.current = null;
      if (startMs === null) return;
      if (endMs === null || Math.abs(endMs - startMs) < 250) {
        onSelectPoint?.(startMs);
        return;
      }
      const range: [number, number] = [Math.min(startMs, endMs), Math.max(startMs, endMs)];
      setSelectedTimeRange(range);
      onSelectRange?.(range[0], range[1]);
    };

    if (isScrubbing) {
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
    }
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isScrubbing, onSeek, onSelectRange, onSelectPoint, pixelsToMs]);

  // Generate ruler tick marks based on zoom level
  const effectiveZoomScale =
    zoomScale ?? (containerWidth > 0 ? containerWidth / totalDurationSec : 6);
  const rulerIntervalSec = effectiveZoomScale > 20 ? 5 : effectiveZoomScale > 10 ? 10 : 15;
  const rulerTicks: number[] = [];
  for (let sec = 0; sec <= totalDurationSec; sec += rulerIntervalSec) {
    rulerTicks.push(sec);
  }

  const playheadPx = msToPixels(currentTimeMs);

  // Group blocks by canonical tracks
  const dialogueCutBlocks = twickData.blocks.filter(
    (b) => b.trackId === "edits" || b.trackId === "dialogue-edits",
  );
  const coverageBlocks = twickData.blocks.filter((b) => b.trackId === "coverage");
  const voiceoverBlocks = twickData.blocks.filter(
    (b) => b.trackId === "voiceover" || b.trackId === "narration",
  );
  const musicBlocks = twickData.blocks.filter((b) => b.trackId === "music");
  const chapterBlocks = twickData.blocks.filter((b) => b.trackId === "chapters");
  const captionBlocks = twickData.blocks.filter((b) => b.trackId === "captions");

  const isOriginalMode = previewMode === "original";
  const isEditedMode = previewMode === "edited";
  const isVoiceoverMode = previewMode === "studio_voice";
  const isFinalMixMode = !previewMode || previewMode === "final_mix";

  // Mode-specific Video Keep Segments:
  const visibleKeepSegments = isOriginalMode ? [[0, durationMs]] : twickData.keepSegments;

  // Mode-specific Audio Regions:
  const visibleAudioRegions = isOriginalMode
    ? [{ type: "speech" as const, startMs: 0, endMs: durationMs, label: "Original source audio" }]
    : twickData.audioRegions;

  interface TrackDef {
    id: string;
    label: string;
    height: number;
    renderHeader: () => React.ReactNode;
    renderTrack: () => React.ReactNode;
  }

  const videoTrackDef: TrackDef = {
    id: "video",
    label: "Video",
    height: TIMELINE_ROW_HEIGHTS.video,
    renderHeader: () => (
      <div className="h-full w-full flex items-center gap-1.5 text-[10px] font-medium text-text-muted">
        <Video className="w-3 h-3 text-text-muted/70 shrink-0" />
        <span className="truncate">Video</span>
      </div>
    ),
    renderTrack: () => (
      <div className="h-full w-full relative flex items-center px-1 bg-surface-1">
        <div className="absolute inset-x-1 h-2 rounded bg-surface-3/90 border border-border-subtle flex overflow-hidden">
          {visibleKeepSegments.map(([startMs, endMs], idx) => {
            const segLeft = msToPixels(startMs);
            const segWidth = Math.max(2, msToPixels(endMs) - segLeft);
            return (
              <button
                type="button"
                key={`keep-${idx}`}
                onMouseDown={(event) => event.stopPropagation()}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelectBlock({
                    id: `keep-${idx}`,
                    trackId: "video",
                    label: isOriginalMode ? "Original Video" : "Video section",
                    startMs,
                    endMs,
                    durationMs: endMs - startMs,
                    type: "keep",
                    details: {
                      summary: isOriginalMode
                        ? "Full untouched continuous source video."
                        : "Continuous source footage retained in the edit.",
                    },
                  });
                }}
                className={`absolute top-0 bottom-0 bg-primary/40 border-r border-background/60 hover:bg-primary/60 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary ${
                  selectedBlockId === `keep-${idx}` ? "ring-1 ring-primary" : ""
                }`}
                style={{ left: `${segLeft}px`, width: `${segWidth}px` }}
                title={`Video section ${formatTimecode(startMs)} → ${formatTimecode(endMs)}`}
                aria-label={`Select video section from ${formatTimecode(startMs)} to ${formatTimecode(endMs)}`}
              />
            );
          })}
        </div>
      </div>
    ),
  };

  const audioTrackDef: TrackDef = {
    id: "audio",
    label: isOriginalMode ? "Original Audio" : "Audio",
    height: TIMELINE_ROW_HEIGHTS.audio,
    renderHeader: () => (
      <div className="h-full w-full flex items-center gap-1.5 text-[10px] font-medium text-text-muted">
        <Volume2 className="w-3 h-3 text-text-muted/70 shrink-0" />
        <span className="truncate">{isOriginalMode ? "Original Audio" : "Audio"}</span>
      </div>
    ),
    renderTrack: () => (
      <div className="h-full w-full relative flex items-center px-1 bg-surface-2/10 overflow-hidden">
        <div className="absolute inset-x-1 h-0.5 bg-surface-3/40 rounded-full" />
        {visibleAudioRegions && visibleAudioRegions.length > 0 ? (
          visibleAudioRegions.map((region, idx) => {
            const leftPx = msToPixels(region.startMs);
            const widthPx = Math.max(2, msToPixels(region.endMs) - leftPx);
            const label =
              region.label ||
              (region.type === "speech"
                ? "Spoken audio"
                : region.type === "removed"
                  ? "Removed audio"
                  : "Pause");
            return (
              <button
                type="button"
                key={`aud-${idx}`}
                onMouseDown={(event) => event.stopPropagation()}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelectBlock({
                    id: `audio-${idx}`,
                    trackId: "audio",
                    label,
                    startMs: region.startMs,
                    endMs: region.endMs,
                    durationMs: region.endMs - region.startMs,
                    type: region.type === "removed" ? "cut-safe" : "source",
                    details: {
                      summary:
                        region.type === "speech"
                          ? "Speech activity detected in the source audio."
                          : region.type === "removed"
                            ? "This audio range is removed by the edit."
                            : "A pause was detected in the source audio.",
                    },
                  });
                }}
                className={`absolute top-1 bottom-1 rounded-xs border focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary ${
                  region.type === "speech"
                    ? "border-emerald-400/80 bg-emerald-500/50 hover:bg-emerald-500/70"
                    : region.type === "removed"
                      ? "border-danger/60 bg-danger/40 hover:bg-danger/60"
                      : "border-border-strong bg-surface-3/80 hover:bg-surface-3"
                } ${selectedBlockId === `audio-${idx}` ? "ring-1 ring-primary" : ""}`}
                style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
                title={`${label} ${formatTimecode(region.startMs)} → ${formatTimecode(region.endMs)}`}
                aria-label={`Select ${label.toLowerCase()} from ${formatTimecode(region.startMs)} to ${formatTimecode(region.endMs)}`}
              />
            );
          })
        ) : (
          <div className="absolute inset-x-1 h-1.5 rounded-full bg-emerald-500/30 border border-emerald-500/40" />
        )}
      </div>
    ),
  };

  const editsTrackDef: TrackDef = {
    id: "edits",
    label: "Edits",
    height: TIMELINE_ROW_HEIGHTS.edits,
    renderHeader: () => (
      <div className="h-full w-full flex items-center gap-1.5 text-[10px] font-semibold text-text-primary">
        <Scissors className="w-3 h-3 text-primary shrink-0" />
        <span className="truncate">Edits</span>
      </div>
    ),
    renderTrack: () => (
      <div className="h-full w-full relative flex items-center px-1 bg-surface-2/20">
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
              <button
                type="button"
                key={cut.id}
                onMouseDown={(event) => event.stopPropagation()}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelectBlock(cut);
                }}
                className={`absolute top-1 bottom-1 rounded cursor-pointer transition-all flex items-center justify-center px-1.5 text-[9px] font-mono font-medium truncate focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
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
              </button>
            );
          })
        )}
      </div>
    ),
  };

  const coverageTrackDef: TrackDef = {
    id: "coverage",
    label: "Coverage",
    height: TIMELINE_ROW_HEIGHTS.coverage,
    renderHeader: () => (
      <div className="h-full w-full flex items-center gap-1.5 text-[10px] font-medium text-text-muted">
        <Layers className="w-3 h-3 text-info shrink-0" />
        <span className="truncate">Coverage</span>
      </div>
    ),
    renderTrack: () => (
      <div className="h-full w-full relative flex items-center px-1 bg-surface-1">
        {coverageBlocks.map((cov) => {
          const leftPx = msToPixels(cov.startMs);
          const widthPx = Math.max(16, msToPixels(cov.endMs) - leftPx);
          const isSelected = selectedBlockId === cov.id;
          const isCurrentActive =
            currentTimeMs >= cov.startMs && currentTimeMs <= cov.endMs;

          return (
            <button
              type="button"
              key={cov.id}
              onMouseDown={(event) => event.stopPropagation()}
              onClick={(event) => {
                event.stopPropagation();
                onSelectBlock(cov);
              }}
              className={`absolute top-0.5 bottom-0.5 rounded cursor-pointer transition-all flex items-center gap-1 px-1.5 text-[9px] font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary bg-surface-3 border border-border-strong text-text-secondary hover:bg-surface-3/80 ${
                isSelected ? "ring-2 ring-primary shadow-md" : ""
              } ${isCurrentActive ? "ring-1 ring-info animate-pulse" : ""}`}
              style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
              title={`Coverage: ${cov.label} (${formatTimecode(cov.startMs)} → ${formatTimecode(cov.endMs)})`}
            >
              <Layers className="w-2.5 h-2.5 shrink-0" />
              <span className="truncate font-semibold">{cov.label}</span>
            </button>
          );
        })}
      </div>
    ),
  };

  const voiceoverTrackDef: TrackDef = {
    id: "voiceover",
    label: "Voiceover",
    height: TIMELINE_ROW_HEIGHTS.voiceover,
    renderHeader: () => (
      <div className="h-full w-full flex items-center gap-1.5 text-[10px] font-medium text-blue-400">
        <Mic className="w-3 h-3 text-blue-400 shrink-0" />
        <span className="truncate">Voiceover</span>
      </div>
    ),
    renderTrack: () => (
      <div className="h-full w-full relative flex items-center px-1 bg-blue-500/5">
        {voiceoverBlocks.length === 0 ? (
          <div className="absolute inset-0 flex items-center px-3 text-[10px] text-blue-300/50 pointer-events-none">
            <span>No voiceover tracks</span>
          </div>
        ) : (
          voiceoverBlocks.map((vo) => {
            const leftPx = msToPixels(vo.startMs);
            const widthPx = Math.max(20, msToPixels(vo.endMs) - leftPx);
            const isSelected = selectedBlockId === vo.id;
            return (
              <button
                type="button"
                key={vo.id}
                onMouseDown={(event) => event.stopPropagation()}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelectBlock(vo);
                }}
                className={`absolute top-0.5 bottom-0.5 rounded cursor-pointer transition-all flex items-center gap-1 px-2 text-[9px] font-medium bg-blue-500/20 border border-blue-500/60 text-blue-200 truncate focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                  isSelected ? "ring-2 ring-primary shadow-md" : ""
                }`}
                style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
                title={`Voiceover: ${vo.label} (${formatTimecode(vo.startMs)} → ${formatTimecode(vo.endMs)})`}
              >
                <Mic className="w-2.5 h-2.5 shrink-0 text-blue-400" />
                <span className="truncate font-semibold">{vo.label}</span>
              </button>
            );
          })
        )}
      </div>
    ),
  };

  const musicTrackDef: TrackDef = {
    id: "music",
    label: "Music",
    height: TIMELINE_ROW_HEIGHTS.music,
    renderHeader: () => (
      <div className="h-full w-full flex items-center gap-1.5 text-[10px] font-medium text-purple-400">
        <Music className="w-3 h-3 text-purple-400 shrink-0" />
        <span className="truncate">Music</span>
      </div>
    ),
    renderTrack: () => (
      <div className="h-full w-full relative flex items-center px-1 bg-purple-500/5">
        {musicBlocks.length === 0 ? (
          <div className="absolute inset-0 flex items-center px-3 text-[10px] text-purple-300/50 pointer-events-none">
            <span>No background music</span>
          </div>
        ) : (
          musicBlocks.map((mb) => {
            const leftPx = msToPixels(mb.startMs);
            const widthPx = Math.max(40, msToPixels(mb.endMs) - leftPx);
            const isSelected = selectedBlockId === mb.id;
            return (
              <button
                type="button"
                key={mb.id}
                onMouseDown={(event) => event.stopPropagation()}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelectBlock(mb);
                }}
                className={`absolute top-0.5 bottom-0.5 rounded cursor-pointer transition-all flex items-center gap-1 px-2 text-[9px] font-medium bg-purple-500/20 border border-purple-500/50 text-purple-200 truncate focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                  isSelected ? "ring-2 ring-primary shadow-md" : ""
                }`}
                style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
                title={`Music: ${mb.label}`}
              >
                <Music className="w-2.5 h-2.5 shrink-0 text-purple-400" />
                <span className="truncate font-semibold">{mb.label}</span>
              </button>
            );
          })
        )}
      </div>
    ),
  };

  const chaptersTrackDef: TrackDef = {
    id: "chapters",
    label: "Chapters",
    height: TIMELINE_ROW_HEIGHTS.chapters,
    renderHeader: () => (
      <div className="h-full w-full flex items-center gap-1.5 text-[10px] font-medium text-amber-400/80">
        <Bookmark className="w-3 h-3 text-amber-400 shrink-0" />
        <span className="truncate">Chapters</span>
      </div>
    ),
    renderTrack: () => (
      <div className="h-full w-full relative flex items-center px-1 bg-amber-500/5">
        {chapterBlocks.map((chap) => {
          const leftPx = msToPixels(chap.startMs);
          const widthPx = Math.max(20, msToPixels(chap.endMs) - leftPx);
          return (
            <button
              key={chap.id}
              onMouseDown={(event) => event.stopPropagation()}
              onClick={(event) => {
                event.stopPropagation();
                onSelectBlock(chap);
              }}
              className={`absolute top-0.5 bottom-0.5 rounded cursor-pointer transition-all flex items-center gap-1 px-1.5 text-[9px] font-medium bg-amber-500/15 border border-amber-500/40 text-amber-300 hover:bg-amber-500/30 truncate focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                selectedBlockId === chap.id ? "ring-2 ring-primary" : ""
              }`}
              style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
              title={`Chapter: ${chap.label} (${formatTimecode(chap.startMs)} → ${formatTimecode(chap.endMs)})`}
            >
              <Bookmark className="w-2.5 h-2.5 shrink-0 text-amber-400" />
              <span className="truncate font-semibold">{chap.label}</span>
            </button>
          );
        })}
      </div>
    ),
  };

  const captionsTrackDef: TrackDef = {
    id: "captions",
    label: "Captions",
    height: TIMELINE_ROW_HEIGHTS.captions,
    renderHeader: () => (
      <div className="h-full w-full flex items-center gap-1.5 text-[10px] font-medium text-text-secondary">
        <FileText className="w-3 h-3 text-text-muted shrink-0" />
        <span className="truncate">Captions</span>
      </div>
    ),
    renderTrack: () => (
      <div className="h-full w-full relative flex items-center px-1 bg-surface-2/10">
        {captionBlocks.map((cap) => {
          const leftPx = msToPixels(cap.startMs);
          const widthPx = Math.max(16, msToPixels(cap.endMs) - leftPx);
          return (
            <button
              type="button"
              key={cap.id}
              onMouseDown={(event) => event.stopPropagation()}
              onClick={(event) => {
                event.stopPropagation();
                onSelectBlock(cap);
              }}
              className={`absolute top-0.5 bottom-0.5 rounded cursor-pointer transition-all flex items-center gap-1 px-1.5 text-[9px] font-medium bg-surface-3/80 border border-border-strong text-text-muted truncate focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                selectedBlockId === cap.id ? "ring-2 ring-primary" : ""
              }`}
              style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
              title={`${cap.label} (${formatTimecode(cap.startMs)} → ${formatTimecode(cap.endMs)})`}
            >
              <span className="truncate">{cap.label}</span>
            </button>
          );
        })}
      </div>
    ),
  };

  // Construct ordered activeTracks based on preview mode:
  // ORIGINAL: 1. Video, 2. Original Audio
  // EDITED: 1. Video, 2. Audio, 3. Edits, [4. Coverage], [5. Chapters], [6. Captions]
  // VOICEOVER: 1. Video, 2. Edits, [3. Coverage], 4. Voiceover, [5. Chapters], [6. Captions]
  // FINAL_MIX: 1. Video, 2. Edits, [3. Coverage], 4. Voiceover, 5. Music, [6. Chapters], [7. Captions]
  const activeTracks: TrackDef[] = [];
  if (isOriginalMode) {
    activeTracks.push(videoTrackDef);
    activeTracks.push(audioTrackDef);
  } else if (isEditedMode) {
    activeTracks.push(videoTrackDef);
    activeTracks.push(audioTrackDef);
    activeTracks.push(editsTrackDef);
    if (coverageBlocks.length > 0) activeTracks.push(coverageTrackDef);
    if (chapterBlocks.length > 0) activeTracks.push(chaptersTrackDef);
    if (captionBlocks.length > 0) activeTracks.push(captionsTrackDef);
  } else if (isVoiceoverMode) {
    activeTracks.push(videoTrackDef);
    activeTracks.push(editsTrackDef);
    if (coverageBlocks.length > 0) activeTracks.push(coverageTrackDef);
    activeTracks.push(voiceoverTrackDef);
    if (chapterBlocks.length > 0) activeTracks.push(chaptersTrackDef);
    if (captionBlocks.length > 0) activeTracks.push(captionsTrackDef);
  } else {
    // final_mix
    activeTracks.push(videoTrackDef);
    activeTracks.push(editsTrackDef);
    if (coverageBlocks.length > 0) activeTracks.push(coverageTrackDef);
    activeTracks.push(voiceoverTrackDef);
    activeTracks.push(musicTrackDef);
    if (chapterBlocks.length > 0) activeTracks.push(chaptersTrackDef);
    if (captionBlocks.length > 0) activeTracks.push(captionsTrackDef);
  }
  return (
    <div
      className={`h-[180px] shrink-0 flex flex-col bg-surface-1 rounded-xl border border-border-subtle overflow-hidden select-none shadow-md ${className}`}
      data-testid="editor-timeline"
    >
      {/* Timeline Header Bar with Track Labels & Zoom Toolbar */}
      <div className="h-7 px-3 bg-surface-2 border-b border-border-subtle flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold text-text-primary tracking-tight">
            Timeline
          </span>
          {isOriginalMode ? (
            <div className="hidden sm:flex items-center gap-1.5 text-[10px] text-text-muted">
              <span>&middot;</span>
              <span className="font-medium text-text-secondary">Untouched source media</span>
              <span>&middot;</span>
              <span>No edits</span>
            </div>
          ) : (
            <div className="hidden sm:flex items-center gap-1.5 text-[10px] text-text-muted">
              <span>&middot;</span>
              <span className="font-medium text-text-secondary">
                {twickData.activeCutCount} cuts
              </span>
              <span>&middot;</span>
              <span>{twickData.coverageMarkerCount} coverage</span>
              <span>&middot;</span>
              <span>{chapterBlocks.length} chapters</span>
            </div>
          )}
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
        <div
          className="w-[90px] shrink-0 bg-surface-1 border-r border-border-subtle flex flex-col z-10 overflow-hidden"
          data-testid="timeline-labels-column"
        >
          <div
            style={{ height: `${TIMELINE_ROW_HEIGHTS.ruler}px` }}
            className="border-b border-border-subtle bg-surface-2/70 shrink-0"
          />
          {activeTracks.map((track) => (
            <div
              key={track.id}
              style={{ height: `${track.height}px` }}
              className="border-b border-border-subtle/30 px-2 flex items-center shrink-0"
            >
              {track.renderHeader()}
            </div>
          ))}
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
          data-testid="timeline-canvas-column"
        >
          <div
            className="relative flex flex-col min-h-full"
            style={{ width: `${timelineContentWidth}px` }}
          >
            {/* 1. Time Ruler Bar (Top 20px) */}
            <div
              style={{ height: `${TIMELINE_ROW_HEIGHTS.ruler}px` }}
              className="border-b border-border-subtle bg-surface-2/70 relative shrink-0"
            >
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

            {/* 2. Track Content Rows */}
            {activeTracks.map((track) => (
              <div
                key={track.id}
                style={{ height: `${track.height}px` }}
                className="border-b border-border-subtle/30 relative flex items-center shrink-0"
              >
                {track.renderTrack()}
              </div>
            ))}

            {selectedTimeRange && (
              <div
                className="pointer-events-none absolute bottom-0 top-5 z-10 border-x border-primary/60 bg-primary/10"
                style={{
                  left: `${msToPixels(selectedTimeRange[0])}px`,
                  width: `${Math.max(
                    2,
                    msToPixels(selectedTimeRange[1]) - msToPixels(selectedTimeRange[0]),
                  )}px`,
                }}
                aria-hidden="true"
              />
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
