import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize2,
  Minimize2,
  Layers,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import {
  findExecutableSkipInterval,
  formatTimecode,
  formatDuration,
  sourceToEditedTimeMs,
  editedToSourceTimeMs,
  type EditDecisionList,
  type CoverageMarker,
} from "../../lib/edl-adapter";
import type { PreviewMode } from "./PreviewToggle";

interface VideoStageProps {
  playbackUrl: string | null;
  renderedPreviewUrl?: string | null;
  studioVoicePreviewUrl?: string | null;
  currentTimeMs: number;
  durationMs: number;
  editedDurationMs?: number;
  studioVoiceDurationMs?: number | null;
  isPlaying: boolean;
  previewMode: PreviewMode;
  edl: EditDecisionList | null;
  activeCoverage: CoverageMarker | null;
  onPlayPause: () => void;
  onSeek: (targetMs: number) => void;
  onDurationChange?: (durationMs: number) => void;
  className?: string;
}

export const VideoStage: React.FC<VideoStageProps> = ({
  playbackUrl,
  renderedPreviewUrl,
  studioVoicePreviewUrl,
  currentTimeMs,
  durationMs,
  editedDurationMs,
  studioVoiceDurationMs,
  isPlaying,
  previewMode,
  edl,
  activeCoverage,
  onPlayPause,
  onSeek,
  onDurationChange,
  className = "",
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const stageContainerRef = useRef<HTMLDivElement>(null);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [lastSkippedNotice, setLastSkippedNotice] = useState<string | null>(null);
  const [videoError, setVideoError] = useState<string | null>(null);
  const isSeekingInternallyRef = useRef<boolean>(false);

  // Sync isPlaying state with video element
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    if (isPlaying && video.paused) {
      video.play().catch(() => {
        // Autoplay policy or interaction error
      });
    } else if (!isPlaying && !video.paused) {
      video.pause();
    }
  }, [isPlaying]);

  const isUsingStudioVoiceArtifact =
    previewMode === "studio_voice" && Boolean(studioVoicePreviewUrl);
  const isUsingRenderedArtifact = previewMode === "edited" && Boolean(renderedPreviewUrl);

  const activeVideoUrl = isUsingStudioVoiceArtifact
    ? studioVoicePreviewUrl
    : isUsingRenderedArtifact
      ? renderedPreviewUrl
      : playbackUrl;

  const activeDurationMs =
    previewMode === "studio_voice"
      ? studioVoiceDurationMs || editedDurationMs || durationMs
      : previewMode === "edited"
        ? editedDurationMs || durationMs
        : durationMs;

  const activeCurrentTimeMs =
    (previewMode === "edited" || previewMode === "studio_voice") && edl
      ? sourceToEditedTimeMs(currentTimeMs, edl)
      : currentTimeMs;

  // Sync external seek to video element
  useEffect(() => {
    const video = videoRef.current;
    if (!video || isSeekingInternallyRef.current) return;

    const targetSec =
      previewMode === "edited" && isUsingRenderedArtifact && edl
        ? sourceToEditedTimeMs(currentTimeMs, edl) / 1000
        : currentTimeMs / 1000;

    if (Math.abs(video.currentTime - targetSec) > 0.1) {
      video.currentTime = targetSec;
    }
  }, [currentTimeMs, edl, isUsingRenderedArtifact, previewMode]);

  // Preserve playback position across source switches
  const prevActiveUrlRef = useRef<string | null>(null);
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !activeVideoUrl) return;
    if (prevActiveUrlRef.current && prevActiveUrlRef.current !== activeVideoUrl) {
      const targetSec =
        previewMode === "edited" && isUsingRenderedArtifact && edl
          ? sourceToEditedTimeMs(currentTimeMs, edl) / 1000
          : currentTimeMs / 1000;
      video.currentTime = targetSec;
      if (isPlaying && video.paused) {
        video.play().catch(() => {});
      }
    }
    prevActiveUrlRef.current = activeVideoUrl;
  }, [activeVideoUrl, currentTimeMs, edl, isPlaying, isUsingRenderedArtifact, previewMode]);

  // Handle time update from video element & execute cut skipping
  const handleTimeUpdate = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;

    const currentMs = Math.round(video.currentTime * 1000);

    if (previewMode === "edited" && isUsingRenderedArtifact && edl) {
      const sourceMs = editedToSourceTimeMs(currentMs, edl);
      onSeek(sourceMs);
      return;
    }

    // Client EDL simulation fallback
    if (previewMode === "edited" && !isUsingRenderedArtifact && edl) {
      const skipInterval = findExecutableSkipInterval(currentMs, edl);
      if (skipInterval) {
        const jumpToSec = skipInterval.safe_end_ms / 1000;
        isSeekingInternallyRef.current = true;
        video.currentTime = jumpToSec;
        onSeek(skipInterval.safe_end_ms);

        const skippedSecs = (
          (skipInterval.safe_end_ms - skipInterval.safe_start_ms) /
          1000
        ).toFixed(1);
        setLastSkippedNotice(`Skipped ${skippedSecs}s cut`);
        setTimeout(() => setLastSkippedNotice(null), 2500);

        setTimeout(() => {
          isSeekingInternallyRef.current = false;
        }, 50);
        return;
      }
    }

    onSeek(currentMs);
  }, [edl, onSeek, previewMode, isUsingRenderedArtifact]);

  const handleLoadedMetadata = () => {
    const video = videoRef.current;
    if (!video) return;
    setVideoError(null);
    if (
      previewMode === "original" &&
      video.duration &&
      !isNaN(video.duration) &&
      onDurationChange
    ) {
      onDurationChange(Math.round(video.duration * 1000));
    }
  };

  // Keyboard shortcut listener for spacebar play/pause
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable)
      ) {
        return;
      }

      if (e.code === "Space") {
        e.preventDefault();
        onPlayPause();
      } else if (e.code === "ArrowLeft") {
        e.preventDefault();
        const nextMs = Math.max(0, currentTimeMs - 5000);
        onSeek(nextMs);
      } else if (e.code === "ArrowRight") {
        e.preventDefault();
        const nextMs = Math.min(durationMs, currentTimeMs + 5000);
        onSeek(nextMs);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentTimeMs, durationMs, onPlayPause, onSeek]);

  // Toggle fullscreen
  const handleToggleFullscreen = async () => {
    if (!stageContainerRef.current) return;
    try {
      if (!document.fullscreenElement) {
        await stageContainerRef.current.requestFullscreen();
        setIsFullscreen(true);
      } else {
        await document.exitFullscreen();
        setIsFullscreen(false);
      }
    } catch {
      // Fullscreen not supported or blocked
    }
  };

  const handleRestart = () => {
    onSeek(0);
    if (videoRef.current) {
      videoRef.current.currentTime = 0;
    }
  };

  const progressPercent = activeDurationMs > 0 ? (activeCurrentTimeMs / activeDurationMs) * 100 : 0;

  const handleScrubberClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clickRatio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const targetModeMs = Math.round(clickRatio * activeDurationMs);

    if (previewMode === "edited" && edl) {
      const sourceMs = editedToSourceTimeMs(targetModeMs, edl);
      onSeek(sourceMs);
    } else {
      onSeek(targetModeMs);
    }
  };

  return (
    <div
      ref={stageContainerRef}
      className={`relative flex flex-col bg-surface-1 rounded-xl border border-border-subtle overflow-hidden select-none group shadow-md ${className}`}
      data-testid="video-stage"
    >
      {/* Video Viewport Container */}
      <div className="relative flex-1 min-h-0 bg-black flex items-center justify-center overflow-hidden p-2">
        {activeVideoUrl ? (
          <video
            key={activeVideoUrl || "preview"}
            ref={videoRef}
            src={activeVideoUrl}
            playsInline
            preload="auto"
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            onError={() => setVideoError("Playback stream could not be loaded")}
            className="w-full h-full object-contain max-h-full rounded-lg"
            data-testid="video-element"
          />
        ) : (
          <div className="flex flex-col items-center justify-center text-center p-6 text-text-muted gap-2">
            <p className="text-xs font-medium">Video media is ready for playback.</p>
          </div>
        )}

        {/* Visual B-roll Coverage Overlay */}
        {activeCoverage && (
          <div
            className="absolute top-4 left-4 flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-info/90 text-white text-xs font-semibold backdrop-blur-md shadow-lg transition-all animate-pulse"
            data-testid="active-coverage-overlay"
          >
            <span>
              {activeCoverage.coverage_type === "BROLL_CANDIDATE"
                ? "B-Roll Coverage"
                : "Source Screen Coverage"}
            </span>
          </div>
        )}

        {/* Edited Preview Cut Skipped Toast */}
        {lastSkippedNotice && (
          <div className="absolute top-3 right-3 flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-white text-xs font-semibold shadow-lg animate-bounce">
            <Sparkles className="w-3.5 h-3.5" />
            <span>{lastSkippedNotice}</span>
          </div>
        )}

        {/* Big Center Play/Pause Indicator on hover/pause */}
        {!isPlaying && playbackUrl && !videoError && (
          <button
            type="button"
            onClick={onPlayPause}
            className="absolute inset-0 m-auto w-14 h-14 rounded-full bg-surface-1/80 backdrop-blur-sm border border-border-strong flex items-center justify-center text-text-primary hover:scale-105 hover:bg-surface-2 transition-all shadow-xl"
            aria-label="Play video"
          >
            <Play className="w-6 h-6 text-primary fill-primary translate-x-0.5" />
          </button>
        )}
      </div>

      {/* Scrub Bar & Player Control Toolbar */}
      <div className="bg-surface-2 border-t border-border-subtle px-3 py-2 flex flex-col gap-1.5">
        {/* Playhead Progress Bar */}
        <div
          className="relative w-full h-2 bg-surface-3 rounded-full cursor-pointer overflow-hidden group/scrub"
          onClick={handleScrubberClick}
          role="slider"
          aria-label="Video scrubber"
          aria-valuemin={0}
          aria-valuemax={activeDurationMs}
          aria-valuenow={activeCurrentTimeMs}
          tabIndex={0}
        >
          <div
            className="h-full bg-primary transition-[width] duration-75 group-hover/scrub:bg-primary-hover"
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        {/* Controls Row */}
        <div className="flex items-center justify-between text-xs text-text-secondary">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onPlayPause}
              className="p-1 rounded text-text-primary hover:bg-surface-3 transition-colors"
              title={isPlaying ? "Pause (Space)" : "Play (Space)"}
              aria-label={isPlaying ? "Pause" : "Play"}
            >
              {isPlaying ? (
                <Pause className="w-4 h-4" />
              ) : (
                <Play className="w-4 h-4 fill-current" />
              )}
            </button>

            <button
              type="button"
              onClick={handleRestart}
              className="p-1 rounded text-text-secondary hover:text-text-primary hover:bg-surface-3 transition-colors"
              title="Restart from beginning"
              aria-label="Restart"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>

            {/* Mode-appropriate Timecode Readout */}
            <div className="font-mono text-[11px] text-text-primary font-medium tracking-tight flex items-center gap-1">
              <span>{formatTimecode(activeCurrentTimeMs)}</span>
              <span className="text-text-muted">/</span>
              <span className="text-text-muted">{formatTimecode(activeDurationMs)}</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Audio Mute Toggle */}
            <button
              type="button"
              onClick={() => {
                if (videoRef.current) {
                  videoRef.current.muted = !isMuted;
                  setIsMuted(!isMuted);
                }
              }}
              className="p-1 rounded text-text-secondary hover:text-text-primary hover:bg-surface-3 transition-colors"
              title={isMuted ? "Unmute" : "Mute"}
            >
              {isMuted ? (
                <VolumeX className="w-4 h-4 text-danger" />
              ) : (
                <Volume2 className="w-4 h-4" />
              )}
            </button>

            {/* Fullscreen Toggle */}
            <button
              type="button"
              onClick={handleToggleFullscreen}
              className="p-1 rounded text-text-secondary hover:text-text-primary hover:bg-surface-3 transition-colors"
              title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
            >
              {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
