output "front_door_endpoint_hostname" {
  description = "Default Azure Front Door hostname used for initial DNS validation."
  value       = azurerm_cdn_frontdoor_endpoint.application.host_name
}

output "front_door_id" {
  description = "Resource GUID sent by Azure Front Door in X-Azure-FDID and enforced by the API."
  value       = azurerm_cdn_frontdoor_profile.application.resource_guid
}

output "custom_domain_validation_tokens" {
  description = "Create the requested _dnsauth TXT records before expecting managed TLS to become active."
  value = {
    for hostname, domain in azurerm_cdn_frontdoor_custom_domain.application :
    hostname => domain.validation_token
  }
  sensitive = true
}

output "container_apps_environment_id" {
  description = "Approve the two Azure Front Door private endpoint requests on this environment after the first apply."
  value       = azurerm_container_app_environment.application.id
}

output "key_vault_uri" {
  value = azurerm_key_vault.application.vault_uri
}

output "service_bus_namespace" {
  value = "${azurerm_servicebus_namespace.campaigns.name}.servicebus.windows.net"
}

output "evidence_storage_account_url" {
  value = azurerm_storage_account.evidence.primary_blob_endpoint
}

output "postgres_primary_fqdn" {
  value     = local.postgres_fqdn
  sensitive = true
}

output "postgres_replica_fqdn" {
  value     = azurerm_postgresql_flexible_server.replica.fqdn
  sensitive = true
}
