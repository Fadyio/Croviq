import React, { useMemo, useState } from "react";
import type { EChartsOption } from "echarts";
import type { components } from "../../api/generated";
import { EChartsWrapper, GRAPHITE_THEME } from "../charts/EChartsWrapper";

type TrendPoint = components["schemas"]["DashboardTrendPoint"];
type TrendMetric = "views" | "watch_time_hours" | "net_subscribers";

interface ChannelTrendChartProps {
  data: TrendPoint[];
  title?: string;
  compact?: boolean;
}

const compactNumber = new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const standardNumber = new Intl.NumberFormat("en", {
  maximumFractionDigits: 1,
});

const formatAxisValue = (metric: TrendMetric, value: number): string => {
  if (metric === "views") return compactNumber.format(value);
  if (metric === "watch_time_hours") return `${compactNumber.format(value)}h`;
  if (metric === "net_subscribers") return `${value >= 0 ? "+" : ""}${compactNumber.format(value)}`;
  return compactNumber.format(value);
};

const formatTooltipValue = (metric: TrendMetric, value: number): string => {
  if (metric === "views") return `${standardNumber.format(value)} views`;
  if (metric === "watch_time_hours") return `${standardNumber.format(value)} hours`;
  if (metric === "net_subscribers")
    return `${value >= 0 ? "+" : ""}${standardNumber.format(value)} subscribers`;
  return String(value);
};

