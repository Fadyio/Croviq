import React from "react";
import { Sparkles, TrendingDown, TrendingUp } from "lucide-react";
import type { components } from "../../api/generated";
import { ChannelTrendChart } from "./ChannelTrendChart";
type ChannelDashboard = components["schemas"]["ChannelDashboard"];
type DashboardKpi = components["schemas"]["DashboardKpi"];

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
  const currentVal = kpi.current_value ?? (kpi as any).current ?? 0;
  if (kpi.metric === "average_retention") return `${Number(currentVal).toFixed(1)}%`;
  if (kpi.metric === "watch_time_hours") return `${compactNumber.format(Number(currentVal))} hours`;
  if (kpi.metric === "net_subscribers") {
    return `${Number(currentVal) >= 0 ? "+" : ""}${compactNumber.format(Number(currentVal))}`;
  }
  return compactNumber.format(Number(currentVal));
};

const formatChange = (value: number | null | undefined): string => {
  if (value === null || value === undefined || Number.isNaN(Number(value)))
    return "No comparable baseline";
  const num = Number(value);
  return `${num >= 0 ? "+" : ""}${num.toFixed(1)}% vs previous period`;
};

export const OverviewView: React.FC<OverviewViewProps> = ({
  dashboard,
  onNavigateToExperiments: _onNavigateToExperiments,
}) => {
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
            <KpiCell key={kpi.metric || (kpi as any).metric_name || idx} kpi={kpi} />
          ))}
        </section>
      </div>

      {/* Since Your Last Upload: Contextual Summary */}
      {dashboard.latest_video ? (
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
                  {(dashboard.latest_video.retention_percentage ?? 0).toFixed(1)}%{" "}
                  <span className="font-sans font-normal text-text-muted">retention</span>
                </span>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 lg:justify-end text-xs">
              <span className="rounded-lg bg-surface-2 px-2.5 py-1.5 font-medium text-text-secondary">
                <span className="font-semibold text-primary">
                  {(dashboard.latest_video.views_percentile ?? 50).toFixed(0)}th
                </span>{" "}
                views percentile
              </span>
              <span className="rounded-lg bg-surface-2 px-2.5 py-1.5 font-medium text-text-secondary">
                <span className="font-semibold text-primary">
                  {(dashboard.latest_video.retention_percentile ?? 50).toFixed(0)}th
                </span>{" "}
                retention percentile
              </span>
              <span className="rounded-lg bg-surface-2 px-2.5 py-1.5 font-medium text-text-secondary font-mono">
                {(dashboard.latest_video.subscriber_conversion_per_1k_views ?? 0).toFixed(1)}{" "}
                subs/1k views
              </span>
              <span className="rounded-lg bg-surface-3 px-2 py-1 text-[10px] text-text-muted">
                {dashboard.latest_video.comparison_window || "lifetime catalog baseline"}
              </span>
            </div>
          </div>
        </section>
      ) : null}

      {/* Dominant Trend Chart */}
      {dashboard.trend && dashboard.trend.length > 0 && (
        <ChannelTrendChart data={dashboard.trend} title="Channel Performance" compact={true} />
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
                  ? dashboard.insights[0].recommended_action.replace(/^ACTION:\s*/i, "")
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
  const changeVal = kpi.change_percentage ?? (kpi as any).delta_percentage ?? null;
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
          <span>{formatChange(changeVal)}</span>
        </p>
      </div>
    </article>
  );
};
