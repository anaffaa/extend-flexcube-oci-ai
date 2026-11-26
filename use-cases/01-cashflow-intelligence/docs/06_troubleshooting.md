# 6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Every agent question fails in about 1 second; trace shows `Invalid value for safety_mode` | Safety mode typed as "Contextual" | Empty the field or type `CONTEXTUAL`, then redeploy |
| Agent says "I could not find any..." after a follow-up; trace shows `Field required` | A tool parameter has no default | Set descriptions and defaults (`ALL`) on all parameters; instruction rule 19 forces a retry |
| Agent explains a previous answer instead of re-checking | Model answers from memory | Rule 20; test in a new session |
| SQL tool: "SQL query is invalid" | Unquoted text parameter | Quote it: `'{{rm_id}}'` |
| Amounts appear as `[TELEPHONE_NUMBER]` | PII guardrail false positive on output | Telephone = Allow on output |
| Publish fails with `INSERT_COLUMN_ARITY_MISMATCH` | Serving columns changed but the catalog has the old definition, or an old copy of a cell still runs | Table-level refresh in the catalog tree, restart the session; check the notebook has no leftover duplicate cell |
| ML Cell 1: `No module named mlflow` | Cluster libraries | Add `mlflow` and `scikit-learn` (PyPI), restart |
| Model logging fails | ARM cluster shape | Use AMD or Intel |
| Scoring type error on `customer_no` | Customer numbers have leading zeros | Keep them as strings |
| Notify task times out | Cluster cannot reach slack.com | Allow egress from the AIDP network |
| HIGH band check fails with your own FLEXCUBE | Transaction codes unmapped or thresholds unsuitable | Map `TRN_CATEGORY` in `fnd_02_silver`; review rules with risk |

Foundation and platform issues (catalog harvest, provisioning, bronze reconciliation) are in
[operations](../../../docs/path-to-production/05_operations.md#troubleshooting).
