#!/usr/bin/env bash
# Build the serving layer in the AIDP Lakehouse: users FCUBS_GOLD (publisher) and AIDP_AGENT (read-only), then the
# serving tables of every use case you enable. Runs foundation/serving/sql/00_serving_users.sql and each
# use-cases/<NN-name>/sql/*serving_tables.sql through the Lakehouse's REST-enabled SQL endpoint.
# Safe to re-run: existing users and tables are kept.
#
# Usage, from the repository root:
#   bash foundation/serving/deploy_serving_layer.sh <Lakehouse OCID> [use case folder ...]
#   e.g. bash foundation/serving/deploy_serving_layer.sh ocid1.autonomousdatabase... 01-cashflow-intelligence
# Without use case folders, all use cases that ship serving SQL are deployed.
# The Lakehouse is the Autonomous AI Database AIDP created with your instance (name starts with "Aidp").
# Passwords come from OCI Vault (FROM_TERRAFORM=true or *_SECRET_OCID in deploy.env) or are prompted; never stored.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
ENV_FILE="${DEPLOY_ENV:-$REPO/foundation/source/sample-bank/deploy.env}"
# shellcheck disable=SC1090
[ -f "$ENV_FILE" ] && source "$ENV_FILE"
LH_OCID="${1:-${LAKEHOUSE_OCID:-}}"
[ -n "$LH_OCID" ] || { echo "Usage: bash foundation/serving/deploy_serving_layer.sh <Lakehouse OCID> [use case folder ...]"; exit 1; }
shift || true
OCI="oci --profile ${OCI_PROFILE:-DEFAULT}"
if [ "$#" -gt 0 ]; then USE_CASES=("$@"); else
  USE_CASES=(); for d in "$REPO"/use-cases/*/sql; do ls "$d"/*serving_tables.sql >/dev/null 2>&1 && USE_CASES+=("$(basename "$(dirname "$d")")"); done
fi
for uc in "${USE_CASES[@]}"; do [ -d "$REPO/use-cases/$uc/sql" ] || { echo "No use case folder use-cases/$uc/sql"; exit 1; }; done
if [ "${FROM_TERRAFORM:-false}" = "true" ]; then
  command -v terraform >/dev/null || { echo "FROM_TERRAFORM=true needs terraform on the PATH"; exit 1; }
  TF_JSON="$(terraform -chdir="${TF_DIR:-$REPO/foundation/terraform}" output -json secret_ids)"
  sid() { printf '%s' "$TF_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get(sys.argv[1],""))' "$1"; }
  LH_ADMIN_SECRET_OCID="$(sid lakehouse-admin)"; GOLD_SECRET_OCID="$(sid fcubs-gold)"; AGENT_SECRET_OCID="$(sid aidp-agent)"
fi
for cmd in oci curl python3; do command -v "$cmd" >/dev/null || { echo "Please install $cmd"; exit 1; }; done

ask_pw() {
  local p1 p2
  while true; do
    read -r -s -p "$1: " p1; echo >&2
    read -r -s -p "Repeat: " p2; echo >&2
    [ "$p1" = "$p2" ] || { echo "Passwords differ, try again." >&2; continue; }
    if [[ ${#p1} -ge 12 && ${#p1} -le 30 && "$p1" =~ [A-Z] && "$p1" =~ [a-z] && "$p1" =~ [0-9] && "$p1" != *'"'* && "$p1" != *"'"* ]]; then
      printf '%s' "$p1"; return
    fi
    echo "Use 12 to 30 characters with upper case, lower case and a number, and no quote characters." >&2
  done
}
secret() { $OCI secrets secret-bundle get --secret-id "$1" --query 'data."secret-bundle-content".content' --raw-output | base64 -d; }
if [ -n "${LH_ADMIN_SECRET_OCID:-}" ]; then ADMIN_PW="$(secret "$LH_ADMIN_SECRET_OCID")"; echo "Lakehouse ADMIN password read from OCI Vault"
else read -r -s -p "Lakehouse ADMIN password (set when you created the AIDP instance): " ADMIN_PW; echo; fi
if [ -n "${GOLD_SECRET_OCID:-}" ]; then GOLD_PW="$(secret "$GOLD_SECRET_OCID")"; else GOLD_PW="$(ask_pw "New password for FCUBS_GOLD (publisher)")"; fi
if [ -n "${AGENT_SECRET_OCID:-}" ]; then AGENT_PW="$(secret "$AGENT_SECRET_OCID")"; else AGENT_PW="$(ask_pw "New password for AIDP_AGENT (agent, read-only)")"; fi

STATE="$($OCI db autonomous-database get --autonomous-database-id "$LH_OCID" --query 'data."lifecycle-state"' --raw-output)"
if [ "$STATE" = "STOPPED" ]; then
  echo "Starting the Lakehouse..."; $OCI db autonomous-database start --autonomous-database-id "$LH_OCID" --wait-for-state AVAILABLE >/dev/null
fi
ORDS_URL="$($OCI db autonomous-database get --autonomous-database-id "$LH_OCID" --query 'data."connection-urls"."ords-url"' --raw-output)"
ORDS_URL="${ORDS_URL%/}"
NETRC="$(mktemp)"; TMP="$(mktemp)"; chmod 600 "$NETRC" "$TMP"; trap 'rm -f "$NETRC" "$TMP"' EXIT
printf 'machine %s login ADMIN password %s\n' "$(printf '%s' "$ORDS_URL" | sed -E 's#https://([^/]+).*#\1#')" "$ADMIN_PW" > "$NETRC"

run_sql() {   # ignores "already exists" errors so re-runs are safe
  curl -sS --fail-with-body --netrc-file "$NETRC" -X POST "$ORDS_URL/admin/_/sql" \
       -H 'Content-Type: application/sql' --data-binary @"$1" | python3 -c '
import json, sys
r = json.load(sys.stdin); bad = 0
ok_codes = {955, 1920, 2260, 2275, 1430, 1442}   # name already used, user exists, PK or FK exists, column exists
for it in r.get("items", []):
    code = it.get("errorCode")
    if code and int(code) not in ok_codes:
        bad += 1; print("ERROR:", code, it.get("errorMessage"), "|", (it.get("statementText") or "")[:120])
    elif code:
        print("exists, kept:", (it.get("statementText") or "")[:80].replace("\n", " "))
sys.exit(1 if bad else 0)'
}
echo "Creating serving users FCUBS_GOLD and AIDP_AGENT..."
GOLD_PW="$GOLD_PW" AGENT_PW="$AGENT_PW" python3 -c '
import os, sys
s = open(sys.argv[1]).read().replace("<FCUBS_GOLD_PASSWORD>", os.environ["GOLD_PW"]).replace("<AIDP_AGENT_PASSWORD>", os.environ["AGENT_PW"])
open(sys.argv[2], "w").write(s)' "$HERE/sql/00_serving_users.sql" "$TMP"
run_sql "$TMP"
for uc in "${USE_CASES[@]}"; do
  for f in "$REPO/use-cases/$uc/sql/"*serving_tables.sql; do
    echo "Serving tables for $uc ($(basename "$f"))..."; cp "$f" "$TMP"; run_sql "$TMP"
  done
done
cat > "$TMP" <<'SQL'
SELECT (SELECT COUNT(*) FROM all_tables WHERE owner = 'FCUBS_GOLD') AS serving_tables,
       (SELECT COUNT(*) FROM all_tab_privs WHERE grantee = 'AIDP_AGENT' AND table_schema = 'FCUBS_GOLD') AS agent_grants
FROM dual;
SQL
curl -sS --netrc-file "$NETRC" -X POST "$ORDS_URL/admin/_/sql" -H 'Content-Type: application/sql' --data-binary @"$TMP" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); print("Check (cash flow alone: 4 tables, 4 grants):", r["items"][0]["resultSet"]["items"][0])'
echo "Next: docs/foundation/02_deploy.md, step 6 (catalogs fcubs_serving_rw with FCUBS_GOLD and fcubs_serving with AIDP_AGENT)."
