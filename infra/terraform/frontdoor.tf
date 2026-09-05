resource "azurerm_cdn_frontdoor_profile" "application" {
  name                     = "afd-${local.common_name}"
  resource_group_name      = azurerm_resource_group.primary.name
  sku_name                 = "Premium_AzureFrontDoor"
  response_timeout_seconds = 60
  tags                     = var.tags
}

resource "azurerm_cdn_frontdoor_endpoint" "application" {
  name                     = "afd-${local.common_name}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.application.id
  enabled                  = true
  tags                     = var.tags
}

resource "azurerm_cdn_frontdoor_origin_group" "api" {
  name                     = "api"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.application.id
  session_affinity_enabled = false

  load_balancing {
    sample_size                        = 4
    successful_samples_required        = 3
    additional_latency_in_milliseconds = 50
  }

  health_probe {
    protocol            = "Https"
    interval_in_seconds = 30
    request_type        = "GET"
    path                = "/health/ready"
  }
}

resource "azurerm_cdn_frontdoor_origin_group" "frontend" {
  name                     = "frontend"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.application.id
  session_affinity_enabled = false

  load_balancing {
    sample_size                        = 4
    successful_samples_required        = 3
    additional_latency_in_milliseconds = 50
  }

  health_probe {
    protocol            = "Https"
    interval_in_seconds = 30
    request_type        = "GET"
    path                = "/login"
  }
}

resource "azurerm_cdn_frontdoor_origin" "api" {
  name                           = "api"
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.api.id
  enabled                        = true
  host_name                      = local.backend_fqdn
  origin_host_header             = local.backend_fqdn
  http_port                      = 80
  https_port                     = 443
  priority                       = 1
  weight                         = 1000
  certificate_name_check_enabled = true

  private_link {
    request_message        = "Approve Azure Front Door access to the production API environment."
    target_type            = "managedEnvironments"
    location               = azurerm_container_app_environment.application.location
    private_link_target_id = azurerm_container_app_environment.application.id
  }
}

resource "azurerm_cdn_frontdoor_origin" "frontend" {
  name                           = "frontend"
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.frontend.id
  enabled                        = true
  host_name                      = local.frontend_fqdn
  origin_host_header             = local.frontend_fqdn
  http_port                      = 80
  https_port                     = 443
  priority                       = 1
  weight                         = 1000
  certificate_name_check_enabled = true

  private_link {
    request_message        = "Approve Azure Front Door access to the production frontend environment."
    target_type            = "managedEnvironments"
    location               = azurerm_container_app_environment.application.location
    private_link_target_id = azurerm_container_app_environment.application.id
  }
}

resource "azurerm_cdn_frontdoor_custom_domain" "application" {
  for_each = local.edge_domains

  name                     = "domain-${substr(md5(each.key), 0, 12)}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.application.id
  host_name                = each.key

  tls {
    certificate_type = "ManagedCertificate"
    minimum_version  = "TLS12"
  }
}

resource "azurerm_cdn_frontdoor_route" "api" {
  name                          = "api-public"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.application.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.api.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.api.id]
  cdn_frontdoor_custom_domain_ids = [
    for domain in azurerm_cdn_frontdoor_custom_domain.application : domain.id
  ]
  enabled                = true
  forwarding_protocol    = "HttpsOnly"
  https_redirect_enabled = true
  link_to_default_domain = true
  patterns_to_match      = ["/api/*", "/q/*", "/l/*", "/qr-assets/*", "/health/*"]
  supported_protocols    = ["Http", "Https"]
}

resource "azurerm_cdn_frontdoor_route" "frontend" {
  name                          = "frontend"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.application.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.frontend.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.frontend.id]
  cdn_frontdoor_custom_domain_ids = [
    for domain in azurerm_cdn_frontdoor_custom_domain.application : domain.id
  ]
  enabled                = true
  forwarding_protocol    = "HttpsOnly"
  https_redirect_enabled = true
  link_to_default_domain = true
  patterns_to_match      = ["/*"]
  supported_protocols    = ["Http", "Https"]
}

resource "azurerm_cdn_frontdoor_firewall_policy" "application" {
  name                              = "waf${local.compact_prefix}${local.suffix}"
  resource_group_name               = azurerm_resource_group.primary.name
  sku_name                          = azurerm_cdn_frontdoor_profile.application.sku_name
  enabled                           = true
  mode                              = "Prevention"
  redirect_url                      = "https://app.${var.platform_domain}/login"
  custom_block_response_status_code = 403
  custom_block_response_body        = base64encode("Request blocked by the platform security policy.")
  tags                              = var.tags

  managed_rule {
    type    = "Microsoft_DefaultRuleSet"
    version = "2.1"
    action  = "Block"
  }

  managed_rule {
    type    = "Microsoft_BotManagerRuleSet"
    version = "1.1"
    action  = "Block"
  }

  custom_rule {
    name                           = "GlobalRateLimit"
    enabled                        = true
    priority                       = 10
    rate_limit_duration_in_minutes = 1
    rate_limit_threshold           = 600
    type                           = "RateLimitRule"
    action                         = "Block"

    match_condition {
      match_variable = "RequestUri"
      operator       = "BeginsWith"
      match_values   = ["/"]
    }
  }
}

resource "azurerm_cdn_frontdoor_security_policy" "application" {
  name                     = "application"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.application.id

  security_policies {
    firewall {
      cdn_frontdoor_firewall_policy_id = azurerm_cdn_frontdoor_firewall_policy.application.id

      association {
        patterns_to_match = ["/*"]

        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_endpoint.application.id
        }

        dynamic "domain" {
          for_each = azurerm_cdn_frontdoor_custom_domain.application
          content {
            cdn_frontdoor_domain_id = domain.value.id
          }
        }
      }
    }
  }
}
