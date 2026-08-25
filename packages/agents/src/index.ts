import { DOMAIN_PACKAGE } from "@croviq/domain";
import { OBSERVABILITY_PACKAGE } from "@croviq/observability";

export const AGENTS_PACKAGE = "@croviq/agents";
export const AGENTS_DEPS = [DOMAIN_PACKAGE, OBSERVABILITY_PACKAGE] as const;
