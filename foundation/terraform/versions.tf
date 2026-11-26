# Extend FLEXCUBE on OCI: foundation stack. Deployable with OCI Resource Manager or the Terraform CLI.
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 7.22.0" # oci_ai_data_platform_ai_data_platform was added in 7.22.0
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5.0"
    }
  }
}

provider "oci" {
  region = var.region
}

# Policies must be created in the home region.
provider "oci" {
  alias  = "home"
  region = local.home_region
}
