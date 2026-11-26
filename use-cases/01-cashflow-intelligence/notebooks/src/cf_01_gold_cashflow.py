# Extend FLEXCUBE on OCI | Use case 01 cash-flow intelligence | cf_01_gold_cashflow
# Builds business-ready tables for early warning, smart collections and SME cash-flow insight.
# Reads the shared silver layer (fcubs_lake.silver), writes fcubs_lake.gold_cashflow. Safe to re-run.
# Fairness: nationality and gender are never used in any feature or score.

# ---------- Cell 1: setup ----------
from pyspark.sql import functions as F, Window as W

SLV = "fcubs_lake.silver"
GLD = "fcubs_lake.gold_cashflow"
FMT = "delta"
AS_OF = None                               # None = same as silver (day after the latest posting); or "YYYY-MM-DD"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {GLD}")
s = lambda t: spark.table(f"{SLV}.{t}")

# ---------- date windows, all derived from the as-of (branch) date ----------
import datetime as dt
if AS_OF is None:
    AS_OF = str(s("transactions").agg(F.date_add(F.max("txn_date"), 1)).first()[0])
_asof = dt.date.fromisoformat(AS_OF)
def month_start(k):                                    # first day of the month k months from the as-of month
    m = _asof.month - 1 + k
    return dt.date(_asof.year + m // 12, m % 12 + 1, 1)
day_before = lambda d: str(d - dt.timedelta(days=1))
L3_FROM, L3_TO = str(month_start(-3)), day_before(month_start(0))     # last 3 full months
P3_FROM, P3_TO = str(month_start(-6)), day_before(month_start(-3))    # prior 3 full months
Y_FROM, Y_TO = str(month_start(-12)), day_before(month_start(-10))    # same season a year ago (first months of history)
HIST_FROM, HIST_TO = str(month_start(-12)), str(month_start(0))       # 13 monthly rows per customer
MONTH_END = day_before(month_start(1))                                # last day of the as-of month
print(f"As-of {AS_OF} | last 3 months {L3_FROM}..{L3_TO} | prior 3 {P3_FROM}..{P3_TO} | year ago {Y_FROM}..{Y_TO}")

def save(df, name, comment):
    df.write.format(FMT).mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{GLD}.{name}")
    try:
        spark.sql(f"COMMENT ON TABLE {GLD}.{name} IS '{comment}'")
    except Exception as e:
        print("comment skipped:", str(e)[:80])
    print(f"{name:28s} {spark.table(f'{GLD}.{name}').count():>10,d}")

cust = s("customer_360")
acct = s("accounts")
txn = (s("transactions").drop("customer_no")
       .join(acct.select("account_no", "customer_no"), "account_no"))      # owner of the account
card = s("card_spend").join(acct.select("account_no", "customer_no"), "account_no")

# ---------- Cell 2: customer_monthly_cashflow ----------
m_txn = (txn.withColumn("month", F.trunc("txn_date", "month"))
    .groupBy("customer_no", "month")
    .agg(F.sum(F.when(F.col("drcr_ind") == "C", F.col("amount_aed")).otherwise(0)).alias("inflow_aed"),
         F.sum(F.when(F.col("drcr_ind") == "D", F.col("amount_aed")).otherwise(0)).alias("outflow_aed"),
         F.sum(F.when((F.col("drcr_ind") == "C") & ~F.col("category").isin("loan_disbursement", "term_deposit", "interest_in"),
                      F.col("amount_aed")).otherwise(0)).alias("operating_inflow_aed"),       # business receipts, no loans or deposits
         F.sum(F.when(F.col("category") == "salary_in", F.col("amount_aed")).otherwise(0)).alias("salary_aed"),
         F.sum(F.when(F.col("category") == "payroll_out", F.col("amount_aed")).otherwise(0)).alias("payroll_paid_aed"),
         F.sum(F.when(F.col("category") == "cash_out", F.col("amount_aed")).otherwise(0)).alias("cash_out_aed"),
         F.sum(F.when(F.col("category") == "loan_repayment", F.col("amount_aed")).otherwise(0)).alias("loan_repaid_aed"),
         F.sum(F.when(F.col("category") == "transfer_out", F.col("amount_aed")).otherwise(0)).alias("transfer_out_aed")))

m_card = (card.where(F.col("is_approved") & (F.col("channel") != "ATM"))
    .withColumn("month", F.trunc("txn_date", "month"))
    .groupBy("customer_no", "month")
    .agg(F.sum("amount_aed").alias("card_spend_aed"),
         F.sum(F.when(F.col("is_essential"), F.col("amount_aed")).otherwise(0)).alias("essential_spend_aed"),
         F.sum(F.when(~F.col("is_domestic"), F.col("amount_aed")).otherwise(0)).alias("foreign_spend_aed")))

# month-end balance per account, carried forward through months without movement, summed per customer
bal = s("account_daily_balance").join(acct.select("account_no", "customer_no"), "account_no")
last_in_month = (bal.withColumn("month", F.trunc("balance_date", "month"))
    .withColumn("rn", F.row_number().over(W.partitionBy("account_no", "month").orderBy(F.desc("balance_date"))))
    .where("rn = 1").select("account_no", "customer_no", "month", "closing_bal_aed"))
months = spark.sql(f"SELECT explode(sequence(to_date('{HIST_FROM}'), to_date('{HIST_TO}'), interval 1 month)) AS month")
spine = acct.select("account_no", "customer_no").crossJoin(months)
month_end = (spine.join(last_in_month, ["account_no", "customer_no", "month"], "left")
    .withColumn("bal", F.last("closing_bal_aed", ignorenulls=True).over(
        W.partitionBy("account_no").orderBy("month").rowsBetween(W.unboundedPreceding, 0)))
    .groupBy("customer_no", "month").agg(F.sum(F.coalesce("bal", F.lit(0))).alias("month_end_balance_aed")))

monthly = (month_end.join(m_txn, ["customer_no", "month"], "left").join(m_card, ["customer_no", "month"], "left")
    .fillna(0)
    .withColumn("net_cashflow_aed", F.col("inflow_aed") - F.col("outflow_aed")))
monthly = monthly.select("customer_no", "month", *[F.round(c, 2).alias(c) for c in monthly.columns if c not in ("customer_no", "month")])
save(monthly, "customer_monthly_cashflow",
     f"One row per customer per month ({HIST_FROM[:7]} to {HIST_TO[:7]}): inflows (total and operating), outflows, salary, payroll paid, card spend (essential and foreign), cash withdrawals, loan repayments and month-end balance.")

# ---------- Cell 3: cashflow_features ----------
mc = spark.table(f"{GLD}.customer_monthly_cashflow")
win = lambda c, a, b: F.avg(F.when(F.col("month").between(a, b), F.col(c)))

agg = mc.groupBy("customer_no").agg(
    win("salary_aed", L3_FROM, L3_TO).alias("avg_salary_l3m"),
    win("salary_aed", P3_FROM, P3_TO).alias("avg_salary_p3m"),
    win("inflow_aed", L3_FROM, L3_TO).alias("avg_inflow_l3m"),
    win("inflow_aed", P3_FROM, P3_TO).alias("avg_inflow_p3m"),
    win("outflow_aed", L3_FROM, L3_TO).alias("avg_outflow_l3m"),
    F.percentile_approx(F.when(F.col("month").between(L3_FROM, L3_TO), F.col("operating_inflow_aed")), 0.5).alias("med_op_inflow_l3m"),
    F.percentile_approx(F.when(F.col("month").between(P3_FROM, P3_TO), F.col("operating_inflow_aed")), 0.5).alias("med_op_inflow_p3m"),
    win("operating_inflow_aed", Y_FROM, Y_TO).alias("avg_op_inflow_year_ago"),
    win("card_spend_aed", L3_FROM, L3_TO).alias("avg_card_spend_l3m"),
    win("card_spend_aed", P3_FROM, P3_TO).alias("avg_card_spend_p3m"),
    win("cash_out_aed", L3_FROM, L3_TO).alias("avg_cash_out_l3m"),
    win("cash_out_aed", P3_FROM, P3_TO).alias("avg_cash_out_p3m"),
    win("month_end_balance_aed", L3_FROM, L3_TO).alias("avg_balance_l3m"),
    win("month_end_balance_aed", P3_FROM, P3_TO).alias("avg_balance_p3m"),
    F.max(F.when(F.col("month").between(P3_FROM, MONTH_END), F.col("transfer_out_aed"))).alias("max_transfer_out_l6m_aed"),
    F.sum(F.when(F.col("month").between(P3_FROM, L3_TO) & (F.col("salary_aed") > 0), 1).otherwise(0)).alias("salary_months_l6m"),
    F.sum(F.when(F.col("salary_aed") > 0, 1).otherwise(0)).alias("salary_months_total"))

last_sal = (txn.where(F.col("category") == "salary_in").groupBy("customer_no")
    .agg(F.max("txn_date").alias("last_salary_date")))
loans = (s("loan_status").groupBy("customer_no")
    .agg(F.count("*").alias("active_loans"), F.sum("emi_aed").alias("total_emi_aed"),
         F.max("days_past_due").alias("max_dpd"), F.sum("overdue_amount_aed").alias("overdue_amount_aed")))
od = (acct.where(~F.col("is_closed")).groupBy("customer_no")
    .agg(F.sum("overdraft_limit").alias("overdraft_limit_aed"), F.sum("current_balance_aed").alias("current_balance_aed")))

pct = lambda a, b: F.when(F.col(b) > 0, F.round((F.col(a) - F.col(b)) / F.col(b) * 100, 1))

features = (cust.select("customer_no", "customer_type", "segment", "home_branch", "rm_id", "bureau_score", "internal_rating")
    .join(agg, "customer_no", "left").join(last_sal, "customer_no", "left")
    .join(loans, "customer_no", "left").join(od, "customer_no", "left")
    .fillna(0, ["active_loans", "total_emi_aed", "max_dpd", "overdue_amount_aed", "overdraft_limit_aed"])
    .withColumn("days_since_salary", F.datediff(F.lit(AS_OF), "last_salary_date"))
    .withColumn("salary_change_pct", pct("avg_salary_l3m", "avg_salary_p3m"))
    .withColumn("inflow_change_pct", pct("med_op_inflow_l3m", "med_op_inflow_p3m"))
    .withColumn("inflow_change_yoy_pct", pct("med_op_inflow_l3m", "avg_op_inflow_year_ago"))
    .withColumn("balance_change_pct", pct("avg_balance_l3m", "avg_balance_p3m"))
    .withColumn("card_spend_change_pct", pct("avg_card_spend_l3m", "avg_card_spend_p3m"))
    .withColumn("cash_out_change_pct", pct("avg_cash_out_l3m", "avg_cash_out_p3m"))
    .withColumn("spending_stopped", (F.coalesce("avg_card_spend_l3m", F.lit(0)) + F.coalesce("avg_cash_out_l3m", F.lit(0)) == 0)
                & ((F.coalesce("avg_card_spend_p3m", F.lit(0)) + F.coalesce("avg_cash_out_p3m", F.lit(0))) > 0))
    .withColumn("debt_burden_ratio", F.when(F.col("avg_salary_p3m") > 0,
                F.round(F.col("total_emi_aed") / F.col("avg_salary_p3m"), 3)))
    .withColumn("salary_stopped", (F.col("salary_months_total") >= 3) & (F.col("days_since_salary") > 35))
    .withColumn("has_credit_exposure", (F.col("active_loans") > 0) | (F.col("overdraft_limit_aed") > 0))
    # balance moved out in one go, relative to the usual salary (switching banks looks like 5x salary or more)
    .withColumn("drain_vs_salary", F.when(F.col("avg_salary_p3m") > 0,
                F.round(F.col("max_transfer_out_l6m_aed") / F.col("avg_salary_p3m"), 2)))
    # attrition: salary and everyday banking moved elsewhere (customer switched bank), not financial distress
    .withColumn("attrition_pattern", F.coalesce(F.col("salary_stopped") & (F.col("spending_stopped")
                | ((F.coalesce("card_spend_change_pct", F.lit(-100)) <= -60) & (F.coalesce("drain_vs_salary", F.lit(0)) >= 5))),
                F.lit(False)))
    .withColumn("salary_stopped", F.coalesce("salary_stopped", F.lit(False)))
    .withColumn("as_of_date", F.to_date(F.lit(AS_OF))))
features = features.select(*[F.round(c, 2).alias(c) if c.startswith("avg_") or c.endswith("_aed") else F.col(c) for c in features.columns])
save(features, "cashflow_features",
     "One row per customer as of branch date: salary, inflow, balance and spend trends (last 3 vs prior 3 months), days since salary, debt burden, loans and DPD. Feature store for early warning and the ML model.")

# ---------- Cell 4: early_warning ----------
f = spark.table(f"{GLD}.cashflow_features")
is_ind = F.col("customer_type") == "I"
is_biz = F.col("customer_type") == "C"
stress_stop = F.col("salary_stopped") & (~F.col("attrition_pattern") | F.col("has_credit_exposure"))
biz_drop = F.least(F.coalesce("inflow_change_pct", F.lit(0)), F.coalesce("inflow_change_yoy_pct", F.lit(0)))
rules = [  # (points, condition, reason)
    (40, is_ind & stress_stop, "Salary credits stopped"),
    (15, is_ind & ~F.col("salary_stopped") & (F.col("salary_change_pct") <= -30), "Salary down more than 30 percent"),
    (40, is_biz & (biz_drop <= -50), "Business receipts down more than 50 percent"),
    (15, is_biz & (biz_drop > -50) & (biz_drop <= -25), "Business receipts down 25 to 50 percent"),
    (15, F.col("balance_change_pct") <= -50, "Average balance down more than 50 percent"),
    (10, F.col("cash_out_change_pct") >= 100, "Cash withdrawals doubled"),
    (10, F.col("debt_burden_ratio") > 0.5, "Debt burden above 50 percent of salary"),
    (15, F.col("max_dpd").between(1, 30), "Loan 1 to 30 days past due"),
    (25, F.col("max_dpd") > 30, "Loan more than 30 days past due"),
    (10, F.col("bureau_score").between(1, 599), "Bureau score below 600"),
]
score = sum(F.when(cond, F.lit(p)).otherwise(F.lit(0)) for p, cond, _ in rules)
reasons = F.array_compact(F.array(*[F.when(cond, F.lit(r)) for _, cond, r in rules]))

early_warning = (f.withColumn("ews_score", F.least(score, F.lit(100)))
    .withColumn("ews_reasons", reasons)
    .withColumn("risk_band", F.when(F.col("ews_score") >= 40, "HIGH").when(F.col("ews_score") >= 25, "MEDIUM").otherwise("LOW"))
    .withColumn("signal_type", F.when(F.col("ews_score") >= 25, "CREDIT_STRESS")
                .when(F.col("attrition_pattern"), "ATTRITION").otherwise("NONE"))
    .select("customer_no", "customer_type", "segment", "home_branch", "rm_id", "ews_score", "risk_band",
            "signal_type", "ews_reasons", "has_credit_exposure", "attrition_pattern", "active_loans", "total_emi_aed", "max_dpd", "overdue_amount_aed",
            "days_since_salary", "salary_change_pct", "inflow_change_pct", "inflow_change_yoy_pct", "balance_change_pct", "debt_burden_ratio",
            "as_of_date"))
save(early_warning, "early_warning",
     "Explainable early-warning score (0 to 100) per customer with risk band, signal type (CREDIT_STRESS or ATTRITION) and plain-language reasons. Cash-flow signals only; nationality and gender are never used.")

# ---------- Cell 5: collections_priority ----------
loan = s("loan_status").where(F.col("matures_on") >= F.lit(AS_OF))
repay_bal = acct.select(F.col("account_no").alias("repayment_account_no"),
                        F.col("current_balance_aed").alias("repayment_ac_balance_aed"))
ews = spark.table(f"{GLD}.early_warning").select("customer_no", "ews_score", "risk_band", "ews_reasons")
coll = (loan.join(repay_bal, "repayment_account_no", "left").join(ews, "customer_no", "left")
    .join(cust.select("customer_no", "customer_name", "segment", "rm_id"), "customer_no", "left")
    .withColumn("amount_needed_aed", F.col("emi_aed") + F.col("overdue_amount_aed"))
    .withColumn("shortfall_aed", F.greatest(F.col("amount_needed_aed") - F.coalesce("repayment_ac_balance_aed", F.lit(0)), F.lit(0)))
    .where((F.col("days_past_due") > 0) | (F.col("risk_band") != "LOW") | (F.col("shortfall_aed") > 0))
    .withColumn("recommended_action",
        F.when(F.col("days_past_due") > 90, "Recovery team: NPA workout")
         .when(F.col("days_past_due") > 30, "Collector call and restructuring assessment")
         .when(F.col("days_past_due") > 0, "Call and agree a payment date")
         .when((F.col("risk_band") == "HIGH") & (F.col("shortfall_aed") > 0), "Proactive RM call: offer payment holiday or restructure before due date")
         .when(F.col("shortfall_aed") > 0, "Pre-due reminder: top up repayment account")
         .otherwise("Monitor"))
    .withColumn("priority_score", F.round(F.col("days_past_due") * 2 + F.coalesce("ews_score", F.lit(0))
                + F.least(F.col("shortfall_aed") / 1000, F.lit(50)), 1))
    .withColumn("priority_rank", F.row_number().over(W.orderBy(F.desc("priority_score"))))
    .select("priority_rank", "loan_no", "customer_no", "customer_name", "segment", "rm_id", "product_code",
            "days_past_due", "dpd_bucket", "emi_aed", "overdue_amount_aed", "next_due_date",
            "repayment_ac_balance_aed", "shortfall_aed", "ews_score", "risk_band", "ews_reasons",
            "recommended_action", "priority_score"))
save(coll, "collections_priority",
     "Loans needing attention, ranked: days past due, EMI shortfall versus repayment account balance, early-warning score and a recommended next action, including proactive pre-delinquency calls.")

# ---------- Cell 6: sme_cashflow ----------
biz = cust.where(F.col("customer_type") == "C").select("customer_no", "customer_name", "segment", "business_description", "rm_id")
sme = (spark.table(f"{GLD}.customer_monthly_cashflow").join(biz, "customer_no")
    .withColumn("receipts_3m_avg", F.avg("inflow_aed").over(W.partitionBy("customer_no").orderBy("month").rowsBetween(-2, 0)))
    .withColumn("payments_3m_avg", F.avg("outflow_aed").over(W.partitionBy("customer_no").orderBy("month").rowsBetween(-2, 0)))
    .withColumn("net_burn_3m_avg", F.col("payments_3m_avg") - F.col("receipts_3m_avg"))
    .withColumn("runway_months", F.when(F.col("net_burn_3m_avg") > 0,
                F.round(F.col("month_end_balance_aed") / F.col("net_burn_3m_avg"), 1)))
    .select("customer_no", "customer_name", "segment", "business_description", "rm_id", "month",
            F.col("inflow_aed").alias("receipts_aed"), F.col("outflow_aed").alias("payments_aed"),
            "payroll_paid_aed", "net_cashflow_aed", "month_end_balance_aed",
            F.round("receipts_3m_avg", 2).alias("receipts_3m_avg"), F.round("net_burn_3m_avg", 2).alias("net_burn_3m_avg"),
            "runway_months"))
save(sme, "sme_cashflow",
     "SME and corporate cash flow per month: receipts, payments, payroll, net cash flow, balance, 3-month averages and cash runway in months when the business is burning cash.")

# ---------- Cell 7: verify ----------
spark.sql(f"SELECT signal_type, risk_band, COUNT(*) n FROM {GLD}.early_warning GROUP BY 1,2 ORDER BY 1,2").show()
spark.sql(f"SELECT risk_band, customer_type, COUNT(*) n, SUM(CAST(has_credit_exposure AS INT)) with_credit FROM {GLD}.early_warning GROUP BY 1,2 ORDER BY 1,2").show()
spark.sql(f"SELECT recommended_action, COUNT(*) n FROM {GLD}.collections_priority GROUP BY 1 ORDER BY 2 DESC").show(truncate=False)
spark.sql(f"SELECT priority_rank, customer_name, days_past_due, shortfall_aed, risk_band, recommended_action FROM {GLD}.collections_priority ORDER BY priority_rank LIMIT 10").show(truncate=False)
