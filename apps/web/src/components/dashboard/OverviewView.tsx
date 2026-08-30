import { Sparkles, TrendingDown, TrendingUp } from "lucide-react";
import React from "react";
import type { components } from "../../api/generated";
import { ChannelTrendChart } from "./ChannelTrendChart";

type ChannelDashboard = components["schemas"]["ChannelDashboard"];
type DashboardKpi = components["schemas"]["DashboardKpi"];
type RecentVideoPerformance = components["schemas"]["RecentVideoPerformance"];

interface OverviewViewProps {
  dashboard: ChannelDashboard;
  onNavigateToExperiments?: () => void;
}

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
  const currentVal = kpi.current_value ?? 0;
  if (kpi.metric === "average_retention") return `${Number(currentVal).toFixed(1)}%`;
  if (kpi.metric === "watch_time_hours") return `${compactNumber.format(Number(currentVal))} hours`;
  if (kpi.metric === "net_subscribers") {
    return `${Number(currentVal) >= 0 ? "+" : ""}${compactNumber.format(Number(currentVal))}`;
  }
  return compactNumber.format(Number(currentVal));
};

const formatChange = (value: number | null | undefined, metric?: string): string => {
  if (value === null || value === undefined || Number.isNaN(Number(value)))
    return "No comparable baseline";
  const num = Number(value);
  const unit = metric === "average_retention" ? " pts" : "%";
  return `${num >= 0 ? "+" : ""}${num.toFixed(1)}${unit} vs previous period`;
};

const formatDeltaPercent = (
  value: number | null | undefined,
  label = "vs channel median",
): { text: string; isPositive: boolean; isNeutral: boolean } => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return { text: "Comparison unavailable", isPositive: false, isNeutral: true };
  }
  const num = Number(value);
  if (Math.abs(num) < 0.05) {
    return { text: `at channel median`, isPositive: false, isNeutral: true };
  }
  const symbol = num > 0 ? "↑" : "↓";
  const absVal = Math.abs(num);
  const formatted = absVal >= 10 ? absVal.toFixed(0) : absVal.toFixed(1);
  return {
    text: `${symbol} ${formatted}% ${label}`,
    isPositive: num > 0,
    isNeutral: false,
  };
};

