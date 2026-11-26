-- Extend FLEXCUBE on OCI | Foundation: governed serving layer in the AIDP 26ai Lakehouse.
-- Two users keep it least-privilege: FCUBS_GOLD owns and writes the serving tables (publish notebooks only),
-- AIDP_AGENT can only read them (agents, BI, apps). Each use-case module adds its own tables in its sql/ folder.
-- Run as ADMIN in the Lakehouse (not the FLEXCUBE source). deploy_serving_layer.sh fills the password placeholders.

-- Publisher: owns the tables; AIDP notebooks write here through catalog fcubs_serving_rw.
CREATE USER FCUBS_GOLD IDENTIFIED BY "<FCUBS_GOLD_PASSWORD>" DEFAULT TABLESPACE DATA QUOTA UNLIMITED ON DATA;
GRANT CREATE SESSION, DWROLE TO FCUBS_GOLD;
GRANT READ, WRITE ON DIRECTORY DATA_PUMP_DIR TO FCUBS_GOLD;

-- Agent reader: read-only; the agent's SQL tools use catalog fcubs_serving.
CREATE USER AIDP_AGENT IDENTIFIED BY "<AIDP_AGENT_PASSWORD>";
GRANT CREATE SESSION TO AIDP_AGENT;
GRANT READ, WRITE ON DIRECTORY DATA_PUMP_DIR TO AIDP_AGENT;
