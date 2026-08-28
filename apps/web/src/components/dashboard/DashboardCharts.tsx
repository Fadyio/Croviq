import React, { useMemo, useRef, useState } from "react";
import type { components } from "../../api/generated";

type TrendPoint = components["schemas"]["DashboardTrendPoint"];
type VideoPoint = components["schemas"]["VideoPerformancePoint"];
type TrafficSource = components["schemas"]["TrafficSourceMetric"];
type TrendMetric = "views" | "watch_time_hours" | "net_subscribers";

const compactNumber = new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const standardNumber = new Intl.NumberFormat("en", {
  maximumFractionDigits: 1,
});

const dateLabel = (value: string): string =>
  new Intl.DateTimeFormat("en", { month: "short", day: "numeric", timeZone: "UTC" }).format(
    new Date(`${value}T00:00:00Z`),
  );

const fullDateLabel = (value: string): string =>
  new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));

const formatMetricValue = (metric: TrendMetric, value: number): string => {
  if (metric === "views") return compactNumber.format(value);
  if (metric === "watch_time_hours") return `${compactNumber.format(value)}h`;
  if (metric === "net_subscribers") return `${value >= 0 ? "+" : ""}${compactNumber.format(value)}`;
  return compactNumber.format(value);
};

const formatMetricFullValue = (metric: TrendMetric, value: number): string => {
  if (metric === "views") return `${standardNumber.format(value)} views`;
  if (metric === "watch_time_hours") return `${value.toFixed(1)} hours`;
  if (metric === "net_subscribers") return `${value >= 0 ? "+" : ""}${value} subscribers`;
  return String(value);
};

