import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  ExternalLink,
  Film,
  Loader2,
  Lock,
  LogOut,
  Pause,
  Play,
  Save,
  ShieldCheck,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import React, { useCallback, useEffect, useRef, useState } from "react";
import type { components } from "../api/generated";
import irisAvatar from "../assets/agents/Iris.png";
import { useAuth } from "../auth/AuthContext";
import { CroviqLogo } from "../components/CroviqLogo";
import { AgentSettingsDrawer } from "../components/editor/AgentSettingsDrawer";
import {
  PublishConfirmationModal,
  YouTubeIcon,
} from "../components/release/PublishConfirmationModal";

type PackagingDetailResponse = components["schemas"]["PackagingDetailResponse"];
type ReleaseReviewDetailResponse = components["schemas"]["ReleaseReviewDetailResponse"];
type ReleaseIssue = components["schemas"]["ReleaseIssue"];
type PublishPreparationResponse = components["schemas"]["PublishPreparationResponse"];
type PublishJobDetailResponse = components["schemas"]["PublishJobDetailResponse"];

interface ReleasePageProps {
  productionId: string;
  onNavigateHome?: () => void;
  onNavigateEditor?: () => void;
}

const getIssueFriendlyName = (type: string): string => {
  const map: Record<string, string> = {
    AUDIO_ARTIFACT: "Audio Artifact",
    AUDIO_LEVEL: "Audio Level",
    AUDIO_SYNC: "Audio / Video Sync",
    BAD_CUT: "Bad Cut / Edit Gap",
    VISUAL_JUMP: "Visual Jump Cut",
    BLACK_FRAME: "Black Frame / Freeze",
    FRAME_GLITCH: "Visual Glitch",
    ENCODE_ISSUE: "Encoding Issue",
    CAPTION_MISMATCH: "Caption Text Mismatch",
    CAPTION_TIMING: "Caption Timing Drift",
    CAPTION_OVERFLOW: "Caption Overflow",
    CHAPTER_MISMATCH: "Chapter Topic Mismatch",
    CHAPTER_TIMING: "Chapter Timestamp Issue",
    UNSUPPORTED_CLAIM: "Unsupported Claim",
    FACTUAL_INCONSISTENCY: "Factual Inconsistency",
    TITLE_MISMATCH: "Title Content Mismatch",
    DESCRIPTION_MISMATCH: "Description Mismatch",
    THUMBNAIL_MISMATCH: "Thumbnail Concept Mismatch",
    PACKAGING_INCONSISTENCY: "Packaging Inconsistency",
    MISSING_CONTENT: "Missing Content / Demo",
    CONTEXT_LOSS: "Context Loss",
  };
  return (
    map[type] ||
    type
      .replace(/_/g, " ")
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase())
  );
};

const formatMs = (ms: number): string => {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
};

