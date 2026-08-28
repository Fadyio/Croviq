import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Copy,
  Edit3,
  ExternalLink,
  Film,
  Flame,
  HelpCircle,
  Image as ImageIcon,
  Info,
  Layers,
  Lightbulb,
  Loader2,
  LogOut,
  Maximize2,
  Minimize2,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Save,
  Scissors,
  ShieldAlert,
  ShieldCheck,
  Smartphone,
  Sparkles,
  Volume2,
  VolumeX,
  Wand2,
  XCircle,
  UploadCloud,
  Lock,
} from "lucide-react";
import { CroviqLogo } from "../components/CroviqLogo";
import { useAuth } from "../auth/AuthContext";
import { AgentSettingsDrawer } from "../components/editor/AgentSettingsDrawer";
import ninaAvatar from "../assets/agents/Nina.png";
import irisAvatar from "../assets/agents/Iris.png";
import {
  PublishConfirmationModal,
  YouTubeIcon,
} from "../components/release/PublishConfirmationModal";
import type { components } from "../api/generated";

type PackagingDetailResponse = components["schemas"]["PackagingDetailResponse"];
type PackagingChapter = components["schemas"]["PackagingChapter"];
type TitleCandidate = components["schemas"]["TitleCandidate"];
type ThumbnailConcept = components["schemas"]["ThumbnailConcept"];
type ReleaseReviewDetailResponse = components["schemas"]["ReleaseReviewDetailResponse"];
type ReleaseReview = components["schemas"]["ReleaseReview"];
type ReleaseIssue = components["schemas"]["ReleaseIssue"];
type ReleaseChecklist = components["schemas"]["ReleaseChecklist"];
type ClaimVerification = components["schemas"]["ClaimVerification"];
type ThumbnailEvaluation = components["schemas"]["ThumbnailEvaluation"];
type AutoCorrectQAResponse = components["schemas"]["AutoCorrectQAResponse"];
type PublishPreparationResponse = components["schemas"]["PublishPreparationResponse"];
type PublishJobDetailResponse = components["schemas"]["PublishJobDetailResponse"];
type YouTubePublishJob = components["schemas"]["YouTubePublishJob"];

interface ReleasePageProps {
  productionId: string;
  onNavigateHome?: () => void;
  onNavigateEditor?: () => void;
}

const getAngleBadgeColor = (angle: string) => {
  switch (angle) {
    case "PROBLEM_SOLUTION":
      return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
    case "DIRECT_VALUE":
      return "bg-blue-500/15 text-blue-400 border-blue-500/30";
    case "CURIOSITY":
      return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    case "CONTRARIAN":
      return "bg-purple-500/15 text-purple-400 border-purple-500/30";
    case "HOW_TO":
      return "bg-cyan-500/15 text-cyan-400 border-cyan-500/30";
    case "COMPARISON":
      return "bg-pink-500/15 text-pink-400 border-pink-500/30";
    case "NEWS_RELEVANT":
      return "bg-orange-500/15 text-orange-400 border-orange-500/30";
    default:
      return "bg-surface-3 text-text-secondary border-border-subtle";
  }
};

const getAngleFriendlyName = (angle: string) => {
  switch (angle) {
    case "PROBLEM_SOLUTION":
      return "Problem-Solution";
    case "DIRECT_VALUE":
      return "Direct Value";
    case "CURIOSITY":
      return "Curiosity";
    case "CONTRARIAN":
      return "Contrarian";
    case "HOW_TO":
      return "How-To";
    case "COMPARISON":
      return "Comparison";
    case "NEWS_RELEVANT":
      return "News Relevant";
    default:
      return angle
        .replace(/_/g, " ")
        .toLowerCase()
        .replace(/\b\w/g, (c) => c.toUpperCase());
  }
};

const getIssueFriendlyName = (type: string) => {
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
    SHORT_QUALITY: "Short Quality Issue",
    SHORT_CAPTION_QUALITY: "Short Caption Quality",
    SHORT_CROP: "Short Vertical Framing Issue",
    MISSING_CONTENT: "Missing Content / Demo",
    CONTEXT_LOSS: "Context Loss",
  };
  return map[type] || type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
};

const getClaimStatusBadge = (status: string) => {
  switch (status) {
    case "SUPPORTED_BY_VIDEO":
      return {
        label: "Supported by Video",
        color: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
        icon: CheckCircle2,
      };
    case "SUPPORTED_EXTERNALLY":
      return {
        label: "Supported Externally",
        color: "bg-blue-500/15 text-blue-400 border-blue-500/30",
        icon: ExternalLink,
      };
    case "UNSUPPORTED":
      return {
        label: "Unsupported",
        color: "bg-rose-500/15 text-rose-400 border-rose-500/30",
        icon: XCircle,
      };
    case "MANUAL_REVIEW":
    default:
      return {
        label: "Manual Review",
        color: "bg-amber-500/15 text-amber-400 border-amber-500/30",
        icon: AlertTriangle,
      };
  }
};

