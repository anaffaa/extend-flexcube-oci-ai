-- Path B: your own FLEXCUBE. Creates a least-privilege, read-only user for the AIDP external catalog.
-- Run as a DBA on a COPY of FLEXCUBE (replica, standby open read-only via a separate PDB, or a refreshed clone),
-- never on the production primary. Works in SQL*Plus, SQLcl and SQL Developer.
--
-- It grants SELECT on only the 15 tables this solution reads. Nothing is created in the FLEXCUBE schema.
DEFINE fcubs_schema = 'FCUBS'                 -- your FLEXCUBE application schema owner
DEFINE reader_pw    = 'ChangeMe_Strong#2026'  -- replace; 12+ chars, upper, lower, digit

CREATE USER AIDP_READER IDENTIFIED BY "&reader_pw";
GRANT CREATE SESSION TO AIDP_READER;

BEGIN
  FOR t IN (SELECT column_value AS table_name FROM TABLE(sys.odcivarchar2list(
              'STTM_CUSTOMER', 'STTM_CUST_PERSONAL', 'STTM_CUST_CORPORATE', 'STTM_KYC_MASTER',
              'STTM_CREDIT_SCORE_GRADE', 'STTM_CUST_ACCOUNT', 'STTM_ACCOUNT_CLASS', 'ACTB_ACCBAL_HISTORY',
              'ACTB_HISTORY', 'STTM_TRN_CODE', 'SWTB_SETTLEMENT_HIST', 'CLTB_ACCOUNT_APPS_MASTER',
              'CLTB_ACCOUNT_SCHEDULES', 'CLTB_AMOUNT_PAID', 'CLTB_ACCOUNT_UDE_VALUES'))) LOOP
    EXECUTE IMMEDIATE 'GRANT SELECT ON "&fcubs_schema".' || t.table_name || ' TO AIDP_READER';
  END LOOP;
END;
/

-- Expected: 15
SELECT COUNT(*) AS tables_granted FROM dba_tab_privs
 WHERE grantee = 'AIDP_READER' AND owner = UPPER('&fcubs_schema') AND privilege = 'SELECT';

-- Optional, recommended on a real bank: mask or exclude personal data before AIDP sees it,
-- for example with Oracle Data Redaction on name, address and ID columns, or by exposing views
-- in a separate schema instead of the base tables. Card numbers, IBANs and national IDs are not needed.
