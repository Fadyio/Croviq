import React, { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  BarChart3,
  Beaker,
  Check,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Info,
  LayoutDashboard,
  LogOut,
  Plus,
  Radio,
  RefreshCw,
  Sparkles,
  TrendingDown,
  TrendingUp,
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
type Insight = components["schemas"]["ChannelInsight"];
type ChannelMode = "sample" | "youtube";
type DashboardTab = "overview" | "performance" | "experiments";

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
  if (kpi.metric === "watch_time_hours") return `${compactNumber.format(kpi.current_value)} hours`;
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
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");
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
  const [evidenceModalInsight, setEvidenceModalInsight] = useState<Insight | null>(null);
  const [openSourcesMap, setOpenSourcesMap] = useState<Record<string, boolean>>({});
  const selectorRef = useRef<HTMLDivElement>(null);
  const prefersReducedMotion = useReducedMotion();

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

  const toggleSources = (findingId: string) => {
    setOpenSourcesMap((prev) => ({ ...prev, [findingId]: !prev[findingId] }));
  };

  const scrollToSection = (tab: DashboardTab) => {
    setActiveTab(tab);
    if (tab === "performance") {
      document.getElementById("performance")?.scrollIntoView({ behavior: "smooth" });
    } else if (tab === "experiments") {
      document.getElementById("experiments")?.scrollIntoView({ behavior: "smooth" });
    } else {
      document.getElementById("overview")?.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <div className="min-h-screen bg-background text-text-primary">
      {/* 2. Top Navigation: Clean, minimal navbar */}
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-border-subtle bg-surface-1 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-5">
          <CroviqLogo height={24} className="h-6 w-auto shrink-0" />

          {/* 3. Channel Selector: Narrow, clean dropdown */}
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
                    ? "bg-red-500/20 text-red-400"
                    : "bg-primary/20 text-primary"
                }`}
              >
                {channelMode === "youtube" ? "YT" : "C"}
              </span>
              <span className="max-w-[140px] sm:max-w-[200px] truncate font-medium">
                {channelMode === "youtube" && youtubeConnection?.channel_title
                  ? youtubeConnection.channel_title
                  : "Croviq Sample Channel"}
              </span>
              <span className="rounded bg-surface-3 px-1.5 py-0.5 text-[9px] text-text-muted">
                {channelMode === "youtube" ? "Live" : "Sample"}
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
                      <span className="block font-medium">Croviq Sample Channel</span>
                      <span className="text-[10px] text-text-muted">Synthetic YouTube model</span>
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

        {/* Top Nav Right: Action + Alex Member + Account */}
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

          {/* Alex Team Member Chip */}
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            className="flex items-center gap-2 rounded-lg border border-border-subtle bg-surface-2/60 px-2.5 py-1 text-left transition-colors hover:border-border-strong hover:bg-surface-2"
            aria-label="Open Alex settings"
            title="Alex · Data Scientist"
          >
            <img
              src={alexAvatar}
              alt="Alex"
              className="h-6 w-6 rounded-full object-cover ring-1 ring-border-subtle"
            />
            <div className="hidden sm:block">
              <span className="block text-xs font-semibold leading-tight text-text-primary">
                Alex
              </span>
              <span className="block text-[10px] leading-tight text-text-muted">
                Data Scientist
              </span>
            </div>
          </button>

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

      {/* 1. Desktop Layout: Main Workspace + Alex Rail (NO Permanent Left Sidebar) */}
      <div className="mx-auto max-w-[1560px] px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_340px] 2xl:grid-cols-[minmax(0,1fr)_360px] gap-6 items-start">
          {/* Main Intelligence Workspace */}
          <main id="overview" className="min-w-0 space-y-6">
            {error && (
              <div
                role="alert"
                className="flex items-center justify-between rounded-xl border border-danger/30 bg-danger/10 p-3.5 text-xs text-danger"
              >
                <span>{error}</span>
                <button
                  type="button"
                  onClick={() => setRefreshKey((key) => key + 1)}
                  className="flex items-center gap-1.5 font-semibold text-danger hover:underline"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Retry
                </button>
              </div>
            )}

            {/* 4. Page Header: Strong, authoritative dashboard header */}
            <header className="space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2.5">
                    <h1 className="text-2xl font-bold tracking-tight text-text-primary">
                      {dashboard?.channel.title ?? "Modern AI Engineering"}
                    </h1>
                    <span className="rounded-full border border-border-subtle bg-surface-2 px-2 py-0.5 text-[10px] font-medium text-text-muted">
                      {channelMode === "youtube" ? "Connected YouTube" : "Sample channel"}
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

              {/* Compact Navigation Tabs */}
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle pb-3">
                <nav className="flex items-center gap-1" aria-label="Dashboard sections">
                  {[
                    { id: "overview", label: "Overview", icon: LayoutDashboard },
                    { id: "performance", label: "Performance", icon: BarChart3 },
                    { id: "experiments", label: "Experiments", icon: Beaker },
                  ].map((tab) => {
                    const Icon = tab.icon;
                    const isActive = activeTab === tab.id;
                    return (
                      <button
                        key={tab.id}
                        type="button"
                        onClick={() => scrollToSection(tab.id as DashboardTab)}
                        className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                          isActive
                            ? "bg-surface-2 text-text-primary font-semibold"
                            : "text-text-muted hover:bg-surface-2/50 hover:text-text-secondary"
                        }`}
                      >
                        <Icon className="h-3.5 w-3.5" />
                        <span>{tab.label}</span>
                      </button>
                    );
                  })}
                </nav>
              </div>
            </header>
            {isLoading || !dashboard ? (
              <DashboardSkeleton />
            ) : (
              <div className="space-y-6">
                {/* 5. KPI Hierarchy: Unified row container with section introduction */}
                <div className="space-y-2.5">
                  <h2 className="text-xs font-semibold tracking-tight text-text-secondary">
                    Here's what changed
                  </h2>
                  <section
                    className="grid grid-cols-2 lg:grid-cols-4 rounded-xl border border-border-subtle bg-surface-1 divide-y lg:divide-y-0 lg:divide-x divide-border-subtle shadow-sm"
                    aria-label="Channel KPIs"
                  >
                    {dashboard.kpis.map((kpi) => (
                      <KpiCell key={kpi.metric} kpi={kpi} />
                    ))}
                  </section>
                </div>
                {/* 8. Since Your Last Upload: Concise contextual summary */}
                <section
                  className="rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm"
                  aria-labelledby="latest-upload-title"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle pb-3">
                    <span className="text-xs font-semibold text-text-primary flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-primary" />
                      Since your last upload
                    </span>
                    <span className="text-[11px] text-text-muted">
                      Published{" "}
                      {new Date(dashboard.latest_video.published_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </span>
                  </div>

                  <div className="mt-3.5 grid gap-4 lg:grid-cols-[1.2fr_1fr] items-center">
                    <div>
                      <h2
                        id="latest-upload-title"
                        className="text-sm font-semibold text-text-primary line-clamp-1"
                      >
                        {dashboard.latest_video.title}
                      </h2>
                      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
                        <span className="font-mono font-semibold text-text-primary">
                          {compactNumber.format(dashboard.latest_video.views)}{" "}
                          <span className="font-sans font-normal text-text-muted">views</span>
                        </span>
                        <span className="text-border-strong">·</span>
                        <span className="font-mono font-semibold text-text-primary">
                          {dashboard.latest_video.net_subscribers >= 0 ? "+" : ""}
                          {dashboard.latest_video.net_subscribers}{" "}
                          <span className="font-sans font-normal text-text-muted">subscribers</span>
                        </span>
                        <span className="text-border-strong">·</span>
                        <span className="font-mono font-semibold text-text-primary">
                          {dashboard.latest_video.retention_percentage.toFixed(1)}%{" "}
                          <span className="font-sans font-normal text-text-muted">retention</span>
                        </span>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 lg:justify-end text-xs">
                      <span className="rounded-lg bg-surface-2 px-2.5 py-1.5 font-medium text-text-secondary">
                        <span
                          className={
                            dashboard.latest_video.view_delta_percentage >= 0
                              ? "text-success font-semibold"
                              : "text-danger font-semibold"
                          }
                        >
                          {dashboard.latest_video.view_delta_percentage >= 0 ? "+" : ""}
                          {dashboard.latest_video.view_delta_percentage.toFixed(1)}%
                        </span>{" "}
                        views vs channel median
                      </span>
                      <span className="rounded-lg bg-surface-2 px-2.5 py-1.5 font-medium text-text-secondary">
                        <span
                          className={
                            dashboard.latest_video.subscriber_conversion_delta_percentage >= 0
                              ? "text-success font-semibold"
                              : "text-danger font-semibold"
                          }
                        >
                          {dashboard.latest_video.subscriber_conversion_delta_percentage >= 0
                            ? "+"
                            : ""}
                          {dashboard.latest_video.subscriber_conversion_delta_percentage.toFixed(1)}
                          %
                        </span>{" "}
                        conversion
                      </span>
                    </div>
                  </div>
                </section>

                {/* 7. Dominant Primary Chart */}
                <ChannelTrendChart data={dashboard.trend} />

                {/* 13 & 14. Secondary Analytical Charts */}
                <section id="performance" className="grid gap-6 lg:grid-cols-2">
                  <VideoPerformanceChart data={dashboard.video_performance} />
                  <TrafficSourceChart data={dashboard.traffic_sources} />
                </section>

                {/* 15. Channel Experiment: Reduced vertical footprint */}
                <section
                  id="experiments"
                  className="rounded-xl border border-border-subtle bg-surface-1 p-4 sm:p-4.5 shadow-sm"
                  aria-labelledby="experiments-title"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Beaker className="h-3.5 w-3.5 text-primary" />
                      <h2
                        id="experiments-title"
                        className="text-xs font-semibold tracking-tight text-text-primary"
                      >
                        Channel Experiment
                      </h2>
                    </div>
                    <span className="rounded-full bg-primary/10 border border-primary/20 px-2 py-0.5 text-[10px] font-semibold text-primary">
                      {dashboard.proposed_experiment.status}
                    </span>
                  </div>

                  <p className="mt-2 text-xs font-normal text-text-secondary leading-relaxed">
                    <span className="font-semibold text-text-primary">Hypothesis: </span>
                    {dashboard.proposed_experiment.hypothesis}
                  </p>

                  <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2.5 rounded-lg bg-surface-2/60 p-2.5 text-xs border border-border-subtle">
                    <div>
                      <span className="text-[10px] text-text-muted block">Primary metric</span>
                      <span className="font-medium text-text-primary mt-0.5 block truncate">
                        Average retention
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-text-muted block">Baseline</span>
                      <span className="font-mono font-medium text-text-primary mt-0.5 block">
                        {dashboard.proposed_experiment.baseline_value.toFixed(1)}%
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-text-muted block">Expected direction</span>
                      <span className="font-medium text-success mt-0.5 block">Increase</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-text-muted block">Status</span>
                      <span className="font-medium text-primary mt-0.5 block">Ready to test</span>
                    </div>
                  </div>
                </section>
              </div>
            )}
          </main>

          {/* 9. Alex Rail: Sticky Primary Agent Data Scientist */}
          <aside className="space-y-6 xl:sticky xl:top-20 xl:self-start xl:max-h-[calc(100vh-6rem)] xl:overflow-y-auto">
            <div className="rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm space-y-5">
              {/* 9. Alex Header: Team Member identity */}
              <div className="flex items-center justify-between border-b border-border-subtle pb-4">
                <div className="flex items-center gap-3">
                  <img
                    src={alexAvatar}
                    alt="Alex"
                    className="h-10 w-10 rounded-full object-cover ring-2 ring-primary/20"
                  />
                  <div>
                    <h2 className="text-sm font-semibold text-text-primary">Alex</h2>
                    <p className="text-xs text-text-muted">Data Scientist</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setSettingsOpen(true)}
                  className="rounded-lg p-1.5 text-text-muted transition-colors hover:bg-surface-2 hover:text-text-primary"
                  title="Configure Alex settings & memory"
                  aria-label="Alex memory and settings"
                >
                  <Info className="h-4 w-4" />
                </button>
              </div>

              {/* 10. Natural Prose Alex Insights (Reduced Nesting) */}
              <div className="space-y-4">
                {dashboard?.insights.map((insight) => (
                  <article
                    key={insight.insight_id}
                    className="rounded-lg bg-surface-2/40 p-4 text-xs space-y-3"
                  >
                    <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
                      <TrendingUp className="h-3 w-3" />
                      <span>{insight.type}</span>
                    </div>

                    <h3 className="text-xs font-semibold leading-snug text-text-primary">
                      {insight.title}
                    </h3>

                    <p className="text-[11px] leading-relaxed text-text-secondary">
                      {insight.statement}
                    </p>

                    <div className="rounded-md border-l-2 border-primary/70 bg-surface-3/50 px-3 py-2 text-[11px] leading-relaxed">
                      <span className="font-semibold text-text-primary">Next: </span>
                      <span className="text-text-secondary">{insight.recommended_action}</span>
                    </div>

                    <div className="flex items-center justify-between pt-1 text-[10px] text-text-muted">
                      <span>Based on 100 videos</span>
                      <button
                        type="button"
                        onClick={() => setEvidenceModalInsight(insight)}
                        className="inline-flex items-center gap-1 text-primary hover:underline font-medium"
                      >
                        <span>View evidence</span>
                        <ChevronRight className="h-3 w-3" />
                      </button>
                    </div>
                  </article>
                ))}
              </div>
              {/* 11 & 12. Worth Watching / Topic Radar */}
              <div className="border-t border-border-subtle pt-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Radio className="h-3.5 w-3.5 text-primary" />
                    <h3 className="text-xs font-semibold text-text-primary">Worth watching</h3>
                  </div>
                  {findings.length > 0 && (
                    <span className="text-[10px] text-text-muted">{findings.length} findings</span>
                  )}
                </div>

                {findings.length > 0 ? (
                  <div className="space-y-3">
                    {findings.slice(0, 3).map((finding) => (
                      <motion.article
                        key={finding.finding_id}
                        initial={prefersReducedMotion ? false : { opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.2 }}
                        className="rounded-lg bg-surface-2/40 p-3.5 text-xs space-y-2"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="rounded bg-surface-3 px-1.5 py-0.5 text-[9px] font-medium text-text-muted">
                            {finding.category}
                          </span>
                          <span className="text-[10px] text-text-muted">
                            {formatDiscoveredAgo(finding.discovered_at)}
                          </span>
                        </div>

                        <h4 className="text-xs font-semibold leading-snug text-text-primary">
                          {finding.title}
                        </h4>

                        <div className="rounded border-l-2 border-border-strong bg-surface-3/40 px-2.5 py-1.5 text-[10px] leading-relaxed text-text-secondary">
                          <span className="font-semibold text-text-primary">Why it matters: </span>
                          <span>{finding.why_it_matters}</span>
                        </div>

                        {/* Citation Sources Pill & Popover */}
                        {finding.source_citations.length > 0 && (
                          <div className="pt-1">
                            <button
                              type="button"
                              onClick={() => toggleSources(finding.finding_id)}
                              className="inline-flex items-center gap-1 rounded bg-surface-3 px-2 py-0.5 text-[10px] font-medium text-text-secondary hover:text-text-primary transition-colors"
                            >
                              <span>Sources · {finding.source_citations.length}</span>
                              <ChevronDown
                                className={`h-2.5 w-2.5 transition-transform ${
                                  openSourcesMap[finding.finding_id] ? "rotate-180" : ""
                                }`}
                              />
                            </button>

                            {openSourcesMap[finding.finding_id] && (
                              <div className="mt-2 space-y-1 rounded-md bg-surface-1 p-2 border border-border-subtle">
                                {finding.source_citations.map((cite) => (
                                  <a
                                    key={cite.url}
                                    href={cite.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center justify-between rounded px-1.5 py-1 text-[10px] text-text-secondary hover:bg-surface-2 hover:text-primary transition-colors"
                                  >
                                    <span className="truncate max-w-[200px]">{cite.domain}</span>
                                    <ExternalLink className="h-2.5 w-2.5 shrink-0" />
                                  </a>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </motion.article>
                    ))}
                  </div>
                ) : (
                  /* 11. Compact Empty State: No giant box */
                  <div className="rounded-lg bg-surface-2/30 p-3 text-center border border-border-subtle/40">
                    <p className="text-[11px] text-text-muted">
                      Alex is monitoring AI engineering topics.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </aside>
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

      {/* Alex Settings Drawer */}
      <AlexSettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
};

const KpiCell: React.FC<{ kpi: DashboardKpi }> = ({ kpi }) => {
  const isPositive = (kpi.change_percentage ?? 0) >= 0;
  return (
    <article className="p-4 sm:p-5 flex flex-col justify-between">
      <p className="text-xs font-medium text-text-secondary">
        {KPI_LABELS[kpi.metric] ?? kpi.metric}
      </p>
      <div className="mt-2">
        <p className="font-mono text-2xl font-bold tracking-tight text-text-primary tabular-nums">
          {formatKpiValue(kpi)}
        </p>
        <p
          className={`mt-1.5 flex items-center gap-1 text-[11px] font-medium ${
            kpi.change_percentage === null
              ? "text-text-muted"
              : isPositive
                ? "text-success"
                : "text-danger"
          }`}
        >
          {kpi.change_percentage !== null &&
            (isPositive ? (
              <TrendingUp className="h-3 w-3" />
            ) : (
              <TrendingDown className="h-3 w-3" />
            ))}
          <span>{formatChange(kpi.change_percentage)}</span>
        </p>
      </div>
    </article>
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
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="h-64 animate-pulse rounded-xl border border-border-subtle bg-surface-1" />
      <div className="h-64 animate-pulse rounded-xl border border-border-subtle bg-surface-1" />
    </div>
  </div>
);
