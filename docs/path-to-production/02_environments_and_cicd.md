# 2. Environments and CI/CD

## Environments

| | Development | Test (UAT) | Production |
|---|---|---|---|
| Compartment, VCN, Vault, AIDP | Own | Own | Own |
| Source | Sample bank | Masked copy of FLEXCUBE, or the sample bank plus a masked extract | FLEXCUBE copy (standby, clone or replica) |
| Who changes it | Developers | Release pipeline only | Release pipeline only |
| Agent users | Developers | Business testers | Business users |
| Schedules | Manual runs | Daily, as production | Daily after end of day |

Deploy each environment from the same Terraform with its own variables file and remote state, for example
`env/dev.tfvars`, `env/test.tfvars`, `env/prod.tfvars` (git-ignored if they hold anything sensitive).

## What is code

| Asset | Source of truth | Promotion |
|---|---|---|
| Infrastructure | `foundation/terraform` | Plan reviewed in the pull request, applied by the pipeline per environment |
| Database objects | `foundation/source/*/`, `foundation/serving/sql`, `use-cases/*/sql` | Scripts are idempotent; run by the pipeline after Terraform |
| Notebooks | `*/notebooks/src/*.py` | `.ipynb` built with `tools/build_notebooks.py`, imported into the target workspace |
| Agent | `use-cases/*/agent/*.md` | Configured from the specification and tested against its demo questions before deployment |
| Thresholds and mappings | Notebook settings cells (`TRN_CATEGORY`, rules, bands) | Same as notebooks; changes reviewed by the business owner |

## Pipeline

1. **Pull request:** [`ci.yml`](../../.github/workflows/ci.yml) runs `terraform fmt` and `validate`, shell syntax, notebook
   build check, sample data integrity, and the full local pipeline on the sample bank. A failing check blocks the merge.
2. **Merge to main:** deploy to development; run the workflow on the sample bank; compare the module results with the
   documented figures.
3. **Release tag:** deploy to test; business testers run each module's demo questions and sign off.
4. **Approval:** deploy to production in a change window; run the workflow once manually; enable the schedule.

Use OCI DevOps or GitHub Actions with OCI credentials stored as pipeline secrets (or OIDC federation where available). Import
notebooks and configure workflows through the AIDP console or its APIs, depending on what your AIDP release exposes.

## Rollback

Keep the previous notebook version in Git and redeploy it. Serving tables keep history by as-of date, so a bad run can be
deleted for that date and the previous run republished. Agents can be redeployed from the previous specification.
