import { DOMAIN_PACKAGE } from "@croviq/domain";
import { OBSERVABILITY_PACKAGE } from "@croviq/observability";

export const ENGINE_PACKAGE = "@croviq/engine";
export const ENGINE_DEPS = [DOMAIN_PACKAGE, OBSERVABILITY_PACKAGE] as const;
