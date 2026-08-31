import {
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Loader2,
  RefreshCw,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import React, { useMemo, useState } from "react";
import type { components } from "../../api/generated";
import { getResolvedProvenance } from "../../lib/provenance";
import { AgentActionMenu } from "../AgentActionMenu";
type ChannelInsight = components["schemas"]["ChannelInsight"];
type ResearchFinding = components["schemas"]["ResearchFinding"];

interface AlexRailProps {
  insights: ChannelInsight[];
  findings: ResearchFinding[];
  lastResearchedAt?: string | null;
  cadence?: string | null;
  isResearching?: boolean;
  researchNotice?: string | null;
  researchError?: string | null;
  onTriggerResearch?: () => void;
  onOpenChat: () => void;
  onOpenSettings: () => void;
  onOpenEvidence: (insight: ChannelInsight) => void;
  onOpenAllFindings: () => void;
}

const formatDiscoveredAgo = (isoDate: string): string => {
  const discovered = new Date(isoDate);
  const diffMinutes = Math.max(1, Math.floor((Date.now() - discovered.getTime()) / 60000));
  if (diffMinutes < 60) return `Discovered ${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `Discovered ${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `Discovered ${diffDays}d ago`;
};
const formatLastResearched = (isoDate: string): string => {
  const researched = new Date(isoDate);
  const diffMinutes = Math.max(1, Math.floor((Date.now() - researched.getTime()) / 60000));
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
};

export const AlexRail: React.FC<AlexRailProps> = ({
  insights,
  findings,
  lastResearchedAt,
  cadence,
  isResearching = false,
  researchNotice = null,
  researchError = null,
  onTriggerResearch,
  onOpenChat,
  onOpenSettings,
  onOpenEvidence,
  onOpenAllFindings,
}) => {
  const [openSourcesMap, setOpenSourcesMap] = useState<Record<string, boolean>>({});

  const toggleSources = (findingId: string) => {
    setOpenSourcesMap((prev) => ({ ...prev, [findingId]: !prev[findingId] }));
  };

  // Diverse top findings
  const visibleFindings = useMemo(() => {
    const seenEntities = new Set<string>();
    const diverse: ResearchFinding[] = [];
    for (const f of findings) {
      const rawEntity =
        f.primary_entity || f.title.split(/[:\-—|]/)[0]?.trim() || f.category || "AI Topic";
      const entityKey = rawEntity.toLowerCase().replace(/[^a-z0-9]/g, "");
      if (!seenEntities.has(entityKey)) {
        seenEntities.add(entityKey);
        diverse.push(f);
      }
      if (diverse.length >= 3) break;
    }
    return diverse;
  }, [findings]);

  return (
    <aside
      className="w-full xl:w-[340px] 2xl:w-[360px] shrink-0 space-y-6 sticky top-20 self-start"
      style={{ position: "sticky", top: "80px", alignSelf: "start" }}
    >
      <div className="rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm space-y-5">
        {/* Alex Header with Canonical AgentActionMenu */}
        <div className="flex items-center justify-between border-b border-border-subtle pb-4">
          <AgentActionMenu
            agentId="alex"
            onChat={onOpenChat}
            onSettings={onOpenSettings}
            align="left"
          />
        </div>

        {/* Natural Prose Alex Insights */}
        {insights.length > 0 && (
          <div className="space-y-4">
            {insights.map((insight) => (
              <article
                key={insight.insight_id}
                className="rounded-lg bg-surface-2/50 p-4 text-xs space-y-3 border border-border-subtle/40"
              >
                <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-primary">
                  <TrendingUp className="h-3.5 w-3.5" />
                  <span>{insight.type}</span>
                </div>

                <h3 className="text-xs font-semibold leading-snug text-text-primary">
                  {insight.title}
                </h3>

                <p className="text-xs leading-relaxed text-text-secondary">{insight.statement}</p>

                <div className="rounded-md border-l-2 border-primary/70 bg-surface-3/60 px-3 py-2 text-xs leading-relaxed space-y-1">
                  <p className="font-semibold text-text-primary">Next</p>
                  <p className="text-text-secondary">
                    {insight.recommended_action.replace(/^(ACTION:\s*|Next:\s*)/i, "")}
                  </p>
                </div>

                <div className="flex items-center justify-between pt-1 text-[11px] text-text-muted">
                  <span>
                    {insight.evidence_stats
                      ? `Based on ${insight.evidence_stats.eligible_video_count} eligible videos`
                      : "Based on channel history"}
                  </span>
                  <button
                    type="button"
                    onClick={() => onOpenEvidence(insight)}
                    className="inline-flex items-center gap-1 text-primary hover:underline font-medium cursor-pointer"
                  >
                    <span>View evidence</span>
                    <ChevronRight className="h-3 w-3" />
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}

        {/* Ideas Worth Making */}
        <div className="border-t border-border-subtle pt-4 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <Sparkles className="h-4 w-4 text-primary shrink-0" />
              <h3 className="text-xs font-semibold text-text-primary truncate">
                Ideas Worth Making
              </h3>
            </div>
            {lastResearchedAt ? (
              <span
                className="text-[10px] text-text-muted font-mono shrink-0"
                title={`Cadence: ${cadence || "Hourly"}`}
              >
                Last researched: {formatLastResearched(lastResearchedAt)}
              </span>
            ) : findings.length > 0 ? (
              <span className="text-[11px] text-text-muted font-mono shrink-0">
                {findings.length} opportunities
              </span>
            ) : null}
          </div>

          {/* Action Row: Manual Research Trigger */}
          <div className="flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={onTriggerResearch}
              disabled={isResearching}
              className="flex items-center gap-1.5 rounded-lg border border-primary/30 bg-primary/10 hover:bg-primary/20 px-3 py-1.5 text-xs font-semibold text-primary transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              data-testid="btn-find-new-ideas"
              aria-label={isResearching ? "Researching…" : "Find new ideas"}
            >
              {isResearching ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-primary shrink-0" />
                  <span>Researching…</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-3.5 w-3.5 shrink-0" />
                  <span>Find new ideas</span>
                </>
              )}
            </button>
            {findings.length > 0 && lastResearchedAt && (
              <span className="text-[11px] text-text-muted font-mono shrink-0">
                {findings.length} opportunities
              </span>
            )}
          </div>

          {/* Research Notice (e.g. no new findings) */}
          {researchNotice && (
            <div
              className="rounded-lg border border-border-subtle bg-surface-2/70 p-2.5 text-xs text-text-secondary leading-relaxed animate-in fade-in"
              data-testid="research-notice"
            >
              {researchNotice}
            </div>
          )}

          {/* Research Error State with Retry */}
          {researchError && (
            <div
              className="rounded-lg border border-danger/30 bg-danger/10 p-2.5 text-xs text-danger space-y-1.5 animate-in fade-in"
              data-testid="research-error"
            >
              <p className="font-medium">{researchError}</p>
              <button
                type="button"
                onClick={onTriggerResearch}
                className="inline-flex items-center gap-1 font-semibold underline cursor-pointer text-text-primary hover:text-danger"
              >
                <RefreshCw className="h-3 w-3" />
                <span>Retry</span>
              </button>
            </div>
          )}
          {findings.length > 0 ? (
            <div className="space-y-3">
              {visibleFindings.map((finding) => (
                <article
                  key={finding.finding_id}
                  className="rounded-lg bg-surface-2/40 p-4 text-xs space-y-2.5 border border-border-subtle/50 transition-colors hover:border-border-strong hover:bg-surface-2/70"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded bg-surface-3 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
                      {finding.primary_entity || finding.category}
                    </span>
                    <span className="text-[11px] text-text-muted">
                      {formatDiscoveredAgo(finding.discovered_at)}
                    </span>
                  </div>

                  <h4 className="text-xs font-semibold leading-snug text-text-primary">
                    {finding.title}
                  </h4>

                  {/* Why it fits Croviq */}
                  <div className="rounded border-l-2 border-primary/50 bg-surface-3/50 px-3 py-2 text-xs leading-relaxed text-text-secondary">
                    <span className="font-semibold text-text-primary">Why it fits: </span>
                    <span>{finding.why_it_matters}</span>
                  </div>

                  {/* Why now */}
                  {finding.summary && (
                    <p className="text-xs leading-relaxed text-text-secondary">
                      <span className="font-semibold text-text-primary">Why now: </span>
                      <span>{finding.summary}</span>
                    </p>
                  )}

                  {/* Sources Pill & Popover */}
                  {(() => {
                    const prov = getResolvedProvenance(finding);
                    const totalCount =
                      (prov.discovery_signal ? 1 : 0) +
                      prov.primary_sources.length +
                      prov.supporting_sources.length;
                    if (totalCount === 0) return null;

                    const leadLabel = prov.discovery_signal
                      ? `Spotted on ${prov.discovery_signal.source_type}`
                      : prov.primary_sources[0]?.domain ||
                        prov.supporting_sources[0]?.domain ||
                        "Source";

                    const extraCount = totalCount - 1;

                    return (
                      <div className="pt-1">
                        <button
                          type="button"
                          onClick={() => toggleSources(finding.finding_id)}
                          className="inline-flex items-center gap-1 rounded bg-surface-3 px-2.5 py-1 text-[11px] font-medium text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
                        >
                          <span className="truncate max-w-[160px]">
                            {leadLabel}
                            {extraCount > 0 ? ` (+${extraCount})` : ""}
                          </span>
                          <ChevronDown
                            className={`h-3 w-3 transition-transform ${
                              openSourcesMap[finding.finding_id] ? "rotate-180" : ""
                            }`}
                          />
                        </button>

                        {openSourcesMap[finding.finding_id] && (
                          <div className="mt-2 space-y-2 rounded-md bg-surface-1 p-2.5 border border-border-subtle text-xs">
                            {prov.discovery_signal && (
                              <div className="space-y-1">
                                <p className="text-[9px] font-semibold uppercase tracking-wider text-text-muted">
                                  Discovered on {prov.discovery_signal.source_type}
                                </p>
                                <a
                                  href={prov.discovery_signal.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="flex items-center justify-between rounded px-2 py-1 text-xs text-text-secondary hover:bg-surface-2 hover:text-primary transition-colors"
                                >
                                  <span className="truncate max-w-[140px] font-medium">
                                    {prov.discovery_signal.title || prov.discovery_signal.domain}
                                  </span>
                                  <div className="flex items-center gap-1 shrink-0 text-text-muted text-[10px]">
                                    <span>{prov.discovery_signal.domain}</span>
                                    <ExternalLink className="h-3 w-3 shrink-0" />
                                  </div>
                                </a>
                              </div>
                            )}

                            {prov.primary_sources.length > 0 && (
                              <div className="space-y-1">
                                <p className="text-[9px] font-semibold uppercase tracking-wider text-text-muted">
                                  Primary Source
                                </p>
                                {prov.primary_sources.map((p) => (
                                  <a
                                    key={p.url}
                                    href={p.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center justify-between rounded px-2 py-1 text-xs text-text-secondary hover:bg-surface-2 hover:text-primary transition-colors"
                                  >
                                    <span className="truncate max-w-[140px] font-medium">
                                      {p.title || p.domain}
                                    </span>
                                    <div className="flex items-center gap-1 shrink-0 text-text-muted text-[10px]">
                                      <span>{p.domain}</span>
                                      <ExternalLink className="h-3 w-3 shrink-0" />
                                    </div>
                                  </a>
                                ))}
                              </div>
                            )}

                            {prov.supporting_sources.length > 0 && (
                              <div className="space-y-1">
                                <p className="text-[9px] font-semibold uppercase tracking-wider text-text-muted">
                                  Supporting Evidence
                                </p>
                                {prov.supporting_sources.map((s) => (
                                  <a
                                    key={s.url}
                                    href={s.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center justify-between rounded px-2 py-1 text-xs text-text-secondary hover:bg-surface-2 hover:text-primary transition-colors"
                                  >
                                    <span className="truncate max-w-[140px] font-medium">
                                      {s.title || s.domain}
                                    </span>
                                    <div className="flex items-center gap-1 shrink-0 text-text-muted text-[10px]">
                                      <span>{s.domain}</span>
                                      <ExternalLink className="h-3 w-3 shrink-0" />
                                    </div>
                                  </a>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </article>
              ))}

              {findings.length > 3 && (
                <button
                  type="button"
                  onClick={onOpenAllFindings}
                  className="w-full rounded-lg border border-border-subtle bg-surface-2/60 py-2.5 text-center text-xs font-medium text-text-secondary hover:bg-surface-2 hover:text-text-primary transition-colors cursor-pointer"
                >
                  View all {findings.length} findings
                </button>
              )}
            </div>
          ) : (
            <div className="rounded-lg bg-surface-2/30 p-4 text-center border border-border-subtle/40 space-y-1">
              <p className="text-xs font-medium text-text-secondary">
                Alex searched the configured sources but did not find a stronger new channel-fit
                opportunity.
              </p>
              <p className="text-[11px] text-text-muted">
                {lastResearchedAt
                  ? `Last checked ${formatLastResearched(lastResearchedAt)}.`
                  : "Click 'Find new ideas' to initiate research."}
              </p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};
