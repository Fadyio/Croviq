terraform {
  required_version = ">= 1.5.0, < 2.0.0"
  backend "gcs" {}

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }
}
