# 1. Security and privacy

The quick start is safe for synthetic data. Before real FLEXCUBE data enters the platform, apply these controls and record
them in the bank's security assessment.

## Identity and access

| Control | Implementation |
|---|---|
| Least-privilege source access | `AIDP_READER` with SELECT on the listed tables only, on a copy; no DML, no DBA roles |
| Separation of duties in serving | `FCUBS_GOLD` writes (publish notebooks only); `AIDP_AGENT` reads (agents only) |
| Administrators | Named group with the policies in [IAM](../foundation/01_prerequisites_and_iam.md); MFA through the identity domain |
| Business users | AIDP workspace roles for Agent Hub use only; no catalog, notebook or compute rights |
| Agent identity | Deploy agents with a dedicated identity; for multi-user channels map each user to their portfolio and filter in the tool SQL |
| Service-to-service | Resource principals for container workloads (Slack bridge); no API keys on servers |

## Secrets

- Terraform generates every database password into OCI Vault; scripts read them from Vault. Rotate them on the bank's
  schedule by updating the secret and the database user together, then the AIDP catalog connection.
- Third-party tokens (Slack, Teams) live in the AIDP Credential Store, never in notebooks or repositories.
- Use a remote, access-controlled Terraform state backend: state contains generated values.

## Network

- Private endpoints for the source copy and the AIDP Lakehouse; AIDP private network access into the solution subnet.
- No internet gateway in the solution VCN. Egress only through the NAT gateway, restricted by the bank's egress controls to
  the destinations a module needs (for example slack.com).
- FastConnect or private interconnect for sources outside OCI; Site-to-Site VPN only for pilots.
- VCN flow logs are on (90-day retention by default); forward them to the bank's SIEM.

## Encryption

- At rest: Object Storage bucket encrypted with the Vault key; Autonomous databases encrypted by default, with customer-managed
  keys if policy requires.
- In transit: TLS to databases (port 1522 or TLS on 1521), HTTPS to every service endpoint.

## Privacy by design

| Principle | How |
|---|---|
| Minimise | No module needs card numbers, IBANs or national identifiers. Grant `AIDP_READER` on views that exclude them, or apply Oracle Data Redaction on the copy |
| Purpose limitation | Each module documents the tables and columns it uses and why |
| Fairness | Nationality, gender and other protected attributes are reporting-only; never features, rules or rankings; agents refuse protected-attribute ranking |
| Explainability | Every flag carries plain-language reasons; ML outputs carry their own drivers |
| Data leaving OCI | Alerts to collaboration tools carry customer names only with approval; otherwise customer numbers |
| Retention | Serving tables keep history by as-of date; set a retention job aligned to the bank's policy |
| Non-production | Development and test use the sample bank or a masked copy, never production data |

## Generative AI

- Agents read only curated serving tables through read-only tools with row limits; they cannot write anywhere.
- Guardrails: PII masking on input and output (with the Telephone exception for amounts), content moderation, prompt-injection
  blocking.
- Prompts and responses stay in the region; review the model provider terms with the bank's legal team.
- Keep agent traces for audit for the retention period the bank requires.

## Audit

OCI Audit records every control-plane action. Notebook runs, workflow runs, MLflow runs and agent traces record the data
plane. Alert notebooks write their own audit tables (for example `rm_alert_log`).
