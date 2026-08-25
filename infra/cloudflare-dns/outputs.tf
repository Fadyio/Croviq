output "cloudflare_zone_id" {
  value       = data.cloudflare_zone.croviq.id
  description = "The Cloudflare zone ID resolved from the zone name."
}

output "cloudflare_zone_name" {
  value       = data.cloudflare_zone.croviq.name
  description = "The Cloudflare zone name."
}
