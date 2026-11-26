# 3. FLEXCUBE source patterns

AIDP reads FLEXCUBE through an **external catalog**: a JDBC connection from AIDP to an Oracle database, as a read-only user.
Whatever pattern you use, the rules are the same:

- Connect to a **copy**: Data Guard standby opened read-only, refreshable clone, GoldenGate replica or restored backup. Never
  the production primary.
- The copy must be **consistent at end of day** when the pipeline runs. Schedule after FLEXCUBE end of day and the copy's
  refresh or apply lag.
- The read-only user `AIDP_READER` gets SELECT on the 15 tables the foundation needs, nothing else
  ([`01_create_aidp_reader.sql`](../../foundation/source/own-flexcube/01_create_aidp_reader.sql)). Modules that need more tables
  list them in their README.
- Traffic stays private: AIDP private network access into the solution subnet, then routing to the copy.

| Pattern | Copy mechanism | Network path from AIDP | Typical lag | Good for |
|---|---|---|---|---|
| A. FLEXCUBE on OCI | Data Guard standby (Active Data Guard read-only) or Autonomous Database refreshable clone | Same VCN, or local or remote VCN peering through a DRG | Seconds (ADG) or the refresh interval (clone) | Banks already running FLEXCUBE on OCI |
| B. FLEXCUBE on premises | Oracle GoldenGate to a database on OCI, or Data Guard to OCI | FastConnect (or Site-to-Site VPN for pilots) to a DRG attached to the solution VCN | Seconds to minutes | Most existing FLEXCUBE estates |
| C. Exadata Cloud@Customer or Oracle Database@Azure | Data Guard standby or GoldenGate replica on the platform, or a copy on OCI | ExaCC: FastConnect from the data center; Database@Azure: OCI and Azure interconnect into the OCI VCN | Seconds to minutes | Data residency in the bank's data center, or Azure-hosted estates |
| D. Sample bank | None (synthetic data) | Public endpoint with allow list, or private endpoint in the solution subnet | n/a | Demos, workshops, development and CI |

## Pattern A: FLEXCUBE on OCI

1. Create the copy: an Active Data Guard standby (if FLEXCUBE runs on Base Database or Exadata Database Service), or a
   refreshable clone (if it runs on Autonomous Database), in a subnet reachable from the solution VCN.
2. Peer the networks: put the solution VCN and the FLEXCUBE VCN on the same DRG, or deploy the foundation into the FLEXCUBE
   VCN's compartment and reuse an existing private subnet.
3. Allow TCP 1521 (or 1522 for TLS) from the solution data subnet to the copy in its NSG or security list.
4. Run the reader and pre-check scripts on the **primary** (grants replicate to the standby) or on the clone.
5. In AIDP, create `fcubs_source` with private network access on the solution data subnet and the copy's service name.

## Pattern B: FLEXCUBE on premises

1. Connectivity: FastConnect to a DRG attached to the solution VCN; a Site-to-Site VPN is acceptable for a pilot. Add a route
   for the on-premises range in the solution route table (`foundation/terraform/network.tf` has a private route table to extend).
2. Copy: replicate the 15 tables (or the full FLEXCUBE schema) with Oracle GoldenGate into a database on OCI (an
   Autonomous AI Database or Base Database in the data subnet), or run a Data Guard standby on OCI. Replicating only the
   needed tables reduces data movement and exposure.
3. Run the reader and pre-check scripts on the OCI copy and connect `fcubs_source` to it. AIDP then reads inside OCI, and only
   the replication stream crosses the link.
4. Mask at the edge: apply GoldenGate column mapping or views to drop identifiers no module needs before data leaves the data
   center.

## Pattern C: Exadata Cloud@Customer or Oracle Database@Azure

- **Exadata Cloud@Customer.** The copy (a Data Guard standby or a GoldenGate target) can stay on the Cloud@Customer
  infrastructure. AIDP reaches it over FastConnect, as in pattern B. If the bank requires data to stay on premises, keep bronze
  minimal and review which silver and gold tables may persist on OCI; otherwise replicate to OCI as in pattern B.
- **Oracle Database@Azure.** The database runs in Azure data centers on OCI infrastructure, with its network in an OCI VCN.
  Attach that VCN and the solution VCN to a DRG (or deploy the foundation in the same OCI region and peer), allow the data
  subnet in the database NSG, and connect `fcubs_source` with private network access. Applications in Azure continue to use the
  database through the Azure network as before.

## Pattern D: sample bank

Terraform creates the database (`deploy_sample_source = true`) and the sample script loads it. For workshops a public endpoint
with `sample_db_allowed_cidrs` is simplest; for an environment that mirrors production, set `sample_db_private_endpoint = true`
and run the load script from a host in the VCN. The sample is the right source for development, CI and training in every
environment: it has planted scenarios and an answer key.

## Your own FLEXCUBE: what to adapt

1. **Pre-check** with [`02_precheck.sql`](../../foundation/source/own-flexcube/02_precheck.sql): table visibility, comments
   over 256 bytes (they break the catalog harvest; trim them on the copy, never in production), at least 13 months of
   `ACTB_HISTORY`, volumes, and your 25 most used transaction codes.
2. **Map transaction codes** and the other bank-specific settings in silver
   ([data foundation](04_data_foundation.md#bank-specific-settings)). This is the step that matters most.
3. **Set `SRC`** (`<catalog>.<schema>`) and `SOURCE_LABEL` in `fnd_01_bronze`, and `SRC` and `TOLERANCE` in
   `fnd_03_quality_checks`.
4. **Minimise personal data** (see [security and privacy](../path-to-production/01_security_and_privacy.md)): grant
   `AIDP_READER` on redacted views in a separate schema instead of base tables if the bank requires it. The notebooks only
   need the columns they select.
