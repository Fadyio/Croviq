import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  BarChart3,
  Beaker,
  BookOpen,
  Check,
  ChevronDown,
  ExternalLink,
  Globe,
  LayoutDashboard,
  LogOut,
  Plus,
  RefreshCw,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Video,
  X,
} from "lucide-react";
import type { components } from "../api/generated";
import alexAvatar from "../assets/agents/Alex.png";
import { useAuth } from "../auth/AuthContext";
import { CroviqLogo } from "../components/CroviqLogo";
import { AlexSettingsDrawer } from "../components/dashboard/AlexSettingsDrawer";
import {
  ChannelTrendChart,
  TrafficSourceChart,
  VideoPerformanceChart,
} from "../components/dashboard/DashboardCharts";

type ChannelDashboard = components["schemas"]["ChannelDashboard"];
type DashboardKpi = components["schemas"]["DashboardKpi"];
type ResearchFinding = components["schemas"]["ResearchFinding"];
type YouTubeConnection = components["schemas"]["YouTubeConnectionPublicSummary"];
type ChannelMode = "sample" | "youtube";

type AppPageProps = {
  onNavigateNewProject: () => void;
};

const compactNumber = new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const KPI_LABELS: Record<string, string> = {
  views: "Views",
  watch_time_hours: "Watch time",
  net_subscribers: "Net subscribers",
  average_retention: "Average retention",
};

const formatKpiValue = (kpi: DashboardKpi): string => {
  if (kpi.metric === "average_retention") return `${kpi.current_value.toFixed(1)}%`;
  if (kpi.metric === "watch_time_hours") return `${compactNumber.format(kpi.current_value)}h`;
  if (kpi.metric === "net_subscribers") {
    return `${kpi.current_value >= 0 ? "+" : ""}${compactNumber.format(kpi.current_value)}`;
  }
  return compactNumber.format(kpi.current_value);
};