const formatDeltaPoints = (
  value: number | null | undefined,
  label = "vs channel median",
): { text: string; isPositive: boolean; isNeutral: boolean } => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return { text: "Comparison unavailable", isPositive: false, isNeutral: true };
  }
  const num = Number(value);
  if (Math.abs(num) < 0.05) {
    return { text: `at channel median`, isPositive: false, isNeutral: true };
  }
  const symbol = num > 0 ? "↑" : "↓";
  return {
    text: `${symbol} ${Math.abs(num).toFixed(1)} pts ${label}`,
    isPositive: num > 0,
    isNeutral: false,
  };
};
export const OverviewView: React.FC<OverviewViewProps> = ({
  dashboard,
  onNavigateToExperiments: _onNavigateToExperiments,
}) => {
  const recentVideos: RecentVideoPerformance[] =
    dashboard.recent_videos && dashboard.recent_videos.length > 0
      ? dashboard.recent_videos
      : dashboard.latest_video
        ? [
            {
              video_id: dashboard.latest_video.video_id,
              title: dashboard.latest_video.title,
              published_at: String(dashboard.latest_video.published_at),
              views: dashboard.latest_video.views,
              views_delta_percentage: dashboard.latest_video.view_delta_percentage,
              average_retention: dashboard.latest_video.retention_percentage,
              retention_delta_points: dashboard.latest_video.retention_delta_points,
              ctr_percentage: dashboard.latest_video.ctr,
              ctr_delta_points: null,
              subscribers_gained: dashboard.latest_video.subscribers_gained,
              subscribers_lost: dashboard.latest_video.subscribers_lost ?? 0,
              net_subscribers: dashboard.latest_video.net_subscribers,
              subs_per_1k: dashboard.latest_video.subscriber_conversion_per_1k_views,
              subs_per_1k_delta_percentage:
                dashboard.latest_video.subscriber_conversion_delta_percentage,
              is_latest: true,
              alex_interpretation: null,
              alex_next_action: null,
            },
          ]
        : [];

  return (
    <div className="space-y-6">
      {/* 4 KPIs: Unified row container */}
      <div className="space-y-2.5">
        <h2 className="text-xs font-semibold tracking-tight text-text-secondary">
          Here's what changed
        </h2>
        <section
          className="grid grid-cols-2 lg:grid-cols-4 rounded-xl border border-border-subtle bg-surface-1 divide-y lg:divide-y-0 lg:divide-x divide-border-subtle shadow-sm"
          aria-label="Channel KPIs"
        >
          {dashboard.kpis.map((kpi, idx) => (
            <KpiCell key={kpi.metric || idx} kpi={kpi} />
          ))}
        </section>
      </div>

      {/* Recent Video Performance Section */}
      {recentVideos.length > 0 && (
        <section
          className="rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm space-y-4"
          aria-labelledby="recent-videos-title"
        >
          {/* Header */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle pb-3">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-primary" />
              <h2 id="recent-videos-title" className="text-xs font-semibold text-text-primary">
                Recent video performance
              </h2>
              <span className="text-[11px] text-text-muted">
                (Top {recentVideos.length} uploads)
              </span>
            </div>
            <span className="text-[11px] text-text-muted">
              {dashboard.channel_baselines?.sample_size
                ? `Compared with your channel's historical median (${dashboard.channel_baselines.sample_size} videos)`
                : "Compared with your channel's historical median"}
            </span>
          </div>

          {/* Videos List */}
          <div className="space-y-4 divide-y divide-border-subtle/40">
            {recentVideos.map((video, idx) => {
              const isLatest = video.is_latest ?? idx === 0;
              const viewsDelta = formatDeltaPercent(video.views_delta_percentage);
              const retDelta = formatDeltaPoints(video.retention_delta_points);
              const ctrDelta = formatDeltaPoints(video.ctr_delta_points);
              const subsDelta = formatDeltaPercent(video.subs_per_1k_delta_percentage);

              return (
                <article
                  key={video.video_id || idx}
                  className={`space-y-3 ${idx > 0 ? "pt-4" : ""}`}
                  data-testid={`recent-video-${video.video_id}`}
                >
                  {/* Title & Metadata Row */}
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0 max-w-[80%]">
                      {isLatest && (
                        <span className="rounded bg-primary/10 border border-primary/25 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-primary shrink-0">
                          Latest Upload
                        </span>
                      )}
                      <h3
                        className={`truncate font-medium text-text-primary ${
                          isLatest ? "text-sm font-semibold" : "text-xs"
                        }`}
                        title={video.title}
                      >
                        {video.title}
                      </h3>
                    </div>
                    <span className="text-[11px] text-text-muted shrink-0 font-mono">
                      {new Date(video.published_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </span>
                  </div>

                  {/* Metrics Row: Views, Retention, CTR, Subs/1K */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                    {/* Views */}
                    <div className="rounded-lg bg-surface-2/60 border border-border-subtle/50 p-2.5 flex flex-col justify-between">
                      <span className="text-[10px] font-medium text-text-muted uppercase tracking-wider">
                        Views
                      </span>
                      <div className="mt-1">
                        <span className="font-mono text-sm font-bold text-text-primary tabular-nums">
                          {compactNumber.format(video.views)}
                        </span>
                        <p
                          className={`mt-0.5 text-[10.5px] font-medium ${
                            viewsDelta.isNeutral
                              ? "text-text-muted"
                              : viewsDelta.isPositive
                                ? "text-success"
                                : "text-danger"
                          }`}
                        >
                          {viewsDelta.text}
                        </p>
                      </div>
                    </div>

                    {/* Retention */}
                    <div className="rounded-lg bg-surface-2/60 border border-border-subtle/50 p-2.5 flex flex-col justify-between">
                      <span className="text-[10px] font-medium text-text-muted uppercase tracking-wider">
                        Retention
                      </span>
                      <div className="mt-1">
                        <span className="font-mono text-sm font-bold text-text-primary tabular-nums">
                          {video.average_retention.toFixed(1)}%
                        </span>
                        <p
                          className={`mt-0.5 text-[10.5px] font-medium ${
                            retDelta.isNeutral
                              ? "text-text-muted"
                              : retDelta.isPositive
                                ? "text-success"
                                : "text-danger"
                          }`}
                        >
                          {retDelta.text}
                        </p>
                      </div>
                    </div>

                    {/* CTR */}
                    <div className="rounded-lg bg-surface-2/60 border border-border-subtle/50 p-2.5 flex flex-col justify-between">
                      <span className="text-[10px] font-medium text-text-muted uppercase tracking-wider">
                        Thumbnail CTR
                      </span>
                      <div className="mt-1">
                        <span className="font-mono text-sm font-bold text-text-primary tabular-nums">
                          {video.ctr_percentage != null
                            ? `${video.ctr_percentage.toFixed(1)}%`
                            : "Unavailable"}
                        </span>
                        <p
                          className={`mt-0.5 text-[10.5px] font-medium ${
                            ctrDelta.isNeutral
                              ? "text-text-muted"
                              : ctrDelta.isPositive
                                ? "text-success"
                                : "text-danger"
                          }`}
                        >
                          {video.ctr_percentage != null ? ctrDelta.text : "No CTR recorded"}
                        </p>
                      </div>
                    </div>

                    {/* Subs / 1K */}
                    <div className="rounded-lg bg-surface-2/60 border border-border-subtle/50 p-2.5 flex flex-col justify-between">
                      <span className="text-[10px] font-medium text-text-muted uppercase tracking-wider">
                        Subs / 1K views
                      </span>
                      <div className="mt-1">
                        <div className="flex items-baseline gap-1.5">
                          <span className="font-mono text-sm font-bold text-text-primary tabular-nums">
                            {video.subs_per_1k != null ? video.subs_per_1k.toFixed(1) : "—"}
                          </span>
                          <span className="text-[10px] font-mono text-text-muted">
                            ({video.net_subscribers >= 0 ? "+" : ""}
                            {video.net_subscribers} net)
                          </span>
                        </div>
                        <p
                          className={`mt-0.5 text-[10.5px] font-medium ${
                            subsDelta.isNeutral
                              ? "text-text-muted"
                              : subsDelta.isPositive
                                ? "text-success"
                                : "text-danger"
                          }`}
                        >
                          {subsDelta.text}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Actionable Signal for Latest Video Only */}
                  {isLatest && video.alex_interpretation && (
                    <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 text-xs space-y-1.5">
                      <div className="flex items-start gap-2">
                        <span className="font-bold text-primary shrink-0">Alex:</span>
                        <p className="text-text-secondary leading-relaxed font-medium">
                          "{video.alex_interpretation}"
                        </p>
                      </div>
                      {video.alex_next_action && (
                        <div className="flex items-start gap-2 pt-1 border-t border-primary/10">
                          <span className="font-bold text-emerald-400 shrink-0">Next:</span>
                          <p className="text-text-primary font-medium leading-relaxed">
                            "{video.alex_next_action}"
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </section>
      )}

      {/* Dominant Trend Chart */}
      {dashboard.trend && dashboard.trend.length > 0 && (
        <ChannelTrendChart
          data={dashboard.trend}
          kpis={dashboard.kpis}
          periodDays={dashboard.period_days}
          title="Channel Performance"
          compact={true}
        />
      )}

      {/* Alex Primary Insight */}
      {dashboard.insights && dashboard.insights.length > 0 && (
        <section
          className="rounded-xl border border-primary/20 bg-primary/5 p-5 shadow-sm space-y-3"
          aria-labelledby="alex-insight-title"
        >
          <div className="flex items-center justify-between gap-2 border-b border-primary/15 pb-2.5">
            <div className="flex items-center gap-2 text-xs font-semibold text-text-primary">
              <Sparkles className="h-4 w-4 text-primary" />
              <h2 id="alex-insight-title" className="tracking-tight">
                Alex Channel Insight · {dashboard.insights[0].title}
              </h2>
            </div>
          </div>

          <div className="space-y-2 text-xs">
            {dashboard.insights[0].evidence && dashboard.insights[0].evidence.length > 0 ? (
              dashboard.insights[0].evidence.map((ev, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  <span className="font-mono text-[10px] font-bold text-primary uppercase mt-0.5 shrink-0">
                    {ev.kind === "FACT" ? "MEASUREMENT" : "INTERPRETATION"}
                  </span>
                  <p className="text-text-secondary leading-relaxed">
                    {ev.statement
                      ? ev.statement.replace(/^(MEASUREMENT|INTERPRETATION):\s*/i, "")
                      : ""}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-text-secondary leading-relaxed">
                {dashboard.insights[0].statement}
              </p>
            )}
            <div className="flex items-start gap-2 pt-1 border-t border-primary/10">
              <span className="font-mono text-[10px] font-bold text-emerald-400 uppercase mt-0.5 shrink-0">
                ACTION
              </span>
              <p className="text-text-primary font-medium leading-relaxed">
                {dashboard.insights[0].recommended_action
                  ? dashboard.insights[0].recommended_action.replace(/^(ACTION:\s*|Next:\s*)/i, "")
                  : ""}
              </p>
            </div>
          </div>
        </section>
      )}
    </div>
  );
};

const KpiCell: React.FC<{ kpi: DashboardKpi }> = ({ kpi }) => {
  const changeVal = kpi.change_percentage ?? null;
  const isPositive = (changeVal ?? 0) >= 0;
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
            changeVal === null ? "text-text-muted" : isPositive ? "text-success" : "text-danger"
          }`}
        >
          {changeVal !== null &&
            (isPositive ? (
              <TrendingUp className="h-3 w-3" />
            ) : (
              <TrendingDown className="h-3 w-3" />
            ))}
          <span>{formatChange(changeVal, kpi.metric)}</span>
        </p>
      </div>
    </article>
  );
};
