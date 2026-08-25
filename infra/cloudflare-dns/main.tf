# Croviq Cloudflare DNS Root Module
# Canonical definition of Cloudflare authoritative DNS for Croviq.

# -----------------------------------------------------------------------------
# 1. Cloudflare Zone Data Source (Authoritative DNS Foundation Only)
# -----------------------------------------------------------------------------

# Read-only zone lookup to resolve zone ID for future DNS record management.
# Cloudflare is authoritative DNS only; all runtime and routing live on Google Cloud.
data "cloudflare_zone" "croviq" {
  name = var.cloudflare_zone_name
}
