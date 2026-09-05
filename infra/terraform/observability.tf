resource "azurerm_log_analytics_workspace" "application" {
  name                = "log-${local.common_name}"
  location            = azurerm_resource_group.primary.location
  resource_group_name = azurerm_resource_group.primary.name
  sku                 = "PerGB2018"
  retention_in_days   = 90
  daily_quota_gb      = 10
  tags                = var.tags
}

resource "azurerm_application_insights" "application" {
  name                       = "appi-${local.common_name}"
  location                   = azurerm_resource_group.primary.location
  resource_group_name        = azurerm_resource_group.primary.name
  workspace_id               = azurerm_log_analytics_workspace.application.id
  application_type           = "web"
  retention_in_days          = 90
  internet_ingestion_enabled = true
  internet_query_enabled     = false
  tags                       = var.tags
}

resource "azurerm_monitor_action_group" "operations" {
  name                = "ag-${local.common_name}-operations"
  resource_group_name = azurerm_resource_group.primary.name
  short_name          = "bssre"
  tags                = var.tags

  dynamic "email_receiver" {
    for_each = var.operations_alert_emails
    content {
      name          = "operations-${substr(md5(email_receiver.value), 0, 8)}"
      email_address = email_receiver.value
    }
  }
}

resource "azurerm_application_insights_standard_web_test" "api_readiness" {
  name                    = "${local.common_name}-api-readiness"
  resource_group_name     = azurerm_resource_group.primary.name
  location                = azurerm_resource_group.primary.location
  application_insights_id = azurerm_application_insights.application.id
  enabled                 = true
  frequency               = 300
  timeout                 = 30
  retry_enabled           = true
  geo_locations           = ["emea-nl-ams-azr", "emea-gb-db3-azr", "us-ca-sjc-azr"]
  tags                    = var.tags

  request {
    url                              = "https://${azurerm_cdn_frontdoor_endpoint.application.host_name}/health/ready"
    http_verb                        = "GET"
    follow_redirects_enabled         = true
    parse_dependent_requests_enabled = false
  }

  validation_rules {
    expected_status_code        = 200
    ssl_check_enabled           = true
    ssl_cert_remaining_lifetime = 14
  }
}

resource "azurerm_monitor_metric_alert" "service_bus_dead_letters" {
  name                = "${local.common_name}-dead-letter-alert"
  resource_group_name = azurerm_resource_group.primary.name
  scopes              = [azurerm_servicebus_namespace.campaigns.id]
  description         = "Campaign messages have reached the dead-letter queue."
  severity            = 1
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = var.tags

  criteria {
    metric_namespace = "Microsoft.ServiceBus/namespaces"
    metric_name      = "DeadletteredMessages"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 0
    dimension {
      name     = "EntityName"
      operator = "Include"
      values   = [azurerm_servicebus_queue.campaign_delivery.name]
    }
  }

  action { action_group_id = azurerm_monitor_action_group.operations.id }
}

resource "azurerm_monitor_metric_alert" "api_availability" {
  name                = "${local.common_name}-api-availability"
  resource_group_name = azurerm_resource_group.primary.name
  scopes              = [azurerm_application_insights.application.id]
  description         = "Authenticated API or public training route availability is below the 99.9% target."
  severity            = 1
  frequency           = "PT5M"
  window_size         = "PT15M"
  tags                = var.tags

  criteria {
    metric_namespace = "Microsoft.Insights/components"
    metric_name      = "availabilityResults/availabilityPercentage"
    aggregation      = "Average"
    operator         = "LessThan"
    threshold        = 99.9
  }

  action { action_group_id = azurerm_monitor_action_group.operations.id }

  depends_on = [azurerm_application_insights_standard_web_test.api_readiness]
}

locals {
  diagnostic_targets = {
    frontdoor  = azurerm_cdn_frontdoor_profile.application.id
    keyvault   = azurerm_key_vault.application.id
    postgres   = azurerm_postgresql_flexible_server.primary.id
    servicebus = azurerm_servicebus_namespace.campaigns.id
    storage    = azurerm_storage_account.evidence.id
    registry   = azurerm_container_registry.application.id
    redis      = azapi_resource.managed_redis.id
  }
}

resource "azurerm_monitor_diagnostic_setting" "platform" {
  for_each = local.diagnostic_targets

  name                           = "send-to-log-analytics"
  target_resource_id             = each.value
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.application.id
  log_analytics_destination_type = "Dedicated"

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}
