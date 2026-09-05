resource "azurerm_container_app_environment" "application" {
  name                           = "cae-${local.common_name}"
  location                       = azurerm_resource_group.primary.location
  resource_group_name            = azurerm_resource_group.primary.name
  infrastructure_subnet_id       = azurerm_subnet.container_apps.id
  internal_load_balancer_enabled = true
  zone_redundancy_enabled        = true
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.application.id
  tags                           = var.tags

  workload_profile {
    name                  = "Delivery"
    workload_profile_type = "D4"
    minimum_count         = 1
    maximum_count         = 20
  }
}

resource "azurerm_container_app" "api" {
  name                         = local.api_name
  container_app_environment_id = azurerm_container_app_environment.application.id
  resource_group_name          = azurerm_resource_group.primary.name
  revision_mode                = "Single"
  workload_profile_name        = "Delivery"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.application.id]
  }

  registry {
    server   = azurerm_container_registry.application.login_server
    identity = azurerm_user_assigned_identity.application.id
  }

  secret {
    name                = "database-url"
    key_vault_secret_id = azurerm_key_vault_secret.database_url.versionless_id
    identity            = azurerm_user_assigned_identity.application.id
  }
  secret {
    name                = "redis-url"
    key_vault_secret_id = azurerm_key_vault_secret.redis_url.versionless_id
    identity            = azurerm_user_assigned_identity.application.id
  }
  secret {
    name                = "secret-key"
    key_vault_secret_id = azurerm_key_vault_secret.application_secret_key.versionless_id
    identity            = azurerm_user_assigned_identity.application.id
  }
  secret {
    name                = "encryption-key"
    key_vault_secret_id = azurerm_key_vault_secret.application_encryption_key.versionless_id
    identity            = azurerm_user_assigned_identity.application.id
  }
  secret {
    name                = "together-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.together_api_key.versionless_id
    identity            = azurerm_user_assigned_identity.application.id
  }

  template {
    min_replicas = 2
    max_replicas = 20

    container {
      name   = "api"
      image  = var.backend_image
      cpu    = 1.0
      memory = "2Gi"

      dynamic "env" {
        for_each = {
          ENVIRONMENT                           = "production"
          AI_PROVIDER                           = "together"
          TOGETHER_MODEL                        = "openai/gpt-oss-20b"
          FRONTEND_BASE_URL                     = "https://app.${var.platform_domain}"
          PUBLIC_URL_SCHEME                     = "https"
          PLATFORM_TRAINING_DOMAIN              = var.platform_domain
          FRONT_DOOR_ID                         = azurerm_cdn_frontdoor_profile.application.resource_guid
          FRONT_DOOR_ENDPOINT_HOSTNAME          = azurerm_cdn_frontdoor_endpoint.application.host_name
          CORS_ORIGINS                          = jsonencode(["https://app.${var.platform_domain}"])
          TRUSTED_HOSTS                         = jsonencode([local.backend_fqdn])
          SESSION_COOKIE_SECURE                 = "true"
          SESSION_COOKIE_DOMAIN                 = ".${var.platform_domain}"
          API_DOCS_ENABLED                      = "false"
          SEED_DEMO_CONTENT                     = "false"
          LAB_EMAIL_PROVIDER_ENABLED            = "false"
          LAB_SMS_PROVIDER_ENABLED              = "false"
          VOICE_CLONE_PROVIDER                  = "none"
          VIDEO_CLONE_PROVIDER                  = "none"
          EMAIL_DELIVERY_BACKEND                = "service_bus"
          SERVICE_BUS_FULLY_QUALIFIED_NAMESPACE = "${azurerm_servicebus_namespace.campaigns.name}.servicebus.windows.net"
          AZURE_KEY_VAULT_URL                   = azurerm_key_vault.application.vault_uri
          MICROSOFT_GRAPH_CLIENT_ID             = var.microsoft_graph_client_id
          MICROSOFT_GRAPH_CLIENT_SECRET_REF     = "kv://microsoft-graph-client-secret"
          MICROSOFT_GRAPH_REDIRECT_URI          = "https://app.${var.platform_domain}/api/v1/email-connections/microsoft/callback"
          GOOGLE_SERVICE_ACCOUNT_SECRET_REF     = "kv://google-service-account"
          SSO_CALLBACK_URL                      = "https://app.${var.platform_domain}/api/v1/sso/callback"
          EVIDENCE_STORAGE_ACCOUNT_URL          = azurerm_storage_account.evidence.primary_blob_endpoint
          EVIDENCE_STORAGE_CONTAINER            = azurerm_storage_container.audit.name
          APPLICATIONINSIGHTS_CONNECTION_STRING = azurerm_application_insights.application.connection_string
        }
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = {
          DATABASE_URL     = "database-url"
          REDIS_URL        = "redis-url"
          SECRET_KEY       = "secret-key"
          ENCRYPTION_KEY   = "encryption-key"
          TOGETHER_API_KEY = "together-api-key"
        }
        content {
          name        = env.key
          secret_name = env.value
        }
      }

      liveness_probe {
        transport        = "HTTP"
        port             = 8000
        path             = "/health/live"
        interval_seconds = 20
      }
      readiness_probe {
        transport        = "HTTP"
        port             = 8000
        path             = "/health/ready"
        interval_seconds = 10
      }
    }

    http_scale_rule {
      name                = "api-concurrency"
      concurrent_requests = 100
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "http"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  depends_on = [
    azurerm_role_assignment.application_acr_pull,
    azurerm_role_assignment.application_key_vault_reader,
  ]
}

resource "azurerm_container_app" "frontend" {
  name                         = local.frontend_name
  container_app_environment_id = azurerm_container_app_environment.application.id
  resource_group_name          = azurerm_resource_group.primary.name
  revision_mode                = "Single"
  workload_profile_name        = "Delivery"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.application.id]
  }
  registry {
    server   = azurerm_container_registry.application.login_server
    identity = azurerm_user_assigned_identity.application.id
  }

  template {
    min_replicas = 2
    max_replicas = 20
    container {
      name   = "frontend"
      image  = var.frontend_image
      cpu    = 1.0
      memory = "2Gi"
      env {
        name  = "SERVER_API_BASE_URL"
        value = "https://${local.backend_fqdn}/api/v1"
      }
      env {
        name  = "NEXT_PUBLIC_DEMO_MODE"
        value = "false"
      }
      liveness_probe {
        transport        = "HTTP"
        port             = 3000
        path             = "/login"
        interval_seconds = 20
      }
      readiness_probe {
        transport        = "HTTP"
        port             = 3000
        path             = "/login"
        interval_seconds = 10
      }
    }
    http_scale_rule {
      name                = "frontend-concurrency"
      concurrent_requests = 100
    }
  }
  ingress {
    external_enabled = true
    target_port      = 3000
    transport        = "http"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
  depends_on = [azurerm_role_assignment.application_acr_pull]
}

