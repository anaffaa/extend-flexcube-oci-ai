# 2. Deploy the foundation

About half a day, most of it waiting for provisioning. At the end you have the shared data foundation (bronze, silver and
quality checks) running on your chosen FLEXCUBE source, and the serving layer ready for use-case modules.

| Step | What | How | Time |
|---|---|---|---|
| 1 | Network, Vault, bucket, AIDP, IAM, logging, optional sample database | Terraform or Resource Manager | 60 to 90 min |
| 2 | Load the FLEXCUBE source | Script (sample bank) or DBA scripts (your FLEXCUBE) | 15 min |
| 3 | Spark cluster | AIDP console | 10 min |
| 4 | Catalogs `fcubs_source` and `fcubs_lake` | AIDP console | 10 min |
| 5 | Foundation notebooks: bronze, silver, quality checks | AIDP console | 20 to 60 min |
| 6 | Serving layer users, tables and catalogs | Script plus AIDP console | 15 min |
| 7 | Enable use-case modules | Each module's README | per module |
| 8 | Daily workflow | AIDP console | 10 min |

Names used throughout (change them consistently if you must): workspace `flexcube`, cluster `fcubs_spark`, catalogs
`fcubs_source`, `fcubs_lake`, `fcubs_serving_rw`, `fcubs_serving`.

## Step 1: deploy the foundation

**Option A: Resource Manager (console).** Create a stack from this repository's `foundation/terraform` folder (zip it, or
use the Deploy to Oracle Cloud button once published), pick the compartment, review the variable groups and apply.

**Option B: Terraform CLI.**

```bash
cd foundation/terraform
cat > terraform.tfvars <<EOF
tenancy_ocid     = "ocid1.tenancy.oc1..."
region           = "eu-frankfurt-1"
compartment_ocid = "ocid1.compartment.oc1..."
# deploy_sample_source       = false   # when you connect your own FLEXCUBE copy
# sample_db_allowed_cidrs    = ["203.0.113.0/24"]
# aidp_admin_group           = "aidp-admins"
# notification_email         = "ops@yourbank.com"
EOF
terraform init && terraform plan -out tf.plan && terraform apply tf.plan
terraform output next_steps
```

Use a remote state backend (an Object Storage bucket) for anything beyond a trial: the state contains the generated
passwords. `*.tfvars` and state files are git-ignored.

What you get: VCN with a private subnet, NAT and service gateways, flow logs; NSG for database endpoints; Vault, key and five
generated password secrets (`sample-db-admin`, `aidp-reader`, `lakehouse-admin`, `fcubs-gold`, `aidp-agent`); a private
staging bucket; the AIDP instance and its AIDP Lakehouse; IAM policies; an operations topic; and, unless disabled, the
Autonomous AI Database for the sample bank. AIDP can take over an hour on first creation.

## Step 2: load the FLEXCUBE source

### Sample bank

```bash
cp foundation/source/sample-bank/deploy.env.example foundation/source/sample-bank/deploy.env
# set FROM_TERRAFORM=true (or set COMPARTMENT_OCID to create everything with the CLI instead)
bash foundation/source/sample-bank/deploy_sample_source.sh
```

The script uploads the 34 synthetic tables, builds schema `FCUBS` with keys and 43 foreign keys, loads the answer key into
`DEMOMETA` (never granted to AIDP) and creates the read-only user `AIDP_READER`. With `FROM_TERRAFORM=true` it reads the
passwords from Vault; otherwise it prompts. Expected check: 34 tables, 2,000 customers, 34 grants. Details and a console-only
alternative: [`foundation/source/README.md`](../../foundation/source/README.md).

If you chose a private endpoint for the sample database, run the script from a host inside the VCN (for example through OCI
Bastion), because it uses the database's REST-enabled SQL endpoint.

### Your own FLEXCUBE

Pick your source pattern and set up connectivity first: [source patterns](03_source_patterns.md). Then, as a DBA on the copy:

```sql
@foundation/source/own-flexcube/01_create_aidp_reader.sql   -- read-only user, SELECT on the 15 tables only
@foundation/source/own-flexcube/02_precheck.sql             -- every line should say OK
```

Store the `AIDP_READER` password in the Vault secret `aidp-reader` (or your own) rather than in a document.

## Step 3: Spark cluster

AIDP > workspace `flexcube` > **Compute** > Create > Cluster:

| Field | Value |
|---|---|
| Name | `fcubs_spark` |
| Spark | 3.5 |
| Shape | AMD or Intel (MLflow model logging does not run on ARM), driver and worker 2 OCPU |
| Workers | 1 for the sample bank; size to your history volume for real data |
| Idle timeout | 30 minutes |
| Libraries (PyPI) | `mlflow`, `scikit-learn` (needed by ML notebooks in the modules) |

