# Vault: one customer-managed key and generated passwords for every database user the solution needs.
# Scripts read them with "oci secrets secret-bundle get", so no password is typed or stored in files.
resource "oci_kms_vault" "this" {
  compartment_id = local.compartment_id
  display_name   = "${var.prefix}-vault"
  vault_type     = "DEFAULT"
  freeform_tags  = local.tags
}

resource "oci_kms_key" "this" {
  compartment_id      = local.compartment_id
  display_name        = "${var.prefix}-key"
  management_endpoint = oci_kms_vault.this.management_endpoint
  protection_mode     = "SOFTWARE"
  key_shape {
    algorithm = "AES"
    length    = 32
  }
  freeform_tags = local.tags
}

locals {
  # name => description
  db_secrets = {
    "sample-db-admin" = "ADMIN password of the sample FLEXCUBE source database"
    "aidp-reader"     = "AIDP_READER: read-only user on the FLEXCUBE source, used by the external catalog"
    "lakehouse-admin" = "ADMIN password of the AIDP 26ai Lakehouse"
    "fcubs-gold"      = "FCUBS_GOLD: serving-layer publisher in the Lakehouse"
    "aidp-agent"      = "AIDP_AGENT: read-only serving-layer user for agents"
  }
}

# Oracle rules: 12 to 30 characters, upper, lower, digit; special characters limited to # and _ to stay SQL- and shell-safe.
resource "random_password" "db" {
  for_each         = local.db_secrets
  length           = 20
  min_upper        = 2
  min_lower        = 2
  min_numeric      = 2
  min_special      = 1
  override_special = "_" # safe in SQL, URLs and netrc files
}

resource "oci_vault_secret" "db" {
  for_each       = local.db_secrets
  compartment_id = local.compartment_id
  vault_id       = oci_kms_vault.this.id
  key_id         = oci_kms_key.this.id
  secret_name    = "${var.prefix}-${each.key}"
  description    = each.value
  secret_content {
    content_type = "BASE64"
    content      = base64encode(random_password.db[each.key].result)
  }
  freeform_tags = local.tags
}
