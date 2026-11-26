# ---------- Tenancy and placement (filled automatically by Resource Manager) ----------
variable "tenancy_ocid" {
  type        = string
  description = "Tenancy OCID."
}

variable "region" {
  type        = string
  description = "Region for all resources, for example eu-frankfurt-1. Must offer AI Data Platform and OCI Generative AI."
}

variable "compartment_ocid" {
  type        = string
  description = "Compartment for the stack. With create_compartment = true, a child compartment is created inside it."
}

variable "create_compartment" {
  type        = bool
  default     = false
  description = "Create a dedicated child compartment for the solution."
}

variable "compartment_name" {
  type        = string
  default     = "flexcube-ai-extension"
  description = "Name of the child compartment when create_compartment = true."
}

variable "prefix" {
  type        = string
  default     = "fcubs"
  description = "Short prefix for resource names (lowercase letters and digits)."
  validation {
    condition     = can(regex("^[a-z][a-z0-9]{1,11}$", var.prefix))
    error_message = "Use 2 to 12 lowercase letters or digits, starting with a letter."
  }
}

# ---------- Network ----------
variable "vcn_cidr" {
  type        = string
  default     = "10.80.0.0/16"
  description = "VCN CIDR. Must not overlap with networks you connect over FastConnect, VPN or peering (for example the FLEXCUBE network)."
}

variable "data_subnet_cidr" {
  type        = string
  default     = "10.80.10.0/24"
  description = "Private subnet for database private endpoints and AIDP private network access."
}

# ---------- Identity ----------
variable "create_iam_policies" {
  type        = bool
  default     = true
  description = "Create the AI Data Platform service policies (requires permission to manage policies in the tenancy)."
}

variable "aidp_admin_group" {
  type        = string
  default     = ""
  description = "Optional group allowed to manage AI Data Platform and Autonomous AI Databases in the compartment, e.g. Default/aidp-admins."
}

variable "enable_private_network_policies" {
  type        = bool
  default     = true
  description = "Allow AIDP compute clusters to use VNICs, subnets and NSGs in the compartment (needed to reach private FLEXCUBE databases)."
}

# ---------- AI Data Platform ----------
variable "aidp_display_name" {
  type        = string
  default     = "flexcube-ai"
  description = "AI Data Platform instance name."
}

variable "aidp_workspace_name" {
  type        = string
  default     = "flexcube"
  description = "Default workspace. Use letters, digits and underscores."
}

# ---------- Sample FLEXCUBE source (path A) ----------
variable "deploy_sample_source" {
  type        = bool
  default     = true
  description = "Create an Autonomous AI Database for the synthetic FLEXCUBE sample bank. Set false when you connect your own FLEXCUBE."
}

variable "sample_db_name" {
  type        = string
  default     = "FCUBSDEMO"
  description = "Database name of the sample source (letters and digits, up to 14 characters)."
}

variable "sample_db_ecpu" {
  type        = number
  default     = 2
  description = "ECPUs for the sample source (2 is the minimum)."
}

variable "sample_db_storage_gb" {
  type        = number
  default     = 20
  description = "Storage in GB for the sample source."
}

variable "sample_db_private_endpoint" {
  type        = bool
  default     = false
  description = "Place the sample source on a private endpoint in the data subnet (production pattern). When false, it uses a public endpoint restricted to sample_db_allowed_cidrs."
}

variable "sample_db_allowed_cidrs" {
  type        = list(string)
  default     = []
  description = "Public IPs or CIDRs allowed to reach the sample source (your workstation, to run the load script). Ignored with a private endpoint."
}

# ---------- Operations ----------
variable "notification_email" {
  type        = string
  default     = ""
  description = "Optional email subscribed to the operations topic (pipeline and platform alerts). Confirm the subscription email."
}

variable "freeform_tags" {
  type        = map(string)
  default     = { "solution" = "extend-flexcube-oci-ai" }
  description = "Tags applied to every resource."
}
