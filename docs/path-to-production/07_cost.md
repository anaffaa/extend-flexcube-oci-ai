# 7. Cost

Measured usage and a list-price estimate are below. For your own sizing, use the
[OCI Cost Estimator](https://www.oracle.com/cloud/costestimator.html) with your region and volumes. The drivers:

| Resource | Sizing in the quick start | Driver | To pause | To remove |
|---|---|---|---|---|
| Sample source database | 2 ECPU, 20 GB | ECPU hours, storage | Stop (storage still billed) | `deploy_sample_source = false` or destroy |
| Your FLEXCUBE copy | Bank's existing standby or clone | Usually already licensed for DR | n/a | n/a |
| AIDP Lakehouse | Created by AIDP | ECPU hours, storage | Stop | Deleted with the AIDP instance |
| Spark cluster | 2 OCPU driver, 1 worker | Hours running | Idle timeout (30 minutes) | Delete |
| AI compute and agent deployment | Default size, 1 replica | Hours deployed | Undeploy | Delete |
| OCI Generative AI | On-demand | Per call (tokens) | n/a | n/a |
| Object Storage, Vault, logging, network | Small | Storage, key versions, log volume, NAT data | n/a | Destroy |

## Observed consumption of the reference deployment

The figures below come from the author's reference deployment of the foundation and use case 01 on the sample bank, in one
OCI region, over 29 days (27 Oct to 24 Nov 2026), read from OCI Cost Analysis filtered to the solution compartment. They
show **usage**, which is what you can compare with your own tenancy. Costs are then estimated at **public list prices**
(pay as you go, USD), not at the rates of the tenancy where they were measured.

| Service and SKU | Observed usage | Unit | Notes |
|---|---|---|---|
| Oracle AI Data Platform | 17,016 AIDP units per day (about 709 per hour) | AIDP Unit Per Hour | Master catalog default cluster (230 units per hour, always on), Spark cluster and agent AI compute left running |
| AIDP Lakehouse ECPU | 48 ECPU hours per day | ECPU Hours | 2 ECPU running 24 hours a day |
| AIDP Lakehouse storage | about 33 GB-months per day | Storage Months | About 1 TB provisioned |
| Sample bank database ECPU | 48 ECPU hours per day | ECPU Hours | 2 ECPU, never stopped during the test |
| Sample bank storage | about 0.6 GB-months per day | Storage Months | About 20 GB |
| Database backup storage | about 1.3 GB-months per day | Storage Months | About 40 GB |
| OCI Generative AI | 3.5 units over the period | Large Cohere | Agent questions during testing |
| Logging, Object Storage, Monitoring | under 1 GB logs, under 0.1 GB objects | various | Within free tiers or negligible |

## Monthly estimate at list prices

| Item | As measured (everything always on) | Pilot pattern (switched off when idle) |
|---|---|---|
| AIDP master catalog cluster (230 units per hour, cannot be stopped) | included below | $166 |
| AIDP Spark cluster and AI compute | $510 total AIDP | $53 (cluster 2 hours a day, agent 10 hours on 22 working days) |
| AIDP Lakehouse ECPU, 2 ECPU | $484 | $148 (business hours on working days) |
| AIDP Lakehouse storage, 1 TB | $24 | $24 |
| Sample bank database ECPU, 2 ECPU | $484 | $20 (1 hour a day for the pipeline) |
| Sample bank storage and backups | $3 | $3 |
| Generative AI, logging, object storage, monitoring | under $5 | under $5 |
| **Total per month** | **about $1,510** | **about $420** |

Assumptions: 30-day month; list prices as published for November 2026 (AIDP unit $0.001, Autonomous AI Database ECPU
$0.336 per hour license included, Lakehouse storage $0.0244 and transaction processing storage $0.1156 per GB-month, backup
storage $0.0244 per GB-month). BYOL rates for the AIDP Lakehouse and the source database reduce the ECPU lines by about
75 percent. Prices change and differ by region and contract: confirm with the
[OCI Cost Estimator](https://www.oracle.com/cloud/costestimator.html) and the
[AI Data Platform pricing page](https://docs.oracle.com/en/cloud/paas/ai-data-platform/aidug/pricing.html).

What the measurement shows:

- **AIDP compute is the largest driver.** At about 709 units per hour around the clock, clusters and the agent deployment were
  never idling. The 230-unit master catalog cluster is the only part that must stay on.
- **Databases are the second driver.** Both ran 2 ECPU all day. Stopping the source database outside the pipeline run and the
  Lakehouse outside business hours saves most of their cost.
- **Everything else is small.** Storage, Generative AI calls, logging and monitoring together stay below $35 a month at this
  scale.
- A production deployment is sized by data volume, history depth and users; use this as the baseline for a pilot, not a quote.

## Keeping a pilot inexpensive

- Set the Spark cluster idle timeout and check it actually stops (Compute page shows the state).
- Undeploy the agent outside demo hours; redeploying takes a few minutes.
- Run the workflow once a day and let the cluster idle out.
- Stop the sample database and pause the schedule between demo sessions.
- Undeploy agents in development outside working hours.
- Size the cluster to the data: the sample needs one worker; scale workers rather than shapes for larger banks.
- Use incremental bronze loads for large history tables.

## Tagging

Terraform applies `freeform_tags` (default `solution = extend-flexcube-oci-ai`) to every resource it creates. Add cost-center
and environment tags, and tag what you create in AIDP the same way, to report cost per environment and module.
