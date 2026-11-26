# Extend FLEXCUBE on OCI | Foundation notebook fnd_01_bronze: bronze layer
# Copies the FLEXCUBE tables the shared silver layer needs from the external catalog into Delta tables.
# Works with the sample bank or your own FLEXCUBE copy: set SRC below. Safe to re-run (each table is overwritten).
# Prerequisites: external catalog over FLEXCUBE (read-only user AIDP_READER) and a standard catalog named fcubs_lake.

# Cell 1: setup
from pyspark.sql import functions as F

SRC = "fcubs_source.fcubs"     # <external catalog>.<FLEXCUBE schema>, read-only user (AIDP_READER)
TGT = "fcubs_lake.bronze"      # Delta tables owned by AIDP
SOURCE_LABEL = "FCUBSDEMO.FCUBS"   # written to the _source lineage column, e.g. "PRODFCUBS.FCUBS"

# The 15 FLEXCUBE tables used by silver, gold and ML. Set COPY_ALL = True to copy every table in SRC
# (fine for the 34-table sample; never for a real FLEXCUBE schema with thousands of tables).
REQUIRED = ["sttm_customer", "sttm_cust_personal", "sttm_cust_corporate", "sttm_kyc_master",
            "sttm_credit_score_grade", "sttm_cust_account", "sttm_account_class", "actb_accbal_history",
            "actb_history", "sttm_trn_code", "swtb_settlement_hist", "cltb_account_apps_master",
            "cltb_account_schedules", "cltb_amount_paid", "cltb_account_ude_values"]
COPY_ALL = False

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {TGT}")
available = {r.tableName.lower() for r in spark.sql(f"SHOW TABLES IN {SRC}").collect()}
missing = [t for t in REQUIRED if t not in available]
if missing:
    raise Exception(f"Missing required FLEXCUBE tables in {SRC}: {missing}. Check grants for the read-only user.")
tables = sorted(available) if COPY_ALL else REQUIRED
print(len(tables), "tables to copy from", SRC)

# Cell 2: copy
results = []
for t in tables:
    try:
        df = (spark.table(f"{SRC}.{t}")
              .withColumn("_ingest_ts", F.current_timestamp())
              .withColumn("_source", F.lit(f"{SOURCE_LABEL}.{t.upper()}")))
        (df.write.format("delta").mode("overwrite")
           .option("overwriteSchema", "true")
           .saveAsTable(f"{TGT}.{t}"))
        n = spark.table(f"{TGT}.{t}").count()
        results.append((t, n, "OK"))
        print(f"{t:32s} {n:>10,d}")
    except Exception as e:
        results.append((t, None, str(e)[:200]))
        print(f"{t:32s} FAILED: {str(e)[:200]}")

# Cell 3: verify (every row should be OK; sample data: ACTB_HISTORY = 843,248, STTM_CUSTOMER = 2,000)
spark.createDataFrame(results, "table string, rows long, status string").orderBy("table").show(50, truncate=False)
