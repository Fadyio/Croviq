import React, { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, ExternalLink, Info, Radio, TrendingUp } from "lucide-react";
import type { components } from "../../api/generated";
import alexAvatar from "../../assets/agents/alex.webp";

type ChannelInsight = components["schemas"]["ChannelInsight"];
type ResearchFinding = components["schemas"]["ResearchFinding"];

interface AlexRailProps {
  insights: ChannelInsight[];
  findings: ResearchFinding[];
  onOpenChat?: () => void;
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

export const AlexRail: React.FC<AlexRailProps> = ({
  insights,
  findings,
  onOpenChat,
  onOpenSettings,
  onOpenEvidence,
  onOpenAllFindings,
}) => {
  const [openSourcesMap, setOpenSourcesMap] = useState<Record<string, boolean>>({});

  const toggleSources = (findingId: string) => {
    setOpenSourcesMap((prev) => ({ ...prev, [findingId]: !prev[findingId] }));
  };

  // Strict Diversity Rule (Phase 18): Maximum ONE card per primary_entity in top 3
  const visibleFindings = useMemo(() => {
    const seenEntities = new Set<string>();
    const diverse: ResearchFinding[] = [];
    for (const f of findings) {
      // Normalize entity identity (using primary_entity or leading subject phrase)
      const rawEntity =
        f.primary_entity || f.title.split(/[:\-\—|]/)[0]?.trim() || f.category || "AI Topic";
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
    <aside className="w-full xl:w-[340px] 2xl:w-[360px] shrink-0 space-y-6 xl:sticky xl:top-20 xl:self-start xl:max-h-[calc(100vh-6rem)] xl:overflow-y-auto">
      <div className="rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-sm space-y-5">
        {/* Alex Header */}
        <div className="flex items-center justify-between border-b border-border-subtle pb-4">
          <button
            type="button"
            onClick={onOpenChat}
            className="flex items-center gap-3 text-left transition-opacity hover:opacity-80 cursor-pointer"
            title="Open Alex workspace & chat"
            aria-label="Open Alex workspace"
          >
            <img
              src={alexAvatar}
              alt="Alex"
              className="h-10 w-10 rounded-full object-cover ring-2 ring-primary/20"
            />
            <div>
              <h2 className="text-sm font-semibold text-text-primary hover:text-primary transition-colors">
                Alex
              </h2>
              <p className="text-xs text-text-muted">Data Scientist · Chat</p>
            </div>
          </button>
          <button
            type="button"
            onClick={onOpenSettings}
            className="rounded-lg p-1.5 text-text-muted transition-colors hover:bg-surface-2 hover:text-text-primary cursor-pointer"
            title="Configure Alex settings & memory"
            aria-label="Open Alex settings"
            data-testid="btn-alex-settings"
          >
            <Info className="h-4 w-4" />
          </button>
        </div>

        {/* Natural Prose Alex Insights */}
        {insights.length > 0 && (
          <div className="space-y-4">
            {insights.map((insight) => (
              <article
                key={insight.insight_id}
                className="rounded-lg bg-surface-2/40 p-4 text-xs space-y-3"
              >
                <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
                  <TrendingUp className="h-3 w-3" />
                  <span>{insight.type}</span>
                </div>

                <h3 className="text-xs font-semibold leading-snug text-text-primary">
                  {insight.title}
                </h3>

                <p className="text-[11px] leading-relaxed text-text-secondary">
                  {insight.statement}
                </p>

                <div className="rounded-md border-l-2 border-primary/70 bg-surface-3/50 px-3 py-2 text-[11px] leading-relaxed">
                  <span className="font-semibold text-text-primary">Next: </span>
                  <span className="text-text-secondary">{insight.recommended_action}</span>
                </div>

                <div className="flex items-center justify-between pt-1 text-[10px] text-text-muted">
                  <span>Based on channel history</span>
                  <button
                    type="button"
                    onClick={() => onOpenEvidence(insight)}
                    className="inline-flex items-center gap-1 text-primary hover:underline font-medium"
                  >
                    <span>View evidence</span>
                    <ChevronRight className="h-3 w-3" />
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}

        {/* Worth Watching / Topic Radar */}
        <div className="border-t border-border-subtle pt-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Radio className="h-3.5 w-3.5 text-primary" />
              <h3 className="text-xs font-semibold text-text-primary">Worth watching</h3>
            </div>
            {findings.length > 0 && (
              <span className="text-[10px] text-text-muted font-mono">
                {findings.length} findings
              </span>
            )}
          </div>

          {findings.length > 0 ? (
            <div className="space-y-3">
              {visibleFindings.map((finding) => (
                <article
                  key={finding.finding_id}
                  className="rounded-lg bg-surface-2/40 p-3.5 text-xs space-y-2 border border-border-subtle/50"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded bg-surface-3 px-1.5 py-0.5 text-[9px] font-medium text-text-muted">
                      {finding.category}
                    </span>
                    <span className="text-[10px] text-text-muted">
                      {formatDiscoveredAgo(finding.discovered_at)}
                    </span>
                  </div>

                  <h4 className="text-xs font-semibold leading-snug text-text-primary">
                    {finding.title}
                  </h4>

                  <div className="rounded border-l-2 border-border-strong bg-surface-3/40 px-2.5 py-1.5 text-[10px] leading-relaxed text-text-secondary">
                    <span className="font-semibold text-text-primary">Why it matters: </span>
                    <span>{finding.why_it_matters}</span>
                  </div>

                  {/* Citation Sources Pill & Popover */}
                  {finding.source_citations.length > 0 && (
                    <div className="pt-1">
                      <button
                        type="button"
                        onClick={() => toggleSources(finding.finding_id)}
                        className="inline-flex items-center gap-1 rounded bg-surface-3 px-2 py-0.5 text-[10px] font-medium text-text-secondary hover:text-text-primary transition-colors"
                      >
                        <span>Sources · {finding.source_citations.length}</span>
                        <ChevronDown
                          className={`h-2.5 w-2.5 transition-transform ${
                            openSourcesMap[finding.finding_id] ? "rotate-180" : ""
                          }`}
                        />
                      </button>

                      {openSourcesMap[finding.finding_id] && (
                        <div className="mt-2 space-y-1 rounded-md bg-surface-1 p-2 border border-border-subtle">
                          {finding.source_citations.map((cite) => (
                            <a
                              key={cite.url}
                              href={cite.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center justify-between rounded px-1.5 py-1 text-[10px] text-text-secondary hover:bg-surface-2 hover:text-primary transition-colors"
                            >
                              <span className="truncate max-w-[190px]">{cite.domain}</span>
                              <ExternalLink className="h-2.5 w-2.5 shrink-0" />
                            </a>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </article>
              ))}

              {findings.length > 3 && (
                <button
                  type="button"
                  onClick={onOpenAllFindings}
                  className="w-full rounded-lg border border-border-subtle bg-surface-2/60 py-2 text-center text-xs font-medium text-text-secondary hover:bg-surface-2 hover:text-text-primary transition-colors"
                >
                  View all {findings.length} findings
                </button>
              )}
            </div>
          ) : (
            <div className="rounded-lg bg-surface-2/30 p-3 text-center border border-border-subtle/40">
              <p className="text-[11px] text-text-muted">
                Alex is monitoring AI engineering topics.
              </p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};
