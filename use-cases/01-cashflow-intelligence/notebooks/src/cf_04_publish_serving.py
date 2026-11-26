# Extend FLEXCUBE on OCI | Use case 01 cash-flow intelligence | cf_04_publish_serving
# Publishes gold to the governed serving layer (AIDP 26ai Lakehouse) for the agent and other consumers.
# Writes FCUBS_GOLD tables through the external catalog fcubs_serving_rw (user FCUBS_GOLD). MERGE on primary keys,
# so re-runs are safe and each as-of date is kept as history.
# Prerequisite: foundation/serving (users) and this module's sql/ (tables) applied; catalog fcubs_serving_rw created.

# ---------- Cell 1: setup ----------
from pyspark.sql import functions as F

GLD = "fcubs_lake.gold_cashflow"
SLV = "fcubs_lake.silver"
TGT = "fcubs_serving_rw.fcubs_gold"      # external catalog over the Lakehouse, schema FCUBS_GOLD

names = spark.table(f"{SLV}.customer_360").select("customer_no", "customer_name")
yn = lambda c: F.when(F.col(c), "Y").otherwise("N")

def merge(df, table, keys):
    # Column order must match the Oracle table (insertInto is positional).
    (df.write.option("write.mode", "MERGE").option("write.merge.keys", keys)
       .option("skip.oos.staging", "true").option("merge.staging.using.username", "true")
       .insertInto(f"{TGT}.{table}"))
    print(f"{table:24s} merged {df.count():>7,d} rows; table now {spark.table(f'{TGT}.{table}').count():,}")

# ---------- Cell 2: early_warning ----------
ews = (spark.table(f"{GLD}.early_warning").join(names, "customer_no", "left")
    .select("as_of_date", "customer_no", F.substring("customer_name", 1, 200).alias("customer_name"),
            "customer_type", "segment", "home_branch", "rm_id",
            F.col("ews_score").cast("int"), "risk_band", "signal_type",
            F.substring(F.array_join("ews_reasons", "; "), 1, 1000).alias("ews_reasons"),
            yn("has_credit_exposure").alias("has_credit_exposure"),
            F.col("active_loans").cast("int"), F.col("total_emi_aed").cast("decimal(18,2)"),
            F.col("max_dpd").cast("int"), F.col("overdue_amount_aed").cast("decimal(18,2)"),
            F.col("days_since_salary").cast("int"),
            F.col("salary_change_pct").cast("decimal(9,1)"), F.col("inflow_change_pct").cast("decimal(9,1)"),
            F.col("balance_change_pct").cast("decimal(9,1)"), F.col("debt_burden_ratio").cast("decimal(9,3)")))
merge(ews, "early_warning", "as_of_date,customer_no")

# ---------- Cell 3: collections_priority ----------
as_of = spark.table(f"{GLD}.early_warning").agg(F.max("as_of_date")).first()[0]
coll = (spark.table(f"{GLD}.collections_priority")
    .select(F.lit(as_of).alias("as_of_date"), "loan_no", F.col("priority_rank").cast("int"),
            "customer_no", F.substring("customer_name", 1, 200).alias("customer_name"), "segment", "rm_id",
            "product_code", F.col("days_past_due").cast("int"), "dpd_bucket",
            F.col("emi_aed").cast("decimal(18,2)"), F.col("overdue_amount_aed").cast("decimal(18,2)"),
            "next_due_date", F.col("repayment_ac_balance_aed").cast("decimal(18,2)"),
            F.col("shortfall_aed").cast("decimal(18,2)"), F.col("ews_score").cast("int"), "risk_band",
            F.substring(F.array_join("ews_reasons", "; "), 1, 1000).alias("ews_reasons"),
            "recommended_action"))
merge(coll, "collections_priority", "as_of_date,loan_no")

# ---------- Cell 4: sme_cashflow ----------
sme = (spark.table(f"{GLD}.sme_cashflow")
    .select("customer_no", F.col("month").alias("month_start"),
            F.substring("customer_name", 1, 200).alias("customer_name"),
            F.substring("business_description", 1, 200).alias("business_description"), "rm_id",
            *[F.col(c).cast("decimal(18,2)") for c in ["receipts_aed", "payments_aed", "payroll_paid_aed",
              "net_cashflow_aed", "month_end_balance_aed", "receipts_3m_avg", "net_burn_3m_avg"]],
            F.col("runway_months").cast("decimal(9,1)")))
merge(sme, "sme_cashflow", "customer_no,month_start")

# ---------- Cell 5: ml_early_warning (needs sql/31_serving_ml.sql and notebook fcubs_07 run first) ----------
mlw = (spark.table(f"{GLD}.ml_early_warning")
    .select("as_of_date", "customer_no", "rm_id", "segment",
            F.col("p_arrears_90d").cast("decimal(6,4)"), "ml_arrears_band",
            F.col("p_attrition_90d").cast("decimal(6,4)"), "ml_attrition_band",
            "rules_band", "rules_signal", yn("ml_only_flag").alias("ml_only_flag"),
            "arrears_run_id", "attrition_run_id", F.substring("ml_drivers", 1, 600).alias("ml_drivers")))
merge(mlw, "ml_early_warning", "as_of_date,customer_no")

# ---------- Cell 6: verify through the read-only agent catalog ----------
spark.sql("SELECT risk_band, signal_type, COUNT(*) n FROM fcubs_serving.fcubs_gold.early_warning "
          "WHERE as_of_date = (SELECT MAX(as_of_date) FROM fcubs_serving.fcubs_gold.early_warning) "
          "GROUP BY risk_band, signal_type ORDER BY 1, 2").show()
