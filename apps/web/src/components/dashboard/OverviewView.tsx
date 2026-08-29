import React from "react";
import { ArrowRight, Beaker, TrendingDown, TrendingUp } from "lucide-react";
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

export const OverviewView: React.FC<OverviewViewProps> = ({
  dashboard,
  onNavigateToExperiments,
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
          {dashboard.kpis.map((kpi) => (
            <KpiCell key={kpi.metric} kpi={kpi} />
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
                  {dashboard.latest_video.subscriber_conversion_delta_percentage >= 0 ? "+" : ""}
                  {dashboard.latest_video.subscriber_conversion_delta_percentage.toFixed(1)}%
                </span>{" "}
                conversion
              </span>
            </div>
          </div>
        </section>
      ) : null}
      {/* Dominant Trend Chart */}
      {dashboard.trend && dashboard.trend.length > 0 && (
        <ChannelTrendChart data={dashboard.trend} title="Channel Performance" compact={true} />
      )}
      {dashboard.proposed_experiment && (
        <section
          className="rounded-xl border border-border-subtle bg-surface-1 p-4 sm:p-5 shadow-sm space-y-3"
          aria-labelledby="experiment-teaser-title"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Beaker className="h-4 w-4 text-primary" />
              <h2
                id="experiment-teaser-title"
                className="text-xs font-semibold tracking-tight text-text-primary uppercase tracking-wider"
              >
                Active Hypothesis & Experiment
              </h2>
            </div>
            <span className="rounded-full bg-primary/10 border border-primary/20 px-2 py-0.5 text-[10px] font-semibold text-primary">
              {dashboard.proposed_experiment.status}
            </span>
          </div>

          <p className="text-xs text-text-secondary leading-relaxed">
            <span className="font-semibold text-text-primary">Hypothesis: </span>
            {dashboard.proposed_experiment.hypothesis}
          </p>

          <div className="flex items-center justify-between pt-1 text-xs">
            <div className="flex items-center gap-4 text-text-muted text-[11px]">
              <span>
                Baseline:{" "}
                <span className="font-mono font-medium text-text-primary">
                  {dashboard.proposed_experiment.baseline_value.toFixed(1)}%
                </span>
              </span>
              <span>
                Target:{" "}
                <span className="font-medium text-success">
                  {dashboard.proposed_experiment.expected_direction}
                </span>
              </span>
            </div>
            {onNavigateToExperiments && (
              <button
                type="button"
                onClick={onNavigateToExperiments}
                className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
              >
                <span>Open Experiments</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </section>
      )}
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
