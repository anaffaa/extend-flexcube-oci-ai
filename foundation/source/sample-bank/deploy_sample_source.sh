#!/usr/bin/env bash
# Path A: build the sample FLEXCUBE source database (synthetic data) in your OCI tenancy.
#
# What it does, in order (safe to re-run):
#   1. (optional) regenerates the synthetic data with the Python generator
#   2. creates a private Object Storage bucket and uploads the data and DDL files
#   3. creates an Autonomous AI Database (Transaction Processing, 2 ECPU, 20 GB) unless ADB_OCID is set
#   4. creates a short-lived read-only pre-authenticated request (PAR) on the bucket
#   5. builds schema FCUBS (34 tables, 43 foreign keys), loads the data and creates read-only user AIDP_READER
#      through the database's REST-enabled SQL endpoint
#   6. deletes the PAR
#
# Requirements: OCI CLI configured (oci setup config), bash, curl, python3. Run from the repository root:
#   cp foundation/source/sample-bank/deploy.env.example foundation/source/sample-bank/deploy.env   # edit it
#   bash foundation/source/sample-bank/deploy_sample_source.sh
# With the Terraform foundation, set FROM_TERRAFORM=true: the bucket, database and passwords come from its outputs
# and OCI Vault. Otherwise passwords are prompted. They are never stored or written to the repository.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE"                                  # sample-bank folder: data/, generator/, validation/, sql/
REPO="$(cd "$HERE/../../.." && pwd)"
ENV_FILE="${1:-$HERE/deploy.env}"
[ -f "$ENV_FILE" ] || { echo "Missing $ENV_FILE. Copy deploy.env.example to deploy.env next to this script and edit it."; exit 1; }
# shellcheck disable=SC1090
source "$ENV_FILE"
OCI="oci --profile ${OCI_PROFILE:-DEFAULT}"
# ---------- optional: take settings from the Terraform foundation ----------
if [ "${FROM_TERRAFORM:-false}" = "true" ]; then
  command -v terraform >/dev/null || { echo "FROM_TERRAFORM=true needs terraform on the PATH"; exit 1; }
  TF_JSON="$(terraform -chdir="${TF_DIR:-$REPO/foundation/terraform}" output -json)"
  tf() { printf '%s' "$TF_JSON" | python3 -c 'import json,sys; v=json.load(sys.stdin); k=sys.argv[1:]
o=v[k[0]]["value"]
for x in k[1:]: o=(o or {}).get(x)
print("" if o is None else o)' "$@"; }
  COMPARTMENT_OCID="$(tf compartment_id)"; BUCKET_NAME="$(tf staging_bucket)"; ADB_OCID="$(tf sample_source_db_id)"
  ADMIN_SECRET_OCID="$(tf secret_ids sample-db-admin)"; READER_SECRET_OCID="$(tf secret_ids aidp-reader)"
  [ -n "$ADB_OCID" ] || { echo "Terraform did not create the sample database (deploy_sample_source = false)."; exit 1; }
fi
: "${COMPARTMENT_OCID:?set COMPARTMENT_OCID in deploy.env}"
BUCKET_NAME="${BUCKET_NAME:-fcubs-demo-data}"
ADB_NAME="${ADB_NAME:-FCUBSDEMO}"
step() { printf '\n==> %s\n' "$*"; }

for cmd in oci curl python3; do command -v "$cmd" >/dev/null || { echo "Please install $cmd"; exit 1; }; done

# ---------- passwords (prompted, kept in memory only) ----------
ask_pw() {   # $1 = prompt; Oracle rules: 12 to 30 chars, upper, lower, digit, no double quote
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
secret() {   # $1 = Vault secret OCID; prints the decoded value
  $OCI secrets secret-bundle get --secret-id "$1" --query 'data."secret-bundle-content".content' --raw-output | base64 -d
}
if [ -n "${ADMIN_SECRET_OCID:-}" ]; then ADMIN_PW="$(secret "$ADMIN_SECRET_OCID")"; echo "ADMIN password read from OCI Vault"
else ADMIN_PW="$(ask_pw "ADMIN password for the database ${ADB_OCID:+(existing database)}")"; fi
if [ -n "${READER_SECRET_OCID:-}" ]; then READER_PW="$(secret "$READER_SECRET_OCID")"; echo "AIDP_READER password read from OCI Vault"
else READER_PW="$(ask_pw "Password for the read-only user AIDP_READER (used by the AIDP external catalog)")"; fi

# ---------- 1. sample data ----------
if [ "${REGENERATE:-false}" = "true" ]; then
  step "Regenerating synthetic FLEXCUBE data for ${CUSTOMERS:-2000} customers"
  python3 "$ROOT/generator/gen_data.py" --customers "${CUSTOMERS:-2000}" --out "$ROOT/data"
  mv -f "$ROOT/data/DEMO_SCENARIO_LABELS.csv.gz" "$ROOT/validation/DEMO_SCENARIO_LABELS.csv.gz"
  if python3 -c "import duckdb" 2>/dev/null; then python3 "$ROOT/generator/validate.py"; else echo "(skipping integrity checks: pip install duckdb to enable)"; fi
fi

# ---------- 2. bucket and upload ----------
NS="$($OCI os ns get --query data --raw-output)"
step "Bucket $BUCKET_NAME (namespace $NS)"
if ! $OCI os bucket get --bucket-name "$BUCKET_NAME" >/dev/null 2>&1; then
  $OCI os bucket create --compartment-id "$COMPARTMENT_OCID" --name "$BUCKET_NAME" --public-access-type NoPublicAccess >/dev/null
  echo "created (private)"
fi
step "Uploading data and DDL files"
$OCI os object bulk-upload --bucket-name "$BUCKET_NAME" --src-dir "$ROOT/data" --include "*.csv.gz" --overwrite >/dev/null
$OCI os object put --bucket-name "$BUCKET_NAME" --file "$ROOT/validation/DEMO_SCENARIO_LABELS.csv.gz" --name DEMO_SCENARIO_LABELS.csv.gz --force >/dev/null
for f in 01_create_tables.sql 03_constraints.sql; do
  $OCI os object put --bucket-name "$BUCKET_NAME" --file "$ROOT/sql/$f" --name "$f" --force >/dev/null
done
echo "uploaded $(ls "$ROOT"/data/*.csv.gz | wc -l | tr -d ' ') data files, the scenario labels and 2 DDL files"

# ---------- 3. Autonomous AI Database ----------
if [ -z "${ADB_OCID:-}" ]; then
  ADB_OCID="$($OCI db autonomous-database list --compartment-id "$COMPARTMENT_OCID" --display-name "$ADB_NAME" \
              --lifecycle-state AVAILABLE --query 'data[0].id' --raw-output 2>/dev/null || true)"
  [ "$ADB_OCID" = "null" ] && ADB_OCID=""
fi
if [ -z "${ADB_OCID:-}" ]; then
  step "Creating Autonomous AI Database $ADB_NAME (a few minutes)"
  ADB_OCID="$($OCI db autonomous-database create --compartment-id "$COMPARTMENT_OCID" \
      --db-name "$ADB_NAME" --display-name "$ADB_NAME" --db-workload OLTP \
      --compute-model ECPU --compute-count "${ADB_ECPU:-2}" --data-storage-size-in-gbs "${ADB_STORAGE_GB:-20}" \
      --is-auto-scaling-enabled false --is-auto-scaling-for-storage-enabled false \
      --admin-password "$ADMIN_PW" --wait-for-state AVAILABLE --query 'data.id' --raw-output)"
else
  step "Using existing database $ADB_OCID"
fi
ORDS_URL="$($OCI db autonomous-database get --autonomous-database-id "$ADB_OCID" --query 'data."connection-urls"."ords-url"' --raw-output)"
ORDS_URL="${ORDS_URL%/}"
echo "REST endpoint: $ORDS_URL"

# ---------- 4. temporary read-only link to the bucket ----------
step "Creating a 1-day read-only pre-authenticated request"
EXPIRES="$(python3 -c 'import datetime as d; print((d.datetime.now(d.timezone.utc)+d.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))')"
PAR_JSON="$($OCI os preauth-request create --bucket-name "$BUCKET_NAME" --name fcubs-load-read \
            --access-type AnyObjectRead --bucket-listing-action Deny --time-expires "$EXPIRES")"
PAR_ID="$(printf '%s' "$PAR_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["id"])')"
PAR_URL="$(printf '%s' "$PAR_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"].get("full-path") or "")')"
if [ -z "$PAR_URL" ]; then
  REGION="$($OCI iam region-subscription list --query 'data[?"is-home-region"]."region-name" | [0]' --raw-output)"
  ACCESS_URI="$(printf '%s' "$PAR_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["access-uri"])')"
  PAR_URL="https://objectstorage.${REGION}.oraclecloud.com${ACCESS_URI}"