resource "azurerm_container_app_job" "delivery_worker" {
  name                         = "job-${local.common_name}-delivery"
  location                     = azurerm_resource_group.primary.location
  resource_group_name          = azurerm_resource_group.primary.name
  container_app_environment_id = azurerm_container_app_environment.application.id
  workload_profile_name        = "Delivery"
  replica_timeout_in_seconds   = 900
  replica_retry_limit          = 2
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.application.id]
  }
  registry {
    server   = azurerm_container_registry.application.login_server
    identity = azurerm_user_assigned_identity.application.id
  }
  secret {
    name                = "database-url"
    key_vault_secret_id = azurerm_key_vault_secret.database_url.versionless_id
    identity            = azurerm_user_assigned_identity.application.id
  }
  secret {
    name                = "redis-url"
    key_vault_secret_id = azurerm_key_vault_secret.redis_url.versionless_id
    identity            = azurerm_user_assigned_identity.application.id
  }
  secret {
    name                = "secret-key"
    key_vault_secret_id = azurerm_key_vault_secret.application_secret_key.versionless_id
    identity            = azurerm_user_assigned_identity.application.id
  }
  secret {
    name                = "encryption-key"
    key_vault_secret_id = azurerm_key_vault_secret.application_encryption_key.versionless_id
    identity            = azurerm_user_assigned_identity.application.id
  }

  event_trigger_config {
    parallelism              = 10
    replica_completion_count = 1
    scale {
      min_executions              = 0
      max_executions              = 50
      polling_interval_in_seconds = 10
      rules {
        name             = "campaign-service-bus"
        custom_rule_type = "azure-servicebus"
        identity_id      = azurerm_user_assigned_identity.application.id
        metadata = {
          namespace    = azurerm_servicebus_namespace.campaigns.name
          queueName    = azurerm_servicebus_queue.campaign_delivery.name
          messageCount = "20"
        }
      }
    }
  }

  template {
    container {
      name    = "delivery-worker"
      image   = var.backend_image
      cpu     = 1.0
      memory  = "2Gi"
      command = ["python", "-m", "app.workers.service_bus_worker"]
      dynamic "env" {
        for_each = local.production_worker_environment
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = {
          DATABASE_URL   = "database-url"
          REDIS_URL      = "redis-url"
          SECRET_KEY     = "secret-key"
          ENCRYPTION_KEY = "encryption-key"
        }
        content {
          name        = env.key
          secret_name = env.value
        }
      }
    }
  }
  depends_on = [
    azurerm_role_assignment.application_acr_pull,
    azurerm_role_assignment.application_service_bus_receiver,
  ]
}

