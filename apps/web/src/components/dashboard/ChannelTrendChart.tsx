import type { EChartsOption } from "echarts";
import { TrendingDown, TrendingUp } from "lucide-react";
import React, { useMemo, useState } from "react";
import type { components } from "../../api/generated";
import { EChartsWrapper, GRAPHITE_THEME } from "../charts/EChartsWrapper";

type TrendPoint = components["schemas"]["DashboardTrendPoint"];
type DashboardKpi = components["schemas"]["DashboardKpi"];
type TrendMetric = "views" | "watch_time_hours" | "net_subscribers";

interface ChannelTrendChartProps {
  data: TrendPoint[];
  kpis?: DashboardKpi[];
  periodDays?: number;
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
  kpis,
  periodDays = 28,
  title = "Channel Performance",
  compact = false,
}) => {
  const [metric, setMetric] = useState<TrendMetric>("views");

  // Relative day index calculation (Day 1..Day N)
  const relativeDays = useMemo(() => {
    return data.map((_, idx) => `Day ${idx + 1}`);
  }, [data]);

  const activeKpi = useMemo(() => {
    return kpis?.find((k) => k.metric === metric);
  }, [kpis, metric]);

  const summaryTotal = useMemo(() => {
    if (activeKpi && activeKpi.current_value !== undefined) {
      const val = activeKpi.current_value;
      if (metric === "views") return `${compactNumber.format(val)} views`;
      if (metric === "watch_time_hours") return `${compactNumber.format(val)} hours`;
      if (metric === "net_subscribers")
        return `${val >= 0 ? "+" : ""}${standardNumber.format(val)} subscribers`;
    }
    const sumVal = data.reduce((sum, p) => sum + (p[metric] ?? 0), 0);
    if (metric === "views") return `${compactNumber.format(sumVal)} views`;
    if (metric === "watch_time_hours") return `${compactNumber.format(sumVal)} hours`;
    if (metric === "net_subscribers")
      return `${sumVal >= 0 ? "+" : ""}${standardNumber.format(sumVal)} subscribers`;
    return compactNumber.format(sumVal);
  }, [activeKpi, data, metric]);

  const summaryDelta = useMemo(() => {
    if (activeKpi && activeKpi.change_percentage !== undefined) {
      return activeKpi.change_percentage;
    }
    const currSum = data.reduce((sum, p) => sum + (p[metric] ?? 0), 0);
    const prevSum = data.reduce(
      (sum, p) => sum + ((p[`previous_${metric}` as keyof TrendPoint] as number | undefined) ?? 0),
      0,
    );
    if (prevSum === 0) return null;
    return ((currSum - prevSum) / Math.abs(prevSum)) * 100;
  }, [activeKpi, data, metric]);

  const { currentDaily, previousDaily, calendarDates, previousCalendarDates } = useMemo(() => {
    const curr = data.map((point) => point[metric] ?? null);
    const prev = data.map(
      (point) => (point[`previous_${metric}` as keyof TrendPoint] as number | undefined) ?? null,
    );
    const dates = data.map((p) => {
      try {
        return new Intl.DateTimeFormat("en-US", {
          month: "short",
          day: "numeric",
          timeZone: "UTC",
        }).format(new Date(`${p.date}T00:00:00Z`));
      } catch {
        return p.date;
      }
    });

    const prevDates = data.map((p) => {
      try {
        const d = new Date(`${p.date}T00:00:00Z`);
        d.setUTCDate(d.getUTCDate() - (periodDays || data.length));
        return new Intl.DateTimeFormat("en-US", {
          month: "short",
          day: "numeric",
          timeZone: "UTC",
        }).format(d);
      } catch {
        return p.date;
      }
    });

    return {
      currentDaily: curr,
      previousDaily: prev,
      calendarDates: dates,
      previousCalendarDates: prevDates,
    };
  }, [data, metric, periodDays]);

  const chartOption = useMemo<EChartsOption>(() => {
    return {
      backgroundColor: GRAPHITE_THEME.background,
      animation: false,
      grid: {
        top: compact ? 16 : 24,
        right: 16,
        bottom: 24,
        left: 48,
        containLabel: true,
      },
      tooltip: {
        trigger: "axis",
        confine: true,
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
          if (!items?.length) return "";
          const idx = items[0].dataIndex;
          const dayLabel = relativeDays[idx] || `Day ${idx + 1}`;
          const currDateStr = calendarDates[idx] || "";
          const prevDateStr = previousCalendarDates[idx] || "";
          const currVal = currentDaily[idx];
          const prevVal = previousDaily[idx];

          let deltaHtml = "";
          if (currVal !== null && prevVal !== null && prevVal !== 0) {
            const delta = ((currVal - prevVal) / Math.abs(prevVal)) * 100;
            const isPos = delta >= 0;
            deltaHtml = `
              <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid ${GRAPHITE_THEME.borderSubtle}; display: flex; align-items: center; justify-content: space-between; font-size: 11px;">
                <span style="color: ${GRAPHITE_THEME.textSecondary}; font-weight: 500;">Difference</span>
                <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 600; color: ${isPos ? GRAPHITE_THEME.success : GRAPHITE_THEME.danger};">
                  ${isPos ? "+" : ""}${delta.toFixed(1)}%
                </span>
              </div>
            `;
          }

          return `
            <div style="font-weight: 600; margin-bottom: 8px; color: ${GRAPHITE_THEME.textPrimary}; font-size: 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px;">
              <span>${currDateStr}</span>
              <span style="font-size: 10px; font-weight: 500; color: ${GRAPHITE_THEME.textMuted}; font-family: ${GRAPHITE_THEME.monoFontFamily};">${dayLabel}</span>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 6px; font-size: 11px;">
              <span style="color: ${GRAPHITE_THEME.textSecondary}; display: flex; align-items: center; gap: 6px;">
                <span style="width: 8px; height: 2.5px; background: #3b82f6; border-radius: 1px; display: inline-block;"></span>
                Current
              </span>
              <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 600; color: ${GRAPHITE_THEME.textPrimary};">
                ${currVal !== null ? formatTooltipValue(metric, currVal) : "—"}
              </span>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 20px; font-size: 11px;">
              <span style="color: ${GRAPHITE_THEME.textMuted}; display: flex; align-items: center; gap: 6px;">
                <span style="width: 8px; height: 2px; border-top: 1.5px dashed #94a3b8; display: inline-block;"></span>
                Previous comparable day (${prevDateStr})
              </span>
              <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 500; color: ${GRAPHITE_THEME.textSecondary};">
                ${prevVal !== null ? formatTooltipValue(metric, prevVal) : "—"}
              </span>
            </div>
            ${deltaHtml}
          `;
        },
      },
      xAxis: {
        type: "category",
        data: relativeDays,
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
            opacity: 0.4,
          },
        },
      },
      series: [
        // 1. Visually dominant current period series
        {
          name: "Current period",
          type: "line",
          data: currentDaily,
          smooth: 0.2,
          showSymbol: false,
          lineStyle: {
            width: 2.5,
            color: "#3b82f6",
          },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(59, 130, 246, 0.16)" },
                { offset: 1, color: "rgba(59, 130, 246, 0.0)" },
              ],
            },
          },
          z: 3,
        },
        // 2. Muted dashed previous period series
        {
          name: "Previous period",
          type: "line",
          data: previousDaily,
          smooth: 0.2,
          showSymbol: false,
          lineStyle: {
            width: 1.75,
            type: "dashed",
            color: "#94a3b8",
            opacity: 0.7,
          },
          z: 2,
        },
      ],
    };
  }, [
    calendarDates,
    compact,
    currentDaily,
    metric,
    previousCalendarDates,
    previousDaily,
    relativeDays,
  ]);

  const isPositive = summaryDelta !== null && summaryDelta > 0;
  const isNegative = summaryDelta !== null && summaryDelta < 0;
  const deltaText =
    summaryDelta !== null
      ? `${isPositive ? "+" : ""}${summaryDelta.toFixed(1)}% vs previous ${periodDays} days`
      : "No previous comparison";

  return (
    <section
      className="rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm space-y-4"
      aria-label={title}
    >
      {/* Header & Metric Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            {title}
          </h2>
          {/* Summary Above Graph */}
          <div className="mt-1 flex flex-wrap items-baseline gap-2.5">
            <span className="font-mono text-2xl font-bold tracking-tight text-text-primary tabular-nums">
              {summaryTotal}
            </span>
            <span
              className={`inline-flex items-center gap-1 text-xs font-semibold ${
                isPositive ? "text-success" : isNegative ? "text-danger" : "text-text-muted"
              }`}
            >
              {isPositive ? (
                <TrendingUp className="h-3.5 w-3.5" />
              ) : isNegative ? (
                <TrendingDown className="h-3.5 w-3.5" />
              ) : null}
              <span>{deltaText}</span>
            </span>
          </div>
        </div>

        {/* Metric Selector Tabs */}
        <div
          role="tablist"
          aria-label="Performance Metric"
          className="flex items-center rounded-lg bg-surface-2 p-1 border border-border-subtle text-xs"
        >
          <button
            role="tab"
            aria-selected={metric === "views"}
            type="button"
            onClick={() => setMetric("views")}
            className={`px-3 py-1.5 rounded-md font-medium transition-all ${
              metric === "views"
                ? "bg-surface-3 text-text-primary shadow-xs font-semibold"
                : "text-text-muted hover:text-text-primary"
            }`}
          >
            Views
          </button>
          <button
            role="tab"
            aria-selected={metric === "watch_time_hours"}
            type="button"
            onClick={() => setMetric("watch_time_hours")}
            className={`px-3 py-1.5 rounded-md font-medium transition-all ${
              metric === "watch_time_hours"
                ? "bg-surface-3 text-text-primary shadow-xs font-semibold"
                : "text-text-muted hover:text-text-primary"
            }`}
          >
            Watch time
          </button>
          <button
            role="tab"
            aria-selected={metric === "net_subscribers"}
            type="button"
            onClick={() => setMetric("net_subscribers")}
            className={`px-3 py-1.5 rounded-md font-medium transition-all ${
              metric === "net_subscribers"
                ? "bg-surface-3 text-text-primary shadow-xs font-semibold"
                : "text-text-muted hover:text-text-primary"
            }`}
          >
            Subscribers
          </button>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="h-64 sm:h-72 w-full">
        <EChartsWrapper option={chartOption} />
      </div>

      {/* Legend & Semantics Note */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-border-subtle/50 text-xs text-text-secondary">
        <div className="flex items-center gap-5">
          <div className="flex items-center gap-2">
            <span className="h-0.5 w-4 rounded-full bg-primary inline-block" />
            <span className="text-[11.5px] font-medium text-text-primary">Current period</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-0.5 w-4 border-t-2 border-dashed border-slate-400 inline-block opacity-75" />
            <span className="text-[11.5px] font-medium text-text-secondary">Previous period</span>
          </div>
        </div>
        <span className="text-[11px] font-mono text-text-muted">
          Aligned by relative day (Day 1..{data.length})
        </span>
      </div>
    </section>
  );
};
