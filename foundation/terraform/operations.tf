# Operations: log group with VCN flow logs, and a notification topic for platform and pipeline alerts.
resource "oci_logging_log_group" "this" {
  compartment_id = local.compartment_id
  display_name   = "${var.prefix}-logs"
  description    = "Extend FLEXCUBE on OCI: network flow logs and service logs"
  freeform_tags  = local.tags
}

resource "oci_logging_log" "subnet_flow" {
  display_name       = "${var.prefix}-subnet-data-flow"
  log_group_id       = oci_logging_log_group.this.id
  log_type           = "SERVICE"
  is_enabled         = true
  retention_duration = 90
  configuration {
    compartment_id = local.compartment_id
    source {
      category    = "all"
      resource    = oci_core_subnet.data.id
      service     = "flowlogs"
      source_type = "OCISERVICE"
    }
  }
  freeform_tags = local.tags
}

resource "oci_ons_notification_topic" "ops" {
  compartment_id = local.compartment_id
  name           = "${var.prefix}-ops-alerts"
  description    = "Pipeline failures, data quality and platform alerts"
  freeform_tags  = local.tags
}

resource "oci_ons_subscription" "ops_email" {
  count          = var.notification_email == "" ? 0 : 1
  compartment_id = local.compartment_id
  topic_id       = oci_ons_notification_topic.ops.id
  protocol       = "EMAIL"
  endpoint       = var.notification_email
  freeform_tags  = local.tags
}
