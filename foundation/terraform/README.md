# Terraform foundation

Deploys the shared infrastructure for Extend FLEXCUBE on OCI. Works with the Terraform CLI and with OCI Resource Manager
(`schema.yaml` groups the variables in the console).

| File | Resources |
|---|---|
| `versions.tf` | Providers: `oracle/oci` 7.22.0 or later (AIDP resource), `hashicorp/random`; a home-region alias for IAM |
| `main.tf` | Tenancy, regions and namespace lookups; optional child compartment |
| `network.tf` | VCN, NAT and service gateways, private route table, security list, private data subnet, NSG `db` |
| `security.tf` | Vault, AES key, generated passwords, Vault secrets |
| `storage.tf` | Private, versioned, KMS-encrypted staging bucket |
| `aidp.tf` | Oracle AI Data Platform instance and default workspace (creates its AIDP Lakehouse) |
| `database.tf` | Optional Autonomous AI Database for the synthetic sample bank |
| `iam.tf` | AIDP service policy (compartment-scoped) and optional administrator policy |
| `operations.tf` | Log group, subnet flow logs, operations topic and email subscription |
| `outputs.tf` | IDs, secret OCIDs and next steps (read by the scripts with `FROM_TERRAFORM=true`) |

## Key variables

| Variable | Default | Notes |
|---|---|---|
| `compartment_ocid` | required | Target, or parent when `create_compartment = true` |
| `prefix` | `fcubs` | Resource name prefix |
| `vcn_cidr`, `data_subnet_cidr` | `10.80.0.0/16`, `10.80.10.0/24` | Agree with the network team before peering |
| `create_iam_policies` | `true` | Needs tenancy policy rights; otherwise an administrator applies the statements |
| `aidp_admin_group` | empty | Group to administer AIDP in the compartment |
| `deploy_sample_source` | `true` | Set `false` when connecting your own FLEXCUBE copy |
| `sample_db_private_endpoint` | `false` | `true` mirrors production; load from a host in the VCN |
| `sample_db_allowed_cidrs` | empty | Allow list for the public endpoint |
| `notification_email` | empty | Subscribed to the operations topic |

## Use

```bash
terraform init
terraform plan -out tf.plan -var-file env/dev.tfvars
terraform apply tf.plan
terraform output next_steps
```

Use a remote backend for state (it holds generated passwords) and one variables file and state per environment. `terraform
destroy` removes everything, including the AIDP instance and its Lakehouse.