fi
cleanup() { [ -n "${PAR_ID:-}" ] && $OCI os preauth-request delete --bucket-name "$BUCKET_NAME" --par-id "$PAR_ID" --force >/dev/null 2>&1 && echo "Pre-authenticated request deleted."; rm -f "${NETRC:-}"; }
trap cleanup EXIT

# ---------- 5. build schema, load data, create AIDP_READER ----------
NETRC="$(mktemp)"; chmod 600 "$NETRC"
HOST="$(printf '%s' "$ORDS_URL" | sed -E 's#https://([^/]+).*#\1#')"
printf 'machine %s login ADMIN password %s\n' "$HOST" "$ADMIN_PW" > "$NETRC"
run_sql() {   # $1 = file with the SQL script; prints DBMS_OUTPUT and fails on any error
  local out
  out="$(curl -sS --fail-with-body --netrc-file "$NETRC" -X POST "$ORDS_URL/admin/_/sql" \
         -H 'Content-Type: application/sql' --data-binary @"$1")" || { echo "$out" | head -c 2000; return 1; }
  printf '%s' "$out" | python3 -c '
import json, sys
r = json.load(sys.stdin); bad = 0
for it in r.get("items", []):
    if it.get("dbmsOutput"): print(it["dbmsOutput"].rstrip())
    if it.get("errorCode") or it.get("errorMessage"):
        bad += 1; print("ERROR:", it.get("errorCode"), it.get("errorMessage"), "|", (it.get("statementText") or "")[:120])
sys.exit(1 if bad else 0)'
}
step "Building schema FCUBS and loading data (about 2 minutes)"
TMP_SQL="$(mktemp)"
sed "s#PASTE_PAR_URL_HERE#${PAR_URL}#" "$ROOT/sql/10_build_from_bucket.sql" > "$TMP_SQL"
run_sql "$TMP_SQL"
step "Creating read-only user AIDP_READER"
cat > "$TMP_SQL" <<SQL
DECLARE
  e EXCEPTION; PRAGMA EXCEPTION_INIT(e, -1920);
