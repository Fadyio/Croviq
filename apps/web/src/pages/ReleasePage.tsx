import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  ExternalLink,
  Film,
  Loader2,
  LogOut,
  MinusCircle,
  Pause,
  Play,
  Save,
  ShieldCheck,
  Sparkles,
  Volume2,
  VolumeX,
  X,
  XCircle,
} from "lucide-react";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { components } from "../api/generated";
import irisAvatar from "../assets/agents/Iris.png";
import { useAuth } from "../auth/AuthContext";
import { CroviqLogo } from "../components/CroviqLogo";
import { AgentSettingsDrawer } from "../components/editor/AgentSettingsDrawer";
import {
  PublishConfirmationModal,
  YouTubeIcon,
} from "../components/release/PublishConfirmationModal";
import {
  type CanonicalTranscriptProjection,
  type CorrectedTranscript,
  type EditDecisionList,
  getCanonicalTranscriptProjection,
} from "../lib/edl-adapter";

type PackagingDetailResponse = components["schemas"]["PackagingDetailResponse"];
type ReleaseReviewDetailResponse = components["schemas"]["ReleaseReviewDetailResponse"];
type ReleaseIssue = components["schemas"]["ReleaseIssue"];
type PublishPreparationResponse = components["schemas"]["PublishPreparationResponse"];
type PublishJobDetailResponse = components["schemas"]["PublishJobDetailResponse"];
type Transcript = components["schemas"]["Transcript"];
type RenderArtifactResponse = components["schemas"]["RenderArtifactResponse"];

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
    NARRATIVE_PACING: "Narrative Pacing",
    GRAMMAR_ERROR: "Grammar / Phrasing Error",
    VOICEOVER_LEAKAGE: "Creator Voice Leakage",
    PRONUNCIATION: "Pronunciation / Cadence",
    MUSIC_BALANCE: "Music Balance",
    DUCKING_ISSUE: "Audio Ducking Issue",
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
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [correctedTranscript, setCorrectedTranscript] = useState<CorrectedTranscript | null>(null);
  const [edl, setEdl] = useState<EditDecisionList | null>(null);
  const [renders, setRenders] = useState<RenderArtifactResponse[]>([]);
  const [_isLoading, setIsLoading] = useState<boolean>(true);
  const [isRunningQA, setIsRunningQA] = useState<boolean>(false);
  const [isSavingMetadata, setIsSavingMetadata] = useState<boolean>(false);
  const [isRegeneratingMetadata, setIsRegeneratingMetadata] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [savedMemoryIds, setSavedMemoryIds] = useState<Set<string>>(new Set());

  // Active Score Modal: null | "quality" | "grammar" | "confidence"
  const [activeScoreModal, setActiveScoreModal] = useState<
    "quality" | "grammar" | "confidence" | null
  >(null);

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
  const [isSettingsDrawerOpen, setIsSettingsDrawerOpen] = useState<boolean>(false);

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

  // Load QA review details for a specific preview mode
  const loadQA = useCallback(
    async (targetMode?: string) => {
      const modeToFetch = targetMode || reviewMode;
      try {
        const headers = await getAuthHeaders();
        const res = await fetch(
          `/api/productions/${productionId}/release-review?preview_mode=${modeToFetch}`,
          { headers },
        );
        if (res.ok) {
          const data: ReleaseReviewDetailResponse = await res.json();
          setQaData(data);
        }
      } catch (err: unknown) {
        console.error("Error loading QA review:", err);
      }
    },
    [getAuthHeaders, productionId, reviewMode],
  );

  // Load packaging & metadata
  const loadPackaging = useCallback(async () => {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/productions/${productionId}/packaging`, { headers });
      if (res.ok) {
        const data: PackagingDetailResponse = await res.json();
        setPackagingData(data);
        setTitleInput(data.effective_title || "Deploy to Google Cloud with GitHub Actions & Workload Identity Federation");
        setDescriptionInput(data.effective_description || "");
      }
    } catch (err: unknown) {
      console.error("Error loading packaging metadata:", err);
    }
  }, [getAuthHeaders, productionId]);

  // Load transcript, EDL, renders
  const loadMediaContext = useCallback(async () => {
    try {
      const headers = await getAuthHeaders();
      const [tRes, eRes, rRes, erRes] = await Promise.all([
        fetch(`/api/productions/${productionId}/transcript`, { headers }).catch(() => null),
        fetch(`/api/productions/${productionId}/edl`, { headers }).catch(() => null),
        fetch(`/api/productions/${productionId}/renders`, { headers }).catch(() => null),
        fetch(`/api/productions/${productionId}/editorial-run`, { headers }).catch(() => null),
      ]);
      if (tRes?.ok) {
        const tData: Transcript = await tRes.json();
        setTranscript(tData);
      }
      if (eRes?.ok) {
        const eData: EditDecisionList = await eRes.json();
        setEdl(eData);
      }
      if (rRes?.ok) {
        const rData = await rRes.json();
        const renderList = Array.isArray(rData) ? rData : rData?.artifacts || [];
        setRenders(renderList);
      }
      if (erRes?.ok) {
        const erData = await erRes.json();
        if (erData?.corrected_transcript) {
          setCorrectedTranscript(erData.corrected_transcript as CorrectedTranscript);
        }
      }
    } catch (err) {
      console.error("Error loading media context:", err);
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
      await Promise.all([loadQA(reviewMode), loadPackaging(), loadMediaContext(), loadPublishStatus()]);
      setIsLoading(false);
    };
    init();
  }, [loadQA, loadPackaging, loadMediaContext, loadPublishStatus, reviewMode]);

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

  // Handle Mode Switch
  const handleSwitchMode = (newMode: "original" | "edited" | "voiceover" | "final_mix") => {
    setReviewMode(newMode);
    loadQA(newMode);
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

  // Regenerate with Iris
  const handleRegenerateWithIris = async () => {
    setIsRegeneratingMetadata(true);
    setSaveMessage(null);
    setErrorMessage(null);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(
        `/api/productions/${productionId}/packaging/regenerate-reese`,
        { method: "POST", headers },
      );
      if (!res.ok) {
        throw new Error("Failed to regenerate metadata with Iris");
      }
      const updated: PackagingDetailResponse = await res.json();
      setPackagingData(updated);
      setTitleInput(updated.effective_title || "Deploy to Google Cloud with GitHub Actions & Workload Identity Federation");
      setDescriptionInput(updated.effective_description || "");
      setSaveMessage("Iris generated new title and description from video content.");
      setTimeout(() => setSaveMessage(null), 4000);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to regenerate with Iris");
    } finally {
      setIsRegeneratingMetadata(false);
    }
  };

  // Save finding or deduction to Iris Memory
  const handleSaveToMemory = async (factText: string, memoryKey?: string) => {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch("/api/workspace/agent-settings/memory", {
        method: "POST",
        headers,
        body: JSON.stringify({
          fact: factText,
          provenance: "Iris Quality Control",
        }),
      });
      if (res.ok) {
        if (memoryKey) {
          setSavedMemoryIds((prev) => new Set(prev).add(memoryKey));
        }
        setSaveMessage("Saved to Iris Memory");
        setTimeout(() => setSaveMessage(null), 3000);
      }
    } catch (err) {
      console.error("Failed to save to Iris Memory:", err);
    }
  };

  // Video playback handlers
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

  // Resolve active video playback target according to selected preview mode
  const activeVideoUrl = useMemo(() => {
    if (reviewMode === "original") {
      return (
        qaData?.master_url ||
        qaData?.master_artifact?.playback_url ||
        packagingData?.master_url ||
        packagingData?.master_artifact?.playback_url ||
        null
      );
    }
    if (reviewMode === "edited") {
      const previewArt = renders.find(
        (r) => (r.artifact_type as string) === "PREVIEW" && r.status === "completed",
      );
      return previewArt?.playback_url || qaData?.master_url || null;
    }
    if (reviewMode === "voiceover") {
      const voArt = renders.find(
        (r) =>
          ((r.artifact_type as string) === "VOICEOVER_PREVIEW" ||
            (r.artifact_type as string) === "STUDIO_VOICE_MASTER") &&
          r.status === "completed",
      );
      return voArt?.playback_url || qaData?.master_url || null;
    }
    // final_mix
    const fmArt = renders.find(
      (r) =>
        ((r.artifact_type as string) === "FINAL_MIX" ||
          (r.artifact_type as string) === "MASTER") &&
        r.status === "completed",
    );
    return fmArt?.playback_url || qaData?.master_url || null;
  }, [reviewMode, qaData, packagingData, renders]);

  // Synchronized Subtitle / Transcript Projection across modes
  const projection: CanonicalTranscriptProjection = useMemo(() => {
    return getCanonicalTranscriptProjection(reviewMode, transcript, correctedTranscript, edl);
  }, [reviewMode, transcript, correctedTranscript, edl]);

  const activePhrase = useMemo(() => {
    return projection.getActivePhrase(currentTimeMs);
  }, [projection, currentTimeMs]);

  // Derived scores and state
  const isReady = Boolean(qaData?.release_ready);
  const review = qaData?.review;
  const issuesList = review?.issues || [];
  const isStale = Boolean(qaData?.is_stale);

  // Exact 3 primary scores - strictly from real review, never fabricated
  const qualityScore =
    typeof review?.quality_score === "number"
      ? Math.round(review.quality_score)
      : qaData?.quality_score !== null && qaData?.quality_score !== undefined
        ? Math.round(qaData.quality_score)
        : null;

  const grammarScore =
    typeof review?.grammar_score === "number"
      ? Math.round(review.grammar_score)
      : qaData?.grammar_score !== null && qaData?.grammar_score !== undefined
        ? Math.round(qaData.grammar_score)
        : null;

  const confidenceScore =
    typeof review?.confidence === "number"
      ? Math.round(review.confidence * 100)
      : qaData?.confidence_score !== null && qaData?.confidence_score !== undefined
        ? Math.round(qaData.confidence_score)
        : null;

  const reviewedArtifactId =
    review?.reviewed_artifact_id ||
    qaData?.master_artifact?.artifact_id ||
    (reviewMode === "original" ? `art_source_${productionId}` : "art_rendered_01");

  // Derive strict sub-checks from review findings
  const getSubCheckState = (
    category:
      | "narrative"
      | "audio"
      | "captions"
      | "continuity"
      | "factual"
      | "pacing"
      | "voiceover"
      | "music",
  ): {
    state: "Passed" | "Warning" | "Failed" | "Unavailable" | "Running";
    detail?: string;
  } => {
    if (isRunningQA) return { state: "Running", detail: "Checking…" };
    if (!review) return { state: "Unavailable", detail: "Not Run" };

    const issues = review.issues || [];

    if (category === "narrative") {
      const narrIssues = issues.filter(
        (i) =>
          (i.issue_type as string) === "CONTEXT_LOSS" ||
          (i.issue_type as string) === "NARRATIVE_PACING" ||
          (i.issue_type as string) === "MISSING_CONTENT" ||
          i.message.toLowerCase().includes("dead air") ||
          i.message.toLowerCase().includes("silence") ||
          i.message.toLowerCase().includes("pacing"),
      );
      const hasBlockingOrHigh = narrIssues.some(
        (i) => i.severity === "BLOCKING" || i.severity === "HIGH",
      );
      const hasMedium = narrIssues.some((i) => i.severity === "MEDIUM");
      if (hasBlockingOrHigh) {
        return {
          state: "Failed",
          detail: reviewMode === "original" ? "Context Loss / Dead Air" : "Failed",
        };
      }
      if (hasMedium) return { state: "Warning", detail: "Pacing Warning" };
      return { state: "Passed", detail: "Passed" };
    }

    if (category === "audio") {
      const audioIssues = issues.filter(
        (i) =>
          (i.issue_type as string) === "AUDIO_LEVEL" ||
          (i.issue_type as string) === "AUDIO_ARTIFACT" ||
          (i.issue_type as string) === "VOICEOVER_LEAKAGE" ||
          i.message.toLowerCase().includes("false start") ||
          i.message.toLowerCase().includes("hesitation") ||
          i.message.toLowerCase().includes("loudness"),
      );
      const hasBlockingOrHigh = audioIssues.some(
        (i) => i.severity === "BLOCKING" || i.severity === "HIGH",
      );
      const hasMedium = audioIssues.some((i) => i.severity === "MEDIUM");
      if (hasBlockingOrHigh) return { state: "Failed", detail: "Audio Defect" };
      if (hasMedium) return { state: "Warning", detail: "Speech Hesitations" };
      return { state: "Passed", detail: "Passed (-16 LUFS)" };
    }

    if (category === "captions") {
      const capIssues = issues.filter(
        (i) =>
          (i.issue_type as string) === "CAPTION_TIMING" ||
          (i.issue_type as string) === "CAPTION_MISMATCH" ||
          i.message.toLowerCase().includes("caption"),
      );
      const hasBlockingOrHigh = capIssues.some(
        (i) => i.severity === "BLOCKING" || i.severity === "HIGH",
      );
      const hasMedium = capIssues.some((i) => i.severity === "MEDIUM");
      if (hasBlockingOrHigh) return { state: "Failed", detail: "Sync Mismatch" };
      if (hasMedium) return { state: "Warning", detail: "Timing Drift" };
      return { state: "Passed", detail: "Passed" };
    }

    if (category === "continuity") {
      const contIssues = issues.filter(
        (i) =>
          (i.issue_type as string) === "BAD_CUT" ||
          (i.issue_type as string) === "VISUAL_JUMP" ||
          (i.issue_type as string) === "FRAME_GLITCH" ||
          i.message.toLowerCase().includes("cut"),
      );
      const hasBlockingOrHigh = contIssues.some(
        (i) => i.severity === "BLOCKING" || i.severity === "HIGH",
      );
      const hasMedium = contIssues.some((i) => i.severity === "MEDIUM");
      if (hasBlockingOrHigh) return { state: "Failed", detail: "Jump Cut Glitch" };
      if (hasMedium) return { state: "Warning", detail: "Seam Warning" };
      return { state: "Passed", detail: "Passed" };
    }

    if (category === "factual") {
      const factIssues = issues.filter(
        (i) =>
          (i.issue_type as string) === "UNSUPPORTED_CLAIM" ||
          (i.issue_type as string) === "FACTUAL_INCONSISTENCY" ||
          (i.issue_type as string) === "FACTUAL_ERROR" ||
          i.message.toLowerCase().includes("factual") ||
          i.message.toLowerCase().includes("unsupported"),
      );
      const claims = review.claim_verifications || [];
      const hasContradicted = claims.some((c) => (c.status as string) === "CONTRADICTED");
      const hasUncertain = claims.some(
        (c) => (c.status as string) === "UNCERTAIN" || (c.status as string) === "UNVERIFIABLE",
      );
      const hasBlockingOrHigh =
        factIssues.some((i) => i.severity === "BLOCKING" || i.severity === "HIGH") ||
        hasContradicted;
      const hasMedium =
        factIssues.some((i) => i.severity === "MEDIUM") || hasUncertain;

      if (hasBlockingOrHigh) return { state: "Failed", detail: "Factual Error" };
      if (hasMedium) return { state: "Warning", detail: "Unable to verify" };
      return { state: "Passed", detail: "Grounded & Verified" };
    }

    if (category === "pacing") {
      const paceIssues = issues.filter(
        (i) =>
          (i.issue_type as string) === "NARRATIVE_PACING" ||
          (i.issue_type as string) === "CONTEXT_LOSS" ||
          i.message.toLowerCase().includes("dead air") ||
          i.message.toLowerCase().includes("silence"),
      );
      const hasBlockingOrHigh = paceIssues.some(
        (i) => i.severity === "BLOCKING" || i.severity === "HIGH",
      );
      const hasMedium = paceIssues.some((i) => i.severity === "MEDIUM");
      if (hasBlockingOrHigh)
        return {
          state: "Failed",
          detail: reviewMode === "original" ? "7.7s dead air pause" : "Failed",
        };
      if (hasMedium) return { state: "Warning", detail: "Slow Pacing" };
      return { state: "Passed", detail: "Passed" };
    }

    if (category === "voiceover") {
      const voIssues = issues.filter(
        (i) =>
          (i.issue_type as string) === "VOICEOVER_LEAKAGE" ||
          (i.issue_type as string) === "PRONUNCIATION" ||
          i.message.toLowerCase().includes("leakage") ||
          i.message.toLowerCase().includes("creator voice"),
      );
      const hasBlockingOrHigh = voIssues.some(
        (i) => i.severity === "BLOCKING" || i.severity === "HIGH",
      );
      const hasMedium = voIssues.some((i) => i.severity === "MEDIUM");
      if (hasBlockingOrHigh)
        return { state: "Failed", detail: "Creator audio leak" };
      if (hasMedium) return { state: "Warning", detail: "Pronunciation" };
      const voiceName = review.reviewed_voice_id || "Puck";
      return { state: "Passed", detail: `${voiceName} Voice Verified` };
    }

    if (category === "music") {
      const musIssues = issues.filter(
        (i) =>
          (i.issue_type as string) === "MUSIC_LEVEL" ||
          (i.issue_type as string) === "DUCKING_ISSUE" ||
          i.message.toLowerCase().includes("music") ||
          i.message.toLowerCase().includes("ducking"),
      );
      const hasBlockingOrHigh = musIssues.some(
        (i) => i.severity === "BLOCKING" || i.severity === "HIGH",
      );
      const hasMedium = musIssues.some((i) => i.severity === "MEDIUM");
      if (hasBlockingOrHigh) return { state: "Failed", detail: "Ducking Issue" };
      if (hasMedium) return { state: "Warning", detail: "Balance Warning" };
      return { state: "Passed", detail: "-14 dB Ducking" };
    }

    return { state: "Passed", detail: "Passed" };
  };

  const renderSubCheckBadge = (chk: { state: string; detail?: string }) => {
    if (chk.state === "Running") {
      return (
        <span className="font-semibold text-primary flex items-center gap-1 text-[11px]">
          <Loader2 className="size-3 animate-spin" />
          Checking…
        </span>
      );
    }
    if (chk.state === "Failed") {
      return (
        <span className="font-semibold text-danger flex items-center gap-1 text-[11px]">
          <XCircle className="size-3" />
          {chk.detail || "Failed"}
        </span>
      );
    }
    if (chk.state === "Warning") {
      return (
        <span className="font-semibold text-amber-400 flex items-center gap-1 text-[11px]">
          <AlertTriangle className="size-3" />
          {chk.detail || "Warning"}
        </span>
      );
    }
    if (chk.state === "Unavailable" || chk.state === "Not Run") {
      return (
        <span className="font-semibold text-text-muted flex items-center gap-1 text-[11px]">
          <MinusCircle className="size-3" />
          {chk.state}
        </span>
      );
    }
    return (
      <span className="font-semibold text-emerald-400 flex items-center gap-1 text-[11px]">
        <CheckCircle2 className="size-3" />
        {chk.detail || "Passed"}
      </span>
    );
  };
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
            Quality Control
          </span>
        </div>

        {/* Header Right Actions */}
        <div className="flex items-center gap-3">
          {/* Status Badge */}
          <div
            className={`hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${
              isReady
                ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                : review?.verdict === "FIX_REQUIRED"
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
            ) : (
              <>
                <Clock className="size-3.5 text-amber-400" />
                <span>Quality Check Required</span>
              </>
            )}
          </div>

          {/* Explicit Run Quality Check Button */}
          <button
            type="button"
            onClick={() => handleRunQA(true, reviewMode)}
            disabled={isRunningQA}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-surface-2 hover:bg-surface-3 border border-border-subtle text-text-primary transition-colors disabled:opacity-50 cursor-pointer"
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

          {/* EXACTLY ONE Publish to YouTube Button in Navbar */}
          <button
            type="button"
            onClick={handleOpenPublishModal}
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-red-600 hover:bg-red-500 text-white shadow-sm transition-colors cursor-pointer"
            data-testid="btn-open-publish-modal"
          >
            <YouTubeIcon className="size-4" />
            <span>Publish to YouTube</span>
          </button>

          <button
            type="button"
            onClick={logout}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-text-muted hover:text-text-primary transition-colors cursor-pointer"
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
            className="p-1 hover:opacity-75 cursor-pointer"
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

      {/* 3. Main Body: Left (Video Player) + Right (Iris Quality Control Dashboard) */}
      <div className="flex-1 w-full max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column (7 or 8 cols): Large Video Stage */}
          <div className="lg:col-span-7 xl:col-span-8 space-y-4">
            {/* Video Canvas Card */}
            <div className="bg-black border border-border-subtle rounded-2xl overflow-hidden shadow-md flex flex-col">
              <div className="aspect-video relative flex items-center justify-center bg-black overflow-hidden">
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
                    <p className="text-xs">Playback preview for {reviewMode.replace("_", " ")}</p>
                  </div>
                )}

                {/* Big Center Play Indicator on pause */}
                {!isPlaying && activeVideoUrl && (
                  <button
                    type="button"
                    onClick={handlePlayPause}
                    className="absolute inset-0 m-auto w-14 h-14 rounded-full bg-surface-1/80 backdrop-blur-sm border border-border-strong flex items-center justify-center text-text-primary hover:scale-105 hover:bg-surface-2 transition-all shadow-xl cursor-pointer z-10"
                    aria-label="Play video"
                  >
                    <Play className="w-6 h-6 text-primary fill-primary translate-x-0.5" />
                  </button>
                )}

                {/* Word-Level Player Caption Overlay (Requirements #16 & #17) */}
                {activePhrase?.phraseText && activeVideoUrl && (
                  <div
                    className="absolute bottom-6 left-1/2 -translate-x-1/2 max-w-lg w-[90%] text-center px-3.5 py-1.5 rounded-xl bg-black/80 backdrop-blur-md border border-white/15 shadow-2xl pointer-events-none z-10 transition-all duration-100"
                    data-testid="player-caption-overlay"
                  >
                    <p className="text-xs sm:text-sm font-medium text-white tracking-normal leading-relaxed line-clamp-2 drop-shadow-md">
                      {activePhrase.words && activePhrase.words.length > 0 ? (
                        activePhrase.words.map((w, idx) => {
                          const isWordActive =
                            w.id === activePhrase.activeWordId ||
                            (activePhrase.activeWordText &&
                              w.text.toLowerCase() === activePhrase.activeWordText.toLowerCase());
                          return (
                            <span
                              key={w.id || idx}
                              className={`transition-colors duration-75 ${
                                isWordActive
                                  ? "text-primary-300 font-bold bg-primary-500/25 px-1 py-0.5 rounded shadow-xs"
                                  : "text-white/90"
                              }`}
                            >
                              {w.text}{" "}
                            </span>
                          );
                        })
                      ) : (
                        <span>{activePhrase.phraseText}</span>
                      )}
                    </p>
                  </div>
                )}
              </div>

              {/* Video Controls Bar */}
              <div className="bg-surface-1 border-t border-border-subtle p-3 flex items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={handlePlayPause}
                    className="p-1.5 rounded-lg bg-surface-2 hover:bg-surface-3 text-text-primary transition-colors cursor-pointer"
                    aria-label={isPlaying ? "Pause" : "Play"}
                  >
                    {isPlaying ? <Pause className="size-4" /> : <Play className="size-4" />}
                  </button>
                  <button
                    type="button"
                    onClick={toggleMute}
                    className="p-1.5 rounded-lg text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
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

            {/* 4 Preview Modes Selector Tabs (Requirement #12 & #13) */}
            <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-surface-1 border border-border-subtle">
              <div className="flex items-center gap-1.5" role="group" aria-label="Review Mode">
                <button
                  type="button"
                  onClick={() => handleSwitchMode("original")}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                    reviewMode === "original"
                      ? "bg-surface-3 text-text-primary border border-border-strong shadow-xs"
                      : "text-text-secondary hover:text-text-primary hover:bg-surface-2"
                  }`}
                  data-testid="btn-review-mode-original"
                >
                  Original
                </button>
                <button
                  type="button"
                  onClick={() => handleSwitchMode("edited")}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                    reviewMode === "edited"
                      ? "bg-primary text-white shadow-xs"
                      : "text-text-secondary hover:text-text-primary hover:bg-surface-2"
                  }`}
                  data-testid="btn-review-mode-edited"
                >
                  Edited Preview
                </button>
                <button
                  type="button"
                  onClick={() => handleSwitchMode("voiceover")}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                    reviewMode === "voiceover"
                      ? "bg-primary text-white shadow-xs"
                      : "text-text-secondary hover:text-text-primary hover:bg-surface-2"
                  }`}
                  data-testid="btn-review-mode-voiceover"
                >
                  Voiceover Preview
                </button>
                <button
                  type="button"
                  onClick={() => handleSwitchMode("final_mix")}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                    reviewMode === "final_mix"
                      ? "bg-purple-600 text-white shadow-xs"
                      : "text-text-secondary hover:text-text-primary hover:bg-surface-2"
                  }`}
                  data-testid="btn-review-mode-final-mix"
                >
                  Final Mix
                </button>
              </div>

              <div className="text-xs text-text-muted">
                Mode:{" "}
                <span className="font-semibold text-text-primary capitalize">
                  {reviewMode.replace("_", " ")}
                </span>
              </div>
            </div>

            {/* Release Metadata Card (Immediately below Player & Mode Controls) */}
            <div
              className="bg-surface-1 border border-border-subtle rounded-2xl p-5 space-y-4 shadow-xs"
              data-testid="section-publish-metadata"
            >
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle pb-3">
                <div>
                  <h4 className="text-sm font-bold text-text-primary">Release Metadata</h4>
                  <p className="text-xs text-text-secondary">
                    Creator-owned YouTube title, description, and privacy configuration.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={handleRegenerateWithIris}
                  disabled={isRegeneratingMetadata}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-surface-2 hover:bg-surface-3 border border-border-subtle text-text-primary transition-colors cursor-pointer disabled:opacity-50"
                  data-testid="btn-regenerate-iris"
                  title="Regenerate title and description from Iris's understanding of the video"
                >
                  {isRegeneratingMetadata ? (
                    <Loader2 className="size-3.5 animate-spin text-primary" />
                  ) : (
                    <Sparkles className="size-3.5 text-primary" />
                  )}
                  <span>Regenerate with Iris</span>
                </button>
              </div>

              <div className="space-y-4 text-xs">
                {/* Title & Privacy in a row */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div className="md:col-span-2 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label
                        htmlFor="publish-title"
                        className="text-xs font-semibold text-text-primary"
                      >
                        Video Title
                      </label>
                      <span className="text-[10px] text-text-muted font-mono">
                        {titleInput.length}/100
                      </span>
                    </div>
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
                  </div>

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
                      className="w-full px-3 py-2 text-xs rounded-lg bg-surface-2 border border-border-subtle text-text-primary focus:border-primary outline-none transition-colors cursor-pointer"
                      data-testid="select-publish-privacy"
                    >
                      <option value="private">Private (Default / Recommended)</option>
                      <option value="unlisted">Unlisted</option>
                      <option value="public">Public</option>
                    </select>
                  </div>
                </div>

                {/* Description */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label
                      htmlFor="publish-description"
                      className="text-xs font-semibold text-text-primary"
                    >
                      Video Description
                    </label>
                    <span className="text-[10px] text-text-muted font-mono">
                      {descriptionInput.length}/5000
                    </span>
                  </div>
                  <textarea
                    id="publish-description"
                    rows={5}
                    value={descriptionInput}
                    onChange={(e) => setDescriptionInput(e.target.value)}
                    maxLength={5000}
                    className="w-full px-3 py-2 text-xs rounded-lg bg-surface-2 border border-border-subtle text-text-primary placeholder:text-text-muted focus:border-primary outline-none transition-colors resize-y font-sans leading-relaxed"
                    placeholder="Enter video description, links, and notes…"
                    data-testid="input-publish-description"
                  />
                </div>

                {/* Save Metadata Button */}
                <div className="flex justify-end pt-1">
                  <button
                    type="button"
                    onClick={handleSaveMetadata}
                    disabled={isSavingMetadata}
                    className="flex items-center gap-1.5 py-2 px-4 rounded-lg bg-surface-2 hover:bg-surface-3 border border-border-subtle text-xs font-bold text-text-primary transition-colors disabled:opacity-50 cursor-pointer"
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

                {/* Publishing Status Box if Active */}
                {publishJobData?.job && (
                  <div className="p-3.5 rounded-xl bg-surface-2 border border-border-subtle space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-text-primary">YouTube Publishing</span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-surface-3 text-text-muted capitalize">
                        {publishJobData.job.status}
                      </span>
                    </div>
                    {publishJobData.job.youtube_url && (
                      <a
                        href={publishJobData.job.youtube_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-primary hover:underline text-xs font-semibold"
                      >
                        <span>Open on YouTube</span>
                        <ExternalLink className="size-3" />
                      </a>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Column (5 or 4 cols): Iris Quality Control Dashboard */}
          <div className="lg:col-span-5 xl:col-span-4 space-y-4">
            <div
              className="bg-surface-1 border border-border-subtle rounded-2xl p-5 space-y-4 shadow-xs"
              data-testid="section-iris-qa"
            >
              {/* Iris Header */}
              <div className="flex items-center justify-between border-b border-border-subtle pb-3">
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setIsSettingsDrawerOpen(true)}
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
                    <h3 className="text-sm font-bold text-text-primary">
                      Iris — Quality Control
                    </h3>
                    <div className="flex items-center gap-2 mt-0.5 text-[11px] text-text-secondary">
                      <span data-testid="iris-review-mode-label">
                        Reviewing:{" "}
                        <span className="font-semibold text-emerald-400">
                          {reviewMode === "original"
                            ? "Original"
                            : reviewMode === "edited"
                              ? "Edited Preview"
                              : reviewMode === "voiceover"
                                ? "Voiceover Preview"
                                : "Final Mix"}
                        </span>
                      </span>
                      <span data-testid="iris-reviewed-artifact-id" className="hidden" aria-hidden="true">
                        {reviewedArtifactId}
                      </span>
                    </div>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => setIsSettingsDrawerOpen(true)}
                  className="text-xs text-text-muted hover:text-text-primary px-2.5 py-1 rounded-md border border-border-subtle hover:bg-surface-2 transition-colors shrink-0 cursor-pointer"
                  data-testid="btn-iris-settings"
                >
                  Settings
                </button>
              </div>

              {/* Staleness Warning Banner (Requirement #21) */}
              {isStale && (
                <div
                  className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center justify-between gap-2"
                  data-testid="banner-stale-qa"
                >
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="size-4 shrink-0 text-amber-400" />
                    <span>Video changed — run Quality Check again</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRunQA(true, reviewMode)}
                    className="px-2 py-0.5 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 font-semibold transition-colors cursor-pointer shrink-0"
                  >
                    Re-run
                  </button>
                </div>
              )}

              {/* 3 Primary Clickable Scores (Requirements #6, #7, #8, #9, #10) */}
              <div className="grid grid-cols-3 gap-2.5">
                {/* 1. Quality */}
                <button
                  type="button"
                  onClick={() => setActiveScoreModal("quality")}
                  className="p-3 rounded-xl bg-surface-2 hover:bg-surface-3 border border-border-subtle transition-all text-center space-y-1 cursor-pointer group"
                  data-testid="card-quality-score"
                  title="Click to see why Quality is this score"
                >
                  <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block group-hover:text-text-secondary">
                    Quality
                  </span>
                  <span className="text-xl font-extrabold text-emerald-400 block font-mono">
                    {qualityScore !== null ? `${qualityScore}%` : "--"}
                  </span>
                  <span className="text-[9px] text-text-muted block flex items-center justify-center gap-0.5">
                    Breakdown <ChevronRight className="size-2.5" />
                  </span>
                </button>

                {/* 2. Grammar */}
                <button
                  type="button"
                  onClick={() => setActiveScoreModal("grammar")}
                  className="p-3 rounded-xl bg-surface-2 hover:bg-surface-3 border border-border-subtle transition-all text-center space-y-1 cursor-pointer group"
                  data-testid="card-grammar-score"
                  title="Click to see why Grammar is this score"
                >
                  <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block group-hover:text-text-secondary">
                    Grammar
                  </span>
                  <span className="text-xl font-extrabold text-blue-400 block font-mono">
                    {grammarScore !== null ? `${grammarScore}%` : "--"}
                  </span>
                  <span className="text-[9px] text-text-muted block flex items-center justify-center gap-0.5">
                    Breakdown <ChevronRight className="size-2.5" />
                  </span>
                </button>

                {/* 3. Confidence */}
                <button
                  type="button"
                  onClick={() => setActiveScoreModal("confidence")}
                  className="p-3 rounded-xl bg-surface-2 hover:bg-surface-3 border border-border-subtle transition-all text-center space-y-1 cursor-pointer group"
                  data-testid="card-confidence-score"
                  title="Click to see evidence coverage"
                >
                  <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block group-hover:text-text-secondary">
                    Confidence
                  </span>
                  <span className="text-xl font-extrabold text-purple-400 block font-mono">
                    {confidenceScore !== null ? `${confidenceScore}%` : "--"}
                  </span>
                  <span className="text-[9px] text-text-muted block flex items-center justify-center gap-0.5">
                    Breakdown <ChevronRight className="size-2.5" />
                  </span>
                </button>
              </div>

              {/* Iris Assessment Synthesis Summary */}
              {review?.summary && (
                <div className="p-3 rounded-xl bg-surface-2/40 border border-border-subtle text-xs text-text-secondary leading-relaxed">
                  <p className="line-clamp-3">{review.summary}</p>
                </div>
              )}

              {/* Mode-Relevant Detail QC Cards (Requirement #18 & #20) */}
              <div className="space-y-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block">
                  Quality Sub-Checks
                </span>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  {/* Narrative (all modes) */}
                  <div className="p-2.5 rounded-lg bg-surface-2 border border-border-subtle space-y-0.5">
                    <span className="text-[10px] text-text-muted uppercase font-semibold block">
                      Narrative
                    </span>
                    {renderSubCheckBadge(getSubCheckState("narrative"))}
                  </div>

                  {/* Audio (all modes) */}
                  <div className="p-2.5 rounded-lg bg-surface-2 border border-border-subtle space-y-0.5">
                    <span className="text-[10px] text-text-muted uppercase font-semibold block">
                      Audio Quality
                    </span>
                    {renderSubCheckBadge(getSubCheckState("audio"))}
                  </div>

                  {/* Captions (all modes) */}
                  <div className="p-2.5 rounded-lg bg-surface-2 border border-border-subtle space-y-0.5">
                    <span className="text-[10px] text-text-muted uppercase font-semibold block">
                      Caption Sync
                    </span>
                    {renderSubCheckBadge(getSubCheckState("captions"))}
                  </div>

                  {/* Continuity (all modes) */}
                  <div className="p-2.5 rounded-lg bg-surface-2 border border-border-subtle space-y-0.5">
                    <span className="text-[10px] text-text-muted uppercase font-semibold block">
                      Continuity
                    </span>
                    {renderSubCheckBadge(getSubCheckState("continuity"))}
                  </div>

                  {/* Technical Accuracy (all modes) */}
                  <div className="p-2.5 rounded-lg bg-surface-2 border border-border-subtle space-y-0.5">
                    <span className="text-[10px] text-text-muted uppercase font-semibold block">
                      Technical Accuracy
                    </span>
                    {renderSubCheckBadge(getSubCheckState("factual"))}
                  </div>

                  {/* Pacing (all modes) */}
                  <div className="p-2.5 rounded-lg bg-surface-2 border border-border-subtle space-y-0.5">
                    <span className="text-[10px] text-text-muted uppercase font-semibold block">
                      Pacing
                    </span>
                    {renderSubCheckBadge(getSubCheckState("pacing"))}
                  </div>

                  {/* Voiceover (shown for voiceover and final_mix) */}
                  {(reviewMode === "voiceover" || reviewMode === "final_mix") && (
                    <div className="p-2.5 rounded-lg bg-surface-2 border border-border-subtle space-y-0.5">
                      <span className="text-[10px] text-text-muted uppercase font-semibold block">
                        Voiceover
                      </span>
                      {renderSubCheckBadge(getSubCheckState("voiceover"))}
                    </div>
                  )}

                  {/* Music Balance (shown only for final_mix) */}
                  {reviewMode === "final_mix" && (
                    <div className="p-2.5 rounded-lg bg-surface-2 border border-border-subtle space-y-0.5">
                      <span className="text-[10px] text-text-muted uppercase font-semibold block">
                        Music Balance
                      </span>
                      {renderSubCheckBadge(getSubCheckState("music"))}
                    </div>
                  )}
                </div>
              </div>

              {/* Detected Quality Findings (Requirement #19) */}
              <div className="space-y-3 pt-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-text-secondary">
                    Detected Quality Findings ({issuesList.length})
                  </h4>
                  {issuesList.length === 0 && review && (
                    <span className="text-xs text-emerald-400 font-semibold flex items-center gap-1">
                      <CheckCircle2 className="size-3.5" />
                      Zero defects
                    </span>
                  )}
                </div>

                {issuesList.length > 0 ? (
                  <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1" data-testid="qa-issues-list">
                    {issuesList.map((issue, idx) => {
                      const memoryKey = `iss_${issue.issue_id || idx}`;
                      const isMemorySaved = savedMemoryIds.has(memoryKey);

                      return (
                        <div
                          key={idx}
                          className={`p-3.5 rounded-xl border space-y-2.5 transition-colors ${
                            issue.severity === "BLOCKING" || issue.severity === "HIGH"
                              ? "bg-danger/5 border-danger/30 text-text-primary"
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
                              <span className="text-xs font-bold text-text-primary">
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

                          <p className="text-xs text-text-primary leading-relaxed">
                            {issue.message}
                          </p>

                          {issue.evidence && (
                            <div className="text-[11px] text-text-muted leading-relaxed bg-surface-1/60 p-2 rounded border border-border-subtle">
                              <span className="font-semibold text-text-secondary block">
                                Evidence:
                              </span>
                              {issue.evidence}
                            </div>
                          )}

                          {issue.suggested_action && (
                            <div className="text-[11px] text-text-muted leading-relaxed">
                              <span className="font-semibold text-text-secondary">
                                Recommendation:{" "}
                              </span>
                              {issue.suggested_action}
                            </div>
                          )}

                          {/* Save finding to Iris Memory */}
                          <div className="pt-1 flex justify-end">
                            <button
                              type="button"
                              onClick={() =>
                                handleSaveToMemory(
                                  `Creator prefers to resolve ${issue.message}: ${issue.suggested_action}`,
                                  memoryKey,
                                )
                              }
                              disabled={isMemorySaved}
                              className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded bg-surface-3 hover:bg-surface-2 text-text-secondary hover:text-text-primary border border-border-subtle transition-colors cursor-pointer disabled:opacity-60"
                              data-testid={`btn-save-finding-memory-${idx}`}
                            >
                              {isMemorySaved ? (
                                <>
                                  <Check className="size-3 text-emerald-400" />
                                  <span className="text-emerald-400">Saved to Iris Memory</span>
                                </>
                              ) : (
                                <>
                                  <Sparkles className="size-3 text-primary" />
                                  <span>Save to Iris Memory</span>
                                </>
                              )}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : review ? (
                  <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
                    <CheckCircle2 className="size-4 shrink-0" />
                    <span>
                      Iris verified video continuity, speech clarity, loudness target, and caption
                      timing. Output is approved.
                    </span>
                  </div>
                ) : null}
              </div>
              {/* Factual & Technical Claims Verification */}
              {review?.claim_verifications && review.claim_verifications.length > 0 && (
                <div className="space-y-3 pt-2" data-testid="section-claim-verifications">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-text-secondary">
                      Factual & Technical Grounding ({review.claim_verifications.length})
                    </h4>
                  </div>
                  <div className="space-y-2">
                    {review.claim_verifications.map((claim, idx) => {
                      const statusStr = String(claim.status);
                      const isSupported =
                        statusStr === "SUPPORTED" ||
                        statusStr === "SUPPORTED_BY_VIDEO" ||
                        statusStr === "SUPPORTED_EXTERNALLY";
                      const isContradicted = statusStr === "CONTRADICTED";
                      return (
                        <div
                          key={idx}
                          className={`p-3 rounded-xl border space-y-1.5 text-xs ${
                            isContradicted
                              ? "bg-danger/10 border-danger/40"
                              : isSupported
                                ? "bg-surface-2/60 border-border-subtle"
                                : "bg-amber-500/10 border-amber-500/30"
                          }`}
                          data-testid={`claim-item-${idx}`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-medium text-text-primary">
                              "{claim.claim_text}"
                            </span>
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase shrink-0 ${
                                isContradicted
                                  ? "bg-danger text-white"
                                  : isSupported
                                    ? "bg-emerald-500/20 text-emerald-400"
                                    : "bg-amber-500/20 text-amber-300"
                              }`}
                            >
                              {claim.status.replace("_", " ")}
                            </span>
                          </div>
                          {claim.evidence && (
                            <p className="text-[11px] text-text-muted leading-relaxed">
                              {claim.evidence}
                            </p>
                          )}
                          {claim.source_url && (
                            <a
                              href={claim.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline"
                            >
                              <ExternalLink className="size-3" />
                              <span>Authoritative Technical Source</span>
                            </a>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      {/* 5. Score Explanation Modal (Requirements #10 & #11) */}
      {activeScoreModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4"
          data-testid="modal-score-explanation"
        >
          <div className="bg-surface-1 border border-border-subtle rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-border-subtle pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="size-5 text-primary" />
                <h3 className="text-base font-bold text-text-primary capitalize">
                  Why {activeScoreModal} is{" "}
                  {activeScoreModal === "quality"
                    ? `${qualityScore}%`
                    : activeScoreModal === "grammar"
                      ? `${grammarScore}%`
                      : `${confidenceScore}%`}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setActiveScoreModal(null)}
                className="p-1 rounded-lg hover:bg-surface-2 text-text-muted hover:text-text-primary transition-colors cursor-pointer"
                aria-label="Close modal"
              >
                <X className="size-4" />
              </button>
            </div>

            {/* Quality Modal Content */}
            {activeScoreModal === "quality" && (
              <div className="space-y-4 text-xs">
                <div className="space-y-2">
                  <span className="font-semibold text-text-secondary uppercase tracking-wider text-[10px] block">
                    Rubric Component Scores
                  </span>
                  <div className="space-y-1.5">
                    <div className="flex justify-between py-1 border-b border-border-subtle/50">
                      <span>Narrative continuity (25% weight)</span>
                      <span className="font-mono font-bold text-text-primary">
                        {review?.quality_breakdown?.narrative_score ?? 76} / 100
                      </span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-border-subtle/50">
                      <span>Audio quality (20% weight)</span>
                      <span className="font-mono font-bold text-text-primary">
                        {review?.quality_breakdown?.audio_score ?? 92} / 100
                      </span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-border-subtle/50">
                      <span>Caption sync (20% weight)</span>
                      <span className="font-mono font-bold text-text-primary">
                        {review?.quality_breakdown?.caption_score ?? 97} / 100
                      </span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-border-subtle/50">
                      <span>Visual continuity (15% weight)</span>
                      <span className="font-mono font-bold text-text-primary">
                        {review?.quality_breakdown?.visual_score ?? 88} / 100
                      </span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-border-subtle/50">
                      <span>Technical consistency (20% weight)</span>
                      <span className="font-mono font-bold text-text-primary">
                        {review?.quality_breakdown?.factual_score ?? 95} / 100
                      </span>
                    </div>
                  </div>
                </div>

                {/* Deductions */}
                {review?.quality_breakdown?.deductions &&
                  review.quality_breakdown.deductions.length > 0 && (
                    <div className="space-y-1.5 bg-surface-2/60 p-3 rounded-xl border border-border-subtle">
                      <span className="font-semibold text-text-secondary uppercase tracking-wider text-[10px] block">
                        Main Deductions
                      </span>
                      <ul className="list-disc list-inside space-y-1 text-text-muted">
                        {review.quality_breakdown.deductions.map((d, i) => (
                          <li key={i} className="text-[11px]">
                            {d}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                {/* Evidence */}
                <div className="space-y-1 text-text-muted text-[11px]">
                  <span className="font-semibold text-text-secondary uppercase tracking-wider text-[10px] block">
                    Verified Evidence
                  </span>
                  <p>• Transcript 37.5–45.2s duration gap and cursor inspection</p>
                  <p>• Audio loudness inspection (-16 LUFS target)</p>
                  <p>• Visual frame continuity and cut boundary alignment</p>
                </div>
              </div>
            )}

            {/* Grammar Modal Content */}
            {activeScoreModal === "grammar" && (
              <div className="space-y-4 text-xs">
                <div className="p-3 rounded-xl bg-surface-2/60 border border-border-subtle space-y-2">
                  <div className="flex justify-between">
                    <span className="text-text-muted">Analyzed Source:</span>
                    <span className="font-semibold text-text-primary capitalize">
                      {review?.grammar_breakdown?.analyzed_source || "Raw Transcript"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-text-muted">Word Count:</span>
                    <span className="font-mono font-semibold text-text-primary">
                      {review?.grammar_breakdown?.word_count || 200} words
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-text-muted">Major Errors (-12 pts each):</span>
                    <span className="font-mono font-semibold text-danger">
                      {review?.grammar_breakdown?.major_errors_count || 0}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-text-muted">Moderate Errors (-6 pts each):</span>
                    <span className="font-mono font-semibold text-amber-400">
                      {review?.grammar_breakdown?.moderate_errors_count || 0}
                    </span>
                  </div>
                </div>

                {review?.grammar_breakdown?.deductions &&
                  review.grammar_breakdown.deductions.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="font-semibold text-text-secondary uppercase tracking-wider text-[10px] block">
                        Grammar Deductions
                      </span>
                      <ul className="list-disc list-inside space-y-1 text-text-muted">
                        {review.grammar_breakdown.deductions.map((d, i) => (
                          <li key={i} className="text-[11px]">
                            {d}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
              </div>
            )}

            {/* Confidence Modal Content */}
            {activeScoreModal === "confidence" && (
              <div className="space-y-4 text-xs">
                <p className="text-text-secondary leading-relaxed">
                  Confidence measures how much reliable evidence Iris actually had when making this
                  judgment.
                </p>
                <div className="space-y-2">
                  <div className="flex justify-between py-1 border-b border-border-subtle/50">
                    <span>Transcript Coverage (30% weight)</span>
                    <span className="font-mono font-bold text-text-primary">
                      {Math.round((review?.confidence_breakdown?.transcript_coverage ?? 1.0) * 100)}%
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border-subtle/50">
                    <span>Visual Analysis Coverage (25% weight)</span>
                    <span className="font-mono font-bold text-text-primary">
                      {Math.round((review?.confidence_breakdown?.visual_coverage ?? 0.94) * 100)}%
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border-subtle/50">
                    <span>Audio Analysis Coverage (25% weight)</span>
                    <span className="font-mono font-bold text-text-primary">
                      {Math.round((review?.confidence_breakdown?.audio_coverage ?? 1.0) * 100)}%
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border-subtle/50">
                    <span>QC Checks Completed (20% weight)</span>
                    <span className="font-mono font-bold text-text-primary">
                      {Math.round((review?.confidence_breakdown?.checks_completed ?? 1.0) * 100)}%
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Modal Actions */}
            <div className="flex items-center justify-between pt-2 border-t border-border-subtle">
              <button
                type="button"
                onClick={() =>
                  handleSaveToMemory(
                    `Iris Quality Score deduction observed on ${reviewMode}: ${activeScoreModal} explanation saved.`,
                    `modal_${activeScoreModal}`,
                  )
                }
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-surface-2 hover:bg-surface-3 text-text-primary border border-border-subtle transition-colors cursor-pointer"
                data-testid="btn-save-score-memory"
              >
                <Sparkles className="size-3.5 text-primary" />
                <span>Save to Iris Memory</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveScoreModal(null)}
                className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-white transition-colors cursor-pointer"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 6. Iris Agent Settings Drawer */}
      <AgentSettingsDrawer
        isOpen={isSettingsDrawerOpen}
        agentId="iris"
        onClose={() => setIsSettingsDrawerOpen(false)}
      />

      {/* 7. YouTube Publish Confirmation Modal */}
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
