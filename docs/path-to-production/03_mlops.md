# 3. MLOps and model risk

The sample ML notebooks retrain on every run so a first deployment shows the full lifecycle. In production, separate training
from scoring and govern models like any other bank model.

## Lifecycle

| Stage | Cadence | How |
|---|---|---|
| Train | Monthly, or when monitoring says so | Training notebook logs all candidates and the rules baseline to the MLflow experiment |
| Validate | Each retrain | Independent review of metrics, stability, fairness and drivers before registration |
| Register | After approval | Register the approved run; record the approval in the model card |
| Score | Daily | Scoring task loads the registered model version and writes the module's ML table |
| Monitor | Daily and monthly | Score distribution, population stability, feature drift, realised outcomes against predictions |
| Retire | When replaced | Keep the old version registered for audit; stop scoring with it |

To split the sample notebook: keep the panel and training cells in a monthly training notebook; in the daily notebook build
only the current snapshot's features and load the model with `mlflow.sklearn.load_model("models:/<name>/<version>")`.

## Monitoring

| Signal | Threshold to investigate |
|---|---|
| Population stability index of scores | Above 0.1 (watch), above 0.25 (act) |
| Share of customers in the HIGH band | Doubles or halves against the 3-month average |
| Feature missing rate | Above twice its training level |
| Realised precision at 90 days | Below the validated average precision band |

Write these to a monitoring table each run and alert through the operations topic.

## Model risk documentation

For each model keep a model card: purpose and decisions supported, population, label definition, features and exclusions
(protected attributes), training window, validation results against the rules baseline, known limitations (for example
"trained on synthetic scenarios" until back-tested), monitoring plan, owner and approver. The module docs give most of it
([cash-flow ML](../../use-cases/01-cashflow-intelligence/docs/02_ml_early_warning.md)).

## Human in the loop

Model outputs inform RMs and collectors; they do not make credit decisions. Any automated decision use needs the bank's model
risk, legal and compliance approval, plus customer-facing explanations.
