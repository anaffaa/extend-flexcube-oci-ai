# 8. Go-live checklist

Use this per module and per environment. Every item needs an owner and evidence.

## Governance

- [ ] Business owner and data owner named for the module
- [ ] Use case approved by risk, compliance and data protection, including any data leaving OCI (alert channels)
- [ ] Model cards approved by model risk (modules with ML)
- [ ] Agent use approved, with the user population and channels listed

## Data

- [ ] Source is a copy, never the primary; refresh or apply lag known and inside the schedule
- [ ] `AIDP_READER` grants limited to the documented tables; personal data minimised (views or redaction)
- [ ] Transaction codes, merchant categories, segments and score types mapped and signed off
- [ ] Thresholds and bands reviewed with the business owner
- [ ] Back-test on the bank's own outcomes completed and documented
- [ ] Quality gates pass on the production copy; production-grade checks added (freshness, volume, sums)

## Security

- [ ] Private endpoints and AIDP private network access in use; no public database endpoints
- [ ] Secrets in Vault and the Credential Store only; rotation scheduled
- [ ] Administrators in a named group with MFA; business users with Agent Hub access only
- [ ] Multi-user channels map each user to their own portfolio
- [ ] Flow logs and audit forwarded to the SIEM

## Operations

- [ ] Workflow scheduled after end of day; failures alert the operations topic
- [ ] Runbook handed to the support team; on-call contact defined
- [ ] Model and data drift monitoring in place
- [ ] Cost tags applied; budget alert set on the compartment
- [ ] DR procedure written and tested

## Release

- [ ] All CI checks green on the release commit
- [ ] Test environment sign-off by business testers using the module's demo questions
- [ ] Change approved; rollback plan (previous notebooks, agent version, serving data by as-of date) confirmed
- [ ] First production run checked manually before enabling the schedule
