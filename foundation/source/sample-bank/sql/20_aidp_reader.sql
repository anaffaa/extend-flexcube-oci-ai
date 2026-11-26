-- Phase 2.3: read-only user for the AI Data Platform external catalog. Run as ADMIN in FCUBSDEMO.
-- Replace the password, then Run Script.
CREATE USER AIDP_READER IDENTIFIED BY "TypeStrongPasswordHere";
GRANT CREATE SESSION TO AIDP_READER;
GRANT READ, WRITE ON DIRECTORY DATA_PUMP_DIR TO AIDP_READER;
BEGIN FOR t IN (SELECT table_name FROM all_tables WHERE owner = 'FCUBS') LOOP EXECUTE IMMEDIATE 'GRANT SELECT ON FCUBS.' || t.table_name || ' TO AIDP_READER'; END LOOP; END;
/
SELECT COUNT(*) AS fcubs_tables_granted FROM all_tab_privs WHERE grantee = 'AIDP_READER' AND table_schema = 'FCUBS';
