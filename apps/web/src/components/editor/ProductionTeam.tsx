import React from "react";
import { Scissors, Clapperboard, CheckCircle2 } from "lucide-react";
import type { EditorProposal, DirectorReview } from "../../lib/edl-adapter";

interface ProductionTeamProps {
  proposal?: EditorProposal | null;
  review?: DirectorReview | null;
  activeAgent?: "leo" | "maya" | null;
  className?: string;
}

export const ProductionTeam: React.FC<ProductionTeamProps> = ({
  proposal,
  review,
  activeAgent = null,
  className = "",
}) => {
  const proposalCount = proposal?.decisions?.length || 0;
  const approvedCount = review?.decisions?.filter((d) => d.verdict === "APPROVE").length || 0;

  return (
    <div
      className={`p-3 bg-surface-1 rounded-xl border border-border-subtle flex flex-col gap-2.5 shadow-sm ${className}`}
      data-testid="production-team"
    >
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold text-text-primary flex items-center gap-1.5">
          <Clapperboard className="w-3.5 h-3.5 text-primary" />
          <span>Autonomous Editorial Team</span>
        </span>
        <span className="text-[10px] font-mono text-success flex items-center gap-1 bg-success/10 px-1.5 py-0.2 rounded border border-success/20">
          <CheckCircle2 className="w-3 h-3" />
          <span>Review Completed</span>
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {/* Leo: Dialogue Editor */}
        <div
          className={`p-2.5 rounded-lg border transition-all flex flex-col gap-1 ${
            activeAgent === "leo"
              ? "bg-surface-2 border-primary ring-1 ring-primary/30"
              : "bg-surface-2/60 border-border-subtle hover:border-border-strong"
          }`}
          data-testid="agent-card-leo"
        >
          <div className="flex items-center gap-2">
            {/* Neutral Local Avatar Badge */}
            <div className="w-6 h-6 rounded-full bg-primary/20 text-primary border border-primary/30 flex items-center justify-center text-[10px] font-bold shrink-0">
              L
            </div>
            <div className="min-w-0 flex flex-col">
              <span className="text-xs font-semibold text-text-primary truncate">Leo</span>
              <span className="text-[10px] text-text-muted leading-none">Dialogue Editor</span>
            </div>
          </div>
          <p className="text-[10px] text-text-secondary mt-0.5">
            {proposalCount > 0
              ? `${proposalCount} editorial decisions`
              : "Analyzing pacing & speech"}
          </p>
        </div>

        {/* Maya: Director */}
        <div
          className={`p-2.5 rounded-lg border transition-all flex flex-col gap-1 ${
            activeAgent === "maya"
              ? "bg-surface-2 border-primary ring-1 ring-primary/30"
              : "bg-surface-2/60 border-border-subtle hover:border-border-strong"
          }`}
          data-testid="agent-card-maya"
        >
          <div className="flex items-center gap-2">
            {/* Neutral Local Avatar Badge */}
            <div className="w-6 h-6 rounded-full bg-info/20 text-info border border-info/30 flex items-center justify-center text-[10px] font-bold shrink-0">
              M
            </div>
            <div className="min-w-0 flex flex-col">
              <span className="text-xs font-semibold text-text-primary truncate">Maya</span>
              <span className="text-[10px] text-text-muted leading-none">Director</span>
            </div>
          </div>
          <p className="text-[10px] text-text-secondary mt-0.5">
            {approvedCount > 0 ? `${approvedCount} decisions approved` : "Director review"}
          </p>
        </div>
      </div>
    </div>
  );
};
