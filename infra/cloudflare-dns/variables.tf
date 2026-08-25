variable "cloudflare_zone_name" {
  type        = string
  description = "The Cloudflare zone domain name."
  default     = "croviq.app"
}

variable "certificate_dns_authorization_name" {
  type        = string
  description = "The DNS Resource Record Name for Google Certificate Manager DNS authorization."
  default     = "_acme-challenge.app.croviq.app."
}

variable "certificate_dns_authorization_type" {
  type        = string
  description = "The DNS Resource Record Type for Google Certificate Manager DNS authorization."
  default     = "CNAME"
}

variable "certificate_dns_authorization_value" {
  type        = string
  description = "The DNS Resource Record Value (data) for Google Certificate Manager DNS authorization."
  default     = "37a12037-33a6-40bc-9905-b7e8d0287946.12.authorize.certificatemanager.goog."
}
