# 4. Data quality

Quality is enforced by gate notebooks that fail the workflow, so bad data never reaches agents or alerts. The last good
serving data stays available while the issue is fixed.

| Gate | Runs after | Checks |
|---|---|---|
| `fnd_03_quality_checks` | silver | Bronze reconciles with the source (row counts within `TOLERANCE`); silver products non-empty; one row per customer; no orphan accounts; under 20 percent uncategorised transactions |
| Module gates (for example `cf_02_quality_checks`) | module gold | Gold non-empty; coverage of every customer; band shares within expected range |

## Extending the gates for production

| Check | Why |
|---|---|
| Freshness: latest `ACTB_HISTORY` date equals the expected business date | Catches a copy that stopped refreshing |
| Volume: today's postings within 3 standard deviations of the same weekday | Catches partial loads |
| Sum reconciliation: total debits equal total credits per day in bronze | FLEXCUBE double entry must hold |
| Key integrity: every loan and account maps to a customer | Joins silently drop rows otherwise |
| Domain checks: currencies, branches and codes exist in reference tables | New codes need mapping |
| Distribution drift on key features | Early sign of a mapping or source change |

Keep each check in one line of the gate notebook's `checks` list so failures read as a report. Record each run's results in a
table for trend analysis.

## Ownership

Every silver product and module gold table has a data owner who approves mappings (`TRN_CATEGORY`, merchant categories,
segments) and thresholds. Record owners in table comments and in the module README.