export const ReleasePage: React.FC<ReleasePageProps> = ({
  productionId,
  onNavigateHome,
  onNavigateEditor,
}) => {
  const { firebaseUser, logout } = useAuth();
  const videoRef = useRef<HTMLVideoElement>(null);

  const [activeStage, setActiveStage] = useState<"packaging" | "qa" | "ready">("qa");
  const [packagingData, setPackagingData] = useState<PackagingDetailResponse | null>(null);
  const [qaData, setQaData] = useState<ReleaseReviewDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isGeneratingPackaging, setIsGeneratingPackaging] = useState<boolean>(false);
  const [isRunningQA, setIsRunningQA] = useState<boolean>(false);
  const [isCorrectingQA, setIsCorrectingQA] = useState<boolean>(false);
  const [isSavingOverrides, setIsSavingOverrides] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [correctionSuccessMsg, setCorrectionSuccessMsg] = useState<string | null>(null);

  // Editable local state
  const [titleInput, setTitleInput] = useState<string>("");
  const [descriptionInput, setDescriptionInput] = useState<string>("");
  const [chaptersInput, setChaptersInput] = useState<PackagingChapter[]>([]);
  const [selectedTitleCandidate, setSelectedTitleCandidate] = useState<string>("");
  const [selectedThumbnailId, setSelectedThumbnailId] = useState<string>("");
  const [shortTitleInput, setShortTitleInput] = useState<string>("");
  const [shortDescInput, setShortDescInput] = useState<string>("");

  // Video playback state
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTimeMs, setCurrentTimeMs] = useState<number>(0);
  const [durationMs, setDurationMs] = useState<number>(113824);
  const [isMuted, setIsMuted] = useState<boolean>(false);

  // Agent Settings Drawers state
  const [drawerAgent, setDrawerAgent] = useState<"nina" | "iris" | null>(null);
  // YouTube Publishing State
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
    }
    return headers;
  }, [firebaseUser]);

  // Load initial packaging details (idempotent GET, 0 model calls)
  const loadPackaging = useCallback(async () => {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/productions/${productionId}/packaging`, { headers });
      if (res.ok) {
        const data: PackagingDetailResponse = await res.json();
        setPackagingData(data);
        if (data.proposal) {
          setTitleInput(data.effective_title || data.proposal.primary_title || "");
          setSelectedTitleCandidate(
            data.overrides?.selected_title || data.proposal.primary_title || "",
          );
          setDescriptionInput(data.effective_description || data.proposal.description || "");
          setChaptersInput(data.effective_chapters || data.proposal.chapters || []);
          setSelectedThumbnailId(
            data.effective_thumbnail_concept_id ||
              data.proposal.thumbnail_concepts?.[0]?.concept_id ||
              "",
          );
          if (data.effective_short_package) {
            setShortTitleInput(data.effective_short_package.title);
            setShortDescInput(data.effective_short_package.description);
          }
        }
      }
    } catch (err: unknown) {
      console.error("Error loading packaging:", err);
    }
  }, [getAuthHeaders, productionId]);

  // Load QA review details (idempotent GET, 0 model calls)
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
  // Load current YouTube publishing job status
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

  // Load publish preparation metadata
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
      await Promise.all([loadPackaging(), loadQA(), loadPublishStatus()]);
      setIsLoading(false);
    };
    init();
  }, [loadPackaging, loadQA, loadPublishStatus]);

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
        const data = await res.json();
        window.location.href = data.auth_url;
      } else {
        setErrorMessage("Failed to generate YouTube authorization URL.");
      }
    } catch (err: unknown) {
      console.error("Error initiating YouTube incremental OAuth:", err);
      setErrorMessage("Error initiating YouTube authorization.");
    }
  };

  const handleConnectYouTube = () => {
    handleGrantUploadAccess();
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
    upload_short: boolean;
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
      if (res.ok) {
        const data: PublishJobDetailResponse = await res.json();
        setPublishJobData(data);
        setIsPublishModalOpen(false);
        setPublishSuccessMsg("Publishing initiated successfully.");
        setTimeout(() => setPublishSuccessMsg(null), 4000);
      } else {
        const errData = await res.json().catch(() => ({ detail: "Publish request failed" }));
        setErrorMessage(errData.detail || "Failed to publish to YouTube");
      }
    } catch (err: unknown) {
      console.error("Error submitting publish job:", err);
      setErrorMessage(err instanceof Error ? err.message : "Error submitting publish job");
    } finally {
      setIsPublishing(false);
    }
  };

  // Run or re-run Iris QA Review
  const handleRunQA = async (forceRegenerate: boolean = false) => {
    setIsRunningQA(true);
    setErrorMessage(null);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/productions/${productionId}/release-review`, {
        method: "POST",
        headers,
        body: JSON.stringify({ force_regenerate: forceRegenerate }),
      });
      if (res.ok) {
        const data: ReleaseReviewDetailResponse = await res.json();
        setQaData(data);
        setSaveMessage(forceRegenerate ? "Fresh QA pass completed!" : "QA review loaded.");
        setTimeout(() => setSaveMessage(null), 3000);
      } else {
        const err = await res.json().catch(() => ({ detail: "QA review failed" }));
        setErrorMessage(err.detail || "QA review execution failed");
      }
    } catch (err: unknown) {
      console.error("Error executing QA review:", err);
      setErrorMessage(err instanceof Error ? err.message : "Error executing QA review");
    } finally {
      setIsRunningQA(false);
    }
  };

  // Perform 1-cycle auto-correction (Nina revises packaging, Iris re-evaluates)
  const handleAutoCorrectQA = async () => {
    setIsCorrectingQA(true);
    setErrorMessage(null);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/productions/${productionId}/release-review/correct`, {
        method: "POST",
        headers,
        body: JSON.stringify({}),
      });
      if (res.ok) {
        const data: AutoCorrectQAResponse = await res.json();
        setCorrectionSuccessMsg(data.message);
        setTimeout(() => setCorrectionSuccessMsg(null), 5000);
        // Refresh both packaging and QA state
        await Promise.all([loadPackaging(), loadQA()]);
      } else {
        const err = await res.json().catch(() => ({ detail: "Auto-correction failed" }));
        setErrorMessage(err.detail || "Auto-correction failed");
      }
    } catch (err: unknown) {
      console.error("Error during auto-correction:", err);
      setErrorMessage(err instanceof Error ? err.message : "Error during auto-correction");
    } finally {
      setIsCorrectingQA(false);
    }
  };

  // Explicit packaging generation pass
  const handleGeneratePackaging = async (forceRegenerate: boolean = false) => {
    setIsGeneratingPackaging(true);
    setErrorMessage(null);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/productions/${productionId}/package`, {
        method: "POST",
        headers,
        body: JSON.stringify({ force_regenerate: forceRegenerate }),
      });
      if (res.ok) {
        const data: PackagingDetailResponse = await res.json();
        setPackagingData(data);
        if (data.proposal) {
          setTitleInput(data.effective_title || data.proposal.primary_title || "");
          setSelectedTitleCandidate(
            data.overrides?.selected_title || data.proposal.primary_title || "",
          );
          setDescriptionInput(data.effective_description || data.proposal.description || "");
          setChaptersInput(data.effective_chapters || data.proposal.chapters || []);
          setSelectedThumbnailId(
            data.effective_thumbnail_concept_id ||
              data.proposal.thumbnail_concepts?.[0]?.concept_id ||
              "",
          );
          if (data.effective_short_package) {
            setShortTitleInput(data.effective_short_package.title);
            setShortDescInput(data.effective_short_package.description);
          }
        }
        setSaveMessage("Packaging generated successfully!");
        setTimeout(() => setSaveMessage(null), 3000);
        // Trigger QA review after packaging
        await loadQA();
      } else {
        const err = await res.json().catch(() => ({ detail: "Packaging generation failed" }));
        setErrorMessage(err.detail || "Packaging generation failed");
      }
    } catch (err: unknown) {
      console.error("Error generating packaging:", err);
      setErrorMessage(err instanceof Error ? err.message : "Error generating packaging");
    } finally {
      setIsGeneratingPackaging(false);
    }
  };

  // Save creator packaging overrides
  const handleSaveOverrides = async () => {
    setIsSavingOverrides(true);
    try {
      const headers = await getAuthHeaders();
      const payload = {
        selected_title: selectedTitleCandidate || undefined,
        custom_title: titleInput || undefined,
        custom_description: descriptionInput || undefined,
        custom_chapters: chaptersInput.length > 0 ? chaptersInput : undefined,
        custom_short_title: shortTitleInput || undefined,
        custom_short_description: shortDescInput || undefined,
        selected_thumbnail_concept_id: selectedThumbnailId || undefined,
      };
      const res = await fetch(`/api/productions/${productionId}/packaging`, {
        method: "PATCH",
        headers,
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const updated: PackagingDetailResponse = await res.json();
        setPackagingData(updated);
        setSaveMessage("Changes saved successfully!");
        setTimeout(() => setSaveMessage(null), 2500);
        // Trigger fresh QA check on packaging override change
        await handleRunQA(true);
      }
    } catch (err: unknown) {
      console.error("Error saving overrides:", err);
      setErrorMessage(err instanceof Error ? err.message : "Failed to save changes.");
    } finally {
      setIsSavingOverrides(false);
    }
  };

  // Video seeking helpers
  const handleSeek = (timeMs: number) => {
    const video = videoRef.current;
    if (!video) return;
    const targetSeconds = timeMs / 1000.0;
    video.currentTime = targetSeconds;
    setCurrentTimeMs(timeMs);
  };

  const handleTogglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    if (isPlaying) {
      video.pause();
      setIsPlaying(false);
    } else {
      video.play().catch(() => {});
      setIsPlaying(true);
    }
  };

  const handleChapterTitleChange = (index: number, newTitle: string) => {
    setChaptersInput((prev) => {
      const updated = [...prev];
      if (updated[index]) {
        updated[index] = { ...updated[index], title: newTitle };
      }
      return updated;
    });
  };

  const activeVideoSrc = packagingData?.master_url || qaData?.master_url || "";
  const releaseStatusText =
    qaData?.release_status || (packagingData?.proposal ? "Checking final output" : "Packaging");
  const isReleaseReady = Boolean(qaData?.release_ready);

  return (
    <div
      className="min-h-screen bg-background text-text-primary flex flex-col font-sans select-none"
      data-testid="release-workspace"
    >
      {/* Top Navbar */}
      <header className="h-14 bg-surface-1 border-b border-border-subtle px-4 md:px-6 flex items-center justify-between shrink-0 sticky top-0 z-30 shadow-xs">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={onNavigateEditor || onNavigateHome}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary hover:bg-surface-2 rounded-lg transition-colors border border-border-subtle"
            title="Back to Editor"
            data-testid="btn-back-to-editor"
          >
            <ArrowLeft className="size-3.5" />
            <span>Editor</span>
          </button>

          <span className="text-border-strong select-none font-light">/</span>

          <div className="flex items-center gap-2">
            <CroviqLogo height={22} className="h-5 w-auto" />
            <span className="text-xs font-semibold text-text-primary tracking-tight">
              Release Gate
            </span>
          </div>
        </div>

        {/* Center: Pipeline Stages & Status */}
        <div className="flex items-center gap-2 md:gap-4">
          {/* Stage Tabs */}
          <div className="hidden sm:flex items-center p-0.5 rounded-lg bg-surface-2 border border-border-subtle text-xs font-medium">
            <button
              type="button"
              onClick={() => setActiveStage("packaging")}
              className={`px-3 py-1 rounded-md transition-all ${
                activeStage === "packaging"
                  ? "bg-surface-1 text-text-primary shadow-xs font-semibold"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              1. Packaging
            </button>
            <button
              type="button"
              onClick={() => setActiveStage("qa")}
              className={`px-3 py-1 rounded-md transition-all ${
                activeStage === "qa"
                  ? "bg-surface-1 text-text-primary shadow-xs font-semibold"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              2. QA Review
            </button>
            <button
              type="button"
              onClick={() => setActiveStage("ready")}
              className={`px-3 py-1 rounded-md transition-all ${
                activeStage === "ready"
                  ? "bg-surface-1 text-text-primary shadow-xs font-semibold"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              3. Ready
            </button>
          </div>

          {/* Canonical Creator-Facing Status Chip */}
          <div
            className={`flex items-center gap-2 px-3 py-1 rounded-full border text-xs font-semibold transition-all ${
              isReleaseReady
                ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                : releaseStatusText === "Fix required"
                  ? "bg-rose-500/15 text-rose-400 border-rose-500/30"
                  : releaseStatusText === "Manual review"
                    ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
                    : "bg-surface-2 text-text-secondary border-border-subtle"
            }`}
            data-testid="release-status-badge"
          >
            {isRunningQA ? (
              <Loader2 className="size-3.5 text-primary animate-spin" />
            ) : isReleaseReady ? (
              <CheckCircle2 className="size-3.5 text-emerald-400" />
            ) : releaseStatusText === "Fix required" ? (
              <AlertCircle className="size-3.5 text-rose-400" />
            ) : releaseStatusText === "Manual review" ? (
              <AlertTriangle className="size-3.5 text-amber-400" />
            ) : (
              <Sparkles className="size-3.5 text-text-muted" />
            )}
            <span className="text-[11px]">{releaseStatusText}</span>
          </div>
        </div>

        {/* Right actions */}
        <div className="flex items-center gap-2.5">
          {saveMessage && (
            <span className="text-xs text-emerald-400 flex items-center gap-1 font-medium animate-fade-in">
              <Check className="size-3.5" />
              {saveMessage}
            </span>
          )}

          <button
            type="button"
            onClick={handleSaveOverrides}
            disabled={isSavingOverrides || isGeneratingPackaging || !packagingData?.proposal}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-surface-2 hover:bg-surface-3 text-text-primary border border-border-subtle rounded-lg transition-colors disabled:opacity-50"
            data-testid="btn-save-package-changes"
          >
            {isSavingOverrides ? (
              <Loader2 className="size-3.5 animate-spin text-primary" />
            ) : (
              <Save className="size-3.5" />
            )}
            <span className="hidden sm:inline">Save Overrides</span>
          </button>

          <button
            onClick={logout}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-text-muted hover:text-text-primary hover:bg-surface-2 rounded-lg transition-colors border border-transparent hover:border-border-subtle"
            title="Sign out"
          >
            <LogOut className="size-3.5" />
            <span className="hidden md:inline">Logout</span>
          </button>
        </div>
      </header>

      {/* Error & Success Toasts */}
      {errorMessage && (
        <div className="bg-rose-500/10 border-b border-rose-500/20 px-4 py-2 text-xs text-rose-400 flex items-center justify-between">
          <span>{errorMessage}</span>
          <button onClick={() => setErrorMessage(null)} className="hover:text-rose-200">
            <XCircle className="size-4" />
          </button>
        </div>
      )}
      {correctionSuccessMsg && (
        <div className="bg-emerald-500/10 border-b border-emerald-500/20 px-4 py-2 text-xs text-emerald-400 flex items-center justify-between">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="size-4" />
            {correctionSuccessMsg}
          </span>
          <button onClick={() => setCorrectionSuccessMsg(null)} className="hover:text-emerald-200">
            <XCircle className="size-4" />
          </button>
        </div>
      )}

      {/* Main Container */}
      <div className="flex-1 max-w-[1720px] w-full mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column (8 cols): Master Video, Packaging Editor, QA Checklist, Issues */}
        <div className="lg:col-span-8 space-y-6">
          {/* 1. Master Video Preview Stage */}
          <section
            className="bg-surface-1 border border-border-subtle rounded-xl overflow-hidden shadow-xs"
            data-testid="section-master-preview"
          >
            <div className="p-3 border-b border-border-subtle bg-surface-2/40 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Film className="size-4 text-primary" />
                <h2 className="text-xs font-semibold tracking-wide uppercase text-text-secondary">
                  Approved Master Video Preview
                </h2>
              </div>
              <span className="text-[11px] font-mono text-text-muted">
                {packagingData?.master_artifact?.duration_ms
                  ? `${(packagingData.master_artifact.duration_ms / 1000).toFixed(1)}s`
                  : "Master"}
              </span>
            </div>

            <div className="relative bg-black aspect-video flex items-center justify-center overflow-hidden">
              {activeVideoSrc ? (
                <video
                  ref={videoRef}
                  src={activeVideoSrc}
                  className="w-full h-full object-contain"
                  onTimeUpdate={() => {
                    if (videoRef.current) {
                      setCurrentTimeMs(Math.floor(videoRef.current.currentTime * 1000));
                    }
                  }}
                  onLoadedMetadata={() => {
                    if (videoRef.current) {
                      setDurationMs(Math.floor(videoRef.current.duration * 1000));
                    }
                  }}
                  onEnded={() => setIsPlaying(false)}
                />
              ) : (
                <div className="text-center p-6 text-text-muted">
                  <Film className="size-8 mx-auto mb-2 opacity-50" />
                  <p className="text-xs font-medium">Master Video Stream</p>
                  <p className="text-[11px] opacity-75">
                    {packagingData?.has_master
                      ? "Loading video stream…"
                      : "Master video render not completed"}
                  </p>
                </div>
              )}
            </div>

            {/* Video Controls Bar */}
            <div className="p-3 bg-surface-1 flex items-center justify-between gap-4 border-t border-border-subtle">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleTogglePlay}
                  className="p-1.5 rounded-lg bg-surface-2 hover:bg-surface-3 text-text-primary transition-colors"
                  aria-label={isPlaying ? "Pause" : "Play"}
                  data-testid="btn-play-pause-master"
                >
                  {isPlaying ? <Pause className="size-4" /> : <Play className="size-4" />}
                </button>

                <button
                  type="button"
                  onClick={() => setIsMuted(!isMuted)}
                  className="p-1.5 rounded-lg text-text-muted hover:text-text-primary transition-colors"
                  aria-label={isMuted ? "Unmute" : "Mute"}
                >
                  {isMuted ? <VolumeX className="size-4" /> : <Volume2 className="size-4" />}
                </button>

                <span className="text-xs font-mono text-text-secondary">
                  {Math.floor(currentTimeMs / 60000)}:
                  {String(Math.floor((currentTimeMs % 60000) / 1000)).padStart(2, "0")} /{" "}
                  {Math.floor(durationMs / 60000)}:
                  {String(Math.floor((durationMs % 60000) / 1000)).padStart(2, "0")}
                </span>
              </div>

              {/* Quick Scrubber */}
              <input
                type="range"
                min={0}
                max={durationMs || 1000}
                value={currentTimeMs}
                onChange={(e) => handleSeek(Number(e.target.value))}
                className="flex-1 h-1.5 bg-surface-3 rounded-lg appearance-none cursor-pointer accent-primary"
              />
            </div>
          </section>

          {/* 2. Iris QA Release Gate & Checklist Section */}
          <section
            className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-5 shadow-xs"
            data-testid="section-iris-qa"
          >
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-3">
                <div className="size-9 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                  <ShieldCheck className="size-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-text-primary flex items-center gap-2">
                    <span>Quality Assurance & Release Gate</span>
                    <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded bg-surface-2 text-text-muted">
                      Iris • gemini-3.7-flash
                    </span>
                  </h3>
                  <p className="text-xs text-text-secondary">
                    Evaluating actual finished Master, Short, captions, chapters, and packaging
                    truth.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleRunQA(true)}
                  disabled={isRunningQA || !packagingData?.has_master}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-surface-2 hover:bg-surface-3 text-text-primary border border-border-subtle rounded-lg transition-colors disabled:opacity-50"
                  data-testid="btn-rerun-qa"
                >
                  {isRunningQA ? (
                    <Loader2 className="size-3.5 animate-spin text-primary" />
                  ) : (
                    <RefreshCw className="size-3.5" />
                  )}
                  <span>Re-check Output</span>
                </button>
              </div>
            </div>

            {/* Compact Release Checklist */}
            <div className="space-y-2">
              <label className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">
                Release Verification Checklist
              </label>

              <div
                className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5"
                data-testid="release-checklist"
              >
                {[
                  {
                    key: "master_video",
                    label: "Master Video",
                    pass: qaData?.checklist?.master_video,
                  },
                  { key: "audio", label: "Audio", pass: qaData?.checklist?.audio },
                  { key: "captions", label: "Captions", pass: qaData?.checklist?.captions },
                  { key: "chapters", label: "Chapters", pass: qaData?.checklist?.chapters },
                  {
                    key: "short",
                    label: "Short",
                    pass: qaData?.has_short ? qaData?.checklist?.short : null,
                  },
                  { key: "packaging", label: "Packaging", pass: qaData?.checklist?.packaging },
                  { key: "claims", label: "Claims", pass: qaData?.checklist?.claims },
                ].map((item) => (
                  <div
                    key={item.key}
                    className={`p-2.5 rounded-lg border flex flex-col items-center justify-center text-center transition-all ${
                      item.pass === true
                        ? "bg-emerald-500/10 border-emerald-500/25 text-emerald-400"
                        : item.pass === false
                          ? "bg-rose-500/10 border-rose-500/25 text-rose-400"
                          : "bg-surface-2/60 border-border-subtle text-text-muted"
                    }`}
                    data-testid={`checklist-item-${item.key}`}
                  >
                    <span className="text-[11px] font-medium text-text-secondary truncate w-full">
                      {item.label}
                    </span>
                    <div className="mt-1 font-bold text-sm">
                      {item.pass === true ? "✓" : item.pass === false ? "!" : "—"}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Identified Issues & Auto-correction Bar */}
            {Boolean(qaData?.review?.issues?.length) && (
              <div className="space-y-3 pt-2" data-testid="section-qa-issues">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="size-4 text-rose-400" />
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-rose-400">
                      QA Defects Requiring Fix ({qaData?.review?.issues?.length})
                    </h4>
                  </div>

                  {/* 1-Cycle Auto-correct button */}
                  <button
                    type="button"
                    onClick={handleAutoCorrectQA}
                    disabled={isCorrectingQA || isRunningQA}
                    className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold bg-primary text-white hover:bg-primary/90 rounded-md transition-colors shadow-xs disabled:opacity-50"
                    data-testid="btn-auto-correct-qa"
                  >
                    {isCorrectingQA ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <Wand2 className="size-3.5" />
                    )}
                    <span>Auto-correct with Nina</span>
                  </button>
                </div>

                <div className="space-y-2.5">
                  {qaData?.review?.issues?.map((issue: ReleaseIssue, idx: number) => (
                    <div
                      key={idx}
                      className="p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/25 space-y-2 text-xs"
                      data-testid={`qa-issue-${idx}`}
                    >
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-rose-300">
                            {getIssueFriendlyName(issue.issue_type)}
                          </span>
                          <span
                            className={`text-[10px] font-semibold px-2 py-0.5 rounded uppercase ${
                              issue.severity === "BLOCKING" || issue.severity === "HIGH"
                                ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                                : "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                            }`}
                          >
                            {issue.severity}
                          </span>
                        </div>

                        {issue.source_start_ms !== null && issue.source_start_ms !== undefined && (
                          <button
                            type="button"
                            onClick={() => handleSeek(issue.source_start_ms!)}
                            className="px-2 py-0.5 bg-surface-2 hover:bg-surface-3 text-text-primary rounded font-mono text-[11px] flex items-center gap-1 transition-colors border border-border-subtle"
                            title="Jump video to defect timestamp"
                            data-testid={`btn-seek-issue-${idx}`}
                          >
                            <Play className="size-2.5" />
                            <span>
                              {Math.floor(issue.source_start_ms / 60000)}:
                              {String(Math.floor((issue.source_start_ms % 60000) / 1000)).padStart(
                                2,
                                "0",
                              )}
                            </span>
                          </button>
                        )}
                      </div>

                      <p className="text-text-primary font-medium">{issue.message}</p>
                      <div className="text-[11px] text-text-secondary bg-surface-1/60 p-2 rounded border border-border-subtle space-y-1">
                        <p>
                          <strong className="text-text-primary font-semibold">
                            Suggested Action:
                          </strong>{" "}
                          {issue.suggested_action}
                        </p>
                        {issue.evidence && (
                          <p className="text-text-muted">
                            <strong className="text-text-secondary font-medium">Evidence:</strong>{" "}
                            {issue.evidence}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Itemized Claim Audit */}
            {Boolean(qaData?.review?.claim_verifications?.length) && (
              <div className="space-y-2.5 pt-2" data-testid="section-claim-audit">
                <label className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">
                  Factual & Packaging Claims Audit
                </label>

                <div className="space-y-2">
                  {qaData?.review?.claim_verifications?.map(
                    (claim: ClaimVerification, idx: number) => {
                      const badge = getClaimStatusBadge(claim.status);
                      const StatusIcon = badge.icon;
                      return (
                        <div
                          key={idx}
                          className="p-3 rounded-lg bg-surface-2/60 border border-border-subtle space-y-1 text-xs"
                          data-testid={`claim-verification-${idx}`}
                        >
                          <div className="flex items-center justify-between gap-2 flex-wrap">
                            <span className="font-semibold text-text-primary">
                              "{claim.claim_text}"
                            </span>
                            <span
                              className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border flex items-center gap-1 ${badge.color}`}
                            >
                              <StatusIcon className="size-3" />
                              {badge.label}
                            </span>
                          </div>
                          <p className="text-[11px] text-text-secondary leading-relaxed">
                            {claim.evidence}
                          </p>
                        </div>
                      );
                    },
                  )}
                </div>
              </div>
            )}
          </section>

          {/* 3. Nina Packaging Proposal Surfaces (Editable) */}
          {packagingData?.proposal && (
            <>
              {/* Primary Title & Candidates */}
              <section
                className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-4 shadow-xs"
                data-testid="section-titles"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Flame className="size-4 text-primary" />
                    <h3 className="text-xs font-semibold tracking-wide uppercase text-text-secondary">
                      Title Strategy & Candidates
                    </h3>
                  </div>
                  <span className="text-[11px] text-text-muted">
                    {packagingData.proposal.title_candidates.length} strategic angles proposed
                  </span>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-text-secondary flex items-center gap-1.5">
                      <span>Primary Title</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/15 text-primary border border-primary/30 font-semibold">
                        Active
                      </span>
                    </label>
                    <span className="text-[11px] font-mono text-text-muted">
                      {titleInput.length} / 100 chars
                    </span>
                  </div>
                  <input
                    type="text"
                    value={titleInput}
                    onChange={(e) => setTitleInput(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-surface-2 border border-border-subtle focus:border-primary rounded-lg text-sm text-text-primary font-medium focus:outline-none transition-colors"
                    placeholder="Enter final YouTube title…"
                    data-testid="input-primary-title"
                  />
                </div>

                {/* Alternative Candidates */}
                <div className="space-y-2 pt-2">
                  <label className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">
                    Alternative Strategic Angles
                  </label>

                  <div className="space-y-2.5" data-testid="list-title-candidates">
                    {packagingData.proposal.title_candidates.map(
                      (candidate: TitleCandidate, idx: number) => {
                        const isSelected = selectedTitleCandidate === candidate.text;
                        return (
                          <div
                            key={idx}
                            className={`p-3 rounded-lg border transition-all cursor-pointer ${
                              isSelected
                                ? "bg-primary/10 border-primary/40 shadow-xs"
                                : "bg-surface-2/70 border-border-subtle hover:border-border-strong hover:bg-surface-2"
                            }`}
                            onClick={() => {
                              setSelectedTitleCandidate(candidate.text);
                              setTitleInput(candidate.text);
                            }}
                            data-testid={`title-candidate-${idx}`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="space-y-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span
                                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${getAngleBadgeColor(
                                      candidate.angle,
                                    )}`}
                                  >
                                    {getAngleFriendlyName(candidate.angle)}
                                  </span>
                                  <span className="text-xs font-semibold text-text-primary truncate">
                                    {candidate.text}
                                  </span>
                                </div>
                                <p className="text-[11px] text-text-secondary leading-relaxed">
                                  {candidate.why_it_works}
                                </p>
                              </div>

                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedTitleCandidate(candidate.text);
                                  setTitleInput(candidate.text);
                                }}
                                className={`shrink-0 px-2.5 py-1 text-[11px] font-semibold rounded-md transition-colors ${
                                  isSelected
                                    ? "bg-primary text-white"
                                    : "bg-surface-3 text-text-secondary hover:text-text-primary"
                                }`}
                                data-testid={`btn-select-title-${idx}`}
                              >
                                {isSelected ? "Selected" : "Use this"}
                              </button>
                            </div>
                          </div>
                        );
                      },
                    )}
                  </div>
                </div>
              </section>

              {/* Description */}
              <section
                className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-3 shadow-xs"
                data-testid="section-description"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Edit3 className="size-4 text-primary" />
                    <h3 className="text-xs font-semibold tracking-wide uppercase text-text-secondary">
                      Publish-Ready Description
                    </h3>
                  </div>
                  <span className="text-[11px] font-mono text-text-muted">
                    {descriptionInput.length} / 5000 chars
                  </span>
                </div>

                <textarea
                  rows={8}
                  value={descriptionInput}
                  onChange={(e) => setDescriptionInput(e.target.value)}
                  className="w-full p-3.5 bg-surface-2 border border-border-subtle focus:border-primary rounded-lg text-xs font-mono text-text-secondary leading-relaxed focus:outline-none transition-colors resize-y"
                  placeholder="YouTube description with chapters and keywords…"
                  data-testid="textarea-description"
                />
              </section>

              {/* Chapters */}
              <section
                className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-4 shadow-xs"
                data-testid="section-chapters"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Layers className="size-4 text-primary" />
                    <h3 className="text-xs font-semibold tracking-wide uppercase text-text-secondary">
                      Video Chapters
                    </h3>
                  </div>
                  <span className="text-[11px] text-text-muted">Anchored to Master timeline</span>
                </div>

                <div className="space-y-2" data-testid="list-chapters">
                  {chaptersInput.map((chapter, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-3 p-2.5 rounded-lg bg-surface-2/60 border border-border-subtle hover:border-border-strong transition-colors"
                      data-testid={`chapter-item-${idx}`}
                    >
                      <button
                        type="button"
                        onClick={() => handleSeek(chapter.start_ms)}
                        className="px-2.5 py-1 rounded bg-surface-3 hover:bg-primary/20 hover:text-primary text-text-secondary font-mono text-xs font-semibold transition-colors flex items-center gap-1 shrink-0"
                        title="Jump video to timestamp"
                        data-testid={`btn-chapter-seek-${idx}`}
                      >
                        <Play className="size-2.5" />
                        <span>{chapter.formatted_time}</span>
                      </button>

                      <input
                        type="text"
                        value={chapter.title}
                        onChange={(e) => handleChapterTitleChange(idx, e.target.value)}
                        className="flex-1 px-2.5 py-1 bg-surface-1 border border-border-subtle focus:border-primary rounded text-xs text-text-primary focus:outline-none"
                        placeholder="Chapter title…"
                        data-testid={`input-chapter-title-${idx}`}
                      />
                    </div>
                  ))}
                </div>
              </section>

              {/* Thumbnails */}
              <section
                className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-4 shadow-xs"
                data-testid="section-thumbnails"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ImageIcon className="size-4 text-primary" />
                    <h3 className="text-xs font-semibold tracking-wide uppercase text-text-secondary">
                      Thumbnail Concepts & Frame Evidence
                    </h3>
                  </div>
                  <span className="text-[11px] text-text-muted">3 verified visual moments</span>
                </div>

                <div
                  className="grid grid-cols-1 md:grid-cols-3 gap-4"
                  data-testid="list-thumbnail-concepts"
                >
                  {packagingData.proposal.thumbnail_concepts.map(
                    (concept: ThumbnailConcept, idx: number) => {
                      const isSelected = selectedThumbnailId === concept.concept_id;
                      return (
                        <div
                          key={idx}
                          className={`p-4 rounded-xl border flex flex-col justify-between space-y-3 transition-all cursor-pointer ${
                            isSelected
                              ? "bg-primary/10 border-primary/50 shadow-xs"
                              : "bg-surface-2/60 border-border-subtle hover:border-border-strong hover:bg-surface-2"
                          }`}
                          onClick={() => setSelectedThumbnailId(concept.concept_id)}
                          data-testid={`thumbnail-concept-${idx}`}
                        >
                          <div className="space-y-2">
                            <div className="flex items-center justify-between">
                              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-surface-3 text-text-secondary">
                                Concept {idx + 1}
                              </span>
                              {concept.frame_verified && (
                                <span className="text-[10px] font-semibold text-emerald-400 flex items-center gap-1 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                                  <ShieldCheck className="size-3" />
                                  Verified Frame
                                </span>
                              )}
                            </div>

                            <h4 className="text-xs font-bold text-text-primary tracking-wide">
                              "{concept.headline}"
                            </h4>

                            <div className="space-y-1 text-[11px] text-text-secondary">
                              <p>
                                <strong className="text-text-primary font-medium">Subject:</strong>{" "}
                                {concept.visual_subject}
                              </p>
                              <p>
                                <strong className="text-text-primary font-medium">
                                  Composition:
                                </strong>{" "}
                                {concept.composition}
                              </p>
                              <p>
                                <strong className="text-text-primary font-medium">Emotion:</strong>{" "}
                                {concept.emotion}
                              </p>
                            </div>
                          </div>

                          <div className="pt-2 border-t border-border-subtle/60 flex items-center justify-between">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleSeek(concept.supporting_frame_ms);
                              }}
                              className="text-[10px] font-mono text-primary hover:underline flex items-center gap-1"
                              data-testid={`btn-seek-frame-${idx}`}
                            >
                              <Play className="size-2.5" />
                              <span>
                                Frame at {(concept.supporting_frame_ms / 1000).toFixed(1)}s
                              </span>
                            </button>

                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedThumbnailId(concept.concept_id);
                              }}
                              className={`px-2.5 py-1 text-[10px] font-semibold rounded ${
                                isSelected
                                  ? "bg-primary text-white"
                                  : "bg-surface-3 text-text-secondary"
                              }`}
                            >
                              {isSelected ? "Selected" : "Select"}
                            </button>
                          </div>
                        </div>
                      );
                    },
                  )}
                </div>
              </section>

              {/* Short Package */}
              {packagingData.proposal.short_package && (
                <section
                  className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-4 shadow-xs"
                  data-testid="section-short-package"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Smartphone className="size-4 text-primary" />
                      <h3 className="text-xs font-semibold tracking-wide uppercase text-text-secondary">
                        Vertical Short Package (9:16)
                      </h3>
                    </div>
                    <span className="text-[11px] text-text-muted">
                      Optimized for YouTube Shorts
                    </span>
                  </div>

                  <div className="space-y-3">
                    <div className="space-y-1">
                      <label className="text-[11px] font-medium text-text-secondary">
                        Short Title
                      </label>
                      <input
                        type="text"
                        value={shortTitleInput}
                        onChange={(e) => setShortTitleInput(e.target.value)}
                        className="w-full px-3 py-2 bg-surface-2 border border-border-subtle focus:border-primary rounded-lg text-xs text-text-primary focus:outline-none"
                        placeholder="Short title…"
                        data-testid="input-short-title"
                      />
                    </div>

                    <div className="p-3 bg-surface-2/60 rounded-lg border border-border-subtle space-y-1">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
                        Spoken Opening Hook
                      </span>
                      <p className="text-xs text-text-primary font-medium">
                        "{packagingData.proposal.short_package.hook}"
                      </p>
                    </div>

                    <div className="space-y-1">
                      <label className="text-[11px] font-medium text-text-secondary">
                        Short Description / Caption
                      </label>
                      <textarea
                        rows={3}
                        value={shortDescInput}
                        onChange={(e) => setShortDescInput(e.target.value)}
                        className="w-full p-2.5 bg-surface-2 border border-border-subtle focus:border-primary rounded-lg text-xs text-text-secondary focus:outline-none font-mono"
                        placeholder="Short description…"
                        data-testid="textarea-short-desc"
                      />
                    </div>

                    {Boolean(packagingData.proposal.short_package.hashtags?.length) && (
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {packagingData.proposal.short_package.hashtags?.map((tag, idx) => (
                          <span
                            key={idx}
                            className="text-[11px] font-mono px-2 py-0.5 bg-surface-2 text-primary rounded border border-primary/20"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </section>
              )}
            </>
          )}
        </div>

        {/* Right Rail (4 cols): Release Action, Agent Team (Iris & Nina), Summary */}
        <div className="lg:col-span-4 space-y-5 lg:sticky lg:top-20">
          {/* Release Gate Summary / Ready to Publish Card */}
          <div
            className={`rounded-xl p-5 border space-y-4 shadow-sm transition-all ${
              publishJobData?.job?.status === "completed"
                ? "bg-emerald-500/10 border-emerald-500/30"
                : isReleaseReady
                  ? "bg-emerald-500/10 border-emerald-500/30"
                  : "bg-surface-1 border-border-subtle"
            }`}
            data-testid="release-gate-card"
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-text-muted">
                Release Gate Status
              </span>
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                  publishJobData?.job?.status === "completed"
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                    : isReleaseReady
                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                      : "bg-surface-2 text-text-secondary border border-border-subtle"
                }`}
                data-testid="release-gate-badge"
              >
                {publishJobData?.job?.status === "completed"
                  ? publishJobData.job.actual_privacy === "private"
                    ? "Uploaded Privately"
                    : publishJobData.job.actual_privacy === "unlisted"
                      ? "Published Unlisted"
                      : "Published"
                  : isReleaseReady
                    ? "Gate Passed"
                    : "Gate Locked"}
              </span>
            </div>

            <div>
              <h3 className="text-base font-bold text-text-primary">
                {publishJobData?.job?.status === "completed"
                  ? publishJobData.job.actual_privacy === "private"
                    ? "Uploaded Privately"
                    : publishJobData.job.actual_privacy === "unlisted"
                      ? "Published Unlisted"
                      : "Published"
                  : isReleaseReady
                    ? "Ready to Publish"
                    : "Release Gate Review"}
              </h3>
              <p className="text-xs text-text-secondary mt-1 leading-relaxed">
                {publishJobData?.job?.status === "completed"
                  ? "Video is live on YouTube. Creator approval and verification complete."
                  : isReleaseReady
                    ? "All media continuity, loudness, caption alignment, and packaging claims are verified."
                    : "Iris must approve all quality and factual criteria before publishing."}
              </p>
            </div>

            {/* In-Progress Uploading / Processing Display */}
            {publishJobData?.job &&
              (publishJobData.job.status === "uploading" ||
                publishJobData.job.status === "processing" ||
                publishJobData.job.status === "pending") && (
                <div
                  className="p-3.5 rounded-lg bg-surface-2 border border-primary/30 space-y-2.5"
                  data-testid="section-upload-progress"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-text-primary flex items-center gap-1.5">
                      <Loader2 className="size-3.5 text-primary animate-spin" />
                      {publishJobData.job.status === "uploading"
                        ? `Uploading to YouTube ${publishJobData.job.progress_percent?.toFixed(0) || 0}%`
                        : publishJobData.job.status === "processing"
                          ? "YouTube is processing the video…"
                          : "Preparing YouTube upload…"}
                    </span>
                    <span className="text-[11px] font-mono text-primary font-semibold">
                      {publishJobData.job.progress_percent?.toFixed(0) || 0}%
                    </span>
                  </div>
                  <div className="w-full bg-surface-3 h-2 rounded-full overflow-hidden border border-border-subtle">
                    <div
                      className="bg-primary h-full transition-all duration-300 rounded-full"
                      style={{ width: `${Math.max(5, publishJobData.job.progress_percent || 0)}%` }}
                    ></div>
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-text-muted">
                    <span>Resumable media stream</span>
                    {Boolean(publishJobData.job.total_bytes) && (
                      <span>
                        {((publishJobData.job.bytes_uploaded || 0) / (1024 * 1024)).toFixed(1)} MB /{" "}
                        {((publishJobData.job.total_bytes || 0) / (1024 * 1024)).toFixed(1)} MB
                      </span>
                    )}
                  </div>
                </div>
              )}

            {/* Completed Success Box with YouTube Link */}
            {publishJobData?.job?.status === "completed" && (
              <div
                className="space-y-3 pt-2 border-t border-border-subtle"
                data-testid="section-publish-completed"
              >
                <div className="p-3.5 rounded-lg bg-surface-2 border border-emerald-500/30 space-y-2.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-text-primary flex items-center gap-1.5">
                      <CheckCircle2 className="size-4 text-emerald-400" />
                      <span>
                        {publishJobData.job.actual_privacy === "private"
                          ? "Uploaded privately"
                          : "Published"}
                      </span>
                    </span>
                    <span
                      className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-3 text-text-secondary border border-border-subtle"
                      data-testid="text-youtube-video-id"
                    >
                      ID: {publishJobData.job.youtube_video_id}
                    </span>
                  </div>

                  {/* Thumbnail Status */}
                  <div className="text-[11px] text-text-secondary flex items-center gap-2">
                    {publishJobData.job.thumbnail_status === "completed" ? (
                      <span className="text-emerald-400 flex items-center gap-1">
                        <Check className="size-3" />
                        Thumbnail uploaded
                      </span>
                    ) : publishJobData.job.thumbnail_status === "failed" ? (
                      <span className="text-amber-400 flex items-center gap-1">
                        <AlertTriangle className="size-3" />
                        Thumbnail needs attention
                      </span>
                    ) : null}
                    {publishJobData.job.short_youtube_video_id && (
                      <span className="text-text-muted">
                        • Short ID: {publishJobData.job.short_youtube_video_id}
                      </span>
                    )}
                  </div>

                  {/* Open on YouTube Button */}
                  {publishJobData.job.youtube_url && (
                    <a
                      href={publishJobData.job.youtube_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="w-full py-2 px-3 bg-red-600 hover:bg-red-700 text-white font-bold text-xs rounded-lg flex items-center justify-center gap-2 transition-colors shadow-xs"
                      data-testid="btn-open-on-youtube"
                    >
                      <YouTubeIcon className="size-4" />
                      <span>Open on YouTube</span>
                      <ExternalLink className="size-3.5" />
                    </a>
                  )}
                </div>

                {/* Audit restriction banner if applicable */}
                {publishJobData.job.audit_restriction_detected && (
                  <div
                    className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-[11px] text-amber-300 flex items-start gap-2 leading-relaxed"
                    data-testid="banner-audit-restriction"
                  >
                    <Info className="size-4 text-amber-400 shrink-0 mt-0.5" />
                    <span>
                      Uploaded successfully, but YouTube restricted this API project to private
                      uploads. YouTube API compliance verification is required before public
                      publishing.
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Publishing Action Button */}
            {publishJobData?.job?.status !== "completed" &&
              publishJobData?.job?.status !== "uploading" &&
              publishJobData?.job?.status !== "processing" && (
                <div className="pt-2 border-t border-border-subtle space-y-2">
                  <button
                    type="button"
                    disabled={!isReleaseReady}
                    onClick={handleOpenPublishModal}
                    className={`w-full py-2.5 px-4 rounded-lg font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-xs ${
                      isReleaseReady
                        ? "bg-red-600 hover:bg-red-700 text-white cursor-pointer"
                        : "bg-surface-3 text-text-muted cursor-not-allowed opacity-60"
                    }`}
                    data-testid="btn-publish-to-youtube"
                  >
                    <YouTubeIcon className="size-4" />
                    <span>{isReleaseReady ? "Publish to YouTube" : "Fix Required to Release"}</span>
                  </button>
                  <p className="text-[10px] text-center text-text-muted">
                    Requires creator approval before external YouTube upload.
                  </p>
                </div>
              )}
          </div>

          {/* Iris (QA Agent) Card */}
          <div
            className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-4 shadow-xs"
            data-testid="iris-agent-card"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setDrawerAgent("iris")}
                  className="relative group focus:outline-none"
                  title="Click to configure Iris QA settings & view memory"
                  data-testid="btn-iris-avatar"
                >
                  <img
                    src={irisAvatar}
                    alt="Iris QA Agent"
                    className="size-12 rounded-full object-cover border-2 border-emerald-500/40 group-hover:border-emerald-500 transition-all shadow-sm"
                  />
                  <div className="absolute inset-0 rounded-full bg-black/20 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                    <span className="text-[9px] text-white font-bold">Edit</span>
                  </div>
                </button>

                <div>
                  <div className="flex items-center gap-1.5">
                    <h3 className="text-sm font-bold text-text-primary">Iris</h3>
                    <span className="size-2 rounded-full bg-emerald-400"></span>
                  </div>
                  <p className="text-xs text-text-secondary">Quality Assurance Gate</p>
                </div>
              </div>

              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                gemini-3.7-flash
              </span>
            </div>

            <p className="text-xs text-text-muted leading-relaxed">
              Iris is the independent release gatekeeper evaluating video continuity, audio
              loudness, caption timing, chapter order, and factual claim truth.
            </p>

            <button
              type="button"
              onClick={() => setDrawerAgent("iris")}
              className="w-full py-1.5 text-xs font-semibold bg-surface-2 hover:bg-surface-3 text-text-primary rounded-lg border border-border-subtle transition-colors"
            >
              Open Iris Settings
            </button>
          </div>

          {/* Nina (Packaging Agent) Card */}
          <div
            className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-4 shadow-xs"
            data-testid="nina-agent-card"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setDrawerAgent("nina")}
                  className="relative group focus:outline-none"
                  title="Click to configure Nina's prompt & view memory"
                  data-testid="btn-nina-avatar"
                >
                  <img
                    src={ninaAvatar}
                    alt="Nina Packaging Agent"
                    className="size-12 rounded-full object-cover border-2 border-primary/40 group-hover:border-primary transition-all shadow-sm"
                  />
                  <div className="absolute inset-0 rounded-full bg-black/20 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                    <span className="text-[9px] text-white font-bold">Edit</span>
                  </div>
                </button>

                <div>
                  <div className="flex items-center gap-1.5">
                    <h3 className="text-sm font-bold text-text-primary">Nina</h3>
                    <span className="size-2 rounded-full bg-emerald-400"></span>
                  </div>
                  <p className="text-xs text-text-secondary">Packaging Agent</p>
                </div>
              </div>

              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Gemini 3.7 Flash
              </span>
            </div>

            <p className="text-xs text-text-muted leading-relaxed">
              Nina turns approved master video into high-converting titles, publish-ready
              descriptions, chapters, and thumbnail moments.
            </p>

            <button
              type="button"
              onClick={() => handleGeneratePackaging(true)}
              disabled={isGeneratingPackaging || !packagingData?.has_master}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-semibold text-text-primary bg-surface-2 hover:bg-surface-3 border border-border-subtle rounded-lg transition-colors disabled:opacity-50 shadow-xs"
              data-testid="btn-regenerate-packaging"
            >
              {isGeneratingPackaging ? (
                <Loader2 className="size-3.5 animate-spin text-primary" />
              ) : (
                <RotateCcw className="size-3.5" />
              )}
              <span>Regenerate Packaging</span>
            </button>
          </div>

          {/* Channel Evidence & Packaging Summary Card */}
          {packagingData?.proposal && (
            <div
              className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-4 shadow-xs"
              data-testid="section-packaging-rationale"
            >
              <div className="flex items-center gap-2">
                <Lightbulb className="size-4 text-amber-400" />
                <h4 className="text-xs font-semibold tracking-wide uppercase text-text-secondary">
                  Channel Rationale & Evidence
                </h4>
              </div>

              <div className="space-y-3">
                <div className="p-3 rounded-lg bg-surface-2/70 border border-border-subtle space-y-1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
                    Channel Evidence
                  </span>
                  <p className="text-xs text-text-primary font-medium leading-relaxed">
                    "{packagingData.proposal.channel_evidence}"
                  </p>
                </div>

                <div className="space-y-1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
                    Packaging Strategy
                  </span>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    {packagingData.proposal.packaging_summary}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Nina Agent Activity Feed */}
          <div
            className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-3 shadow-xs"
            data-testid="section-agent-activity"
          >
            <h4 className="text-xs font-semibold tracking-wide uppercase text-text-secondary">
              Agent Activity
            </h4>

            <div className="space-y-2.5 text-xs">
              <div className="flex items-start gap-2 text-text-secondary">
                <CheckCircle2 className="size-3.5 text-emerald-400 shrink-0 mt-0.5" />
                <span>Nina packaged the approved master video.</span>
              </div>
              <div className="flex items-start gap-2 text-text-secondary">
                <CheckCircle2 className="size-3.5 text-emerald-400 shrink-0 mt-0.5" />
                <span>Iris evaluated media continuity, audio levels, and packaging claims.</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Agent Settings Drawer (Prompt & Memory tabs) */}
      <AgentSettingsDrawer
        isOpen={drawerAgent !== null}
        agentId={drawerAgent || "iris"}
        onClose={() => setDrawerAgent(null)}
      />

      {/* Publish Confirmation Modal */}
      <PublishConfirmationModal
        isOpen={isPublishModalOpen}
        onClose={() => setIsPublishModalOpen(false)}
        prepData={prepData}
        isLoadingPrep={isLoadingPrep}
        onConfirmPublish={handleConfirmPublish}
        isPublishing={isPublishing}
        onGrantUploadAccess={handleGrantUploadAccess}
        onConnectYouTube={handleConnectYouTube}
      />
    </div>
  );
};

export default ReleasePage;
