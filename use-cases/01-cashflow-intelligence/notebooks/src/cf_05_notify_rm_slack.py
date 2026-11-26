# Extend FLEXCUBE on OCI | Use case 01 cash-flow intelligence | cf_05_notify_rm_slack
# Daily Slack direct message to each relationship manager (RM), after cf_04_publish_serving.
# For every RM in the directory it builds one short message (collections, credit stress, attrition, model early
# signs) and sends it as a Slack DM. The bot token is read from the AIDP Credential Store, never written here.
# Writes fcubs_lake.gold_cashflow.rm_directory (first run) and fcubs_lake.gold_cashflow.rm_alert_log (audit).

# ---------- Cell 1: settings ----------
import json, time, datetime as dt
import requests
from pyspark.sql import functions as F

SLV, GLD = "fcubs_lake.silver", "fcubs_lake.gold_cashflow"
FMT = "delta"
DRY_RUN = True                 # True: print the messages only. Set False to send to Slack.
DEMO_TO = None                 # e.g. "you@yourcompany.com": every RM message goes to this one Slack user (demo)
ONLY_RMS = None                # e.g. ["RM014", "RM001"]: limit the run to these RMs; None = all in the directory
UNASSIGNED_TO = None   # e.g. "teamlead@yourbank.com": alerts for customers with no RM (mass retail) go to this team lead; None = skip
SLACK_EMAILS = {}              # e.g. {"RM014": "rm014@yourbank.com"}: RM to Slack email, applied to rm_directory on every run; RMs without an email are skipped
CRED_NAME = "fcubs_slack_bot"  # Credential Store entry (type Secret Token)
CRED_KEY = "bot_token"         # key inside it holding the xoxb- token
MAX_ITEMS = 3                  # per section; the rest are counted and left to the copilot
AGENT_HINT = "Ask the RM copilot in Agent Hub for details on any customer."

# ---------- Cell 2: RM directory (who gets which message) ----------
# One row per RM: rm_id as used in FLEXCUBE, display name, and the email of their Slack account.
# The email is the stable key; the Slack user ID is looked up from it at send time.
# First run only: creates the table with placeholders. Afterwards maintain it in place, e.g.
#   UPDATE fcubs_lake.gold_cashflow.rm_directory SET slack_email = 'name@bank.ae' WHERE rm_id = 'RM014'
if not spark.catalog.tableExists(f"{GLD}.rm_directory"):
    rms = [r[0] for r in spark.table(f"{GLD}.early_warning").where("rm_id IS NOT NULL")
           .select("rm_id").distinct().orderBy("rm_id").collect()]
    rows = [(r, f"Relationship Manager {r[2:]}", SLACK_EMAILS.get(r), True) for r in rms]
    (spark.createDataFrame(rows, "rm_id string, rm_name string, slack_email string, active boolean")
     .write.format(FMT).mode("overwrite").saveAsTable(f"{GLD}.rm_directory"))
    try:
        spark.sql(f"COMMENT ON TABLE {GLD}.rm_directory IS 'Relationship managers and the email of their Slack account, for daily alert direct messages.'")
    except Exception as e:
        print("comment skipped:", str(e)[:80])
else:
    for rm, email in SLACK_EMAILS.items():          # keep the directory in line with the settings above
        spark.sql(f"UPDATE {GLD}.rm_directory SET slack_email = '{email}' WHERE rm_id = '{rm}'")
rm_dir = spark.table(f"{GLD}.rm_directory").where("active")
if ONLY_RMS:
    rm_dir = rm_dir.where(F.col("rm_id").isin(ONLY_RMS))
rm_dir.orderBy("rm_id").show(30, False)

# ---------- Cell 3: build each RM's items from the gold tables ----------
names = spark.table(f"{SLV}.customer_360").select("customer_no", "customer_name")
ew = spark.table(f"{GLD}.early_warning").join(names, "customer_no", "left")
reasons = F.array_join("ews_reasons", "; ")
fmt_aed = lambda c: F.format_number(F.col(c).cast("double"), 0)

items = []
# 1. Collections today: late loans and proactive calls, by priority
coll = (spark.table(f"{GLD}.collections_priority")
        .where(F.col("recommended_action").rlike("^(Proactive|Call|Collector)"))
        .select("rm_id", F.lit(1).alias("section"), F.col("priority_rank").cast("double").alias("ord"),
                F.concat(F.col("customer_name"), F.lit(": "), F.col("recommended_action"),
                         F.when(F.col("days_past_due") > 0, F.concat(F.lit(" ("), F.col("days_past_due"), F.lit(" days late)")))
                          .otherwise(F.concat(F.lit(" (shortfall AED "), fmt_aed("shortfall_aed"), F.lit(", due "), F.col("next_due_date").cast("string"), F.lit(")")))
                         ).alias("line")))
items.append(coll)
# 2. Credit stress from the rules
items.append(ew.where((F.col("signal_type") == "CREDIT_STRESS") & F.col("risk_band").isin("HIGH", "MEDIUM"))
             .select("rm_id", F.lit(2).alias("section"), (-F.col("ews_score")).cast("double").alias("ord"),
                     F.concat(F.col("customer_name"), F.lit(", "), F.col("risk_band"), F.lit(": "), reasons).alias("line")))
# 3. May be leaving the bank (rules)
items.append(ew.where(F.col("signal_type") == "ATTRITION")
             .select("rm_id", F.lit(3).alias("section"), (-F.col("ews_score")).cast("double").alias("ord"),
                     F.concat(F.col("customer_name"), F.lit(": "), reasons).alias("line")))
