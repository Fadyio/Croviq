import { DOMAIN_PACKAGE } from "@croviq/domain";
import { OBSERVABILITY_PACKAGE } from "@croviq/observability";

export const MEDIA_PACKAGE = "@croviq/media";
export const MEDIA_DEPS = [DOMAIN_PACKAGE, OBSERVABILITY_PACKAGE] as const;
