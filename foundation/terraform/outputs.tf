output "compartment_id" {
  value = local.compartment_id
}

output "aidp_id" {
  value = oci_ai_data_platform_ai_data_platform.this.id
}

output "aidp_workspace" {
  value = var.aidp_workspace_name
}

output "vcn_id" {
  value = oci_core_vcn.this.id
}

output "data_subnet_id" {
  value       = oci_core_subnet.data.id
  description = "Use for AIDP private network access and database private endpoints."
}

output "db_nsg_id" {
  value = oci_core_network_security_group.db.id
}

output "staging_bucket" {
  value = oci_objectstorage_bucket.staging.name
}

output "objectstorage_namespace" {
  value = data.oci_objectstorage_namespace.this.namespace
}

output "vault_id" {
  value = oci_kms_vault.this.id
}

output "secret_ids" {
  value       = { for k, s in oci_vault_secret.db : k => s.id }
  description = "Vault secrets holding generated database passwords; read with: oci secrets secret-bundle get --secret-id <id>"
}

output "sample_source_db_id" {
  value = var.deploy_sample_source ? oci_database_autonomous_database.sample_source[0].id : null
}

output "ops_topic_id" {
  value = oci_ons_notification_topic.ops.id
}

output "next_steps" {
  value = <<-EOT
    1. Load the source: bash foundation/source/sample-bank/deploy_sample_source.sh (FROM_TERRAFORM=true), or foundation/source/own-flexcube for your FLEXCUBE copy
    2. In AIDP: Spark cluster, catalogs fcubs_source and fcubs_lake, foundation notebooks (docs/foundation/02_deploy.md, steps 3 to 5)
    3. Serving layer: bash foundation/serving/deploy_serving_layer.sh <AIDP Lakehouse OCID> (step 6)
    4. Enable use-case modules: use-cases/README.md
  EOT
}