# 4. Model early signs: ML HIGH or MEDIUM where the rules see nothing yet
ml = spark.table(f"{GLD}.ml_early_warning").join(names, "customer_no", "left")
p = F.greatest(F.coalesce("p_arrears_90d", F.lit(0.0)), F.coalesce("p_attrition_90d", F.lit(0.0)))
items.append(ml.where((F.col("rules_signal") == "NONE")
                      & (F.col("ml_arrears_band").isin("HIGH", "MEDIUM") | F.col("ml_attrition_band").isin("HIGH", "MEDIUM")))
             .select("rm_id", F.lit(4).alias("section"), (-p).alias("ord"),
                     F.concat(F.col("customer_name"), F.lit(": "), F.round(p * 100).cast("int"), F.lit("% "),
                              F.when(F.col("p_attrition_90d") >= F.coalesce("p_arrears_90d", F.lit(0.0)), F.lit("chance of leaving"))
                               .otherwise(F.lit("chance of 30+ days late")),
                              F.lit(" in 90 days. "), F.coalesce("ml_drivers", F.lit(""))).alias("line")))

all_items = items[0]
for df in items[1:]:
    all_items = all_items.unionByName(df)
rows = all_items.withColumn("rm_id", F.coalesce("rm_id", F.lit("UNASSIGNED"))).toPandas()

TITLES = {1: ":telephone_receiver: *Collections today*", 2: ":warning: *Credit stress*",
          3: ":door: *May be leaving the bank*", 4: ":crystal_ball: *Model early signs* (rules not flagged yet)"}

def build_message(rm_id, rm_name, df):
    df = df.sort_values(["section", "ord"])
    total = len(df)
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": f"Good morning {rm_name}: {total} customer alert{'s' if total != 1 else ''} today"}}]
    text_lines = [f"Good morning {rm_name}: {total} customer alert{'s' if total != 1 else ''} today"]
    for sec, g in df.groupby("section"):
        lines = [f"• {l}" for l in g["line"].head(MAX_ITEMS)]
        more = len(g) - MAX_ITEMS
        if more > 0:
            lines.append(f"_and {more} more_")
        body = TITLES[sec] + "\n" + "\n".join(lines)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": body[:2900]}})
        text_lines.append(body)
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"{AGENT_HINT}  |  {rm_id}  |  Oasis Demo Bank (synthetic)"}]})
    return blocks, "\n".join(text_lines)[:3000]

directory = rm_dir.toPandas()
if UNASSIGNED_TO:                                   # customers with no RM go to a team lead
    directory.loc[len(directory)] = ["UNASSIGNED", "Retail team (customers without an RM)", UNASSIGNED_TO, True]
messages = []
for r in directory.itertuples():
    df = rows[rows.rm_id == r.rm_id]
    if len(df) == 0:
        continue                                    # nothing today: no message, no noise
    blocks, text = build_message(r.rm_id, r.rm_name, df)
    messages.append({"rm_id": r.rm_id, "email": DEMO_TO or (r.slack_email if isinstance(r.slack_email, str) and r.slack_email else None), "n": len(df), "blocks": blocks, "text": text})
skipped = [m["rm_id"] for m in messages if not m["email"]]
messages = [m for m in messages if m["email"]]          # no Slack email yet: skip quietly, listed below
print(f"{len(messages)} messages to send; skipped (no Slack email): {', '.join(skipped) or 'none'}")
for m in messages[:3]:
    print("-" * 60, "\n", m["rm_id"], "->", m["email"], "\n", m["text"])

# ---------- Cell 4: send as Slack direct messages ----------
# Bot token scopes needed: chat:write, users:read, users:read.email
results = []
if not DRY_RUN:
    token = aidputils.secrets.get(name=CRED_NAME, key=CRED_KEY)
    H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
    user_ids = {}
    for m in messages:
        status = "sent"
        try:
            if m["email"] not in user_ids:
                u = requests.get("https://slack.com/api/users.lookupByEmail", headers=H,
                                 params={"email": m["email"]}, timeout=20).json()
                if not u.get("ok"):
                    raise ValueError(f"lookup failed: {u.get('error')}")
                user_ids[m["email"]] = u["user"]["id"]
            r = requests.post("https://slack.com/api/chat.postMessage", headers=H, timeout=20,
                              data=json.dumps({"channel": user_ids[m["email"]], "text": m["text"], "blocks": m["blocks"]})).json()
            if not r.get("ok"):
                raise ValueError(f"post failed: {r.get('error')}")
        except Exception as e:
            status = f"failed: {str(e)[:180]}"
        results.append((m["rm_id"], m["email"], m["n"], status))
        print(f"{m['rm_id']:6s} {status}")
        time.sleep(1.1)                             # stay under Slack's rate limit of about 1 message per second
else:
    results = [(m["rm_id"], m["email"], m["n"], "dry run") for m in messages]

# ---------- Cell 5: audit log ----------
if results:
    as_of = spark.table(f"{GLD}.early_warning").agg(F.max("as_of_date")).first()[0]
    log = (spark.createDataFrame(results, "rm_id string, slack_email string, alert_count int, status string")
           .withColumn("as_of_date", F.lit(as_of).cast("date"))
           .withColumn("sent_at", F.current_timestamp()))
    log.write.format(FMT).mode("append").saveAsTable(f"{GLD}.rm_alert_log")
    spark.table(f"{GLD}.rm_alert_log").orderBy(F.desc("sent_at")).show(30, False)
failed = [r for r in results if r[3].startswith("failed")]
if failed:
    raise Exception(f"{len(failed)} Slack message(s) failed: {failed[:3]}")
