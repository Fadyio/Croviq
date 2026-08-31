import {
  AlertCircle,
  ArrowLeft,
  FileText,
  Loader2,
  LogOut,
  MessageSquare,
  Mic,
  Music,
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
import { MusicTab } from "../components/editor/MusicTab";
import { type PreviewMode, PreviewToggle } from "../components/editor/PreviewToggle";
import {
  TranscriptPanel,
  type TranscriptRangeSelection,
} from "../components/editor/TranscriptPanel";
import {
  FALLBACK_GEMINI_VOICES,
  type VoiceCatalogItem,
  VoiceSettingsTab,
} from "../components/editor/VoiceSettingsTab";
import { VideoStage } from "../components/editor/VideoStage";
import {
  type AgentActivity,
  type ApiMediaOutputState,
  apiMediaOutputToState,
  buildCutSelection,
  buildPointSelection,
  buildRangeSelection,
  buildTranscriptSegmentSelection,
  buildTranscriptWordSelection,
  type CanonicalMediaOutputs,
  type CorrectedTranscript,
  type CoverageMarker,
  createInitialMediaOutputs,
  deriveKeepSegments,
  type EditDecisionList,
  type EditorDecision,
  type EditorProposal,
  type EditorSelection,
  edlToTwickTimeline,
  findCutAtSourceTime,
  findCutById,
  formatTimecode,
  type MediaOutputState,
  type TimelineBlock,
  type Transcript,
  type TranscriptSegment,
  type TranscriptWord,
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
  const [mediaOutputs, setMediaOutputs] =
    useState<CanonicalMediaOutputs>(createInitialMediaOutputs);

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
  const [editorialRun, setEditorialRun] = useState<EditorialRunDetail["run"] | null>(null);
  const [edl, setEdl] = useState<EditDecisionList | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeProcessingStage, setActiveProcessingStage] = useState<ProcessingStage | null>(null);
  const [failedProcessingStage, setFailedProcessingStage] = useState<ProcessingStage | null>(null);

  const [currentTimeMs, setCurrentTimeMs] = useState(0);
  const [durationMs, setDurationMs] = useState(0);
  const [previewMode, setPreviewModeState] = useState<PreviewMode>(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const modeParam = params.get("mode");
      if (
        modeParam === "original" ||
        modeParam === "edited" ||
        modeParam === "studio_voice" ||
        modeParam === "final_mix"
      ) {
        return modeParam as PreviewMode;
      }
      if (modeParam === "voiceover") {
        return "studio_voice";
      }
    }
    return "final_mix";
  });

  const setPreviewMode = useCallback((newModeOrFn: React.SetStateAction<PreviewMode>) => {
    setPreviewModeState((prev) => {
      const next = typeof newModeOrFn === "function" ? newModeOrFn(prev) : newModeOrFn;
      if (typeof window !== "undefined") {
        const url = new URL(window.location.href);
        if (url.searchParams.get("mode") !== next) {
          url.searchParams.set("mode", next);
          window.history.replaceState(null, "", url.toString());
        }
      }
      return next;
    });
  }, []);
  const [isPlaying, setIsPlaying] = useState(false);
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(null);
  const [selectedBlock, setSelectedBlock] = useState<TimelineBlock | null>(null);
  const [rightPanelTab, setRightPanelTab] = useState<
    "agent-log" | "chat" | "transcript" | "voice" | "music"
  >("agent-log");
  const [chatContext, setChatContext] = useState<LeoChatContext | null>(null);

  // Voice and Music tab states
  const [selectedVoice, setSelectedVoice] = useState<string>("Puck");
  const [currentVoiceoverVoiceId, setCurrentVoiceoverVoiceId] = useState<string | null>(null);
  const [voices, setVoices] = useState<VoiceCatalogItem[]>(FALLBACK_GEMINI_VOICES);
  const [isGeneratingVoiceover, setIsGeneratingVoiceover] = useState<boolean>(false);
  const [musicPlaybackUrl, setMusicPlaybackUrl] = useState<string | null>(null);
  const [isGeneratingMusic, setIsGeneratingMusic] = useState<boolean>(false);
  const [isRenderingFinalMix, setIsRenderingFinalMix] = useState<boolean>(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settingsAgentId, setSettingsAgentId] = useState<"leo">("leo");

  const runPromiseRef = useRef<Promise<void> | null>(null);
  const processingProductionIdRef = useRef<string | null>(null);
  const activeProcessingStageRef = useRef<ProcessingStage | null>(null);

  const loadPersistedData = useCallback(async (): Promise<LoadedEditorData> => {
    let token = "";
    if (firebaseUser) {
      token = await firebaseUser.getIdToken();
    } else if (import.meta.env.DEV || window.location.hostname === "localhost") {
      token =
        "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIyN2lFQlVNY3U2VG9EWXdwMk9kRUlIQnV3SUEzIiwidXNlcl9pZCI6IjI3aUVCVU1jdTZUb0RZd3AyT2RFSUhCdXdJQTMiLCJlbWFpbCI6ImRlbW9AY3JvdmlxLmFwcCJ9.signature";
    } else {
      throw new Error("Authentication required");
    }
    const headers = { Authorization: `Bearer ${token}` };
    const [
      productionResponse,
      playbackResponse,
      transcriptResponse,
      runResponse,
      edlResponse,
      rendersResponse,
    ] = await Promise.all([
      fetch(`/api/productions/${productionId}`, { headers }),
      fetch(`/api/productions/${productionId}/playback`, { headers }).catch(() => null),
      fetch(`/api/productions/${productionId}/transcript`, { headers }),
      fetch(`/api/productions/${productionId}/editorial-run`, { headers }),
      fetch(`/api/productions/${productionId}/edl`, { headers }),
      fetch(`/api/productions/${productionId}/renders`, { headers }).catch(() => null),
    ]);
    if (!productionResponse.ok) {
      throw new Error(`Production '${productionId}' could not be loaded`);
    }

    // Load corrected script asynchronously in background so LLM generation never blocks editor mounting
    void fetch(`/api/productions/${productionId}/corrected-script`, { headers })
      .then((res) =>
        res.ok ? (res.json() as Promise<components["schemas"]["CorrectedScriptResponse"]>) : null,
      )
      .then((payload) => {
        if (payload?.corrected_transcript) {
          setCorrectedTranscript(payload.corrected_transcript as unknown as CorrectedTranscript);
        }
      })
      .catch(() => {});

    // Load workspace voice settings and voices in background
    void fetch("/api/workspace/agent-settings", { headers })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.voice_settings?.selected_voice) {
          setSelectedVoice(data.voice_settings.selected_voice);
        }
        if (data?.voices && Array.isArray(data.voices) && data.voices.length > 0) {
          setVoices(data.voices);
        }
      })
      .catch(() => {});

    // Load latest studio voice state
    void fetch(`/api/productions/${productionId}/studio-voice`, { headers })
      .then((res) => (res.ok ? res.json() : null))
      .then((svData) => {
        if (svData?.voice_id) {
          setCurrentVoiceoverVoiceId(svData.voice_id);
        }
      })
      .catch(() => {});
    const [
      productionPayload,
      playbackPayload,
      transcriptPayload,
      runPayload,
      edlPayload,
      rendersPayload,
    ] = await Promise.all([
      productionResponse.json() as Promise<Production>,
      playbackResponse
        ? readOptionalJson<
            components["schemas"]["ProductionPlaybackResponse"] & {
              original?: ApiMediaOutputState;
              edited?: ApiMediaOutputState;
              voiceover?: ApiMediaOutputState;
              final_mix?: ApiMediaOutputState;
              final_mix_url?: string | null;
            }
          >(playbackResponse, "Playback")
        : Promise.resolve(null),
      readOptionalJson<Transcript>(transcriptResponse, "Transcript"),
      readOptionalJson<EditorialRunDetail>(runResponse, "Editorial run"),
      readOptionalJson<EditDecisionList>(edlResponse, "EDL"),
      rendersResponse
        ? readOptionalJson<components["schemas"]["RenderListResponse"]>(rendersResponse, "Renders")
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
    if (apiVoiceover?.voiceId) {
      setCurrentVoiceoverVoiceId(apiVoiceover.voiceId);
    }
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

    const hasExplicitApiEdited = playbackPayload?.edited !== undefined;
    const editedOutput: MediaOutputState =
      apiEdited?.available && apiEdited.url
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
              available: hasExplicitApiEdited ? Boolean(apiEdited?.available) : Boolean(actualEdl),
              artifactId: preview?.artifact_id || apiEdited?.artifactId || null,
              edlId: preview?.edl_id || apiEdited?.edlId || activeEdlId,
              url: null,
              durationMs: 0,
              status:
                preview?.status === "rendering" ||
                preview?.status === "pending" ||
                apiEdited?.status === "generating"
                  ? "generating"
                  : preview?.status === "failed" || apiEdited?.status === "failed"
                    ? "failed"
                    : (hasExplicitApiEdited ? apiEdited?.available : Boolean(actualEdl))
                      ? "ready"
                      : "unavailable",
            };

    const hasExplicitApiVoiceover = playbackPayload?.voiceover !== undefined;
    const voiceoverOutput: MediaOutputState = (() => {
      if (hasExplicitApiVoiceover && apiVoiceover) {
        const isReady =
          apiVoiceover.status === "ready" &&
          Boolean(apiVoiceover.available) &&
          Boolean(apiVoiceover.url) &&
          (!actualEdl?.edl_id || apiVoiceover.edlId === actualEdl.edl_id);
        if (isReady) {
          return {
            available: true,
            artifactId: apiVoiceover.artifactId || null,
            edlId: apiVoiceover.edlId || activeEdlId,
            url: apiVoiceover.url || null,
            durationMs: apiVoiceover.durationMs || 0,
            status: "ready",
            voiceId: apiVoiceover.voiceId || null,
          };
        }
        return {
          available: false,
          artifactId: apiVoiceover.artifactId || null,
          edlId: apiVoiceover.edlId || activeEdlId,
          url: null,
          durationMs: 0,
          status:
            apiVoiceover.status === "generating"
              ? "generating"
              : apiVoiceover.status === "failed"
                ? "failed"
                : apiVoiceover.status === "incomplete"
                  ? "incomplete"
                  : apiVoiceover.status === "stale" ||
                      (apiVoiceover.status as string) === "needs_regeneration"
                    ? "stale"
                    : "unavailable",
          voiceId: apiVoiceover.voiceId || null,
        };
      }
      if (playbackPayload?.studio_voice_preview_url) {
        return {
          available: true,
          artifactId: svPreview?.artifact_id || null,
          edlId: svPreview?.edl_id || activeEdlId,
          url: playbackPayload.studio_voice_preview_url,
          durationMs: svPreview?.duration_ms || 0,
          status: "ready",
        };
      }
      if (
        svPreview &&
        svPreview.status === "completed" &&
        svPreview.playback_url &&
        (!actualEdl?.edl_id || svPreview.edl_id === actualEdl.edl_id)
      ) {
        return {
          available: true,
          artifactId: svPreview.artifact_id,
          edlId: svPreview.edl_id,
          url: svPreview.playback_url,
          durationMs: svPreview.duration_ms || 0,
          status: "ready",
        };
      }
      return {
        available: false,
        artifactId: svPreview?.artifact_id || null,
        edlId: svPreview?.edl_id || activeEdlId,
        url: null,
        durationMs: 0,
        status:
          svPreview?.status === "rendering" || svPreview?.status === "pending"
            ? "generating"
            : svPreview?.status === "failed"
              ? "failed"
              : "unavailable",
      };
    })();

    const finalMixOutput: MediaOutputState =
      apiFinalMix?.available && apiFinalMix.url
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
              status:
                finalMix?.status === "rendering" ||
                finalMix?.status === "pending" ||
                apiFinalMix?.status === "generating"
                  ? "generating"
                  : finalMix?.status === "failed" || apiFinalMix?.status === "failed"
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

    // Explicit fallback to highest valid artifact or URL param
    setPreviewMode((prevMode) => {
      if (typeof window !== "undefined") {
        const params = new URLSearchParams(window.location.search);
        const modeParam = params.get("mode");
        if (modeParam === "original" && canonicalOutputs.original.available) return "original";
        if (modeParam === "edited" && canonicalOutputs.edited.available) return "edited";
        if (
          (modeParam === "studio_voice" || modeParam === "voiceover") &&
          canonicalOutputs.voiceover.available
        )
          return "studio_voice";
        if (modeParam === "final_mix" && canonicalOutputs.final_mix.available) return "final_mix";
      }
      if (prevMode === "final_mix" && canonicalOutputs.final_mix.available) return "final_mix";
      if (prevMode === "studio_voice" && canonicalOutputs.voiceover.available)
        return "studio_voice";
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
    if (playbackPayload?.music_url) {
      setMusicPlaybackUrl(playbackPayload.music_url);
    }
    setPreviewArtifact(preview);
    setMasterArtifact(master);
    setStudioVoiceArtifact(svPreview);
    setFinalMixArtifact(finalMix);

    setTranscript(transcriptPayload);
    setEdl(actualEdl);

    const initialDur =
      actualEdl?.source_duration_ms ||
      transcriptPayload?.duration_ms ||
      originalOutput.durationMs ||
      0;
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
        renderCompletedAt:
          preview?.completed_at ||
          (rendersResponse && !rendersResponse.ok && actualEdl
            ? actualEdl.created_at || new Date().toISOString()
            : null),
        renderStatus:
          preview?.status ||
          (rendersResponse && !rendersResponse.ok && actualEdl ? "completed" : null),
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
    setEditorialRun(null);
    setEdl(null);
    setSelectedDecisionId(null);
    setSelectedBlock(null);
    setCurrentTimeMs(0);
    setIsPlaying(false);
    const params =
      typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
    const modeParam = params?.get("mode");
    if (!modeParam) {
      setPreviewMode("final_mix");
    }
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

  const getAuthToken = useCallback(async (): Promise<string> => {
    if (firebaseUser) {
      return firebaseUser.getIdToken();
    }
    if (import.meta.env.DEV || window.location.hostname === "localhost") {
      return "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIyN2lFQlVNY3U2VG9EWXdwMk9kRUlIQnV3SUEzIiwidXNlcl9pZCI6IjI3aUVCVU1jdTZUb0RZd3AyT2RFSUhCdXdJQTMiLCJlbWFpbCI6ImRlbW9AY3JvdmlxLmFwcCJ9.signature";
    }
    throw new Error("Authentication required");
  }, [firebaseUser]);

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

      setSelectedDecisionId(block.decisionId || null);
      handleSeek(block.startMs);

      const cut = block.decisionId
        ? (edl?.cuts || []).find((c) => c.decision_id === block.decisionId || c.cut_id === block.id)
        : null;
      let selection: EditorSelection;
      if (cut || block.trackId === "edits" || block.trackId === "dialogue-edits") {
        const cutObj = cut || findCutById(block.id, edl) || findCutAtSourceTime(block.startMs, edl);
        if (cutObj) {
          selection = buildCutSelection({
            productionId,
            cut: cutObj,
            previewMode,
            edl,
            transcript,
          });
        } else {
          selection = buildRangeSelection({
            productionId,
            startMs: block.startMs,
            endMs: block.endMs,
            previewMode,
            edl,
            transcript,
          });
          selection.selection_type = "CUT";
          selection.label = block.label;
        }
      } else if (block.trackId === "chapters") {
        selection = buildRangeSelection({
          productionId,
          startMs: block.startMs,
          endMs: block.endMs,
          previewMode,
          edl,
          transcript,
        });
        selection.selection_type = "CHAPTER";
        selection.chapter_id = block.id;
        selection.label = `Chapter: ${block.label}`;
      } else {
        selection = buildRangeSelection({
          productionId,
          startMs: block.startMs,
          endMs: block.endMs,
          previewMode,
          edl,
          transcript,
        });
        selection.label = `${block.label} (${formatTimecode(block.startMs)} → ${formatTimecode(block.endMs)})`;
      }
      setChatContext(selection);
      setRightPanelTab((prev) => (prev === "voice" || prev === "music" ? "agent-log" : prev));
    },
    [handleSeek, edl, productionId, previewMode, transcript],
  );

  const handleSelectDecision = useCallback(
    (decision: EditorDecision | null) => {
      setSelectedDecisionId(decision?.decision_id || null);
      if (decision) {
        handleSeek(decision.source_start_ms);
        const selection = buildRangeSelection({
          productionId,
          startMs: decision.source_start_ms,
          endMs: decision.source_end_ms,
          previewMode,
          edl,
          transcript,
        });
        selection.label =
          decision.concise_reason || `Edit at ${formatTimecode(decision.source_start_ms)}`;
        setChatContext(selection);
        setRightPanelTab((prev) => (prev === "voice" || prev === "music" ? "agent-log" : prev));
      }
    },
    [handleSeek, productionId, previewMode, edl, transcript],
  );
  const handleSelectVoice = useCallback(
    async (voiceId: string) => {
      setSelectedVoice(voiceId);
      setMediaOutputs((prev) => ({
        ...prev,
        voiceover: {
          ...prev.voiceover,
          available: false,
          url: null,
          status: "stale",
        },
      }));
      setPreviewMode((currentMode) => (currentMode === "studio_voice" ? "edited" : currentMode));
      const token = await getAuthToken();
      const headers = {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      };
      await fetch("/api/workspace/agent-settings/voice", {
        method: "PUT",
        headers,
        body: JSON.stringify({
          narration_mode: "studio_voice",
          selected_voice: voiceId,
          language: "en-US",
        }),
      });
    },
    [getAuthToken],
  );

  const handleGenerateVoiceover = useCallback(async () => {
    setIsGeneratingVoiceover(true);
    setMediaOutputs((prev) => ({
      ...prev,
      voiceover: {
        ...prev.voiceover,
        status: "generating",
      },
    }));
    try {
      const token = await getAuthToken();
      const headers = {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      };
      const res = await fetch(`/api/productions/${productionId}/studio-voice`, {
        method: "POST",
        headers,
        body: JSON.stringify({ voice_id: selectedVoice }),
      });
      if (!res.ok) {
        setMediaOutputs((prev) => ({
          ...prev,
          voiceover: {
            ...prev.voiceover,
            status: "failed",
          },
        }));
        throw new Error(`Voiceover generation failed (${res.status})`);
      }
      const svData = await res.json();
      if (svData.result?.voice_id) {
        setCurrentVoiceoverVoiceId(svData.result.voice_id);
      }
      await loadPersistedData();
      if (svData.result?.status === "completed" && svData.studio_voice_preview_url) {
        setPreviewMode("studio_voice");
      }
    } catch (err) {
      setMediaOutputs((prev) => ({
        ...prev,
        voiceover: {
          ...prev.voiceover,
          status: "failed",
        },
      }));
      throw err;
    } finally {
      setIsGeneratingVoiceover(false);
    }
  }, [getAuthToken, loadPersistedData, productionId, selectedVoice]);

  const handleGenerateMusic = useCallback(
    async (prompt: string, modelId = "lyria-3-pro-preview") => {
      setIsGeneratingMusic(true);
      try {
        const token = await getAuthToken();
        const headers = {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        };
        const res = await fetch(`/api/productions/${productionId}/music/generate`, {
          method: "POST",
          headers,
          body: JSON.stringify({
            prompt,
            model_id: modelId,
            volume_db: -24.0,
            ducking_db: -14.0,
          }),
        });
        if (!res.ok) {
          throw new Error(`Music generation failed (${res.status})`);
        }
        const edlData = await res.json();
        if (edlData.edl) {
          setEdl(edlData.edl);
        }
        await loadPersistedData();
      } finally {
        setIsGeneratingMusic(false);
      }
    },
    [getAuthToken, loadPersistedData, productionId],
  );

  const handleUpdateMusicSettings = useCallback(
    async (settings: {
      volume_db?: number;
      ducking_db?: number;
      is_muted?: boolean;
      style?: string;
    }) => {
      const token = await getAuthToken();
      const headers = {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      };
      const res = await fetch(`/api/productions/${productionId}/music`, {
        method: "PATCH",
        headers,
        body: JSON.stringify(settings),
      });
      if (!res.ok) {
        throw new Error(`Updating music mix failed (${res.status})`);
      }
      const edlData = await res.json();
      if (edlData.edl) {
        setEdl(edlData.edl);
      }
      await loadPersistedData();
    },
    [getAuthToken, loadPersistedData, productionId],
  );

  const handleRemoveMusic = useCallback(async () => {
    const token = await getAuthToken();
    const headers = {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
    const res = await fetch(`/api/productions/${productionId}/music`, {
      method: "DELETE",
      headers,
    });
    if (!res.ok) {
      throw new Error(`Removing music failed (${res.status})`);
    }
    const edlData = await res.json();
    if (edlData.edl) {
      setEdl(edlData.edl);
    }
    setMusicPlaybackUrl(null);
    await loadPersistedData();
  }, [getAuthToken, loadPersistedData, productionId]);

  const handleRenderFinalMix = useCallback(async () => {
    setIsRenderingFinalMix(true);
    setMediaOutputs((prev) => ({
      ...prev,
      final_mix: {
        ...prev.final_mix,
        status: "generating",
        available: false,
      },
    }));
    try {
      const token = await getAuthToken();
      const headers = {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      };
      const res = await fetch(`/api/productions/${productionId}/renders/final-mix`, {
        method: "POST",
        headers,
      });
      if (!res.ok) {
        throw new Error(`Final Mix rendering failed (${res.status})`);
      }
      await loadPersistedData();
      setPreviewMode("final_mix");
    } catch (err) {
      setMediaOutputs((prev) => ({
        ...prev,
        final_mix: {
          ...prev.final_mix,
          status: "failed",
          available: false,
        },
      }));
      throw err;
    } finally {
      setIsRenderingFinalMix(false);
    }
  }, [getAuthToken, loadPersistedData, productionId]);
  const handleTimelinePoint = useCallback(
    (targetMs: number) => {
      handleSeek(targetMs);
      const selection = buildPointSelection({
        productionId,
        clickMs: targetMs,
        previewMode,
        edl,
        transcript,
      });
      setChatContext(selection);
    },
    [handleSeek, productionId, previewMode, edl, transcript],
  );

  const handleTimelineRange = useCallback(
    (startMs: number, endMs: number) => {
      handleSeek(startMs);
      const selection = buildRangeSelection({
        productionId,
        startMs,
        endMs,
        previewMode,
        edl,
        transcript,
      });
      setChatContext(selection);
      setRightPanelTab("chat");
    },
    [handleSeek, productionId, previewMode, edl, transcript],
  );

  const handleTranscriptWord = useCallback(
    (word: TranscriptWord) => {
      handleSeek(word.start_ms);
      const selection = buildTranscriptWordSelection({
        productionId,
        word,
        previewMode,
        edl,
        transcript,
      });
      setChatContext(selection);
    },
    [handleSeek, productionId, previewMode, edl, transcript],
  );

  const handleTranscriptSegment = useCallback(
    (segment: TranscriptSegment, openChat = false) => {
      handleSeek(segment.start_ms);
      const selection = buildTranscriptSegmentSelection({
        productionId,
        segment,
        previewMode,
        edl,
        transcript,
      });
      setChatContext(selection);
      if (openChat) setRightPanelTab("chat");
    },
    [handleSeek, productionId, previewMode, edl, transcript],
  );

  const handleTranscriptRange = useCallback(
    (selection: TranscriptRangeSelection, openChat = false) => {
      handleSeek(selection.startMs);
      const canonical = buildRangeSelection({
        productionId,
        startMs: selection.startMs,
        endMs: selection.endMs,
        previewMode,
        edl,
        transcript,
      });
      canonical.label = selection.label;
      setChatContext(canonical);
      if (openChat) setRightPanelTab("chat");
    },
    [handleSeek, productionId, previewMode, edl, transcript],
  );

  const handleChatWorkspaceUpdated = useCallback(
    async (response: LeoChatResponse) => {
      if (response.edl) setEdl(response.edl);
      if (response.timeline_updated || response.voiceover_updated || response.preview_updated) {
        setPreviewMode((prev) =>
          prev === "final_mix" || prev === "studio_voice" ? "edited" : prev,
        );
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

        {activeProcessingStage && (
          <div
            className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-surface-2/70 border border-border-subtle text-xs"
            data-testid="compact-status-banner"
          >
            <Loader2 className="size-3.5 animate-spin text-primary shrink-0" />
            <span className="text-text-primary font-medium">{compactStatus}</span>
            {renderSubStatus && (
              <span className="text-text-muted text-[11px]">&middot; {renderSubStatus}</span>
            )}
          </div>
        )}

        {/* Right: Preview Mode Switcher + User Actions */}
        <div className="flex items-center gap-3">
          <PreviewToggle
            mode={previewMode}
            onModeChange={setPreviewMode}
            activeCutCount={twickData.activeCutCount}
            mediaOutputs={mediaOutputs}
            hasStudioVoice={mediaOutputs.voiceover.available}
            hasFinalMix={mediaOutputs.final_mix.available}
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
                title="Send this cut to Iris for quality review"
                aria-label="Send this cut to Iris for quality review"
                data-testid="btn-run-check"
              >
                <ShieldCheck className="size-3.5" />
                <span>Send to Iris</span>
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

      {/* Main Professional Editor NLE Workstation (2 Columns: Large Player + Leo Panel) */}
      <div className="flex-1 min-h-0 flex overflow-hidden">
        {/* Main Video Player Canvas Area */}
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
            studioVoiceDurationMs={
              mediaOutputs.voiceover.durationMs || studioVoiceArtifact?.duration_ms
            }
            finalMixDurationMs={mediaOutputs.final_mix.durationMs || finalMixArtifact?.duration_ms}
            isPlaying={isPlaying}
            previewMode={previewMode}
            edl={edl}
            activeCoverage={activeCoverage}
            onPlayPause={handlePlayPause}
            onSeek={handleSeek}
            onRetryPlayback={async () => {
              await loadPersistedData();
            }}
            onRenderFinalMix={handleRenderFinalMix}
            isRenderingFinalMix={isRenderingFinalMix}
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
            className="grid grid-cols-5 border-b border-border-subtle bg-surface-2/20 px-1"
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
              <span className="truncate">LOG</span>
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
              <span className="truncate">CHAT</span>
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
              <span className="truncate">TRANSCRIPT</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={rightPanelTab === "voice"}
              onClick={() => setRightPanelTab("voice")}
              className={`flex min-w-0 items-center justify-center gap-1 border-b-2 px-1 py-2.5 text-[9px] font-semibold tracking-wide transition-colors ${
                rightPanelTab === "voice"
                  ? "border-primary text-text-primary"
                  : "border-transparent text-text-muted hover:text-text-secondary"
              }`}
              data-testid="tab-voice"
            >
              <Mic className="size-3 shrink-0" aria-hidden="true" />
              <span className="truncate">VOICE</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={rightPanelTab === "music"}
              onClick={() => setRightPanelTab("music")}
              className={`flex min-w-0 items-center justify-center gap-1 border-b-2 px-1 py-2.5 text-[9px] font-semibold tracking-wide transition-colors ${
                rightPanelTab === "music"
                  ? "border-primary text-text-primary"
                  : "border-transparent text-text-muted hover:text-text-secondary"
              }`}
              data-testid="tab-music"
            >
              <Music className="size-3 shrink-0" aria-hidden="true" />
              <span className="truncate">MUSIC</span>
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
                <LeoChatPanel
                  productionId={productionId}
                  currentPlayheadMs={currentTimeMs}
                  activeEdlId={edl?.edl_id}
                  context={chatContext}
                  getAuthToken={getAuthToken}
                  onClearContext={() => setChatContext(null)}
                  onWorkspaceUpdated={handleChatWorkspaceUpdated}
                />
              </div>
            ) : rightPanelTab === "transcript" ? (
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
                  onSelectWord={handleTranscriptWord}
                  onSelectSegment={handleTranscriptSegment}
                  className="h-full"
                />
              </div>
            ) : rightPanelTab === "voice" ? (
              <VoiceSettingsTab
                productionId={productionId}
                selectedVoice={selectedVoice}
                currentVoiceoverVoiceId={currentVoiceoverVoiceId}
                voiceoverStatus={mediaOutputs.voiceover.status}
                voices={voices}
                getAuthToken={getAuthToken}
                onSelectVoice={handleSelectVoice}
                onGenerateVoiceover={handleGenerateVoiceover}
                isGeneratingVoiceover={isGeneratingVoiceover}
                className="h-full"
              />
            ) : (
              <MusicTab
                productionId={productionId}
                backgroundMusic={edl?.background_music}
                musicPlaybackUrl={musicPlaybackUrl}
                onGenerateMusic={handleGenerateMusic}
                onUpdateMusicSettings={handleUpdateMusicSettings}
                onRemoveMusic={handleRemoveMusic}
                isGenerating={isGeneratingMusic}
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
          previewMode={previewMode}
          selectedBlockId={selectedBlock?.id || null}
          onSelectBlock={handleSelectBlock}
          onSeek={handleSeek}
          onSelectPoint={handleTimelinePoint}
          onSelectRange={handleTimelineRange}
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
