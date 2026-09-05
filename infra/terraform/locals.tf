locals {
  compact_prefix = replace(var.name_prefix, "-", "")
  suffix         = random_string.suffix.result
  common_name    = "${var.name_prefix}-${local.suffix}"
  custom_domains = setunion(
    var.additional_custom_domains,
    var.enable_platform_wildcard_domain ? toset(["*.${var.platform_domain}"]) : toset([]),
  )
  edge_domains  = setunion(toset(["app.${var.platform_domain}"]), local.custom_domains)
  postgres_fqdn = "${azurerm_postgresql_flexible_server.primary.name}.postgres.database.azure.com"
  redis_fqdn    = "${azapi_resource.managed_redis.name}.${var.location}.redis.azure.net"
  api_name      = "ca-${local.common_name}-api"
  frontend_name = "ca-${local.common_name}-web"
  backend_fqdn  = "${local.api_name}.${azurerm_container_app_environment.application.default_domain}"
  frontend_fqdn = "${local.frontend_name}.${azurerm_container_app_environment.application.default_domain}"
  production_worker_environment = {
    ENVIRONMENT                           = "production"
    FRONTEND_BASE_URL                     = "https://app.${var.platform_domain}"
    PUBLIC_URL_SCHEME                     = "https"
    PLATFORM_TRAINING_DOMAIN              = var.platform_domain
    FRONT_DOOR_ID                         = azurerm_cdn_frontdoor_profile.application.resource_guid
    FRONT_DOOR_ENDPOINT_HOSTNAME          = azurerm_cdn_frontdoor_endpoint.application.host_name
    CORS_ORIGINS                          = jsonencode(["https://app.${var.platform_domain}"])
    TRUSTED_HOSTS                         = jsonencode([local.backend_fqdn])
    SESSION_COOKIE_SECURE                 = "true"
    API_DOCS_ENABLED                      = "false"
    SEED_DEMO_CONTENT                     = "false"
    LAB_EMAIL_PROVIDER_ENABLED            = "false"
    LAB_SMS_PROVIDER_ENABLED              = "false"
    VOICE_CLONE_PROVIDER                  = "none"
    VIDEO_CLONE_PROVIDER                  = "none"
    EMAIL_DELIVERY_BACKEND                = "service_bus"
    SERVICE_BUS_FULLY_QUALIFIED_NAMESPACE = "${azurerm_servicebus_namespace.campaigns.name}.servicebus.windows.net"
    AZURE_KEY_VAULT_URL                   = azurerm_key_vault.application.vault_uri
    GOOGLE_SERVICE_ACCOUNT_SECRET_REF     = "kv://google-service-account"
    MICROSOFT_GRAPH_CLIENT_ID             = var.microsoft_graph_client_id
    MICROSOFT_GRAPH_CLIENT_SECRET_REF     = "kv://microsoft-graph-client-secret"
    EVIDENCE_STORAGE_ACCOUNT_URL          = azurerm_storage_account.evidence.primary_blob_endpoint
    EVIDENCE_STORAGE_CONTAINER            = azurerm_storage_container.audit.name
  }
}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}
