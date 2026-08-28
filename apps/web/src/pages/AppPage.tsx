import React, { useCallback, useEffect, useState } from "react";
import {
  BarChart3,
  Beaker,
  BookOpen,
  ChevronDown,
  ExternalLink,
  LayoutDashboard,
  LogOut,
  Plus,
  RefreshCw,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Video,
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

export const AppPage: React.FC<AppPageProps> = ({ onNavigateNewProject }) => {
  const { user, firebaseUser, logout } = useAuth();
  const [period, setPeriod] = useState<28 | 90 | 365>(28);
  const [dashboard, setDashboard] = useState<ChannelDashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [youtubeNotice, setYoutubeNotice] = useState(false);

  const loadDashboard = useCallback(async () => {
    if (!firebaseUser) return;
    setIsLoading(true);
    setError(null);
    try {
      const token = await firebaseUser.getIdToken();
      const response = await fetch(`/api/channels/sample/dashboard?days=${period}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error("Channel intelligence could not be loaded");
      setDashboard((await response.json()) as ChannelDashboard);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Channel intelligence could not be loaded",
      );
    } finally {
      setIsLoading(false);
    }
  }, [firebaseUser, period]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard, refreshKey]);

  return (
    <div className="min-h-screen bg-background text-text-primary">
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-border-subtle bg-surface-1 px-4 lg:px-6">
        <div className="flex min-w-0 items-center gap-5">
          <CroviqLogo height={24} className="h-6 w-auto shrink-0" />
          <div className="relative hidden sm:block">
            <button
              type="button"
              className="flex min-w-48 items-center justify-between gap-3 rounded-md border border-border-subtle bg-background px-3 py-2 text-xs text-text-secondary hover:border-border-strong"
              aria-label="Select channel"
            >
              <span className="flex min-w-0 items-center gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded bg-primary/15 text-[9px] font-bold text-primary">
                  C
                </span>
                <span className="truncate">Croviq · Sample channel</span>
              </span>
              <ChevronDown className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2 sm:gap-3">
          <button
            type="button"
            onClick={onNavigateNewProject}
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

      <div className="mx-auto grid max-w-[1800px] grid-cols-1 xl:grid-cols-[168px_minmax(0,1fr)_310px]">
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
              <button
                type="button"
                onClick={() => setYoutubeNotice(true)}
                className="mt-2 flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs text-text-muted hover:bg-surface-2"
              >
                <Video className="h-3.5 w-3.5" />
                Connect YouTube
              </button>
            </div>
          </nav>
        </aside>

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
          {youtubeNotice && (
            <div
              role="status"
              className="mb-5 flex items-start justify-between gap-4 rounded-md border border-warning/30 bg-warning/10 p-3 text-xs text-text-secondary"
            >
              <div>
                <p className="font-semibold text-text-primary">
                  YouTube connection is not configured
                </p>
                <p className="mt-1">
                  An administrator must provision the server-side Google OAuth client before
                  connection can begin. Sample analytics remain isolated.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setYoutubeNotice(false)}
                className="text-text-muted"
              >
                Dismiss
              </button>
            </div>
          )}

          <section className="mb-5 flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-md border border-border-strong bg-surface-2 text-sm font-bold text-primary">
                C
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-lg font-semibold tracking-tight">
                    {dashboard?.channel.title ?? "Channel intelligence"}
                  </h1>
                  <span
                    className="rounded border border-border-subtle bg-surface-2 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-text-muted"
                    title="Synthetic analytics modeled on the YouTube Data and Analytics APIs"
                  >
                    Sample channel
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
              <section className="grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Channel KPIs">
                {dashboard.kpis.map((kpi) => (
                  <KpiCard key={kpi.metric} kpi={kpi} />
                ))}
              </section>
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
              <ChannelTrendChart data={dashboard.trend} />
              <section id="performance" className="grid gap-4 lg:grid-cols-2">
                <VideoPerformanceChart data={dashboard.video_performance} />
                <TrafficSourceChart data={dashboard.traffic_sources} />
              </section>
              <section
                id="experiments"
                className="rounded-lg border border-border-subtle bg-surface-1 p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
                      Proposed experiment
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
                </div>
              </section>
            </div>
          )}
        </main>

        <aside className="border-t border-border-subtle bg-surface-1/50 p-4 xl:border-l xl:border-t-0 xl:p-5">
          <div className="sticky top-20 space-y-4">
            <div className="flex items-center gap-3">
              <img
                src={alexAvatar}
                alt=""
                className="h-9 w-9 rounded-md border border-border-strong object-cover"
              />
              <div>
                <h2 className="text-sm font-semibold">Alex Briefing</h2>
                <p className="text-[10px] text-text-muted">Evidence-backed channel intelligence</p>
              </div>
            </div>
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
            <section className="rounded-lg border border-dashed border-border-strong p-4">
              <div className="flex items-center gap-2">
                <ExternalLink className="h-3.5 w-3.5 text-text-muted" />
                <h3 className="text-xs font-semibold">Topic Radar</h3>
              </div>
              <p className="mt-2 text-[10px] leading-4 text-text-muted">
                No grounded research findings yet. Alex will show opportunities here only after a
                real scheduled search completes with source citations.
              </p>
            </section>
            <p className="text-[9px] leading-4 text-text-muted">
              Sample daily trends are deterministically modeled from the canonical synthetic
              fixture. Research is never synthesized.
            </p>
          </div>
        </aside>
      </div>
      <AlexSettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
};

const KpiCard: React.FC<{ kpi: DashboardKpi }> = ({ kpi }) => {
  const change = kpi.change_percentage;
  const positive = change !== null && change >= 0;
  return (
    <article className="rounded-lg border border-border-subtle bg-surface-1 p-3.5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.13em] text-text-muted">
          {KPI_LABELS[kpi.metric] ?? kpi.metric}
        </p>
        {change !== null &&
          (positive ? (
            <TrendingUp className="h-3.5 w-3.5 text-success" />
          ) : (
            <TrendingDown className="h-3.5 w-3.5 text-error" />
          ))}
      </div>
      <p className="mt-3 font-mono text-xl font-semibold tracking-tight">{formatKpiValue(kpi)}</p>
      <p
        className={`mt-1 text-[10px] ${change === null ? "text-text-muted" : positive ? "text-success" : "text-error"}`}
      >
        {formatChange(change)}
      </p>
    </article>
  );
};

const DashboardSkeleton: React.FC = () => (
  <div aria-busy="true" aria-label="Loading channel intelligence" className="space-y-4">
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {Array.from({ length: 4 }, (_, index) => (
        <div
          key={index}
          className="h-24 animate-pulse rounded-lg border border-border-subtle bg-surface-1"
        />
      ))}
    </div>
    <div className="h-80 animate-pulse rounded-lg border border-border-subtle bg-surface-1" />
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="h-64 animate-pulse rounded-lg border border-border-subtle bg-surface-1" />
      <div className="h-64 animate-pulse rounded-lg border border-border-subtle bg-surface-1" />
    </div>
  </div>
);
