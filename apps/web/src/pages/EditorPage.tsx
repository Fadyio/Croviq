import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  AlertCircle,
  LogOut,
  Loader2,
  CheckCircle2,
  Sparkles,
  MessageSquare,
  FileText,
  Sliders,
  Play,
  RotateCcw,
} from "lucide-react";
import { CroviqLogo } from "../components/CroviqLogo";
import { useAuth } from "../auth/AuthContext";
import { PreviewToggle, type PreviewMode } from "../components/editor/PreviewToggle";
import { VideoStage } from "../components/editor/VideoStage";
import { EditorTimeline } from "../components/editor/EditorTimeline";
import { TranscriptPanel } from "../components/editor/TranscriptPanel";
import { AgentPresence } from "../components/editor/AgentPresence";
import { AgentActivityFeed } from "../components/editor/AgentActivityFeed";
import { DecisionInspector } from "../components/editor/DecisionInspector";
import { MediaBin, type BRollAssetItem } from "../components/editor/MediaBin";
import { AgentSettingsDrawer } from "../components/editor/AgentSettingsDrawer";
import {
  edlToTwickTimeline,
  deriveKeepSegments,
  type EditDecisionList,
  type EditorProposal,
  type DirectorReview,
  type EditorDecision,
  type DirectorDecision,
  type AgentActivity,
  type Transcript,
  type TimelineBlock,
  type CoverageMarker,
  formatDuration,
} from "../lib/edl-adapter";
import type { components } from "../api/generated";
import {
  deriveProductionRunStages,
  nextMissingProcessingStage,
  type PersistedProductionRun,
  type ProcessingStage,
} from "../lib/production-run";

const waitForRunUpdate = async (): Promise<void> => {
  const { promise, resolve } = Promise.withResolvers<void>();
  window.setTimeout(resolve, 1000);
  await promise;
};

type Production = components["schemas"]["Production"];
type EditorialRunDetail = components["schemas"]["EditorialRunDetailResponse"];
type BRollArtifact = components["schemas"]["BRollArtifact"];

interface LoadedEditorData {
  productionRun: PersistedProductionRun;
  runDetail: EditorialRunDetail | null;
}

const readOptionalJson = async <T,>(response: Response, label: string): Promise<T | null> => {
  if (!response.ok) return null;
  return response.json() as Promise<T>;
};

interface EditorPageProps {
  productionId: string;
  onNavigateHome?: () => void;
}