Leave the default master catalog compute cluster alone; AIDP manages it.

## Step 4: catalogs

**Create > Catalog**:

1. `fcubs_source`, **External catalog** on your source database, user `AIDP_READER`, service `_low` (or your service name).
   For a private endpoint, turn on private network access and select the solution's data subnet. Refresh until every
   granted table appears (sample: 34; your FLEXCUBE: at least 15).
2. `fcubs_lake`, **Standard catalog**. The notebooks create its schemas: `bronze` and `silver` (shared) and one gold schema per
   module.

## Step 5: foundation notebooks

Import [`foundation/lakehouse/notebooks/`](../../foundation/lakehouse/notebooks) into the workspace, attach each to
`fcubs_spark` and **Run all** in order:

| Order | Notebook | Writes | Sample result |
|---|---|---|---|
| 1 | `fnd_01_bronze` | `fcubs_lake.bronze`: the 15 FLEXCUBE tables with `_ingest_ts` and `_source` | 15 tables |
| 2 | `fnd_02_silver` | `fcubs_lake.silver`: `customer_360`, `accounts`, `account_daily_balance`, `transactions`, `loan_status`, `card_spend` | 2,000 customers, 430,019 transactions |
| 3 | `fnd_03_quality_checks` | nothing; fails the run when a check fails | "All 14 foundation checks passed." |

Your own FLEXCUBE: set `SRC` in `fnd_01_bronze` and `fnd_03_quality_checks`, and map your transaction codes in
`fnd_02_silver` first ([data foundation](04_data_foundation.md#bank-specific-settings)).

## Step 6: serving layer

Find the AIDP Lakehouse OCID (Autonomous AI Database in the solution compartment whose name starts with `Aidp`) and run:

```bash
bash foundation/serving/deploy_serving_layer.sh <Lakehouse OCID>    # all modules that ship serving SQL
# or only some modules:
bash foundation/serving/deploy_serving_layer.sh <Lakehouse OCID> 01-cashflow-intelligence
```

It creates `FCUBS_GOLD` (publisher, owns the serving tables) and `AIDP_AGENT` (read-only), then each module's serving
tables. Passwords come from Vault with `FROM_TERRAFORM=true`; otherwise it prompts. Safe to re-run.

Then create two **External catalogs** on the AIDP Lakehouse, service `_low`:

| Catalog | User | Used by |
|---|---|---|
| `fcubs_serving_rw` | `FCUBS_GOLD` | Publish notebooks only |
| `fcubs_serving` | `AIDP_AGENT` | Agent SQL tools (read-only) |

When a serving table's columns change later, use the **table-level refresh** next to that table: a catalog-level refresh
keeps the old column list.

## Step 7: enable use-case modules

| Module | Status | Start here |
|---|---|---|
| 01 Cash-flow intelligence | Available | [use-cases/01-cashflow-intelligence](../../use-cases/01-cashflow-intelligence/README.md) |
| 02 Reconciliation watch | Design | [use-cases/02-reconciliation-watch](../../use-cases/02-reconciliation-watch/README.md) |
| 03 FLEXCUBE data copilot | Design | [use-cases/03-flexcube-data-copilot](../../use-cases/03-flexcube-data-copilot/README.md) |
| 04 SME supply chain and life events | Design | [use-cases/04-sme-supply-chain-and-life-events](../../use-cases/04-sme-supply-chain-and-life-events/README.md) |

## Step 8: daily workflow

Workspace > **Workflows** > Jobs > Create job `fcubs_daily_pipeline`, max concurrent runs 1. Add Notebook tasks on
`fcubs_spark`, retries 1, each depending on the previous one ("Run if: success"):

```text
fnd_01_bronze > fnd_02_silver > fnd_03_quality_checks > <module tasks, in each module's documented order>
```

Modules that do not depend on each other can run in parallel after `fnd_03_quality_checks`. Schedule after FLEXCUBE end of day
in your time zone, and send failures to the operations topic or watch **Job runs** (see
[operations](../path-to-production/05_operations.md)). Keep the schedule paused while a non-production source database is stopped.

## Clean up

`terraform destroy` removes everything Terraform created, including the AIDP instance and its Lakehouse (Vault keys enter a
pending deletion period). Delete any catalogs, clusters and AI compute you created in AIDP first if destroy reports
dependencies. To pause instead: stop the sample database and the Spark cluster, undeploy agents, and pause the workflow.
