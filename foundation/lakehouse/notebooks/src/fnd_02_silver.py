# Extend FLEXCUBE on OCI | Foundation notebook fnd_02_silver: silver layer (shared data products)
# Cleans and conforms bronze FLEXCUBE tables into 6 business-friendly tables reused by every use case.
# Safe to re-run (overwrite). Reads fcubs_lake.bronze, writes fcubs_lake.silver.

# ---------- Cell 1: setup ----------
from pyspark.sql import functions as F, Window as W

BRZ = "fcubs_lake.bronze"
SLV = "fcubs_lake.silver"
FMT = "delta"
AS_OF = None                  # None = derive from FLEXCUBE (day after the latest ACTB_HISTORY posting); or "YYYY-MM-DD"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SLV}")
b = lambda t: spark.table(f"{BRZ}.{t}")
if AS_OF is None:
    AS_OF = str(b("actb_history").agg(F.date_add(F.max(F.to_date("trn_dt")), 1)).first()[0])
print("As-of (branch) date:", AS_OF)

def save(df, name, comment):
    df.write.format(FMT).mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SLV}.{name}")
    try:
        spark.sql(f"COMMENT ON TABLE {SLV}.{name} IS '{comment}'")
    except Exception as e:
        print("comment skipped:", str(e)[:80])
    print(f"{name:24s} {spark.table(f'{SLV}.{name}').count():>10,d}")

# ---------- Cell 2: customer_360 ----------
score = (b("sttm_credit_score_grade")
         .groupBy("customer_no")
         .agg(F.max(F.when(F.col("rule_id") == "BUREAU_SCORE", F.col("final_score"))).cast("int").alias("bureau_score"),
              F.max(F.when(F.col("rule_id") == "INTERNAL_RATING", F.col("final_score"))).cast("int").alias("internal_rating"),
              F.max("grade").alias("score_grade")))

c = b("sttm_customer").alias("c")
p = b("sttm_cust_personal").alias("p")
co = b("sttm_cust_corporate").alias("co")
k = b("sttm_kyc_master").alias("k")

customer_360 = (c.join(p, "customer_no", "left").join(co, "customer_no", "left")
    .join(score, "customer_no", "left")
    .join(k, F.col("c.kyc_ref_no") == F.col("k.kyc_ref_no"), "left")
    .select(
        "customer_no",
        F.col("c.customer_type").alias("customer_type"),                 # I individual, C corporate
        F.col("c.customer_category").alias("segment"),                   # INDIVIDUAL, PRIORITY, STAFF, SME, CORPORATE
        F.coalesce("c.full_name", "c.customer_name1").alias("customer_name"),
        F.col("c.local_branch").alias("home_branch"),
        F.col("c.rm_id").alias("rm_id"),
        F.to_date("c.cif_creation_date").alias("customer_since"),
        F.col("c.risk_category").alias("aml_risk_category"),
        F.col("k.risk_level").alias("kyc_risk_level"),
        "bureau_score", "internal_rating", "score_grade",
        F.floor(F.months_between(F.lit(AS_OF), F.col("p.date_of_birth")) / 12).cast("int").alias("age"),
        F.col("p.resident_status").alias("resident_status"),
        F.col("co.business_description").alias("business_description"),
        F.to_date("co.incorp_date").alias("incorporation_date"),
        F.col("co.networth").cast("decimal(18,2)").alias("declared_networth"),
        # protected attributes kept for reporting only, never used as model features
        F.col("c.nationality").alias("nationality"),
        F.col("p.sex").alias("gender"),
        F.col("c.record_stat").alias("record_stat")))
save(customer_360, "customer_360",
     "One row per customer: segment, branch, RM, KYC and AML risk, bureau score or internal rating, age, business profile. Nationality and gender are for reporting only, never model features.")

# ---------- Cell 3: accounts ----------
accounts = (b("sttm_cust_account").alias("a")
    .join(b("sttm_account_class").alias("ac"), "account_class", "left")
    .select(
        F.col("a.cust_ac_no").alias("account_no"),
        F.col("a.cust_no").alias("customer_no"),
        F.col("a.branch_code").alias("branch"),
        F.col("a.ccy").alias("ccy"),
        "account_class",
        F.col("ac.description").alias("account_type"),
        F.col("ac.ac_class_type").alias("class_type"),                  # S savings, C current, U term deposit
        F.to_date("a.ac_open_date").alias("opened_on"),
        (F.col("a.salary_account") == "Y").alias("is_salary_account"),
        (F.col("a.ac_stat_dormant") == "Y").alias("is_dormant"),
        (F.col("a.record_stat") == "C").alias("is_closed"),
        F.coalesce(F.col("a.tod_limit"), F.lit(0)).cast("decimal(18,2)").alias("overdraft_limit"),
        F.col("a.lcy_curr_balance").cast("decimal(18,2)").alias("current_balance_aed"),
        F.to_date("a.date_last_cr").alias("last_credit_date"),
        F.to_date("a.date_last_dr").alias("last_debit_date")))
