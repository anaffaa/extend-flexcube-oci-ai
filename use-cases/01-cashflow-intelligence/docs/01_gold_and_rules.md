# 1. Gold layer, early-warning rules and collections

`cf_01_gold_cashflow` reads the shared silver layer and writes `fcubs_lake.gold_cashflow`. Windows are derived from the as-of
date: the **last 3 full months** against the **prior 3**, plus **the same season a year ago** for business receipts (sample:
Jul to Sep 2026, Apr to Jun 2026, Oct to Nov 2025). Nationality and gender are never used.

| Table | Grain | How | Why |
|---|---|---|---|
| `customer_monthly_cashflow` (26,000) | customer and month, 13 months | Inflows, operating inflows (excluding disbursements, deposits and interest), outflows, salary, payroll, cash out, loan repaid, transfers out, card spend (essential, foreign); month-end balance carried forward through quiet months | The monthly cash-flow statement of every customer |
| `cashflow_features` (2,000) | customer | Window averages and changes; business receipts as **medians** (robust to spikes) against prior months and a year ago; days since salary; `salary_stopped`; debt burden; `spending_stopped`; `drain_vs_salary` | The feature store for rules, ML and the agent |
| `early_warning` (2,000) | customer | Additive points capped at 100; bands HIGH 40+, MEDIUM 25 to 39, LOW; `signal_type` CREDIT_STRESS or ATTRITION; reasons in plain language | Explainable early warning that separates distress from switching banks |
| `collections_priority` (109) | loan needing attention | Live loans with DPD above 0, a non-LOW band, or a shortfall (instalment plus overdue minus repayment-account balance); recommended action; priority = DPD x 2 + score + shortfall / 1000 (capped at 50) | Work the right loans first, and reach customers before they miss a payment |
| `sme_cashflow` (3,900) | SME or corporate and month | Receipts, payments, payroll, net cash flow, balance, 3-month averages, **cash runway** = balance / average net monthly burn | Proactive conversations about working capital |

## Early-warning points

Edit `rules` in Cell 4 with the bank's risk team; these were tuned on the sample bank.

| Signal | Points |
|---|---|
| Salary stopped (3+ salary months before, none in 35 days) | 40 |
| Business receipts down more than 50 percent (25 to 50 percent: 15) | 40 |
| DPD above 30 days (1 to 30: 15) | 25 |
| Salary down more than 30 percent | 15 |
| Balance down more than 50 percent | 15 |
| Cash withdrawals doubled | 10 |
| Debt burden above 50 percent of salary | 10 |
| Bureau score below 600 | 10 |

`signal_type` is ATTRITION when the pattern is a drain without credit exposure (salary moved, balance emptied, spending
stopped), so RMs treat a switching customer differently from one in distress.

## Recommended actions

| Situation | Action |
|---|---|
| 90+ DPD | Recovery team |
| 31 to 90 DPD | Collector call, discuss restructuring |
| 1 to 30 DPD | Call and agree a payment date |
| HIGH risk with a shortfall, not yet overdue | **Proactive RM call before the due date** |
| Shortfall only | Pre-due reminder |

## Quality gate: `cf_02_quality_checks`

7 checks after gold, before ML and publishing: the 5 gold tables are non-empty, `early_warning` covers every customer in
`customer_360`, and the HIGH band stays below 20 percent of customers (far above usually means unmapped transaction codes or
thresholds that do not fit the bank). Any failure stops the workflow, so the agent and alerts keep the last good data.
