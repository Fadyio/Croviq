import React, { useMemo, useState } from "react";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import type { components } from "../../api/generated";

type VideoPoint = components["schemas"]["VideoPerformancePoint"];

interface VideoPerformanceTableProps {
  data: VideoPoint[];
  medianCtr?: number;
  medianRetention?: number;
  onSelectVideo?: (video: VideoPoint) => void;
}

type SortField = "title" | "views" | "ctr_percentage" | "average_retention" | "subscribers_gained";
type SortOrder = "asc" | "desc";

const compactNumber = new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: 1,
});

export const VideoPerformanceTable: React.FC<VideoPerformanceTableProps> = ({
  data,
  medianCtr = 5.0,
  medianRetention = 55.0,
  onSelectVideo,
}) => {
  const [sortField, setSortField] = useState<SortField>("views");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortOrder("desc");
    }
  };

  const getStatusBadge = (video: VideoPoint) => {
    const ctr = video.ctr_percentage ?? 0;
    const isHighCtr = ctr >= medianCtr;
    const isHighRet = video.average_retention >= medianRetention;
    if (isHighCtr && isHighRet) {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-success/15 px-2 py-0.5 text-[10px] font-semibold text-success">
          Winner
        </span>
      );
    } else if (isHighCtr && !isHighRet) {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-warning/15 px-2 py-0.5 text-[10px] font-semibold text-warning">
          Packaging Works
        </span>
      );
    } else if (!isHighCtr && isHighRet) {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-semibold text-primary">
          Strong Content
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-surface-3 px-2 py-0.5 text-[10px] font-medium text-text-muted">
          Needs Work
        </span>
      );
    }
  };

  const sortedData = useMemo(() => {
    return [...data].sort((a, b) => {
      let aVal = a[sortField] ?? 0;
      let bVal = b[sortField] ?? 0;
      if (typeof aVal === "string") {
        aVal = aVal.toLowerCase();
        bVal = String(bVal).toLowerCase();
      }
      if (aVal < bVal) return sortOrder === "asc" ? -1 : 1;
      if (aVal > bVal) return sortOrder === "asc" ? 1 : -1;
      return 0;
    });
  }, [data, sortField, sortOrder]);

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) {
      return <ArrowUpDown className="h-3 w-3 text-text-muted opacity-40 group-hover:opacity-100" />;
    }
    return sortOrder === "asc" ? (
      <ArrowUp className="h-3 w-3 text-primary" />
    ) : (
      <ArrowDown className="h-3 w-3 text-primary" />
    );
  };

  return (
    <section
      className="rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm space-y-4"
      aria-labelledby="video-table-title"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2
            id="video-table-title"
            className="text-sm font-semibold tracking-tight text-text-primary"
          >
            Video Catalog Performance
          </h2>
          <p className="mt-0.5 text-xs text-text-muted">
            Detailed metrics, packaging conversion, and audience retention by video
          </p>
        </div>
        <span className="text-xs text-text-muted font-mono">{data.length} videos tracked</span>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border-subtle">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-border-subtle bg-surface-2/60 text-text-muted uppercase text-[10px] tracking-wider font-semibold">
            <tr>
              <th className="px-4 py-2.5">
                <button
                  type="button"
                  onClick={() => handleSort("title")}
                  className="group flex items-center gap-1 hover:text-text-primary transition-colors"
                >
                  <span>Video Title</span>
                  <SortIcon field="title" />
                </button>
              </th>
              <th className="px-3 py-2.5 text-right">
                <button
                  type="button"
                  onClick={() => handleSort("views")}
                  className="group ml-auto flex items-center gap-1 hover:text-text-primary transition-colors"
                >
                  <span>Views</span>
                  <SortIcon field="views" />
                </button>
              </th>
              <th className="px-3 py-2.5 text-right">
                <button
                  type="button"
                  onClick={() => handleSort("ctr_percentage")}
                  className="group ml-auto flex items-center gap-1 hover:text-text-primary transition-colors"
                >
                  <span>CTR</span>
                  <SortIcon field="ctr_percentage" />
                </button>
              </th>
              <th className="px-3 py-2.5 text-right">
                <button
                  type="button"
                  onClick={() => handleSort("average_retention")}
                  className="group ml-auto flex items-center gap-1 hover:text-text-primary transition-colors"
                >
                  <span>Retention</span>
                  <SortIcon field="average_retention" />
                </button>
              </th>
              <th className="px-3 py-2.5 text-right">
                <button
                  type="button"
                  onClick={() => handleSort("subscribers_gained")}
                  className="group ml-auto flex items-center gap-1 hover:text-text-primary transition-colors"
                >
                  <span>Net Subs</span>
                  <SortIcon field="subscribers_gained" />
                </button>
              </th>
              <th className="px-4 py-2.5 text-right">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle text-text-secondary">
            {sortedData.map((video) => (
              <tr
                key={video.video_id}
                onClick={() => onSelectVideo && onSelectVideo(video)}
                className="hover:bg-surface-2/40 transition-colors cursor-pointer"
              >
                <td className="px-4 py-3 min-w-[220px]">
                  <div className="font-medium text-text-primary line-clamp-1">{video.title}</div>
                  {video.content_pillar && (
                    <div className="mt-0.5 text-[10px] text-text-muted">{video.content_pillar}</div>
                  )}
                </td>
                <td className="px-3 py-3 text-right font-mono text-text-primary tabular-nums font-medium">
                  {compactNumber.format(video.views)}
                </td>
                <td className="px-3 py-3 text-right font-mono tabular-nums">
                  <span
                    className={
                      (video.ctr_percentage ?? 0) >= medianCtr
                        ? "text-success font-semibold"
                        : "text-text-secondary"
                    }
                  >
                    {video.ctr_percentage !== null && video.ctr_percentage !== undefined
                      ? `${video.ctr_percentage.toFixed(1)}%`
                      : "—"}
                  </span>
                </td>
                <td className="px-3 py-3 text-right font-mono tabular-nums">
                  <span
                    className={
                      video.average_retention >= medianRetention
                        ? "text-success font-semibold"
                        : "text-text-secondary"
                    }
                  >
                    {video.average_retention.toFixed(1)}%
                  </span>
                </td>
                <td className="px-3 py-3 text-right font-mono tabular-nums">
                  <span
                    className={
                      video.subscribers_gained >= 0
                        ? "text-text-primary font-medium"
                        : "text-danger font-medium"
                    }
                  >
                    {video.subscribers_gained >= 0 ? "+" : ""}
                    {video.subscribers_gained}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">{getStatusBadge(video)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};
