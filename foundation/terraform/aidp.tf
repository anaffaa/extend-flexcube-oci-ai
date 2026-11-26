# Oracle AI Data Platform instance. AIDP creates its own Autonomous AI Lakehouse (26ai) for the serving layer and AI
# features. Its ADMIN password is generated here and also stored in the Vault secret "lakehouse-admin" for scripts.
resource "oci_ai_data_platform_ai_data_platform" "this" {
  compartment_id         = local.compartment_id
  display_name           = var.aidp_display_name
  default_workspace_name = var.aidp_workspace_name
  is_enable_ai_feature   = true
  vector_db_admin_cred   = random_password.db["lakehouse-admin"].result
  freeform_tags          = local.tags

  timeouts {
    create = "120m" # first builds can take over an hour
  }

  depends_on = [oci_identity_policy.aidp_service]
}
