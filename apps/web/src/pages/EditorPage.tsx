import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, AlertCircle, LogOut, Sparkles, Loader2 } from "lucide-react";
import { CroviqLogo } from "../components/CroviqLogo";
import { useAuth } from "../auth/AuthContext";
import { PreviewToggle, type PreviewMode } from "../components/editor/PreviewToggle";
import { VideoStage } from "../components/editor/VideoStage";
import { EditorTimeline } from "../components/editor/EditorTimeline";
import { TranscriptPanel } from "../components/editor/TranscriptPanel";
import { ProductionTeam } from "../components/editor/ProductionTeam";
import { AgentActivityFeed } from "../components/editor/AgentActivityFeed";
import { DecisionInspector } from "../components/editor/DecisionInspector";
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

type Production = components["schemas"]["Production"];

interface EditorPageProps {
  productionId: string;
  onNavigateHome?: () => void;
}

export const EditorPage: React.FC<EditorPageProps> = ({ productionId, onNavigateHome }) => {
  const { user, firebaseUser, logout } = useAuth();

  // Data State
  const [production, setProduction] = useState<Production | null>(null);
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [proposal, setProposal] = useState<EditorProposal | null>(null);
  const [review, setReview] = useState<DirectorReview | null>(null);
  const [activities, setActivities] = useState<AgentActivity[]>([]);
  const [edl, setEdl] = useState<EditDecisionList | null>(null);

  // Loading & Error State
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Playhead & Playback State
  const [currentTimeMs, setCurrentTimeMs] = useState<number>(0);
  const [durationMs, setDurationMs] = useState<number>(113824);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [previewMode, setPreviewMode] = useState<PreviewMode>("edited");

  // Selection State
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(null);
  const [selectedBlock, setSelectedBlock] = useState<TimelineBlock | null>(null);

  // Fetch all persisted production data in parallel
  const fetchEditorData = useCallback(async () => {
    if (!firebaseUser || !productionId) return;
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const token = await firebaseUser.getIdToken();
      const headers = { Authorization: `Bearer ${token}` };

      // 1. Fetch Production
      const prodRes = await fetch(`/api/productions/${productionId}`, { headers });
      if (!prodRes.ok) {
        throw new Error(`Production '${productionId}' not found`);
      }
      const prodData: Production = await prodRes.json();
      setProduction(prodData);

      // 2. Fetch Playback Signed URL
      try {
        const playRes = await fetch(`/api/productions/${productionId}/playback`, { headers });
        if (playRes.ok) {
          const playData = await playRes.json();
          setPlaybackUrl(playData.playback_url);
        }
      } catch {
        // Fallback if playback url is unavailable
      }

      // 3. Fetch Transcript
      try {
        const trRes = await fetch(`/api/productions/${productionId}/transcript`, { headers });
        if (trRes.ok) {
          const trData: Transcript = await trRes.json();
          setTranscript(trData);
        }
      } catch {
        // Transcript not yet available
      }

      // 4. Fetch Editorial Run (Proposal, Review, Activities)
      try {
        const runRes = await fetch(`/api/productions/${productionId}/editorial-run`, { headers });
        if (runRes.ok) {
          const runData = await runRes.json();
          setProposal(runData.proposal || null);
          setReview(runData.review || null);
          setActivities(runData.activities || []);
        }
      } catch {
        // Editorial run not yet available
      }

      // 5. Fetch Canonical EDL
      try {
        const edlRes = await fetch(`/api/productions/${productionId}/edl`, { headers });
        if (edlRes.ok) {
          const edlData = await edlRes.json();
          const loadedEdl: EditDecisionList = edlData.edl;
          setEdl(loadedEdl);
          if (loadedEdl.source_duration_ms > 0) {
            setDurationMs(loadedEdl.source_duration_ms);
          }
        }
      } catch {
        // EDL not yet available
      }
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to load production editor workspace",
      );
    } finally {
      setIsLoading(false);
    }
  }, [firebaseUser, productionId]);

  useEffect(() => {
    fetchEditorData();
  }, [fetchEditorData]);

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

  // Derive active agent based on playhead or selection
  const activeAgent = useMemo<"leo" | "maya" | null>(() => {
    if (activeCoverage) return "leo";
    if (selectedDecisionId) {
      const dec = proposal?.decisions?.find((d) => d.decision_id === selectedDecisionId);
      if (dec) return "leo";
    }
    return null;
  }, [activeCoverage, proposal?.decisions, selectedDecisionId]);

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
      className="min-h-screen bg-background text-text-primary flex flex-col font-sans selection:bg-primary/25"
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

      {/* Editor Main Content: ~75-80% Video & Timeline (Left) + ~20-25% Agents & Transcript (Right) */}
      <main className="flex-1 p-3 sm:p-4 grid grid-cols-1 lg:grid-cols-12 gap-4 items-start max-w-[1920px] w-full mx-auto">
        {/* Left Section: Video Stage + Twick Timeline (8 or 9 cols on desktop) */}
        <div className="lg:col-span-8 xl:col-span-9 flex flex-col gap-4">
          {/* Video Stage */}
          <VideoStage
            playbackUrl={playbackUrl}
            currentTimeMs={currentTimeMs}
            durationMs={durationMs}
            isPlaying={isPlaying}
            previewMode={previewMode}
            edl={edl}
            activeCoverage={activeCoverage}
            onPlayPause={handlePlayPause}
            onSeek={handleSeek}
            onDurationChange={setDurationMs}
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
          />
        </div>

        {/* Right Section: Autonomous Production Team + Activity / Decision Inspector + Transcript Rail */}
        <div className="lg:col-span-4 xl:col-span-3 flex flex-col gap-4">
          {/* Autonomous Editorial Team Status */}
          <ProductionTeam proposal={proposal} review={review} activeAgent={activeAgent} />

          {/* Decision Inspector (when selected) OR Agent Activity Feed */}
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
              onSelectActivity={(act) => {
                // If activity relates to a decision, select it
                if (proposal?.decisions) {
                  const matching = proposal.decisions.find(
                    (d) =>
                      act.message.includes(d.action) ||
                      (d.concise_reason && act.message.includes(d.concise_reason.substring(0, 15))),
                  );
                  if (matching) {
                    handleSelectDecision(matching);
                  }
                }
              }}
            />
          )}

          {/* Canonical Groq Transcript Panel */}
          <TranscriptPanel
            transcript={transcript}
            currentTimeMs={currentTimeMs}
            decisions={proposal?.decisions || []}
            selectedDecisionId={selectedDecisionId}
            onSelectDecision={handleSelectDecision}
            onSeek={handleSeek}
          />
        </div>
      </main>
    </div>
  );
};