export const ChannelTrendChart: React.FC<ChannelTrendChartProps> = ({
  data,
  title = "Channel Performance",
  compact = false,
}) => {
  const [metric, setMetric] = useState<TrendMetric>("views");
  const [includeForecast, setIncludeForecast] = useState<boolean>(true);

  // Statistical 7-day projection derived from recent moving trend + variance
  const { extendedDates, currentSeries, previousSeries, forecastLow, forecastBand } = useMemo(() => {
    const dateLabels = data.map((p) => {
      try {
        return new Intl.DateTimeFormat("en", {
          month: "short",
          day: "numeric",
          timeZone: "UTC",
        }).format(new Date(`${p.date}T00:00:00Z`));
      } catch {
        return p.date;
      }
    });

    const curr = data.map((point) => point[metric] ?? null);
    const prev = data.map(
      (point) => (point[`previous_${metric}` as keyof TrendPoint] as number | undefined) ?? null,
    );

    if (!includeForecast || data.length < 7) {
      return {
        extendedDates: dateLabels,
        currentSeries: curr,
        previousSeries: prev,
        forecastLow: [] as (number | null)[],
        forecastBand: [] as (number | null)[],
      };
    }

    const validVals = curr.filter((v): v is number => typeof v === "number" && !isNaN(v));
    const n = validVals.length;
    if (n < 7) {
      return {
        extendedDates: dateLabels,
        currentSeries: curr,
        previousSeries: prev,
        forecastLow: [],
        forecastBand: [],
      };
    }

    const recent = validVals.slice(-7);
    const recentAvg = recent.reduce((sum, v) => sum + v, 0) / 7;
    const lastVal = validVals[n - 1];
    const stepSlope = (lastVal - recent[0]) / 6;
    const variance = recent.reduce((sum, v) => sum + Math.pow(v - recentAvg, 2), 0) / 7;
    const stdDev = Math.sqrt(variance);

    const lastDate = new Date(`${data[data.length - 1].date}T00:00:00Z`);
    const forecastDates: string[] = [];
    const forecastLowVals: (number | null)[] = new Array(data.length - 1).fill(null);
    const forecastBandVals: (number | null)[] = new Array(data.length - 1).fill(null);

    forecastLowVals.push(lastVal);
    forecastBandVals.push(0);

    for (let day = 1; day <= 7; day++) {
      const projDate = new Date(lastDate);
      projDate.setUTCDate(lastDate.getUTCDate() + day);
      try {
        forecastDates.push(
          new Intl.DateTimeFormat("en", {
            month: "short",
            day: "numeric",
            timeZone: "UTC",
          }).format(projDate),
        );
      } catch {
        forecastDates.push(`+${day}d`);
      }

      const centerProj = Math.max(0, lastVal + stepSlope * day);
      const spread = stdDev * (1 + 0.15 * day);
      const low = Math.max(0, centerProj - spread);
      const high = centerProj + spread;

      forecastLowVals.push(Math.round(low * 10) / 10);
      forecastBandVals.push(Math.round((high - low) * 10) / 10);
    }

    return {
      extendedDates: [...dateLabels, ...forecastDates],
      currentSeries: [...curr, ...new Array(7).fill(null)],
      previousSeries: [...prev, ...new Array(7).fill(null)],
      forecastLow: forecastLowVals,
      forecastBand: forecastBandVals,
    };
  }, [data, metric, includeForecast]);

  const chartOption = useMemo<EChartsOption>(() => {
    return {
      backgroundColor: GRAPHITE_THEME.background,
      animation: false,
      grid: {
        top: compact ? 20 : 30,
        right: 16,
        bottom: 30,
        left: 54,
        containLabel: false,
      },
      tooltip: {
        trigger: "axis",
        backgroundColor: GRAPHITE_THEME.tooltipBg,
        borderColor: GRAPHITE_THEME.borderStrong,
        borderWidth: 1,
        padding: [10, 14],
        textStyle: {
          color: GRAPHITE_THEME.textPrimary,
          fontFamily: GRAPHITE_THEME.fontFamily,
          fontSize: 12,
        },
        axisPointer: {
          type: "line",
          lineStyle: {
            color: GRAPHITE_THEME.borderStrong,
            width: 1,
            type: "dashed",
          },
        },
        formatter: (params: unknown) => {
          const items = params as Array<{
            seriesName: string;
            value: number | null;
            dataIndex: number;
          }>;
          if (!items || !items.length) return "";
          const idx = items[0].dataIndex;
          const dateStr = extendedDates[idx] || "";
          const isForecastPoint = idx >= data.length;
          const curr = currentSeries[idx];
          const prev = previousSeries[idx];
          const low = forecastLow[idx];
          const band = forecastBand[idx];

          if (isForecastPoint && low !== null && band !== null && band > 0) {
            const high = low + band;
            const center = low + band / 2;
            return `
              <div style="font-weight: 600; margin-bottom: 6px; color: ${GRAPHITE_THEME.textPrimary}; font-size: 12px;">
                ${dateStr} <span style="font-size: 10px; font-weight: 500; color: ${GRAPHITE_THEME.primary}; background: rgba(37,99,235,0.15); padding: 1px 5px; border-radius: 4px; margin-left: 4px;">Forecast Range</span>
              </div>
              <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 3px; font-size: 11px;">
                <span style="color: ${GRAPHITE_THEME.textSecondary};">Expected projection:</span>
                <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 600; color: ${GRAPHITE_THEME.textPrimary};">${formatTooltipValue(metric, center)}</span>
              </div>
              <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px; font-size: 11px;">
                <span style="color: ${GRAPHITE_THEME.textMuted};">Confidence band:</span>
                <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 500; color: ${GRAPHITE_THEME.textSecondary};">${formatAxisValue(metric, low)} – ${formatAxisValue(metric, high)}</span>
              </div>
            `;
          }

          let deltaHtml = "";
          if (curr !== null && prev !== null && prev > 0) {
            const delta = ((curr - prev) / prev) * 100;
            const isPos = delta >= 0;
            deltaHtml = `<div style="margin-top: 6px; padding-top: 6px; border-top: 1px solid ${GRAPHITE_THEME.borderSubtle}; font-weight: 600; font-size: 11px; color: ${isPos ? GRAPHITE_THEME.success : GRAPHITE_THEME.danger};">${isPos ? "+" : ""}${delta.toFixed(1)}% vs previous period</div>`;
          }

          return `
            <div style="font-weight: 600; margin-bottom: 6px; color: ${GRAPHITE_THEME.textPrimary}; font-size: 12px;">${dateStr}</div>
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 3px; font-size: 11px;">
              <span style="color: ${GRAPHITE_THEME.textSecondary}; display: flex; align-items: center; gap: 6px;">
                <span style="width: 8px; height: 8px; border-radius: 50%; background: ${GRAPHITE_THEME.primary}; display: inline-block;"></span>
                Actual
              </span>
              <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 600; color: ${GRAPHITE_THEME.textPrimary};">${curr !== null ? formatTooltipValue(metric, curr) : "—"}</span>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px; font-size: 11px;">
              <span style="color: ${GRAPHITE_THEME.textMuted}; display: flex; align-items: center; gap: 6px;">
                <span style="width: 8px; height: 2px; background: ${GRAPHITE_THEME.textMuted}; display: inline-block;"></span>
                Previous
              </span>
              <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 500; color: ${GRAPHITE_THEME.textSecondary};">${prev !== null ? formatTooltipValue(metric, prev) : "—"}</span>
            </div>
            ${deltaHtml}
          `;
        },
      },
      xAxis: {
        type: "category",
        data: extendedDates,
        boundaryGap: false,
        axisLine: {
          lineStyle: {
            color: GRAPHITE_THEME.borderSubtle,
          },
        },
        axisTick: { show: false },
        axisLabel: {
          color: GRAPHITE_THEME.textMuted,
          fontSize: 10,
          fontFamily: GRAPHITE_THEME.fontFamily,
          interval: "auto",
        },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: GRAPHITE_THEME.textMuted,
          fontSize: 10,
          fontFamily: GRAPHITE_THEME.monoFontFamily,
          formatter: (val: number) => formatAxisValue(metric, val),
        },
        splitLine: {
          lineStyle: {
            color: GRAPHITE_THEME.borderSubtle,
            type: "dashed",
            opacity: 0.7,
          },
        },
      },
      series: [
        {
          name: "Previous period",
          type: "line",
          data: previousSeries,
          showSymbol: false,
          lineStyle: {
            color: GRAPHITE_THEME.textMuted,
            width: 1.5,
            type: "dashed",
          },
          z: 1,
        },
        {
          name: "Current",
          type: "line",
          data: currentSeries,
          showSymbol: false,
          lineStyle: {
            color: GRAPHITE_THEME.primary,
            width: 2.2,
          },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(37, 99, 235, 0.22)" },
                { offset: 1, color: "rgba(37, 99, 235, 0.00)" },
              ],
            },
          },
          z: 2,
        },
        ...(forecastBand.length > 0
          ? [
              {
                name: "Forecast Lower",
                type: "line" as const,
                data: forecastLow,
                lineStyle: { opacity: 0 },
                stack: "forecast",
                symbol: "none",
              },
              {
                name: "Forecast Range",
                type: "line" as const,
                data: forecastBand,
                lineStyle: {
                  color: "rgba(59, 130, 246, 0.6)",
                  type: "dashed" as const,
                  width: 1.5,
                },
                areaStyle: {
                  color: "rgba(59, 130, 246, 0.12)",
                },
                stack: "forecast",
                symbol: "none",
              },
            ]
          : []),
      ],
    };
  }, [extendedDates, currentSeries, previousSeries, forecastLow, forecastBand, metric, compact, data.length]);

  return (
    <section
      className="rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm space-y-4"
      aria-labelledby="trend-title"
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 id="trend-title" className="text-sm font-semibold tracking-tight text-text-primary">
            {title}
          </h2>
          <p className="mt-0.5 text-xs text-text-muted">
            {metric === "views"
              ? "Daily views compared to previous period baseline"
              : metric === "watch_time_hours"
                ? "Total watch time hours compared to previous period"
                : "Net subscriber gains compared to previous period"}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => setIncludeForecast((prev) => !prev)}
            className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors border ${
              includeForecast
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-border-subtle bg-surface-2 text-text-muted hover:text-text-secondary"
            }`}
            title="Statistical 7-day projection range"
          >
            <span>{includeForecast ? "Projection active" : "Add projection"}</span>
          </button>

          <div className="hidden sm:flex items-center gap-3 text-[11px] text-text-muted">
            <span className="inline-flex items-center gap-1.5 font-medium text-text-secondary">
              <span className="h-2 w-2 rounded-full bg-primary" />
              Actual
            </span>
            <span className="inline-flex items-center gap-1.5 font-medium text-text-muted">
              <span className="h-0.5 w-3 border-t border-dashed border-text-muted" />
              Previous period
            </span>
          </div>
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

      <div className="h-64 sm:h-72 w-full">
        <EChartsWrapper option={chartOption} ariaLabel={`${title} chart showing ${metric}`} />
      </div>
    </section>
  );
};