resource "azurerm_container_app_job" "outbox_dispatcher" {
  name                         = "job-${local.common_name}-outbox"
  location                     = azurerm_resource_group.primary.location
  resource_group_name          = azurerm_resource_group.primary.name
  container_app_environment_id = azurerm_container_app_environment.application.id
  workload_profile_name        = "Delivery"
  replica_timeout_in_seconds   = 300
  replica_retry_limit          = 2
  tags                         = var.tags
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.application.id]
  }
  registry {
    server   = azurerm_container_registry.application.login_server
    identity = azurerm_user_assigned_identity.application.id
  }
  secret {
    name                = "database-url"
    key_vault_secret_id = azurerm_key_vault_secret.database_url.versionless_id
    identity            = azurerm_user_assigned_identity.application.id
  }
  secret {
    name                = "redis-url"
    key_vault_secret_id = azurerm_key_vault_secret.redis_url.versionless_id
    identity            = azurerm_user_assigned_identity.application.id
  }
  secret {
    name                = "secret-key"
    key_vault_secret_id = azurerm_key_vault_secret.application_secret_key.versionless_id
    identity            = azurerm_user_assigned_identity.application.id
  }
  secret {
    name                = "encryption-key"
    key_vault_secret_id = azurerm_key_vault_secret.application_encryption_key.versionless_id
    identity            = azurerm_user_assigned_identity.application.id
  }
  schedule_trigger_config {
    cron_expression          = "* * * * *"
    parallelism              = 1
    replica_completion_count = 1
  }
  template {
    container {
      name    = "outbox-dispatcher"
      image   = var.backend_image
      cpu     = 0.5
      memory  = "1Gi"
      command = ["python", "-m", "app.workers.outbox_dispatcher"]
      dynamic "env" {
        for_each = local.production_worker_environment
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = {
          DATABASE_URL   = "database-url"
          REDIS_URL      = "redis-url"
          SECRET_KEY     = "secret-key"
          ENCRYPTION_KEY = "encryption-key"
        }
        content {
          name        = env.key
          secret_name = env.value
        }
      }
    }
  }
  depends_on = [azurerm_role_assignment.application_service_bus_sender]
}
