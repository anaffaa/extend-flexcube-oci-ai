-- Extend FLEXCUBE on OCI | Use case 01 cash-flow intelligence: serving tables in the AIDP 26ai Lakehouse.
-- Run as ADMIN in the Lakehouse after foundation/serving/sql/00_serving_users.sql (deploy_serving_layer.sh does both).
-- Spark cannot run DDL through external catalogs, so tables exist before the publish notebook writes to them.

CREATE TABLE FCUBS_GOLD.EARLY_WARNING (
  AS_OF_DATE           DATE         NOT NULL,
  CUSTOMER_NO          VARCHAR2(9)  NOT NULL,
  CUSTOMER_NAME        VARCHAR2(200),
  CUSTOMER_TYPE        VARCHAR2(1),
  SEGMENT              VARCHAR2(20),
  HOME_BRANCH          VARCHAR2(3),
  RM_ID                VARCHAR2(10),
  EWS_SCORE            NUMBER(3),
  RISK_BAND            VARCHAR2(10),
  SIGNAL_TYPE          VARCHAR2(20),
  EWS_REASONS          VARCHAR2(1000),
  HAS_CREDIT_EXPOSURE  VARCHAR2(1),
  ACTIVE_LOANS         NUMBER(5),
  TOTAL_EMI_AED        NUMBER(18,2),
  MAX_DPD              NUMBER(6),
  OVERDUE_AMOUNT_AED   NUMBER(18,2),
  DAYS_SINCE_SALARY    NUMBER(6),
  SALARY_CHANGE_PCT    NUMBER(9,1),
  INFLOW_CHANGE_PCT    NUMBER(9,1),
  BALANCE_CHANGE_PCT   NUMBER(9,1),
  DEBT_BURDEN_RATIO    NUMBER(9,3),
  CONSTRAINT PK_EWS PRIMARY KEY (AS_OF_DATE, CUSTOMER_NO));
COMMENT ON TABLE FCUBS_GOLD.EARLY_WARNING IS 'Early-warning score per customer per run (as_of_date): 0 to 100 score, HIGH/MEDIUM/LOW band, CREDIT_STRESS or ATTRITION, plain-language reasons. Source: fcubs_lake.gold_cashflow.early_warning.';

CREATE TABLE FCUBS_GOLD.COLLECTIONS_PRIORITY (
  AS_OF_DATE               DATE         NOT NULL,
  LOAN_NO                  VARCHAR2(20) NOT NULL,
  PRIORITY_RANK            NUMBER(6),
  CUSTOMER_NO              VARCHAR2(9),
  CUSTOMER_NAME            VARCHAR2(200),
  SEGMENT                  VARCHAR2(20),
  RM_ID                    VARCHAR2(10),
  PRODUCT_CODE             VARCHAR2(10),
  DAYS_PAST_DUE            NUMBER(6),
  DPD_BUCKET               VARCHAR2(12),
  EMI_AED                  NUMBER(18,2),
  OVERDUE_AMOUNT_AED       NUMBER(18,2),
  NEXT_DUE_DATE            DATE,
  REPAYMENT_AC_BALANCE_AED NUMBER(18,2),
  SHORTFALL_AED            NUMBER(18,2),
  EWS_SCORE                NUMBER(3),
  RISK_BAND                VARCHAR2(10),
  EWS_REASONS              VARCHAR2(1000),
  RECOMMENDED_ACTION       VARCHAR2(200),
  CONSTRAINT PK_COLL PRIMARY KEY (AS_OF_DATE, LOAN_NO));
COMMENT ON TABLE FCUBS_GOLD.COLLECTIONS_PRIORITY IS 'Ranked collections worklist per run: DPD, EMI shortfall versus repayment account, early-warning score and recommended next action. Source: fcubs_lake.gold_cashflow.collections_priority.';

CREATE TABLE FCUBS_GOLD.SME_CASHFLOW (
  CUSTOMER_NO           VARCHAR2(9)  NOT NULL,
  MONTH_START           DATE         NOT NULL,
  CUSTOMER_NAME         VARCHAR2(200),
  BUSINESS_DESCRIPTION  VARCHAR2(200),
  RM_ID                 VARCHAR2(10),
  RECEIPTS_AED          NUMBER(18,2),
  PAYMENTS_AED          NUMBER(18,2),
  PAYROLL_PAID_AED      NUMBER(18,2),
  NET_CASHFLOW_AED      NUMBER(18,2),
  MONTH_END_BALANCE_AED NUMBER(18,2),
  RECEIPTS_3M_AVG       NUMBER(18,2),
  NET_BURN_3M_AVG       NUMBER(18,2),
  RUNWAY_MONTHS         NUMBER(9,1),
  CONSTRAINT PK_SME PRIMARY KEY (CUSTOMER_NO, MONTH_START));
COMMENT ON TABLE FCUBS_GOLD.SME_CASHFLOW IS 'Monthly cash flow per SME and corporate customer: receipts, payments, payroll, balance, 3-month averages and cash runway. Source: fcubs_lake.gold_cashflow.sme_cashflow.';

GRANT SELECT ON FCUBS_GOLD.EARLY_WARNING TO AIDP_AGENT;
GRANT SELECT ON FCUBS_GOLD.COLLECTIONS_PRIORITY TO AIDP_AGENT;
GRANT SELECT ON FCUBS_GOLD.SME_CASHFLOW TO AIDP_AGENT;

SELECT table_name FROM all_tables WHERE owner = 'FCUBS_GOLD' ORDER BY 1;

CREATE TABLE FCUBS_GOLD.ML_EARLY_WARNING (
  AS_OF_DATE         DATE         NOT NULL,
  CUSTOMER_NO        VARCHAR2(9)  NOT NULL,
  RM_ID              VARCHAR2(10),
  SEGMENT            VARCHAR2(20),
  P_ARREARS_90D      NUMBER(6,4),
  ML_ARREARS_BAND    VARCHAR2(10),
  P_ATTRITION_90D    NUMBER(6,4),
  ML_ATTRITION_BAND  VARCHAR2(10),
  RULES_BAND         VARCHAR2(10),
  RULES_SIGNAL       VARCHAR2(20),
  ML_ONLY_FLAG       VARCHAR2(1),
  ARREARS_RUN_ID     VARCHAR2(64),
  ATTRITION_RUN_ID   VARCHAR2(64),
  ML_DRIVERS         VARCHAR2(600),
  CONSTRAINT PK_ML_EWS PRIMARY KEY (AS_OF_DATE, CUSTOMER_NO));
COMMENT ON TABLE FCUBS_GOLD.ML_EARLY_WARNING IS 'ML probabilities per customer per run: 30+ DPD arrears and balance drain in the next 90 days (registered models fcubs_ews_arrears_90d and fcubs_ews_attrition_90d), with the rules result side by side. Source: fcubs_lake.gold_cashflow.ml_early_warning.';

GRANT SELECT ON FCUBS_GOLD.ML_EARLY_WARNING TO AIDP_AGENT;

SELECT table_name FROM all_tables WHERE owner = 'FCUBS_GOLD' ORDER BY 1;
