import React, { useMemo } from "react";
import type { EChartsOption } from "echarts";
import type { components } from "../../api/generated";
import { EChartsWrapper, GRAPHITE_THEME } from "../charts/EChartsWrapper";

type VideoPoint = components["schemas"]["VideoPerformancePoint"];

interface VideoPerformanceQuadrantProps {
  data: VideoPoint[];
  onSelectVideo?: (video: VideoPoint) => void;
}

const compactNumber = new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const calculateMedian = (values: number[]): number => {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
};

export const VideoPerformanceQuadrant: React.FC<VideoPerformanceQuadrantProps> = ({
  data,
  onSelectVideo,
}) => {
  const ctrs = useMemo(() => data.map((v) => v.ctr_percentage ?? 0), [data]);
  const retentions = useMemo(() => data.map((v) => v.average_retention), [data]);
  const viewsList = useMemo(() => data.map((v) => v.views), [data]);

  const medianCtr = useMemo(() => calculateMedian(ctrs), [ctrs]);
  const medianRetention = useMemo(() => calculateMedian(retentions), [retentions]);
  const maxViews = useMemo(() => Math.max(...viewsList, 1000), [viewsList]);
  const minViews = useMemo(() => Math.min(...viewsList, 100), [viewsList]);

  const chartOption = useMemo<EChartsOption>(() => {
    // Determine quadrant and color per point
    const pointsData = data.map((v) => {
      const ctr = v.ctr_percentage ?? 0;
      const isHighCtr = ctr >= medianCtr;
      const isHighRet = v.average_retention >= medianRetention;
      let color = GRAPHITE_THEME.primary;
      let quadrantLabel = "Winner";
      if (isHighCtr && isHighRet) {
        color = GRAPHITE_THEME.success; // Winner
        quadrantLabel = "High CTR · High Retention (Winner)";
      } else if (isHighCtr && !isHighRet) {
        color = GRAPHITE_THEME.warning; // Packaging works, content drops
        quadrantLabel = "High CTR · Low Retention (Packaging works)";
      } else if (!isHighCtr && isHighRet) {
        color = GRAPHITE_THEME.primary; // Strong video, weak packaging
        quadrantLabel = "Low CTR · High Retention (Strong content)";
      } else {
        color = GRAPHITE_THEME.textMuted; // Needs work
        quadrantLabel = "Low CTR · Low Retention (Needs work)";
      }

      // Scale bubble size between 12px and 34px
      const sizeNormalized =
        maxViews > minViews ? (v.views - minViews) / (maxViews - minViews) : 0.5;
      const bubbleSize = Math.round(14 + sizeNormalized * 22);

      return {
        name: v.title,
        value: [ctr, v.average_retention, v.views, bubbleSize, v.video_id, quadrantLabel],
        itemStyle: {
          color: color,
          opacity: 0.85,
          borderColor: GRAPHITE_THEME.borderStrong,
          borderWidth: 1,
        },
      };
    });

    const minCtr = Math.max(0, Math.min(...ctrs, 2) - 1);
    const maxCtr = Math.max(...ctrs, 8) + 1.5;
    const minRet = Math.max(0, Math.min(...retentions, 30) - 5);
    const maxRet = Math.min(100, Math.max(...retentions, 70) + 5);

    return {
      backgroundColor: GRAPHITE_THEME.background,
      animation: false,
      grid: {
        top: 36,
        right: 32,
        bottom: 48,
        left: 54,
      },
      tooltip: {
        trigger: "item",
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
          const item = params as {
            name: string;
            value: [number, number, number, number, string, string];
          };
          if (!item || !item.value) return "";
          const [ctr, ret, views, , , quadLabel] = item.value;
          const ctrDiff = ctr - medianCtr;
          const retDiff = ret - medianRetention;

          return `
            <div style="font-weight: 600; margin-bottom: 6px; color: ${GRAPHITE_THEME.textPrimary}; font-size: 12px; max-width: 260px; word-break: break-word;">
              ${item.name}
            </div>
            <div style="margin-bottom: 8px; font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: ${GRAPHITE_THEME.textSecondary};">
              ${quadLabel}
            </div>
            <div style="display: grid; grid-template-columns: auto auto; gap: 4px 16px; font-size: 11px;">
              <span style="color: ${GRAPHITE_THEME.textMuted};">Views:</span>
              <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 600; color: ${GRAPHITE_THEME.textPrimary}; text-align: right;">${views.toLocaleString()}</span>
              
              <span style="color: ${GRAPHITE_THEME.textMuted};">Thumbnail CTR:</span>
              <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 600; color: ${GRAPHITE_THEME.textPrimary}; text-align: right;">
                ${ctr.toFixed(1)}% <span style="font-size: 10px; color: ${ctrDiff >= 0 ? GRAPHITE_THEME.success : GRAPHITE_THEME.danger};">(${ctrDiff >= 0 ? "+" : ""}${ctrDiff.toFixed(1)}% vs median)</span>
              </span>

              <span style="color: ${GRAPHITE_THEME.textMuted};">Avg Retention:</span>
              <span style="font-family: ${GRAPHITE_THEME.monoFontFamily}; font-weight: 600; color: ${GRAPHITE_THEME.textPrimary}; text-align: right;">
                ${ret.toFixed(1)}% <span style="font-size: 10px; color: ${retDiff >= 0 ? GRAPHITE_THEME.success : GRAPHITE_THEME.danger};">(${retDiff >= 0 ? "+" : ""}${retDiff.toFixed(1)}% vs median)</span>
              </span>
            </div>
          `;
        },
      },
      xAxis: {
        type: "value",
        name: "Thumbnail CTR (%)",
        nameLocation: "middle",
        nameGap: 30,
        nameTextStyle: {
          color: GRAPHITE_THEME.textSecondary,
          fontSize: 11,
          fontFamily: GRAPHITE_THEME.fontFamily,
        },
        min: minCtr,
        max: maxCtr,
        axisLine: {
          lineStyle: { color: GRAPHITE_THEME.borderSubtle },
        },
        axisLabel: {
          color: GRAPHITE_THEME.textMuted,
          fontSize: 10,
          fontFamily: GRAPHITE_THEME.monoFontFamily,
          formatter: "{value}%",
        },
        splitLine: {
          lineStyle: {
            color: GRAPHITE_THEME.borderSubtle,
            type: "dashed",
            opacity: 0.6,
          },
        },
      },
      yAxis: {
        type: "value",
        name: "Average Retention (%)",
        nameLocation: "middle",
        nameGap: 38,
        nameTextStyle: {
          color: GRAPHITE_THEME.textSecondary,
          fontSize: 11,
          fontFamily: GRAPHITE_THEME.fontFamily,
        },
        min: minRet,
        max: maxRet,
        axisLine: { show: false },
        axisLabel: {
          color: GRAPHITE_THEME.textMuted,
          fontSize: 10,
          fontFamily: GRAPHITE_THEME.monoFontFamily,
          formatter: "{value}%",
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
        {
          name: "Video Performance",
          type: "scatter",
          data: pointsData,
          symbolSize: (dataVal: number[]) => dataVal[3] || 16,
          markLine: {
            silent: true,
            symbol: "none",
            lineStyle: {
              color: GRAPHITE_THEME.borderStrong,
              type: "dashed",
              width: 1.5,
            },
            data: [
              {
                xAxis: medianCtr,
                label: {
                  formatter: `Median CTR: ${medianCtr.toFixed(1)}%`,
                  position: "end",
                  color: GRAPHITE_THEME.textMuted,
                  fontSize: 10,
                  fontFamily: GRAPHITE_THEME.monoFontFamily,
                },
              },
              {
                yAxis: medianRetention,
                label: {
                  formatter: `Median Ret: ${medianRetention.toFixed(1)}%`,
                  position: "end",
                  color: GRAPHITE_THEME.textMuted,
                  fontSize: 10,
                  fontFamily: GRAPHITE_THEME.monoFontFamily,
                },
              },
            ],
          },
          markArea: {
            silent: true,
            itemStyle: {
              opacity: 0.04,
            },
            data: [
              [
                {
                  name: "Strong Content\n(Packaging bottleneck)",
                  xAxis: minCtr,
                  yAxis: medianRetention,
                  itemStyle: { color: GRAPHITE_THEME.primary },
                  label: {
                    position: "insideTopLeft",
                    color: GRAPHITE_THEME.textMuted,
                    fontSize: 10,
                    fontFamily: GRAPHITE_THEME.fontFamily,
                  },
                },
                {
                  xAxis: medianCtr,
                  yAxis: maxRet,
                },
              ],
              [
                {
                  name: "Winners\n(High CTR & Retention)",
                  xAxis: medianCtr,
                  yAxis: medianRetention,
                  itemStyle: { color: GRAPHITE_THEME.success },
                  label: {
                    position: "insideTopRight",
                    color: GRAPHITE_THEME.textMuted,
                    fontSize: 10,
                    fontFamily: GRAPHITE_THEME.fontFamily,
                  },
                },
                {
                  xAxis: maxCtr,
                  yAxis: maxRet,
                },
              ],
              [
                {
                  name: "Needs Work\n(Low CTR & Retention)",
                  xAxis: minCtr,
                  yAxis: minRet,
                  itemStyle: { color: GRAPHITE_THEME.background },
                  label: {
                    position: "insideBottomLeft",
                    color: GRAPHITE_THEME.textMuted,
                    fontSize: 10,
                    fontFamily: GRAPHITE_THEME.fontFamily,
                  },
                },
                {
                  xAxis: medianCtr,
                  yAxis: medianRetention,
                },
              ],
              [
                {
                  name: "Packaging Works\n(Retention bottleneck)",
                  xAxis: medianCtr,
                  yAxis: minRet,
                  itemStyle: { color: GRAPHITE_THEME.warning },
                  label: {
                    position: "insideBottomRight",
                    color: GRAPHITE_THEME.textMuted,
                    fontSize: 10,
                    fontFamily: GRAPHITE_THEME.fontFamily,
                  },
                },
                {
                  xAxis: maxCtr,
                  yAxis: medianRetention,
                },
              ],
            ],
          },
        },
      ],
    };
  }, [data, ctrs, retentions, medianCtr, medianRetention, maxViews, minViews]);

  return (
    <section
      className="rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm space-y-4"
      aria-labelledby="quadrant-title"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2
            id="quadrant-title"
            className="text-sm font-semibold tracking-tight text-text-primary"
          >
            Video Performance Quadrant
          </h2>
          <p className="mt-0.5 text-xs text-text-muted">
            Packaging vs Content Retention relationship with channel medians (bubble size represents
            views)
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-[11px] text-text-muted">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-success" />
            Winners
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-primary" />
            Strong Content
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-warning" />
            Strong Packaging
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-text-muted" />
            Needs Work
          </span>
        </div>
      </div>

      <div className="h-80 sm:h-96 w-full">
        <EChartsWrapper
          option={chartOption}
          ariaLabel="Video Performance Quadrant Chart"
          onChartClick={(params) => {
            const dataVal = (params.data as { value?: [number, number, number, number, string] })
              ?.value;
            if (dataVal && dataVal[4] && onSelectVideo) {
              const selected = data.find((v) => v.video_id === dataVal[4]);
              if (selected) onSelectVideo(selected);
            }
          }}
        />
      </div>
    </section>
  );
};
