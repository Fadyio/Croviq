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
  type EditDecisionList,
  type CoverageMarker,
} from "../../lib/edl-adapter";
import type { PreviewMode } from "./PreviewToggle";

interface VideoStageProps {
  playbackUrl: string | null;
  renderedPreviewUrl?: string | null;
  currentTimeMs: number;
  durationMs: number;
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
  currentTimeMs,
  durationMs,
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

  // Sync external seek (e.g. from timeline scrub or transcript click) to video
  useEffect(() => {
    const video = videoRef.current;
    if (!video || isSeekingInternallyRef.current) return;

    const currentSec = video.currentTime;
    const targetSec = currentTimeMs / 1000;

    // Only update if difference is greater than 100ms to avoid feedback loops
    if (Math.abs(currentSec - targetSec) > 0.1) {
      video.currentTime = targetSec;
    }
  }, [currentTimeMs]);

  const isUsingRenderedArtifact = previewMode === "edited" && Boolean(renderedPreviewUrl);
  const activeVideoUrl = isUsingRenderedArtifact ? renderedPreviewUrl : playbackUrl;

  // Preserve playback position across source switches (e.g. Original vs Edited Preview)
  const prevActiveUrlRef = useRef<string | null>(null);
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !activeVideoUrl) return;
    if (prevActiveUrlRef.current && prevActiveUrlRef.current !== activeVideoUrl) {
      const targetSec = currentTimeMs / 1000;
      video.currentTime = targetSec;
      if (isPlaying && video.paused) {
        video.play().catch(() => {});
      }
    }
    prevActiveUrlRef.current = activeVideoUrl;
  }, [activeVideoUrl, currentTimeMs, isPlaying]);

  // Handle time update from video element & execute Edited Preview cut skipping
  const handleTimeUpdate = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;

    const currentMs = Math.round(video.currentTime * 1000);

    // If Edited Preview is active and falling back to client simulation (no real render yet)
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
  // Handle loaded metadata for duration
  const handleLoadedMetadata = () => {
    const video = videoRef.current;
    if (!video) return;
    setVideoError(null);
    if (video.duration && !isNaN(video.duration) && onDurationChange) {
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

  // Restart video from beginning
  const handleRestart = () => {
    onSeek(0);
    if (videoRef.current) {
      videoRef.current.currentTime = 0;
    }
  };

  const progressPercent = durationMs > 0 ? (currentTimeMs / durationMs) * 100 : 0;

  return (
    <div
      ref={stageContainerRef}
      className={`relative flex flex-col bg-surface-1 rounded-xl border border-border-subtle overflow-hidden select-none group shadow-md ${className}`}
      data-testid="video-stage"
    >
      {/* Video Viewport Container */}
      <div className="relative flex-1 min-h-0 bg-black flex items-center justify-center overflow-hidden">
        {activeVideoUrl ? (
          <video
            ref={videoRef}
            src={activeVideoUrl}
            playsInline
            crossOrigin="anonymous"
            className="w-full h-full object-contain max-h-full"
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            onEnded={() => onPlayPause()}
            onError={() => {
              setVideoError("Unable to load video stream from signed storage URL");
            }}
            onClick={onPlayPause}
          />
        ) : (
          <div className="flex flex-col items-center justify-center gap-3 p-8 text-center text-text-muted">
            <div className="w-12 h-12 rounded-full bg-surface-2 flex items-center justify-center border border-border-subtle">
              <Play className="w-6 h-6 text-text-secondary translate-x-0.5" />
            </div>
            <p className="text-xs text-text-secondary font-medium">
              Source video ready for playback
            </p>
          </div>
        )}

        {/* Rendered Preview Active Badge Overlay */}
        {isUsingRenderedArtifact && (
          <div
            className="absolute top-3 left-3 flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-surface-1/90 backdrop-blur-md text-text-primary text-[11px] font-medium shadow-md border border-border-subtle"
            data-testid="rendered-preview-badge"
          >
            <span className="size-1.5 rounded-full bg-success" />
            <span>Rendered Preview</span>
          </div>
        )}
        {/* Video Loading or Network Error Overlay */}
        {videoError && (
          <div className="absolute inset-0 bg-surface-1/90 flex flex-col items-center justify-center p-6 text-center gap-2">
            <p className="text-xs text-danger font-medium">{videoError}</p>
            <p className="text-[11px] text-text-muted">
              Check that CORS GET permissions are active on the private storage bucket.
            </p>
          </div>
        )}

        {/* Active B-Roll Coverage Badge Overlay */}
        {activeCoverage && (
          <div
            className="absolute top-3 left-3 flex items-center gap-2 px-3 py-1.5 rounded-md bg-info/90 backdrop-blur-md text-white text-xs font-medium shadow-lg border border-info/40 animate-fade-in"
            data-testid="active-coverage-overlay"
          >
            <Layers className="w-3.5 h-3.5 text-white animate-pulse shrink-0" />
            <span>
              B-Roll Coverage Active &middot; {formatTimecode(activeCoverage.source_start_ms)}{" "}
              &rarr; {formatTimecode(activeCoverage.source_end_ms)}
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
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const clickRatio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            onSeek(Math.round(clickRatio * durationMs));
          }}
          role="slider"
          aria-label="Video scrubber"
          aria-valuemin={0}
          aria-valuemax={durationMs}
          aria-valuenow={currentTimeMs}
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

            {/* Timecode Readout */}
            <div className="font-mono text-[11px] text-text-primary font-medium tracking-tight flex items-center gap-1">
              <span>{formatTimecode(currentTimeMs)}</span>
              <span className="text-text-muted">/</span>
              <span className="text-text-muted">{formatTimecode(durationMs)}</span>
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
