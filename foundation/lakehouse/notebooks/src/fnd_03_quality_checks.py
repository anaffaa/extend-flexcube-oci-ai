# Extend FLEXCUBE on OCI | Foundation notebook fnd_03_quality_checks: data quality gate for bronze and silver
# Fails the workflow run if bronze no longer reconciles with the FLEXCUBE source or a silver data product is empty
# or inconsistent. Use-case modules add their own checks on top (for example cf_02_quality_checks).

# ---------- Cell 1: checks ----------
SRC = "fcubs_source.fcubs"     # same as fnd_01_bronze: <external catalog>.<FLEXCUBE schema>
TOLERANCE = 0.0                # allowed bronze vs source row-count gap; e.g. 0.01 (1%) for a FLEXCUBE copy still receiving postings
checks = []

# 1. bronze reconciles with the FLEXCUBE source (row counts)
for t in ["sttm_customer", "sttm_cust_account", "actb_history", "cltb_account_apps_master", "swtb_settlement_hist"]:
    src = spark.table(f"{SRC}.{t}").count()
    brz = spark.table(f"fcubs_lake.bronze.{t}").count()
    checks.append((f"bronze.{t} = source", abs(src - brz) <= TOLERANCE * src, f"source {src:,} / bronze {brz:,}"))

# 2. silver data products are populated
for t in ["customer_360", "accounts", "account_daily_balance", "transactions", "loan_status", "card_spend"]:
    n = spark.table(f"fcubs_lake.silver.{t}").count()
    checks.append((f"silver.{t} not empty", n > 0, f"{n:,} rows"))

# 3. consistency: one row per customer, every account has a known customer, no uncategorised majority
c = spark.table("fcubs_lake.silver.customer_360")
checks.append(("customer_360 unique per customer", c.count() == c.select("customer_no").distinct().count(), f"{c.count():,} rows"))
orphans = (spark.table("fcubs_lake.silver.accounts").join(c.select("customer_no"), "customer_no", "left_anti").count())
checks.append(("accounts all belong to a customer", orphans == 0, f"{orphans:,} orphan accounts"))
tx = spark.table("fcubs_lake.silver.transactions")
other_share = tx.where("category = 'other'").count() / max(1, tx.count())
checks.append(("transactions mostly categorised (other < 20%)", other_share < 0.20,
               f"{other_share:.1%} uncategorised: extend TRN_CATEGORY in fnd_02_silver"))

for name, ok, detail in checks:
    print(("PASS " if ok else "FAIL ") + f"{name:48s} {detail}")
failed = [n for n, ok, _ in checks if not ok]
if failed:
    raise Exception(f"{len(failed)} quality check(s) failed: {failed}")
print(f"All {len(checks)} foundation checks passed.")
