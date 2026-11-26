# FLEXCUBE source

Choose one: the synthetic sample bank, or a copy of your own FLEXCUBE. Everything downstream is identical.

## Sample bank (`sample-bank/`)

"Oasis Demo Bank" is a fictional UAE retail and SME bank (AED, branch date 21 Oct 2026): 2,000 customers, 3,288 accounts,
12.7 months of history, 843,248 balanced accounting entries, 230,613 card transactions and 486 loans with schedules and
payments, in 34 tables with FLEXCUBE UBS structure. Planted scenarios (job loss, SME revenue drop, churn, plus AML and card
patterns for future modules) come with an answer key that AIDP never sees.

| Path | What it is |
|---|---|
| `data/` | 34 tables as compressed CSV and `manifest.json` with row counts |
| `generator/` | Python generator (deterministic seed) and `validate.py` integrity checks |
| `sql/` | Schema with keys and 43 foreign keys, the one-shot load from Object Storage, the reader grant, verify and drop scripts |
| `validation/` | Answer key for offline validation only |
| `deploy_sample_source.sh`, `deploy.env.example` | One-command load |

```bash
cp foundation/source/sample-bank/deploy.env.example foundation/source/sample-bank/deploy.env
bash foundation/source/sample-bank/deploy_sample_source.sh
```

With `FROM_TERRAFORM=true` the script uses the bucket, database and Vault secrets from the Terraform foundation; otherwise it
creates a bucket and database with the OCI CLI and prompts for passwords. It is safe to re-run. Set `REGENERATE=true` (and
`CUSTOMERS`) to rebuild the data first.

**Console-only alternative:** create the database and a private bucket, upload `data/*.csv.gz`,
`validation/DEMO_SCENARIO_LABELS.csv.gz`, `sql/01_create_tables.sql` and `sql/03_constraints.sql`; create a one-day read-only
pre-authenticated request on the bucket; in Database Actions as ADMIN run `sql/10_build_from_bucket.sql` with the request URL
in place of `PASTE_PAR_URL_HERE`, then `sql/20_aidp_reader.sql` with a password; delete the request.

## Your own FLEXCUBE (`own-flexcube/`)

| Script | Run as | What it does |
|---|---|---|
| `01_create_aidp_reader.sql` | DBA on the copy | Creates `AIDP_READER` with SELECT on the 15 tables the foundation needs (expected: 15 grants) |
| `02_precheck.sql` | DBA on the copy | Visibility, comment lengths, history depth, volumes, and your most used transaction codes |

Then follow [source patterns](../../docs/foundation/03_source_patterns.md) for connectivity and the settings to adapt.
