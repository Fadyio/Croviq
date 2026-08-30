import type { components } from "../api/generated";

export type ResearchFinding = components["schemas"]["ResearchFinding"];
export type FindingProvenance = components["schemas"]["FindingProvenance"];
export type DiscoverySignal = components["schemas"]["DiscoverySignal"];
export type PrimarySourceCitation = components["schemas"]["PrimarySourceCitation"];
export type SupportingSourceCitation = components["schemas"]["SupportingSourceCitation"];
export type SourceCitation = components["schemas"]["SourceCitation"];

export interface ResolvedProvenance {
  discovery_signal: DiscoverySignal | null;
  primary_sources: PrimarySourceCitation[];
  supporting_sources: SupportingSourceCitation[];
}

export function classifyUrlRole(
  url: string,
  title?: string,
): { role: "COMMUNITY_SIGNAL" | "PRIMARY" | "SUPPORTING"; sourceType: string } {
  const clean = url.trim().toLowerCase();
  let domain = "";
  try {
    const parsed = new URL(clean.startsWith("http") ? clean : `https://${clean}`);
    domain = parsed.hostname.replace(/^www\./, "");
  } catch {
    domain = clean;
  }

  const tLower = (title || "").toLowerCase();

  // Community Signal: Strictly actual community platforms
  if (domain === "news.ycombinator.com" || domain === "hacker-news.firebaseio.com") {
    return { role: "COMMUNITY_SIGNAL", sourceType: "Hacker News" };
  }
  if (domain === "reddit.com" || domain.endsWith(".reddit.com")) {
    return { role: "COMMUNITY_SIGNAL", sourceType: "Reddit" };
  }
  if (domain === "x.com" || domain === "twitter.com") {
    return { role: "COMMUNITY_SIGNAL", sourceType: "X (Twitter)" };
  }
  if (domain.startsWith("forum.") || domain.startsWith("discourse.")) {
    return { role: "COMMUNITY_SIGNAL", sourceType: "Developer Community" };
  }

  // Primary: Official repositories, standards, specs, official vendor docs
  if (domain === "github.com" || domain === "gitlab.com") {
    return { role: "PRIMARY", sourceType: "GitHub Repository" };
  }
  if (
    [
      "modelcontextprotocol.io",
      "opentelemetry.io",
      "w3.org",
      "ietf.org",
      "iso.org",
      "peps.python.org",
    ].includes(domain)
  ) {
    return { role: "PRIMARY", sourceType: "Official Specification" };
  }
  if (
    [
      "ai.google.dev",
      "cloud.google.com",
      "blog.google",
      "deepmind.google",
      "support.google.com",
      "anthropic.com",
      "openai.com",
      "developer.apple.com",
      "aws.amazon.com",
      "microsoft.com",
      "azure.microsoft.com",
      "docs.python.org",
      "developer.mozilla.org",
      "fastapi.tiangolo.com",
      "docs.vllm.ai",
      "sgl-project.github.io",
      "pypi.org",
      "docker.com",
      "kubernetes.io",
    ].some((d) => domain === d || domain.endsWith(`.${d}`))
  ) {
    return { role: "PRIMARY", sourceType: "Official Documentation" };
  }

  // Supporting: Independent blogs, benchmarks, tutorials
  if (
    ["benchmark", "benchmarks", "vs", "latency", "throughput", "comparison"].some(
      (k) => tLower.includes(k) || clean.includes(k),
    )
  ) {
    return { role: "SUPPORTING", sourceType: "Independent Benchmark" };
  }
  if (
    ["tutorial", "guide", "walkthrough", "how-to", "deploying"].some(
      (k) => tLower.includes(k) || clean.includes(k),
    )
  ) {
    return { role: "SUPPORTING", sourceType: "Engineering Tutorial" };
  }
  return { role: "SUPPORTING", sourceType: "Independent Analysis" };
}

export function getResolvedProvenance(finding: ResearchFinding): ResolvedProvenance {
  // If typed provenance is explicitly present and populated:
  if (
    finding.provenance &&
    (finding.provenance.discovery_signal ||
      (finding.provenance.primary_sources && finding.provenance.primary_sources.length > 0) ||
      (finding.provenance.supporting_sources && finding.provenance.supporting_sources.length > 0))
  ) {
    return {
      discovery_signal: finding.provenance.discovery_signal || null,
      primary_sources: finding.provenance.primary_sources || [],
      supporting_sources: finding.provenance.supporting_sources || [],
    };
  }

  // Otherwise, degrade truthfully from source_citations
  let discovery_signal: DiscoverySignal | null = null;
  const primary_sources: PrimarySourceCitation[] = [];
  const supporting_sources: SupportingSourceCitation[] = [];

  const citations = finding.source_citations || [];
  for (const cite of citations) {
    if (!cite.url) continue;
    const { role, sourceType } = classifyUrlRole(cite.url, cite.title);
    if (role === "COMMUNITY_SIGNAL") {
      if (!discovery_signal) {
        discovery_signal = {
          source_type: sourceType,
          title: cite.title || cite.domain,
          url: cite.url,
          domain: cite.domain,
        };
      }
    } else if (role === "PRIMARY") {
      if (!primary_sources.some((p) => p.url === cite.url)) {
        primary_sources.push({
          title: cite.title || cite.domain,
          url: cite.url,
          domain: cite.domain,
        });
      }
    } else {
      if (!supporting_sources.some((s) => s.url === cite.url)) {
        supporting_sources.push({
          title: cite.title || cite.domain,
          url: cite.url,
          domain: cite.domain,
          source_type: sourceType,
        });
      }
    }
  }

  return {
    discovery_signal,
    primary_sources,
    supporting_sources,
  };
}
