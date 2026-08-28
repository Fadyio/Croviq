import React, { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart, ScatterChart, BarChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  MarkAreaComponent,
  DatasetComponent,
  GraphicComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsOption } from "echarts";

// Register tree-shakeable components once
echarts.use([
  LineChart,
  ScatterChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  MarkAreaComponent,
  DatasetComponent,
  GraphicComponent,
  CanvasRenderer,
]);

export interface EChartsWrapperProps {
  option: EChartsOption;
  height?: string | number;
  className?: string;
  ariaLabel?: string;
  onChartClick?: (params: echarts.ECElementEvent) => void;
}

export const GRAPHITE_THEME = {
  background: "transparent",
  borderSubtle: "#22272f",
  borderStrong: "#323a45",
  textPrimary: "#f3f5f7",
  textSecondary: "#9da7b3",
  textMuted: "#646e7b",
  primary: "#2563eb",
  primaryHover: "#1d4ed8",
  success: "#10b981",
  warning: "#f59e0b",
  danger: "#ef4444",
  tooltipBg: "#171b20",
  fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  monoFontFamily: "'JetBrains Mono', ui-monospace, SF Mono, Menlo, Consolas, monospace",
};

export const EChartsWrapper: React.FC<EChartsWrapperProps> = ({
  option,
  height = "100%",
  className = "w-full",
  ariaLabel = "Chart visualization",
  onChartClick,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = echarts.init(containerRef.current, undefined, {
      renderer: "canvas",
    });
    chartInstanceRef.current = chart;

    if (onChartClick) {
      chart.on("click", onChartClick);
    }

    const resizeObserver = new ResizeObserver(() => {
      chart.resize({
        animation: { duration: 150 },
      });
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      if (onChartClick) {
        chart.off("click", onChartClick);
      }
      chart.dispose();
      chartInstanceRef.current = null;
    };
  }, [onChartClick]);

  useEffect(() => {
    if (chartInstanceRef.current) {
      chartInstanceRef.current.setOption(option, { notMerge: true });
    }
  }, [option]);

  return (
    <div
      ref={containerRef}
      style={{ height, minHeight: typeof height === "number" ? `${height}px` : height }}
      className={`relative select-none ${className}`}
      role="img"
      aria-label={ariaLabel}
    />
  );
};
