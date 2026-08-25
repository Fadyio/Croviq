import { AGENTS_PACKAGE } from "@croviq/agents";
import { DOMAIN_PACKAGE } from "@croviq/domain";
import { ENGINE_PACKAGE } from "@croviq/engine";
import { MEDIA_PACKAGE } from "@croviq/media";
import { OBSERVABILITY_PACKAGE } from "@croviq/observability";

export const API_APP = "@croviq/api";
export const API_DEPS = [
  DOMAIN_PACKAGE,
  OBSERVABILITY_PACKAGE,
  ENGINE_PACKAGE,
  AGENTS_PACKAGE,
  MEDIA_PACKAGE,
] as const;
