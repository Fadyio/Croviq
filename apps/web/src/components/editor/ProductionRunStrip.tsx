import React from "react";
import { AlertCircle, Check, Loader2 } from "lucide-react";
import { formatStageDuration, type ProductionRunStage } from "../../lib/production-run";

interface ProductionRunStripProps {
  stages: ProductionRunStage[];
}

export const ProductionRunStrip: React.FC<ProductionRunStripProps> = ({ stages }) => {
  const activeStage = stages.find((s) => s.status === "active");
  const failedStage = stages.find((s) => s.status === "failed");
  const isAllComplete = stages.every((s) => s.status === "completed");
  const totalDurationMs = stages.reduce((acc, s) => (s.durationMs ? acc + s.durationMs : acc), 0);

  return (
    <nav
      aria-label="Production run"
      className="border-b border-border-subtle bg-surface-1/95 px-4 sm:px-6 py-1.5 backdrop-blur-sm"
      data-testid="production-run-strip"
    >
      <div className="mx-auto flex w-full max-w-[1920px] items-center justify-between min-h-[28px]">
        <div className="flex items-center gap-2.5 min-w-0">
          {failedStage ? (
            <div className="flex items-center gap-2 text-xs font-semibold text-danger">
              <span className="flex size-4 items-center justify-center rounded-full bg-danger/15 text-danger border border-danger/30">
                <AlertCircle className="size-2.5" />
              </span>
              <span>Processing paused &middot; {failedStage.label}</span>
            </div>
          ) : activeStage ? (
            <div className="flex items-center gap-2.5 text-xs text-text-primary min-w-0">
              <span className="flex size-4 items-center justify-center rounded-full bg-primary/20 text-primary border border-primary/40 animate-pulse">
                <Loader2 className="size-2.5 animate-spin motion-reduce:animate-none" />
              </span>
              <span className="font-semibold tracking-tight text-text-primary">
                Croviq is editing your video
              </span>
              <span className="text-border-strong select-none">&middot;</span>
              <span className="text-text-secondary truncate text-[11px] font-medium">
                {activeStage.subStatus || activeStage.label}
              </span>
            </div>
          ) : isAllComplete ? (
            <div className="flex items-center gap-2 text-xs font-medium text-text-secondary">
              <span className="flex size-4 items-center justify-center rounded-full bg-success/15 text-success border border-success/30">
                <Check className="size-2.5" strokeWidth={2.5} />
              </span>
              <span className="font-semibold text-text-primary">Production complete</span>
              {totalDurationMs > 0 && (
                <>
                  <span className="text-border-strong select-none">&middot;</span>
                  <span className="text-text-muted text-[11px] tabular-nums">
                    {formatStageDuration(totalDurationMs)}
                  </span>
                </>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2 text-xs text-text-muted">
              <span className="size-2 rounded-full bg-surface-3" />
              <span>Ready to start production</span>
            </div>
          )}
        </div>

        {/* Hidden/accessible stage items for test selectors & telemetry */}
        <ol className="hidden">
          {stages.map((stage) => {
            const duration =
              stage.durationMs === undefined ? null : formatStageDuration(stage.durationMs);
            return (
              <li
                key={stage.id}
                data-status={stage.status}
                data-testid={`run-stage-${stage.id}`}
                title={duration ? `${stage.label} ${duration}` : stage.label}
              >
                {stage.label}
              </li>
            );
          })}
        </ol>
      </div>
    </nav>
  );
};
