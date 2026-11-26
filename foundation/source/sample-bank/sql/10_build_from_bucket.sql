-- FCUBS demo: one-shot build. Run as ADMIN in Database Actions > SQL ("Run Script", F5).
-- Paste the bucket pre-authenticated request URL (ends with /o/) in place of PASTE_PAR_URL_HERE.
-- Safe to re-run: existing users, tables and constraints are skipped; data is truncated and reloaded.
SET SERVEROUTPUT ON SIZE UNLIMITED
DECLARE
  l_base VARCHAR2(4000) := 'PASTE_PAR_URL_HERE';
  TYPE t_tabs IS TABLE OF VARCHAR2(128);
  l_tabs t_tabs := t_tabs('STTM_BANK', 'STTM_BRANCH', 'STTM_COUNTRY', 'CYTM_CCY_DEFN_MASTER', 'CYTM_RATES_MASTER', 'STTM_CUSTOMER_CAT', 'STTM_ACCOUNT_CLASS', 'STTM_TRN_CODE', 'GLTM_GLMASTER', 'CLTM_PRODUCT', 'STTM_CUSTOMER', 'STTM_CUST_PERSONAL', 'STTM_CUST_CORPORATE', 'STTM_CUST_DOMESTIC', 'STTM_KYC_MASTER', 'STTM_KYC_RETAIL', 'STTM_CREDIT_SCORE_GRADE', 'STTM_CUST_ACCOUNT', 'STTM_ACCOUNT_BALANCE', 'ACTB_ACCBAL_HISTORY', 'STTM_CUST_ACCOUNT_DORMANCY', 'STTM_DEBIT_CARD_MASTER', 'ACTB_DAILY_LOG', 'ACTB_HISTORY', 'FTTB_CONTRACT_MASTER', 'SWTB_SETTLEMENT_HIST', 'CSTB_AML_DAILY_TOV', 'CLTB_ACCOUNT_APPS_MASTER', 'CLTB_ACCOUNT_COMPONENTS', 'CLTB_ACCOUNT_SCHEDULES', 'CLTB_AMOUNT_PAID', 'CLTB_ACCOUNT_UDE_VALUES', 'CLTB_ACCOUNT_CREDIT_SCORE', 'CLTB_ACC_GUARANTOR_CUSTOMER');
  l_fmt  CLOB := '{"type":"csv","skipheaders":1,"compression":"gzip","dateformat":"YYYY-MM-DD HH24:MI:SS",'
              || '"timestampformat":"YYYY-MM-DD HH24:MI:SS.FF6","blankasnull":true,"rejectlimit":0,"ignoremissingcolumns":true}';
  l_n    NUMBER;

  PROCEDURE ddl(p VARCHAR2) IS
  BEGIN
    EXECUTE IMMEDIATE p;
  EXCEPTION WHEN OTHERS THEN
    IF SQLCODE NOT IN (-955, -1920, -2275, -2260, -1430, -1442) THEN RAISE; END IF;
  END;

  PROCEDURE run_file(p_name VARCHAR2) IS
    l_blob BLOB; l_clob CLOB; l_pos INTEGER := 1; l_end INTEGER; l_stmt VARCHAR2(32767); l_cnt INTEGER := 0;
    l_d INTEGER := 1; l_s INTEGER := 1; l_c INTEGER := 0; l_w INTEGER;
  BEGIN
    l_blob := DBMS_CLOUD.GET_OBJECT(credential_name => NULL, object_uri => l_base || p_name);
    DBMS_LOB.CREATETEMPORARY(l_clob, TRUE);
    DBMS_LOB.CONVERTTOCLOB(l_clob, l_blob, DBMS_LOB.LOBMAXSIZE, l_d, l_s, DBMS_LOB.DEFAULT_CSID, l_c, l_w);
    LOOP
      l_end := DBMS_LOB.INSTR(l_clob, ';' || CHR(10), l_pos);
      EXIT WHEN l_end = 0 OR l_end IS NULL;
      l_stmt := DBMS_LOB.SUBSTR(l_clob, l_end - l_pos, l_pos);
      l_pos := l_end + 2;
      LOOP   -- drop leading blank and comment lines
        l_stmt := LTRIM(l_stmt, ' ' || CHR(10) || CHR(13));
        EXIT WHEN SUBSTR(l_stmt, 1, 2) <> '--' OR l_stmt IS NULL;
        l_stmt := SUBSTR(l_stmt, INSTR(l_stmt || CHR(10), CHR(10)) + 1);
      END LOOP;
      IF l_stmt IS NOT NULL AND UPPER(l_stmt) NOT LIKE 'ALTER SESSION%' THEN
        ddl(l_stmt);
        l_cnt := l_cnt + 1;
      END IF;
    END LOOP;
    DBMS_OUTPUT.PUT_LINE(p_name || ': ' || l_cnt || ' statements');
  END;
