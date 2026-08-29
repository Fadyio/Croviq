import React, { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Check, ChevronDown, LogOut, Plus, RefreshCw, TrendingUp, X } from "lucide-react";
import type { components } from "../api/generated";
import alexAvatar from "../assets/agents/alex.webp";
import { useAuth } from "../auth/AuthContext";
import { CroviqLogo } from "../components/CroviqLogo";
import { AgentTeamSelector, type AgentId } from "../components/AgentTeamSelector";
import { AgentSettingsDrawer } from "../components/editor/AgentSettingsDrawer";
import { AgentChatDrawer } from "../components/AgentChatDrawer";
import { AlexRail } from "../components/dashboard/AlexRail";
import { OverviewView } from "../components/dashboard/OverviewView";
import { WorthWatchingFindingsDrawer } from "../components/dashboard/WorthWatchingFindingsDrawer";
type ChannelDashboard = components["schemas"]["ChannelDashboard"];
type ResearchFinding = components["schemas"]["ResearchFinding"];
type ResearchConfig = components["schemas"]["ResearchConfig"];
type Insight = components["schemas"]["ChannelInsight"];
type YouTubeConnection = components["schemas"]["YouTubeConnectionPublicSummary"];
type ChannelMode = "sample" | "youtube";

interface AppPageProps {
  onNavigateRoute?: (route: string) => void;
  onNavigateNewProject: () => void;
}