BEGIN
  BEGIN EXECUTE IMMEDIATE 'CREATE USER AIDP_READER IDENTIFIED BY "${READER_PW}"';
  EXCEPTION WHEN e THEN EXECUTE IMMEDIATE 'ALTER USER AIDP_READER IDENTIFIED BY "${READER_PW}"'; END;
  EXECUTE IMMEDIATE 'GRANT CREATE SESSION TO AIDP_READER';
  EXECUTE IMMEDIATE 'GRANT READ, WRITE ON DIRECTORY DATA_PUMP_DIR TO AIDP_READER';
  FOR t IN (SELECT table_name FROM all_tables WHERE owner = 'FCUBS') LOOP
    EXECUTE IMMEDIATE 'GRANT SELECT ON FCUBS.' || t.table_name || ' TO AIDP_READER';
  END LOOP;
END;
/
SQL
run_sql "$TMP_SQL"
rm -f "$TMP_SQL"
cat > "$NETRC.q" <<'SQL'
SELECT COUNT(*) AS fcubs_tables, (SELECT COUNT(*) FROM FCUBS.STTM_CUSTOMER) AS customers,
       (SELECT COUNT(*) FROM all_tab_privs WHERE grantee = 'AIDP_READER' AND table_schema = 'FCUBS') AS reader_grants
FROM all_tables WHERE owner = 'FCUBS';
SQL
curl -sS --netrc-file "$NETRC" -X POST "$ORDS_URL/admin/_/sql" -H 'Content-Type: application/sql' --data-binary @"$NETRC.q" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); print("Check:", r["items"][0]["resultSet"]["items"][0])'
rm -f "$NETRC.q"

step "Done. Sample FLEXCUBE source is ready."
cat <<EOF
Database OCID : $ADB_OCID
Schema        : FCUBS (34 tables), answer key in DEMOMETA (never granted to AIDP)
AIDP user     : AIDP_READER (read-only; password from OCI Vault or the one you typed)

Next: docs/foundation/02_deploy.md, step 4 (external catalog fcubs_source on this database with AIDP_READER).
Tip: stop the database between sessions to save cost: oci db autonomous-database stop --autonomous-database-id $ADB_OCID
EOF
