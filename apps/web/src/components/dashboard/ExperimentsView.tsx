import { Beaker, CheckCircle2, Clock, Sparkles } from "lucide-react";
import React from "react";
import type { components } from "../../api/generated";

type ChannelDashboard = components["schemas"]["ChannelDashboard"];
type ChannelExperiment = components["schemas"]["ChannelExperiment"];

interface ExperimentsViewProps {
  dashboard: ChannelDashboard;
}

export const ExperimentsView: React.FC<ExperimentsViewProps> = ({ dashboard }) => {
  const proposed = dashboard.proposed_experiment;
  const active = dashboard.active_experiment;

  const _hasAnyExperiment = Boolean(proposed || active);

  return (
    <div className="space-y-6">
      {/* Overview Header */}
      <div className="space-y-1">
        <h2 className="text-sm font-semibold tracking-tight text-text-primary">
          Channel Experiments & Causal Tests
        </h2>
        <p className="text-xs text-text-muted">
          Formulate falsifiable hypotheses, define quantitative baselines, and test editorial
          interventions with Alex.
        </p>
      </div>

      {/* Active Experiments Section */}
      <section className="space-y-3" aria-labelledby="active-exp-title">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-warning" />
          <h3
            id="active-exp-title"
            className="text-xs font-semibold uppercase tracking-wider text-text-secondary"
          >
            Active Experiments
          </h3>
        </div>

        {active ? (
          <ExperimentCard experiment={active} />
        ) : (
          <div className="rounded-xl border border-dashed border-border-subtle bg-surface-1/50 p-6 text-center">
            <p className="text-xs text-text-muted">
              No active experiment currently collecting live video cohorts.
            </p>
          </div>
        )}
      </section>

      {/* Proposed Experiments Section */}
      <section className="space-y-3" aria-labelledby="proposed-exp-title">
        <div className="flex items-center gap-2">
          <Beaker className="h-4 w-4 text-primary" />
          <h3
            id="proposed-exp-title"
            className="text-xs font-semibold uppercase tracking-wider text-text-secondary"
          >
            Proposed Experiments
          </h3>
        </div>

        {proposed ? (
          <ExperimentCard experiment={proposed} isProposed />
        ) : (
          <div className="rounded-xl border border-dashed border-border-subtle bg-surface-1/50 p-6 text-center">
            <p className="text-xs text-text-muted">
              Alex has no pending experiment proposals for this time period.
            </p>
          </div>
        )}
      </section>

      {/* Completed Experiments Section */}
      <section className="space-y-3" aria-labelledby="completed-exp-title">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-success" />
          <h3
            id="completed-exp-title"
            className="text-xs font-semibold uppercase tracking-wider text-text-secondary"
          >
            Completed Experiments & Lessons
          </h3>
        </div>

        <div className="rounded-xl border border-dashed border-border-subtle bg-surface-1/50 p-6 text-center">
          <p className="text-xs text-text-muted">
            Completed experimental findings are distilled into Alex long-term memory directives.
          </p>
        </div>
      </section>
    </div>
  );
};

const ExperimentCard: React.FC<{ experiment: ChannelExperiment; isProposed?: boolean }> = ({
  experiment,
  isProposed = false,
}) => {
  return (
    <article className="rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle pb-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/15 text-primary font-bold text-xs">
            <Beaker className="h-3.5 w-3.5" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-text-primary">
              {experiment.primary_metric === "averageViewPercentage"
                ? "First-Demo Timing & Viewer Retention Test"
                : "Thumbnail Packaging Conversion Test"}
            </h4>
            <span className="text-[11px] text-text-muted">
              Created by {experiment.created_by.toUpperCase()} · Falsifiable statistical trial
            </span>
          </div>
        </div>

        <span
          className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
            isProposed
              ? "bg-primary/10 border border-primary/20 text-primary"
              : "bg-warning/10 border border-warning/20 text-warning"
          }`}
        >
          {experiment.status}
        </span>
      </div>

      {/* Hypothesis */}
      <div className="space-y-1">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
          Hypothesis
        </span>
        <p className="text-xs text-text-secondary leading-relaxed font-normal">
          {experiment.hypothesis}
        </p>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 rounded-lg bg-surface-2/60 p-3 text-xs border border-border-subtle">
        <div>
          <span className="text-[10px] text-text-muted block font-medium">Primary metric</span>
          <span className="font-medium text-text-primary mt-0.5 block truncate">
            {experiment.primary_metric === "averageViewPercentage"
              ? "Average Retention"
              : experiment.primary_metric}
          </span>
        </div>
        <div>
          <span className="text-[10px] text-text-muted block font-medium">Baseline</span>
          <span className="font-mono font-medium text-text-primary mt-0.5 block">
            {experiment.baseline_value.toFixed(1)}%
          </span>
        </div>
        <div>
          <span className="text-[10px] text-text-muted block font-medium">Expected direction</span>
          <span className="font-medium text-success mt-0.5 block">
            {experiment.expected_direction}
          </span>
        </div>
        <div>
          <span className="text-[10px] text-text-muted block font-medium">Cohort sample</span>
          <span className="font-mono text-text-secondary mt-0.5 block">
            {experiment.video_ids.length > 0
              ? `${experiment.video_ids.length} videos`
              : "Next upload"}
          </span>
        </div>
      </div>

      {/* Alex Recommendation & Confidence */}
      {experiment.confidence_summary && (
        <div className="rounded-lg border-l-2 border-primary/70 bg-surface-3/50 p-3 text-xs leading-relaxed">
          <div className="flex items-center gap-1.5 font-semibold text-text-primary mb-1">
            <Sparkles className="h-3 w-3 text-primary" />
            <span>Alex Data Scientist Assessment</span>
          </div>
          <span className="text-text-secondary text-[11px]">{experiment.confidence_summary}</span>
        </div>
      )}
    </article>
  );
};
