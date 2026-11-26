# FCUBS RM Copilot in Slack

Lets relationship managers ask the deployed AIDP agent `fcubs_rm_copilot_v1` questions from Slack, by direct
message or by @mentioning the bot in a channel. Answers come back in the same thread; follow-ups in a thread keep
the conversation. The agent's instructions, 8 SQL tools, guardrails and trace all still apply, because Slack only
carries the question and the answer.

```
Slack (DM or @mention) -> copilot_bridge.py (Socket Mode, OCI-signed) -> AIDP agent /chat -> answer in thread
```

## 1. Update the Slack app (same FCUBS RM Alerts app)
1. api.slack.com/apps > FCUBS RM Alerts > **App Manifest**: replace with `slack_app_manifest.yaml` > Save.
   It adds Socket Mode, the events `app_mention` and `message.im`, and the scopes `app_mentions:read`,
   `im:history`, `im:read`, `reactions:write`.
2. **Basic Information > App-Level Tokens > Generate Token and Scopes**: name `socket`, scope
   `connections:write` > Generate. Copy the `xapp-...` token (do not screenshot it).
3. **Install App > Reinstall to <your workspace> > Allow** (needed after adding scopes). The bot token stays the same.
4. **App Home**: tick "Allow users to send Slash commands and messages from the messages tab".

## 2. Run the bridge on your laptop (demo)
Needs Python 3.10+ and an OCI API key profile in `~/.oci/config` for a user allowed to use the agent.
```bash
cd slack_bridge
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                       # fill in the 3 values, keep it private
set -a; source .env; set +a                                 # Windows PowerShell: set each with $env:NAME="value"
python copilot_bridge.py
```
Expected: `FCUBS RM Copilot bridge starting (Socket Mode)` and `Bolt app is running`.
Then in Slack: DM **FCUBS RM Alerts**: "How is the portfolio looking this morning?"

## 3. Run it in OCI (always on)
Build the image from the `Dockerfile`, push to OCIR, create an OCI Container Instance in your compartment with the three
environment variables (`SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `AIDP_CHAT_URL`; better: read them from OCI Vault).
It then authenticates with its resource principal: add it to a dynamic group and grant that group use of the
AIDP agent endpoint (confirm the exact policy in the AIDP docs). Outbound HTTPS to slack.com and the AIDP gateway
is required; no inbound access.

## Good to know
- Everyone in Slack queries as the bridge's identity (your OCI user or the container's resource principal), not
  as themselves. Fine for a demo; production needs a user mapping or per-RM filtering.
- Conversation memory per thread is kept in memory; restarting the bridge starts new conversations.
- The Cohere "I will use the ... tool" sentence is removed before posting; markdown tables are shown as code blocks.
- Customer names appear in Slack, outside OCI: synthetic data only, approval needed for a real bank.
