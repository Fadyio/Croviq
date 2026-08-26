import React from "react";
import { AlertCircle, Check, Loader2 } from "lucide-react";
import { formatStageDuration, type ProductionRunStage } from "../../lib/production-run";

interface ProductionRunStripProps {
  stages: ProductionRunStage[];
}

export const ProductionRunStrip: React.FC<ProductionRunStripProps> = ({ stages }) => (
  <nav
    aria-label="Production run"
    className="border-b border-border-subtle bg-surface-1/95 px-4 sm:px-6"
    data-testid="production-run-strip"
  >
    <ol className="mx-auto flex h-10 w-full max-w-[1920px] items-center overflow-x-auto">
      {stages.map((stage, index) => {
        const duration =
          stage.durationMs === undefined ? null : formatStageDuration(stage.durationMs);
        return (
          <li
            key={stage.id}
            className="flex min-w-0 shrink-0 items-center"
            data-status={stage.status}
            data-testid={`run-stage-${stage.id}`}
            title={duration ? `${stage.label} ${duration}` : stage.label}
          >
            {index > 0 && (
              <span
                aria-hidden="true"
                className={`mx-2 h-px w-4 sm:w-7 ${
                  stage.status === "completed" ? "bg-text-muted/55" : "bg-border-subtle"
                }`}
              />
            )}
            <span
              className={`flex items-center gap-1.5 text-[11px] font-medium whitespace-nowrap ${
                stage.status === "failed"
                  ? "text-danger"
                  : stage.status === "active"
                    ? "text-text-primary"
                    : stage.status === "completed"
                      ? "text-text-secondary"
                      : "text-text-muted/65"
              }`}
            >
              <span
                className={`flex size-4 items-center justify-center rounded-full border ${
                  stage.status === "completed"
                    ? "border-success/40 bg-success/10 text-success"
                    : stage.status === "active"
                      ? "border-primary/40 bg-primary/10 text-primary"
                      : stage.status === "failed"
                        ? "border-danger/40 bg-danger/10 text-danger"
                        : "border-border-subtle text-text-muted/50"
                }`}
              >
                {stage.status === "completed" ? (
                  <Check className="size-2.5" strokeWidth={2.5} />
                ) : stage.status === "active" ? (
                  <Loader2 className="size-2.5 animate-spin motion-reduce:animate-none" />
                ) : stage.status === "failed" ? (
                  <AlertCircle className="size-2.5" />
                ) : (
                  <span className="size-1 rounded-full bg-current" />
                )}
              </span>
              {stage.id === "render" && stage.status === "active" && stage.subStatus
                ? stage.subStatus
                : stage.label}
            </span>
          </li>
        );
      })}
    </ol>
  </nav>
);
