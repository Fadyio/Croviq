import React from "react";
import type { components } from "../../api/generated";
import { ChannelTrendChart } from "./ChannelTrendChart";
import { VideoPerformanceRankedChart } from "./VideoPerformanceRankedChart";
import { VideoPerformanceTable } from "./VideoPerformanceTable";
import { TrafficSourceChart } from "./TrafficSourceChart";

type ChannelDashboard = components["schemas"]["ChannelDashboard"];
type VideoPoint = components["schemas"]["VideoPerformancePoint"];

interface PerformanceViewProps {
  dashboard: ChannelDashboard;
  onSelectVideo?: (video: VideoPoint) => void;
}

export const PerformanceView: React.FC<PerformanceViewProps> = ({ dashboard, onSelectVideo }) => {
  // Compute channel median CTR and retention
  const ctrs = dashboard.video_performance.map((v) => v.ctr_percentage ?? 0);
  const retentions = dashboard.video_performance.map((v) => v.average_retention);
  const calculateMedian = (values: number[]): number => {
    if (!values.length) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  };

  const medianCtr = calculateMedian(ctrs);
  const medianRetention = calculateMedian(retentions);

  return (
    <div className="space-y-6">
      {/* 1. Dominant Channel Performance Chart */}
      <ChannelTrendChart data={dashboard.trend} title="Channel Performance Over Time" />

      {/* 2. Video Performance Ranked Bar Chart */}
      <VideoPerformanceRankedChart
        data={dashboard.video_performance}
        onSelectVideo={onSelectVideo}
      />

      {/* 3. Sortable Video Catalog Table */}
      <VideoPerformanceTable
        data={dashboard.video_performance}
        medianCtr={medianCtr}
        medianRetention={medianRetention}
        onSelectVideo={onSelectVideo}
      />

      {/* 4. Traffic Sources Bar Chart */}
      <TrafficSourceChart data={dashboard.traffic_sources} />
    </div>
  );
};
