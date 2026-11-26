"""Local integrity checks on the generated CSVs before loading to Oracle (uses DuckDB)."""
import duckdb, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'data'))
META = json.load(open(os.path.join(HERE, 'columns.json')))
con = duckdb.connect()
fails = 0


def check(name, sql, expect_zero=True):
    global fails
    v = con.execute(sql).fetchone()[0]
    ok = (v == 0) if expect_zero else bool(v)
    fails += 0 if ok else 1
    print(f'{"PASS" if ok else "FAIL"}  {name}: {v}')


for t in META:
    p = os.path.join(DATA, f'{t}.csv.gz')
    con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_csv('{p}', header=true, all_varchar=true)")
print('Row counts:')
for t in META:
    print(f'  {t:30} {con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]:>9,}')

print('\nPrimary keys')
for t, m in META.items():
    if m['pk']:
        cols = ', '.join(m['pk'])
        check(f'{t} PK unique', f'SELECT count(*) FROM (SELECT {cols} FROM {t} GROUP BY ALL HAVING count(*) > 1)')
        check(f'{t} PK not null', f"SELECT count(*) FROM {t} WHERE " + ' OR '.join(f'{c} IS NULL' for c in m['pk']))

print('\nForeign keys (from 03_constraints.sql)')
fk_re = re.compile(r'ALTER TABLE (\w+) ADD CONSTRAINT (\w+) FOREIGN KEY \(([^)]*)\) REFERENCES (\w+) \(([^)]*)\)')
for line in open(os.path.join(HERE, '..', 'sql', '03_constraints.sql')):
    m = fk_re.search(line)
    if not m:
        continue
    t, name, fc, rt, rc = m.groups()
    fc, rc = [x.strip() for x in fc.split(',')], [x.strip() for x in rc.split(',')]
    present = {r[0] for r in con.execute(f'DESCRIBE {t}').fetchall()}
    if not set(fc) <= present:
        print(f'SKIP  {name} {t}->{rt}: column not populated (all NULL)')
        continue
    on = ' AND '.join(f'c.{a} = p.{b}' for a, b in zip(fc, rc))
    notnull = ' AND '.join(f'c.{a} IS NOT NULL' for a in fc)
    check(f'{name} {t}->{rt}', f'SELECT count(*) FROM {t} c LEFT JOIN {rt} p ON {on} WHERE {notnull} AND p.{rc[0]} IS NULL')

print('\nAccounting')
for t in ('ACTB_HISTORY', 'ACTB_DAILY_LOG'):
    check(f'{t} every TRN_REF_NO balances in LCY', f"""
        SELECT count(*) FROM (SELECT TRN_REF_NO, EVENT_SR_NO,
            round(sum(CASE WHEN DRCR_IND='D' THEN CAST(LCY_AMOUNT AS DOUBLE) ELSE -CAST(LCY_AMOUNT AS DOUBLE) END), 2) d
            FROM {t} GROUP BY ALL HAVING abs(d) > 0.05)""")
check('AC_ENTRY_SR_NO unique across history and daily log', """
    SELECT count(*) - count(DISTINCT AC_ENTRY_SR_NO) FROM
    (SELECT AC_ENTRY_SR_NO FROM ACTB_HISTORY UNION ALL SELECT AC_ENTRY_SR_NO FROM ACTB_DAILY_LOG)""")
check('Customer legs reference existing accounts', """
    SELECT count(*) FROM ACTB_HISTORY h LEFT JOIN STTM_CUST_ACCOUNT a ON h.AC_NO = a.CUST_AC_NO
    WHERE h.CUST_GL = 'A' AND a.CUST_AC_NO IS NULL""")
check('GL legs reference existing GLs', """
    SELECT count(*) FROM ACTB_HISTORY h LEFT JOIN GLTM_GLMASTER g ON h.AC_NO = g.GL_CODE
    WHERE h.CUST_GL = 'G' AND g.GL_CODE IS NULL""")
check('Daily balance history closes equal next day opening', """
    SELECT count(*) FROM (SELECT ACCOUNT, BKG_DATE, CAST(ACY_OPENING_BAL AS DOUBLE) o,
        lag(CAST(ACY_CLOSING_BAL AS DOUBLE)) OVER (PARTITION BY ACCOUNT ORDER BY BKG_DATE) pc FROM ACTB_ACCBAL_HISTORY)
    WHERE pc IS NOT NULL AND abs(o - pc) > 0.01""")
check('Balance history movement equals accounting entries', """
    WITH e AS (SELECT AC_NO, sum(CASE WHEN DRCR_IND='C' THEN 1 ELSE -1 END *
                  CAST(coalesce(FCY_AMOUNT, LCY_AMOUNT) AS DOUBLE)) net FROM ACTB_HISTORY WHERE CUST_GL='A' GROUP BY 1),
         b AS (SELECT ACCOUNT, sum(CAST(ACY_CR_TUR AS DOUBLE) - CAST(ACY_DR_TUR AS DOUBLE)) net FROM ACTB_ACCBAL_HISTORY GROUP BY 1)
    SELECT count(*) FROM e FULL JOIN b ON e.AC_NO = b.ACCOUNT WHERE abs(coalesce(e.net,0) - coalesce(b.net,0)) > 0.05""")
