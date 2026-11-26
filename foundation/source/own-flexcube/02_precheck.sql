-- Path B pre-check: run as AIDP_READER (or a DBA) on your FLEXCUBE copy before connecting AIDP.
-- Every line should say OK. Fix anything marked CHECK before running the pipeline.
DEFINE fcubs_schema = 'FCUBS'
SET LINESIZE 200 PAGESIZE 100
COLUMN check_name FORMAT A55
COLUMN result FORMAT A10
COLUMN detail FORMAT A90

WITH req AS (
  SELECT column_value AS table_name FROM TABLE(sys.odcivarchar2list(
    'STTM_CUSTOMER', 'STTM_CUST_PERSONAL', 'STTM_CUST_CORPORATE', 'STTM_KYC_MASTER',
    'STTM_CREDIT_SCORE_GRADE', 'STTM_CUST_ACCOUNT', 'STTM_ACCOUNT_CLASS', 'ACTB_ACCBAL_HISTORY',
    'ACTB_HISTORY', 'STTM_TRN_CODE', 'SWTB_SETTLEMENT_HIST', 'CLTB_ACCOUNT_APPS_MASTER',
    'CLTB_ACCOUNT_SCHEDULES', 'CLTB_AMOUNT_PAID', 'CLTB_ACCOUNT_UDE_VALUES'))
)
-- 1. all 15 tables visible to this user
SELECT '1. required tables visible: ' || r.table_name AS check_name,
       CASE WHEN t.table_name IS NOT NULL THEN 'OK' ELSE 'CHECK' END AS result,
       CASE WHEN t.table_name IS NULL THEN 'missing or not granted' END AS detail
  FROM req r LEFT JOIN all_tables t ON t.owner = UPPER('&fcubs_schema') AND t.table_name = r.table_name
UNION ALL
-- 2. comments longer than 256 bytes break the AIDP external catalog harvest
SELECT '2. column comments within 256 bytes',
       CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'CHECK' END,
       COUNT(*) || ' column comments over 256 bytes (trim them on the copy, see docs/path-to-production/05_operations.md)'
  FROM all_col_comments c JOIN req r ON c.table_name = r.table_name
 WHERE c.owner = UPPER('&fcubs_schema') AND LENGTHB(c.comments) > 256
UNION ALL
SELECT '2. table comments within 256 bytes',
       CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'CHECK' END,
       COUNT(*) || ' table comments over 256 bytes'
  FROM all_tab_comments c JOIN req r ON c.table_name = r.table_name
 WHERE c.owner = UPPER('&fcubs_schema') AND LENGTHB(c.comments) > 256;

-- 3. history depth: gold and ML need at least 13 months of postings ending near today
SELECT '3. ACTB_HISTORY covers 13+ months' AS check_name,
       CASE WHEN MONTHS_BETWEEN(MAX(trn_dt), MIN(trn_dt)) >= 13 THEN 'OK' ELSE 'CHECK' END AS result,
       'from ' || TO_CHAR(MIN(trn_dt), 'YYYY-MM-DD') || ' to ' || TO_CHAR(MAX(trn_dt), 'YYYY-MM-DD')
       || '; as-of date used by the notebooks = ' || TO_CHAR(MAX(trn_dt) + 1, 'YYYY-MM-DD') AS detail
  FROM "&fcubs_schema".actb_history;

-- 4. volumes, to size the Spark cluster (bronze copies these tables daily)
SELECT '4. rows in ' || table_name AS check_name, 'INFO' AS result, TO_CHAR(num_rows, '999,999,999,990') || ' (from statistics)' AS detail
  FROM all_tables
 WHERE owner = UPPER('&fcubs_schema')
   AND table_name IN ('ACTB_HISTORY', 'ACTB_ACCBAL_HISTORY', 'SWTB_SETTLEMENT_HIST', 'STTM_CUSTOMER', 'STTM_CUST_ACCOUNT')
 ORDER BY num_rows DESC NULLS LAST;

-- 5. transaction codes: silver maps FLEXCUBE TRN_CODEs into 12 business categories.
--    Codes not in the mapping fall into "other". Review the top unmapped codes and extend
--    the `category` mapping (TRN_CODE to category) in notebook fnd_02_silver (foundation/lakehouse/notebooks/src/fnd_02_silver.py) for your bank.
SELECT '5. top transaction codes (last 90 days)' AS check_name, trn_code AS result,
       TO_CHAR(COUNT(*), '999,999,990') || ' customer entries' AS detail
  FROM "&fcubs_schema".actb_history
 WHERE cust_gl = 'A' AND trn_dt >= (SELECT MAX(trn_dt) - 90 FROM "&fcubs_schema".actb_history)
 GROUP BY trn_code ORDER BY COUNT(*) DESC FETCH FIRST 25 ROWS ONLY;
