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

# -----------------------------------------------------------------------------
# 2. Google Certificate Manager DNS Authorization Record
# -----------------------------------------------------------------------------

# DNS CNAME validation record for Google Certificate Manager (croviq-app-cert).
# Must be DNS-only (proxied = false) so Google's ACME challenge validation can resolve the CNAME.
resource "cloudflare_record" "app_cert_dns_authorization" {
  zone_id = data.cloudflare_zone.croviq.id
  name    = var.certificate_dns_authorization_name
  type    = var.certificate_dns_authorization_type
  value   = var.certificate_dns_authorization_value
  proxied = false
  ttl     = 1
  comment = "Google Certificate Manager DNS authorization for app.croviq.app"
}
