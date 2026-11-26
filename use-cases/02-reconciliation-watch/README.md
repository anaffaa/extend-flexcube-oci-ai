# Use case 02: Reconciliation watch

**Status:** design (not yet built). **Builds on:** the shared foundation, plus 3 more FLEXCUBE tables.
**Business owners:** finance and product control, operations, internal audit.

## Problem

Operations teams find breaks late: suspense and clearing GLs that do not clear, end-of-day entries that do not net to zero by
reference, account balances that drift from their posting history, and unauthorised entries that age quietly. Each break is
found by a person running a report, usually after month end, when the root cause is harder to trace.

## What it will answer

- Which GLs, accounts and transaction references are out of balance today, by how much, and since when?
- Which breaks are new since yesterday, and which are ageing past tolerance?
- Is this break unusual for this GL, branch and day of the month, or normal timing?
- What is the likely cause (one-sided entry, value-date mismatch, currency revaluation, unauthorised posting)?

## Design

| Layer | Plan |
|---|---|
| FLEXCUBE tables (added to the reader grants) | `ACTB_DAILY_LOG` (current-day entries), `GLTM_GLMASTER` (GL hierarchy, reconciliation flag), `STTM_ACCOUNT_BALANCE` (current balances); plus foundation tables `ACTB_HISTORY`, `ACTB_ACCBAL_HISTORY`, `STTM_TRN_CODE` |
| Silver (shared) | `gl_master` (readable GL tree with the reconciliation flag), `daily_entries` (conformed `ACTB_DAILY_LOG`) |
| Gold (`fcubs_lake.gold_recon`) | `reference_balance_check` (debits against credits per transaction reference and currency), `gl_suspense_ageing` (open items on reconciliation GLs by age bucket), `balance_drift` (stored balance against the sum of postings per account), `unauthorised_ageing`, `recon_breaks` (one row per break with type, amount, age, owner) |
| ML | Anomaly score per GL and day against its own history (seasonality by day of month and month end), to separate unusual breaks from normal timing |
| Quality gate | `rc_02_quality_checks`: every reference checked, break counts within expected range |
| Serving (`FCUBS_GOLD`) | `RECON_BREAKS`, `GL_SUSPENSE_AGEING` |
| Agent | `fcubs_recon_copilot`: tools `get_open_breaks`, `get_break_detail`, `get_gl_ageing`, `get_new_breaks_since` |
| Alerts | Daily summary to the operations channel; new breaks above tolerance to the GL owner |

## Why it fits the platform

The checks are set-based Spark jobs over data the foundation already lands, so they cost little to run daily. The serving
layer and agent pattern are reused from use case 01 unchanged. FLEXCUBE stays untouched: breaks are reported, never corrected
automatically.

## Success measures

Breaks found on the day they occur rather than at month end; ageing of suspense items; analyst time per break; false-break rate.

## Open questions for the bank

- Which GLs are reconciliation GLs, and who owns each (owner mapping to load into a gold reference table)?
- Tolerance per GL and currency.
- Nostro reconciliation with external statements (SWIFT MT940 or camt.053) is a natural extension and needs a second source.
