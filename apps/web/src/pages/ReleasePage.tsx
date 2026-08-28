import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Check,
  CheckCircle2,
  Copy,
  Edit3,
  ExternalLink,
  Film,
  Flame,
  HelpCircle,
  Image as ImageIcon,
  Layers,
  Lightbulb,
  Loader2,
  LogOut,
  Maximize2,
  Minimize2,
  Pause,
  Play,
  RotateCcw,
  Save,
  Scissors,
  ShieldCheck,
  Smartphone,
  Sparkles,
  Volume2,
  VolumeX,
} from "lucide-react";
import { CroviqLogo } from "../components/CroviqLogo";
import { useAuth } from "../auth/AuthContext";
import { AgentSettingsDrawer } from "../components/editor/AgentSettingsDrawer";
import ninaAvatar from "../assets/agents/nina.png";
import type { components } from "../api/generated";

type PackagingDetailResponse = components["schemas"]["PackagingDetailResponse"];
type PackagingChapter = components["schemas"]["PackagingChapter"];
type TitleCandidate = components["schemas"]["TitleCandidate"];
type ThumbnailConcept = components["schemas"]["ThumbnailConcept"];

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

export const ReleasePage: React.FC<ReleasePageProps> = ({
  productionId,
  onNavigateHome,
  onNavigateEditor,
}) => {
  const { firebaseUser, logout } = useAuth();
  const videoRef = useRef<HTMLVideoElement>(null);

  const [packagingData, setPackagingData] = useState<PackagingDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isSavingOverrides, setIsSavingOverrides] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

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
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  // Nina Settings Drawer state
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

  const getAuthHeaders = useCallback(async (): Promise<Record<string, string>> => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (firebaseUser) {
      const token = await firebaseUser.getIdToken();
      headers.Authorization = `Bearer ${token}`;
    }
    return headers;
  }, [firebaseUser]);

  // Load packaging details on mount (idempotent, no Gemini call on GET)
  const loadPackaging = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
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
      } else {
        const err = await res.json().catch(() => ({ detail: "Failed to load packaging" }));
        setErrorMessage(err.detail || "Failed to load packaging");
      }
    } catch (err: unknown) {
      console.error("Error loading packaging:", err);
      setErrorMessage(err instanceof Error ? err.message : "Failed to connect to API");
    } finally {
      setIsLoading(false);
    }
  }, [getAuthHeaders, productionId]);

  useEffect(() => {
    loadPackaging();
  }, [loadPackaging]);

  // Explicit packaging generation pass
  const handleGeneratePackaging = async (forceRegenerate: boolean = false) => {
    setIsGenerating(true);
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
      } else {
        const err = await res.json().catch(() => ({ detail: "Packaging generation failed" }));
        setErrorMessage(err.detail || "Packaging generation failed");
      }
    } catch (err: unknown) {
      console.error("Error generating packaging:", err);
      setErrorMessage(err instanceof Error ? err.message : "Error generating packaging");
    } finally {
      setIsGenerating(false);
    }
  };

  // Save creator overrides
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

  const activeVideoSrc = packagingData?.master_url || "";

  return (
    <div
      className="min-h-screen bg-background text-text-primary flex flex-col font-sans select-none"
      data-testid="release-workspace"
    >
      {/* Top Navbar */}
      <header className="h-12 bg-surface-1 border-b border-border-subtle px-4 flex items-center justify-between shrink-0 sticky top-0 z-30">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={onNavigateEditor || onNavigateHome}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-text-secondary hover:text-text-primary hover:bg-surface-2 rounded-md transition-colors border border-border-subtle"
            title="Back to Editor"
            data-testid="btn-back-to-editor"
          >
            <ArrowLeft className="size-3.5" />
            <span>Editor</span>
          </button>

          <span className="text-border-strong select-none font-light">/</span>

          <div className="flex items-center gap-2">
            <CroviqLogo height={20} className="h-5 w-auto" />
            <span className="text-xs font-semibold text-text-primary tracking-tight">
              Release & Packaging
            </span>
          </div>
        </div>

        {/* Center: Packaging Readiness Status */}
        <div
          className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-surface-2 border border-border-subtle text-xs"
          data-testid="packaging-status-badge"
        >
          {isGenerating ? (
            <Loader2 className="size-3.5 text-primary animate-spin" />
          ) : (
            <CheckCircle2 className="size-3.5 text-emerald-400" />
          )}
          <span className="font-medium text-text-secondary text-[11px]">
            {isGenerating
              ? "Nina is packaging the approved master…"
              : packagingData?.proposal
                ? "Publish-ready package generated"
                : "Awaiting packaging generation"}
          </span>
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
            disabled={isSavingOverrides || isGenerating || !packagingData?.proposal}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-surface-2 hover:bg-surface-3 text-text-primary border border-border-subtle rounded-md transition-colors disabled:opacity-50"
            data-testid="btn-save-package-changes"
          >
            {isSavingOverrides ? (
              <Loader2 className="size-3.5 animate-spin text-primary" />
            ) : (
              <Save className="size-3.5" />
            )}
            <span>Save Overrides</span>
          </button>

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

      {/* Main Container */}
      <div className="flex-1 max-w-[1680px] w-full mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left / Center: Master Preview & Packaging Content (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          {/* 1. Master Video Preview Stage */}
          <section
            className="bg-surface-1 border border-border-subtle rounded-xl overflow-hidden shadow-sm"
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

          {/* Initial State / Missing Proposal Banner */}
          {!packagingData?.proposal && (
            <div
              className="p-6 bg-surface-1 border border-border-subtle rounded-xl text-center space-y-4"
              data-testid="banner-initial-package"
            >
              <div className="size-12 rounded-full bg-primary/10 text-primary flex items-center justify-center mx-auto">
                <Sparkles className="size-6" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-text-primary">
                  Ready to Package for YouTube
                </h3>
                <p className="text-xs text-text-secondary max-w-md mx-auto mt-1">
                  Nina will inspect the approved Master video, channel audience patterns, and
                  research findings to generate high-CTR titles, publish-ready descriptions,
                  chapters, and thumbnail concepts.
                </p>
              </div>

              <button
                type="button"
                onClick={() => handleGeneratePackaging(false)}
                disabled={isGenerating || !packagingData?.has_master}
                className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-primary hover:bg-primary/90 rounded-lg transition-colors shadow-sm disabled:opacity-50"
                data-testid="btn-generate-packaging-initial"
              >
                {isGenerating ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Sparkles className="size-4" />
                )}
                <span>Generate Packaging with Nina</span>
              </button>
            </div>
          )}

          {/* Packaging Content Surfaces */}
          {packagingData?.proposal && (
            <>
              {/* 2. Primary Title & Title Candidates */}
              <section
                className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-4 shadow-sm"
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

                {/* Primary Title Input (Editable) */}
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
                                ? "bg-primary/10 border-primary/40 shadow-sm"
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

              {/* 3. Description (Editable) */}
              <section
                className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-3 shadow-sm"
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

              {/* 4. Canonical Chapters (Editable Titles, Fixed Timestamps) */}
              <section
                className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-4 shadow-sm"
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

              {/* 5. Thumbnail Concepts */}
              <section
                className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-4 shadow-sm"
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
                              ? "bg-primary/10 border-primary/50 shadow-sm"
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

              {/* 6. Vertical Short Package (if exists) */}
              {packagingData.proposal.short_package && (
                <section
                  className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-4 shadow-sm"
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

        {/* Right Rail: Nina Agent Activity & Channel Evidence (4 cols) */}
        <div className="lg:col-span-4 space-y-5 lg:sticky lg:top-16">
          {/* Nina Avatar & Persona Card */}
          <div
            className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-4 shadow-sm"
            data-testid="nina-agent-card"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setIsSettingsOpen(true)}
                  className="relative group focus:outline-none"
                  title="Click to configure Nina's prompt & view memory"
                  data-testid="btn-nina-avatar"
                >
                  <img
                    src={ninaAvatar}
                    alt="Nina Packaging Agent"
                    className="size-12 rounded-full object-cover border-2 border-primary/40 group-hover:border-primary transition-all shadow-md"
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
              Nina turns your approved Master video into high-converting titles, publish-ready
              descriptions, chapters, and thumbnail moments.
            </p>

            {/* Explicit Regenerate Button */}
            <div className="pt-2 border-t border-border-subtle">
              <button
                type="button"
                onClick={() => handleGeneratePackaging(true)}
                disabled={isGenerating || !packagingData?.has_master}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-semibold text-text-primary bg-surface-2 hover:bg-surface-3 border border-border-subtle rounded-lg transition-colors disabled:opacity-50 shadow-sm"
                data-testid="btn-regenerate-packaging"
              >
                {isGenerating ? (
                  <Loader2 className="size-3.5 animate-spin text-primary" />
                ) : (
                  <RotateCcw className="size-3.5" />
                )}
                <span>Regenerate Packaging</span>
              </button>
            </div>
          </div>

          {/* Channel Evidence & Packaging Summary Card */}
          {packagingData?.proposal && (
            <div
              className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-4 shadow-sm"
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

          {/* Agent Activity Feed */}
          <div
            className="bg-surface-1 border border-border-subtle rounded-xl p-5 space-y-3 shadow-sm"
            data-testid="section-agent-activity"
          >
            <h4 className="text-xs font-semibold tracking-wide uppercase text-text-secondary">
              Nina Activity
            </h4>

            <div className="space-y-2.5 text-xs">
              <div className="flex items-start gap-2 text-text-secondary">
                <CheckCircle2 className="size-3.5 text-emerald-400 shrink-0 mt-0.5" />
                <span>Packaging the final approved video.</span>
              </div>
              <div className="flex items-start gap-2 text-text-secondary">
                <CheckCircle2 className="size-3.5 text-emerald-400 shrink-0 mt-0.5" />
                <span>The repairability angle is the strongest fit for this channel.</span>
              </div>
              <div className="flex items-start gap-2 text-text-secondary">
                <CheckCircle2 className="size-3.5 text-emerald-400 shrink-0 mt-0.5" />
                <span>I found three frames that could work as high-contrast thumbnails.</span>
              </div>
              <div className="flex items-start gap-2 text-text-secondary">
                <CheckCircle2 className="size-3.5 text-emerald-400 shrink-0 mt-0.5" />
                <span>
                  The first title is my recommendation because similar practical hardware videos on
                  this channel have stronger click-through rates.
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Nina Agent Settings Drawer (Prompt & Memory tabs) */}
      <AgentSettingsDrawer
        isOpen={isSettingsOpen}
        agentId="nina"
        onClose={() => setIsSettingsOpen(false)}
      />
    </div>
  );
};
export default ReleasePage;
