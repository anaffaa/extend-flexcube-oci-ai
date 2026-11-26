# Path A: Autonomous AI Database that hosts the synthetic FLEXCUBE sample bank (schema FCUBS).
# For your own FLEXCUBE (path B), set deploy_sample_source = false and connect a replica, standby or clone instead.
resource "oci_database_autonomous_database" "sample_source" {
  count                               = var.deploy_sample_source ? 1 : 0
  compartment_id                      = local.compartment_id
  db_name                             = var.sample_db_name
  display_name                        = var.sample_db_name
  db_workload                         = "OLTP"
  compute_model                       = "ECPU"
  compute_count                       = var.sample_db_ecpu
  data_storage_size_in_gb             = var.sample_db_storage_gb
  is_auto_scaling_enabled             = false
  is_auto_scaling_for_storage_enabled = false
  backup_retention_period_in_days     = 7
  admin_password                      = random_password.db["sample-db-admin"].result

  # Private endpoint (production pattern) or public endpoint limited to an allow list (quick start).
  subnet_id              = var.sample_db_private_endpoint ? oci_core_subnet.data.id : null
  nsg_ids                = var.sample_db_private_endpoint ? [oci_core_network_security_group.db.id] : null
  private_endpoint_label = var.sample_db_private_endpoint ? lower(var.sample_db_name) : null
  whitelisted_ips        = var.sample_db_private_endpoint ? null : (length(var.sample_db_allowed_cidrs) > 0 ? var.sample_db_allowed_cidrs : null)

  freeform_tags = local.tags
}
