# 1. Prerequisites and IAM

## Tenancy and region

- A region where **Oracle AI Data Platform** and **OCI Generative AI** on-demand chat models (with tool calling) are both
  available. Check the current region lists in the product documentation before you start.
- Service limits for one AIDP instance, one Autonomous AI Database (sample bank only), one Vault and one VCN in the target
  compartment.

## Who deploys

| Task | Needs |
|---|---|
| Terraform foundation with `create_iam_policies = true` | Manage policies in the tenancy root (or an administrator runs it once) |
| Terraform foundation with `create_iam_policies = false` | Manage the resources below in the target compartment; an administrator creates the policies from this page |
| Source load and serving layer scripts | OCI CLI with an API key or session token, read access to the Vault secrets |
| AIDP configuration (catalogs, notebooks, agents) | Member of the AIDP administrator group |

## Tools on the deploying machine

- Terraform 1.5 or later with the OCI provider 7.22.0 or later, **or** OCI Resource Manager (nothing to install)
- OCI CLI configured (`oci setup config`), bash, curl, python3
- Optional: `pip install duckdb` to run the sample data integrity checks

## IAM policies

Terraform creates these when `create_iam_policies = true`. They are created in the root compartment (some statements are tenancy-wide) and scoped to the solution compartment
wherever possible. Replace `<compartment-ocid>` and `<region>` if you create them yourself.

### AI Data Platform service

```text
allow any-user TO {AUTHENTICATION_INSPECT, DOMAIN_INSPECT, DOMAIN_READ, DYNAMIC_GROUP_INSPECT, GROUP_INSPECT, GROUP_MEMBERSHIP_INSPECT, USER_INSPECT, USER_READ} IN TENANCY where all {request.principal.type='aidataplatform'}
allow any-user to manage log-groups in compartment id <compartment-ocid> where ALL { request.principal.type='aidataplatform' }
allow any-user to read log-content in compartment id <compartment-ocid> where ALL { request.principal.type='aidataplatform' }
allow any-user to use metrics in compartment id <compartment-ocid> where ALL {request.principal.type='aidataplatform', target.metrics.namespace='oracle_aidataplatform'}
allow any-user to manage buckets in compartment id <compartment-ocid> where all { request.principal.type='aidataplatform', any {request.permission = 'BUCKET_CREATE', request.permission = 'BUCKET_INSPECT', request.permission = 'BUCKET_READ', request.permission = 'BUCKET_UPDATE'}}
allow any-user to {TAG_NAMESPACE_USE} in tenancy where all {request.principal.type = 'aidataplatform'}
allow any-user to manage buckets in compartment id <compartment-ocid> where all { request.principal.id=target.resource.tag.orcl-aidp.governingAidpId, any {request.permission = 'BUCKET_DELETE', request.permission = 'PAR_MANAGE', request.permission = 'RETENTION_RULE_LOCK', request.permission = 'RETENTION_RULE_MANAGE'} }
allow any-user to read objectstorage-namespaces in compartment id <compartment-ocid> where all { request.principal.type='aidataplatform', any {request.permission = 'OBJECTSTORAGE_NAMESPACE_READ'}}
allow any-user to manage objects in compartment id <compartment-ocid> where all { request.principal.id=target.bucket.system-tag.orcl-aidp.governingAidpId  }
allow any-user to use generative-ai-family in tenancy where all { request.principal.type='aidataplatform'}
allow service objectstorage-<region> to manage object-family in compartment id <compartment-ocid>
```

These follow the AIDP documentation (compartment-level option) and are the exact statements in
[`foundation/terraform/iam.tf`](../../foundation/terraform/iam.tf). If AIDP publishes new statements, add them there: an
instance that lacks a newer statement can fail late in provisioning with an empty error log.

### Private network access (optional, recommended)

```text
allow any-user to manage vnics in compartment id <compartment-ocid> where all { request.principal.type='aidataplatform'}
allow any-user to use subnets in compartment id <compartment-ocid> where all { request.principal.type='aidataplatform'}
allow any-user to use network-security-groups in compartment id <compartment-ocid> where all { request.principal.type='aidataplatform'}
```

### Administrators (optional, when `aidp_admin_group` is set)

```text
allow group <aidp-admins> to manage ai-data-platforms in compartment id <compartment-ocid>
allow group <aidp-admins> to manage autonomous-databases in compartment id <compartment-ocid>
allow group <aidp-admins> to use generative-ai-family in tenancy
allow group <aidp-admins> to read secret-bundles in compartment id <compartment-ocid>
```

Give business users only the AIDP workspace roles they need (for example agent use in Agent Hub), not these statements.

## Checklist

- [ ] Region offers AIDP and on-demand Generative AI chat models
- [ ] Compartment chosen (or `create_compartment = true`)
- [ ] Policies created by Terraform or an administrator
- [ ] Network CIDRs agreed with the network team (defaults `10.80.0.0/16`, subnet `10.80.10.0/24`)
- [ ] For your own FLEXCUBE: a copy identified and its connectivity agreed (see [source patterns](03_source_patterns.md))

Next: [Deploy the foundation](02_deploy.md).