save(accounts, "accounts",
     "One row per customer account with product type, salary flag, dormancy, overdraft limit and current balance in AED.")

# ---------- Cell 4: account_daily_balance ----------
account_daily_balance = (b("actb_accbal_history")
    .select(F.col("account").alias("account_no"),
            F.to_date("bkg_date").alias("balance_date"),
            F.col("acc_ccy").alias("ccy"),
            F.col("lcy_opening_bal").cast("decimal(18,2)").alias("opening_bal_aed"),
            F.col("lcy_closing_bal").cast("decimal(18,2)").alias("closing_bal_aed"),
            F.col("lcy_cr_tur").cast("decimal(18,2)").alias("credits_aed"),
            F.col("lcy_dr_tur").cast("decimal(18,2)").alias("debits_aed")))
save(account_daily_balance, "account_daily_balance",
     "One row per account per day with movement: opening and closing balance, total credits and debits in AED.")

# ---------- Cell 5: transactions ----------
# FLEXCUBE transaction codes are defined per bank. These are the sample bank's codes: map YOUR codes here
# (run foundation/source/own-flexcube/02_precheck.sql, section 5, to list your most used codes). "by_direction" means
# credit = transfer_in, debit = transfer_out. Codes not listed become "other" and are left out of most features.
TRN_CATEGORY = {
    "SAL": "salary_in",
    "POS": "card_spend", "ECM": "card_spend",
    "ATM": "cash_out", "CSW": "cash_out",
    "CSD": "cash_in", "CDM": "cash_in",
    "FTI": "transfer_in", "SWI": "transfer_in", "CHD": "transfer_in",
    "FTO": "transfer_out", "SWO": "transfer_out", "CHQ": "transfer_out",
    "BKT": "by_direction",
    "PAY": "payroll_out",
    "LNR": "loan_repayment",
    "LND": "loan_disbursement",
    "BIL": "bill_payment",
    "CHG": "fees",
    "INT": "interest_in",
    "TDF": "term_deposit", "TDM": "term_deposit",
}
category = F.lit("other")
for code, cat in reversed(list(TRN_CATEGORY.items())):
    value = (F.when(F.col("drcr_ind") == "C", "transfer_in").otherwise("transfer_out")) if cat == "by_direction" else F.lit(cat)
    category = F.when(F.col("trn_code") == code, value).otherwise(category)

transactions = (b("actb_history").where(F.col("cust_gl") == "A")          # customer legs only, GL legs excluded
    .join(b("sttm_trn_code").select("trn_code", "trn_desc"), "trn_code", "left")
    .select(F.col("trn_ref_no"), F.col("ac_no").alias("account_no"),
            F.col("related_customer").alias("customer_no"),
            F.to_date("trn_dt").alias("txn_date"),
            F.col("drcr_ind"), "trn_code", "trn_desc",
            category.alias("category"),
            F.col("lcy_amount").cast("decimal(18,2)").alias("amount_aed"),
            F.when(F.col("drcr_ind") == "C", F.col("lcy_amount")).otherwise(-F.col("lcy_amount"))
             .cast("decimal(18,2)").alias("signed_amount_aed"),
            F.col("module"), F.col("product"),
            F.col("related_reference").alias("related_reference")))
save(transactions, "transactions",
     "Customer-side accounting entries with readable category (salary_in, card_spend, cash_out, transfer_in or out, loan_repayment, fees) and signed AED amount.")

# ---------- Cell 6: loan_status ----------
sch = b("cltb_account_schedules")
overdue = (sch.where((F.col("amount_overdue") > 0) & (F.to_date("schedule_due_date") <= F.lit(AS_OF)))
    .groupBy("account_number")
    .agg(F.sum("amount_overdue").cast("decimal(18,2)").alias("overdue_amount_aed"),
         F.min(F.to_date("schedule_due_date")).alias("oldest_overdue_due_date")))
progress = (sch.where(F.col("component_name") == "PRINCIPAL").groupBy("account_number")
    .agg(F.count("*").alias("installments_total"),
         F.sum(F.when(F.to_date("schedule_due_date") <= F.lit(AS_OF), 1).otherwise(0)).alias("installments_due"),
         F.sum("amount_settled").cast("decimal(18,2)").alias("principal_repaid_aed"),
         F.min(F.when(F.to_date("schedule_due_date") > F.lit(AS_OF), F.to_date("schedule_due_date"))).alias("next_due_date")))
