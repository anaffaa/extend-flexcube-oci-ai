# 5. Operations and monitoring

## Daily operation

`fcubs_daily_pipeline` runs the foundation tasks and then each enabled module's tasks. Each depends on the previous one, so a
failure stops everything after it. Agents keep answering from the last good serving data and alerts stop, which makes
failures silent unless you watch for them.

- Send workflow failures to the operations topic created by Terraform (job notifications if your AIDP release offers them, or
  a final task that publishes a summary to the topic), and subscribe the support team.
- Use **Repair run** on a failed run to rerun the failed task and those after it.
- Check the copy's refresh or apply lag before the scheduled start.

## Runbook

| Event | Action |
|---|---|
| Bronze fails | Check the source copy is open and reachable (catalog test connection), the reader password is valid, and grants are intact |
| Foundation gate fails on reconciliation | The copy was still changing: rerun after it settles, or set `TOLERANCE` for a live replica |
| Module gate fails on band shares | Look for new transaction codes or a source change before rerunning; do not relax the gate without the owner |
| Publish fails | Refresh the affected table in both serving catalogs; check for leftover duplicate notebook cells |
| Agent errors | Read the trace; check the deployment is on the latest version; see the module troubleshooting page |
| Alerts fail | Check egress to the channel and the Credential Store token |

## Scaling bronze

Bronze copies whole tables through JDBC, one table at a time. That suits the sample and smaller banks. For large volumes:

- Load `ACTB_HISTORY` and `ACTB_ACCBAL_HISTORY` incrementally: read only rows with `TRN_DT` after the last loaded date and
  append, with a weekly full reconciliation.
- Partition bronze and silver Delta tables by month of the transaction date.
- Increase cluster workers and read tables in parallel.
- For on-premises sources, let GoldenGate land changes on OCI and read from there.

## Change management

- Edit notebook sources (`notebooks/src/*.py`), rebuild with `tools/build_notebooks.py`, and promote through environments.
  When editing in AIDP directly, replace cells rather than adding new ones next to old ones: a leftover old cell silently
  overrides the new one.
- After changing agent instructions or tools: test in a new session, read the trace, then redeploy.
- Adding a serving column: alter the table, refresh that table in both serving catalogs, update the publish cell and the tool
  SQL, then rerun.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| AIDP instance fails late in provisioning with an empty error log | AIDP service principal lacks a newer IAM statement | Compare `iam.tf` with the current AIDP documentation, add the statement, recreate |
| External catalog shows only some tables | Harvest still running | Refresh the catalog until the count is complete |
| Catalog harvest fails on some tables | Table or column comments over 256 bytes | Trim comments on the copy (`02_precheck.sql` lists them); never in production |
| Bronze vs source mismatch on your own FLEXCUBE | Source still posting during the copy | Set `TOLERANCE = 0.01` in `fnd_03_quality_checks` |
| Silver features empty for your bank | Transaction codes not mapped | Edit `TRN_CATEGORY` in `fnd_02_silver` |
| Sample load: `ORA-20003 Reject limit reached`, `KUP-04023` | CSV format option missing | Use `10_build_from_bucket.sql` as provided |
| Script cannot reach the database REST endpoint | Private endpoint | Run the script from a host in the VCN or through OCI Bastion |

Module-specific issues: see each module's troubleshooting page.
