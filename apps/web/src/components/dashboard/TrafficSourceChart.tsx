import React, { useMemo } from "react";
import type { EChartsOption } from "echarts";
import type { components } from "../../api/generated";
import { EChartsWrapper, GRAPHITE_THEME } from "../charts/EChartsWrapper";

type TrafficSource = components["schemas"]["TrafficSourceMetric"];

interface TrafficSourceChartProps {
  data: TrafficSource[];
}

const formatSourceName = (source: string): string => {
  const map: Record<string, string> = {
    suggested_videos: "Suggested videos",
    youtube_search: "YouTube search",
    browse_features: "Browse features",
    external: "External",
    direct_or_other: "Direct or other",
  };
  return map[source] || source.replace(/_/g, " ");
};

export const TrafficSourceChart: React.FC<TrafficSourceChartProps> = ({ data }) => {
  // Sort in ascending order so that the largest appears at the top of horizontal bars
  const sortedData = useMemo(() => {
    return [...data].sort((a, b) => a.percentage - b.percentage);
  }, [data]);

  const categories = useMemo(
    () => sortedData.map((item) => formatSourceName(item.source)),
    [sortedData],
  );

  const values = useMemo(() => sortedData.map((item) => item.percentage), [sortedData]);
  const viewCounts = useMemo(() => sortedData.map((item) => item.views), [sortedData]);

  const chartOption = useMemo<EChartsOption>(() => {
    return {
      backgroundColor: GRAPHITE_THEME.background,
      animation: false,
      grid: {
        top: 10,
        right: 48,
        bottom: 10,
        left: 110,
      },
      tooltip: {
        trigger: "axis",
        axisPointer: {
          type: "shadow",
          shadowStyle: {
            color: "rgba(255, 255, 255, 0.03)",
          },
        },
        backgroundColor: GRAPHITE_THEME.tooltipBg,
        borderColor: GRAPHITE_THEME.borderStrong,
        borderWidth: 1,
        padding: [10, 14],
        textStyle: {
          color: GRAPHITE_THEME.textPrimary,
          fontFamily: GRAPHITE_THEME.fontFamily,
          fontSize: 12,
        },
        formatter: (params: unknown) => {
          const items = params as Array<{
            dataIndex: number;
          }>;
          if (!items || !items.length) return "";
          const idx = items[0].dataIndex;
          const name = categories[idx];
          const pct = values[idx];
          const views = viewCounts[idx];

          return `
            <div style="font-weight: 600; margin-bottom: 4px; color: ${GRAPHITE_THEME.textPrimary}; font-size: 12px;">${name}</div>
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px; font-size: 11px;">
              <span style="color: ${GRAPHITE_THEME.textMuted};">Traffic Share:</span>
              <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 600; color: ${GRAPHITE_THEME.primary};">${pct.toFixed(1)}%</span>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px; font-size: 11px; margin-top: 2px;">
              <span style="color: ${GRAPHITE_THEME.textMuted};">Views:</span>
              <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 500; color: ${GRAPHITE_THEME.textPrimary};">${views.toLocaleString()}</span>
            </div>
          `;
        },
      },
      xAxis: {
        type: "value",
        show: false,
        max: 100,
      },
      yAxis: {
        type: "category",
        data: categories,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: GRAPHITE_THEME.textSecondary,
          fontSize: 11,
          fontFamily: GRAPHITE_THEME.fontFamily,
        },
      },
      series: [
        {
          name: "Traffic Share",
          type: "bar",
          data: values,
          barWidth: 14,
          itemStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 1,
              y2: 0,
              colorStops: [
                { offset: 0, color: "#1d4ed8" },
                { offset: 1, color: "#2563eb" },
              ],
            },
            borderRadius: [0, 4, 4, 0],
          },
          label: {
            show: true,
            position: "right",
            formatter: "{c}%",
            color: GRAPHITE_THEME.textMuted,
            fontSize: 11,
            fontFamily: GRAPHITE_THEME.monoFontFamily,
          },
        },
      ],
    };
  }, [categories, values, viewCounts]);

  return (
    <section
      className="rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm space-y-4"
      aria-labelledby="traffic-title"
    >
      <div className="flex items-center justify-between">
        <div>
          <h2 id="traffic-title" className="text-sm font-semibold tracking-tight text-text-primary">
            Traffic Sources
          </h2>
          <p className="mt-0.5 text-xs text-text-muted">
            Audience acquisition channels and distribution percentages
          </p>
        </div>
      </div>

      <div className="h-56 sm:h-64 w-full">
        <EChartsWrapper
          option={chartOption}
          ariaLabel="Traffic sources distribution horizontal bar chart"
        />
      </div>
    </section>
  );
};
