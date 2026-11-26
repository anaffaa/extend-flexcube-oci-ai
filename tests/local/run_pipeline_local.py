"""Run the pipeline notebooks locally on the sample bank (PySpark 3.5, parquet instead of Delta, no AIDP needed).

Use it to test a change before importing notebooks into AIDP, or in CI. From the repository root:
    pip install pyspark==3.5.3 scikit-learn mlflow pandas
    MLFLOW_ALLOW_FILE_STORE=true MLFLOW_TRACKING_URI=file://$PWD/.mlruns python3 tests/local/run_pipeline_local.py .
Optional second argument: comma-separated steps (load,bronze,silver,fchecks,gold,checks,ml,report).
Expected on the shipped sample bank: 101 HIGH, 8 MEDIUM, 38 ATTRITION, 1,853 no signal; 109 collections rows."""
import json, os, sys, re, time
from pyspark.sql import SparkSession, functions as F, types as T

REPO = sys.argv[1]
STEPS = sys.argv[2].split(",") if len(sys.argv) > 2 else ["load", "bronze", "silver", "fchecks", "gold", "checks", "ml"]
WH = os.path.join(os.path.abspath(REPO), ".spark-warehouse")
spark = (SparkSession.builder.master("local[2]").appName("fcubs-test")
         .config("spark.sql.warehouse.dir", WH).config("spark.driver.memory", "5g")
         .config("spark.sql.shuffle.partitions", "8").config("spark.ui.enabled", "false")
         .config("spark.sql.session.timeZone", "UTC")
         .enableHiveSupport().getOrCreate())
spark.sparkContext.setLogLevel("ERROR")

def oracle_type(t):
    t = t.upper()
    if t.startswith(("VARCHAR", "CHAR", "NVARCHAR", "CLOB", "RAW")): return T.StringType()
    if t.startswith("DATE") or t.startswith("TIMESTAMP"): return T.TimestampType()
    m = re.match(r"NUMBER\((\d+)(?:,(\d+))?\)", t)
    if m:
        p, s = int(m.group(1)), int(m.group(2) or 0)
        return T.DecimalType(min(p, 38), s)
    if t.startswith("NUMBER") or t.startswith("FLOAT"): return T.DecimalType(38, 10)
    return T.StringType()

def load_source():
    meta = json.load(open(os.path.join(REPO, "foundation/source/sample-bank/generator", "columns.json")))
    spark.sql("CREATE DATABASE IF NOT EXISTS src_fcubs")
    for tab, m in meta.items():
        path = os.path.join(REPO, "foundation/source/sample-bank/data", f"{tab}.csv.gz")
        hdr = spark.read.option("header", True).csv(path).columns
        types = dict((c, oracle_type(t)) for c, t in m["columns"])
        schema = T.StructType([T.StructField(c.lower(), types.get(c, T.StringType())) for c in hdr])
        df = (spark.read.option("header", True).option("timestampFormat", "yyyy-MM-dd HH:mm:ss[.SSSSSS]")
              .option("mode", "FAILFAST").schema(schema).csv(path))
        df.write.mode("overwrite").format("parquet").saveAsTable(f"src_fcubs.{tab.lower()}")
        print(f"source {tab:32s} {spark.table(f'src_fcubs.{tab.lower()}').count():>9,d}")

def run(nb):
    code = open(os.path.join(REPO, nb)).read()
    code = (code.replace('"fcubs_source.fcubs"', '"spark_catalog.src_fcubs"')
                .replace("fcubs_lake.", "spark_catalog.")
                .replace('FMT = "delta"', 'FMT = "parquet"')
                .replace('.format("delta")', '.format("parquet")')
                .replace('.option("overwriteSchema", "true")', ''))
    code = code.replace("spark_catalog.bronze", "spark_catalog.bronze").replace("SHOW TABLES IN {SRC}", "SHOW TABLES IN {SRC}")
    t = time.time()
    g = {"spark": spark, "__name__": "__main__"}
    exec(compile(code, nb, "exec"), g)
    print(f"=== {nb} done in {time.time() - t:.0f}s")
    return g

if "load" in STEPS: load_source()
for step, nb in [("bronze", "foundation/lakehouse/notebooks/src/fnd_01_bronze.py"), ("silver", "foundation/lakehouse/notebooks/src/fnd_02_silver.py"),
                 ("fchecks", "foundation/lakehouse/notebooks/src/fnd_03_quality_checks.py"),
                 ("gold", "use-cases/01-cashflow-intelligence/notebooks/src/cf_01_gold_cashflow.py"),
                 ("checks", "use-cases/01-cashflow-intelligence/notebooks/src/cf_02_quality_checks.py"),
                 ("ml", "use-cases/01-cashflow-intelligence/notebooks/src/cf_03_ml_early_warning.py")]:
    if step in STEPS:
        run(nb)

if "gold" in STEPS or "report" in STEPS:
    spark.sql("SELECT risk_band, signal_type, COUNT(*) n FROM spark_catalog.gold_cashflow.early_warning GROUP BY 1, 2 ORDER BY 1, 2").show()
    print("collections_priority", spark.table("spark_catalog.gold_cashflow.collections_priority").count(),
          "sme_cashflow", spark.table("spark_catalog.gold_cashflow.sme_cashflow").count(),
          "monthly", spark.table("spark_catalog.gold_cashflow.customer_monthly_cashflow").count())
if "ml" in STEPS or "report" in STEPS:
    ml = spark.table("spark_catalog.gold_cashflow.ml_early_warning")
    ml.groupBy("ml_arrears_band", "ml_attrition_band").count().orderBy("ml_arrears_band", "ml_attrition_band").show()
    print("ml_only_flag:", ml.where("ml_only_flag").count())
