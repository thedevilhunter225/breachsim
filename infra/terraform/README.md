# Azure infrastructure

This module provisions the production Azure topology. It is validated against Terraform
1.15.8, AzureRM 5.2.0 and AzAPI 2.12.0.

It creates Front Door Premium/WAF, private-linked Container Apps and event jobs, Service Bus
Premium, Azure Managed Redis using the 2025-07-01 API, PostgreSQL Flexible Server with
zone-redundant HA and a cross-region replica, Key Vault, immutable RA-GZRS Blob evidence
storage, ACR, private DNS/endpoints, Application Insights and alerts.

Before `init`, configure an Azure Storage remote backend with state locking. Copy
`terraform.tfvars.example`, supply only non-secret values there, and inject sensitive values
as protected `TF_VAR_*` CI variables. Pin application images by digest.

The first apply needs two manual follow-ups: approve the Front Door private endpoint requests
on the Container Apps environment, and publish the custom-domain validation records returned
by the outputs. Customer custom domains must be added to `additional_custom_domains` before
the platform operator activates them in the application.
