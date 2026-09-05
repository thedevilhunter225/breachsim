variable "name_prefix" {
  description = "Short lowercase product/environment prefix used in globally unique resource names."
  type        = string
  default     = "breachsim-prod"
  validation {
    condition     = can(regex("^[a-z0-9-]{3,24}$", var.name_prefix))
    error_message = "name_prefix must contain 3-24 lowercase letters, numbers, or hyphens."
  }
}

variable "location" {
  type    = string
  default = "westeurope"
}

variable "secondary_location" {
  type    = string
  default = "northeurope"
}

variable "platform_domain" {
  description = "Root hostname for tenant subdomains, for example training.example.com."
  type        = string
}

variable "enable_platform_wildcard_domain" {
  description = "Enable only after the wildcard TXT and CNAME records are ready."
  type        = bool
  default     = false
}

variable "additional_custom_domains" {
  description = "Verified customer landing hostnames to attach to both Front Door routes."
  type        = set(string)
  default     = []
}

variable "backend_image" {
  description = "Immutable backend image reference, preferably pinned by sha256 digest."
  type        = string
}

variable "frontend_image" {
  description = "Immutable frontend image reference, preferably pinned by sha256 digest."
  type        = string
}

variable "postgres_admin_login" {
  type    = string
  default = "breachsimadmin"
}

variable "postgres_admin_password" {
  description = "Bootstrap database password. Supply through a protected TF_VAR value; rotate into Key Vault after deployment."
  type        = string
  sensitive   = true
  validation {
    condition     = length(var.postgres_admin_password) >= 24
    error_message = "postgres_admin_password must be at least 24 characters."
  }
}

variable "application_secret_key" {
  description = "At least 32 random bytes used for sessions and keyed hashes."
  type        = string
  sensitive   = true
  validation {
    condition     = length(var.application_secret_key) >= 32
    error_message = "application_secret_key must be at least 32 characters."
  }
}

variable "application_encryption_key" {
  description = "Fernet key used for application-level field encryption."
  type        = string
  sensitive   = true
}

variable "together_api_key" {
  description = "Together AI key for ZDR-enabled generation."
  type        = string
  sensitive   = true
}

variable "microsoft_graph_client_id" {
  type    = string
  default = ""
}

variable "microsoft_graph_client_secret" {
  type      = string
  sensitive = true
  default   = ""
}

variable "google_service_account_json" {
  type      = string
  sensitive = true
  default   = ""
}

variable "sso_client_secrets" {
  description = "Key Vault secret name to client secret mappings for approved tenant OIDC connections."
  type        = map(string)
  sensitive   = true
  default     = {}
}

variable "reconciliation_signing_secrets" {
  description = "Key Vault secret name to HMAC key mappings for provider reconciliation endpoints."
  type        = map(string)
  sensitive   = true
  default     = {}
}

variable "operations_alert_emails" {
  description = "Addresses that receive production availability, queue and security alerts."
  type        = set(string)
  default     = []
}

variable "tags" {
  type = map(string)
  default = {
    workload         = "breachsim"
    environment      = "production"
    data_class       = "confidential"
    managed_by       = "terraform"
    availability_slo = "99.9"
  }
}
