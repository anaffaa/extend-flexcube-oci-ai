data "oci_identity_tenancy" "this" {
  tenancy_id = var.tenancy_ocid
}

data "oci_identity_regions" "all" {}

data "oci_objectstorage_namespace" "this" {
  compartment_id = var.tenancy_ocid
}

locals {
  home_region    = [for r in data.oci_identity_regions.all.regions : r.name if r.key == data.oci_identity_tenancy.this.home_region_key][0]
  compartment_id = var.create_compartment ? oci_identity_compartment.solution[0].id : var.compartment_ocid
  tags           = var.freeform_tags
}

resource "oci_identity_compartment" "solution" {
  count          = var.create_compartment ? 1 : 0
  provider       = oci.home
  compartment_id = var.compartment_ocid
  name           = var.compartment_name
  description    = "Extend FLEXCUBE on OCI with AI: AI Data Platform, serving layer, sample source and operations."
  enable_delete  = true
  freeform_tags  = local.tags
}