const linePath = (
  values: number[],
  paddingLeft: number,
  paddingRight: number,
  paddingTop: number,
  height: number,
  maximum: number,
): string => {
  const width = 800 - paddingLeft - paddingRight;
  return values
    .map((value, index) => {
      const x = paddingLeft + (values.length <= 1 ? 0 : (index / (values.length - 1)) * width);
      const y = paddingTop + height - (Math.max(0, value) / maximum) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
};

export const ChannelTrendChart: React.FC<{ data: TrendPoint[] }> = ({ data }) => {
  const [metric, setMetric] = useState<TrendMetric>("views");
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const currentValues = useMemo(() => data.map((point) => point[metric] ?? 0), [data, metric]);
  const previousValues = useMemo(
    () => data.map((point) => (point[`previous_${metric}` as keyof TrendPoint] as number) ?? 0),
    [data, metric],
  );

  const rawMax = Math.max(1, ...currentValues, ...previousValues);
  // Round maximum to a nice clean number for ticks
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawMax)));
  const normalized = rawMax / magnitude;
  let niceMax = rawMax;
  if (normalized <= 1.2) niceMax = 1.2 * magnitude;
  else if (normalized <= 2) niceMax = 2 * magnitude;
  else if (normalized <= 5) niceMax = 5 * magnitude;
  else niceMax = 10 * magnitude;

  const chartWidth = 800;
  const paddingLeft = 56;
  const paddingRight = 16;
  const paddingTop = 16;
  const plotHeight = 180;
  const plotWidth = chartWidth - paddingLeft - paddingRight;

  const currentPath = linePath(
    currentValues,
    paddingLeft,
    paddingRight,
    paddingTop,
    plotHeight,
    niceMax,
  );
  const previousPath = linePath(
    previousValues,
    paddingLeft,
    paddingRight,
    paddingTop,
    plotHeight,
    niceMax,
  );
  const areaPath = `${currentPath} L${paddingLeft + plotWidth},${paddingTop + plotHeight} L${paddingLeft},${paddingTop + plotHeight} Z`;

  // Generate 4 Y-axis tick values
  const yTicks = [1, 0.66, 0.33, 0].map((frac) => ({
    fraction: frac,
    value: niceMax * frac,
    y: paddingTop + plotHeight * (1 - frac),
  }));

  // Generate 5-6 date ticks
  const xTicks = useMemo(() => {
    if (data.length <= 1) return [];
    const count = Math.min(6, data.length);
    const step = (data.length - 1) / (count - 1);
    const ticks = [];
    for (let i = 0; i < count; i++) {
      const idx = Math.round(i * step);
      const point = data[idx];
      if (point) {
        ticks.push({
          index: idx,
          date: point.date,
          x: paddingLeft + (idx / (data.length - 1)) * plotWidth,
        });
      }
    }
    return ticks;
  }, [data, paddingLeft, plotWidth]);

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!data.length) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const relX = clientX / rect.width;
    const svgX = relX * chartWidth;
    if (svgX < paddingLeft || svgX > paddingLeft + plotWidth) {
      setHoverIndex(null);
      return;
    }
    const ratio = (svgX - paddingLeft) / plotWidth;
    const index = Math.min(data.length - 1, Math.max(0, Math.round(ratio * (data.length - 1))));
    setHoverIndex(index);
  };

  const hoveredPoint = hoverIndex !== null ? data[hoverIndex] : null;
  const hoveredCurrent = hoverIndex !== null ? currentValues[hoverIndex] : null;
  const hoveredPrevious = hoverIndex !== null ? previousValues[hoverIndex] : null;
  const hoveredDelta =
    hoveredCurrent !== null && hoveredPrevious !== null && hoveredPrevious > 0
      ? ((hoveredCurrent - hoveredPrevious) / hoveredPrevious) * 100
      : null;

  const hoveredX =
    hoverIndex !== null && data.length > 1
      ? paddingLeft + (hoverIndex / (data.length - 1)) * plotWidth
      : 0;
  const hoveredCurrentY =
    hoveredCurrent !== null ? paddingTop + plotHeight - (hoveredCurrent / niceMax) * plotHeight : 0;
  const hoveredPrevY =
    hoveredPrevious !== null
      ? paddingTop + plotHeight - (hoveredPrevious / niceMax) * plotHeight
      : 0;

  return (
    <section
      className="rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm"
      aria-labelledby="trend-title"
    >
      {/* Header with Title and Integrated Metric Switcher */}
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 id="trend-title" className="text-sm font-semibold tracking-tight text-text-primary">
            Channel Performance
          </h2>
          <p className="mt-0.5 text-xs text-text-muted">
            {metric === "views"
              ? "Daily views compared to previous 28-day baseline"
              : metric === "watch_time_hours"
                ? "Total watch time hours compared to previous period"
                : "Net subscriber gain and conversion trends"}
          </p>
        </div>

        <div className="flex items-center gap-4">
          {/* Legend */}
          <div className="hidden sm:flex items-center gap-3 text-[11px] text-text-muted">
            <span className="inline-flex items-center gap-1.5 font-medium text-text-secondary">
              <span className="h-2 w-2 rounded-full bg-primary" />
              Current
            </span>
            <span className="inline-flex items-center gap-1.5 font-medium text-text-muted">
              <span className="h-0.5 w-3 border-t border-dashed border-text-muted" />
              Previous period
            </span>
          </div>

          {/* Metric Switcher */}
          <div
            className="inline-flex rounded-lg border border-border-subtle bg-surface-2 p-0.5"
            role="tablist"
            aria-label="Trend metric"
          >
            {(
              [
                { id: "views", label: "Views" },
                { id: "watch_time_hours", label: "Watch time" },
                { id: "net_subscribers", label: "Subscribers" },
              ] as const
            ).map((opt) => (
              <button
                key={opt.id}
                type="button"
                role="tab"
                aria-selected={metric === opt.id}
                onClick={() => setMetric(opt.id)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                  metric === opt.id
                    ? "bg-surface-1 text-text-primary shadow-sm"
                    : "text-text-muted hover:text-text-secondary"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* SVG Chart Area */}
      <div
        ref={containerRef}
        className="relative h-64 sm:h-72 w-full select-none"
        role="img"
        aria-label="Channel trend chart over time"
      >
        <svg
          viewBox={`0 0 ${chartWidth} ${paddingTop + plotHeight + 32}`}
          preserveAspectRatio="none"
          className="h-full w-full overflow-visible"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoverIndex(null)}
        >
          <defs>
            <linearGradient id="primaryAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-primary)" stopOpacity="0.18" />
              <stop offset="100%" stopColor="var(--color-primary)" stopOpacity="0.00" />
            </linearGradient>
          </defs>

          {/* Horizontal Gridlines & Y-Axis Labels */}
          {yTicks.map((tick) => (
            <g key={tick.fraction}>
              <line
                x1={paddingLeft}
                x2={paddingLeft + plotWidth}
                y1={tick.y}
                y2={tick.y}
                stroke="var(--color-border-subtle)"
                strokeDasharray="2 4"
                strokeWidth="1"
                vectorEffect="non-scaling-stroke"
              />
              <text
                x={paddingLeft - 8}
                y={tick.y + 3.5}
                textAnchor="end"
                fill="var(--color-text-muted)"
                fontSize="10"
                className="font-mono"
              >
                {formatMetricValue(metric, tick.value)}
              </text>
            </g>
          ))}

          {/* Area Fill */}
          <path d={areaPath} fill="url(#primaryAreaGrad)" />

          {/* Previous Period Line (Dashed) */}
          <path
            d={previousPath}
            fill="none"
            stroke="var(--color-text-muted)"
            strokeDasharray="4 4"
            strokeWidth="1.5"
            vectorEffect="non-scaling-stroke"
          />

          {/* Current Period Line (Solid Vibrant) */}
          <path
            d={currentPath}
            fill="none"
            stroke="var(--color-primary)"
            strokeWidth="2.25"
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />

          {/* X-Axis Date Labels */}
          {xTicks.map((tick) => (
            <text
              key={tick.date}
              x={tick.x}
              y={paddingTop + plotHeight + 20}
              textAnchor="middle"
              fill="var(--color-text-muted)"
              fontSize="10"
              className="font-sans"
            >
              {dateLabel(tick.date)}
            </text>
          ))}

          {/* Hover Crosshair and Dots */}
          {hoverIndex !== null && hoveredPoint && (
            <g className="pointer-events-none">
              <line
                x1={hoveredX}
                x2={hoveredX}
                y1={paddingTop}
                y2={paddingTop + plotHeight}
                stroke="var(--color-border-strong)"
                strokeWidth="1"
                strokeDasharray="2 2"
                vectorEffect="non-scaling-stroke"
              />
              {/* Previous Dot */}
              <circle
                cx={hoveredX}
                cy={hoveredPrevY}
                r="3.5"
                fill="var(--color-surface-1)"
                stroke="var(--color-text-muted)"
                strokeWidth="1.5"
              />
              {/* Current Dot */}
              <circle
                cx={hoveredX}
                cy={hoveredCurrentY}
                r="5"
                fill="var(--color-primary)"
                stroke="var(--color-surface-1)"
                strokeWidth="2"
              />
            </g>
          )}
        </svg>

        {/* Hover Tooltip Overlay */}
        {hoverIndex !== null && hoveredPoint && (
          <div
            className="pointer-events-none absolute z-20 rounded-lg border border-border-strong bg-surface-2/95 px-3 py-2.5 shadow-xl backdrop-blur-sm transition-transform duration-75 text-xs"
            style={{
              left: `${Math.min(Math.max(hoveredX / 8, 12), 88)}%`,
              top: "12px",
              transform: "translateX(-50%)",
            }}
          >
            <p className="font-semibold text-text-primary">{fullDateLabel(hoveredPoint.date)}</p>
            <div className="mt-1.5 space-y-1">
              <div className="flex items-center justify-between gap-4">
                <span className="flex items-center gap-1.5 text-text-secondary">
                  <span className="h-2 w-2 rounded-full bg-primary" />
                  Current:
                </span>
                <span className="font-mono font-semibold text-text-primary">
                  {formatMetricFullValue(metric, hoveredCurrent ?? 0)}
                </span>
              </div>
              <div className="flex items-center justify-between gap-4 text-text-muted">
                <span className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-text-muted" />
                  Previous:
                </span>
                <span className="font-mono">
                  {formatMetricFullValue(metric, hoveredPrevious ?? 0)}
                </span>
              </div>
              {hoveredDelta !== null && (
                <div className="pt-1 border-t border-border-subtle flex items-center justify-between gap-4 text-[11px]">
                  <span className="text-text-muted">Change:</span>
                  <span
                    className={`font-semibold ${
                      hoveredDelta >= 0 ? "text-success" : "text-danger"
                    }`}
                  >
                    {hoveredDelta >= 0 ? "+" : ""}
                    {hoveredDelta.toFixed(1)}%
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

export const VideoPerformanceChart: React.FC<{ data: VideoPoint[] }> = ({ data }) => {
  const [focused, setFocused] = useState<VideoPoint | null>(null);

  const bounds = useMemo(() => {
    const ctrs = data.map((p) => p.discovery_value ?? p.ctr_percentage ?? 0);
    const retentions = data.map((p) => p.average_retention ?? 0);
    const views = data.map((p) => p.views ?? 0);
    return {
      minX: 0,
      maxX: Math.max(Math.ceil(Math.max(...ctrs, 8)), 10),
      minY: 0,
      maxY: Math.max(Math.ceil(Math.max(...retentions, 60)), 100),
      maxViews: Math.max(...views, 1),
    };
  }, [data]);

  const width = 500;
  const height = 200;
  const paddingLeft = 36;
  const paddingBottom = 28;
  const plotW = width - paddingLeft;
  const plotH = height - paddingBottom;

  const xFor = (value: number) => paddingLeft + (value / bounds.maxX) * plotW;
  const yFor = (value: number) => plotH - (value / bounds.maxY) * plotH;

  return (
    <section
      className="relative rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm"
      aria-labelledby="performance-title"
    >
      <div className="mb-4">
        <h2
          id="performance-title"
          className="text-sm font-semibold tracking-tight text-text-primary"
        >
          Video performance map
        </h2>
        <p className="mt-0.5 text-xs text-text-muted">
          Thumbnail CTR vs average retention (bubble size represents views)
        </p>
      </div>

      <div className="h-56 relative">
        <svg
          viewBox={`0 0 ${width + 10} ${height + 10}`}
          className="h-full w-full overflow-visible"
          role="img"
          aria-label="Video discovery compared with average retention; bubble size represents views"
        >
          {/* Grid lines and tick labels */}
          {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
            const yVal = bounds.maxY * fraction;
            const yPos = yFor(yVal);
            return (
              <g key={`y-${fraction}`}>
                <line
                  x1={paddingLeft}
                  x2={width}
                  y1={yPos}
                  y2={yPos}
                  stroke="var(--color-border-subtle)"
                  strokeDasharray="2 4"
                  strokeWidth="1"
                />
                <text
                  x={paddingLeft - 6}
                  y={yPos + 3.5}
                  textAnchor="end"
                  fill="var(--color-text-muted)"
                  fontSize="9"
                  className="font-mono"
                >
                  {Math.round(yVal)}%
                </text>
              </g>
            );
          })}

          {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
            const xVal = bounds.maxX * fraction;
            const xPos = xFor(xVal);
            return (
              <g key={`x-${fraction}`}>
                <line
                  x1={xPos}
                  x2={xPos}
                  y1={0}
                  y2={plotH}
                  stroke="var(--color-border-subtle)"
                  strokeDasharray="2 4"
                  strokeWidth="1"
                />
                <text
                  x={xPos}
                  y={plotH + 14}
                  textAnchor="middle"
                  fill="var(--color-text-muted)"
                  fontSize="9"
                  className="font-mono"
                >
                  {Math.round(xVal)}%
                </text>
              </g>
            );
          })}

          {/* Scatter Bubbles */}
          {data.map((point) => {
            const discoveryVal = point.discovery_value ?? point.ctr_percentage ?? 0;
            const radius = 3.5 + Math.sqrt(point.views / bounds.maxViews) * 6.5;
            const label = `${point.title}: ${compactNumber.format(point.views)} views, ${discoveryVal.toFixed(1)}% CTR, ${point.average_retention.toFixed(1)}% retention`;
            const isHovered = focused?.video_id === point.video_id;

            return (
              <circle
                key={point.video_id}
                cx={xFor(discoveryVal)}
                cy={yFor(point.average_retention)}
                r={isHovered ? radius + 2 : radius}
                fill="var(--color-primary)"
                fillOpacity={isHovered ? 0.9 : 0.6}
                stroke={isHovered ? "var(--color-text-primary)" : "var(--color-primary)"}
                strokeWidth={isHovered ? "2" : "1"}
                tabIndex={0}
                aria-label={label}
                className="cursor-pointer transition-all"
                onFocus={() => setFocused(point)}
                onBlur={() => setFocused(null)}
                onMouseEnter={() => setFocused(point)}
                onMouseLeave={() => setFocused(null)}
              >
                <title>{label}</title>
              </circle>
            );
          })}

          {/* Axis Titles */}
          <text
            x={paddingLeft + plotW / 2}
            y={height + 6}
            textAnchor="middle"
            fill="var(--color-text-secondary)"
            fontSize="10"
            className="font-medium"
          >
            Thumbnail CTR
          </text>
          <text
            x={-plotH / 2}
            y="12"
            transform="rotate(-90)"
            textAnchor="middle"
            fill="var(--color-text-secondary)"
            fontSize="10"
            className="font-medium"
          >
            Average retention
          </text>
        </svg>

        {/* Focused Video Tooltip */}
        {focused && (
          <div className="pointer-events-none absolute left-1/2 top-3 z-10 -translate-x-1/2 max-w-xs rounded-lg border border-border-strong bg-surface-2 p-3 text-xs shadow-xl backdrop-blur-sm">
            <p className="font-semibold text-text-primary line-clamp-1">{focused.title}</p>
            <div className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
              <span className="text-text-muted">Views:</span>
              <span className="font-mono text-text-primary text-right font-medium">
                {compactNumber.format(focused.views)}
              </span>
              <span className="text-text-muted">Thumbnail CTR:</span>
              <span className="font-mono text-text-primary text-right font-medium">
                {(focused.ctr_percentage ?? focused.discovery_value ?? 0).toFixed(1)}%
              </span>
              <span className="text-text-muted">Avg Retention:</span>
              <span className="font-mono text-text-primary text-right font-medium">
                {focused.average_retention.toFixed(1)}%
              </span>
              <span className="text-text-muted">Net Subscribers:</span>
              <span className="font-mono text-text-primary text-right font-medium">
                +{focused.subscribers_gained}
              </span>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

export const TrafficSourceChart: React.FC<{ data: TrafficSource[] }> = ({ data }) => {
  const rows = useMemo(
    () => [...data].sort((a, b) => b.percentage - a.percentage).slice(0, 5),
    [data],
  );

  const formatSourceName = (source: string): string => {
    const map: Record<string, string> = {
      suggested_videos: "Suggested videos",
      youtube_search: "YouTube search",
      browse_features: "Browse features",
      external: "External",
      direct_or_other: "Direct or other",
    };
    return map[source] || source.replaceAll("_", " ");
  };

  return (
    <section
      className="rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm"
      aria-labelledby="traffic-title"
    >
      <div className="mb-4">
        <h2 id="traffic-title" className="text-sm font-semibold tracking-tight text-text-primary">
          Traffic sources
        </h2>
        <p className="mt-0.5 text-xs text-text-muted">How viewers discover your channel content</p>
      </div>

      <div className="space-y-3.5 pt-1">
        {rows.map((source) => (
          <div key={source.source} title={`${source.views.toLocaleString()} views`}>
            <div className="mb-1.5 flex justify-between gap-3 text-xs">
              <span className="font-medium text-text-secondary">
                {formatSourceName(source.source)}
              </span>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-text-muted">
                  {compactNumber.format(source.views)} views
                </span>
                <span className="font-mono font-semibold text-text-primary">
                  {source.percentage.toFixed(1)}%
                </span>
              </div>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-surface-3">
              <div
                className="h-full rounded-full bg-primary transition-all duration-300"
                style={{ width: `${Math.min(100, Math.max(1, source.percentage))}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};
