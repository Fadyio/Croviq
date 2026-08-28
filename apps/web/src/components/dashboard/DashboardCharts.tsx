import React, { useMemo, useState } from "react";
import type { components } from "../../api/generated";

type TrendPoint = components["schemas"]["DashboardTrendPoint"];
type VideoPoint = components["schemas"]["VideoPerformancePoint"];
type TrafficSource = components["schemas"]["TrafficSourceMetric"];
type TrendMetric = "views" | "watch_time_hours" | "net_subscribers";

const compactNumber = new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: 1,
});
const dateLabel = (value: string): string =>
  new Intl.DateTimeFormat("en", { month: "short", day: "numeric", timeZone: "UTC" }).format(
    new Date(`${value}T00:00:00Z`),
  );

const linePath = (values: number[], width: number, height: number, maximum: number): string =>
  values
    .map((value, index) => {
      const x = values.length <= 1 ? 0 : (index / (values.length - 1)) * width;
      const y = height - (value / maximum) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

export const ChannelTrendChart: React.FC<{ data: TrendPoint[] }> = ({ data }) => {
  const [metric, setMetric] = useState<TrendMetric>("views");
  const currentValues = data.map((point) => point[metric]);
  const previousValues = data.map(
    (point) => point[`previous_${metric}` as keyof TrendPoint] as number,
  );
  const maximum = Math.max(1, ...currentValues, ...previousValues);
  const chartWidth = 800;
  const chartHeight = 220;
  const currentPath = linePath(currentValues, chartWidth, chartHeight, maximum);
  const previousPath = linePath(previousValues, chartWidth, chartHeight, maximum);
  const areaPath = `${currentPath} L${chartWidth},${chartHeight} L0,${chartHeight} Z`;

  return (
    <section
      className="rounded-lg border border-border-subtle bg-surface-1 p-4"
      aria-labelledby="trend-title"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
            Channel trend
          </p>
          <h2 id="trend-title" className="mt-1 text-sm font-semibold">
            {metric === "views"
              ? "Views"
              : metric === "watch_time_hours"
                ? "Watch time"
                : "Subscribers"}{" "}
            over time
          </h2>
        </div>
        <div
          className="flex rounded-md border border-border-subtle bg-background p-0.5"
          aria-label="Trend metric"
        >
          {(["views", "watch_time_hours", "net_subscribers"] as TrendMetric[]).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setMetric(option)}
              aria-pressed={metric === option}
              className={`rounded px-2.5 py-1 text-[11px] transition-colors ${metric === option ? "bg-surface-3 text-text-primary" : "text-text-muted hover:text-text-secondary"}`}
            >
              {option === "views"
                ? "Views"
                : option === "watch_time_hours"
                  ? "Watch time"
                  : "Subscribers"}
            </button>
          ))}
        </div>
      </div>
      <div
        className="relative h-64 w-full overflow-hidden"
        role="img"
        aria-label="Current and previous period channel trend"
      >
        <svg
          viewBox={`-42 -12 ${chartWidth + 54} ${chartHeight + 38}`}
          preserveAspectRatio="none"
          className="h-full w-full"
          aria-hidden="true"
        >
          {[0, 0.25, 0.5, 0.75, 1].map((fraction) => (
            <line
              key={fraction}
              x1="0"
              x2={chartWidth}
              y1={chartHeight * fraction}
              y2={chartHeight * fraction}
              stroke="var(--color-border-subtle)"
              strokeDasharray="3 5"
              vectorEffect="non-scaling-stroke"
            />
          ))}
          <path d={areaPath} fill="var(--color-primary)" fillOpacity="0.08" />
          <path
            d={previousPath}
            fill="none"
            stroke="var(--color-text-muted)"
            strokeDasharray="5 5"
            strokeWidth="1.25"
            vectorEffect="non-scaling-stroke"
          />
          <path
            d={currentPath}
            fill="none"
            stroke="var(--color-primary)"
            strokeWidth="2"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-between text-[10px] text-text-muted">
          <span>{data[0] ? dateLabel(data[0].date) : ""}</span>
          <span>{data.at(-1) ? dateLabel(data.at(-1)!.date) : ""}</span>
        </div>
        <div className="pointer-events-none absolute right-1 top-1 flex gap-3 text-[10px] text-text-muted">
          <span className="before:mr-1 before:inline-block before:h-0.5 before:w-3 before:bg-primary">
            Current
          </span>
          <span className="before:mr-1 before:inline-block before:w-3 before:border-t before:border-dashed before:border-text-muted">
            Previous
          </span>
        </div>
      </div>
    </section>
  );
};

