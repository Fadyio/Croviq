import {
  AlertCircle,
  Film,
  Loader2,
  Maximize2,
  Minimize2,
  Pause,
  Play,
  RotateCcw,
  Volume2,
  VolumeX,
} from "lucide-react";
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  type CanonicalMediaOutputs,
  type CoverageMarker,
  type EditDecisionList,
  editedToSourceTimeMs,
  formatTimecode,
  sourceToEditedTimeMs,
} from "../../lib/edl-adapter";
import type { PreviewMode } from "./PreviewToggle";

interface VideoStageProps {
  playbackUrl: string | null;
  renderedPreviewUrl?: string | null;
  studioVoicePreviewUrl?: string | null;
  finalMixUrl?: string | null;
  mediaOutputs?: CanonicalMediaOutputs;
  currentTimeMs: number;
  durationMs: number;
  editedDurationMs?: number;
  studioVoiceDurationMs?: number | null;
  finalMixDurationMs?: number | null;
  isPlaying: boolean;
  previewMode: PreviewMode;
  edl: EditDecisionList | null;
  activeCoverage: CoverageMarker | null;
  onPlayPause: () => void;
  onSeek: (targetMs: number) => void;
  onDurationChange?: (durationMs: number) => void;
  onRetryPlayback?: () => Promise<void> | void;
  onRenderFinalMix?: () => Promise<void> | void;
  isRenderingFinalMix?: boolean;
  className?: string;
}
export const VideoStage: React.FC<VideoStageProps> = ({
  playbackUrl,
  renderedPreviewUrl,
  studioVoicePreviewUrl,
  finalMixUrl,
  mediaOutputs,
  currentTimeMs,
  durationMs,
  editedDurationMs,
  studioVoiceDurationMs,
  finalMixDurationMs,
  isPlaying,
  previewMode,
  edl,
  activeCoverage,
  onPlayPause,
  onSeek,
  onDurationChange,
  onRetryPlayback,
  onRenderFinalMix,
  isRenderingFinalMix = false,
  className = "",
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const stageContainerRef = useRef<HTMLDivElement>(null);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [videoError, setVideoError] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState<boolean>(false);
  const isSeekingInternallyRef = useRef<boolean>(false);

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

  const isEdlDerivedMode =
    previewMode === "edited" || previewMode === "studio_voice" || previewMode === "final_mix";

  const currentOutput = mediaOutputs
    ? previewMode === "original"
      ? mediaOutputs.original
      : previewMode === "edited"
        ? mediaOutputs.edited
        : previewMode === "studio_voice"
          ? mediaOutputs.voiceover
          : mediaOutputs.final_mix
    : null;

  const activeVideoUrl = currentOutput
    ? currentOutput.available
      ? currentOutput.url ||
        (previewMode === "edited" || previewMode === "original" ? playbackUrl : null)
      : null
    : previewMode === "final_mix"
      ? finalMixUrl || null
      : previewMode === "studio_voice"
        ? studioVoicePreviewUrl || null
        : previewMode === "edited"
          ? renderedPreviewUrl || playbackUrl || null
          : playbackUrl || null;
  // Clear error state on media source or preview mode change
  useEffect(() => {
    if (activeVideoUrl || previewMode) {
      setVideoError(null);
    }
  }, [activeVideoUrl, previewMode]);
  const outputStatus = currentOutput
    ? currentOutput.status
    : activeVideoUrl
      ? "ready"
      : "unavailable";

  const modeLabel =
    previewMode === "original"
      ? "Original"
      : previewMode === "edited"
        ? "Edited Preview"
        : previewMode === "studio_voice"
          ? "Voiceover Preview"
          : "Final Mix";

  const activeDurationMs =
    currentOutput?.available && currentOutput.durationMs > 0
      ? currentOutput.durationMs
      : previewMode === "final_mix"
        ? finalMixDurationMs || studioVoiceDurationMs || editedDurationMs || durationMs
        : previewMode === "studio_voice"
          ? studioVoiceDurationMs || editedDurationMs || durationMs
          : previewMode === "edited"
            ? editedDurationMs || durationMs
            : durationMs;

  const activeCurrentTimeMs =
    isEdlDerivedMode && edl ? sourceToEditedTimeMs(currentTimeMs, edl) : currentTimeMs;

  // Sync external seek to video element
  useEffect(() => {
    const video = videoRef.current;
    if (!video || isSeekingInternallyRef.current) return;

    const targetSec =
      isEdlDerivedMode && edl
        ? sourceToEditedTimeMs(currentTimeMs, edl) / 1000
        : currentTimeMs / 1000;

    if (Math.abs(video.currentTime - targetSec) > 0.1) {
      video.currentTime = targetSec;
    }
  }, [currentTimeMs, edl, isEdlDerivedMode]);
  // Preserve playback position across source switches
  const prevActiveUrlRef = useRef<string | null>(null);
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !activeVideoUrl) return;
    if (prevActiveUrlRef.current && prevActiveUrlRef.current !== activeVideoUrl) {
      const targetSec =
        isEdlDerivedMode && edl
          ? sourceToEditedTimeMs(currentTimeMs, edl) / 1000
          : currentTimeMs / 1000;
      video.currentTime = targetSec;
      if (isPlaying && video.paused) {
        video.play().catch(() => {});
      }
    }
    prevActiveUrlRef.current = activeVideoUrl;
  }, [activeVideoUrl, currentTimeMs, edl, isPlaying, isEdlDerivedMode]);

  // Handle time update from video element & execute cut skipping
  const handleTimeUpdate = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;

    const currentMs = Math.round(video.currentTime * 1000);

    if (isEdlDerivedMode && edl) {
      const sourceMs = editedToSourceTimeMs(currentMs, edl);
      onSeek(sourceMs);
      return;
    }

    onSeek(currentMs);
  }, [edl, onSeek, isEdlDerivedMode]);
  const handleLoadedMetadata = () => {
    const video = videoRef.current;
    if (!video) return;
    setVideoError(null);
    if (
      previewMode === "original" &&
      video.duration &&
      !Number.isNaN(video.duration) &&
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
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

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

    if (isEdlDerivedMode && edl) {
      const sourceMs = editedToSourceTimeMs(targetModeMs, edl);
      onSeek(sourceMs);
    } else {
      onSeek(targetModeMs);
    }
  };
  const handleScrubberKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    let target = activeCurrentTimeMs;
    if (e.key === "ArrowLeft") {
      target = Math.max(0, activeCurrentTimeMs - 5000);
    } else if (e.key === "ArrowRight") {
      target = Math.min(activeDurationMs, activeCurrentTimeMs + 5000);
    } else if (e.key === "Home") {
      target = 0;
    } else if (e.key === "End") {
      target = activeDurationMs;
    } else {
      return;
    }
    e.preventDefault();
    if (isEdlDerivedMode && edl) {
      const sourceMs = editedToSourceTimeMs(target, edl);
      onSeek(sourceMs);
    } else {
      onSeek(target);
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
          <div
            className="flex flex-col items-center justify-center text-center p-6 text-text-muted gap-3 max-w-sm"
            data-testid="media-unavailable-card"
          >
            {outputStatus === "generating" ? (
              <>
                <Loader2 className="size-8 text-primary animate-spin" />
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-text-primary">
                    {modeLabel} is generating…
                  </p>
                  <p className="text-[11px] text-text-secondary">
                    Rendering artifact for active timeline.
                  </p>
                </div>
              </>
            ) : outputStatus === "failed" ? (
              <>
                <AlertCircle className="size-8 text-danger" />
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-danger">{modeLabel} failed</p>
                  <p className="text-[11px] text-text-secondary">
                    Could not render the requested output artifact.
                  </p>
                </div>
              </>
            ) : outputStatus === "needs_regeneration" ? (
              <>
                <RotateCcw className="size-8 text-purple-400" />
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-text-primary">{modeLabel} needs rebuild</p>
                  <p className="text-[11px] text-text-secondary">
                    Timeline cuts, voiceover narration, or music settings changed since last render.
                  </p>
                </div>
                {previewMode === "final_mix" && onRenderFinalMix && (
                  <button
                    type="button"
                    onClick={() => onRenderFinalMix()}
                    disabled={isRenderingFinalMix}
                    className="mt-1 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-semibold text-xs transition-all shadow-sm flex items-center gap-1.5 cursor-pointer"
                    data-testid="btn-rebuild-final-mix"
                  >
                    {isRenderingFinalMix ? (
                      <>
                        <Loader2 className="size-3 animate-spin" />
                        <span>Rendering Final Mix…</span>
                      </>
                    ) : (
                      <>
                        <RotateCcw className="size-3" />
                        <span>Rebuild Final Mix</span>
                      </>
                    )}
                  </button>
                )}
              </>
            ) : (
              <>
                <Film className="size-8 text-text-muted/60" />
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-text-primary">{modeLabel} unavailable</p>
                  <p className="text-[11px] text-text-secondary">
                    No rendered artifact exists for this mode on the active timeline.
                  </p>
                </div>
                {previewMode === "final_mix" && onRenderFinalMix && (
                  <button
                    type="button"
                    onClick={() => onRenderFinalMix()}
                    disabled={isRenderingFinalMix}
                    className="mt-1 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-semibold text-xs transition-all shadow-sm flex items-center gap-1.5 cursor-pointer"
                    data-testid="btn-render-final-mix"
                  >
                    {isRenderingFinalMix ? (
                      <>
                        <Loader2 className="size-3 animate-spin" />
                        <span>Rendering Final Mix…</span>
                      </>
                    ) : (
                      <>
                        <Film className="size-3" />
                        <span>Render Final Mix</span>
                      </>
                    )}
                  </button>
                )}
              </>
            )}
          </div>
        )}

        {/* Video Error Message Overlay if signed URL fails */}
        {videoError && (
          <div
            className="absolute inset-0 m-auto max-w-sm h-fit bg-surface-1/95 border border-danger/40 rounded-xl p-4 flex flex-col items-center text-center gap-2.5 shadow-2xl backdrop-blur-sm z-20"
            data-testid="video-error-overlay"
          >
            <AlertCircle className="size-6 text-danger" />
            <p className="text-xs font-semibold text-danger">{videoError}</p>
            <p className="text-[11px] text-text-secondary">
              The signed media URL could not be played or has expired.
            </p>
            {onRetryPlayback && (
              <button
                onClick={async () => {
                  setIsRetrying(true);
                  setVideoError(null);
                  try {
                    await onRetryPlayback();
                    if (videoRef.current) {
                      videoRef.current.load();
                    }
                  } finally {
                    setIsRetrying(false);
                  }
                }}
                className="mt-1 px-3 py-1.5 rounded-lg bg-surface-3 hover:bg-surface-2 border border-border-subtle text-xs font-medium text-text-primary transition-colors flex items-center gap-1.5 disabled:opacity-60"
                data-testid="retry-playback-button"
              >
                {isRetrying ? (
                  <>
                    <Loader2 className="size-3 animate-spin text-primary" />
                    <span>Renewing URL…</span>
                  </>
                ) : (
                  <>
                    <RotateCcw className="size-3" />
                    <span>Reload Playback</span>
                  </>
                )}
              </button>
            )}
          </div>
        )}

        {/* Visual Screen Coverage Overlay */}
        {activeCoverage && (
          <div
            className="absolute top-4 left-4 flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-info/90 text-white text-xs font-semibold backdrop-blur-md shadow-lg transition-all animate-pulse"
            data-testid="active-coverage-overlay"
          >
            <span>Source Screen Coverage</span>
          </div>
        )}

        {/* Big Center Play/Pause Indicator on hover/pause */}
        {!isPlaying && activeVideoUrl && !videoError && (
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
          className="relative w-full h-2 bg-surface-3 rounded-full cursor-pointer overflow-hidden group/scrub focus:outline-none focus:ring-2 focus:ring-primary"
          onClick={handleScrubberClick}
          onKeyDown={handleScrubberKeyDown}
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
            <div
              className="font-mono text-[11px] text-text-primary font-medium tracking-tight flex items-center gap-1"
              data-testid="timecode-display"
            >
              <span data-testid="timecode-current">{formatTimecode(activeCurrentTimeMs)}</span>
              <span className="text-text-muted">/</span>
              <span className="text-text-muted" data-testid="timecode-duration">
                {formatTimecode(activeDurationMs)}
              </span>
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
              aria-label={isMuted ? "Unmute audio" : "Mute audio"}
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
              aria-label={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
            >
              {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
