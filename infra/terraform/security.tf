data "azurerm_client_config" "current" {}

resource "azurerm_user_assigned_identity" "application" {
  name                = "id-${local.common_name}-app"
  location            = azurerm_resource_group.primary.location
  resource_group_name = azurerm_resource_group.primary.name
  tags                = var.tags
}

resource "azurerm_key_vault" "application" {
  name                          = substr("kv-${local.common_name}", 0, 24)
  location                      = azurerm_resource_group.primary.location
  resource_group_name           = azurerm_resource_group.primary.name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "premium"
  rbac_authorization_enabled    = true
  purge_protection_enabled      = true
  soft_delete_retention_days    = 90
  public_network_access_enabled = false
  tags                          = var.tags

  network_acls {
    bypass         = "AzureServices"
    default_action = "Deny"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_role_assignment" "terraform_key_vault_admin" {
  scope                = azurerm_key_vault.application.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "application_key_vault_reader" {
  scope                = azurerm_key_vault.application.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.application.principal_id
}

resource "azurerm_role_assignment" "application_acr_pull" {
  scope                = azurerm_container_registry.application.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.application.principal_id
}

resource "azurerm_role_assignment" "application_service_bus_sender" {
  scope                = azurerm_servicebus_namespace.campaigns.id
  role_definition_name = "Azure Service Bus Data Sender"
  principal_id         = azurerm_user_assigned_identity.application.principal_id
}

resource "azurerm_role_assignment" "application_service_bus_receiver" {
  scope                = azurerm_servicebus_namespace.campaigns.id
  role_definition_name = "Azure Service Bus Data Receiver"
  principal_id         = azurerm_user_assigned_identity.application.principal_id
}

resource "azurerm_role_assignment" "application_blob_contributor" {
  scope                = azurerm_storage_account.evidence.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.application.principal_id
}

resource "azurerm_key_vault_secret" "database_url" {
  name         = "database-url"
  value        = "postgresql+psycopg://${var.postgres_admin_login}:${urlencode(var.postgres_admin_password)}@${local.postgres_fqdn}:5432/breachsim?sslmode=require"
  key_vault_id = azurerm_key_vault.application.id
  content_type = "application/x-sqlalchemy-url"
  depends_on   = [azurerm_role_assignment.terraform_key_vault_admin]
}

resource "azurerm_key_vault_secret" "redis_url" {
  name         = "redis-url"
  value        = "rediss://:${urlencode(azapi_resource_action.managed_redis_keys.output.primaryKey)}@${local.redis_fqdn}:10000/0"
  key_vault_id = azurerm_key_vault.application.id
  content_type = "application/x-redis-url"
  depends_on   = [azurerm_role_assignment.terraform_key_vault_admin]
}

resource "azurerm_key_vault_secret" "application_secret_key" {
  name         = "application-secret-key"
  value        = var.application_secret_key
  key_vault_id = azurerm_key_vault.application.id
  depends_on   = [azurerm_role_assignment.terraform_key_vault_admin]
}

resource "azurerm_key_vault_secret" "application_encryption_key" {
  name         = "application-encryption-key"
  value        = var.application_encryption_key
  key_vault_id = azurerm_key_vault.application.id
  depends_on   = [azurerm_role_assignment.terraform_key_vault_admin]
}

resource "azurerm_key_vault_secret" "together_api_key" {
  name         = "together-api-key"
  value        = var.together_api_key
  key_vault_id = azurerm_key_vault.application.id
  depends_on   = [azurerm_role_assignment.terraform_key_vault_admin]
}

resource "azurerm_key_vault_secret" "microsoft_graph_client_secret" {
  count        = var.microsoft_graph_client_secret == "" ? 0 : 1
  name         = "microsoft-graph-client-secret"
  value        = var.microsoft_graph_client_secret
  key_vault_id = azurerm_key_vault.application.id
  depends_on   = [azurerm_role_assignment.terraform_key_vault_admin]
}

resource "azurerm_key_vault_secret" "google_service_account" {
  count        = var.google_service_account_json == "" ? 0 : 1
  name         = "google-service-account"
  value        = var.google_service_account_json
  key_vault_id = azurerm_key_vault.application.id
  content_type = "application/json"
  depends_on   = [azurerm_role_assignment.terraform_key_vault_admin]
}

resource "azurerm_key_vault_secret" "sso" {
  for_each     = nonsensitive(toset(keys(var.sso_client_secrets)))
  name         = each.value
  value        = var.sso_client_secrets[each.value]
  key_vault_id = azurerm_key_vault.application.id
  depends_on   = [azurerm_role_assignment.terraform_key_vault_admin]
}

resource "azurerm_key_vault_secret" "reconciliation" {
  for_each     = nonsensitive(toset(keys(var.reconciliation_signing_secrets)))
  name         = each.value
  value        = var.reconciliation_signing_secrets[each.value]
  key_vault_id = azurerm_key_vault.application.id
  depends_on   = [azurerm_role_assignment.terraform_key_vault_admin]
}
