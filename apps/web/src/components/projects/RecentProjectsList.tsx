import { Clock, Film, Play, Trash2, Video } from "lucide-react";
import React from "react";
import type { components } from "../../api/generated";

type Production = components["schemas"]["Production"];

interface RecentProjectsListProps {
  productions: Production[];
  isLoading?: boolean;
  onOpenProject: (productionId: string) => void;
  onDeleteProject?: (productionId: string, filename: string) => void;
}

const formatBytes = (bytes?: number | null): string => {
  if (!bytes || bytes <= 0) return "";
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(1)} MB`;
};

const formatDate = (isoDate: string): string => {
  try {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
    }).format(new Date(isoDate));
  } catch {
    return isoDate;
  }
};

export const RecentProjectsList: React.FC<RecentProjectsListProps> = ({
  productions,
  isLoading = false,
  onOpenProject,
  onDeleteProject,
}) => {
  if (isLoading) {
    return (
      <div className="rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm space-y-3">
        <div className="h-4 w-32 bg-surface-3 animate-pulse rounded" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-14 bg-surface-2 animate-pulse rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  // Show up to 5 recent productions
  const recentList = productions.slice(0, 5);

  return (
    <section
      className="rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm space-y-4"
      aria-labelledby="recent-projects-heading"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Film className="h-4 w-4 text-primary" />
          <h2
            id="recent-projects-heading"
            className="text-sm font-semibold tracking-tight text-text-primary"
          >
            Recent projects
          </h2>
        </div>
        {productions.length > 0 && (
          <span className="text-xs text-text-muted font-mono">
            {productions.length} productions
          </span>
        )}
      </div>

      {recentList.length > 0 ? (
        <div className="space-y-2">
          {recentList.map((prod) => (
            <div
              key={prod.production_id}
              onClick={() => onOpenProject(prod.production_id)}
              className="group flex items-center justify-between gap-3 rounded-lg border border-border-subtle/70 bg-surface-2/40 p-3 text-xs transition-colors hover:border-border-strong hover:bg-surface-2 cursor-pointer"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-3 text-text-secondary group-hover:bg-primary/20 group-hover:text-primary transition-colors">
                  <Video className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <span className="block truncate font-medium text-text-primary group-hover:text-primary transition-colors">
                    {prod.source_media?.original_filename ||
                      `Production ${prod.production_id.slice(-6)}`}
                  </span>
                  <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-text-muted">
                    {prod.source_media?.size_bytes ? (
                      <>
                        <span>{formatBytes(prod.source_media.size_bytes)}</span>
                        <span>·</span>
                      </>
                    ) : null}
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatDate(prod.created_at)}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <span className="rounded-full bg-surface-3 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-text-muted">
                  {prod.status}
                </span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpenProject(prod.production_id);
                  }}
                  className="flex items-center gap-1 rounded-md bg-surface-3 px-2.5 py-1 text-xs font-semibold text-text-primary hover:bg-primary hover:text-white transition-colors cursor-pointer"
                >
                  <Play className="h-3 w-3 fill-current" />
                  <span>Open &gt;</span>
                </button>
                {onDeleteProject && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteProject(
                        prod.production_id,
                        prod.source_media?.original_filename ||
                          `Production ${prod.production_id.slice(-6)}`,
                      );
                    }}
                    className="p-1 text-text-muted hover:text-danger hover:bg-danger/10 rounded-md transition-colors cursor-pointer"
                    title="Delete project"
                    aria-label={`Delete ${prod.source_media?.original_filename || prod.production_id}`}
                    data-testid={`btn-delete-${prod.production_id}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-lg bg-surface-2/30 p-6 text-center border border-dashed border-border-subtle">
          <p className="text-xs text-text-muted">No recent productions found in this workspace.</p>
        </div>
      )}
    </section>
  );
};
