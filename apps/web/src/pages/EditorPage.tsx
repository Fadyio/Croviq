import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, AlertCircle, LogOut, Loader2 } from "lucide-react";
import { CroviqLogo } from "../components/CroviqLogo";
import { useAuth } from "../auth/AuthContext";
import { PreviewToggle, type PreviewMode } from "../components/editor/PreviewToggle";
import { VideoStage } from "../components/editor/VideoStage";
import { EditorTimeline } from "../components/editor/EditorTimeline";
import { TranscriptPanel } from "../components/editor/TranscriptPanel";
import { AgentPresence } from "../components/editor/AgentPresence";
import { AgentActivityFeed } from "../components/editor/AgentActivityFeed";
import { DecisionInspector } from "../components/editor/DecisionInspector";
import { ProductionRunStrip } from "../components/editor/ProductionRunStrip";
import {
  edlToTwickTimeline,
  type EditDecisionList,
  type EditorProposal,
  type DirectorReview,
  type EditorDecision,
  type DirectorDecision,
  type AgentActivity,
  type Transcript,
  type TimelineBlock,
  type CoverageMarker,
} from "../lib/edl-adapter";
import type { components } from "../api/generated";
import {
  deriveProductionRunStages,
  nextMissingProcessingStage,
  type PersistedProductionRun,
  type ProcessingStage,
} from "../lib/production-run";

type Production = components["schemas"]["Production"];
type EditorialRunDetail = components["schemas"]["EditorialRunDetailResponse"];

interface LoadedEditorData {
  productionRun: PersistedProductionRun;
  runDetail: EditorialRunDetail | null;
}