export const EditorPage: React.FC<EditorPageProps> = ({ productionId, onNavigateHome }) => {
  const { user, firebaseUser, logout } = useAuth();

  const [production, setProduction] = useState<Production | null>(null);
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [renderedPreviewUrl, setRenderedPreviewUrl] = useState<string | null>(null);
  const [studioVoicePreviewUrl, setStudioVoicePreviewUrl] = useState<string | null>(null);
  const [masterUrl, setMasterUrl] = useState<string | null>(null);

  const [previewArtifact, setPreviewArtifact] = useState<
    components["schemas"]["RenderArtifactResponse"] | null
  >(null);
  const [masterArtifact, setMasterArtifact] = useState<
    components["schemas"]["RenderArtifactResponse"] | null
  >(null);
  const [shortArtifact, setShortArtifact] = useState<
    components["schemas"]["RenderArtifactResponse"] | null
  >(null);
  const [studioVoiceArtifact, setStudioVoiceArtifact] = useState<
    components["schemas"]["RenderArtifactResponse"] | null
  >(null);
  const [renderReview, setRenderReview] = useState<components["schemas"]["RenderReview"] | null>(
    null,
  );
  const [renderSubStatus, setRenderSubStatus] = useState<string | null>(null);
  const [isManualReviewRequired, setIsManualReviewRequired] = useState<boolean>(false);

  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [proposal, setProposal] = useState<EditorProposal | null>(null);
  const [review, setReview] = useState<DirectorReview | null>(null);
  const [activities, setActivities] = useState<AgentActivity[]>([]);
  const [brollArtifacts, setBrollArtifacts] = useState<BRollArtifact[]>([]);
  const [editorialRun, setEditorialRun] = useState<EditorialRunDetail["run"] | null>(null);
  const [edl, setEdl] = useState<EditDecisionList | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeProcessingStage, setActiveProcessingStage] = useState<ProcessingStage | null>(null);
  const [failedProcessingStage, setFailedProcessingStage] = useState<ProcessingStage | null>(null);

  const [currentTimeMs, setCurrentTimeMs] = useState(0);
  const [durationMs, setDurationMs] = useState(113824);
  const [isPlaying, setIsPlaying] = useState(false);
  const [previewMode, setPreviewMode] = useState<PreviewMode>("edited");
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(null);
  const [selectedBlock, setSelectedBlock] = useState<TimelineBlock | null>(null);

  // Production Room inspector tab: "agents" | "transcript" | "decision"
  const [rightPanelTab, setRightPanelTab] = useState<"agents" | "transcript" | "decision">(
    "agents",
  );

  // Agent settings drawer state
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settingsAgentId, setSettingsAgentId] = useState<"leo" | "maya">("leo");

  const runPromiseRef = useRef<Promise<void> | null>(null);
  const processingProductionIdRef = useRef<string | null>(null);
  const activeProcessingStageRef = useRef<ProcessingStage | null>(null);

  const loadPersistedData = useCallback(async (): Promise<LoadedEditorData> => {
    if (!firebaseUser) throw new Error("Authentication required");
    const token = await firebaseUser.getIdToken();
    const headers = { Authorization: `Bearer ${token}` };

    const [
      productionResponse,
      playbackResponse,
      transcriptResponse,
      runResponse,
      edlResponse,
      rendersResponse,
      reviewResponse,
      brollResponse,
    ] = await Promise.all([
      fetch(`/api/productions/${productionId}`, { headers }),
      fetch(`/api/productions/${productionId}/playback`, { headers }).catch(() => null),
      fetch(`/api/productions/${productionId}/transcript`, { headers }),
      fetch(`/api/productions/${productionId}/editorial-run`, { headers }),
      fetch(`/api/productions/${productionId}/edl`, { headers }),
      fetch(`/api/productions/${productionId}/renders`, { headers }).catch(() => null),
      fetch(`/api/productions/${productionId}/render-reviews`, { headers }).catch(() => null),
      fetch(`/api/productions/${productionId}/broll`, { headers }).catch(() => null),
    ]);

    if (!productionResponse.ok) {
      throw new Error(`Production '${productionId}' could not be loaded`);
    }

    const [
      productionPayload,
      playbackPayload,
      transcriptPayload,
      runPayload,
      edlPayload,
      rendersPayload,
      reviewPayload,
      brollPayload,
    ] = await Promise.all([
      productionResponse.json() as Promise<Production>,
      playbackResponse
        ? readOptionalJson<components["schemas"]["ProductionPlaybackResponse"]>(
            playbackResponse,
            "Playback",
          )
        : Promise.resolve(null),
      readOptionalJson<Transcript>(transcriptResponse, "Transcript"),
      readOptionalJson<EditorialRunDetail>(runResponse, "Editorial run"),
      readOptionalJson<EditDecisionList>(edlResponse, "EDL"),
      rendersResponse
        ? readOptionalJson<components["schemas"]["RenderListResponse"]>(rendersResponse, "Renders")
        : Promise.resolve(null),
      reviewResponse
        ? readOptionalJson<components["schemas"]["RenderReviewDetailResponse"]>(
            reviewResponse,
            "Render review",
          )
        : Promise.resolve(null),
      brollResponse
        ? readOptionalJson<components["schemas"]["BRollListResponse"]>(brollResponse, "BRoll")
        : Promise.resolve(null),
    ]);

    const preview =
      rendersPayload?.renders?.find(
        (render: components["schemas"]["RenderArtifactResponse"]) =>
          render.artifact_type === "PREVIEW",
      ) ?? null;
    const master =
      rendersPayload?.renders?.find(
        (render: components["schemas"]["RenderArtifactResponse"]) =>
          render.artifact_type === "MASTER",
      ) ?? null;
    const short =
      rendersPayload?.renders?.find(
        (render: components["schemas"]["RenderArtifactResponse"]) =>
          render.artifact_type === "SHORT",
      ) ?? null;
    const svPreview =
      rendersPayload?.renders?.find(
        (render: components["schemas"]["RenderArtifactResponse"]) =>
          render.artifact_type === "STUDIO_VOICE_PREVIEW",
      ) ?? null;
    setProduction(productionPayload);
    setPlaybackUrl(playbackPayload?.playback_url ?? null);
    setRenderedPreviewUrl(preview?.playback_url ?? playbackPayload?.rendered_preview_url ?? null);
    setStudioVoicePreviewUrl(
      svPreview?.playback_url ?? playbackPayload?.studio_voice_preview_url ?? null,
    );
    setMasterUrl(master?.playback_url ?? playbackPayload?.master_url ?? null);

    setPreviewArtifact(preview);
    setMasterArtifact(master);
    setShortArtifact(short);
    setStudioVoiceArtifact(svPreview);

    if (brollPayload?.artifacts) {
      setBrollArtifacts(brollPayload.artifacts);
    }

    if (reviewPayload) {
      setRenderReview(reviewPayload.review ?? null);
      setIsManualReviewRequired(Boolean(reviewPayload.needs_manual_review));
    }
    const actualEdl: EditDecisionList | null = (edlPayload as any)?.edl
      ? (edlPayload as any).edl
      : edlPayload;
    setTranscript(transcriptPayload);
    setEdl(actualEdl);

    const initialDur = actualEdl?.source_duration_ms || transcriptPayload?.duration_ms || 113824;
    if (initialDur > 0) {
      setDurationMs(initialDur);
    }

    if (runPayload) {
      setProposal(runPayload.proposal as EditorProposal | null);
      setReview(runPayload.review as DirectorReview | null);
      setActivities(runPayload.activities as AgentActivity[]);
      setEditorialRun(runPayload.run ?? null);
    }

    return {
      productionRun: {
        uploaded: productionPayload.source_media?.status === "uploaded",
        uploadedAt: productionPayload.source_media?.uploaded_at,
        transcriptCreatedAt: transcriptPayload?.created_at,
        editorialRun: runPayload?.run ?? null,
        proposal: (runPayload?.proposal as EditorProposal) || null,
        activities: (runPayload?.activities as AgentActivity[]) || [],
        edlCreatedAt: actualEdl?.created_at,
        renderCompletedAt: preview?.completed_at,
        renderStatus: preview?.status,
        renderDurationMs: preview?.duration_ms,
        renderReview: reviewPayload?.review ?? null,
        masterArtifact: master,
        masterStatus: master?.status,
        shortStatus: short?.status,
        shortCompletedAt: short?.completed_at,
        needsManualReview: Boolean(reviewPayload?.needs_manual_review),
      },
      runDetail: runPayload,
    };
  }, [firebaseUser, productionId]);

  const beginProductionRun = useCallback(
    async (initialRun?: PersistedProductionRun, forceRetry = false) => {
      if (!firebaseUser) return;
      if (runPromiseRef.current && !forceRetry) return;

      const runExecution = (async () => {
        try {
          setErrorMessage(null);
          setFailedProcessingStage(null);

          let productionRun = initialRun || (await loadPersistedData()).productionRun;
          let missingStage = nextMissingProcessingStage(productionRun);
          if (
            missingStage === null &&
            forceRetry &&
            productionRun.editorialRun?.status === "failed"
          ) {
            missingStage = "leo-edit";
          }
          while (missingStage !== null) {
            if (
              productionRun.editorialRun &&
              (productionRun.editorialRun.status === "analyzing" ||
                productionRun.editorialRun.status === "reviewing")
            ) {
              setActiveProcessingStage(
                productionRun.editorialRun.status === "reviewing" ? "maya-review" : "leo-edit",
              );
              await waitForRunUpdate();
              const refreshed = await loadPersistedData();
              productionRun = refreshed.productionRun;
              missingStage = nextMissingProcessingStage(productionRun);
              continue;
            }

            setActiveProcessingStage(missingStage);
            activeProcessingStageRef.current = missingStage;

            const token = await firebaseUser.getIdToken();
            const headers = { Authorization: `Bearer ${token}` };

            if (missingStage === "transcript") {
              const resTranscribe = await fetch(`/api/productions/${productionId}/transcribe`, {
                method: "POST",
                headers,
              });
              if (!resTranscribe.ok) throw new Error("Transcription failed");
            } else if (
              missingStage === ("leo-edit" as ProcessingStage) ||
              missingStage === ("maya-review" as ProcessingStage)
            ) {
              setActiveProcessingStage("leo-edit");
              const analyzePromise = fetch(`/api/productions/${productionId}/analyze`, {
                method: "POST",
                headers,
              });
              const pollInterval = window.setInterval(async () => {
                try {
                  const curr = await loadPersistedData();
                  if (curr.productionRun.editorialRun?.status === "reviewing") {
                    setActiveProcessingStage("maya-review");
                  }
                } catch {
                  // Ignore poll error while in flight
                }
              }, 200);
              const resAnalyze = await analyzePromise;
              window.clearInterval(pollInterval);
              if (!resAnalyze.ok) throw new Error("Editorial analysis failed");
            } else if (missingStage === "edit-plan") {
              const resAssemble = await fetch(`/api/productions/${productionId}/edl`, {
                method: "POST",
                headers,
              });
              if (!resAssemble.ok) throw new Error("Edit Decision List assembly failed");
            } else if (missingStage === "render") {
              setRenderSubStatus("Rendering preview video…");
              const resRender = await fetch(`/api/productions/${productionId}/renders/preview`, {
                method: "POST",
                headers,
              });
              if (!resRender.ok) throw new Error("Preview rendering failed");

              setRenderSubStatus("Director reviewing preview…");
              const revRes = await fetch(`/api/productions/${productionId}/review-preview`, {
                method: "POST",
                headers,
              });
              if (!revRes.ok) throw new Error("Director post-render review failed");
            }
            const updated = await loadPersistedData();
            productionRun = updated.productionRun;
            missingStage = nextMissingProcessingStage(productionRun);
          }
        } catch (err: unknown) {
          const stage = activeProcessingStageRef.current || "render";
          setFailedProcessingStage(stage);
          setErrorMessage(err instanceof Error ? err.message : "Production run error");
          setActiveProcessingStage(null);
          activeProcessingStageRef.current = null;
          runPromiseRef.current = null;
        }
      })();

      runPromiseRef.current = runExecution;
      await runExecution;
    },
    [firebaseUser, loadPersistedData, productionId],
  );

  useEffect(() => {
    let isMounted = true;
    const init = async () => {
      try {
        const loaded = await loadPersistedData();
        if (isMounted) {
          setIsLoading(false);
          if (processingProductionIdRef.current !== productionId) {
            processingProductionIdRef.current = productionId;
            beginProductionRun(loaded.productionRun);
          }
        }
      } catch (err) {
        if (isMounted) {
          setErrorMessage(err instanceof Error ? err.message : "Unable to load production");
          setIsLoading(false);
        }
      }
    };
    init();
    return () => {
      isMounted = false;
    };
  }, [loadPersistedData, productionId, beginProductionRun]);

  // Handle seeking and synchronized block selections
  const handleSeek = useCallback((targetMs: number) => {
    setCurrentTimeMs(targetMs);
  }, []);

  const handlePlayPause = useCallback(() => {
    setIsPlaying((prev) => !prev);
  }, []);

  const handleSelectBlock = useCallback((block: TimelineBlock | null) => {
    setSelectedBlock(block);
    if (block) {
      setSelectedDecisionId(block.decisionId || (block as any).decision_id || null);
      setRightPanelTab("decision");
    }
  }, []);

  const handleSelectDecision = useCallback(
    (decision: EditorDecision | null) => {
      if (!decision) {
        setSelectedDecisionId(null);
        return;
      }
      setSelectedDecisionId(decision.decision_id);
      handleSeek(decision.source_start_ms);
      setRightPanelTab("decision");
    },
    [handleSeek],
  );
  const handleOpenSettings = useCallback((agent: "leo" | "maya") => {
    setSettingsAgentId(agent);
    setIsSettingsOpen(true);
  }, []);

  // Twick data representation for bottom timeline
  const twickData = useMemo(() => {
    if (!edl) {
      return {
        tracks: [],
        blocks: [],
        totalDurationMs: durationMs,
        activeCutCount: 0,
        coverageMarkerCount: 0,
        keepSegments: [[0, durationMs]] as Array<[number, number]>,
        audioRegions: [{ type: "speech" as const, startMs: 0, endMs: durationMs }],
        chapters: proposal?.chapters || [],
        shortCandidate: proposal?.short_candidate,
      };
    }
    return edlToTwickTimeline(edl, proposal, review, transcript);
  }, [edl, durationMs, proposal, review, transcript]);
  // Compute actual or estimated edited duration
  const derivedEditedDurationMs = useMemo(() => {
    if (
      previewArtifact?.duration_ms &&
      previewArtifact.duration_ms > 0 &&
      (!edl || previewArtifact.edl_id === edl.edl_id)
    ) {
      return previewArtifact.duration_ms;
    }
    if (edl) {
      const keeps = deriveKeepSegments(edl);
      const total = keeps.reduce((acc, [s, e]) => acc + (e - s), 0);
      if (total > 0) return total;
      const removed = (edl.cuts || []).reduce(
        (acc, c) =>
          c.safety_status !== "REJECTED_UNSAFE"
            ? acc + (c.removed_duration_ms || Math.max(0, c.safe_end_ms - c.safe_start_ms))
            : acc,
        0,
      );
      if (removed > 0) return Math.max(1000, edl.source_duration_ms - removed);
    }
    return durationMs;
  }, [previewArtifact, edl, durationMs]);
  const selectedDecision = useMemo(() => {
    if (!selectedDecisionId || !proposal || !proposal.decisions) return null;
    return (
      proposal.decisions.find((d: EditorDecision) => d.decision_id === selectedDecisionId) || null
    );
  }, [selectedDecisionId, proposal]);

  const selectedDirectorDecision = useMemo<DirectorDecision | null>(() => {
    if (!selectedDecisionId || !review || !review.decisions) return null;
    return (
      (review.decisions as any).find(
        (d: any) =>
          d.editor_decision_id === selectedDecisionId || d.decision_id === selectedDecisionId,
      ) || null
    );
  }, [selectedDecisionId, review]);

  const activeCoverage = useMemo<CoverageMarker | null>(() => {
    if (!edl?.coverage_markers) return null;
    return (
      edl.coverage_markers.find(
        (m: CoverageMarker) =>
          currentTimeMs >= m.source_start_ms && currentTimeMs <= m.source_end_ms,
      ) || null
    );
  }, [edl, currentTimeMs]);

  // Derive B-roll items for Media Bin
  const brollBinItems = useMemo<BRollAssetItem[]>(() => {
    return brollArtifacts.map((b: BRollArtifact) => ({
      artifactId: b.artifact_id,
      sourceStartMs: b.source_start_ms,
      sourceEndMs: b.source_end_ms,
      durationMs: b.duration_ms,
      promptSummary: b.prompt_summary || "",
    }));
  }, [brollArtifacts]);
  const processingFailureMessage: Record<ProcessingStage, string> = {
    transcript: "Transcription failed",
    "leo-edit": "Leo analysis failed",
    "maya-review": "Director review failed",
    "edit-plan": "Edit plan failed",
    render: "Preview render failed",
  };

  // Compact Single Status Message
  const compactStatus = useMemo(() => {
    if (activeProcessingStage) {
      if (activeProcessingStage === "transcript") return "Preparing transcript…";
      if (activeProcessingStage === "leo-edit") return "Leo is reviewing the footage…";
      if (activeProcessingStage === "maya-review") return "Maya is reviewing Leo's edit…";
      if (activeProcessingStage === "edit-plan") return "Preparing edit plan…";
      if (activeProcessingStage === "render") return renderSubStatus || "Rendering preview video…";
      return "Croviq is editing your video…";
    }
    if (editorialRun?.status === "analyzing") return "Leo is reviewing the footage…";
    if (editorialRun?.status === "reviewing") return "Maya is reviewing Leo's edit…";
    if (failedProcessingStage) return "Editing pass encountered an issue";
    if (previewArtifact?.status === "completed") {
      return "Production complete";
    }
    return "Ready";
  }, [
    activeProcessingStage,
    failedProcessingStage,
    editorialRun?.status,
    previewArtifact,
    durationMs,
    renderSubStatus,
  ]);

  const activeAgent = useMemo(() => {
    if (activeProcessingStage === "leo-edit") return "leo";
    if (activeProcessingStage === "maya-review") return "maya";
    if (editorialRun?.status === "analyzing") return "leo";
    if (editorialRun?.status === "reviewing") return "maya";
    return null;
  }, [activeProcessingStage, editorialRun?.status]);

  const activeStatusMessage = useMemo(() => {
    if (activeProcessingStage) return compactStatus;
    if (editorialRun?.status === "analyzing") return "Leo is reviewing the footage…";
    if (editorialRun?.status === "reviewing") return "Maya is reviewing Leo's edit…";
    return null;
  }, [activeProcessingStage, compactStatus, editorialRun?.status]);
  const videoFilename = production?.source_media?.original_filename || "Recording.mp4";

  if (isLoading) {
    return (
      <div className="h-[100dvh] bg-background text-text-primary flex flex-col items-center justify-center gap-3">
        <Loader2 className="size-8 text-primary animate-spin" />
        <p className="text-xs text-text-secondary font-medium">Opening Croviq Studio...</p>
      </div>
    );
  }

  if (errorMessage && !production) {
    return (
      <div className="h-[100dvh] bg-background text-text-primary flex flex-col items-center justify-center p-6 text-center gap-4">
        <div className="size-12 rounded-full bg-danger/10 text-danger flex items-center justify-center border border-danger/20">
          <AlertCircle className="size-6" />
        </div>
        <div className="max-w-md flex flex-col gap-1">
          <h1 className="text-base font-semibold text-text-primary">Unable to load production</h1>
          <p className="text-xs text-text-secondary">{errorMessage}</p>
        </div>
        <button
          type="button"
          onClick={onNavigateHome}
          className="px-4 py-2 bg-surface-2 text-text-primary hover:bg-surface-3 rounded-lg text-xs font-medium transition-colors border border-border-subtle flex items-center gap-2"
        >
          <ArrowLeft className="size-3.5" />
          <span>Back to Productions</span>
        </button>
      </div>
    );
  }

  return (
    <div
      className="h-[100dvh] max-h-[100dvh] bg-background text-text-primary flex flex-col font-sans select-none overflow-hidden"
      data-testid="editor-workspace"
    >
      {/* Top Navigation Bar */}
      <header className="h-11 bg-surface-1 border-b border-border-subtle px-4 flex items-center justify-between shrink-0 z-30">
        {/* Left: Brand + Project Title */}
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={onNavigateHome}
            className="hover:opacity-80 transition-opacity flex items-center gap-2 shrink-0"
            title="Back to Productions"
            aria-label="Back to Productions"
          >
            <CroviqLogo height={22} className="h-5.5 w-auto" />
          </button>

          <span className="text-border-strong select-none font-light">/</span>

          <span className="text-xs font-semibold text-text-primary truncate tracking-tight">
            {videoFilename}
          </span>
        </div>

        {/* Center: Compact Current Status (No checklist pipeline bar) */}
        <div
          className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-surface-2/70 border border-border-subtle text-xs"
          data-testid="compact-status-banner"
        >
          {activeProcessingStage ? (
            <Loader2 className="size-3.5 text-primary animate-spin shrink-0" />
          ) : (
            <CheckCircle2 className="size-3.5 text-emerald-400 shrink-0" />
          )}
          <span className="font-medium text-text-secondary text-[11px] truncate max-w-xs">
            {compactStatus}
          </span>
        </div>

        {/* Right: Preview Mode Switcher + User Actions */}
        <div className="flex items-center gap-3">
          <PreviewToggle
            mode={previewMode}
            onModeChange={setPreviewMode}
            activeCutCount={twickData.activeCutCount}
            hasStudioVoice={Boolean(studioVoicePreviewUrl)}
            hasShort={Boolean(shortArtifact?.playback_url)}
          />

          <button
            onClick={logout}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-text-muted hover:text-text-primary hover:bg-surface-2 rounded-md transition-colors border border-transparent hover:border-border-subtle"
            title="Sign out"
          >
            <LogOut className="size-3.5" />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </header>

      {/* Main Professional Editor NLE Workstation (3 Columns) */}
      <div className="flex-1 min-h-0 flex overflow-hidden">
        {/* Left Column: Media Bin (220-260px) */}
        <MediaBin
          currentMode={previewMode}
          sourceDurationMs={durationMs}
          editedDurationMs={derivedEditedDurationMs}
          studioVoiceDurationMs={studioVoiceArtifact?.duration_ms}
          masterDurationMs={masterArtifact?.duration_ms}
          shortDurationMs={
            shortArtifact?.duration_ms ||
            (proposal?.short_candidate
              ? proposal.short_candidate.end_ms - proposal.short_candidate.start_ms
              : null)
          }
          hasRenderedPreview={Boolean(renderedPreviewUrl)}
          hasMaster={Boolean(masterArtifact?.playback_url || masterUrl)}
          hasStudioVoice={Boolean(studioVoicePreviewUrl)}
          hasShort={Boolean(shortArtifact?.playback_url || proposal?.short_candidate)}
          brollAssets={brollBinItems}
          onSelectMode={setPreviewMode}
          onSeek={handleSeek}
          className="w-[230px] shrink-0"
        />

        {/* Center Column: Video Canvas (Flexible width, contained video, centered 9:16 Short) */}
        <div className="flex-1 min-h-0 min-w-0 flex flex-col bg-black overflow-hidden relative">
          <VideoStage
            playbackUrl={playbackUrl}
            renderedPreviewUrl={renderedPreviewUrl}
            studioVoicePreviewUrl={studioVoicePreviewUrl}
            shortPlaybackUrl={shortArtifact?.playback_url}
            currentTimeMs={currentTimeMs}
            durationMs={durationMs}
            editedDurationMs={derivedEditedDurationMs}
            studioVoiceDurationMs={studioVoiceArtifact?.duration_ms}
            shortDurationMs={
              shortArtifact?.duration_ms ||
              (proposal?.short_candidate
                ? proposal.short_candidate.end_ms - proposal.short_candidate.start_ms
                : null)
            }
            isPlaying={isPlaying}
            previewMode={previewMode}
            edl={edl}
            shortCandidate={proposal?.short_candidate}
            activeCoverage={activeCoverage}
            onPlayPause={handlePlayPause}
            onSeek={handleSeek}
            onDurationChange={setDurationMs}
            className="flex-1 min-h-0"
          />
        </div>
        {/* Right Column: Production Room (340-400px, Inspector Tabs: AGENTS / TRANSCRIPT / DECISION) */}
        <aside
          className="w-[360px] shrink-0 h-full min-h-0 flex flex-col bg-surface-1 border-l border-border-subtle overflow-hidden"
          data-testid="production-room"
        >
          {/* Agent Presence Header (Click avatar to open settings) */}
          <div className="p-3 border-b border-border-subtle bg-surface-2/30">
            <AgentPresence
              activeAgent={activeAgent}
              statusMessage={activeStatusMessage}
              onOpenSettings={handleOpenSettings}
            />

            {(failedProcessingStage ||
              (editorialRun?.status === "failed" ? "maya-review" : null)) && (
              <div
                className="mt-2 flex items-center justify-between gap-3 rounded-md bg-danger/10 px-2.5 py-1.5 border border-danger/20"
                role="alert"
              >
                <span className="flex items-center gap-1.5 text-[11px] font-medium text-danger">
                  <AlertCircle className="size-3.5 shrink-0" />
                  {processingFailureMessage[failedProcessingStage || "maya-review"]}
                </span>
                <button
                  type="button"
                  className="rounded px-2 py-0.5 text-[10px] font-semibold text-text-primary ring-1 ring-border-strong transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-primary"
                  onClick={() => beginProductionRun(undefined, true)}
                >
                  Retry
                </button>
              </div>
            )}
          </div>

          {/* Inspector Tab Switcher */}
          <div className="flex border-b border-border-subtle bg-surface-2/20 px-3">
            <button
              type="button"
              onClick={() => setRightPanelTab("agents")}
              className={`flex items-center gap-1.5 py-2.5 px-3 text-xs font-semibold border-b-2 transition-colors ${
                rightPanelTab === "agents"
                  ? "border-primary text-text-primary"
                  : "border-transparent text-text-muted hover:text-text-secondary"
              }`}
              data-testid="tab-agents-feed"
            >
              <MessageSquare className="size-3.5" />
              Agents
            </button>
            <button
              type="button"
              onClick={() => setRightPanelTab("transcript")}
              className={`flex items-center gap-1.5 py-2.5 px-3 text-xs font-semibold border-b-2 transition-colors ${
                rightPanelTab === "transcript"
                  ? "border-primary text-text-primary"
                  : "border-transparent text-text-muted hover:text-text-secondary"
              }`}
              data-testid="tab-transcript"
            >
              <FileText className="size-3.5" />
              Transcript
            </button>
            {(selectedDecision || selectedBlock) && (
              <button
                type="button"
                onClick={() => setRightPanelTab("decision")}
                className={`flex items-center gap-1.5 py-2.5 px-3 text-xs font-semibold border-b-2 transition-colors ${
                  rightPanelTab === "decision"
                    ? "border-primary text-text-primary"
                    : "border-transparent text-text-muted hover:text-text-secondary"
                }`}
                data-testid="tab-decision-inspector"
              >
                <Sliders className="size-3.5" />
                Decision
              </button>
            )}
          </div>

          {/* Active Tab Surface */}
          <div className="flex-1 min-h-0 overflow-hidden">
            {rightPanelTab === "agents" ? (
              <AgentActivityFeed
                activities={activities}
                decisions={proposal?.decisions ?? []}
                review={review}
                statusMessage={activeProcessingStage ? compactStatus : null}
                activeAgent={
                  activeProcessingStage === "leo-edit"
                    ? "leo"
                    : activeProcessingStage === "maya-review"
                      ? "maya"
                      : null
                }
                onSeek={handleSeek}
                onSelectActivity={(activity) => {
                  const matching = proposal?.decisions?.find(
                    (decision: EditorDecision) =>
                      decision.decision_id === activity.related_decision_id,
                  );
                  if (matching) handleSelectDecision(matching);
                }}
              />
            ) : rightPanelTab === "transcript" ? (
              <TranscriptPanel
                transcript={transcript}
                currentTimeMs={currentTimeMs}
                decisions={proposal?.decisions || []}
                selectedDecisionId={selectedDecisionId}
                onSelectDecision={handleSelectDecision}
                onSeek={handleSeek}
                className="h-full"
              />
            ) : (
              <div className="p-3 h-full overflow-y-auto">
                <DecisionInspector
                  decision={selectedDecision}
                  directorDecision={selectedDirectorDecision}
                  selectedBlock={selectedBlock}
                  onClose={() => {
                    setSelectedDecisionId(null);
                    setSelectedBlock(null);
                    setRightPanelTab("agents");
                  }}
                  onSeek={handleSeek}
                />
              </div>
            )}
          </div>
        </aside>
      </div>

      {/* Bottom Row: Compressed Twick Timeline (~180-220px) */}
      <div className="h-[190px] shrink-0 border-t border-border-subtle bg-surface-1">
        <EditorTimeline
          twickData={twickData}
          currentTimeMs={currentTimeMs}
          durationMs={durationMs}
          selectedBlockId={selectedBlock?.id || null}
          onSelectBlock={handleSelectBlock}
          onSeek={handleSeek}
          isPlaying={isPlaying}
          className="h-full"
        />
      </div>

      {/* Agent Settings Drawer (Leo / Maya) */}
      <AgentSettingsDrawer
        isOpen={isSettingsOpen}
        agentId={settingsAgentId}
        onClose={() => setIsSettingsOpen(false)}
      />
    </div>
  );
};
