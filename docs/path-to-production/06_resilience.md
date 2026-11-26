# 6. Resilience: high availability and disaster recovery

The platform is an analytics extension, not part of the payment path: if it is unavailable, FLEXCUBE and banking operations
continue. Set targets with the business accordingly, typically a recovery time of one business day and a recovery point of
the last successful daily run.

| Component | High availability | Disaster recovery |
|---|---|---|
| FLEXCUBE copy | Data Guard or refreshable clone as designed for the source pattern | Point the external catalog at the DR copy |
| AIDP lakehouse files | Object Storage durability within the region | Rebuild bronze and silver from the source in the DR region, or replicate the AIDP bucket with Object Storage replication |
| AIDP Lakehouse (serving) | Autonomous AI Database built-in availability | Autonomous Data Guard to a standby region, or republish from gold after rebuild |
| Notebooks, agents, workflows | Managed service | Redeploy from Git into an AIDP instance in the DR region (same Terraform, DR variables) |
| MLflow models | Registry in the instance | Retrain from the panel in DR, or export approved model artifacts to a replicated bucket |
| Secrets | Vault replicas within the region | Vault replication to the DR region, or regenerate in DR and update users |

## DR procedure (outline)

1. Apply the Terraform foundation in the DR region with the DR variables file.
2. Connect `fcubs_source` to the DR copy of FLEXCUBE.
3. Import notebooks, create catalogs, run the workflow once (bronze rebuilds from the source).
4. Run the serving script, publish, and redeploy agents.
5. Switch users to the DR Agent Hub and the bridge to the DR `/chat` endpoint.

Test it at least once a year, and after major platform upgrades.
