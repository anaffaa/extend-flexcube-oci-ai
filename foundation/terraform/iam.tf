# AI Data Platform service policies, from "IAM Policies for Oracle AI Data Platform Workbench" (compartment-level option).
# Created in the root compartment (some statements are tenancy-scoped) in the home region.
locals {
  cid = local.compartment_id

  aidp_service_statements = concat([
    "allow any-user TO {AUTHENTICATION_INSPECT, DOMAIN_INSPECT, DOMAIN_READ, DYNAMIC_GROUP_INSPECT, GROUP_INSPECT, GROUP_MEMBERSHIP_INSPECT, USER_INSPECT, USER_READ} IN TENANCY where all {request.principal.type='aidataplatform'}",
    "allow any-user to manage log-groups in compartment id ${local.cid} where ALL { request.principal.type='aidataplatform' }",
    "allow any-user to read log-content in compartment id ${local.cid} where ALL { request.principal.type='aidataplatform' }",
    "allow any-user to use metrics in compartment id ${local.cid} where ALL {request.principal.type='aidataplatform', target.metrics.namespace='oracle_aidataplatform'}",
    "allow any-user to manage buckets in compartment id ${local.cid} where all { request.principal.type='aidataplatform', any {request.permission = 'BUCKET_CREATE', request.permission = 'BUCKET_INSPECT', request.permission = 'BUCKET_READ', request.permission = 'BUCKET_UPDATE'}}",
    "allow any-user to {TAG_NAMESPACE_USE} in tenancy where all {request.principal.type = 'aidataplatform'}",
    "allow any-user to manage buckets in compartment id ${local.cid} where all { request.principal.id=target.resource.tag.orcl-aidp.governingAidpId, any {request.permission = 'BUCKET_DELETE', request.permission = 'PAR_MANAGE', request.permission = 'RETENTION_RULE_LOCK', request.permission = 'RETENTION_RULE_MANAGE'} }",
    "allow any-user to read objectstorage-namespaces in compartment id ${local.cid} where all { request.principal.type='aidataplatform', any {request.permission = 'OBJECTSTORAGE_NAMESPACE_READ'}}",
    "allow any-user to manage objects in compartment id ${local.cid} where all { request.principal.id=target.bucket.system-tag.orcl-aidp.governingAidpId  }",
    "allow any-user to use generative-ai-family in tenancy where all { request.principal.type='aidataplatform'}",
    "allow service objectstorage-${var.region} to manage object-family in compartment id ${local.cid}",
    ],
    var.enable_private_network_policies ? [
      "allow any-user to manage vnics in compartment id ${local.cid} where all { request.principal.type='aidataplatform'}",
      "allow any-user to use subnets in compartment id ${local.cid} where all { request.principal.type='aidataplatform'}",
      "allow any-user to use network-security-groups in compartment id ${local.cid} where all { request.principal.type='aidataplatform'}",
  ] : [])

  admin_statements = var.aidp_admin_group == "" ? [] : [
    "allow group ${var.aidp_admin_group} to manage ai-data-platforms in compartment id ${local.cid}",
    "allow group ${var.aidp_admin_group} to manage autonomous-databases in compartment id ${local.cid}",
    "allow group ${var.aidp_admin_group} to use generative-ai-family in tenancy",
    "allow group ${var.aidp_admin_group} to read secret-bundles in compartment id ${local.cid}",
  ]
}

resource "oci_identity_policy" "aidp_service" {
  count          = var.create_iam_policies ? 1 : 0
  provider       = oci.home
  compartment_id = var.tenancy_ocid
  name           = "${var.prefix}-aidp-service-policy"
  description    = "AI Data Platform service permissions for the Extend FLEXCUBE on OCI solution"
  statements     = local.aidp_service_statements
  freeform_tags  = local.tags
}

resource "oci_identity_policy" "aidp_admins" {
  count          = var.create_iam_policies && var.aidp_admin_group != "" ? 1 : 0
  provider       = oci.home
  compartment_id = var.tenancy_ocid
  name           = "${var.prefix}-aidp-admin-policy"
  description    = "AI Data Platform administrators for the Extend FLEXCUBE on OCI solution"
  statements     = local.admin_statements
  freeform_tags  = local.tags
}