export const VideoPerformanceChart: React.FC<{ data: VideoPoint[] }> = ({ data }) => {
  const [focused, setFocused] = useState<VideoPoint | null>(null);
  const discoveryLabel = data[0]?.discovery_metric ?? "Thumbnail CTR";
  const bounds = useMemo(
    () => ({
      minX: Math.min(...data.map((point) => point.discovery_value ?? point.ctr_percentage ?? 0), 0),
      maxX: Math.max(...data.map((point) => point.discovery_value ?? point.ctr_percentage ?? 0), 1),
      minY: Math.min(...data.map((point) => point.average_retention), 0),
      maxY: Math.max(...data.map((point) => point.average_retention), 1),
      maxViews: Math.max(...data.map((point) => point.views), 1),
    }),
    [data],
  );
  const width = 520;
  const height = 210;
  const xFor = (value: number) =>
    ((value - bounds.minX) / Math.max(1, bounds.maxX - bounds.minX)) * width;
  const yFor = (value: number) =>
    height - ((value - bounds.minY) / Math.max(1, bounds.maxY - bounds.minY)) * height;

  return (
    <section
      className="relative rounded-lg border border-border-subtle bg-surface-1 p-4"
      aria-labelledby="performance-title"
    >
      <div className="mb-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
          Discovery × retention
        </p>
        <h2 id="performance-title" className="mt-1 text-sm font-semibold">
          Video performance map
        </h2>
      </div>
      <div className="h-56">
        <svg
          viewBox={`-34 -8 ${width + 45} ${height + 34}`}
          className="h-full w-full"
          role="img"
          aria-label="Video discovery compared with average retention; bubble size represents views"
        >
          {[0, 0.25, 0.5, 0.75, 1].map((fraction) => (
            <React.Fragment key={fraction}>
              <line
                x1={width * fraction}
                x2={width * fraction}
                y1="0"
                y2={height}
                stroke="var(--color-border-subtle)"
                strokeDasharray="3 5"
              />
              <line
                x1="0"
                x2={width}
                y1={height * fraction}
                y2={height * fraction}
                stroke="var(--color-border-subtle)"
                strokeDasharray="3 5"
              />
            </React.Fragment>
          ))}
          {data.map((point) => {
            const discoveryVal = point.discovery_value ?? point.ctr_percentage ?? 0;
            const radius = 2.5 + Math.sqrt(point.views / bounds.maxViews) * 7;
            const metricText =
              point.ctr_percentage != null
                ? `${point.ctr_percentage.toFixed(1)}% CTR`
                : `${point.discovery_metric || "Discovery"}: ${discoveryVal.toFixed(1)}`;
            const label = `${point.title}: ${compactNumber.format(point.views)} views, ${metricText}, ${point.average_retention.toFixed(1)}% retention, +${point.subscribers_gained} subscribers`;
            return (
              <circle
                key={point.video_id}
                cx={xFor(discoveryVal)}
                cy={yFor(point.average_retention)}
                r={radius}
                fill="var(--color-primary)"
                fillOpacity="0.55"
                stroke="var(--color-primary)"
                strokeWidth="0.8"
                tabIndex={0}
                aria-label={label}
                onFocus={() => setFocused(point)}
                onBlur={() => setFocused(null)}
                onMouseEnter={() => setFocused(point)}
                onMouseLeave={() => setFocused(null)}
              >
                <title>{label}</title>
              </circle>
            );
          })}
          <text
            x={width / 2}
            y={height + 28}
            textAnchor="middle"
            fill="var(--color-text-muted)"
            fontSize="10"
          >
            {discoveryLabel}
          </text>
          <text
            x={-height / 2}
            y="-25"
            transform="rotate(-90)"
            textAnchor="middle"
            fill="var(--color-text-muted)"
            fontSize="10"
          >
            Average retention
          </text>
        </svg>
      </div>
      {focused && (
        <div className="pointer-events-none absolute right-4 top-14 z-10 max-w-64 rounded-md border border-border-strong bg-surface-2 p-3 text-[11px] shadow-xl">
          <p className="font-medium text-text-primary">{focused.title}</p>
          <p className="mt-1 text-text-secondary">
            {compactNumber.format(focused.views)} views ·{" "}
            {focused.ctr_percentage != null
              ? `${focused.ctr_percentage.toFixed(1)}% CTR`
              : `${focused.discovery_metric || "Discovery"}: ${(focused.discovery_value ?? 0).toFixed(1)}`}{" "}
            · {focused.average_retention.toFixed(1)}% retention · +{focused.subscribers_gained}{" "}
            subscribers
          </p>
        </div>
      )}
    </section>
  );
};

export const TrafficSourceChart: React.FC<{ data: TrafficSource[] }> = ({ data }) => {
  const rows = useMemo(
    () => [...data].sort((a, b) => b.percentage - a.percentage).slice(0, 5),
    [data],
  );
  return (
    <section
      className="rounded-lg border border-border-subtle bg-surface-1 p-4"
      aria-labelledby="traffic-title"
    >
      <div className="mb-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
          How viewers find you
        </p>
        <h2 id="traffic-title" className="mt-1 text-sm font-semibold">
          Traffic sources
        </h2>
      </div>
      <div className="space-y-3">
        {rows.map((source) => (
          <div key={source.source} title={`${source.views.toLocaleString()} views`}>
            <div className="mb-1.5 flex justify-between gap-3 text-[11px]">
              <span className="capitalize text-text-secondary">
                {source.source.replaceAll("_", " ")}
              </span>
              <span className="font-mono text-text-primary">{source.percentage.toFixed(1)}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-sm bg-surface-3">
              <div
                className="h-full bg-primary"
                style={{ width: `${Math.min(100, source.percentage)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};