last_paid = (b("cltb_amount_paid").groupBy("account_number")
    .agg(F.max(F.to_date("paid_date")).alias("last_payment_date")))
rate = (b("cltb_account_ude_values").where(F.col("ude_id") == "INTEREST_RATE")
    .select("account_number", F.col("ude_value").cast("decimal(6,2)").alias("interest_rate_pct")))

loan_status = (b("cltb_account_apps_master")
    .join(overdue, "account_number", "left").join(progress, "account_number", "left")
    .join(last_paid, "account_number", "left").join(rate, "account_number", "left")
    .select(F.col("account_number").alias("loan_no"),
            F.col("customer_id").alias("customer_no"),
            F.col("product_code"), F.col("product_category"),
            F.to_date("value_date").alias("disbursed_on"),
            F.to_date("maturity_date").alias("matures_on"),
            F.col("amount_financed").cast("decimal(18,2)").alias("amount_financed_aed"),
            F.col("emi_amount").cast("decimal(18,2)").alias("emi_aed"),
            "interest_rate_pct", "installments_total", "installments_due", "principal_repaid_aed",
            F.coalesce("overdue_amount_aed", F.lit(0).cast("decimal(18,2)")).alias("overdue_amount_aed"),
            F.coalesce(F.datediff(F.lit(AS_OF), F.col("oldest_overdue_due_date")), F.lit(0)).alias("days_past_due"),
            "next_due_date", "last_payment_date",
            F.col("dr_prod_ac").alias("repayment_account_no"),
            F.col("derived_status").alias("flexcube_status"))          # NORM, PDO1 to PDO3, NPA
    .withColumn("dpd_bucket", F.when(F.col("days_past_due") == 0, "0 current")
                .when(F.col("days_past_due") <= 30, "1-30").when(F.col("days_past_due") <= 60, "31-60")
                .when(F.col("days_past_due") <= 90, "61-90").otherwise("90+ NPA")))
save(loan_status, "loan_status",
     "One row per loan as of branch date: EMI, rate, installments due, overdue amount, days past due, DPD bucket, FLEXCUBE status and repayment account.")

# ---------- Cell 7: card_spend ----------
mcc_map = {"5411": "Groceries", "5812": "Restaurants", "5814": "Fast Food", "5541": "Fuel", "5912": "Pharmacy",
           "5732": "Electronics", "5651": "Clothing", "5311": "Department Store", "4121": "Taxi and Ride Hailing",
           "4511": "Airlines", "7011": "Hotels", "4814": "Telecom", "5999": "Online Marketplace",
           "7832": "Entertainment", "8062": "Hospitals", "8220": "Education", "6011": "ATM Cash"}
mcc_df = spark.createDataFrame(list(mcc_map.items()), "mcc string, merchant_category string")
essential = ["Groceries", "Pharmacy", "Fuel", "Telecom", "Hospitals", "Education"]

card_spend = (b("swtb_settlement_hist")
    .withColumn("mcc", F.col("merchant_category_code").cast("string"))
    .join(mcc_df, "mcc", "left")
    .select(F.col("external_ref_no").alias("card_txn_ref"),
            F.col("acc").alias("account_no"), F.col("pan").alias("masked_pan"),
            F.to_date("txn_date").alias("txn_date"),
            F.col("txn_time"), F.col("channel"),                         # POS, ECM (online), ATM
            F.col("bill_amt").cast("decimal(18,2)").alias("amount_aed"),
            F.col("merchant_name"), F.col("merchant_city"), F.col("merchant_country"),
            "mcc", "merchant_category",
            F.col("merchant_category").isin(essential).alias("is_essential"),
            (F.col("domestic_flag") == "Y").alias("is_domestic"),
            (F.col("status") == "S").alias("is_approved"),
            F.col("resp_code")))
save(card_spend, "card_spend",
     "Card and ATM transactions with merchant category, essential versus discretionary flag, domestic or foreign, online or in-store, approved or declined.")

# ---------- Cell 8: verify ----------
for t in ["customer_360", "accounts", "account_daily_balance", "transactions", "loan_status", "card_spend"]:
    print(f"{t:24s} {spark.table(f'{SLV}.{t}').count():>10,d}")
spark.sql(f"SELECT dpd_bucket, flexcube_status, COUNT(*) n FROM {SLV}.loan_status GROUP BY 1,2 ORDER BY 1,2").show()
spark.sql(f"SELECT category, COUNT(*) n, ROUND(SUM(amount_aed)/1e6,1) aed_m FROM {SLV}.transactions GROUP BY 1 ORDER BY 2 DESC").show()