const readOptionalJson = async <T,>(response: Response, label: string): Promise<T | null> => {
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`${label} could not be loaded`);
  return response.json() as Promise<T>;
};
const waitForRunUpdate = async (): Promise<void> => {
  const { promise, resolve } = Promise.withResolvers<void>();
  window.setTimeout(resolve, 750);
  await promise;
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
  const [previewArtifact, setPreviewArtifact] = useState<
    components["schemas"]["RenderArtifactResponse"] | null
  >(null);
  const [masterArtifact, setMasterArtifact] = useState<
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
    ] = await Promise.all([
      fetch(`/api/productions/${productionId}`, { headers }),
      fetch(`/api/productions/${productionId}/playback`, { headers }).catch(() => null),
      fetch(`/api/productions/${productionId}/transcript`, { headers }),
      fetch(`/api/productions/${productionId}/editorial-run`, { headers }),
      fetch(`/api/productions/${productionId}/edl`, { headers }),
      fetch(`/api/productions/${productionId}/renders`, { headers }).catch(() => null),
      fetch(`/api/productions/${productionId}/render-reviews`, { headers }).catch(() => null),
    ]);

    if (!productionResponse.ok) {
      throw new Error(`Production '${productionId}' could not be loaded`);
    }

    const productionData = (await productionResponse.json()) as Production;
    const transcriptData = await readOptionalJson<Transcript>(transcriptResponse, "Transcript");
    const runData = await readOptionalJson<EditorialRunDetail>(runResponse, "Editorial run");
    const edlData = await readOptionalJson<components["schemas"]["EDLDetailResponse"]>(
      edlResponse,
      "Edit plan",
    );
    let rendersData: components["schemas"]["RenderListResponse"] | null = null;
    if (rendersResponse && rendersResponse.ok) {
      try {
        rendersData = (await rendersResponse.json()) as components["schemas"]["RenderListResponse"];
      } catch {
        rendersData = null;
      }
    }
    let reviewsData: components["schemas"]["RenderReviewDetailResponse"] | null = null;
    if (reviewResponse && reviewResponse.ok) {
      try {
        reviewsData =
          (await reviewResponse.json()) as components["schemas"]["RenderReviewDetailResponse"];
      } catch {
        reviewsData = null;
      }
    }
    const latestReview = reviewsData?.review ?? null;
    setRenderReview(latestReview);
    const needsManualReview = Boolean(reviewsData?.needs_manual_review);
    setIsManualReviewRequired(needsManualReview);
    setProduction(productionData);
    setTranscript(transcriptData);
    setProposal(runData?.proposal ?? null);
    setReview(runData?.review ?? null);
    setActivities(runData?.activities ?? []);
    setEditorialRun(runData?.run ?? null);

    const loadedEdl = edlData?.edl ?? null;
    setEdl(loadedEdl);
    if (loadedEdl?.source_duration_ms) setDurationMs(loadedEdl.source_duration_ms);
    else if (transcriptData?.duration_ms) setDurationMs(transcriptData.duration_ms);

    if (playbackResponse?.ok) {
      const playbackData = await playbackResponse.json();
      setPlaybackUrl(playbackData.playback_url);
    }

    const completedPreview =
      rendersData?.renders?.find(
        (r) => r.artifact_type === "PREVIEW" && r.status === "completed",
      ) ?? null;
    setPreviewArtifact(completedPreview);
    if (completedPreview?.playback_url) {
      setRenderedPreviewUrl(completedPreview.playback_url);
    }

    const completedMaster =
      rendersData?.renders?.find((r) => r.artifact_type === "MASTER" && r.status === "completed") ??
      null;
    setMasterArtifact(completedMaster);
    return {
      runDetail: runData,
      productionRun: {
        uploaded: productionData.source_media?.status === "uploaded",
        uploadedAt: productionData.source_media?.uploaded_at,
        transcriptCreatedAt: transcriptData?.created_at,
        editorialRun: runData?.run,
        activities: runData?.activities,
        edlCreatedAt: loadedEdl?.created_at,
        renderCompletedAt: completedPreview?.completed_at,
        renderStatus: completedPreview?.status,
        renderDurationMs: completedPreview?.duration_ms,
        renderReview: latestReview,
        masterArtifact: completedMaster,
        masterStatus: completedMaster?.status,
        masterCompletedAt: completedMaster?.completed_at,
        needsManualReview,
      },
    };
  }, [firebaseUser, productionId]);

  const refreshEditorialRun = useCallback(
    async (headers: HeadersInit): Promise<EditorialRunDetail | null> => {
      const response = await fetch(`/api/productions/${productionId}/editorial-run`, {
        headers,
      });
      if (!response.ok) return null;
      const runData = (await response.json()) as EditorialRunDetail;
      setEditorialRun(runData.run);
      setProposal(runData.proposal ?? null);
      setReview(runData.review ?? null);
      setActivities(runData.activities ?? []);
      if (runData.run.status === "reviewing") {
        activeProcessingStageRef.current = "maya-review";
        setActiveProcessingStage("maya-review");
      }
      return runData;
    },
    [productionId],
  );

  const processProduction = useCallback(
    async (showInitialLoader: boolean, retryFailedRun = false) => {
      setFailedProcessingStage(null);
      setErrorMessage(null);
      if (showInitialLoader) setIsLoading(true);

      let snapshot: LoadedEditorData;
      try {
        snapshot = await loadPersistedData();
      } catch (error) {
        if (showInitialLoader) {
          setErrorMessage(
            error instanceof Error ? error.message : "Failed to load production editor workspace",
          );
        }
        return;
      } finally {
        if (showInitialLoader) setIsLoading(false);
      }

      const persistedEditorialStatus = snapshot.runDetail?.run.status;
      const persistedEditorialStage: ProcessingStage =
        persistedEditorialStatus === "reviewing" ||
        (persistedEditorialStatus === "failed" && snapshot.runDetail?.proposal)
          ? "maya-review"
          : "leo-edit";

      if (persistedEditorialStatus === "failed" && !retryFailedRun) {
        setFailedProcessingStage(persistedEditorialStage);
        return;
      }

      if (persistedEditorialStatus === "analyzing" || persistedEditorialStatus === "reviewing") {
        if (!firebaseUser) return;
        activeProcessingStageRef.current = persistedEditorialStage;
        setActiveProcessingStage(persistedEditorialStage);
        const token = await firebaseUser.getIdToken();
        const headers = { Authorization: `Bearer ${token}` };
        let currentStatus: components["schemas"]["EditorialRunStatus"] = persistedEditorialStatus;
        while (currentStatus === "analyzing" || currentStatus === "reviewing") {
          await waitForRunUpdate();
          const currentRun = await refreshEditorialRun(headers);
          if (currentRun) currentStatus = currentRun.run.status ?? "pending";
        }
        if (currentStatus === "failed") {
          setFailedProcessingStage(activeProcessingStageRef.current ?? persistedEditorialStage);
          setActiveProcessingStage(null);
          return;
        }
        snapshot = await loadPersistedData();
      }

      let nextStage = nextMissingProcessingStage(snapshot.productionRun);
      while (nextStage) {
        const visibleStage: ProcessingStage =
          nextStage === "leo-edit" &&
          (snapshot.runDetail?.run.status === "reviewing" ||
            (snapshot.runDetail?.run.status === "failed" && snapshot.runDetail.proposal))
            ? "maya-review"
            : nextStage;
        activeProcessingStageRef.current = visibleStage;
        setActiveProcessingStage(visibleStage);

        let pollTimer: number | undefined;
        try {
          if (!firebaseUser) throw new Error("Authentication required");
          const token = await firebaseUser.getIdToken();
          const headers = { Authorization: `Bearer ${token}` };
          if (nextStage === "render") {
            const hasPreview = Boolean(
              snapshot.productionRun.renderCompletedAt ||
              snapshot.productionRun.renderStatus === "completed",
            );
            if (!hasPreview) {
              setRenderSubStatus("Rendering preview…");
              const previewResp = await fetch(`/api/productions/${productionId}/renders/preview`, {
                method: "POST",
                headers,
              });
              if (!previewResp.ok) throw new Error("renders/preview failed");
              snapshot = await loadPersistedData();
            }

            if (!snapshot.productionRun.renderReview && !snapshot.productionRun.masterArtifact) {
              setRenderSubStatus("Maya reviewing preview…");
              const reviewResp = await fetch(`/api/productions/${productionId}/review-preview`, {
                method: "POST",
                headers,
              });
              if (!reviewResp.ok) throw new Error("review-preview failed");
              const reviewResult =
                (await reviewResp.json()) as components["schemas"]["ReviewPreviewResponse"];
              if (reviewResult.status === "needs_manual_review") {
                setIsManualReviewRequired(true);
                setRenderSubStatus("Needs manual review");
              } else if (reviewResult.status === "complete") {
                setIsManualReviewRequired(false);
                setRenderSubStatus("Complete");
              }
              snapshot = await loadPersistedData();
            }
          } else {
            const endpoint =
              nextStage === "transcript"
                ? "transcribe"
                : nextStage === "leo-edit"
                  ? "analyze"
                  : "edl";
            if (nextStage === "leo-edit") {
              pollTimer = window.setInterval(() => {
                void refreshEditorialRun(headers);
              }, 750);
            }

            const response = await fetch(`/api/productions/${productionId}/${endpoint}`, {
              method: "POST",
              headers,
            });
            if (!response.ok) throw new Error(`${endpoint} failed`);
            if (pollTimer !== undefined) window.clearInterval(pollTimer);

            snapshot = await loadPersistedData();
          }
          nextStage = nextMissingProcessingStage(snapshot.productionRun);
        } catch {
          if (pollTimer !== undefined) window.clearInterval(pollTimer);
          setFailedProcessingStage(activeProcessingStageRef.current ?? visibleStage);
          setActiveProcessingStage(null);
          return;
        }
      }

      activeProcessingStageRef.current = null;
      setActiveProcessingStage(null);
      setRenderSubStatus(null);
    },
    [firebaseUser, loadPersistedData, productionId, refreshEditorialRun],
  );

  const beginProductionRun = useCallback(
    (showInitialLoader: boolean, retryFailedRun = false) => {
      if (runPromiseRef.current) return;
      runPromiseRef.current = processProduction(showInitialLoader, retryFailedRun).finally(() => {
        runPromiseRef.current = null;
      });
    },
    [processProduction],
  );

  useEffect(() => {
    if (!firebaseUser) return;
    if (processingProductionIdRef.current !== productionId) {
      processingProductionIdRef.current = productionId;
      runPromiseRef.current = null;
    }
    beginProductionRun(true);
  }, [beginProductionRun, firebaseUser, productionId]);

  // Construct Twick Timeline Representation from EDL & Editorial Run
  const twickData = useMemo(() => {
    const effectiveEdl: EditDecisionList = edl || {
      edl_id: `edl_${productionId}`,
      production_id: productionId,
      source_duration_ms: durationMs,
      cuts: [],
      coverage_markers: [],
      created_at: new Date().toISOString(),
    };
    return edlToTwickTimeline(effectiveEdl, proposal, review);
  }, [durationMs, edl, productionId, proposal, review]);

  // Derive active coverage region during playback
  const activeCoverage: CoverageMarker | null = useMemo(() => {
    if (!edl?.coverage_markers) return null;
    return (
      edl.coverage_markers.find(
        (m) => currentTimeMs >= m.source_start_ms && currentTimeMs <= m.source_end_ms,
      ) || null
    );
  }, [currentTimeMs, edl?.coverage_markers]);

  const activeAgent = useMemo<"leo" | "maya" | null>(() => {
    if (activeProcessingStage === "leo-edit") return "leo";
    if (activeProcessingStage === "maya-review") return "maya";
    if (activeProcessingStage === "render" && renderSubStatus?.includes("Maya")) return "maya";
    if (activeProcessingStage === "render" && renderSubStatus?.includes("correction")) return "leo";
    return null;
  }, [activeProcessingStage, renderSubStatus]);

  // Selected decision entity
  const selectedDecision = useMemo<EditorDecision | null>(() => {
    if (!selectedDecisionId || !proposal?.decisions) return null;
    return proposal.decisions.find((d) => d.decision_id === selectedDecisionId) || null;
  }, [proposal?.decisions, selectedDecisionId]);

  // Selected director decision entity
  const selectedDirectorDecision = useMemo<DirectorDecision | null>(() => {
    if (!selectedDecisionId || !review?.decisions) return null;
    return review.decisions.find((d) => d.editor_decision_id === selectedDecisionId) || null;
  }, [review?.decisions, selectedDecisionId]);

  // Handlers
  const handlePlayPause = useCallback(() => {
    setIsPlaying((p) => !p);
  }, []);

  const handleSeek = useCallback((targetMs: number) => {
    setCurrentTimeMs(targetMs);
  }, []);

  const handleSelectBlock = useCallback((block: TimelineBlock | null) => {
    setSelectedBlock(block);
    if (block?.decisionId) {
      setSelectedDecisionId(block.decisionId);
    } else {
      setSelectedDecisionId(null);
    }
  }, []);

  const handleSelectDecision = useCallback(
    (decision: EditorDecision | null) => {
      if (decision) {
        setSelectedDecisionId(decision.decision_id);
        setCurrentTimeMs(decision.source_start_ms);
        const matchingBlock = twickData.blocks.find((b) => b.decisionId === decision.decision_id);
        setSelectedBlock(matchingBlock || null);
      } else {
        setSelectedDecisionId(null);
        setSelectedBlock(null);
      }
    },
    [twickData.blocks],
  );

  const handleCloseInspector = useCallback(() => {
    setSelectedDecisionId(null);
    setSelectedBlock(null);
  }, []);

  const videoFilename =
    production?.source_media?.original_filename ||
    (productionId === "prod_f0b41bfd429e" ? "Fairphone 6 Plus teardown.mp4" : productionId);
  const runStages = deriveProductionRunStages(
    {
      uploaded: production?.source_media?.status === "uploaded",
      uploadedAt: production?.source_media?.uploaded_at,
      transcriptCreatedAt: transcript?.created_at,
      editorialRun,
      activities,
      edlCreatedAt: edl?.created_at,
      renderCompletedAt: previewArtifact?.completed_at,
      renderStatus: previewArtifact?.status,
      renderDurationMs: previewArtifact?.duration_ms,
    },
    { active: activeProcessingStage, failed: failedProcessingStage },
  );

  const processingStatusMessage: Partial<Record<ProcessingStage, string>> = {
    transcript: "Preparing transcript…",
    "leo-edit": "Leo is reviewing the footage…",
    "maya-review": "Maya is reviewing Leo's edit…",
    "edit-plan": "Preparing edit plan…",
    render: renderSubStatus ?? "Rendering preview video…",
  };
  const processingFailureMessage: Record<ProcessingStage, string> = {
    transcript: "Transcription failed",
    "leo-edit": "Leo analysis failed",
    "maya-review": "Director review failed",
    "edit-plan": "Edit plan failed",
    render: "Preview render failed",
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background text-text-primary flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
        <p className="text-xs text-text-secondary font-medium">Opening Editor workspace...</p>
      </div>
    );
  }

  if (errorMessage) {
    return (
      <div className="min-h-screen bg-background text-text-primary flex flex-col items-center justify-center p-6 text-center gap-4">
        <div className="w-12 h-12 rounded-full bg-danger/10 text-danger flex items-center justify-center border border-danger/20">
          <AlertCircle className="w-6 h-6" />
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
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Productions</span>
        </button>
      </div>
    );
  }

  return (
    <div
      className="h-[100dvh] max-h-[100dvh] bg-background text-text-primary flex flex-col font-sans selection:bg-primary/25 overflow-hidden"
      data-testid="editor-workspace"
    >
      {/* Editor Header Bar */}
      <header className="h-12 bg-surface-1 border-b border-border-subtle px-4 sm:px-6 flex items-center justify-between shrink-0 sticky top-0 z-30 backdrop-blur-sm">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={onNavigateHome}
            className="hover:opacity-80 transition-opacity flex items-center gap-2 shrink-0"
            title="Back to Productions"
            aria-label="Back to Productions"
          >
            <CroviqLogo height={24} className="h-6 w-auto" />
          </button>

          <span className="text-border-strong select-none font-light">/</span>

          <span className="text-xs font-semibold text-text-primary truncate tracking-tight">
            {videoFilename}
          </span>
        </div>

        {/* Right Header Controls: PreviewToggle + User / Logout */}
        <div className="flex items-center gap-3">
          <PreviewToggle
            mode={previewMode}
            onModeChange={setPreviewMode}
            activeCutCount={twickData.activeCutCount}
          />

          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-surface-2 border border-border-subtle text-xs text-text-secondary">
            <span className="w-1.5 h-1.5 rounded-full bg-success"></span>
            <span className="font-mono text-text-muted text-[11px]">
              {user?.email || "creator@croviq.app"}
            </span>
          </div>

          <button
            onClick={logout}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-text-muted hover:text-text-primary hover:bg-surface-2 rounded-md transition-colors border border-transparent hover:border-border-subtle"
            title="Sign out"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </header>
      <ProductionRunStrip
        stages={deriveProductionRunStages(
          {
            uploaded: production?.source_media?.status === "uploaded",
            uploadedAt: production?.source_media?.uploaded_at,
            transcriptCreatedAt: transcript?.created_at,
            editorialRun,
            activities,
            edlCreatedAt: edl?.created_at,
            renderCompletedAt: previewArtifact?.completed_at,
            renderStatus: previewArtifact?.status,
            renderDurationMs: previewArtifact?.duration_ms,
            renderReview,
            masterArtifact,
            masterStatus: masterArtifact?.status,
            masterCompletedAt: masterArtifact?.completed_at,
            needsManualReview:
              isManualReviewRequired ||
              (renderReview?.verdict === "CORRECT" && renderSubStatus === "Needs manual review"),
          },
          {
            active: activeProcessingStage,
            failed: failedProcessingStage,
            renderSubStatus,
          },
        )}
      />

      <main className="flex-1 min-h-0 p-3 sm:p-4 flex flex-col lg:flex-row gap-3 sm:gap-4 max-w-[1920px] w-full mx-auto overflow-hidden">
        {/* Main Editor Column (flexible remaining width) */}
        <div className="flex-1 min-h-0 min-w-0 flex flex-col gap-3 overflow-hidden">
          {/* Video Stage */}
          <VideoStage
            playbackUrl={playbackUrl}
            renderedPreviewUrl={renderedPreviewUrl}
            currentTimeMs={currentTimeMs}
            durationMs={durationMs}
            isPlaying={isPlaying}
            previewMode={previewMode}
            edl={edl}
            activeCoverage={activeCoverage}
            onPlayPause={handlePlayPause}
            onSeek={handleSeek}
            onDurationChange={setDurationMs}
            className="flex-1 min-h-0"
          />

          {/* Twick Timeline */}
          <EditorTimeline
            twickData={twickData}
            currentTimeMs={currentTimeMs}
            durationMs={durationMs}
            selectedBlockId={selectedBlock?.id || null}
            onSelectBlock={handleSelectBlock}
            onSeek={handleSeek}
            isPlaying={isPlaying}
            className="h-[220px] shrink-0"
          />
        </div>

        {/* Right Rail (fixed 380px, bounded height to workspace, 25-30% activity / 70-75% transcript) */}
        <aside className="w-full lg:w-[380px] shrink-0 h-full min-h-0 flex flex-col gap-2.5 overflow-hidden bg-surface-1/40 rounded-xl border border-border-subtle p-3">
          <section className="shrink-0 flex flex-col gap-2 border-b border-border-subtle pb-2.5 max-h-[36%] overflow-y-auto overflow-x-hidden w-full min-w-0">
            <AgentPresence activeAgent={activeAgent} />

            {failedProcessingStage && (
              <div
                className="mt-1 flex items-center justify-between gap-3 rounded-md bg-danger/10 px-2.5 py-1.5"
                role="alert"
              >
                <span className="flex items-center gap-2 text-[11px] font-medium text-danger">
                  <AlertCircle className="size-3.5 shrink-0" />
                  {processingFailureMessage[failedProcessingStage]}
                </span>
                <button
                  type="button"
                  className="rounded px-2 py-0.5 text-[10px] font-semibold text-text-primary ring-1 ring-border-strong transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-primary"
                  onClick={() => beginProductionRun(false, true)}
                >
                  Retry
                </button>
              </div>
            )}

            <div className="min-h-0">
              {selectedDecision || selectedBlock ? (
                <DecisionInspector
                  decision={selectedDecision}
                  directorDecision={selectedDirectorDecision}
                  selectedBlock={selectedBlock}
                  onClose={handleCloseInspector}
                  onSeek={handleSeek}
                />
              ) : (
                <AgentActivityFeed
                  activities={activities}
                  decisions={proposal?.decisions ?? []}
                  review={review}
                  statusMessage={
                    activeProcessingStage ? processingStatusMessage[activeProcessingStage] : null
                  }
                  onSelectActivity={(activity) => {
                    const matching = proposal?.decisions?.find(
                      (decision) => decision.decision_id === activity.related_decision_id,
                    );
                    if (matching) handleSelectDecision(matching);
                  }}
                />
              )}
            </div>
          </section>

          <TranscriptPanel
            transcript={transcript}
            currentTimeMs={currentTimeMs}
            decisions={proposal?.decisions || []}
            selectedDecisionId={selectedDecisionId}
            onSelectDecision={handleSelectDecision}
            onSeek={handleSeek}
            className="flex-1 min-h-0"
          />
        </aside>
      </main>
    </div>
  );
};