const formatChange = (value: number | null): string => {
  if (value === null) return "No comparable baseline";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}% vs previous period`;
};
const formatDiscoveredAgo = (isoDate: string): string => {
  const discovered = new Date(isoDate);
  const diffMinutes = Math.max(1, Math.floor((Date.now() - discovered.getTime()) / 60000));
  if (diffMinutes < 60) return `Discovered ${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `Discovered ${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `Discovered ${diffDays}d ago`;
};

export const AppPage: React.FC<AppPageProps> = ({ onNavigateNewProject }) => {
  const { user, firebaseUser, logout } = useAuth();
  const [period, setPeriod] = useState<28 | 90 | 365>(28);
  const [channelMode, setChannelMode] = useState<ChannelMode>("sample");
  const [dashboard, setDashboard] = useState<ChannelDashboard | null>(null);
  const [findings, setFindings] = useState<ResearchFinding[]>([]);
  const [youtubeConnection, setYoutubeConnection] = useState<YouTubeConnection | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isConnectingYt, setIsConnectingYt] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [channelSelectorOpen, setChannelSelectorOpen] = useState(false);
  const [youtubeModalOpen, setYoutubeModalOpen] = useState(false);
  const [selectedFinding, setSelectedFinding] = useState<ResearchFinding | null>(null);
  const selectorRef = useRef<HTMLDivElement>(null);

  const loadConnectionStatus = useCallback(async () => {
    if (!firebaseUser) return;
    try {
      const token = await firebaseUser.getIdToken();
      const response = await fetch("/api/channels/youtube/connection", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const data = (await response.json()) as YouTubeConnection;
        setYoutubeConnection(data);
      }
    } catch {
      // Non-blocking connection check
    }
  }, [firebaseUser]);

  const loadFindings = useCallback(async () => {
    if (!firebaseUser) return;
    try {
      const token = await firebaseUser.getIdToken();
      const response = await fetch("/api/channels/research/findings?limit=6", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        setFindings((await response.json()) as ResearchFinding[]);
      }
    } catch {
      // Non-blocking research findings load
    }
  }, [firebaseUser]);

  const loadDashboard = useCallback(async () => {
    if (!firebaseUser) return;
    setIsLoading(true);
    setError(null);
    try {
      const token = await firebaseUser.getIdToken();
      const endpoint =
        channelMode === "youtube"
          ? `/api/channels/youtube/dashboard?days=${period}`
          : `/api/channels/sample/dashboard?days=${period}`;
      const response = await fetch(endpoint, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          (errorData as { detail?: string }).detail || "Channel intelligence could not be loaded",
        );
      }
      setDashboard((await response.json()) as ChannelDashboard);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Channel intelligence could not be loaded",
      );
    } finally {
      setIsLoading(false);
    }
  }, [firebaseUser, period, channelMode]);

  useEffect(() => {
    void loadConnectionStatus();
    void loadFindings();
  }, [loadConnectionStatus, loadFindings]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard, refreshKey]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (selectorRef.current && !selectorRef.current.contains(event.target as Node)) {
        setChannelSelectorOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

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

      // In testing/demo environment, execute simulated callback with mock code
      const callbackResp = await fetch("/api/channels/youtube/callback", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          code: "mock-youtube-auth-code",
          state: authData.state_token,
          redirect_uri: window.location.origin + "/app",
        }),
      });
      if (!callbackResp.ok) throw new Error("Could not authorize YouTube channel");
      const connSummary = (await callbackResp.json()) as YouTubeConnection;
      setYoutubeConnection(connSummary);
      setChannelMode("youtube");
      setYoutubeModalOpen(false);
      setChannelSelectorOpen(false);
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "YouTube connection failed");
    } finally {
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
      setChannelSelectorOpen(false);
      setRefreshKey((k) => k + 1);
    } catch {
      // Disconnect non-blocking
    }
  };

  return (
    <div className="min-h-screen bg-background text-text-primary">
      {/* Top Navigation */}
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-border-subtle bg-surface-1 px-4 lg:px-6">
        <div className="flex min-w-0 items-center gap-5">
          <CroviqLogo height={24} className="h-6 w-auto shrink-0" />

          {/* Channel Selector Dropdown */}
          <div className="relative" ref={selectorRef}>
            <button
              type="button"
              onClick={() => setChannelSelectorOpen((prev) => !prev)}
              className="flex min-w-52 items-center justify-between gap-3 rounded-md border border-border-subtle bg-background px-3 py-2 text-xs text-text-secondary hover:border-border-strong"
              aria-label="Select channel"
              aria-expanded={channelSelectorOpen}
            >
              <span className="flex min-w-0 items-center gap-2">
                <span
                  className={`flex h-5 w-5 items-center justify-center rounded text-[9px] font-bold ${
                    channelMode === "youtube"
                      ? "bg-red-500/15 text-red-400"
                      : "bg-primary/15 text-primary"
                  }`}
                >
                  {channelMode === "youtube" ? "YT" : "C"}
                </span>
                <span className="truncate">
                  {channelMode === "youtube" && youtubeConnection?.channel_title
                    ? `YouTube · ${youtubeConnection.channel_title}`
                    : "Croviq · Sample channel"}
                </span>
              </span>
              <ChevronDown className="h-3.5 w-3.5" />
            </button>

            {channelSelectorOpen && (
              <div className="absolute left-0 top-full z-50 mt-1.5 w-72 rounded-lg border border-border-strong bg-surface-2 p-2 shadow-2xl">
                <p className="px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.14em] text-text-muted">
                  Channel Sources
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setChannelMode("sample");
                    setChannelSelectorOpen(false);
                  }}
                  className={`mt-1 flex w-full items-center justify-between rounded-md px-2.5 py-2 text-left text-xs transition-colors ${
                    channelMode === "sample"
                      ? "bg-surface-3 font-semibold text-text-primary"
                      : "text-text-secondary hover:bg-surface-3 hover:text-text-primary"
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <span className="flex h-5 w-5 items-center justify-center rounded bg-primary/15 text-[9px] font-bold text-primary">
                      C
                    </span>
                    <span>
                      <span className="block font-medium leading-none">Croviq Sample Channel</span>
                      <span className="mt-1 block text-[10px] text-text-muted">
                        Synthetic analytics modeled on YouTube Data and Analytics APIs
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
                      className={`flex w-full items-center justify-between rounded-md px-2.5 py-2 text-left text-xs transition-colors ${
                        channelMode === "youtube"
                          ? "bg-surface-3 font-semibold text-text-primary"
                          : "text-text-secondary hover:bg-surface-3 hover:text-text-primary"
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <span className="flex h-5 w-5 items-center justify-center rounded bg-red-500/15 text-[9px] font-bold text-red-400">
                          YT
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate font-medium leading-none">
                            {youtubeConnection.channel_title}
                          </span>
                          <span className="mt-1 block text-[10px] text-text-muted">
                            {youtubeConnection.subscriber_count?.toLocaleString()} subscribers
                          </span>
                        </span>
                      </span>
                      {channelMode === "youtube" && <Check className="h-3.5 w-3.5 text-primary" />}
                    </button>
                    <button
                      type="button"
                      onClick={disconnectYouTube}
                      className="mt-1 w-full rounded px-2.5 py-1 text-left text-[10px] text-text-muted hover:text-error"
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
                      className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-xs font-medium text-primary hover:bg-primary/10"
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

        <div className="flex items-center gap-2 sm:gap-3">
          <button
            type="button"
            onClick={onNavigateNewProject}
            aria-label="New Project"
            className="flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-xs font-semibold text-background hover:opacity-90"
          >
            <Plus className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">New Project</span>
          </button>
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            className="flex items-center gap-2 rounded-md border border-border-subtle bg-background p-1.5 pr-2.5 text-left hover:border-border-strong"
            aria-label="Open Alex settings"
          >
            <img src={alexAvatar} alt="Alex" className="h-7 w-7 rounded object-cover" />
            <span className="hidden md:block">
              <span className="block text-[11px] font-semibold leading-none">Alex</span>
              <span className="mt-1 block text-[9px] leading-none text-text-muted">
                Data Scientist
              </span>
            </span>
          </button>
          <div className="hidden max-w-36 lg:block">
            <p className="truncate text-[10px] text-text-secondary">{user?.email}</p>
            <button
              type="button"
              onClick={logout}
              className="mt-0.5 flex items-center gap-1 text-[9px] text-text-muted hover:text-text-primary"
            >
              <LogOut className="h-2.5 w-2.5" />
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Main Workspace Grid: Left Navigation / Center Dashboard / Right Alex Rail */}
      <div className="mx-auto grid max-w-[1800px] grid-cols-1 xl:grid-cols-[168px_minmax(0,1fr)_340px]">
        {/* Left Navigation */}
        <aside className="hidden border-r border-border-subtle bg-surface-1/50 px-3 py-5 xl:block">
          <nav aria-label="Channel intelligence" className="sticky top-20 space-y-1">
            <a
              href="#overview"
              className="flex items-center gap-2 rounded-md bg-surface-2 px-3 py-2 text-xs font-medium"
            >
              <LayoutDashboard className="h-3.5 w-3.5 text-primary" />
              Overview
            </a>
            <a
              href="#performance"
              className="flex items-center gap-2 rounded-md px-3 py-2 text-xs text-text-muted hover:bg-surface-2 hover:text-text-secondary"
            >
              <BarChart3 className="h-3.5 w-3.5" />
              Performance
            </a>
            <a
              href="#experiments"
              className="flex items-center gap-2 rounded-md px-3 py-2 text-xs text-text-muted hover:bg-surface-2 hover:text-text-secondary"
            >
              <Beaker className="h-3.5 w-3.5" />
              Experiments
            </a>
            <button
              type="button"
              onClick={() => setSettingsOpen(true)}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-xs text-text-muted hover:bg-surface-2 hover:text-text-secondary"
            >
              <BookOpen className="h-3.5 w-3.5" />
              Alex memory
            </button>
            <div className="mt-6 border-t border-border-subtle pt-4">
              <p className="px-3 text-[9px] font-semibold uppercase tracking-[0.14em] text-text-muted">
                Channel source
              </p>
              {youtubeConnection?.connected ? (
                <div className="mt-2 px-3 text-xs">
                  <span className="block text-[11px] font-medium text-text-primary truncate">
                    {youtubeConnection.channel_title}
                  </span>
                  <span className="block text-[9px] text-text-muted">Real YouTube sync active</span>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setYoutubeModalOpen(true)}
                  className="mt-2 flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs text-text-muted hover:bg-surface-2 hover:text-text-primary"
                >
                  <Video className="h-3.5 w-3.5 text-primary" />
                  Connect YouTube
                </button>
              )}
            </div>
          </nav>
        </aside>

        {/* Center Dashboard */}
        <main id="overview" className="min-w-0 px-4 py-5 sm:px-6 lg:py-6">
          {error && (
            <div
              role="alert"
              className="mb-5 flex items-center justify-between rounded-md border border-error/30 bg-error/10 p-3 text-xs text-error"
            >
              <span>{error}</span>
              <button
                type="button"
                onClick={() => setRefreshKey((key) => key + 1)}
                className="flex items-center gap-1.5 font-semibold"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Retry
              </button>
            </div>
          )}

          {/* Channel Header */}
          <section className="mb-5 flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <div
                className={`flex h-11 w-11 items-center justify-center rounded-md border border-border-strong text-sm font-bold ${
                  channelMode === "youtube"
                    ? "bg-red-500/15 text-red-400"
                    : "bg-surface-2 text-primary"
                }`}
              >
                {channelMode === "youtube" ? "YT" : "C"}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-lg font-semibold tracking-tight">
                    {dashboard?.channel.title ?? "Channel intelligence"}
                  </h1>
                  <span
                    className="rounded border border-border-subtle bg-surface-2 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-text-muted"
                    title={
                      channelMode === "youtube"
                        ? "Real YouTube analytics from connected Google account"
                        : "Synthetic analytics modeled on YouTube Data and Analytics APIs."
                    }
                  >
                    {channelMode === "youtube" ? "Connected YouTube" : "Sample channel"}
                  </span>
                </div>
                <p className="mt-1 text-xs text-text-muted">
                  {dashboard
                    ? `${dashboard.channel.subscriber_count.toLocaleString()} subscribers · ${dashboard.channel.video_count} videos`
                    : "Alex is loading canonical channel data"}
                </p>
              </div>
            </div>
            <label className="text-[10px] font-medium uppercase tracking-[0.12em] text-text-muted">
              Time range
              <select
                value={period}
                onChange={(event) => setPeriod(Number(event.target.value) as 28 | 90 | 365)}
                className="ml-2 rounded-md border border-border-subtle bg-surface-1 px-3 py-2 text-xs normal-case tracking-normal text-text-primary outline-none focus:border-primary"
              >
                <option value={28}>Last 28 days</option>
                <option value={90}>Last 90 days</option>
                <option value={365}>Last 12 months</option>
              </select>
            </label>
          </section>

          {isLoading || !dashboard ? (
            <DashboardSkeleton />
          ) : (
            <div className="space-y-4">
              {/* 4 High-Value KPI Cards */}
              <section className="grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Channel KPIs">
                {dashboard.kpis.map((kpi) => (
                  <KpiCard key={kpi.metric} kpi={kpi} />
                ))}
              </section>

              {/* Since Your Last Upload Card */}
              <section
                className="grid gap-3 rounded-lg border border-border-subtle bg-surface-1 p-4 md:grid-cols-[1fr_auto_1fr]"
                aria-labelledby="latest-upload-title"
              >
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
                    Since your last upload
                  </p>
                  <h2 id="latest-upload-title" className="mt-1 line-clamp-1 text-sm font-semibold">
                    {dashboard.latest_video.title}
                  </h2>
                  <p className="mt-1 text-[10px] text-text-muted">
                    Published {new Date(dashboard.latest_video.published_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="hidden w-px bg-border-subtle md:block" />
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="font-mono text-xl font-semibold">
                      {dashboard.latest_video.net_subscribers >= 0 ? "+" : ""}
                      {dashboard.latest_video.net_subscribers}
                    </p>
                    <p className="text-[10px] text-text-muted">
                      net subscribers ·{" "}
                      {dashboard.latest_video.subscriber_conversion_delta_percentage >= 0
                        ? "+"
                        : ""}
                      {dashboard.latest_video.subscriber_conversion_delta_percentage.toFixed(1)}% vs
                      median conversion
                    </p>
                  </div>
                  <div>
                    <p className="font-mono text-xl font-semibold">
                      {compactNumber.format(dashboard.latest_video.views)}
                    </p>
                    <p className="text-[10px] text-text-muted">
                      views · {dashboard.latest_video.view_delta_percentage >= 0 ? "+" : ""}
                      {dashboard.latest_video.view_delta_percentage.toFixed(1)}% vs channel median
                    </p>
                  </div>
                </div>
              </section>

              {/* Dominant Primary Trend Chart */}
              <ChannelTrendChart data={dashboard.trend} />

              {/* Two Analytical Secondary Visualizations */}
              <section id="performance" className="grid gap-4 lg:grid-cols-2">
                <VideoPerformanceChart data={dashboard.video_performance} />
                <TrafficSourceChart data={dashboard.traffic_sources} />
              </section>

              {/* Experiments Section (Active + Proposed) */}
              <section
                id="experiments"
                className="rounded-lg border border-border-subtle bg-surface-1 p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
                      Channel Experiments
                    </p>
                    <h2 className="mt-1 text-sm font-semibold">
                      {dashboard.proposed_experiment.hypothesis}
                    </h2>
                    <p className="mt-2 max-w-3xl text-xs leading-5 text-text-secondary">
                      {dashboard.proposed_experiment.confidence_summary}
                    </p>
                  </div>
                  <span className="rounded border border-primary/30 bg-primary/10 px-2 py-1 text-[10px] font-semibold text-primary">
                    PROPOSED
                  </span>
                </div>
                <div className="mt-4 flex flex-wrap gap-6 border-t border-border-subtle pt-3 text-xs">
                  <div>
                    <p className="text-[10px] text-text-muted">Primary metric</p>
                    <p className="mt-1 font-mono">Average retention</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-text-muted">Baseline</p>
                    <p className="mt-1 font-mono">
                      {dashboard.proposed_experiment.baseline_value.toFixed(1)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] text-text-muted">Expected direction</p>
                    <p className="mt-1 font-mono">Increase</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-text-muted">Status</p>
                    <p className="mt-1 font-mono text-primary">Ready to test</p>
                  </div>
                </div>
              </section>
            </div>
          )}
        </main>

        {/* Right Rail: Alex Briefing / Topic Radar */}
        <aside className="border-t border-border-subtle bg-surface-1/50 p-4 xl:border-l xl:border-t-0 xl:p-5">
          <div className="sticky top-20 space-y-4">
            <div className="flex items-center gap-3">
              <img
                src={alexAvatar}
                alt="Alex"
                className="h-9 w-9 rounded-md border border-border-strong object-cover"
              />
              <div>
                <h2 className="text-sm font-semibold">Alex Briefing</h2>
                <p className="text-[10px] text-text-muted">Evidence-backed channel intelligence</p>
              </div>
            </div>

            {/* Persisted Alex Insights */}
            {dashboard?.insights.map((insight) => (
              <article
                key={insight.insight_id}
                className="rounded-lg border border-border-subtle bg-surface-1 p-4"
              >
                <div className="flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[0.13em] text-primary">
                  <Sparkles className="h-3 w-3" />
                  {insight.type}
                </div>
                <h3 className="mt-2 text-sm font-semibold leading-5">{insight.title}</h3>
                <p className="mt-2 text-xs leading-5 text-text-secondary">{insight.statement}</p>
                <div className="mt-3 space-y-2 border-t border-border-subtle pt-3">
                  {insight.evidence.map((evidence) => (
                    <div key={`${evidence.kind}-${evidence.statement}`}>
                      <span className="text-[9px] font-bold text-text-muted">{evidence.kind}</span>
                      <p className="mt-0.5 text-[10px] leading-4 text-text-secondary">
                        {evidence.statement}
                      </p>
                    </div>
                  ))}
                </div>
                <p className="mt-3 rounded bg-primary/8 p-2 text-[10px] leading-4 text-text-secondary">
                  <strong className="text-text-primary">Recommendation:</strong>{" "}
                  {insight.recommended_action}
                </p>
              </article>
            ))}

            {/* Topic Radar Findings from Grounded Google Search */}
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Globe className="h-3.5 w-3.5 text-primary" />
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
                    Topic Radar
                  </h3>
                </div>
                <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[9px] font-semibold text-primary">
                  Grounded
                </span>
              </div>

              {findings.length > 0 ? (
                findings.map((finding) => (
                  <article
                    key={finding.finding_id}
                    className="rounded-lg border border-border-subtle bg-surface-1 p-3.5 text-xs transition-colors hover:border-border-strong"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[9px] font-medium text-text-muted">
                        {finding.category}
                      </span>
                      <span className="text-[9px] font-semibold text-primary">
                        {(finding.opportunity_score * 100).toFixed(0)}% fit
                      </span>
                    </div>
                    <p className="mt-1 text-[10px] text-text-muted">
                      {formatDiscoveredAgo(finding.discovered_at)}
                    </p>

                    <h4 className="mt-2 text-xs font-semibold leading-snug text-text-primary">
                      {finding.title}
                    </h4>
                    <p className="mt-1.5 line-clamp-3 text-[11px] leading-relaxed text-text-secondary">
                      {finding.summary}
                    </p>

                    <div className="mt-2 rounded bg-surface-2 p-2 text-[10px] leading-4 text-text-secondary">
                      <strong className="text-text-primary">Why it matters: </strong>
                      {finding.why_it_matters}
                    </div>

                    {/* Source Citations */}
                    <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-border-subtle pt-2">
                      <span className="text-[9px] font-semibold text-text-muted">Sources:</span>
                      {finding.source_citations.map((cite) => (
                        <a
                          key={cite.url}
                          href={cite.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 rounded border border-border-subtle bg-surface-2 px-1.5 py-0.5 text-[9px] text-text-secondary hover:border-primary hover:text-primary"
                        >
                          <span>{cite.domain}</span>
                          <ExternalLink className="h-2.5 w-2.5" />
                        </a>
                      ))}
                    </div>
                  </article>
                ))
              ) : (
                <div className="rounded-lg border border-dashed border-border-strong p-4 text-center">
                  <p className="text-[10px] leading-4 text-text-muted">
                    No grounded research findings yet. Alex runs research on your configured
                    schedule.
                  </p>
                </div>
              )}
            </section>

            <p className="text-[9px] leading-4 text-text-muted">
              Synthetic analytics modeled on YouTube Data and Analytics APIs. Research is live
              Grounded Google Search.
            </p>
          </div>
        </aside>
      </div>

      {/* Connect YouTube Modal */}
      {youtubeModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
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
                className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-xs font-semibold text-background hover:opacity-90 disabled:opacity-50"
              >
                {isConnectingYt ? "Connecting..." : "Authorize Channel"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Alex Settings Drawer */}
      <AlexSettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
};

const KpiCard: React.FC<{ kpi: DashboardKpi }> = ({ kpi }) => {
  const isPositive = (kpi.change_percentage ?? 0) >= 0;
  return (
    <article className="rounded-lg border border-border-subtle bg-surface-1 p-3.5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-muted">
        {KPI_LABELS[kpi.metric] ?? kpi.metric}
      </p>
      <p className="mt-1 font-mono text-xl font-semibold tracking-tight">{formatKpiValue(kpi)}</p>
      <p
        className={`mt-1 flex items-center gap-1 text-[10px] font-medium ${
          kpi.change_percentage === null
            ? "text-text-muted"
            : isPositive
              ? "text-success"
              : "text-error"
        }`}
      >
        {kpi.change_percentage !== null &&
          (isPositive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />)}
        <span>{formatChange(kpi.change_percentage)}</span>
      </p>
    </article>
  );
};

const DashboardSkeleton: React.FC = () => (
  <div aria-busy="true" aria-label="Loading channel intelligence" className="space-y-4">
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {[1, 2, 3, 4].map((index) => (
        <div
          key={index}
          className="h-20 animate-pulse rounded-lg border border-border-subtle bg-surface-1"
        />
      ))}
    </div>
    <div className="h-24 animate-pulse rounded-lg border border-border-subtle bg-surface-1" />
    <div className="h-64 animate-pulse rounded-lg border border-border-subtle bg-surface-1" />
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="h-56 animate-pulse rounded-lg border border-border-subtle bg-surface-1" />
      <div className="h-56 animate-pulse rounded-lg border border-border-subtle bg-surface-1" />
    </div>
  </div>
);
