resource "azurerm_private_endpoint" "key_vault" {
  name                = "pe-${local.common_name}-keyvault"
  location            = azurerm_resource_group.primary.location
  resource_group_name = azurerm_resource_group.primary.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  tags                = var.tags
  private_service_connection {
    name                           = "keyvault"
    private_connection_resource_id = azurerm_key_vault.application.id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }
  private_dns_zone_group {
    name                 = "keyvault"
    private_dns_zone_ids = [azurerm_private_dns_zone.zones["privatelink.vaultcore.azure.net"].id]
  }
}

resource "azurerm_private_endpoint" "service_bus" {
  name                = "pe-${local.common_name}-servicebus"
  location            = azurerm_resource_group.primary.location
  resource_group_name = azurerm_resource_group.primary.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  tags                = var.tags
  private_service_connection {
    name                           = "servicebus"
    private_connection_resource_id = azurerm_servicebus_namespace.campaigns.id
    subresource_names              = ["namespace"]
    is_manual_connection           = false
  }
  private_dns_zone_group {
    name                 = "servicebus"
    private_dns_zone_ids = [azurerm_private_dns_zone.zones["privatelink.servicebus.windows.net"].id]
  }
}

resource "azurerm_private_endpoint" "storage_blob" {
  name                = "pe-${local.common_name}-blob"
  location            = azurerm_resource_group.primary.location
  resource_group_name = azurerm_resource_group.primary.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  tags                = var.tags
  private_service_connection {
    name                           = "blob"
    private_connection_resource_id = azurerm_storage_account.evidence.id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }
  private_dns_zone_group {
    name                 = "blob"
    private_dns_zone_ids = [azurerm_private_dns_zone.zones["privatelink.blob.core.windows.net"].id]
  }
}

resource "azurerm_private_endpoint" "container_registry" {
  name                = "pe-${local.common_name}-acr"
  location            = azurerm_resource_group.primary.location
  resource_group_name = azurerm_resource_group.primary.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  tags                = var.tags
  private_service_connection {
    name                           = "acr"
    private_connection_resource_id = azurerm_container_registry.application.id
    subresource_names              = ["registry"]
    is_manual_connection           = false
  }
  private_dns_zone_group {
    name                 = "acr"
    private_dns_zone_ids = [azurerm_private_dns_zone.zones["privatelink.azurecr.io"].id]
  }
}

resource "azurerm_private_endpoint" "managed_redis" {
  name                = "pe-${local.common_name}-redis"
  location            = azurerm_resource_group.primary.location
  resource_group_name = azurerm_resource_group.primary.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  tags                = var.tags
  private_service_connection {
    name                           = "redis-enterprise"
    private_connection_resource_id = azapi_resource.managed_redis.id
    subresource_names              = ["redisEnterprise"]
    is_manual_connection           = false
  }
  private_dns_zone_group {
    name                 = "redis"
    private_dns_zone_ids = [azurerm_private_dns_zone.zones["privatelink.redis.azure.net"].id]
  }
}