BEGIN
  IF l_base NOT LIKE 'https://%/o/' THEN
    RAISE_APPLICATION_ERROR(-20001, 'Paste the bucket pre-authenticated request URL (ending in /o/) first.');
  END IF;
  -- 1. schemas (schema-only accounts, nobody logs in as them)
  ddl('CREATE USER FCUBS NO AUTHENTICATION DEFAULT TABLESPACE DATA QUOTA UNLIMITED ON DATA');
  ddl('CREATE USER DEMOMETA NO AUTHENTICATION DEFAULT TABLESPACE DATA QUOTA UNLIMITED ON DATA');
  ddl('CREATE TABLE DEMOMETA.DEMO_SCENARIO_LABELS (CUSTOMER_NO VARCHAR2(9), CUST_AC_NO VARCHAR2(20), '
      || 'SCENARIO VARCHAR2(40), START_DATE DATE, END_DATE DATE, NOTES VARCHAR2(400))');
  -- 2. FLEXCUBE-style tables and primary keys
  EXECUTE IMMEDIATE 'ALTER SESSION SET CURRENT_SCHEMA = FCUBS';
  run_file('01_create_tables.sql');
  EXECUTE IMMEDIATE 'ALTER SESSION SET CURRENT_SCHEMA = ADMIN';
  -- 3. data
  FOR c IN (SELECT table_name, constraint_name FROM all_constraints
             WHERE owner = 'FCUBS' AND constraint_type = 'R' AND status = 'ENABLED') LOOP
    EXECUTE IMMEDIATE 'ALTER TABLE FCUBS.' || c.table_name || ' DISABLE CONSTRAINT ' || c.constraint_name;
  END LOOP;
  FOR i IN 1 .. l_tabs.COUNT LOOP
    EXECUTE IMMEDIATE 'TRUNCATE TABLE FCUBS.' || l_tabs(i);
    DBMS_CLOUD.COPY_DATA(table_name => l_tabs(i), schema_name => 'FCUBS', credential_name => NULL,
                         file_uri_list => l_base || l_tabs(i) || '.csv.gz', format => l_fmt);
    EXECUTE IMMEDIATE 'SELECT COUNT(*) FROM FCUBS.' || l_tabs(i) INTO l_n;
    DBMS_OUTPUT.PUT_LINE(RPAD(l_tabs(i), 32) || TO_CHAR(l_n, '999,999,990'));
  END LOOP;
  EXECUTE IMMEDIATE 'TRUNCATE TABLE DEMOMETA.DEMO_SCENARIO_LABELS';
  DBMS_CLOUD.COPY_DATA(table_name => 'DEMO_SCENARIO_LABELS', schema_name => 'DEMOMETA', credential_name => NULL,
                       file_uri_list => l_base || 'DEMO_SCENARIO_LABELS.csv.gz', format => l_fmt);
  -- 4. foreign keys (created once, re-enabled on reloads)
  EXECUTE IMMEDIATE 'ALTER SESSION SET CURRENT_SCHEMA = FCUBS';
  run_file('03_constraints.sql');
  EXECUTE IMMEDIATE 'ALTER SESSION SET CURRENT_SCHEMA = ADMIN';
  FOR c IN (SELECT table_name, constraint_name FROM all_constraints
             WHERE owner = 'FCUBS' AND constraint_type = 'R' AND status = 'DISABLED') LOOP
    EXECUTE IMMEDIATE 'ALTER TABLE FCUBS.' || c.table_name || ' ENABLE CONSTRAINT ' || c.constraint_name;
  END LOOP;
  DBMS_STATS.GATHER_SCHEMA_STATS('FCUBS');
  DBMS_OUTPUT.PUT_LINE('FCUBS build complete.');
END;
/
