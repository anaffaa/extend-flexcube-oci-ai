# 4. Daily RM alerts and the copilot in Slack

Both parts are optional. The same pattern works for Microsoft Teams or email by changing the sending cell or the bridge.

## Part 1: one direct message per RM each morning

Each RM receives one Slack direct message with only their customers: collections today, credit stress, possible attrition,
and model early signs (ML HIGH or MEDIUM where the rules see nothing). Customers without an RM can go to a team lead. Nothing
to report means no message.

**Why a notebook and not the agent:** a daily push needs no conversation. A workflow task is cheaper, predictable and
auditable. The agent stays for questions.

1. **Slack app.** api.slack.com/apps > Create New App > From scratch (installing may need a workspace admin). Bot token
   scopes `chat:write`, `users:read`, `users:read.email`; App Home > Messages tab on; install and copy the bot token. Treat it
   as a secret: never paste it in a notebook, chat or screenshot, and revoke it if exposed.
2. **Credential Store.** AIDP > Create > Credentials: name `fcubs_slack_bot`, type Secret Token, key `bot_token`. The notebook
   reads it with `aidputils.secrets.get(name="fcubs_slack_bot", key="bot_token")`.
3. **RM directory.** The first run of `cf_05_notify_rm_slack` creates `fcubs_lake.gold_cashflow.rm_directory` (rm_id, rm_name,
   slack_email, active). The Slack account email is the key; the Slack user ID is looked up at send time. Fill emails in
   `SLACK_EMAILS` (applied every run) or with `UPDATE ... SET slack_email = ... WHERE rm_id = ...`. RMs without an email are
   skipped and listed. In production, load this table from the bank's HR or identity directory.
4. **Dry run.** Keep `DRY_RUN = True`, run, read the printed messages.
5. **One real message.** `DRY_RUN = False`, `ONLY_RMS = ["RM014"]`, `DEMO_TO = "<your Slack email>"`. A timeout means the
   cluster cannot reach slack.com (egress through the NAT gateway).
6. **Go live.** Clear `ONLY_RMS` and `DEMO_TO`, optionally set `UNASSIGNED_TO`, and add the notebook to the workflow after
   `cf_04_publish_serving`. Every run appends to `rm_alert_log`; the task fails if any message fails.

**Watch-outs:** customer names leave OCI into Slack. That needs the bank's approval for real data; otherwise send customer
numbers only. Production should alert only on changes since the previous day.

## Part 2: the copilot inside Slack

RMs message the bot or mention it in a channel and get the agent's answer in the thread; follow-ups keep context. A small
bridge ([`channels/slack`](../../../channels/slack)) forwards questions to the deployed agent's `/chat` endpoint with OCI-signed
requests and posts the answers back. Instructions, tools, guardrails and traces still apply.

1. Update the Slack app with the bridge's manifest (Socket Mode, events `app_mention` and `message.im`) and create an
   app-level token with `connections:write`.
2. Run the bridge: locally for a test, or as an OCI Container Instance with a resource principal (no keys stored). Socket Mode
   needs no public URL or inbound rule. Steps: [`channels/slack/README.md`](../../../channels/slack/README.md).
3. Test: "How is the portfolio looking this morning?", then in the same thread "Which customers is the model worried about
   that the rules have not flagged, and why?".

**Before production:** every Slack user queries as the bridge's identity. Map Slack users to RMs and filter results per RM.
