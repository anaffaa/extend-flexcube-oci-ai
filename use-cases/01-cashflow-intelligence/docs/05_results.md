# 5. Results and validation

All results are on the synthetic sample bank. The answer key (`foundation/source/sample-bank/validation/`, schema `DEMOMETA`)
is used only offline to measure results; it is never exposed to AIDP, the models or the agent.

## Rules-based early warning

| Planted scenario | Customers | Flagged | Notes |
|---|---|---|---|
| SME revenue drop | 9 | **9 of 9 HIGH** | Needed medians and the year-ago comparison: drops started in different months and loan disbursements created spikes |
| Job loss | 37 | **34 of 37** (33 HIGH, 1 MEDIUM) | The 3 missed had salary stopping too recently or other income |
| Churn | 102 | 35 ATTRITION, 59 CREDIT_STRESS, 8 not flagged | 21 of the credit-stress churners have a loan or overdraft and are correctly kept as credit risk |
| Normal customers | 1,818 | **0 HIGH**, 4 MEDIUM, 3 ATTRITION | Very low false-alarm rate |

Portfolio on the as-of date: 101 HIGH, 8 MEDIUM, 38 ATTRITION, 1,853 no signal. Collections worklist: 109 loans.

## Machine learning

| Model | Rules average precision | ML average precision | Comment |
|---|---|---|---|
| Arrears in 90 days | 0.41 | **0.53** | Same ranking quality (AUC about 0.82), more precise at the top of the list |
| Attrition in 90 days | 0.06 | **0.15** | More than twice as precise: the model learns the balance-drain pattern the rules miss |

On AIDP the registered runs scored 0.51 against 0.44 (arrears) and 0.14 against 0.06 (attrition). Small differences between
runs are expected; the gap to the rules is stable.

## Reproduce

- In AIDP: the quality-check notebooks print every check and must pass.
- Locally, without AIDP: `tests/local/run_pipeline_local.py` runs bronze to ML on the sample bank and prints the figures above.
- Data integrity: `python3 foundation/source/sample-bank/generator/validate.py` (needs duckdb).
- To score the planted scenarios, join the answer key to `early_warning` on `customer_no` outside AIDP.

## What synthetic data cannot tell you

Synthetic scenarios start suddenly, so there is little signal months ahead; the models detect events in their first weeks,
which is still before arrears or account closure. On real data expect different thresholds and more noise, and back-test
with the bank's own outcomes before any decision use.
