# 7. Cost

Use the [OCI cost estimator](https://www.oracle.com/cloud/costestimator.html) with your region and volumes; prices are not
repeated here because they change. The drivers:

| Resource | Sizing in the quick start | Driver | To pause | To remove |
|---|---|---|---|---|
| Sample source database | 2 ECPU, 20 GB | ECPU hours, storage | Stop (storage still billed) | `deploy_sample_source = false` or destroy |
| Your FLEXCUBE copy | Bank's existing standby or clone | Usually already licensed for DR | n/a | n/a |
| AIDP Lakehouse | Created by AIDP | ECPU hours, storage | Stop | Deleted with the AIDP instance |
| Spark cluster | 2 OCPU driver, 1 worker | Hours running | Idle timeout (30 minutes) | Delete |
| AI compute and agent deployment | Default size, 1 replica | Hours deployed | Undeploy | Delete |
| OCI Generative AI | On-demand | Per call (tokens) | n/a | n/a |
| Object Storage, Vault, logging, network | Small | Storage, key versions, log volume, NAT data | n/a | Destroy |

## Keeping a pilot inexpensive

- Run the workflow once a day and let the cluster idle out.
- Stop the sample database and pause the schedule between demo sessions.
- Undeploy agents in development outside working hours.
- Size the cluster to the data: the sample needs one worker; scale workers rather than shapes for larger banks.
- Use incremental bronze loads for large history tables.

## Tagging

Terraform applies `freeform_tags` (default `solution = extend-flexcube-oci-ai`) to every resource it creates. Add cost-center
and environment tags, and tag what you create in AIDP the same way, to report cost per environment and module.
