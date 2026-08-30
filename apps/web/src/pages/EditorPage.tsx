import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  FileText,
  Loader2,
  LogOut,
  MessageSquare,
  ScrollText,
  ShieldCheck,
} from "lucide-react";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { components } from "../api/generated";
import { useAuth } from "../auth/AuthContext";
import { CroviqLogo } from "../components/CroviqLogo";
import { AgentLogPanel } from "../components/editor/AgentLogPanel";
import { AgentPresence } from "../components/editor/AgentPresence";
import { AgentSettingsDrawer } from "../components/editor/AgentSettingsDrawer";
import { DecisionInspector } from "../components/editor/DecisionInspector";
import { EditorTimeline } from "../components/editor/EditorTimeline";
import {
  type LeoChatContext,
  LeoChatPanel,
  type LeoChatResponse,
} from "../components/editor/LeoChatPanel";
import { type BRollAssetItem, MediaBin } from "../components/editor/MediaBin";
import { type PreviewMode, PreviewToggle } from "../components/editor/PreviewToggle";
import {
  TranscriptPanel,
  type TranscriptRangeSelection,
} from "../components/editor/TranscriptPanel";
import { VideoStage } from "../components/editor/VideoStage";
import {
  type AgentActivity,
  type ApiMediaOutputState,
  apiMediaOutputToState,
  type CanonicalMediaOutputs,
  type CorrectedTranscript,
  type CoverageMarker,
  createInitialMediaOutputs,
  deriveKeepSegments,
  type EditDecisionList,
  type EditorDecision,
  type EditorProposal,
  edlToTwickTimeline,
  type MediaOutputState,
  type TimelineBlock,
  type TimelineTrackId,
  type Transcript,
} from "../lib/edl-adapter";
import {
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

const readOptionalJson = async <T,>(response: Response, _label: string): Promise<T | null> => {
  if (!response.ok) return null;
  return response.json() as Promise<T>;
};

interface EditorPageProps {
  productionId: string;
  onNavigateHome?: () => void;
  onNavigateRelease?: () => void;
}

export const EditorPage: React.FC<EditorPageProps> = ({
  productionId,
  onNavigateHome,
  onNavigateRelease,
}) => {
  const { firebaseUser, logout } = useAuth();

  const [production, setProduction] = useState<Production | null>(null);
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [renderedPreviewUrl, setRenderedPreviewUrl] = useState<string | null>(null);
  const [studioVoicePreviewUrl, setStudioVoicePreviewUrl] = useState<string | null>(null);
  const [masterUrl, setMasterUrl] = useState<string | null>(null);
  const [finalMixUrl, setFinalMixUrl] = useState<string | null>(null);
  const [mediaOutputs, setMediaOutputs] = useState<CanonicalMediaOutputs>(createInitialMediaOutputs);

  const [previewArtifact, setPreviewArtifact] = useState<
    components["schemas"]["RenderArtifactResponse"] | null
  >(null);
  const [masterArtifact, setMasterArtifact] = useState<
    components["schemas"]["RenderArtifactResponse"] | null
  >(null);
  const [studioVoiceArtifact, setStudioVoiceArtifact] = useState<
    components["schemas"]["RenderArtifactResponse"] | null
  >(null);
  const [finalMixArtifact, setFinalMixArtifact] = useState<
    components["schemas"]["RenderArtifactResponse"] | null
  >(null);
  const [renderSubStatus, setRenderSubStatus] = useState<string | null>(null);
  const [correctedTranscript, setCorrectedTranscript] = useState<CorrectedTranscript | null>(null);

  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [proposal, setProposal] = useState<EditorProposal | null>(null);
  const [activities, setActivities] = useState<AgentActivity[]>([]);
  const [brollArtifacts, setBrollArtifacts] = useState<BRollArtifact[]>([]);
  const [editorialRun, setEditorialRun] = useState<EditorialRunDetail["run"] | null>(null);
  const [edl, setEdl] = useState<EditDecisionList | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeProcessingStage, setActiveProcessingStage] = useState<ProcessingStage | null>(null);
  const [failedProcessingStage, setFailedProcessingStage] = useState<ProcessingStage | null>(null);

  const [currentTimeMs, setCurrentTimeMs] = useState(0);
  const [durationMs, setDurationMs] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [previewMode, setPreviewMode] = useState<PreviewMode>("final_mix");
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(null);
  const [selectedBlock, setSelectedBlock] = useState<TimelineBlock | null>(null);

  const [rightPanelTab, setRightPanelTab] = useState<"agent-log" | "chat" | "transcript">(
    "agent-log",
  );
  const [chatContext, setChatContext] = useState<LeoChatContext | null>(null);

  // Agent settings drawer state
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settingsAgentId, setSettingsAgentId] = useState<"leo">("leo");

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
      brollResponse,
      correctedScriptResponse,
    ] = await Promise.all([
      fetch(`/api/productions/${productionId}`, { headers }),
      fetch(`/api/productions/${productionId}/playback`, { headers }).catch(() => null),
      fetch(`/api/productions/${productionId}/transcript`, { headers }),
      fetch(`/api/productions/${productionId}/editorial-run`, { headers }),
      fetch(`/api/productions/${productionId}/edl`, { headers }),
      fetch(`/api/productions/${productionId}/renders`, { headers }).catch(() => null),
      fetch(`/api/productions/${productionId}/broll`, { headers }).catch(() => null),
      fetch(`/api/productions/${productionId}/corrected-script`, { headers }).catch(() => null),
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
      brollPayload,
      correctedScriptPayload,
    ] = await Promise.all([
      productionResponse.json() as Promise<Production>,
      playbackResponse
        ? readOptionalJson<components["schemas"]["ProductionPlaybackResponse"] & {
            original?: ApiMediaOutputState;
            edited?: ApiMediaOutputState;
            voiceover?: ApiMediaOutputState;
            final_mix?: ApiMediaOutputState;
            final_mix_url?: string | null;
          }>(playbackResponse, "Playback")
        : Promise.resolve(null),
      readOptionalJson<Transcript>(transcriptResponse, "Transcript"),
      readOptionalJson<EditorialRunDetail>(runResponse, "Editorial run"),
      readOptionalJson<EditDecisionList>(edlResponse, "EDL"),
      rendersResponse
        ? readOptionalJson<components["schemas"]["RenderListResponse"]>(rendersResponse, "Renders")
        : Promise.resolve(null),
      brollResponse
        ? readOptionalJson<components["schemas"]["BRollListResponse"]>(brollResponse, "BRoll")
        : Promise.resolve(null),
      correctedScriptResponse
        ? readOptionalJson<components["schemas"]["CorrectedScriptResponse"]>(
            correctedScriptResponse,
            "Corrected Script",
          )
        : Promise.resolve(null),
    ]);
    let actualEdl: EditDecisionList | null = null;
    if (edlPayload && typeof edlPayload === "object") {
      if ("edl" in edlPayload && edlPayload.edl) {
        actualEdl = edlPayload.edl as EditDecisionList;
      } else if ("edl_id" in edlPayload) {
        actualEdl = edlPayload as EditDecisionList;
      }
    }
    const activeEdlId = actualEdl?.edl_id ?? null;

    // Filter renders matching the active EDL lineage
    const activeRenders = (rendersPayload?.renders || []).filter(
      (r: components["schemas"]["RenderArtifactResponse"]) =>
        !activeEdlId || r.edl_id === activeEdlId,
    );

    const preview =
      activeRenders.find(
        (render: components["schemas"]["RenderArtifactResponse"]) =>
          render.artifact_type === "PREVIEW",
      ) ?? null;
    const master =
      activeRenders.find(
        (render: components["schemas"]["RenderArtifactResponse"]) =>
          (render.artifact_type as string) === "MASTER",
      ) ?? null;
    const svPreview =
      activeRenders.find(
        (render: components["schemas"]["RenderArtifactResponse"]) =>
          (render.artifact_type as string) === "STUDIO_VOICE_PREVIEW" ||
          (render.artifact_type as string) === "VOICEOVER_PREVIEW",
      ) ?? null;
    const finalMix =
      activeRenders.find(
        (render: components["schemas"]["RenderArtifactResponse"]) =>
          (render.artifact_type as string) === "FINAL_MIX",
      ) ?? null;

    const apiOriginal = apiMediaOutputToState(playbackPayload?.original);
    const apiEdited = apiMediaOutputToState(playbackPayload?.edited);
    const apiVoiceover = apiMediaOutputToState(playbackPayload?.voiceover);
    const apiFinalMix = apiMediaOutputToState(playbackPayload?.final_mix);

    const originalOutput: MediaOutputState = apiOriginal?.available
      ? apiOriginal
      : {
          available: Boolean(
            productionPayload.source_media?.status === "uploaded" &&
              (apiOriginal?.url || playbackPayload?.playback_url),
          ),
          artifactId: productionPayload.source_media?.upload_id || null,
          edlId: null,
          url: apiOriginal?.url || playbackPayload?.playback_url || null,
          durationMs:
            apiOriginal?.durationMs ||
            transcriptPayload?.duration_ms ||
            actualEdl?.source_duration_ms ||
            0,
          status: apiOriginal?.status || (playbackPayload?.playback_url ? "ready" : "unavailable"),
        };

    const editedOutput: MediaOutputState = apiEdited?.available && apiEdited.url
      ? apiEdited
      : preview && preview.status === "completed" && preview.playback_url
        ? {
            available: true,
            artifactId: preview.artifact_id,
            edlId: preview.edl_id,
            url: preview.playback_url || null,
            durationMs: preview.duration_ms || 0,
            status: "ready",
          }
        : {
            available: false,
            artifactId: preview?.artifact_id || apiEdited?.artifactId || null,
            edlId: preview?.edl_id || apiEdited?.edlId || activeEdlId,
            url: null,
            durationMs: 0,
            status: (preview?.status === "rendering" || preview?.status === "pending" || apiEdited?.status === "generating")
              ? "generating"
              : (preview?.status === "failed" || apiEdited?.status === "failed")
                ? "failed"
                : "unavailable",
          };

    const voiceoverOutput: MediaOutputState = apiVoiceover?.available && apiVoiceover.url
      ? apiVoiceover
      : svPreview && svPreview.status === "completed" && svPreview.playback_url
        ? {
            available: true,
            artifactId: svPreview.artifact_id,
            edlId: svPreview.edl_id,
            url: svPreview.playback_url || null,
            durationMs: svPreview.duration_ms || 0,
            status: "ready",
          }
        : {
            available: false,
            artifactId: svPreview?.artifact_id || apiVoiceover?.artifactId || null,
            edlId: svPreview?.edl_id || apiVoiceover?.edlId || activeEdlId,
            url: null,
            durationMs: 0,
            status: (svPreview?.status === "rendering" || svPreview?.status === "pending" || apiVoiceover?.status === "generating")
              ? "generating"
              : (svPreview?.status === "failed" || apiVoiceover?.status === "failed")
                ? "failed"
                : "unavailable",
          };

    const finalMixOutput: MediaOutputState = apiFinalMix?.available && apiFinalMix.url
      ? apiFinalMix
      : finalMix && finalMix.status === "completed" && finalMix.playback_url
        ? {
            available: true,
            artifactId: finalMix.artifact_id,
            edlId: finalMix.edl_id,
            url: finalMix.playback_url || null,
            durationMs: finalMix.duration_ms || 0,
            status: "ready",
          }
        : {
            available: false,
            artifactId: finalMix?.artifact_id || apiFinalMix?.artifactId || null,
            edlId: finalMix?.edl_id || apiFinalMix?.edlId || activeEdlId,
            url: null,
            durationMs: 0,
            status: (finalMix?.status === "rendering" || finalMix?.status === "pending" || apiFinalMix?.status === "generating")
              ? "generating"
              : (finalMix?.status === "failed" || apiFinalMix?.status === "failed")
                ? "failed"
                : "unavailable",
          };

    const canonicalOutputs: CanonicalMediaOutputs = {
      original: originalOutput,
      edited: editedOutput,
      voiceover: voiceoverOutput,
      final_mix: finalMixOutput,
    };
    setMediaOutputs(canonicalOutputs);

    // Explicit fallback to highest valid artifact
    setPreviewMode((prevMode) => {
      if (prevMode === "final_mix" && canonicalOutputs.final_mix.available) return "final_mix";
      if (prevMode === "studio_voice" && canonicalOutputs.voiceover.available) return "studio_voice";
      if (prevMode === "edited" && canonicalOutputs.edited.available) return "edited";
      if (prevMode === "original" && canonicalOutputs.original.available) return "original";

      if (canonicalOutputs.final_mix.available) return "final_mix";
      if (canonicalOutputs.voiceover.available) return "studio_voice";
      if (canonicalOutputs.edited.available) return "edited";
      return "original";
    });

    setProduction(productionPayload);
    setPlaybackUrl(originalOutput.url);
    setRenderedPreviewUrl(editedOutput.url);
    setStudioVoicePreviewUrl(voiceoverOutput.url);
    setMasterUrl(master?.playback_url ?? playbackPayload?.master_url ?? null);
    setFinalMixUrl(finalMixOutput.url);

    setPreviewArtifact(preview);
    setMasterArtifact(master);
    setStudioVoiceArtifact(svPreview);
    setFinalMixArtifact(finalMix);
    if (correctedScriptPayload?.corrected_transcript) {
      setCorrectedTranscript(correctedScriptPayload.corrected_transcript as unknown as CorrectedTranscript);
    }
    if (brollPayload?.artifacts) {
      setBrollArtifacts(brollPayload.artifacts);
    }

    setTranscript(transcriptPayload);
    setEdl(actualEdl);

    const initialDur = actualEdl?.source_duration_ms || transcriptPayload?.duration_ms || originalOutput.durationMs || 0;
    if (initialDur > 0) {
      setDurationMs(initialDur);
    }

    if (runPayload) {
      setProposal(runPayload.proposal as EditorProposal | null);
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
        masterArtifact: master,
        masterStatus: master?.status,
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
              setActiveProcessingStage("leo-edit");
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
            } else if (missingStage === "leo-edit") {
              setActiveProcessingStage("leo-edit");
              const resAnalyze = await fetch(`/api/productions/${productionId}/analyze`, {
                method: "POST",
                headers,
              });
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
    // Strict project isolation: reset previous production state immediately
    setProduction(null);
    setPlaybackUrl(null);
    setRenderedPreviewUrl(null);
    setStudioVoicePreviewUrl(null);
    setMasterUrl(null);
    setFinalMixUrl(null);
    setMediaOutputs(createInitialMediaOutputs());
    setPreviewArtifact(null);
    setMasterArtifact(null);
    setStudioVoiceArtifact(null);
    setFinalMixArtifact(null);
    setTranscript(null);
    setProposal(null);
    setActivities([]);
    setBrollArtifacts([]);
    setEditorialRun(null);
    setEdl(null);
    setSelectedDecisionId(null);
    setSelectedBlock(null);
    setCurrentTimeMs(0);
    setIsPlaying(false);
    setPreviewMode("final_mix");
    setErrorMessage(null);
    setIsLoading(true);

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

  const handleSelectBlock = useCallback(
    (block: TimelineBlock | null) => {
      setSelectedBlock(block);
      if (!block) return;

      const labelPrefix: Record<TimelineTrackId, string> = {
        video: "Video",
        audio: "Audio",
        edits: "Edit",
        broll: "Visual",
        voiceover: "Voiceover",
        music: "Music",
        narration: "Voiceover",
        captions: "Caption",
        chapters: "Chapter",
        "source-video": "Video",
        "dialogue-edits": "Edit",
        coverage: "Visual",
      };
      setSelectedDecisionId(block.decisionId || null);
      handleSeek(block.startMs);
      setChatContext({
        kind: "element",
        label: `${labelPrefix[block.trackId]}: ${block.label}`,
        startMs: block.startMs,
        endMs: block.endMs,
        elementType: block.trackId,
        elementId: block.id,
      });
      setRightPanelTab("chat");
    },
    [handleSeek],
  );

  const handleSelectDecision = useCallback(
    (decision: EditorDecision | null) => {
      setSelectedDecisionId(decision?.decision_id || null);
      if (decision) {
        handleSeek(decision.source_start_ms);
        setRightPanelTab("agent-log");
      }
    },
    [handleSeek],
  );

  const handleTimelineRange = useCallback(
    (startMs: number, endMs: number) => {
      handleSeek(startMs);
      setChatContext({
        kind: "range",
        label: "Timeline selection",
        startMs,
        endMs,
      });
      setRightPanelTab("chat");
    },
    [handleSeek],
  );

  const handleTranscriptRange = useCallback(
    (selection: TranscriptRangeSelection, openChat = false) => {
      handleSeek(selection.startMs);
      setChatContext({
        kind: "element",
        label: selection.label,
        startMs: selection.startMs,
        endMs: selection.endMs,
        elementType: "transcript",
        elementId: selection.id,
      });
      if (openChat) setRightPanelTab("chat");
    },
    [handleSeek],
  );

  const getAuthToken = useCallback(async (): Promise<string> => {
    if (!firebaseUser) throw new Error("Authentication required");
    return firebaseUser.getIdToken();
  }, [firebaseUser]);

  const handleChatWorkspaceUpdated = useCallback(
    async (response: LeoChatResponse) => {
      if (response.edl) setEdl(response.edl);
      if (response.timeline_updated || response.voiceover_updated || response.preview_updated) {
        await loadPersistedData();
      }
    },
    [loadPersistedData],
  );
  const handleOpenSettings = useCallback((agent: "leo") => {
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
      };
    }
    return edlToTwickTimeline(edl, proposal, transcript);
  }, [edl, durationMs, proposal, transcript]);
  // Compute actual or estimated edited duration
  const derivedEditedDurationMs = useMemo(() => {
    if (editorialRun?.status === "failed" || failedProcessingStage === "leo-edit") {
      return 0;
    }
    if (
      previewArtifact?.duration_ms &&
      previewArtifact.duration_ms > 0 &&
      previewArtifact.status === "completed" &&
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
  }, [previewArtifact, edl, durationMs, editorialRun?.status, failedProcessingStage]);
  const selectedDecision = useMemo(() => {
    if (!selectedDecisionId || !proposal?.decisions) return null;
    return (
      proposal.decisions.find((d: EditorDecision) => d.decision_id === selectedDecisionId) || null
    );
  }, [selectedDecisionId, proposal]);

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
      status: b.status,
      isGenerated: b.status === "accepted" || Boolean(b.gcs_object),
    }));
  }, [brollArtifacts]);
  const processingFailureMessage: Record<ProcessingStage, string> = {
    transcript: "Transcription failed",
    "leo-edit": "Leo analysis failed",
    "edit-plan": "Edit plan failed",
    render: "Preview render failed",
  };

  // Compact Single Status Message
  const compactStatus = useMemo(() => {
    if (activeProcessingStage) {
      if (activeProcessingStage === "transcript") return "Preparing transcript…";
      if (activeProcessingStage === "leo-edit") return "Leo is reviewing the footage…";
      if (activeProcessingStage === "edit-plan") return "Preparing edit plan…";
      if (activeProcessingStage === "render") return renderSubStatus || "Rendering preview video…";
      return "Croviq is editing your video…";
    }
    if (editorialRun?.status === "analyzing") return "Leo is reviewing the footage…";
    if (editorialRun?.status === "reviewing") return "Leo is finalizing the edit proposal…";
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
    renderSubStatus,
  ]);

  const activeAgent = useMemo(() => {
    if (activeProcessingStage === "leo-edit") return "leo";
    if (editorialRun?.status === "analyzing" || editorialRun?.status === "reviewing") return "leo";
    return null;
  }, [activeProcessingStage, editorialRun?.status]);

  const activeStatusMessage = useMemo(() => {
    if (activeProcessingStage) return compactStatus;
    if (editorialRun?.status === "analyzing") return "Leo is reviewing the footage…";
    if (editorialRun?.status === "reviewing") return "Leo is finalizing the edit proposal…";
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

        <div
          className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-surface-2/70 border border-border-subtle text-xs"
          data-testid="compact-status-banner"
        >
          {activeProcessingStage ? (
            <>
              <Loader2 className="size-3.5 animate-spin text-primary shrink-0" />
              <span className="text-text-primary font-medium">{compactStatus}</span>
              {renderSubStatus && (
                <span className="text-text-muted text-[11px]">&middot; {renderSubStatus}</span>
              )}
            </>
          ) : (
            <>
              <CheckCircle2 className="size-3.5 text-success shrink-0" />
              <span className="text-text-primary font-medium">Edit ready</span>
            </>
          )}
        </div>

        {/* Right: Preview Mode Switcher + User Actions */}
        <div className="flex items-center gap-3">
          <PreviewToggle
            mode={previewMode}
            onModeChange={setPreviewMode}
            activeCutCount={twickData.activeCutCount}
            mediaOutputs={mediaOutputs}
            hasStudioVoice={mediaOutputs.voiceover.available}
            hasFinalMix={mediaOutputs.final_mix.available}
            hasRenderedPreview={mediaOutputs.edited.available}
          />
          {editorialRun?.status !== "failed" &&
            !failedProcessingStage &&
            Boolean(
              (masterArtifact?.playback_url && masterArtifact?.status === "completed") ||
              (masterUrl && masterArtifact?.status === "completed") ||
              (renderedPreviewUrl && previewArtifact?.status === "completed") ||
              (proposal?.decisions && proposal.decisions.length > 0),
            ) && (
              <button
                type="button"
                onClick={
                  onNavigateRelease ||
                  (() => {
                    window.location.href = `/productions/${productionId}/release`;
                  })
                }
                className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-white bg-primary hover:bg-primary/90 rounded-md transition-colors shadow-sm cursor-pointer"
                title="Run Quality Check with Iris"
                data-testid="btn-run-check"
              >
                <ShieldCheck className="size-3.5" />
                <span>Check</span>
              </button>
            )}
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
        {/* Left Column: compact project artifacts */}
        <MediaBin
          currentMode={previewMode}
          sourceDurationMs={durationMs}
          editedDurationMs={derivedEditedDurationMs}
          studioVoiceDurationMs={mediaOutputs.voiceover.durationMs || studioVoiceArtifact?.duration_ms}
          finalMixDurationMs={mediaOutputs.final_mix.durationMs || finalMixArtifact?.duration_ms}
          hasRenderedPreview={mediaOutputs.edited.available}
          hasMaster={Boolean(
            (masterArtifact?.playback_url || masterUrl) && masterArtifact?.status === "completed",
          )}
          hasStudioVoice={mediaOutputs.voiceover.available}
          hasFinalMix={mediaOutputs.final_mix.available}
          hasProposalOrEdl={Boolean(
            (proposal?.decisions && proposal.decisions.length > 0) ||
            (edl?.cuts && edl.cuts.length > 0),
          )}
          isRunFailed={Boolean(editorialRun?.status === "failed" || failedProcessingStage !== null)}
          brollAssets={brollBinItems}
          mediaOutputs={mediaOutputs}
          onSelectMode={setPreviewMode}
          onSeek={handleSeek}
          className="w-48 shrink-0"
        />

        {/* Center Column: Video Canvas */}
        <div className="flex-1 min-h-0 min-w-0 flex flex-col bg-black overflow-hidden relative">
          <VideoStage
            playbackUrl={playbackUrl}
            renderedPreviewUrl={renderedPreviewUrl}
            studioVoicePreviewUrl={studioVoicePreviewUrl}
            finalMixUrl={finalMixUrl}
            mediaOutputs={mediaOutputs}
            currentTimeMs={currentTimeMs}
            durationMs={durationMs}
            editedDurationMs={derivedEditedDurationMs}
            studioVoiceDurationMs={mediaOutputs.voiceover.durationMs || studioVoiceArtifact?.duration_ms}
            finalMixDurationMs={mediaOutputs.final_mix.durationMs || finalMixArtifact?.duration_ms}
            isPlaying={isPlaying}
            previewMode={previewMode}
            edl={edl}
            activeCoverage={activeCoverage}
            onPlayPause={handlePlayPause}
            onSeek={handleSeek}
            onDurationChange={setDurationMs}
            className="flex-1 min-h-0"
          />
        </div>
        <aside
          className="w-[360px] shrink-0 h-full min-h-0 flex flex-col bg-surface-1 border-l border-border-subtle overflow-hidden"
          data-testid="production-room"
        >
          <div className="p-3 border-b border-border-subtle bg-surface-2/30">
            <AgentPresence
              activeAgent={activeAgent}
              statusMessage={activeStatusMessage}
              onOpenSettings={handleOpenSettings}
            />

            {(failedProcessingStage || editorialRun?.status === "failed") && (
              <div
                className="mt-2 flex items-center justify-between gap-3 rounded-md bg-danger/10 px-2.5 py-1.5 border border-danger/20"
                role="alert"
              >
                <span className="flex items-center gap-1.5 text-[11px] font-medium text-danger">
                  <AlertCircle className="size-3.5 shrink-0" />
                  {processingFailureMessage[failedProcessingStage || "leo-edit"]}
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

          <div
            className="grid grid-cols-3 border-b border-border-subtle bg-surface-2/20 px-2"
            role="tablist"
            aria-label="Editor information"
          >
            <button
              type="button"
              role="tab"
              aria-selected={rightPanelTab === "agent-log"}
              onClick={() => setRightPanelTab("agent-log")}
              className={`flex min-w-0 items-center justify-center gap-1 border-b-2 px-1 py-2.5 text-[9px] font-semibold tracking-wide transition-colors ${
                rightPanelTab === "agent-log"
                  ? "border-primary text-text-primary"
                  : "border-transparent text-text-muted hover:text-text-secondary"
              }`}
              data-testid="tab-agent-log"
            >
              <ScrollText className="size-3 shrink-0" aria-hidden="true" />
              <span>AGENT LOG</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={rightPanelTab === "chat"}
              onClick={() => setRightPanelTab("chat")}
              className={`flex min-w-0 items-center justify-center gap-1 border-b-2 px-1 py-2.5 text-[9px] font-semibold tracking-wide transition-colors ${
                rightPanelTab === "chat"
                  ? "border-primary text-text-primary"
                  : "border-transparent text-text-muted hover:text-text-secondary"
              }`}
              data-testid="tab-chat-leo"
            >
              <MessageSquare className="size-3 shrink-0" aria-hidden="true" />
              <span>CHAT WITH LEO</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={rightPanelTab === "transcript"}
              onClick={() => setRightPanelTab("transcript")}
              className={`flex min-w-0 items-center justify-center gap-1 border-b-2 px-1 py-2.5 text-[9px] font-semibold tracking-wide transition-colors ${
                rightPanelTab === "transcript"
                  ? "border-primary text-text-primary"
                  : "border-transparent text-text-muted hover:text-text-secondary"
              }`}
              data-testid="tab-transcript"
            >
              <FileText className="size-3 shrink-0" aria-hidden="true" />
              <span>TRANSCRIPT</span>
            </button>
          </div>

          <div className="flex min-h-0 flex-1 overflow-hidden">
            {rightPanelTab === "agent-log" ? (
              <div className="flex min-h-0 flex-1 flex-col">
                {(selectedDecision || selectedBlock) && (
                  <div className="max-h-[56%] shrink-0 overflow-y-auto border-b border-border-subtle p-2">
                    <DecisionInspector
                      decision={selectedDecision}
                      selectedBlock={selectedBlock}
                      onClose={() => {
                        setSelectedDecisionId(null);
                        setSelectedBlock(null);
                      }}
                      onSeek={handleSeek}
                    />
                  </div>
                )}
                <AgentLogPanel
                  activities={activities}
                  decisions={proposal?.decisions ?? []}
                  statusMessage={activeProcessingStage ? compactStatus : null}
                  onSeek={handleSeek}
                  onSelectActivity={(activity) => {
                    const matching = proposal?.decisions?.find(
                      (decision: EditorDecision) =>
                        decision.decision_id === activity.related_decision_id,
                    );
                    if (matching) handleSelectDecision(matching);
                  }}
                />
              </div>
            ) : rightPanelTab === "chat" ? (
              <LeoChatPanel
                productionId={productionId}
                currentPlayheadMs={currentTimeMs}
                context={chatContext}
                getAuthToken={getAuthToken}
                onClearContext={() => setChatContext(null)}
                onWorkspaceUpdated={handleChatWorkspaceUpdated}
              />
            ) : (
              <TranscriptPanel
                transcript={transcript}
                correctedTranscript={correctedTranscript}
                edl={edl}
                mode={previewMode}
                currentTimeMs={currentTimeMs}
                decisions={proposal?.decisions || []}
                selectedDecisionId={selectedDecisionId}
                onSelectDecision={handleSelectDecision}
                onSeek={handleSeek}
                onModeChange={setPreviewMode}
                onRangeSelect={(selection) => handleTranscriptRange(selection)}
                onSendRangeToChat={(selection) => handleTranscriptRange(selection, true)}
                className="h-full"
              />
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
          onSelectRange={handleTimelineRange}
          isPlaying={isPlaying}
          className="h-full"
        />
      </div>

      {/* Agent Settings Drawer */}
      <AgentSettingsDrawer
        isOpen={isSettingsOpen}
        agentId={settingsAgentId}
        onClose={() => setIsSettingsOpen(false)}
      />
    </div>
  );
};
