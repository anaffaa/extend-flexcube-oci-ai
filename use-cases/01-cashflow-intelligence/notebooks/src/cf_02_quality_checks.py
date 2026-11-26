# Extend FLEXCUBE on OCI | Use case 01 cash-flow intelligence | cf_02_quality_checks
# Fails the workflow run if a gold table is empty or does not cover every customer. Runs after cf_01_gold_cashflow.

# ---------- Cell 1: checks ----------
checks = []
for t in ["customer_monthly_cashflow", "cashflow_features", "early_warning", "collections_priority", "sme_cashflow"]:
    n = spark.table(f"fcubs_lake.gold_cashflow.{t}").count()
    checks.append((f"gold_cashflow.{t} not empty", n > 0, f"{n:,} rows"))
c = spark.table("fcubs_lake.silver.customer_360").count()
e = spark.table("fcubs_lake.gold_cashflow.early_warning").count()
checks.append(("early_warning covers every customer", c == e, f"customers {c:,} / scored {e:,}"))
bands = {r[0]: r[1] for r in spark.table("fcubs_lake.gold_cashflow.early_warning").groupBy("risk_band").count().collect()}
high_share = bands.get("HIGH", 0) / max(1, e)
checks.append(("HIGH band below 20% of customers", high_share < 0.20,
               f"{high_share:.1%} HIGH: if far above, review thresholds or transaction-code mapping"))

for name, ok, detail in checks:
    print(("PASS " if ok else "FAIL ") + f"{name:45s} {detail}")
failed = [n for n, ok, _ in checks if not ok]
if failed:
    raise Exception(f"{len(failed)} check(s) failed: {failed}")
print(f"All {len(checks)} cash-flow checks passed.")
