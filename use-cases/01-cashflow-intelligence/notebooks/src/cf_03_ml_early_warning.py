# Extend FLEXCUBE on OCI | Use case 01 cash-flow intelligence | cf_03_ml_early_warning
# Two models on one point-in-time feature panel:
#   arrears_90d   : will a borrower who is under 30 days late today reach 30+ DPD in the next 90 days?
#   attrition_90d : will a customer drain their balance (below 10% of their 90-day average, still under 20% at day 90)?
# Labels are outcomes FLEXCUBE itself records later (loan schedules, balances); no answer key is used.
# Features only use data from BEFORE each snapshot date (no look-ahead). Nationality and gender are never used.
# Reads fcubs_lake.bronze and silver. Writes fcubs_lake.gold_cashflow.ml_feature_panel and ml_early_warning.
# Logs runs to the AIDP experiment fcubs_early_warning. Use an AMD or Intel cluster (model logging does not run on ARM).

# ---------- Cell 1: setup ----------
import datetime as dt
import mlflow, mlflow.sklearn, numpy as np, pandas as pd
from pyspark.sql import functions as F, Window as W
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.model_selection import GroupKFold

BRZ, SLV, GLD = "fcubs_lake.bronze", "fcubs_lake.silver", "fcubs_lake.gold_cashflow"
FMT = "delta"
AS_OF = None                               # None = day after the latest posting (as in silver); or "YYYY-MM-DD"
if AS_OF is None:
    AS_OF = str(spark.table(f"{SLV}.transactions").agg(F.date_add(F.max("txn_date"), 1)).first()[0])
