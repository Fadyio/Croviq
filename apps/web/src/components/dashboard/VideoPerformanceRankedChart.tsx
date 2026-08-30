import type { EChartsOption } from "echarts";
import {
  AlertCircle,
  Award,
  Eye,
  MousePointerClick,
  Percent,
  TrendingUp,
  UserPlus,
} from "lucide-react";
import React, { useMemo, useState } from "react";
import type { components } from "../../api/generated";
import { EChartsWrapper, GRAPHITE_THEME } from "../charts/EChartsWrapper";

type VideoPoint = components["schemas"]["VideoPerformancePoint"];
type MetricKey = "views" | "average_retention" | "ctr_percentage" | "subscribers_gained";

interface VideoPerformanceRankedChartProps {
  data: VideoPoint[];
  onSelectVideo?: (video: VideoPoint) => void;
}

const compactNumber = new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const METRIC_CONFIGS: Record<
  MetricKey,
  {
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    unit: string;
    format: (v: number) => string;
  }
> = {
  views: {
    label: "Views",
    icon: Eye,
    unit: "views",
    format: (v) => compactNumber.format(v),
  },
  average_retention: {
    label: "Retention",
    icon: Percent,
    unit: "%",
    format: (v) => `${v.toFixed(1)}%`,
  },
  ctr_percentage: {
    label: "Thumbnail CTR",
    icon: MousePointerClick,
    unit: "%",
    format: (v) => `${v.toFixed(1)}%`,
  },
  subscribers_gained: {
    label: "Subscribers",
    icon: UserPlus,
    unit: "subs",
    format: (v) => `${v >= 0 ? "+" : ""}${compactNumber.format(v)}`,
  },
};

const calculateMedian = (values: number[]): number => {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
};