export const AppPage: React.FC<AppPageProps> = ({ onNavigateRoute, onNavigateNewProject }) => {
  const { user, firebaseUser, logout } = useAuth();
  const [period, setPeriod] = useState<28 | 90 | 365>(28);
  const [channelMode, setChannelMode] = useState<ChannelMode>("sample");
  const [dashboard, setDashboard] = useState<ChannelDashboard | null>(null);
  const [findings, setFindings] = useState<ResearchFinding[]>([]);
  const [researchConfig, setResearchConfig] = useState<ResearchConfig | null>(null);
  const [youtubeConnection, setYoutubeConnection] = useState<YouTubeConnection | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isConnectingYt, setIsConnectingYt] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [settingsAgentId, setSettingsAgentId] = useState<AgentId | null>(null);
  const [chatAgentId, setChatAgentId] = useState<AgentId | null>(null);
  const [channelSelectorOpen, setChannelSelectorOpen] = useState(false);
  const [youtubeModalOpen, setYoutubeModalOpen] = useState(false);
  const [evidenceModalInsight, setEvidenceModalInsight] = useState<Insight | null>(null);
  const [allFindingsDrawerOpen, setAllFindingsDrawerOpen] = useState(false);
  const selectorRef = useRef<HTMLDivElement>(null);
  const prefersReducedMotion = useReducedMotion();

  const loadFindings = useCallback(async () => {
    if (!firebaseUser) return;
    try {
      const token = await firebaseUser.getIdToken();
      const [findingsRes, configRes] = await Promise.all([
        fetch("/api/channels/research/findings?limit=10", {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch("/api/channels/research/config", {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);
      if (findingsRes.ok) {
        setFindings((await findingsRes.json()) as ResearchFinding[]);
      }
      if (configRes.ok) {
        setResearchConfig((await configRes.json()) as ResearchConfig);
      }
    } catch {
      // Non-blocking research findings load
    }
  }, [firebaseUser]);

  // Unified deterministic connection & dashboard loading
  useEffect(() => {
    if (!firebaseUser) return;
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    const load = async () => {
      try {
        const token = await firebaseUser.getIdToken();
        const params = new URLSearchParams(window.location.search);
        const code = params.get("code");
        const state = params.get("state");
        const errorParam = params.get("error");

        let activeMode: ChannelMode = channelMode;

        if (errorParam) {
          setError(`YouTube OAuth authorization was cancelled or denied: ${errorParam}`);
          window.history.replaceState({}, document.title, "/app");
        } else if (code && state) {
          setIsConnectingYt(true);
          const callbackResp = await fetch("/api/channels/youtube/callback", {
            method: "POST",
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              code,
              state,
              redirect_uri: window.location.origin + "/app",
            }),
          });
          window.history.replaceState({}, document.title, "/app");
          if (callbackResp.ok && !cancelled) {
            const connSummary = (await callbackResp.json()) as YouTubeConnection;
            setYoutubeConnection(connSummary);
            if (connSummary.connected) {
              activeMode = "youtube";
              if (channelMode !== "youtube") {
                setChannelMode("youtube");
              }
            }
          }
        } else {
          const connResp = await fetch("/api/channels/youtube/connection", {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (connResp.ok && !cancelled) {
            const connData = (await connResp.json()) as YouTubeConnection;
            setYoutubeConnection(connData);
            if (connData.connected) {
              activeMode = "youtube";
              if (channelMode !== "youtube") {
                setChannelMode("youtube");
              }
            }
          }
        }

        const endpoint =
          activeMode === "youtube"
            ? `/api/channels/youtube/dashboard?days=${period}`
            : `/api/channels/sample/dashboard?days=${period}`;
        const dashResp = await fetch(endpoint, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!dashResp.ok) {
          if (!cancelled) {
            setDashboard(null);
            const errData = await dashResp.json().catch(() => ({}));
            throw new Error(
              (errData as { detail?: string }).detail || "Channel intelligence could not be loaded",
            );
          }
          return;
        }
        const dashData = (await dashResp.json()) as ChannelDashboard;
        if (!cancelled) {
          setDashboard(dashData);
        }
      } catch (reason) {
        if (!cancelled) {
          setDashboard(null);
          setError(
            reason instanceof Error ? reason.message : "Channel intelligence could not be loaded",
          );
        }
      } finally {
        if (!cancelled) {
          setIsConnectingYt(false);
          setIsLoading(false);
        }
      }
    };

    void load();
    void loadFindings();

    return () => {
      cancelled = true;
    };
  }, [firebaseUser, period, channelMode, refreshKey, loadFindings]);

  const startYouTubeConnect = async () => {
    if (!firebaseUser) return;
    setIsConnectingYt(true);
    setError(null);
    try {
      const token = await firebaseUser.getIdToken();
      const authUrlResp = await fetch("/api/channels/youtube/auth-url", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          redirect_uri: window.location.origin + "/app",
          include_monetary: false,
        }),
      });
      if (!authUrlResp.ok) throw new Error("Could not initialize YouTube connection");
      const authData = (await authUrlResp.json()) as { auth_url: string; state_token: string };
      sessionStorage.setItem("croviq_yt_oauth_state", authData.state_token);
      window.location.href = authData.auth_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "YouTube connection failed");
      setIsConnectingYt(false);
    }
  };

  const disconnectYouTube = async () => {
    if (!firebaseUser) return;
    try {
      const token = await firebaseUser.getIdToken();
      await fetch("/api/channels/youtube/disconnect", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      setYoutubeConnection(null);
      setChannelMode("sample");
      setDashboard(null);
      setChannelSelectorOpen(false);
      setRefreshKey((k) => k + 1);
    } catch {
      // Disconnect non-blocking
    }
  };
  return (
    <div className="min-h-screen bg-background text-text-primary">
      {/* 1. Top Navigation Navbar: Consistent h-14, logo, channel selector, new project, Alex chip */}
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-border-subtle bg-surface-1 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-5">
          <button
            type="button"
            onClick={() => onNavigateRoute?.("/app")}
            className="flex items-center hover:opacity-80 transition-opacity cursor-pointer shrink-0"
            aria-label="Croviq Home"
            title="Croviq Home"
          >
            <CroviqLogo height={24} className="h-6 w-auto" />
          </button>

          {/* Channel Selector Dropdown */}
          <div className="relative" ref={selectorRef}>
            <button
              type="button"
              onClick={() => setChannelSelectorOpen((prev) => !prev)}
              className="flex items-center gap-2.5 rounded-lg border border-border-subtle bg-surface-2/60 px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
              aria-label="Select channel"
              aria-expanded={channelSelectorOpen}
            >
              <span
                className={`flex h-4 w-4 items-center justify-center rounded text-[8px] font-bold ${
                  channelMode === "youtube"
                    ? youtubeConnection?.status === "reauth_required"
                      ? "bg-amber-500/20 text-amber-400"
                      : "bg-red-500/20 text-red-400"
                    : "bg-primary/20 text-primary"
                }`}
              >
                {channelMode === "youtube" ? "YT" : "C"}
              </span>
              <span className="max-w-[140px] sm:max-w-[200px] truncate font-medium">
                {channelMode === "youtube" && youtubeConnection?.channel_title
                  ? youtubeConnection.channel_title
                  : "Croviq"}
              </span>
              <span className="rounded bg-surface-3 px-1.5 py-0.5 text-[9px] text-text-muted">
                {channelMode === "youtube"
                  ? youtubeConnection?.status === "reauth_required"
                    ? "Action Needed"
                    : "Live"
                  : "Sample"}
              </span>
              <ChevronDown className="h-3 w-3 text-text-muted" />
            </button>

            {channelSelectorOpen && (
              <div className="absolute left-0 top-full z-50 mt-1.5 w-64 rounded-xl border border-border-strong bg-surface-2 p-1.5 shadow-2xl backdrop-blur-md">
                <p className="px-2 py-1 text-[10px] font-medium text-text-muted">Channel Source</p>
                <button
                  type="button"
                  onClick={() => {
                    setChannelMode("sample");
                    setChannelSelectorOpen(false);
                  }}
                  className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-xs transition-colors ${
                    channelMode === "sample"
                      ? "bg-surface-1 font-semibold text-text-primary shadow-sm"
                      : "text-text-secondary hover:bg-surface-3 hover:text-text-primary"
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <span className="flex h-5 w-5 items-center justify-center rounded bg-primary/20 text-[9px] font-bold text-primary">
                      C
                    </span>
                    <span>
                      <span className="block font-medium">Croviq</span>
                      <span className="text-[10px] text-text-muted">
                        Deterministic sample dataset
                      </span>
                    </span>
                  </span>
                  {channelMode === "sample" && <Check className="h-3.5 w-3.5 text-primary" />}
                </button>

                {youtubeConnection?.connected ? (
                  <div className="mt-1 border-t border-border-subtle pt-1">
                    <button
                      type="button"
                      onClick={() => {
                        setChannelMode("youtube");
                        setChannelSelectorOpen(false);
                      }}
                      className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-xs transition-colors ${
                        channelMode === "youtube"
                          ? "bg-surface-1 font-semibold text-text-primary shadow-sm"
                          : "text-text-secondary hover:bg-surface-3 hover:text-text-primary"
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <span className="flex h-5 w-5 items-center justify-center rounded bg-red-500/20 text-[9px] font-bold text-red-400">
                          YT
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate font-medium">
                            {youtubeConnection.channel_title}
                          </span>
                          <span className="text-[10px] text-text-muted">
                            {youtubeConnection.subscriber_count?.toLocaleString()} subscribers
                          </span>
                        </span>
                      </span>
                      {channelMode === "youtube" && <Check className="h-3.5 w-3.5 text-primary" />}
                    </button>
                    <button
                      type="button"
                      onClick={disconnectYouTube}
                      className="mt-1 w-full rounded-md px-2.5 py-1 text-left text-[11px] text-text-muted hover:text-danger"
                    >
                      Disconnect YouTube channel
                    </button>
                  </div>
                ) : (
                  <div className="mt-1 border-t border-border-subtle pt-1">
                    <button
                      type="button"
                      onClick={() => {
                        setChannelSelectorOpen(false);
                        setYoutubeModalOpen(true);
                      }}
                      className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-primary hover:bg-primary/10"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      Connect YouTube Channel
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Top Nav Right: New Project + Alex Chip + Account */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onNavigateNewProject}
            aria-label="New Project"
            className="flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm transition-all hover:bg-primary-hover active:scale-[0.98]"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>New Project</span>
          </button>

          <AgentTeamSelector
            onChat={(agentId) => setChatAgentId(agentId)}
            onSettings={(agentId) => setSettingsAgentId(agentId)}
            onSelect={(agentId) => onNavigateRoute?.(`/app/agents/${agentId}`)}
          />

          <div className="hidden md:flex items-center gap-3 border-l border-border-subtle pl-3">
            <span className="max-w-[130px] truncate text-xs text-text-secondary">
              {user?.email}
            </span>
            <button
              type="button"
              onClick={logout}
              className="flex items-center gap-1 text-xs text-text-muted transition-colors hover:text-text-primary"
              aria-label="Logout"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Logout</span>
            </button>
          </div>
        </div>
      </header>

      {/* 2. Desktop Layout: Full available width without dead right gap */}
      <div className="w-full px-4 sm:px-6 py-6">
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_340px] 2xl:grid-cols-[minmax(0,1fr)_360px] gap-6">
          {/* Main Intelligence Workspace */}
          <main className="min-w-0 space-y-6">
            {error && (
              <div
                role="alert"
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger/30 bg-danger/10 p-3.5 text-xs text-danger"
              >
                <span className="min-w-0 flex-1">{error}</span>
                <div className="flex items-center gap-2 shrink-0">
                  {channelMode === "youtube" && (
                    <>
                      <button
                        type="button"
                        onClick={() => setYoutubeModalOpen(true)}
                        className="rounded-md bg-danger/20 px-2.5 py-1 font-semibold text-danger hover:bg-danger/30 transition-colors"
                      >
                        Reconnect YouTube
                      </button>
                      <button
                        type="button"
                        onClick={() => setChannelMode("sample")}
                        className="rounded-md border border-danger/30 px-2.5 py-1 font-medium text-danger hover:bg-danger/10 transition-colors"
                      >
                        Switch to Sample
                      </button>
                    </>
                  )}
                  <button
                    type="button"
                    onClick={() => setRefreshKey((key) => key + 1)}
                    className="flex items-center gap-1.5 font-semibold text-danger hover:underline"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    Retry
                  </button>
                </div>
              </div>
            )}

            {/* Dashboard Header & URL-backed Navigation Tabs */}
            <header className="space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2.5">
                    <h1 className="text-2xl font-bold tracking-tight text-text-primary">
                      {channelMode === "youtube"
                        ? youtubeConnection?.channel_title ||
                          dashboard?.channel.title ||
                          "Connected YouTube"
                        : (dashboard?.channel.title ?? "Croviq")}
                    </h1>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${
                        channelMode === "youtube"
                          ? youtubeConnection?.status === "reauth_required"
                            ? "border-amber-500/40 bg-amber-500/10 text-amber-400"
                            : "border-green-500/40 bg-green-500/10 text-green-400"
                          : "border-border-subtle bg-surface-2 text-text-muted"
                      }`}
                    >
                      {channelMode === "youtube"
                        ? youtubeConnection?.status === "reauth_required"
                          ? "Reauthorization required"
                          : "Connected YouTube"
                        : "Sample channel"}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-text-secondary">
                    {dashboard
                      ? `${dashboard.channel.subscriber_count.toLocaleString()} subscribers · ${dashboard.channel.video_count} videos`
                      : "Alex is analyzing channel data"}
                  </p>
                </div>

                {/* Time Range Selector */}
                <div className="flex items-center gap-2">
                  <select
                    value={period}
                    onChange={(event) => setPeriod(Number(event.target.value) as 28 | 90 | 365)}
                    className="rounded-lg border border-border-subtle bg-surface-1 px-3 py-1.5 text-xs font-medium text-text-primary outline-none transition-colors hover:border-border-strong focus:border-primary"
                    aria-label="Time range"
                  >
                    <option value={28}>Last 28 days</option>
                    <option value={90}>Last 90 days</option>
                    <option value={365}>Last 12 months</option>
                  </select>
                </div>
              </div>
            </header>

            {/* Single Unified Channel Intelligence Dashboard */}
            {isLoading || !dashboard ? (
              <DashboardSkeleton />
            ) : (
              <OverviewView dashboard={dashboard} />
            )}
          </main>

          {/* Persistent Alex Rail (Sticky across all views) */}
          <AlexRail
            insights={dashboard?.insights || []}
            findings={findings}
            lastResearchedAt={
              researchConfig?.last_run_at ||
              (findings.length > 0 ? findings[0].discovered_at : null)
            }
            cadence={researchConfig?.cadence}
            onOpenChat={() => setChatAgentId("alex")}
            onOpenSettings={() => setSettingsAgentId("alex")}
            onOpenEvidence={(insight) => setEvidenceModalInsight(insight)}
            onOpenAllFindings={() => setAllFindingsDrawerOpen(true)}
          />
        </div>
      </div>

      {/* Evidence Modal for Alex Insights */}
      <AnimatePresence>
        {evidenceModalInsight && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
            <motion.div
              initial={prefersReducedMotion ? false : { opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="w-full max-w-lg rounded-xl border border-border-strong bg-surface-1 p-6 shadow-2xl space-y-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-primary">
                    <TrendingUp className="h-3 w-3" />
                    Evidence Analysis
                  </span>
                  <h3 className="mt-1 text-base font-semibold text-text-primary">
                    {evidenceModalInsight.title}
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setEvidenceModalInsight(null)}
                  className="rounded-lg p-1 text-text-muted hover:bg-surface-2 hover:text-text-primary"
                  aria-label="Close dialog"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <p className="text-xs text-text-secondary leading-relaxed">
                {evidenceModalInsight.statement}
              </p>

              <div className="space-y-2.5 pt-1">
                <div className="flex items-center justify-between">
                  <p className="text-[11px] font-semibold text-text-primary">Supporting Evidence</p>
                  {evidenceModalInsight.confidence !== undefined && (
                    <span className="text-[10px] text-text-muted font-mono">
                      Confidence: {(evidenceModalInsight.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                <div className="space-y-2">
                  {evidenceModalInsight.evidence.map((ev) => (
                    <div
                      key={`${ev.kind}-${ev.statement}`}
                      className="rounded-lg bg-surface-2 p-3 text-xs border border-border-subtle"
                    >
                      <div className="flex items-center justify-between">
                        <span className="rounded bg-surface-3 px-1.5 py-0.5 text-[9px] font-bold text-text-muted uppercase tracking-wider">
                          {ev.kind}
                        </span>
                      </div>
                      <p className="mt-1.5 text-text-secondary leading-relaxed">{ev.statement}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-lg bg-primary/10 border border-primary/20 p-3 text-xs">
                <p className="font-semibold text-primary">Action Plan</p>
                <p className="mt-1 text-text-secondary leading-relaxed">
                  {evidenceModalInsight.recommended_action}
                </p>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="button"
                  onClick={() => setEvidenceModalInsight(null)}
                  className="rounded-lg bg-surface-2 px-4 py-2 text-xs font-semibold text-text-primary hover:bg-surface-3 transition-colors"
                >
                  Close
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Connect YouTube Modal */}
      {youtubeModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-xl border border-border-strong bg-surface-1 p-6 shadow-2xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded bg-red-500/15 text-xs font-bold text-red-400">
                  YT
                </span>
                <h3 className="text-sm font-semibold">Connect YouTube Channel</h3>
              </div>
              <button
                type="button"
                onClick={() => setYoutubeModalOpen(false)}
                className="rounded p-1 text-text-muted hover:bg-surface-2"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-3 text-xs leading-relaxed text-text-secondary">
              Connect your official YouTube channel using server-side Google OAuth 2.0. Croviq
              requests read-only access to channel metadata and performance reports.
            </p>
            <div className="mt-4 rounded-md border border-border-subtle bg-surface-2 p-3 text-[11px] text-text-muted">
              <p className="font-medium text-text-primary">Requested read-only scopes:</p>
              <ul className="mt-1 list-inside list-disc space-y-0.5">
                <li>youtube.readonly (channel metadata & video catalog)</li>
                <li>yt-analytics.readonly (retention & views analytics)</li>
              </ul>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setYoutubeModalOpen(false)}
                className="rounded-md border border-border-subtle px-3 py-2 text-xs font-medium text-text-secondary hover:bg-surface-2"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={startYouTubeConnect}
                disabled={isConnectingYt}
                className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-xs font-semibold text-white hover:bg-primary-hover disabled:opacity-50"
              >
                {isConnectingYt ? "Connecting..." : "Authorize Channel"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Worth Watching Topic Radar Drawer */}
      <WorthWatchingFindingsDrawer
        open={allFindingsDrawerOpen}
        findings={findings}
        onClose={() => setAllFindingsDrawerOpen(false)}
      />
      {/* Canonical Agent Chat Drawer */}
      <AgentChatDrawer
        isOpen={Boolean(chatAgentId)}
        agentId={chatAgentId || "alex"}
        onClose={() => setChatAgentId(null)}
        onOpenSettings={() => {
          const currentAid = chatAgentId || "alex";
          setChatAgentId(null);
          setSettingsAgentId(currentAid);
        }}
      />

      {/* Canonical Agent Settings Drawer */}
      <AgentSettingsDrawer
        isOpen={Boolean(settingsAgentId)}
        agentId={settingsAgentId || "alex"}
        onClose={() => setSettingsAgentId(null)}
        onSaved={() => {
          void loadFindings();
          setRefreshKey((k) => k + 1);
        }}
      />
    </div>
  );
};

const DashboardSkeleton: React.FC = () => (
  <div aria-busy="true" aria-label="Loading channel intelligence" className="space-y-6">
    <div className="grid grid-cols-2 lg:grid-cols-4 rounded-xl border border-border-subtle bg-surface-1 divide-y lg:divide-y-0 lg:divide-x divide-border-subtle">
      {[1, 2, 3, 4].map((index) => (
        <div key={index} className="h-24 animate-pulse p-4" />
      ))}
    </div>
    <div className="h-28 animate-pulse rounded-xl border border-border-subtle bg-surface-1" />
    <div className="h-72 animate-pulse rounded-xl border border-border-subtle bg-surface-1" />
  </div>
);
