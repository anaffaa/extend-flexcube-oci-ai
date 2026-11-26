# 2. ML early warning with MLflow

The rules say **what** is happening. Two models estimate **how likely** a bad outcome is in the next 90 days. They learn only
from outcomes FLEXCUBE records later (schedules, paid dates, balances), which is how a bank would train them. No answer key
is used.

| Model | Question | Label (what actually happened next) | Population |
|---|---|---|---|
| `arrears_90d` | Will this borrower reach 30+ days past due in the next 90 days? | An instalment still unpaid 30 days after its due date, within 90 days of the snapshot | Borrowers with a live loan, under 30 DPD today |
| `attrition_90d` | Will this customer drain their balance and not rebuild it? | Lowest balance in the next 90 days below 10 percent of the 90-day average, and still below 20 percent on day 90 | Customers with an average balance of AED 20k or more |

## Point-in-time design

13 training snapshots, 14 days apart. The last is 93 days before the as-of date, so its 90-day label is fully observed (sample:
2 Feb to 20 Jul 2026). Features use only the 180 days before each snapshot; labels only the 90 days after. Cross-validation
keeps each customer entirely in training or in test. All dates derive from the as-of date.

34 features: monthly rates for the last 30, last 90 and prior 90 days (salary, operating inflow, card spend, cash out,
transfers, bills, activity) and their ratios; days since salary; balance today, 30-day low, 90-day average; credit position
(live loans, instalments, DPD, unpaid instalments, debt burden, months of instalments covered by balance); bureau score.
Nationality and gender are never features.

## Steps

1. Make sure the cluster has `mlflow` and `scikit-learn` (foundation step 3) and restart it once.
2. Home > **Experiments** > Create `fcubs_early_warning`.
3. Run `cf_03_ml_early_warning`. It builds the panel, logs 8 runs (per model: the rules baseline plus 3 gradient-boosting
   candidates, 5-fold cross-validation by customer), refits each candidate with feature importance, and scores the as-of date
   into `ml_early_warning`. It prints the best run per model.
4. Experiments > `fcubs_early_warning` > **Compare**, sort by `cv_avg_precision`.
5. **Register** the best run per model as `fcubs_ews_arrears_90d` and `fcubs_ews_attrition_90d` (logged model `model`,
   location `fcubs_lake` > `gold_cashflow`).

## Output: `ml_early_warning`

- `p_arrears_90d`, `p_attrition_90d`: empty when the customer is outside that model's population (not the same as zero risk)
- Bands: HIGH 25 percent and above, MEDIUM 10 to 25 percent (about 25 and 10 times the base rate)
- The rules band and signal side by side, and `ml_only_flag` when ML says HIGH but the rules see nothing
- `ml_drivers`: the model's own top 3 reasons in plain language

**How `ml_drivers` works:** for each feature, replace the customer's value with a typical customer's (median) and measure how
far the probability falls. The 3 largest falls become text, for example "account activity at 50% of usual; lowest balance in
30 days at 10% of the 90-day average". A driver is shown only when the customer is at least 20 percent beyond typical on the
risky side.

## Reading the metrics

Average precision is the honest metric for rare events. Sample results (5-fold by customer):

| Model | Run | AUC | Average precision | Caught in top 5 percent |
|---|---|---|---|---|
| arrears_90d | rules baseline | 0.83 | 0.41 | 54% |
| arrears_90d | gbt_depth2 | 0.82 | **0.53** | 57% |
| attrition_90d | rules baseline | 0.67 | 0.06 | 28% |
| attrition_90d | gbt_depth3 | **0.81** | **0.16** | 42% |

For arrears, ML matches the rules on ranking and is more precise at the top. For attrition, ML is clearly better: the rules
target credit stress, the model learns the drain pattern. The winning depth can change between runs; the gap to the rules does not.

For production retraining, scoring from the registry, monitoring and model risk documentation, see
[MLOps](../../../docs/path-to-production/03_mlops.md).