export const VideoPerformanceRankedChart: React.FC<VideoPerformanceRankedChartProps> = ({
  data,
  onSelectVideo,
}) => {
  const [selectedMetric, setSelectedMetric] = useState<MetricKey>("views");

  // Secondary signals calculation
  const signals = useMemo(() => {
    if (!data.length) return null;

    const retentions = data.map((v) => v.average_retention);
    const ctrs = data.map((v) => v.ctr_percentage ?? 0);
    const medianRet = calculateMedian(retentions);
    const medianCtr = calculateMedian(ctrs);

    const bestRetention = [...data].sort((a, b) => b.average_retention - a.average_retention)[0];
    const bestCtr = [...data].sort((a, b) => (b.ctr_percentage ?? 0) - (a.ctr_percentage ?? 0))[0];
    const mostSubs = [...data].sort((a, b) => b.subscribers_gained - a.subscribers_gained)[0];

    // Needs attention: High CTR (> median) but Low retention (< median), or lowest retention
    const packagingGap = data.find(
      (v) => (v.ctr_percentage ?? 0) >= medianCtr && v.average_retention < medianRet,
    );
    const needsAttention =
      packagingGap || [...data].sort((a, b) => a.average_retention - b.average_retention)[0];

    return {
      bestRetention,
      bestCtr,
      mostSubs,
      needsAttention,
      isPackagingIssue: Boolean(packagingGap),
    };
  }, [data]);

  // Top 8-10 ranked videos by selected metric
  const rankedVideos = useMemo(() => {
    const sorted = [...data].sort((a, b) => {
      const valA = (a[selectedMetric] ?? 0) as number;
      const valB = (b[selectedMetric] ?? 0) as number;
      return valB - valA;
    });
    return sorted.slice(0, 10);
  }, [data, selectedMetric]);

  const chartOption = useMemo<EChartsOption>(() => {
    // In ECharts horizontal bar charts, category index 0 is at the bottom.
    // We reverse so the #1 ranked item appears at the top.
    const reversed = [...rankedVideos].reverse();
    const titles = reversed.map((v) => {
      const t = v.title;
      return t.length > 32 ? `${t.slice(0, 30)}…` : t;
    });
    const values = reversed.map((v) => (v[selectedMetric] ?? 0) as number);

    const config = METRIC_CONFIGS[selectedMetric];

    return {
      backgroundColor: GRAPHITE_THEME.background,
      animation: false,
      grid: {
        top: 16,
        right: 48,
        bottom: 24,
        left: 200,
        containLabel: false,
      },
      tooltip: {
        trigger: "axis",
        axisPointer: {
          type: "shadow",
          shadowStyle: {
            color: "rgba(255, 255, 255, 0.04)",
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
          const arr = params as Array<{ dataIndex: number }>;
          if (!arr?.length) return "";
          const idx = arr[0].dataIndex;
          const video = reversed[idx];
          if (!video) return "";

          return `
            <div style="font-weight: 600; margin-bottom: 6px; color: ${GRAPHITE_THEME.textPrimary}; font-size: 12px; max-width: 280px; word-break: break-word;">
              ${video.title}
            </div>
            <div style="margin-bottom: 8px; font-size: 10px; color: ${GRAPHITE_THEME.textMuted}; text-transform: uppercase; letter-spacing: 0.05em;">
              ${video.content_pillar || "AI Engineering"}
            </div>
            <div style="display: grid; grid-template-columns: auto auto; gap: 4px 16px; font-size: 11px;">
              <span style="color: ${GRAPHITE_THEME.textMuted};">Views:</span>
              <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 600; color: ${GRAPHITE_THEME.textPrimary}; text-align: right;">${video.views.toLocaleString()}</span>
              
              <span style="color: ${GRAPHITE_THEME.textMuted};">Thumbnail CTR:</span>
              <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 600; color: ${GRAPHITE_THEME.textPrimary}; text-align: right;">${(video.ctr_percentage ?? 0).toFixed(1)}%</span>
              
              <span style="color: ${GRAPHITE_THEME.textMuted};">Retention:</span>
              <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 600; color: ${GRAPHITE_THEME.textPrimary}; text-align: right;">${video.average_retention.toFixed(1)}%</span>
              
              <span style="color: ${GRAPHITE_THEME.textMuted};">Subscribers gained:</span>
              <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 600; color: ${video.subscribers_gained >= 0 ? GRAPHITE_THEME.success : GRAPHITE_THEME.danger}; text-align: right;">${video.subscribers_gained >= 0 ? "+" : ""}${video.subscribers_gained.toLocaleString()}</span>
            </div>
          `;
        },
      },
      xAxis: {
        type: "value",
        axisLabel: {
          color: GRAPHITE_THEME.textMuted,
          fontFamily: GRAPHITE_THEME.monoFontFamily,
          fontSize: 10,
          formatter: (val: number) => config.format(val),
        },
        splitLine: {
          lineStyle: {
            color: GRAPHITE_THEME.borderSubtle,
            type: "dashed",
          },
        },
      },
      yAxis: {
        type: "category",
        data: titles,
        axisLabel: {
          color: GRAPHITE_THEME.textSecondary,
          fontFamily: GRAPHITE_THEME.fontFamily,
          fontSize: 11,
          width: 180,
          overflow: "truncate",
        },
        axisLine: {
          lineStyle: {
            color: GRAPHITE_THEME.borderSubtle,
          },
        },
        axisTick: { show: false },
      },
      series: [
        {
          name: config.label,
          type: "bar",
          data: values,
          barWidth: "60%",
          itemStyle: {
            color: GRAPHITE_THEME.primary,
            borderRadius: [0, 4, 4, 0],
          },
          emphasis: {
            itemStyle: {
              color: GRAPHITE_THEME.primaryHover,
            },
          },
          label: {
            show: true,
            position: "right",
            formatter: (params: unknown) => {
              const p = params as { value: number };
              return config.format(p.value);
            },
            color: GRAPHITE_THEME.textMuted,
            fontFamily: GRAPHITE_THEME.monoFontFamily,
            fontSize: 10,
          },
        },
      ],
    };
  }, [rankedVideos, selectedMetric]);

  const handleChartClick = (params: { dataIndex?: number }) => {
    if (!onSelectVideo || params.dataIndex === undefined) return;
    const reversed = [...rankedVideos].reverse();
    const video = reversed[params.dataIndex];
    if (video) onSelectVideo(video);
  };

  return (
    <section
      className="rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm space-y-5"
      aria-labelledby="video-performance-title"
    >
      {/* Header & Metric Switcher Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle pb-4">
        <div>
          <h3 id="video-performance-title" className="text-sm font-semibold text-text-primary">
            Video Performance
          </h3>
          <p className="text-xs text-text-muted mt-0.5">
            Ranked video performance across key channel growth metrics
          </p>
        </div>

        {/* Metric Switcher Tabs */}
        <div className="flex items-center gap-1 rounded-lg border border-border-subtle bg-surface-2/60 p-1">
          {(Object.keys(METRIC_CONFIGS) as MetricKey[]).map((key) => {
            const config = METRIC_CONFIGS[key];
            const Icon = config.icon;
            const isSelected = selectedMetric === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => setSelectedMetric(key)}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  isSelected
                    ? "bg-surface-1 text-text-primary shadow-xs font-semibold"
                    : "text-text-muted hover:text-text-secondary"
                }`}
                aria-pressed={isSelected}
              >
                <Icon className="h-3 w-3" />
                <span>{config.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Primary Visualization: Horizontal Ranked Bar Chart */}
      <div className="h-[340px] w-full">
        {data.length > 0 ? (
          <EChartsWrapper
            option={chartOption}
            height="100%"
            ariaLabel={`Ranked video performance by ${METRIC_CONFIGS[selectedMetric].label}`}
            onChartClick={handleChartClick}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-text-muted">
            No video performance data available for this time range.
          </div>
        )}
      </div>

      {/* Secondary Signals: Compact 4-Card Summary Row (Phase 12) */}
      {signals && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-2 border-t border-border-subtle">
          {/* 1. Best Retention */}
          {signals.bestRetention && (
            <div className="rounded-lg bg-surface-2/40 border border-border-subtle/60 p-3 text-xs space-y-1">
              <div className="flex items-center justify-between text-text-muted text-[10px] uppercase font-semibold tracking-wider">
                <span className="flex items-center gap-1 text-primary">
                  <Award className="h-3 w-3" />
                  Best retention
                </span>
                <span className="font-mono text-text-primary font-bold">
                  {signals.bestRetention.average_retention.toFixed(1)}%
                </span>
              </div>
              <p
                className="font-medium text-text-primary truncate"
                title={signals.bestRetention.title}
              >
                {signals.bestRetention.title}
              </p>
            </div>
          )}

          {/* 2. Best CTR */}
          {signals.bestCtr && (
            <div className="rounded-lg bg-surface-2/40 border border-border-subtle/60 p-3 text-xs space-y-1">
              <div className="flex items-center justify-between text-text-muted text-[10px] uppercase font-semibold tracking-wider">
                <span className="flex items-center gap-1 text-primary">
                  <MousePointerClick className="h-3 w-3" />
                  Best CTR
                </span>
                <span className="font-mono text-text-primary font-bold">
                  {(signals.bestCtr.ctr_percentage ?? 0).toFixed(1)}%
                </span>
              </div>
              <p className="font-medium text-text-primary truncate" title={signals.bestCtr.title}>
                {signals.bestCtr.title}
              </p>
            </div>
          )}

          {/* 3. Most Subscribers Gained */}
          {signals.mostSubs && (
            <div className="rounded-lg bg-surface-2/40 border border-border-subtle/60 p-3 text-xs space-y-1">
              <div className="flex items-center justify-between text-text-muted text-[10px] uppercase font-semibold tracking-wider">
                <span className="flex items-center gap-1 text-success">
                  <TrendingUp className="h-3 w-3" />
                  Most subscribers
                </span>
                <span className="font-mono text-success font-bold">
                  +{compactNumber.format(signals.mostSubs.subscribers_gained)}
                </span>
              </div>
              <p className="font-medium text-text-primary truncate" title={signals.mostSubs.title}>
                {signals.mostSubs.title}
              </p>
            </div>
          )}

          {/* 4. Needs Attention */}
          {signals.needsAttention && (
            <div className="rounded-lg bg-surface-2/40 border border-border-subtle/60 p-3 text-xs space-y-1">
              <div className="flex items-center justify-between text-text-muted text-[10px] uppercase font-semibold tracking-wider">
                <span className="flex items-center gap-1 text-warning">
                  <AlertCircle className="h-3 w-3" />
                  Needs attention
                </span>
                <span className="text-[10px] text-warning font-medium">
                  {signals.isPackagingIssue ? "High CTR · Low retention" : "Low retention"}
                </span>
              </div>
              <p
                className="font-medium text-text-primary truncate"
                title={signals.needsAttention.title}
              >
                {signals.needsAttention.title}
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  );
};