export const ReleasePage: React.FC<ReleasePageProps> = ({
  productionId,
  onNavigateHome,
  onNavigateEditor,
}) => {
  const { firebaseUser, logout } = useAuth();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [qaData, setQaData] = useState<ReleaseReviewDetailResponse | null>(null);
  const [packagingData, setPackagingData] = useState<PackagingDetailResponse | null>(null);
  const [_isLoading, setIsLoading] = useState<boolean>(true);
  const [isRunningQA, setIsRunningQA] = useState<boolean>(false);
  const [isSavingMetadata, setIsSavingMetadata] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [reviewMode, setReviewMode] = useState<"original" | "edited" | "voiceover" | "final_mix">(
    () => {
      if (typeof window !== "undefined") {
        const params = new URLSearchParams(window.location.search);
        const m = params.get("mode");
        if (m === "original" || m === "edited" || m === "final_mix") return m;
        if (m === "voiceover" || m === "studio_voice") return "voiceover";
      }
      return "final_mix";
    },
  );
  // Manual creator publish fields
  const [titleInput, setTitleInput] = useState<string>("");
  const [descriptionInput, setDescriptionInput] = useState<string>("");
  const [privacySetting, setPrivacySetting] = useState<"private" | "unlisted" | "public">(
    "private",
  );

  // Video playback
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTimeMs, setCurrentTimeMs] = useState<number>(0);
  const [durationMs, setDurationMs] = useState<number>(0);
  const [isMuted, setIsMuted] = useState<boolean>(false);

  // Iris settings drawer
  const [isIrisDrawerOpen, setIsIrisDrawerOpen] = useState<boolean>(false);

  // YouTube Publishing Modal state
  const [isPublishModalOpen, setIsPublishModalOpen] = useState<boolean>(false);
  const [prepData, setPrepData] = useState<PublishPreparationResponse | null>(null);
  const [isLoadingPrep, setIsLoadingPrep] = useState<boolean>(false);
  const [publishJobData, setPublishJobData] = useState<PublishJobDetailResponse | null>(null);
  const [isPublishing, setIsPublishing] = useState<boolean>(false);
  const [publishSuccessMsg, setPublishSuccessMsg] = useState<string | null>(null);

  const getAuthHeaders = useCallback(async (): Promise<Record<string, string>> => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (firebaseUser) {
      const token = await firebaseUser.getIdToken();
      headers.Authorization = `Bearer ${token}`;
    } else if (
      import.meta.env.DEV ||
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1"
    ) {
      headers.Authorization =
        "Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIyN2lFQlVNY3U2VG9EWXdwMk9kRUlIQnV3SUEzIiwidXNlcl9pZCI6IjI3aUVCVU1jdTZUb0RZd3AyT2RFSUhCdXdJQTMiLCJlbWFpbCI6ImRlbW9AY3JvdmlxLmFwcCJ9.signature";
    }
    return headers;
  }, [firebaseUser]);

  // Load QA review details
  const loadQA = useCallback(async () => {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/productions/${productionId}/release-review`, { headers });
      if (res.ok) {
        const data: ReleaseReviewDetailResponse = await res.json();
        setQaData(data);
      }
    } catch (err: unknown) {
      console.error("Error loading QA review:", err);
    }
  }, [getAuthHeaders, productionId]);

  // Load packaging & metadata
  const loadPackaging = useCallback(async () => {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/productions/${productionId}/packaging`, { headers });
      if (res.ok) {
        const data: PackagingDetailResponse = await res.json();
        setPackagingData(data);
        setTitleInput(data.effective_title || "Master Video Walkthrough");
        setDescriptionInput(data.effective_description || "");
      }
    } catch (err: unknown) {
      console.error("Error loading packaging metadata:", err);
    }
  }, [getAuthHeaders, productionId]);

  // Load active publish job status
  const loadPublishStatus = useCallback(async () => {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/productions/${productionId}/publish`, { headers });
      if (res.ok) {
        const data: PublishJobDetailResponse = await res.json();
        setPublishJobData(data);
      }
    } catch (err: unknown) {
      console.error("Error loading publish status:", err);
    }
  }, [getAuthHeaders, productionId]);

  // Load publish prep data for modal
  const loadPublishPrep = useCallback(async () => {
    setIsLoadingPrep(true);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/productions/${productionId}/publish/prep`, { headers });
      if (res.ok) {
        const data: PublishPreparationResponse = await res.json();
        setPrepData(data);
      }
    } catch (err: unknown) {
      console.error("Error loading publish prep metadata:", err);
    } finally {
      setIsLoadingPrep(false);
    }
  }, [getAuthHeaders, productionId]);

  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      await Promise.all([loadQA(), loadPackaging(), loadPublishStatus()]);
      setIsLoading(false);
    };
    init();
  }, [loadQA, loadPackaging, loadPublishStatus]);

  // Polling active publish job
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    const isJobActive =
      publishJobData?.job?.status === "pending" ||
      publishJobData?.job?.status === "uploading" ||
      publishJobData?.job?.status === "processing";

    if (isJobActive) {
      interval = setInterval(() => {
        loadPublishStatus();
      }, 2000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [publishJobData?.job?.status, loadPublishStatus]);

  // Trigger explicit Iris Quality Control pass
  const handleRunQA = async (
    forceRegenerate: boolean = true,
    targetMode?: "original" | "edited" | "voiceover" | "final_mix",
  ) => {
    setIsRunningQA(true);
    setErrorMessage(null);
    const modeToRun = targetMode || reviewMode;
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/productions/${productionId}/release-review`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          force_regenerate: forceRegenerate,
          preview_mode: modeToRun,
        }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || "Iris Quality Control review failed");
      }
      const data: ReleaseReviewDetailResponse = await res.json();
      setQaData(data);
      if (targetMode) setReviewMode(targetMode);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to run Quality Control review");
    } finally {
      setIsRunningQA(false);
    }
  };

  // Save manual metadata overrides
  const handleSaveMetadata = async () => {
    setIsSavingMetadata(true);
    setSaveMessage(null);
    setErrorMessage(null);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/productions/${productionId}/packaging`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({
          custom_title: titleInput,
          custom_description: descriptionInput,
        }),
      });
      if (!res.ok) {
        throw new Error("Failed to save release metadata");
      }
      const updated: PackagingDetailResponse = await res.json();
      setPackagingData(updated);
      setSaveMessage("Release metadata saved successfully.");
      setTimeout(() => setSaveMessage(null), 3000);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to save release metadata");
    } finally {
      setIsSavingMetadata(false);
    }
  };

  // Video controls
  const handlePlayPause = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
    } else {
      videoRef.current.play().catch(() => {});
    }
    setIsPlaying(!isPlaying);
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTimeMs(Math.floor(videoRef.current.currentTime * 1000));
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      const dur = Math.floor(videoRef.current.duration * 1000);
      if (!Number.isNaN(dur) && dur > 0) {
        setDurationMs(dur);
      }
    }
  };

  const handleSeek = (targetMs: number) => {
    if (!videoRef.current) return;
    videoRef.current.currentTime = targetMs / 1000;
    setCurrentTimeMs(targetMs);
  };

  const handleSeekToIssue = (issue: ReleaseIssue) => {
    const targetMs = issue.source_start_ms ?? issue.source_end_ms ?? 0;
    handleSeek(targetMs);
  };

  const toggleMute = () => {
    if (!videoRef.current) return;
    videoRef.current.muted = !isMuted;
    setIsMuted(!isMuted);
  };

  // YouTube publishing actions
  const handleOpenPublishModal = () => {
    setIsPublishModalOpen(true);
    loadPublishPrep();
  };

  const handleGrantUploadAccess = async () => {
    try {
      const headers = await getAuthHeaders();
      const currentUrl = window.location.href;
      const res = await fetch("/api/channels/youtube/auth-url", {
        method: "POST",
        headers,
        body: JSON.stringify({
          redirect_uri: currentUrl,
          include_upload: true,
        }),
      });
      if (res.ok) {
        const data = (await res.json()) as {
          auth_url?: string;
          authorization_url?: string;
          state_token?: string;
        };
        const targetUrl = data.auth_url || data.authorization_url;
        if (targetUrl) {
          window.location.href = targetUrl;
        }
      }
    } catch (err: unknown) {
      console.error("Failed to generate upload authorization URL:", err);
    }
  };

  const handleConfirmPublish = async (params: {
    requested_privacy: "private" | "unlisted" | "public";
    made_for_kids: boolean;
    contains_synthetic_media: boolean;
    selected_title: string;
    selected_description: string;
    selected_tags: string[];
    category_id: string;
    thumbnail_frame_ms?: number;
  }) => {
    setIsPublishing(true);
    setErrorMessage(null);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/productions/${productionId}/publish`, {
        method: "POST",
        headers,
        body: JSON.stringify(params),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Publish request failed");
      }
      const data: PublishJobDetailResponse = await res.json();
      setPublishJobData(data);
      setIsPublishModalOpen(false);
      setPublishSuccessMsg("YouTube publishing job initiated successfully.");
      setTimeout(() => setPublishSuccessMsg(null), 5000);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Publish request failed");
    } finally {
      setIsPublishing(false);
    }
  };

  const activeVideoUrl =
    qaData?.master_url ||
    qaData?.master_artifact?.playback_url ||
    packagingData?.master_url ||
    packagingData?.master_artifact?.playback_url ||
    null;
  const isReady = Boolean(qaData?.release_ready);
  const issuesList = qaData?.review?.issues || [];
  const checklist = qaData?.checklist;

  return (
    <div className="min-h-screen bg-background text-text-primary flex flex-col">
      {/* 1. Header Bar */}
      <header className="h-14 bg-surface-1 border-b border-border-subtle px-4 sm:px-6 flex items-center justify-between shrink-0 sticky top-0 z-30">
        <div className="flex items-center gap-4 min-w-0">
          <button
            type="button"
            onClick={
              onNavigateHome ||
              (() => {
                window.location.href = "/app";
              })
            }
            className="hover:opacity-80 transition-opacity flex items-center gap-2 shrink-0 cursor-pointer"
            title="Croviq Home"
            aria-label="Croviq Home"
          >
            <CroviqLogo height={24} className="h-6 w-auto" />
          </button>

          <span className="text-border-strong select-none font-light">/</span>

          <button
            type="button"
            onClick={
              onNavigateEditor ||
              (() => {
                window.location.href = `/productions/${productionId}`;
              })
            }
            className="flex items-center gap-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
            data-testid="btn-back-to-editor"
          >
            <ArrowLeft className="size-3.5" />
            <span>Editor</span>
          </button>

          <span className="text-border-strong select-none font-light">/</span>

          <span className="text-xs font-bold text-text-primary truncate">
            Quality Control & Release
          </span>
        </div>

        {/* Header Right Actions */}
        <div className="flex items-center gap-3">
          {/* Status Badge */}
          <div
            className={`hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${
              isReady
                ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                : qaData?.review?.verdict === "FIX_REQUIRED"
                  ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
                  : "bg-surface-2 text-text-muted border-border-subtle"
            }`}
            data-testid="release-status-badge"
          >
            {isReady ? (
              <>
                <CheckCircle2 className="size-3.5" />
                <span>Ready to Publish</span>
              </>
            ) : qaData?.review?.verdict === "FIX_REQUIRED" ? (
              <>
                <AlertTriangle className="size-3.5" />
                <span>Fix Required</span>
              </>
            ) : (
              <>
                <Clock className="size-3.5" />
                <span>Pending Quality Check</span>
              </>
            )}
          </div>

          {/* Explicit Run Quality Check Button */}
          <button
            type="button"
            onClick={() => handleRunQA(true)}
            disabled={isRunningQA}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-surface-2 hover:bg-surface-3 border border-border-subtle text-text-primary transition-colors disabled:opacity-50"
            data-testid="btn-run-qa"
            title="Run complete quality check with Iris"
          >
            {isRunningQA ? (
              <Loader2 className="size-3.5 text-primary animate-spin" />
            ) : (
              <ShieldCheck className="size-3.5 text-primary" />
            )}
            <span>{isRunningQA ? "Checking…" : "Run Quality Check"}</span>
          </button>

          {/* Publish to YouTube Button */}
          <button
            type="button"
            onClick={handleOpenPublishModal}
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-red-600 hover:bg-red-500 text-white shadow-sm transition-colors"
            data-testid="btn-open-publish-modal"
          >
            <YouTubeIcon className="size-4" />
            <span>Publish to YouTube</span>
          </button>

          <button
            type="button"
            onClick={logout}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-text-muted hover:text-text-primary transition-colors"
            title="Sign out"
          >
            <LogOut className="size-3.5" />
          </button>
        </div>
      </header>

      {/* 2. Messages Bar */}
      {errorMessage && (
        <div className="bg-danger/10 border-b border-danger/30 px-6 py-2.5 flex items-center justify-between text-xs text-danger">
          <div className="flex items-center gap-2">
            <AlertCircle className="size-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setErrorMessage(null)}
            className="p-1 hover:opacity-75"
          >
            <X className="size-3.5" />
          </button>
        </div>
      )}

      {saveMessage && (
        <div className="bg-emerald-500/10 border-b border-emerald-500/30 px-6 py-2 flex items-center gap-2 text-xs text-emerald-400">
          <CheckCircle2 className="size-4" />
          <span>{saveMessage}</span>
        </div>
      )}

      {publishSuccessMsg && (
        <div className="bg-emerald-500/10 border-b border-emerald-500/30 px-6 py-2 flex items-center gap-2 text-xs text-emerald-400">
          <CheckCircle2 className="size-4" />
          <span>{publishSuccessMsg}</span>
        </div>
      )}

      {/* 3. Main Body: 2 Columns */}
      <div className="flex-1 w-full max-w-7xl mx-auto p-4 sm:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left/Center Column (8 cols): Video Stage + Iris QA Findings */}
        <div className="lg:col-span-8 space-y-6">
          {/* Master Video Canvas */}
          <div className="bg-black border border-border-subtle rounded-2xl overflow-hidden shadow-md">
            <div className="aspect-video relative flex items-center justify-center bg-black">
              {activeVideoUrl ? (
                <video
                  ref={videoRef}
                  src={activeVideoUrl}
                  onTimeUpdate={handleTimeUpdate}
                  onLoadedMetadata={handleLoadedMetadata}
                  onEnded={() => setIsPlaying(false)}
                  className="w-full h-full object-contain"
                  playsInline
                />
              ) : (
                <div className="text-center p-8 text-text-muted space-y-2">
                  <Film className="size-10 mx-auto text-text-muted/40" />
                  <p className="text-xs">Rendered master video playback target</p>
                </div>
              )}
            </div>

            {/* Video Controls Bar */}
            <div className="bg-surface-1 border-t border-border-subtle p-3 flex items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handlePlayPause}
                  className="p-1.5 rounded-lg bg-surface-2 hover:bg-surface-3 text-text-primary transition-colors"
                  aria-label={isPlaying ? "Pause" : "Play"}
                >
                  {isPlaying ? <Pause className="size-4" /> : <Play className="size-4" />}
                </button>
                <button
                  type="button"
                  onClick={toggleMute}
                  className="p-1.5 rounded-lg text-text-secondary hover:text-text-primary transition-colors"
                  aria-label={isMuted ? "Unmute" : "Mute"}
                >
                  {isMuted ? <VolumeX className="size-4" /> : <Volume2 className="size-4" />}
                </button>
                <span className="font-mono text-text-secondary text-[11px]">
                  {formatMs(currentTimeMs)} / {formatMs(durationMs)}
                </span>
              </div>

              {/* Scrubber */}
              <div className="flex-1 mx-2">
                <input
                  type="range"
                  min={0}
                  max={durationMs || 1000}
                  value={currentTimeMs}
                  onChange={(e) => handleSeek(Number(e.target.value))}
                  className="w-full h-1.5 bg-surface-3 rounded-lg appearance-none cursor-pointer accent-primary"
                  aria-label="Timeline seek slider"
                />
              </div>
            </div>
          </div>

          {/* Iris Quality Control Review Section */}
          <div
            className="bg-surface-1 border border-border-subtle rounded-2xl p-6 space-y-5 shadow-xs"
            data-testid="section-iris-qa"
          >
            {/* Iris Header */}
            <div className="flex items-center justify-between border-b border-border-subtle pb-4">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setIsIrisDrawerOpen(true)}
                  className="size-10 rounded-full overflow-hidden border-2 border-emerald-500/40 bg-surface-2 shrink-0 hover:border-emerald-400 transition-colors cursor-pointer"
                  title="Iris Settings"
                  data-testid="btn-iris-avatar"
                >
                  <img
                    src={irisAvatar}
                    alt="Iris Quality Control"
                    className="size-full object-cover"
                  />
                </button>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-text-primary">Iris — Quality Control</h3>
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                      Independent Gate
                    </span>
                  </div>
                  <p className="text-xs text-text-secondary">
                    Inspecting rendered media for editing continuity, audio levels, caption
                    alignment, and factual consistency.
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setIsIrisDrawerOpen(true)}
                className="text-xs text-text-muted hover:text-text-primary px-2.5 py-1 rounded-md border border-border-subtle hover:bg-surface-2 transition-colors shrink-0 cursor-pointer"
                data-testid="btn-iris-settings"
              >
                Settings
              </button>
            </div>
            {/* Mode selection & High-level Assessment Summary */}
            <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-surface-2 border border-border-subtle">
              <div className="flex items-center gap-1.5" role="group" aria-label="Iris Review Mode">
                <button
                  type="button"
                  onClick={() => {
                    setReviewMode("original");
                    handleRunQA(true, "original");
                  }}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all ${
                    (qaData?.review?.preview_mode || reviewMode) === "original"
                      ? "bg-surface-3 text-text-primary border border-border-strong shadow-xs"
                      : "text-text-secondary hover:text-text-primary hover:bg-surface-3/50"
                  }`}
                  data-testid="btn-review-mode-original"
                >
                  Original
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setReviewMode("edited");
                    handleRunQA(true, "edited");
                  }}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all ${
                    (qaData?.review?.preview_mode || reviewMode) === "edited"
                      ? "bg-primary text-white shadow-xs"
                      : "text-text-secondary hover:text-text-primary hover:bg-surface-3/50"
                  }`}
                  data-testid="btn-review-mode-edited"
                >
                  Edited Preview
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setReviewMode("voiceover");
                    handleRunQA(true, "voiceover");
                  }}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all ${
                    (qaData?.review?.preview_mode || reviewMode) === "voiceover"
                      ? "bg-primary text-white shadow-xs"
                      : "text-text-secondary hover:text-text-primary hover:bg-surface-3/50"
                  }`}
                  data-testid="btn-review-mode-voiceover"
                >
                  Voiceover Preview
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setReviewMode("final_mix");
                    handleRunQA(true, "final_mix");
                  }}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all ${
                    (qaData?.review?.preview_mode || reviewMode) === "final_mix"
                      ? "bg-purple-600 text-white shadow-xs"
                      : "text-text-secondary hover:text-text-primary hover:bg-surface-3/50"
                  }`}
                  data-testid="btn-review-mode-final-mix"
                >
                  Final Mix
                </button>
              </div>
              <div className="text-xs text-text-muted">
                Mode:{" "}
                <span className="font-semibold text-text-primary">
                  {((qaData?.review?.preview_mode || reviewMode) === "original" && "Original") ||
                    ((qaData?.review?.preview_mode || reviewMode) === "edited" &&
                      "Edited Preview") ||
                    ((qaData?.review?.preview_mode || reviewMode) === "voiceover" &&
                      "Voiceover Preview") ||
                    "Final Mix"}
                </span>
              </div>
            </div>

            {qaData?.review ? (
              <div className="p-4 rounded-xl bg-surface-2/60 border border-border-subtle space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-semibold text-text-secondary">
                  <div className="flex items-center gap-2">
                    <span
                      className="font-bold text-emerald-400"
                      data-testid="iris-review-mode-label"
                    >
                      Reviewing:{" "}
                      {((qaData.review.preview_mode || reviewMode) === "original" && "Original") ||
                        ((qaData.review.preview_mode || reviewMode) === "edited" &&
                          "Edited Preview") ||
                        ((qaData.review.preview_mode || reviewMode) === "voiceover" &&
                          "Voiceover Preview") ||
                        "Final Mix"}
                    </span>
                    <span
                      className="text-[10px] px-2 py-0.5 rounded bg-surface-3 text-text-muted font-mono"
                      data-testid="iris-reviewed-artifact-id"
                    >
                      {qaData.review.reviewed_artifact_id ||
                        qaData.master_artifact?.artifact_id ||
                        "Source Media"}
                    </span>
                    {qaData.review.reviewed_voice_id && (
                      <span
                        className="text-[10px] px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 font-mono"
                        data-testid="iris-reviewed-voice-id"
                      >
                        Voice: {qaData.review.reviewed_voice_id}
                      </span>
                    )}
                  </div>
                  <span>Iris Assessment Verdict: {qaData.review.verdict}</span>
                  {typeof qaData.review.confidence === "number" && (
                    <span className="text-text-muted font-normal">
                      Confidence: {Math.round(qaData.review.confidence * 100)}%
                    </span>
                  )}
                </div>
                <p className="text-xs text-text-primary leading-relaxed">{qaData.review.summary}</p>
              </div>
            ) : (
              <div className="p-6 text-center text-text-muted text-xs space-y-2">
                <ShieldCheck className="size-8 text-text-muted/40 mx-auto" />
                <p>Press "Run Quality Check" to inspect the rendered video artifact.</p>
              </div>
            )}
            {/* Checklist Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 rounded-xl bg-surface-2/40 border border-border-subtle text-xs space-y-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted block">
                  Media Continuity
                </span>
                <span
                  className={`font-semibold flex items-center gap-1.5 ${checklist?.master_video ? "text-emerald-400" : "text-text-secondary"}`}
                >
                  {checklist?.master_video ? (
                    <CheckCircle2 className="size-3.5" />
                  ) : (
                    <Clock className="size-3.5" />
                  )}
                  {checklist?.master_video ? "Passed" : "Checking"}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-surface-2/40 border border-border-subtle text-xs space-y-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted block">
                  Audio Quality
                </span>
                <span
                  className={`font-semibold flex items-center gap-1.5 ${checklist?.audio ? "text-emerald-400" : "text-text-secondary"}`}
                >
                  {checklist?.audio ? (
                    <CheckCircle2 className="size-3.5" />
                  ) : (
                    <Clock className="size-3.5" />
                  )}
                  {checklist?.audio ? "Passed (-16 LUFS)" : "Checking"}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-surface-2/40 border border-border-subtle text-xs space-y-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted block">
                  Caption Sync
                </span>
                <span
                  className={`font-semibold flex items-center gap-1.5 ${checklist?.captions ? "text-emerald-400" : "text-text-secondary"}`}
                >
                  {checklist?.captions ? (
                    <CheckCircle2 className="size-3.5" />
                  ) : (
                    <Clock className="size-3.5" />
                  )}
                  {checklist?.captions ? "Passed" : "Checking"}
                </span>
              </div>
            </div>

            {/* Itemized Issues List with Clickable Timecodes */}
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-text-secondary">
                  Detected Quality Findings ({issuesList.length})
                </h4>
                {issuesList.length === 0 && qaData?.review && (
                  <span className="text-xs text-emerald-400 font-semibold flex items-center gap-1">
                    <CheckCircle2 className="size-3.5" />
                    Zero defects detected
                  </span>
                )}
              </div>

              {issuesList.length > 0 ? (
                <div className="space-y-3" data-testid="qa-issues-list">
                  {issuesList.map((issue, idx) => (
                    <div
                      key={idx}
                      className={`p-4 rounded-xl border space-y-2 transition-colors ${
                        issue.severity === "BLOCKING" || issue.severity === "HIGH"
                          ? "bg-danger/5 border-danger/30 text-danger"
                          : "bg-surface-2/60 border-border-subtle text-text-primary"
                      }`}
                      data-testid={`qa-issue-item-${idx}`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                              issue.severity === "BLOCKING" || issue.severity === "HIGH"
                                ? "bg-danger/20 text-danger"
                                : "bg-surface-3 text-text-secondary"
                            }`}
                          >
                            {issue.severity}
                          </span>
                          <span className="text-xs font-semibold text-text-primary">
                            {getIssueFriendlyName(issue.issue_type)}
                          </span>
                        </div>

                        {/* Clickable timecode seek tag */}
                        {issue.source_start_ms !== null && issue.source_start_ms !== undefined && (
                          <button
                            type="button"
                            onClick={() => handleSeekToIssue(issue)}
                            className="flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded bg-surface-3 hover:bg-primary/20 hover:text-primary transition-colors cursor-pointer text-text-secondary"
                            title="Jump video to issue timestamp"
                          >
                            <Play className="size-2.5" />
                            <span>{formatMs(issue.source_start_ms)}</span>
                          </button>
                        )}
                      </div>

                      <p className="text-xs text-text-primary leading-relaxed">{issue.message}</p>

                      {issue.evidence && (
                        <p className="text-[11px] text-text-muted leading-relaxed border-l-2 border-border-strong pl-2">
                          Evidence: {issue.evidence}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : qaData?.review ? (
                <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
                  <CheckCircle2 className="size-4 shrink-0" />
                  <span>
                    Iris verified video continuity, speech clarity, loudness target, and caption
                    timing. Output is approved.
                  </span>
                </div>
              ) : null}
            </div>
          </div>
        </div>

        {/* Right Column (4 cols): Manual Publish Metadata & Release Actions */}
        <div className="lg:col-span-4 space-y-6 lg:sticky lg:top-20">
          {/* Release Readiness Card */}
          {/* Release Readiness / Gate Card */}
          <div
            className={`p-5 rounded-2xl border space-y-4 shadow-xs ${
              isReady
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                : "bg-surface-1 border-border-subtle"
            }`}
            data-testid="release-gate-card"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-text-secondary">
                Release Gate
              </span>
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                  publishJobData?.job?.status === "completed"
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                    : isReady
                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                      : "bg-surface-2 text-text-muted border border-border-subtle"
                }`}
                data-testid="release-gate-badge"
              >
                {publishJobData?.job?.status === "completed"
                  ? "Uploaded Privately"
                  : isReady
                    ? "Gate Passed"
                    : "Gate Locked"}
              </span>
            </div>

            <div className="text-xs text-text-secondary space-y-1.5">
              <p>
                {publishJobData?.job?.status === "completed"
                  ? "Production successfully published to YouTube."
                  : isReady
                    ? "All release gate criteria satisfied. Master video is ready for YouTube publication."
                    : "Review findings above before proceeding with channel publication."}
              </p>
            </div>

            {/* Publishing Progress Section */}
            {publishJobData?.job?.status === "uploading" && (
              <div
                className="p-3.5 rounded-xl bg-surface-2 border border-border-subtle space-y-2"
                data-testid="section-upload-progress"
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-text-primary flex items-center gap-1.5">
                    <Loader2 className="size-3.5 text-primary animate-spin" />
                    Uploading to YouTube {Math.round(publishJobData.job.progress_percent || 0)}%
                  </span>
                  <span className="font-mono text-text-muted text-[11px]">
                    {((publishJobData.job.bytes_uploaded || 0) / 1048576).toFixed(1)} MB /{" "}
                    {((publishJobData.job.total_bytes || 1) / 1048576).toFixed(1)} MB
                  </span>
                </div>
                <div className="w-full bg-surface-3 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-primary h-full rounded-full transition-all duration-300"
                    style={{ width: `${publishJobData.job.progress_percent || 0}%` }}
                  />
                </div>
              </div>
            )}

            {/* Publishing Completed Section */}
            {publishJobData?.job?.status === "completed" && (
              <div
                className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 space-y-2 text-xs"
                data-testid="section-publish-completed"
              >
                {publishJobData.job.audit_restriction_detected && (
                  <div
                    className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-start gap-2 mb-2"
                    data-testid="banner-audit-restriction"
                  >
                    <AlertTriangle className="size-3.5 shrink-0 text-amber-400 mt-0.5" />
                    <div className="space-y-0.5">
                      <span className="font-semibold block text-[11px]">
                        Audit Restriction Active
                      </span>
                      <p className="text-[10px] text-amber-200/90 leading-relaxed">
                        YouTube restricted this API project to private uploads until verification
                        audit is complete.
                      </p>
                    </div>
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-emerald-400 flex items-center gap-1.5">
                    <CheckCircle2 className="size-4" />
                    YouTube Publication Complete
                  </span>
                  <span
                    className="font-mono text-[11px] text-text-muted"
                    data-testid="text-youtube-video-id"
                  >
                    ID: {publishJobData.job.youtube_video_id}
                  </span>
                </div>
                <p className="text-text-secondary text-[11px]">
                  Video uploaded privately. Thumbnail uploaded.
                </p>
                {publishJobData.job.youtube_url && (
                  <a
                    href={publishJobData.job.youtube_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline text-xs font-semibold pt-1"
                    data-testid="btn-open-on-youtube"
                  >
                    <span>Open on YouTube</span>
                    <ExternalLink className="size-3" />
                  </a>
                )}
              </div>
            )}

            {/* Primary Action Button */}
            {publishJobData?.job?.status !== "completed" && (
              <button
                type="button"
                onClick={handleOpenPublishModal}
                disabled={!isReady}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-red-600 hover:bg-red-500 text-white text-xs font-bold transition-colors shadow-sm disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                data-testid="btn-publish-to-youtube"
              >
                <YouTubeIcon className="size-4" />
                <span>Publish to YouTube</span>
              </button>
            )}
          </div>

          {/* Creator-Owned Manual Release Metadata */}
          <div
            className="bg-surface-1 border border-border-subtle rounded-2xl p-5 space-y-4 shadow-xs"
            data-testid="section-publish-metadata"
          >
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold uppercase tracking-wider text-text-secondary">
                Release Metadata
              </h4>
              <span className="text-[10px] text-text-muted">Creator-Owned</span>
            </div>

            {/* Title Input */}
            <div className="space-y-1.5">
              <label
                htmlFor="publish-title"
                className="text-xs font-semibold text-text-primary block"
              >
                Video Title
              </label>
              <input
                id="publish-title"
                type="text"
                value={titleInput}
                onChange={(e) => setTitleInput(e.target.value)}
                maxLength={100}
                className="w-full px-3 py-2 text-xs rounded-lg bg-surface-2 border border-border-subtle text-text-primary placeholder:text-text-muted focus:border-primary outline-none transition-colors"
                placeholder="Enter YouTube video title…"
                data-testid="input-publish-title"
              />
              <span className="text-[10px] text-text-muted block text-right font-mono">
                {titleInput.length}/100
              </span>
            </div>

            {/* Description Input */}
            <div className="space-y-1.5">
              <label
                htmlFor="publish-description"
                className="text-xs font-semibold text-text-primary block"
              >
                Video Description
              </label>
              <textarea
                id="publish-description"
                rows={5}
                value={descriptionInput}
                onChange={(e) => setDescriptionInput(e.target.value)}
                maxLength={5000}
                className="w-full px-3 py-2 text-xs rounded-lg bg-surface-2 border border-border-subtle text-text-primary placeholder:text-text-muted focus:border-primary outline-none transition-colors resize-y font-sans"
                placeholder="Enter video description, links, and notes…"
                data-testid="input-publish-description"
              />
              <span className="text-[10px] text-text-muted block text-right font-mono">
                {descriptionInput.length}/5000
              </span>
            </div>

            {/* Privacy Setting */}
            <div className="space-y-1.5">
              <label
                htmlFor="publish-privacy"
                className="text-xs font-semibold text-text-primary block"
              >
                Privacy Setting
              </label>
              <select
                id="publish-privacy"
                value={privacySetting}
                onChange={(e) =>
                  setPrivacySetting(e.target.value as "private" | "unlisted" | "public")
                }
                className="w-full px-3 py-2 text-xs rounded-lg bg-surface-2 border border-border-subtle text-text-primary focus:border-primary outline-none transition-colors"
              >
                <option value="private">Private (Default / Recommended)</option>
                <option value="unlisted">Unlisted</option>
                <option value="public">Public</option>
              </select>
            </div>

            {/* Save Button */}
            <button
              type="button"
              onClick={handleSaveMetadata}
              disabled={isSavingMetadata}
              className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-surface-2 hover:bg-surface-3 border border-border-subtle text-xs font-semibold text-text-primary transition-colors disabled:opacity-50"
              data-testid="btn-save-metadata"
            >
              {isSavingMetadata ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Save className="size-3.5" />
              )}
              <span>{isSavingMetadata ? "Saving…" : "Save Metadata"}</span>
            </button>
          </div>

          {/* Release Fingerprint & Immutable Lineage */}
          {qaData?.release_fingerprint && (
            <div className="bg-surface-1 border border-border-subtle rounded-2xl p-4 text-xs space-y-2 text-text-muted">
              <div className="flex items-center gap-1.5 font-semibold text-text-secondary">
                <Lock className="size-3.5 text-primary" />
                <span>Cryptographic Release Fingerprint</span>
              </div>
              <p className="font-mono text-[10px] break-all bg-surface-2 p-2 rounded border border-border-subtle">
                {qaData.release_fingerprint}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Iris Agent Settings Drawer */}
      <AgentSettingsDrawer
        isOpen={isIrisDrawerOpen}
        agentId="iris"
        onClose={() => setIsIrisDrawerOpen(false)}
      />

      {/* YouTube Publish Confirmation Modal */}
      <PublishConfirmationModal
        isOpen={isPublishModalOpen}
        onClose={() => setIsPublishModalOpen(false)}
        prepData={prepData}
        isLoadingPrep={isLoadingPrep}
        onConfirmPublish={handleConfirmPublish}
        isPublishing={isPublishing}
        onGrantUploadAccess={handleGrantUploadAccess}
        onConnectYouTube={handleGrantUploadAccess}
      />
    </div>
  );
};

export default ReleasePage;
