resource "azurerm_resource_group" "primary" {
  name     = "rg-${local.common_name}"
  location = var.location
  tags     = var.tags
}

resource "azurerm_resource_group" "secondary" {
  name     = "rg-${local.common_name}-dr"
  location = var.secondary_location
  tags     = merge(var.tags, { role = "disaster-recovery" })
}

resource "azurerm_virtual_network" "primary" {
  name                = "vnet-${local.common_name}"
  location            = azurerm_resource_group.primary.location
  resource_group_name = azurerm_resource_group.primary.name
  address_space       = ["10.40.0.0/16"]
  tags                = var.tags
}

resource "azurerm_subnet" "container_apps" {
  name                 = "snet-container-apps"
  resource_group_name  = azurerm_resource_group.primary.name
  virtual_network_name = azurerm_virtual_network.primary.name
  address_prefixes     = ["10.40.0.0/23"]

  delegation {
    name = "container-app-environments"
    service_delegation {
      name = "Microsoft.App/environments"
    }
  }
}

resource "azurerm_subnet" "private_endpoints" {
  name                              = "snet-private-endpoints"
  resource_group_name               = azurerm_resource_group.primary.name
  virtual_network_name              = azurerm_virtual_network.primary.name
  address_prefixes                  = ["10.40.4.0/24"]
  private_endpoint_network_policies = "Disabled"
}

resource "azurerm_subnet" "postgres" {
  name                 = "snet-postgres"
  resource_group_name  = azurerm_resource_group.primary.name
  virtual_network_name = azurerm_virtual_network.primary.name
  address_prefixes     = ["10.40.8.0/24"]

  service_endpoint {
    service = "Microsoft.Storage"
  }

  delegation {
    name = "postgres-flexible"
    service_delegation {
      name    = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_virtual_network" "secondary" {
  name                = "vnet-${local.common_name}-dr"
  location            = azurerm_resource_group.secondary.location
  resource_group_name = azurerm_resource_group.secondary.name
  address_space       = ["10.50.0.0/16"]
  tags                = var.tags
}

resource "azurerm_subnet" "postgres_secondary" {
  name                 = "snet-postgres"
  resource_group_name  = azurerm_resource_group.secondary.name
  virtual_network_name = azurerm_virtual_network.secondary.name
  address_prefixes     = ["10.50.8.0/24"]

  service_endpoint {
    service = "Microsoft.Storage"
  }

  delegation {
    name = "postgres-flexible"
    service_delegation {
      name    = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_private_dns_zone" "zones" {
  for_each = toset([
    "privatelink.azurecr.io",
    "privatelink.blob.core.windows.net",
    "privatelink.postgres.database.azure.com",
    "privatelink.redis.azure.net",
    "privatelink.servicebus.windows.net",
    "privatelink.vaultcore.azure.net",
  ])

  name                = each.value
  resource_group_name = azurerm_resource_group.primary.name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "primary" {
  for_each = azurerm_private_dns_zone.zones

  name                 = "${local.compact_prefix}-${replace(each.key, ".", "-")}-primary"
  private_dns_zone_id  = each.value.id
  virtual_network_id   = azurerm_virtual_network.primary.id
  registration_enabled = false
  tags                 = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "secondary_postgres" {
  name                 = "${local.compact_prefix}-postgres-dr"
  private_dns_zone_id  = azurerm_private_dns_zone.zones["privatelink.postgres.database.azure.com"].id
  virtual_network_id   = azurerm_virtual_network.secondary.id
  registration_enabled = false
  tags                 = var.tags
}

resource "azurerm_network_security_group" "private_endpoints" {
  name                = "nsg-${local.common_name}-private-endpoints"
  location            = azurerm_resource_group.primary.location
  resource_group_name = azurerm_resource_group.primary.name
  tags                = var.tags

  security_rule {
    name                       = "DenyInternetInbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "Internet"
    destination_address_prefix = "VirtualNetwork"
  }
}

resource "azurerm_subnet_network_security_group_association" "private_endpoints" {
  subnet_id                 = azurerm_subnet.private_endpoints.id
  network_security_group_id = azurerm_network_security_group.private_endpoints.id
}