check('Current balance equals today opening plus today movement', """
    SELECT count(*) FROM STTM_CUST_ACCOUNT WHERE abs(CAST(ACY_CURR_BALANCE AS DOUBLE) -
      (CAST(ACY_OPENING_BAL AS DOUBLE) + CAST(ACY_TODAY_TOVER_CR AS DOUBLE) - CAST(ACY_TODAY_TOVER_DR AS DOUBLE))) > 0.05""")
check('No individual account below zero', """
    SELECT count(*) FROM STTM_CUST_ACCOUNT a JOIN STTM_CUSTOMER c ON a.CUST_NO = c.CUSTOMER_NO
    WHERE c.CUSTOMER_TYPE = 'I' AND CAST(a.ACY_CURR_BALANCE AS DOUBLE) < -0.01""")
check('Corporate accounts within overdraft limit', """
    SELECT count(*) FROM STTM_CUST_ACCOUNT WHERE CAST(ACY_CURR_BALANCE AS DOUBLE) < -coalesce(CAST(TOD_LIMIT AS DOUBLE),0) - 0.01""",
      )
check('Closed accounts have zero balance', """
    SELECT count(*) FROM STTM_CUST_ACCOUNT WHERE RECORD_STAT = 'C' AND abs(CAST(ACY_CURR_BALANCE AS DOUBLE)) > 0.01""")
check('Card settlements match card postings', """
    SELECT count(*) FROM SWTB_SETTLEMENT_HIST s LEFT JOIN ACTB_HISTORY h ON h.EXTERNAL_REF_NO = s.EXTERNAL_REF_NO AND h.CUST_GL='A'
    WHERE s.STATUS = 'S' AND s.TXN_DATE < '2026-10-21' AND h.TRN_REF_NO IS NULL""")

print('\nLending')
check('Schedule principal adds up to amount financed', """
    SELECT count(*) FROM (SELECT ACCOUNT_NUMBER, sum(CAST(AMOUNT_DUE AS DOUBLE)) p FROM CLTB_ACCOUNT_SCHEDULES
      WHERE COMPONENT_NAME = 'PRINCIPAL' GROUP BY 1) s JOIN CLTB_ACCOUNT_APPS_MASTER m USING (ACCOUNT_NUMBER)
    WHERE abs(s.p - CAST(m.AMOUNT_FINANCED AS DOUBLE)) > 1""")
check('Schedule rows unique per due date and component', """
    SELECT count(*) FROM (SELECT ACCOUNT_NUMBER, COMPONENT_NAME, SCHEDULE_DUE_DATE FROM CLTB_ACCOUNT_SCHEDULES GROUP BY ALL HAVING count(*) > 1)""")
check('Every repayment in the window has an accounting entry', """
    SELECT count(*) FROM CLTB_AMOUNT_PAID p LEFT JOIN (SELECT DISTINCT RELATED_REFERENCE, TRN_DT FROM ACTB_HISTORY
      WHERE TRN_CODE='LNR' AND CUST_GL='A') h ON h.RELATED_REFERENCE = p.ACCOUNT_NUMBER AND h.TRN_DT = p.PAID_DATE
    WHERE p.PAID_DATE >= '2025-10-01' AND p.PAID_DATE < '2026-10-21' AND h.TRN_DT IS NULL""")

print('\nProfile')
for label, sql in [
    ('Loans by status', "SELECT USER_DEFINED_STATUS, count(*) FROM CLTB_ACCOUNT_APPS_MASTER GROUP BY 1 ORDER BY 1"),
    ('Loans by product', "SELECT PRODUCT_CODE, count(*), round(sum(CAST(AMOUNT_FINANCED AS DOUBLE))/1e6,1) AS aed_m FROM CLTB_ACCOUNT_APPS_MASTER GROUP BY 1 ORDER BY 1"),
    ('Customers by type and category', "SELECT CUSTOMER_TYPE, CUSTOMER_CATEGORY, count(*) FROM STTM_CUSTOMER GROUP BY ALL ORDER BY 1,2"),
    ('Accounts by class and state', "SELECT ACCOUNT_CLASS, RECORD_STAT, AC_STAT_DORMANT, count(*), round(sum(CAST(LCY_CURR_BALANCE AS DOUBLE))/1e6,1) aed_m FROM STTM_CUST_ACCOUNT GROUP BY ALL ORDER BY 1,2,3"),
    ('KYC risk levels', "SELECT KYC_CUST_TYPE, RISK_LEVEL, count(*) FROM STTM_KYC_MASTER GROUP BY ALL ORDER BY 1,2"),
    ('Monthly transaction volume', "SELECT substr(TRN_DT,1,7) m, count(DISTINCT TRN_REF_NO) txns, round(sum(CASE WHEN CUST_GL='A' AND DRCR_IND='C' THEN CAST(LCY_AMOUNT AS DOUBLE) END)/1e6,1) credits_aed_m FROM ACTB_HISTORY GROUP BY 1 ORDER BY 1"),
]:
    print(f'  {label}:')
    for r in con.execute(sql).fetchall():
        print('    ', r)
print(f'\n{"ALL CHECKS PASSED" if not fails else f"{fails} CHECK(S) FAILED"}')
sys.exit(1 if fails else 0)
