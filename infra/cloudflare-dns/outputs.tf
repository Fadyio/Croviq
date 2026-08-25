output "cloudflare_zone_id" {
  value       = data.cloudflare_zone.croviq.id
  description = "The Cloudflare zone ID resolved from the zone name."
}

output "cloudflare_zone_name" {
  value       = data.cloudflare_zone.croviq.name
  description = "The Cloudflare zone name."
}

output "certificate_dns_authorization_record_id" {
  value       = cloudflare_record.app_cert_dns_authorization.id
  description = "The Cloudflare DNS record ID for the certificate authorization record."
}

output "certificate_dns_authorization_record_hostname" {
  value       = cloudflare_record.app_cert_dns_authorization.hostname
  description = "The FQDN of the certificate authorization record."
}

output "app_record_id" {
  value       = cloudflare_record.app.id
  description = "The Cloudflare DNS record ID for app.croviq.app."
}

output "app_record_hostname" {
  value       = cloudflare_record.app.hostname
  description = "The FQDN of the app A record."
}
