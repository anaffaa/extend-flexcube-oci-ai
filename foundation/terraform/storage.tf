# Private, versioned, customer-key encrypted staging bucket for sample data loads and file exchanges.
resource "oci_objectstorage_bucket" "staging" {
  compartment_id = local.compartment_id
  namespace      = data.oci_objectstorage_namespace.this.namespace
  name           = "${var.prefix}-staging"
  access_type    = "NoPublicAccess"
  versioning     = "Enabled"
  kms_key_id     = oci_kms_key.this.id
  freeform_tags  = local.tags
}