_asof = dt.date.fromisoformat(AS_OF)
_m = _asof.month - 1 - 12
DATA_FROM = str(dt.date(_asof.year + _m // 12, _m % 12 + 1, 1))   # first day of history: 12 months before the as-of month
# 13 training snapshots every 14 days; the last one is 93 days before the as-of date, so its 90-day label is fully observed
_last = _asof - dt.timedelta(days=93)
SNAPS = [str(_last - dt.timedelta(days=14 * (12 - i))) for i in range(13)]   # sample data: 2026-02-02 .. 2026-07-20
print("As-of", AS_OF, "| history from", DATA_FROM, "| snapshots", SNAPS[0], "..", SNAPS[-1])
EXPERIMENT = "fcubs_early_warning"
SEED = 42

# ---------- Cell 2: daily building blocks ----------
acct = spark.table(f"{SLV}.accounts").select("account_no", "customer_no")
cust = spark.table(f"{SLV}.customer_360").select("customer_no", "customer_type", "bureau_score")

# customer daily transactions by category (owner of the account)
txd = (spark.table(f"{SLV}.transactions").drop("customer_no").join(acct, "account_no")
       .groupBy("customer_no", F.col("txn_date").cast("date").alias("d"))
       .agg(*[F.sum(F.when(F.col("category") == c, F.col("amount_aed").cast("double")).otherwise(0)).alias(c)
              for c in ["salary_in", "card_spend", "cash_out", "transfer_out", "bill_payment"]],
            F.sum(F.when((F.col("drcr_ind") == "C") & ~F.col("category").isin("loan_disbursement", "term_deposit", "interest_in"),
                         F.col("amount_aed").cast("double")).otherwise(0)).alias("op_inflow"),
            F.count("*").alias("txn_count")))

# customer balance for every calendar day (last known closing balance carried forward, all accounts summed)
days = spark.sql(f"SELECT explode(sequence(DATE'{DATA_FROM}', DATE'{AS_OF}', interval 1 day)) AS d")
bal = (spark.table(f"{SLV}.account_daily_balance")
       .select("account_no", F.col("balance_date").cast("date").alias("d"), F.col("closing_bal_aed").cast("double").alias("b")))
w = W.partitionBy("account_no").orderBy("d").rowsBetween(W.unboundedPreceding, 0)
bal_daily = (acct.select("account_no").crossJoin(days).join(bal, ["account_no", "d"], "left")
             .withColumn("b", F.last("b", ignorenulls=True).over(w)).fillna(0, ["b"])
             .join(acct, "account_no").groupBy("customer_no", "d").agg(F.sum("b").alias("balance")))
bal_daily = bal_daily.cache()

# loan instalments with the date each was paid (principal component), as FLEXCUBE records them
sch = (spark.table(f"{BRZ}.cltb_account_schedules").where("component_name = 'PRINCIPAL'")
       .select("account_number", F.to_date("schedule_due_date").alias("due")))
paid = (spark.table(f"{BRZ}.cltb_amount_paid").where("component_name = 'PRINCIPAL'")
        .groupBy("account_number", F.to_date("due_date").alias("due")).agg(F.max(F.to_date("paid_date")).alias("paid_on")))
loans = (spark.table(f"{BRZ}.cltb_account_apps_master")
         .select("account_number", F.col("customer_id").alias("customer_no"),
                 F.to_date("value_date").alias("disbursed_on"), F.col("emi_amount").cast("double").alias("emi")))
last_due = sch.groupBy("account_number").agg(F.max("due").alias("last_due"))
inst = (sch.join(paid, ["account_number", "due"], "left").join(loans, "account_number").join(last_due, "account_number")
        .withColumn("paid_on", F.coalesce("paid_on", F.lit("2999-12-31").cast("date"))))

# ---------- Cell 3: point-in-time feature panel ----------
def build_panel(snaps):
    snap = (spark.createDataFrame([(s,) for s in snaps], "s string").select(F.to_date("s").alias("t"))
            .withColumn("p_days", F.greatest(F.lit(1), F.datediff(F.date_sub("t", 90), F.greatest(F.date_sub("t", 180), F.lit(DATA_FROM).cast("date"))))))
    L30 = (F.col("d") >= F.date_sub("t", 30)) & (F.col("d") < F.col("t"))
    L90 = (F.col("d") >= F.date_sub("t", 90)) & (F.col("d") < F.col("t"))
    P90 = (F.col("d") >= F.date_sub("t", 180)) & (F.col("d") < F.date_sub("t", 90))
    per30 = lambda c, win, n: (F.sum(F.when(win, F.col(c)).otherwise(0)) / n * 30)          # monthly rate

    # cash-flow behaviour (all monthly rates in AED)
    tx = txd.crossJoin(F.broadcast(snap)).where((F.col("d") < F.col("t")) & (F.col("d") >= F.date_sub("t", 180)))
    aggs = [F.max(F.when(F.col("salary_in") > 0, F.col("d"))).alias("last_salary_d"),
            F.sum(F.when(P90 & (F.col("salary_in") > 0), 1).otherwise(0)).alias("salary_credits_p90"),
            F.sum(F.when(L90 & (F.col("salary_in") > 0), 1).otherwise(0)).alias("salary_credits_l90")]
    for c in ["salary_in", "op_inflow", "card_spend", "cash_out", "transfer_out", "bill_payment", "txn_count"]:
        aggs += [per30(c, L30, 30).alias(f"{c}_l30"), per30(c, L90, 90).alias(f"{c}_l90"),
                 (F.sum(F.when(P90, F.col(c)).otherwise(0)) / F.first("p_days") * 30).alias(f"{c}_p90")]
    f = (tx.groupBy("customer_no", "t").agg(*aggs)
           .withColumn("days_since_salary", F.datediff("t", "last_salary_d")).drop("last_salary_d"))
    ratio = lambda a, b: F.when(F.col(b) > 0, F.round(F.col(a) / F.col(b), 3))
    for c in ["salary_in", "op_inflow", "card_spend", "cash_out", "txn_count", "bill_payment"]:
        f = f.withColumn(f"{c}_l30_vs_p90", ratio(f"{c}_l30", f"{c}_p90")).withColumn(f"{c}_l90_vs_p90", ratio(f"{c}_l90", f"{c}_p90"))
    f = f.withColumn("transfer_out_l30_vs_salary", ratio("transfer_out_l30", "salary_in_p90"))

    # balances: today, 30-day low, 90-day average; and the outcome window for the attrition label
    bd = bal_daily.crossJoin(F.broadcast(snap)).where((F.col("d") >= F.date_sub("t", 90)) & (F.col("d") <= F.date_add("t", 90)))
    b = (bd.groupBy("customer_no", "t")
           .agg(F.max(F.when(F.col("d") == F.date_sub("t", 1), F.col("balance"))).alias("balance_now"),
                F.min(F.when(L30, F.col("balance"))).alias("balance_min_l30"),
                F.avg(F.when(L90, F.col("balance"))).alias("balance_avg_l90"),
                F.min(F.when(F.col("d") >= F.col("t"), F.col("balance"))).alias("future_min_balance"),
                F.max(F.when(F.col("d") == F.date_add("t", 89), F.col("balance"))).alias("future_end_balance"),
                F.max(F.col("d")).alias("future_last_day"))
           .withColumn("balance_now_vs_l90", ratio("balance_now", "balance_avg_l90"))
           .withColumn("balance_min_l30_vs_l90", ratio("balance_min_l30", "balance_avg_l90")))

    # credit position on the snapshot date and the arrears outcome after it
    li = inst.crossJoin(F.broadcast(snap))
    active = (F.col("disbursed_on") <= F.col("t")) & (F.col("last_due") >= F.col("t"))
    unpaid_now = (F.col("due") < F.col("t")) & (F.col("paid_on") >= F.col("t"))
    hits_30 = ((F.date_add("due", 30) >= F.col("t")) & (F.date_add("due", 30) < F.date_add("t", 90))
               & (F.col("paid_on") > F.date_add("due", 30)))                   # still unpaid 30 days after due
    cr = (li.groupBy("customer_no", "t")
            .agg(F.max(F.when(active, 1).otherwise(0)).alias("is_borrower"),
                 F.countDistinct(F.when(active, F.col("account_number"))).alias("active_loans"),
                 F.coalesce(F.max(F.when(unpaid_now, F.datediff("t", "due"))), F.lit(0)).alias("dpd_now"),
                 F.sum(F.when(unpaid_now, 1).otherwise(0)).alias("instalments_unpaid"),
                 F.max(F.when(hits_30, 1).otherwise(0)).alias("y_arrears_90d")))

    emi = (loans.join(last_due, "account_number").crossJoin(F.broadcast(snap))
             .where((F.col("disbursed_on") <= F.col("t")) & (F.col("last_due") >= F.col("t")))
             .groupBy("customer_no", "t").agg(F.sum("emi").alias("total_emi")))

    p = (f.join(b, ["customer_no", "t"], "left").join(cr, ["customer_no", "t"], "left")
          .join(emi, ["customer_no", "t"], "left").join(cust, "customer_no", "left")
          .fillna(0, ["is_borrower", "active_loans", "total_emi", "dpd_now", "instalments_unpaid", "y_arrears_90d"])
          .withColumn("is_corporate", (F.col("customer_type") == "C").cast("int"))
          .withColumn("debt_burden_ratio", ratio("total_emi", "salary_in_p90"))
          .withColumn("emi_cover_months", ratio("balance_now", "total_emi"))
          # drained and not rebuilt: a dip on payday week is not attrition, money gone for good is
          .withColumn("y_attrition_90d", F.when(F.datediff("future_last_day", "t") >= 89,
                      ((F.col("future_min_balance") < 0.1 * F.col("balance_avg_l90"))
                       & (F.col("future_end_balance") < 0.2 * F.col("balance_avg_l90"))).cast("int")))
          .withColumn("in_arrears_pop", (F.col("is_borrower") == 1) & (F.col("dpd_now") < 30))
          .withColumn("in_attrition_pop", (F.col("balance_avg_l90") >= 20000) & (F.col("balance_now_vs_l90") >= 0.1))
          .withColumnRenamed("t", "snapshot_date")
          .drop("customer_type", "future_min_balance", "future_end_balance", "future_last_day"))
    return p

FEATURES = ["days_since_salary", "salary_credits_l90", "salary_credits_p90",
            "salary_in_l30", "salary_in_l90", "salary_in_p90", "salary_in_l30_vs_p90", "salary_in_l90_vs_p90",
            "op_inflow_l30", "op_inflow_p90", "op_inflow_l30_vs_p90", "op_inflow_l90_vs_p90",
            "card_spend_l30", "card_spend_l30_vs_p90", "card_spend_l90_vs_p90",
            "cash_out_l30_vs_p90", "bill_payment_l30_vs_p90", "txn_count_l30", "txn_count_l30_vs_p90",
            "transfer_out_l30", "transfer_out_l30_vs_salary",
            "balance_now", "balance_avg_l90", "balance_now_vs_l90", "balance_min_l30_vs_l90",
            "is_borrower", "active_loans", "total_emi", "dpd_now", "instalments_unpaid", "debt_burden_ratio",
            "emi_cover_months", "bureau_score", "is_corporate"]

panel = build_panel(SNAPS)
panel.write.format(FMT).mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{GLD}.ml_feature_panel")
try:
    spark.sql(f"COMMENT ON TABLE {GLD}.ml_feature_panel IS 'ML training panel: one row per customer per 14-day snapshot, features from the 180 days before, labels from the 90 days after.'")
except Exception as e:
    print("comment skipped:", str(e)[:80])
spark.table(f"{GLD}.ml_feature_panel").groupBy("snapshot_date").agg(
    F.count("*").alias("rows"),
    F.sum(F.when(F.col("in_arrears_pop"), F.col("y_arrears_90d"))).alias("arrears_events"),
    F.sum(F.when(F.col("in_attrition_pop"), F.col("y_attrition_90d"))).alias("attrition_events")).orderBy("snapshot_date").show(20)

# ---------- Cell 4: rules baseline on the same panel (simplified copy of the gold early_warning logic) ----------
def rule_points(d):
    stopped = (d.salary_credits_p90 >= 2) & (d.days_since_salary.fillna(999) > 35)
    return (40 * stopped + 15 * (d.salary_in_l90_vs_p90 <= 0.7) + 40 * (d.op_inflow_l90_vs_p90 <= 0.5)
            + 15 * (d.balance_now_vs_l90 <= 0.5) + 10 * (d.cash_out_l30_vs_p90 >= 2) + 10 * (d.debt_burden_ratio > 0.5)
            + 15 * d.dpd_now.between(1, 30) + 25 * (d.dpd_now > 30) + 10 * d.bureau_score.between(1, 599)).astype(float)

def rule_attrition(d):
    stopped = (d.salary_credits_p90 >= 2) & (d.days_since_salary.fillna(999) > 35)
    pattern = stopped & ((d.card_spend_l30_vs_p90.fillna(1) <= 0.4) | (d.transfer_out_l30_vs_salary.fillna(0) >= 5))
    return 100 * pattern + rule_points(d)

pdf = spark.table(f"{GLD}.ml_feature_panel").toPandas()
for c in FEATURES:
    pdf[c] = pd.to_numeric(pdf[c], errors="coerce").astype(float)

# ---------- Cell 5: compare candidates with 5-fold cross-validation by customer, log every run to Experiments ----------
# Folds split by customer, so a customer is never in training and test at the same time.
mlflow.set_experiment(EXPERIMENT)
CANDIDATES = {"gbt_depth2": dict(max_depth=2, max_iter=150, learning_rate=0.05, min_samples_leaf=40),
              "gbt_depth3": dict(max_depth=3, max_iter=100, learning_rate=0.05, min_samples_leaf=80),
              "gbt_depth2_strong_reg": dict(max_depth=2, max_iter=300, learning_rate=0.03, min_samples_leaf=100, l2_regularization=5.0)}
TARGETS = {"arrears_90d": ("y_arrears_90d", "in_arrears_pop", rule_points),
           "attrition_90d": ("y_attrition_90d", "in_attrition_pop", rule_attrition)}
TAGS = {"use_case": "cash-flow early warning", "label_source": "FLEXCUBE outcomes, no answer key",
        "fairness": "no nationality or gender", "split": "5-fold GroupKFold by customer"}

def cv_scores(d, target, score_fn):
    out = []
    for tr_i, te_i in GroupKFold(5).split(d, d[target], d.customer_no):
        tr, te = d.iloc[tr_i], d.iloc[te_i]
        s = score_fn(tr, te)
        k = max(1, int(len(te) * 0.05))                                       # RM capacity: top 5% of the book
        out.append([roc_auc_score(te[target], s), average_precision_score(te[target], s),
                    te[target].values[np.argsort(-s)[:k]].sum() / te[target].sum()])
    m = np.array(out)
    return {"cv_auc": m[:, 0].mean(), "cv_auc_std": m[:, 0].std(), "cv_avg_precision": m[:, 1].mean(),
            "cv_capture_top5pct": m[:, 2].mean()}

models, summary, MEDIANS = {}, [], {}
for name, (target, pop, rule_fn) in TARGETS.items():
    d = pdf[pdf[pop] & pdf[target].notna()].reset_index(drop=True)
    d[target] = d[target].astype(int)
    base = {"target": target, "population": pop, "rows": len(d), "events": int(d[target].sum()),
            "customers": d.customer_no.nunique(), "snapshots": f"{SNAPS[0]}..{SNAPS[-1]} every 14 days"}

    with mlflow.start_run(run_name=f"{name}_rules_baseline"):                 # the current rules, for comparison
        met = cv_scores(d, target, lambda tr, te: rule_fn(te).values)
        mlflow.log_params({**base, "model": "rules (gold early_warning points)"}); mlflow.log_metrics(met); mlflow.set_tags(TAGS)
        summary.append((name, "rules_baseline", met))

    best = None
    for cand, prm in CANDIDATES.items():
        with mlflow.start_run(run_name=f"{name}_{cand}") as run:
            met = cv_scores(d, target, lambda tr, te: HistGradientBoostingClassifier(random_state=SEED, **prm)
                            .fit(tr[FEATURES], tr[target]).predict_proba(te[FEATURES])[:, 1])
            final = HistGradientBoostingClassifier(random_state=SEED, **prm).fit(d[FEATURES], d[target])  # refit on all
            imp = permutation_importance(final, d[FEATURES], d[target], scoring="average_precision", n_repeats=3, random_state=SEED)
            top = pd.DataFrame({"feature": FEATURES, "importance": imp.importances_mean}).sort_values("importance", ascending=False)
            mlflow.log_params({**base, **prm, "model": "HistGradientBoostingClassifier", "n_features": len(FEATURES)})
            mlflow.log_metrics(met); mlflow.set_tags(TAGS)
            mlflow.log_text(top.to_csv(index=False), "feature_importance.csv")
            mlflow.sklearn.log_model(final, artifact_path="model", input_example=d[FEATURES].head(5),
                                     serialization_format="cloudpickle")
            summary.append((name, cand, met))
            if best is None or met["cv_avg_precision"] > best[2]["cv_avg_precision"]:
                best = (final, run.info.run_id, met, cand, list(top.feature.head(5)))
    models[name] = best
    MEDIANS[name] = d[FEATURES].median()                                  # typical customer, used to explain scores

print(f"{'target':14s} {'run':24s} {'AUC':>12s} {'avg prec':>9s} {'top5% capture':>14s}")
for name, run, m in summary:
    print(f"{name:14s} {run:24s} {m['cv_auc']:.3f}+/-{m['cv_auc_std']:.3f} {m['cv_avg_precision']:9.3f} {m['cv_capture_top5pct']:14.0%}")
for name, (_, run_id, m, cand, top5) in models.items():
    print(f"BEST {name}: {cand} (run {run_id}); register this run. Top drivers: {', '.join(top5)}")

# ---------- Cell 6: score today and save ml_early_warning ----------
cur = build_panel([AS_OF]).toPandas()
for c in FEATURES:
    cur[c] = pd.to_numeric(cur[c], errors="coerce").astype(float)
cur["p_arrears_90d"] = np.where(cur.in_arrears_pop, models["arrears_90d"][0].predict_proba(cur[FEATURES])[:, 1], np.nan)
cur["p_attrition_90d"] = np.where(cur.in_attrition_pop, models["attrition_90d"][0].predict_proba(cur[FEATURES])[:, 1], np.nan)
# base rate is about 1 in 100, so 25% means 25 times more likely than an average customer
band = lambda p: np.where(np.isnan(p), None, np.select([p >= 0.25, p >= 0.10], ["HIGH", "MEDIUM"], "LOW"))
cur["ml_arrears_band"], cur["ml_attrition_band"] = band(cur.p_arrears_90d.values), band(cur.p_attrition_90d.values)
cur["arrears_run_id"], cur["attrition_run_id"] = models["arrears_90d"][1], models["attrition_90d"][1]

# Plain-language drivers for HIGH and MEDIUM customers: for each feature, replace the customer's value with the
# value of a typical customer and see how far the probability falls. The 3 biggest falls are the drivers.
TEXT = {"days_since_salary": lambda v: "no salary credit for 35+ days" if np.isnan(v) else f"last salary credit {v:.0f} days ago",
        "salary_credits_l90": lambda v: f"{v:.0f} salary credits in the last 90 days",
        "salary_credits_p90": lambda v: f"{v:.0f} salary credits in the 90 days before that",
        "salary_in_l30_vs_p90": lambda v: f"salary in the last 30 days at {v:.0%} of usual",
        "salary_in_l90_vs_p90": lambda v: f"salary in the last 90 days at {v:.0%} of usual",
        "op_inflow_l30_vs_p90": lambda v: f"money coming in over the last 30 days at {v:.0%} of usual",
        "op_inflow_l90_vs_p90": lambda v: f"money coming in over the last 90 days at {v:.0%} of usual",
        "balance_now_vs_l90": lambda v: f"balance now {v:.0%} of its 90-day average",
        "balance_min_l30_vs_l90": lambda v: f"lowest balance in 30 days at {v:.0%} of the 90-day average",
        "balance_now": lambda v: f"balance AED {v:,.0f}",
        "balance_avg_l90": lambda v: f"90-day average balance AED {v:,.0f}",
        "card_spend_l30_vs_p90": lambda v: f"card spending at {v:.0%} of usual",
        "card_spend_l90_vs_p90": lambda v: f"card spending over 90 days at {v:.0%} of usual",
        "cash_out_l30_vs_p90": lambda v: f"cash withdrawals at {v:.0%} of usual",
        "bill_payment_l30_vs_p90": lambda v: f"bill payments at {v:.0%} of usual",
        "txn_count_l30_vs_p90": lambda v: f"account activity at {v:.0%} of usual",
        "txn_count_l30": lambda v: f"{v:.0f} transactions in the last 30 days",
        "transfer_out_l30": lambda v: f"AED {v:,.0f} transferred out in 30 days",
        "transfer_out_l30_vs_salary": lambda v: f"transfers out in 30 days {v:.1f} times monthly salary",
        "dpd_now": lambda v: f"{v:.0f} days past due today",
        "instalments_unpaid": lambda v: f"{v:.0f} unpaid instalments",
        "total_emi": lambda v: f"loan instalments AED {v:,.0f} a month",
        "debt_burden_ratio": lambda v: f"instalments {v:.0%} of salary",
        "emi_cover_months": lambda v: f"balance covers {v:.1f} months of instalments",
        "bureau_score": lambda v: f"bureau score {v:.0f}",
        "op_inflow_l30": lambda v: f"AED {v:,.0f} came in over the last 30 days",
        "op_inflow_p90": lambda v: f"usual monthly money in AED {v:,.0f}",
        "salary_in_l30": lambda v: f"salary in the last 30 days AED {v:,.0f}",
        "salary_in_l90": lambda v: f"average monthly salary over 90 days AED {v:,.0f}",
        "salary_in_p90": lambda v: f"usual monthly salary AED {v:,.0f}",
        "card_spend_l30": lambda v: f"card spending AED {v:,.0f} in 30 days",
        "active_loans": lambda v: f"{v:.0f} live loans"}

# Which side of a typical customer counts as a warning sign: +1 higher is riskier, -1 lower is riskier.
# A driver is only shown when the customer is at least 20% beyond the typical value on the risky side, so
# normal values (for example a high bureau score) are never presented as reasons.
RISKY = {"days_since_salary": 1, "salary_credits_l90": -1, "salary_in_l30_vs_p90": -1, "salary_in_l90_vs_p90": -1,
         "op_inflow_l30_vs_p90": -1, "op_inflow_l90_vs_p90": -1, "op_inflow_l30": -1,
         "balance_now_vs_l90": -1, "balance_min_l30_vs_l90": -1, "card_spend_l30_vs_p90": -1, "card_spend_l90_vs_p90": -1,
         "cash_out_l30_vs_p90": 1, "bill_payment_l30_vs_p90": -1, "txn_count_l30_vs_p90": -1, "txn_count_l30": -1,
         "transfer_out_l30": 1, "transfer_out_l30_vs_salary": 1, "dpd_now": 1, "instalments_unpaid": 1,
         "total_emi": 1, "debt_burden_ratio": 1, "emi_cover_months": -1, "bureau_score": -1, "salary_in_l30": -1}

def drivers(model, med, row, k=3):
    x = row[FEATURES].to_frame().T.astype(float)
    base = model.predict_proba(x)[:, 1][0]
    drops = []
    for f in FEATURES:
        x2 = x.copy(); x2[f] = med[f]
        drops.append((base - model.predict_proba(x2)[:, 1][0], f))
    out = []
    for drop, f in sorted(drops, reverse=True):
        v = row[f]
        # only features that really move the score, have a plain-language text, and have a value (empty = not applicable)
        risky = (np.isnan(v) and f == "days_since_salary") or (
            not np.isnan(v) and RISKY.get(f, 0) * (v - med[f]) > 0.2 * max(abs(med[f]), 1e-9))
        if drop > 0.01 and f in TEXT and risky:
            out.append(TEXT[f](v))
        if len(out) == k:
            break
    return "; ".join(out)

def explain(row):
    parts = []
    for name, label in [("arrears_90d", "Arrears"), ("attrition_90d", "Attrition")]:
        if row[f"ml_{name.split('_')[0]}_band"] in ("HIGH", "MEDIUM"):
            parts.append(f"{label}: " + drivers(models[name][0], MEDIANS[name], row))
    return " | ".join(parts) if parts else None

cur["ml_drivers"] = cur.apply(explain, axis=1)

cols = ["customer_no", "p_arrears_90d", "ml_arrears_band", "p_attrition_90d", "ml_attrition_band", "arrears_run_id", "attrition_run_id",
        "ml_drivers"]
res = cur[cols].astype(object).where(cur[cols].notna(), None)              # NaN to NULL
res["customer_no"] = res["customer_no"].astype(str)                       # FLEXCUBE customer numbers are text (leading zeros)
out = (spark.createDataFrame(res,
                             "customer_no string, p_arrears_90d double, ml_arrears_band string, p_attrition_90d double, "
                             "ml_attrition_band string, arrears_run_id string, attrition_run_id string, ml_drivers string")
       .withColumn("as_of_date", F.lit(AS_OF).cast("date"))
       .withColumn("p_arrears_90d", F.round("p_arrears_90d", 4)).withColumn("p_attrition_90d", F.round("p_attrition_90d", 4))
       .join(spark.table(f"{GLD}.early_warning").select("customer_no", "rm_id", "segment", F.col("risk_band").alias("rules_band"),
             F.col("signal_type").alias("rules_signal"), "ews_score"), "customer_no", "left")
       # where ML and rules disagree is the demo story: early flags the rules have not caught yet
       .withColumn("ml_only_flag", F.coalesce(((F.col("ml_arrears_band") == "HIGH") | (F.col("ml_attrition_band") == "HIGH"))
                   & (F.col("rules_signal") == "NONE"), F.lit(False))))
out.write.format(FMT).mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{GLD}.ml_early_warning")
try:
    spark.sql(f"COMMENT ON TABLE {GLD}.ml_early_warning IS 'ML probabilities per customer: 30+ DPD arrears and balance drain in the next 90 days, bands, model run ids, and the rules result side by side.'")
except Exception as e:
    print("comment skipped:", str(e)[:80])

# ---------- Cell 7: ML versus rules today ----------
r = spark.table(f"{GLD}.ml_early_warning")
r.groupBy("rules_signal").pivot("ml_arrears_band", ["HIGH", "MEDIUM", "LOW"]).count().orderBy("rules_signal").show()
r.groupBy("rules_signal").pivot("ml_attrition_band", ["HIGH", "MEDIUM", "LOW"]).count().orderBy("rules_signal").show()
print("ML-only early flags (rules say NONE):", r.where("ml_only_flag").count())
r.where("ml_drivers IS NOT NULL").select("customer_no", "p_arrears_90d", "p_attrition_90d", "rules_signal", "ml_drivers").orderBy(F.desc("p_attrition_90d")).show(20, False)
