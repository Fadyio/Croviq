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

const computeRollingMean = (values: (number | null)[], windowSize = 7): (number | null)[] => {
  const result: (number | null)[] = [];
  for (let i = 0; i < values.length; i++) {
    const windowVals = values
      .slice(Math.max(0, i - windowSize + 1), i + 1)
      .filter((v): v is number => typeof v === "number" && !Number.isNaN(v));
    if (windowVals.length === 0) {
      result.push(null);
    } else {
      const avg = windowVals.reduce((sum, v) => sum + v, 0) / windowVals.length;
      result.push(Math.round(avg * 10) / 10);
    }
  }
  return result;
};

export const ChannelTrendChart: React.FC<ChannelTrendChartProps> = ({
  data,
  title = "Channel Performance",
  compact = false,
}) => {
  const [metric, setMetric] = useState<TrendMetric>("views");

  // Relative day index calculation (Day 1..Day N)
  const relativeDays = useMemo(() => {
    return data.map((_, idx) => `Day ${idx + 1}`);
  }, [data]);

  const { currentDaily, currentRolling7, previousRolling7, calendarDates, maxObservationIndex } =
    useMemo(() => {
      const curr = data.map((point) => point[metric] ?? null);
      const prev = data.map(
        (point) => (point[`previous_${metric}` as keyof TrendPoint] as number | undefined) ?? null,
      );
      const dates = data.map((p) => {
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

      const currRolling = computeRollingMean(curr, 7);
      const prevRolling = computeRollingMean(prev, 7);

      // Find peak daily observation for evidence-backed annotation (max 1 peak annotation)
      let maxIdx = -1;
      let maxVal = -Infinity;
      curr.forEach((val, i) => {
        if (typeof val === "number" && val > maxVal) {
          maxVal = val;
          maxIdx = i;
        }
      });

      return {
        currentDaily: curr,
        currentRolling7: currRolling,
        previousRolling7: prevRolling,
        calendarDates: dates,
        maxObservationIndex: maxIdx,
      };
    }, [data, metric]);

  const chartOption = useMemo<EChartsOption>(() => {
    // Evidence-backed annotations: at most 2 (e.g. Period Peak and Latest Day)
    const markData: Array<{
      name: string;
      coord: [number, number];
      value: string;
    }> = [];

    if (maxObservationIndex >= 0 && typeof currentDaily[maxObservationIndex] === "number") {
      markData.push({
        name: "Peak",
        coord: [maxObservationIndex, currentDaily[maxObservationIndex] as number],
        value: "Peak",
      });
    }

    return {
      backgroundColor: GRAPHITE_THEME.background,
      animation: false,
      grid: {
        top: compact ? 24 : 32,
        right: 16,
        bottom: 30,
        left: 54,
        containLabel: false,
      },
      legend: {
        show: !compact,
        top: 0,
        right: 16,
        itemWidth: 14,
        itemHeight: 8,
        textStyle: {
          color: GRAPHITE_THEME.textSecondary,
          fontSize: 11,
          fontFamily: GRAPHITE_THEME.fontFamily,
        },
        data: ["Current 7-Day Mean", "Previous 7-Day Baseline", "Daily Observations"],
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
          if (!items?.length) return "";
          const idx = items[0].dataIndex;
          const dayLabel = relativeDays[idx] || `Day ${idx + 1}`;
          const dateStr = calendarDates[idx] || "";
          const curr = currentDaily[idx];
          const currRolling = currentRolling7[idx];
          const prevRolling = previousRolling7[idx];

          let deltaHtml = "";
          if (currRolling !== null && prevRolling !== null && prevRolling > 0) {
            const delta = ((currRolling - prevRolling) / prevRolling) * 100;
            const isPos = delta >= 0;
            deltaHtml = `<div style="margin-top: 6px; padding-top: 6px; border-top: 1px solid ${GRAPHITE_THEME.borderSubtle}; font-weight: 600; font-size: 11px; color: ${isPos ? GRAPHITE_THEME.success : GRAPHITE_THEME.danger};">${isPos ? "+" : ""}${delta.toFixed(1)}% vs previous baseline</div>`;
          }

          return `
            <div style="font-weight: 600; margin-bottom: 6px; color: ${GRAPHITE_THEME.textPrimary}; font-size: 12px;">
              ${dayLabel} <span style="font-size: 11px; font-weight: 400; color: ${GRAPHITE_THEME.textMuted}; margin-left: 4px;">(${dateStr})</span>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 3px; font-size: 11px;">
              <span style="color: ${GRAPHITE_THEME.textSecondary}; display: flex; align-items: center; gap: 6px;">
                <span style="width: 8px; height: 8px; border-radius: 50%; background: #38bdf8; display: inline-block;"></span>
                Daily Actual
              </span>
              <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 600; color: ${GRAPHITE_THEME.textPrimary};">${curr !== null ? formatTooltipValue(metric, curr) : "—"}</span>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 3px; font-size: 11px;">
              <span style="color: ${GRAPHITE_THEME.textSecondary}; display: flex; align-items: center; gap: 6px;">
                <span style="width: 8px; height: 2px; background: ${GRAPHITE_THEME.primary}; display: inline-block;"></span>
                7-Day Rolling Mean
              </span>
              <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 600; color: ${GRAPHITE_THEME.textPrimary};">${currRolling !== null ? formatTooltipValue(metric, currRolling) : "—"}</span>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px; font-size: 11px;">
              <span style="color: ${GRAPHITE_THEME.textMuted}; display: flex; align-items: center; gap: 6px;">
                <span style="width: 8px; height: 2px; border-top: 1px dashed ${GRAPHITE_THEME.textMuted}; display: inline-block;"></span>
                Previous Baseline
              </span>
              <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 500; color: ${GRAPHITE_THEME.textSecondary};">${prevRolling !== null ? formatTooltipValue(metric, prevRolling) : "—"}</span>
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
            opacity: 0.6,
          },
        },
      },
      series: [
        // 1. Subtle daily observations
        {
          name: "Daily Observations",
          type: "line",
          data: currentDaily,
          showSymbol: true,
          symbolSize: 4,
          itemStyle: {
            color: "#38bdf8",
            opacity: 0.5,
          },
          lineStyle: {
            width: 1,
            color: "#38bdf8",
            opacity: 0.25,
          },
          z: 2,
        },
        // 2. Dominant 7-Day Rolling Mean
        {
          name: "Current 7-Day Mean",
          type: "line",
          data: currentRolling7,
          smooth: true,
          showSymbol: false,
          lineStyle: {
            width: 2.5,
            color: GRAPHITE_THEME.primary,
          },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(37, 99, 235, 0.18)" },
                { offset: 1, color: "rgba(37, 99, 235, 0.0)" },
              ],
            },
          },
          markPoint:
            markData.length > 0
              ? {
                  data: markData,
                  symbol: "circle",
                  symbolSize: 6,
                  itemStyle: {
                    color: "#f59e0b",
                  },
                  label: {
                    show: true,
                    position: "top",
                    fontSize: 9,
                    color: GRAPHITE_THEME.textSecondary,
                    formatter: "{b}",
                  },
                }
              : undefined,
          z: 4,
        },
        // 3. Muted Previous-Period 7-Day Rolling Baseline
        {
          name: "Previous 7-Day Baseline",
          type: "line",
          data: previousRolling7,
          smooth: true,
          showSymbol: false,
          lineStyle: {
            width: 1.75,
            type: "dashed",
            color: "#64748b",
            opacity: 0.75,
          },
          z: 3,
        },
      ],
    };
  }, [
    compact,
    relativeDays,
    calendarDates,
    currentDaily,
    currentRolling7,
    previousRolling7,
    maxObservationIndex,
    metric,
  ]);

  return (
    <div className="rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm space-y-4">
      {/* Header & Metric Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-text-primary">{title}</h2>
          <p className="text-xs text-text-muted mt-0.5">
            Relative period baseline comparison · 7-day rolling mean
          </p>
        </div>

        {/* Metric Selector Tabs */}
        <div className="flex items-center rounded-lg bg-surface-2 p-1 border border-border-subtle text-xs">
          <button
            type="button"
            onClick={() => setMetric("views")}
            className={`px-3 py-1 rounded-md font-medium transition-all ${
              metric === "views"
                ? "bg-surface-3 text-text-primary shadow-xs font-semibold"
                : "text-text-muted hover:text-text-primary"
            }`}
          >
            Views
          </button>
          <button
            type="button"
            onClick={() => setMetric("watch_time_hours")}
            className={`px-3 py-1 rounded-md font-medium transition-all ${
              metric === "watch_time_hours"
                ? "bg-surface-3 text-text-primary shadow-xs font-semibold"
                : "text-text-muted hover:text-text-primary"
            }`}
          >
            Watch time
          </button>
          <button
            type="button"
            onClick={() => setMetric("net_subscribers")}
            className={`px-3 py-1 rounded-md font-medium transition-all ${
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
      <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-border-subtle/50 text-[11px] text-text-muted">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-primary" />
            Current 7-day mean
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-3 border-t border-dashed border-slate-500" />
            Previous 7-day baseline
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-sky-400 opacity-60" />
            Daily observations
          </span>
        </div>
        <span className="text-[10px] font-mono text-text-muted">
          Aligned by relative day index (Day 1..{data.length})
        </span>
      </div>
    </div>
  );
};
