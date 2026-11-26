# 4. The shared data foundation

```text
FLEXCUBE copy  ->  fcubs_source (external catalog, read-only, no copy)
  -> fcubs_lake.bronze (15 tables, as in FLEXCUBE)  ->  fcubs_lake.silver (6 conformed data products)  ->  module gold schemas
```

The foundation interprets FLEXCUBE once. Modules read silver (and bronze only where they need a raw detail) and never write
to either. All notebooks are safe to re-run. Sample row counts are in brackets.

## Bronze: `fnd_01_bronze`

- A 1:1 copy of the FLEXCUBE tables in `REQUIRED`, same names and columns, plus `_ingest_ts` and `_source` for lineage.
- Stops with a clear message if a required table is missing (usually a missing grant).
- `COPY_ALL = True` copies every table in the source schema: fine for the 34-table sample, never for a real FLEXCUBE schema.
- Why: analytics must not query the core on every run; bronze is the auditable landing zone and can be reloaded at any time.
- For large banks, change the `ACTB_HISTORY` and `ACTB_ACCBAL_HISTORY` copies to incremental loads on the transaction date
  (see [operations](../path-to-production/05_operations.md#scaling-bronze)).

## Silver: `fnd_02_silver`

FLEXCUBE codes become readable values, types are cast, related tables are joined, one clear grain per table. The as-of
(branch) date is derived automatically: the day after the latest `ACTB_HISTORY` posting (sample: 2026-10-21). Set `AS_OF` only
to back-test a past date.

| Data product | Grain | From | What it adds |
|---|---|---|---|
| `customer_360` (2,000) | customer | customer, personal, corporate, KYC and credit score tables | One profile: segment, branch, RM, KYC and AML risk, bureau score or internal rating, age, business profile. Nationality and gender kept for reporting only |
| `accounts` (3,288) | account | customer account and account class | Readable class, booleans for salary, dormant and closed, limits and balance |
| `account_daily_balance` (303,687) | account and day with movement | balance history | Clean daily balances for trends |
| `transactions` (430,019) | customer-side posting | `ACTB_HISTORY`, transaction codes | Customer legs only, each mapped to one of 13 categories, signed amount |
| `loan_status` (486) | loan | loan master, schedules, payments, user-defined values | Overdue amount, days past due, instalments, next due date, last payment, rate, DPD bucket |
| `card_spend` (230,613) | card transaction | settlement history | Merchant category, essential spend flag, domestic or foreign, approved or declined |

### Bank-specific settings

FLEXCUBE is configured per bank. Review these with the bank's FLEXCUBE team before trusting any module's output:

| Setting | Where | Why it matters |
|---|---|---|
| `TRN_CATEGORY` | Cell 5 | Maps your transaction codes to the 13 categories (salary_in, card_spend, cash_out, cash_in, transfer_in, transfer_out, payroll_out, loan_repayment, loan_disbursement, bill_payment, fees, interest_in, term_deposit). Every cash-flow feature depends on it. `02_precheck.sql` lists your most used codes |
| `mcc_map` | Cell 7 | Merchant category codes to readable categories and the essential flag |
| Customer categories (`segment`) | Cell 2 | Your customer category codes for individual, priority, staff, SME and corporate |
| Score types | Cell 2 | Which credit score types become `bureau_score` and `internal_rating` |

The quality gate warns when more than 20 percent of transactions are uncategorised.

## Quality gate: `fnd_03_quality_checks`

14 checks; any failure raises an error and stops the workflow before modules run:

- Bronze row counts match the source for 5 key tables, within `TOLERANCE` (use `0.01` for a copy still receiving postings)
- All 6 silver data products are non-empty
- `customer_360` has exactly one row per customer
- Every account belongs to a customer
- Fewer than 20 percent of transactions are uncategorised

Modules add their own gates (for example `cf_02_quality_checks`). More on extending checks:
[data quality](../path-to-production/04_data_quality.md).

## Adding to the foundation

Add a silver data product only when two or more modules need it; otherwise keep it in the module's gold schema. A new bronze
table means a new grant in `01_create_aidp_reader.sql`, an entry in `REQUIRED`, and a line in the module's README listing the
tables it needs.
