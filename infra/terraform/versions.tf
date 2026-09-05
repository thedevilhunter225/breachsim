terraform {
  required_version = ">= 1.9.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.55.0, < 6.0.0"
    }
    azapi = {
      source  = "Azure/azapi"
      version = ">= 2.4.0, < 3.0.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.7.0, < 4.0.0"
    }
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = false
    }
  }
}

provider "azapi" {
  skip_provider_registration = false
}
