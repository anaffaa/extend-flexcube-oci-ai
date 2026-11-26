"""FCUBS RM Copilot in Slack: a small bridge between Slack and the deployed AIDP agent.

Slack user DMs the bot (or @mentions it in a channel)  ->  this app  ->  AIDP agent /chat endpoint
(OCI-signed request)  ->  answer posted back in the same Slack thread. Each Slack thread keeps its own
conversation by passing the agent's previous response id, so follow-up questions keep their context.

Runs with Slack Socket Mode: no public URL, no inbound firewall rule. Start it on a laptop with an OCI
API key profile, or in an OCI Container Instance (resource principal, no keys stored).

Environment variables (never put the values in code):
  SLACK_BOT_TOKEN    xoxb-...  Bot User OAuth Token of the FCUBS RM Alerts app
  SLACK_APP_TOKEN    xapp-...  App-level token with connections:write (Socket Mode)
  AIDP_CHAT_URL      https://gateway.aidp.<region>.oci.oraclecloud.com/agentendpoint/<id>/chat
  OCI_CONFIG_PROFILE OCI profile name in ~/.oci/config (default DEFAULT); ignored in a Container Instance
"""
import os
import re
import logging

import oci
import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("fcubs-copilot-bridge")

AIDP_CHAT_URL = os.environ["AIDP_CHAT_URL"].rstrip("/")
TIMEOUT_S = int(os.getenv("AIDP_TIMEOUT_S", "180"))


# ---------- OCI signing (same approach as Oracle's oracle-aidp-samples Streamlit client) ----------
def make_signer():
    if os.getenv("OCI_RESOURCE_PRINCIPAL_VERSION"):                 # running in an OCI Container Instance
        log.info("Auth: resource principal")
        return oci.auth.signers.get_resource_principals_signer()
    profile = os.getenv("OCI_CONFIG_PROFILE", "DEFAULT")
    cfg = oci.config.from_file(profile_name=profile)
    if "security_token_file" in cfg:                                 # oci session authenticate
        log.info("Auth: security token profile %s", profile)
        with open(os.path.expanduser(cfg["security_token_file"])) as f:
            token = f.read().strip()
        key = oci.signer.load_private_key_from_file(cfg["key_file"])
        return oci.auth.signers.SecurityTokenSigner(token, key)
    log.info("Auth: API key profile %s", profile)
    return oci.Signer(tenancy=cfg["tenancy"], user=cfg["user"], fingerprint=cfg["fingerprint"],
                      private_key_file_location=cfg["key_file"], pass_phrase=cfg.get("pass_phrase"))


SIGNER = make_signer()


def ask_agent(text, previous_response_id=None):
    """Send one question to the deployed agent; return (answer_text, response_id)."""
    body = {"isStreamEnabled": False,
            "input": [{"role": "user", "content": [{"type": "INPUT_TEXT", "text": text}]}],
            "previous_response_id": previous_response_id}
    r = requests.post(AIDP_CHAT_URL, json=body, auth=SIGNER, timeout=TIMEOUT_S,
                      headers={"Content-Type": "application/json"})
    r.raise_for_status()
    data = r.json()
    parts = [c.get("text", "") for o in data.get("output", []) for c in (o.get("content") or []) if c.get("text")]
    return "\n".join(parts).strip(), data.get("id")


# ---------- make the agent's markdown read well in Slack ----------
TOOL_PLAN = re.compile(r"^\s*I will (use|call|run|check)[^.]*\.\s*", re.IGNORECASE)   # Cohere "tool plan" sentence


def to_slack(md):
    md = TOOL_PLAN.sub("", md)
    out, table = [], []
    for line in md.splitlines():
        if line.strip().startswith("|"):                     # markdown tables do not render in Slack: keep as a code block
            if not re.match(r"^\s*\|[\s:\-|]+\|\s*$", line):  # drop the |---|---| separator row
                table.append(line.strip())
            continue
        if table:
            out.append("```\n" + "\n".join(table) + "\n```")
            table = []
        line = re.sub(r"\*\*(.+?)\*\*", r"*\1*", line)        # **bold** -> *bold*
        line = re.sub(r"^#{1,6}\s*(.+)$", r"*\1*", line)       # headings -> bold
        out.append(line)
    if table:
        out.append("```\n" + "\n".join(table) + "\n```")
    return "\n".join(out).strip()[:39000] or "_The copilot returned no text._"


# ---------- Slack app ----------
app = App(token=os.environ["SLACK_BOT_TOKEN"])
threads = {}          # Slack thread -> last agent response id (in memory; restart = new conversations)


def handle(question, channel, thread_ts, say, client, msg_ts):
    question = re.sub(r"<@[A-Z0-9]+>", "", question).strip()      # remove the @mention itself
    if not question:
        say(text="Ask me about your customers, for example: _Which of my customers are at risk?_", thread_ts=thread_ts)
        return
    try:
        client.reactions_add(channel=channel, timestamp=msg_ts, name="hourglass_flowing_sand")
    except Exception:
        pass
    key = f"{channel}:{thread_ts}"
    try:
        answer, rid = ask_agent(question, threads.get(key))
        threads[key] = rid
        say(text=to_slack(answer), thread_ts=thread_ts)
    except requests.HTTPError as e:
        log.warning("AIDP error %s: %s", e.response.status_code, e.response.text[:300])
        say(text=f"Sorry, the copilot returned an error ({e.response.status_code}). Please try again.", thread_ts=thread_ts)
    except Exception as e:
        log.exception("bridge error")
        say(text="Sorry, I could not reach the copilot right now.", thread_ts=thread_ts)
    finally:
        try:
            client.reactions_remove(channel=channel, timestamp=msg_ts, name="hourglass_flowing_sand")
        except Exception:
            pass


@app.event("app_mention")                 # @FCUBS RM Alerts ... in a channel: answer in the thread
def on_mention(event, say, client):
    handle(event.get("text", ""), event["channel"], event.get("thread_ts") or event["ts"], say, client, event["ts"])


@app.event("message")                     # direct message to the bot
def on_dm(event, say, client):
    if event.get("channel_type") != "im" or event.get("bot_id") or event.get("subtype"):
        return
    handle(event.get("text", ""), event["channel"], event.get("thread_ts") or event["ts"], say, client, event["ts"])


if __name__ == "__main__":
    log.info("FCUBS RM Copilot bridge starting (Socket Mode) for %s", AIDP_CHAT_URL.split("/agentendpoint/")[0])
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
