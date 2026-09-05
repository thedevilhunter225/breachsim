resource "azurerm_postgresql_flexible_server" "primary" {
  name                          = "psql-${local.common_name}"
  resource_group_name           = azurerm_resource_group.primary.name
  location                      = azurerm_resource_group.primary.location
  version                       = "17"
  delegated_subnet_id           = azurerm_subnet.postgres.id
  private_dns_zone_id           = azurerm_private_dns_zone.zones["privatelink.postgres.database.azure.com"].id
  public_network_access_enabled = false
  administrator_login           = var.postgres_admin_login
  administrator_password        = var.postgres_admin_password
  sku_name                      = "GP_Standard_D4ds_v5"
  storage_mb                    = 131072
  storage_tier                  = "P30"
  backup_retention_days         = 35
  geo_redundant_backup_enabled  = true
  zone                          = "1"
  tags                          = var.tags

  authentication {
    active_directory_auth_enabled = true
    password_auth_enabled         = true
  }

  high_availability {
    mode                      = "ZoneRedundant"
    standby_availability_zone = "2"
  }

  maintenance_window {
    day_of_week  = 0
    start_hour   = 2
    start_minute = 0
  }

  lifecycle {
    prevent_destroy = true
    ignore_changes = [
      zone,
      high_availability[0].standby_availability_zone,
    ]
  }

  depends_on = [azurerm_private_dns_zone_virtual_network_link.primary]
}

resource "azurerm_postgresql_flexible_server_database" "application" {
  name      = "breachsim"
  server_id = azurerm_postgresql_flexible_server.primary.id
  collation = "en_US.utf8"
  charset   = "UTF8"

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_postgresql_flexible_server" "replica" {
  name                          = "psql-${local.common_name}-dr"
  resource_group_name           = azurerm_resource_group.secondary.name
  location                      = azurerm_resource_group.secondary.location
  create_mode                   = "Replica"
  source_server_id              = azurerm_postgresql_flexible_server.primary.id
  delegated_subnet_id           = azurerm_subnet.postgres_secondary.id
  private_dns_zone_id           = azurerm_private_dns_zone.zones["privatelink.postgres.database.azure.com"].id
  public_network_access_enabled = false
  sku_name                      = "GP_Standard_D4ds_v5"
  storage_mb                    = 131072
  storage_tier                  = "P30"
  zone                          = "1"
  tags                          = merge(var.tags, { role = "cross-region-replica" })

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [azurerm_private_dns_zone_virtual_network_link.secondary_postgres]
}

resource "azurerm_servicebus_namespace" "campaigns" {
  name                          = "sb-${local.common_name}"
  location                      = azurerm_resource_group.primary.location
  resource_group_name           = azurerm_resource_group.primary.name
  sku                           = "Premium"
  capacity                      = 1
  premium_messaging_partitions  = 1
  minimum_tls_version           = "1.2"
  local_auth_enabled            = false
  public_network_access_enabled = false
  tags                          = var.tags
}

resource "azurerm_servicebus_queue" "campaign_delivery" {
  name                                    = "campaign-delivery"
  namespace_id                            = azurerm_servicebus_namespace.campaigns.id
  max_delivery_count                      = 10
  lock_duration                           = "PT5M"
  duplicate_detection_history_time_window = "P1D"
  requires_duplicate_detection            = true
  dead_lettering_on_message_expiration    = true
  default_message_ttl                     = "P14D"
  max_size_in_megabytes                   = 5120
}

resource "azapi_resource" "managed_redis" {
  type      = "Microsoft.Cache/redisEnterprise@2025-07-01"
  parent_id = azurerm_resource_group.primary.id
  name      = "redis-${local.common_name}"
  location  = azurerm_resource_group.primary.location
  tags      = var.tags
  body = {
    properties = {
      minimumTlsVersion   = "1.2"
      highAvailability    = "Enabled"
      publicNetworkAccess = "Disabled"
      encryption          = {}
    }
    sku = {
      name = "Balanced_B3"
    }
    zones = ["1", "2", "3"]
  }
  response_export_values = ["properties.hostName"]
}

resource "azapi_resource" "managed_redis_database" {
  type      = "Microsoft.Cache/redisEnterprise/databases@2025-07-01"
  parent_id = azapi_resource.managed_redis.id
  name      = "default"
  body = {
    properties = {
      clientProtocol           = "Encrypted"
      clusteringPolicy         = "EnterpriseCluster"
      evictionPolicy           = "VolatileLRU"
      port                     = 10000
      accessKeysAuthentication = "Enabled"
      modules                  = []
    }
  }
  response_export_values = ["*"]
}

resource "azapi_resource_action" "managed_redis_keys" {
  type                   = "Microsoft.Cache/redisEnterprise/databases@2025-07-01"
  resource_id            = azapi_resource.managed_redis_database.id
  action                 = "listKeys"
  method                 = "POST"
  response_export_values = ["primaryKey"]
}

resource "azurerm_storage_account" "evidence" {
  name                              = substr("st${local.compact_prefix}${local.suffix}", 0, 24)
  resource_group_name               = azurerm_resource_group.primary.name
  location                          = azurerm_resource_group.primary.location
  account_tier                      = "Standard"
  account_replication_type          = "RAGZRS"
  account_kind                      = "StorageV2"
  min_tls_version                   = "TLS1_2"
  public_network_access_enabled     = false
  allow_nested_items_to_be_public   = false
  shared_access_key_enabled         = false
  infrastructure_encryption_enabled = true
  tags                              = var.tags

  blob_properties {
    versioning_enabled  = true
    change_feed_enabled = true
    delete_retention_policy { days = 30 }
    container_delete_retention_policy { days = 30 }
  }

  network_rules {
    default_action = "Deny"
    bypass         = ["AzureServices"]
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_container" "audit" {
  name                  = "audit-evidence"
  storage_account_id    = azurerm_storage_account.evidence.id
  container_access_type = "private"
}

resource "azurerm_storage_container_immutability_policy" "audit" {
  storage_container_resource_manager_id = azurerm_storage_container.audit.id
  immutability_period_in_days           = 2555
  protected_append_writes_all_enabled   = true
}

resource "azurerm_container_registry" "application" {
  name                          = substr("acr${local.compact_prefix}${local.suffix}", 0, 50)
  resource_group_name           = azurerm_resource_group.primary.name
  location                      = azurerm_resource_group.primary.location
  sku                           = "Premium"
  admin_enabled                 = false
  public_network_access_enabled = false
  zone_redundancy_enabled       = true
  anonymous_pull_enabled        = false
  data_endpoint_enabled         = true
  tags                          = var.tags
}
