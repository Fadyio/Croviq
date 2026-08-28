import React from "react";
import { AnimatePresence, motion } from "motion/react";
import { ExternalLink, Radio, X } from "lucide-react";
import type { components } from "../../api/generated";

type ResearchFinding = components["schemas"]["ResearchFinding"];

interface WorthWatchingFindingsDrawerProps {
  open: boolean;
  findings: ResearchFinding[];
  onClose: () => void;
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

export const WorthWatchingFindingsDrawer: React.FC<WorthWatchingFindingsDrawerProps> = ({
  open,
  findings,
  onClose,
}) => {
  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm">
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 30 }}
            transition={{ duration: 0.2 }}
            className="flex h-full w-full max-w-xl flex-col border-l border-border-strong bg-surface-1 shadow-2xl"
          >
            {/* Drawer Header */}
            <div className="flex items-center justify-between border-b border-border-subtle p-5">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/15 text-primary">
                  <Radio className="h-4 w-4" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-text-primary">
                    Worth Watching · Topic Radar
                  </h2>
                  <p className="text-xs text-text-muted">
                    {findings.length} active research findings grounded in web search
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg p-1.5 text-text-muted hover:bg-surface-2 hover:text-text-primary transition-colors"
                aria-label="Close research findings"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Findings List */}
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {findings.map((finding) => (
                <article
                  key={finding.finding_id}
                  className="rounded-xl border border-border-subtle bg-surface-2/40 p-4 text-xs space-y-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded bg-surface-3 px-2 py-0.5 text-[10px] font-medium text-text-secondary">
                      {finding.category}
                    </span>
                    <span className="text-[11px] text-text-muted">
                      {formatDiscoveredAgo(finding.discovered_at)}
                    </span>
                  </div>

                  <h3 className="text-sm font-semibold text-text-primary leading-snug">
                    {finding.title}
                  </h3>

                  <p className="text-xs text-text-secondary leading-relaxed">{finding.summary}</p>

                  <div className="rounded-lg border-l-2 border-primary/70 bg-surface-3/50 p-3 text-xs leading-relaxed">
                    <span className="font-semibold text-text-primary">Why it matters: </span>
                    <span className="text-text-secondary">{finding.why_it_matters}</span>
                  </div>

                  {/* Sources & Citations */}
                  {finding.source_citations.length > 0 && (
                    <div className="pt-2 border-t border-border-subtle/60 space-y-1.5">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                        Verified Sources ({finding.source_citations.length})
                      </p>
                      <div className="space-y-1">
                        {finding.source_citations.map((cite) => (
                          <a
                            key={cite.url}
                            href={cite.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center justify-between rounded-lg bg-surface-1 px-2.5 py-1.5 text-xs text-text-secondary hover:bg-surface-3 hover:text-primary transition-colors border border-border-subtle"
                          >
                            <span className="truncate max-w-[340px] font-medium">
                              {cite.title || cite.domain}
                            </span>
                            <div className="flex items-center gap-1.5 shrink-0 text-text-muted text-[10px]">
                              <span>{cite.domain}</span>
                              <ExternalLink className="h-3 w-3" />
                            </div>
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                </article>
              ))}
            </div>

            {/* Footer */}
            <div className="border-t border-border-subtle p-4 flex justify-end">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg bg-surface-2 px-4 py-2 text-xs font-semibold text-text-primary hover:bg-surface-3 transition-colors"
              >
                Close
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
