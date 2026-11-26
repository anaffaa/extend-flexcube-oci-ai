# Use case 03: FLEXCUBE data copilot

**Status:** design (not yet built). **Builds on:** the shared foundation and the semantic descriptions of silver and gold.
**Business owners:** business analysts, MIS and regulatory reporting teams, product managers.

## Problem

Simple business questions ("how many SME customers opened a current account in the Dubai branches last quarter, and what is
their average balance?") wait in an MIS queue because answering them needs someone who knows FLEXCUBE's table structure and
code values. Thousands of tables and bank-specific codes make self-service on the core impossible.

## What it will answer

Ad hoc questions in plain language over **curated, governed data products** (silver and module gold), not raw FLEXCUBE:
counts, sums, trends, top-N and comparisons by segment, branch, product, RM and period, with the SQL shown for audit.

## Design

| Layer | Plan |
|---|---|
| Data | Read-only access to selected silver and gold tables, published as views in a dedicated serving schema `FCUBS_ANALYTICS` with masked personal data |
| Semantic layer | A business description for every published table and column, approved values for coded columns, join paths and certified metric definitions (for example "active customer", "SME"). Written by the bank's data owners for the curated tables; never a copy of FLEXCUBE's internal documentation |
| Agent | `fcubs_data_copilot`: a text-to-SQL tool restricted to `FCUBS_ANALYTICS`, a metric lookup tool, and a result explainer. Row limits, read-only user, query timeout |
| Guardrails | PII masking on output, refusal for protected-attribute ranking, no free-text access to bronze |
| Evaluation | A test set of 100 or more questions with expected SQL or answers, run in CI against the sample bank to measure accuracy before each release |
| Channel | Agent Hub for analysts; results exportable to CSV |

## Why it fits the platform

The foundation has already turned FLEXCUBE codes into readable data products, which is what makes text-to-SQL reliable. The
same guardrails, serving pattern and deployment are reused. Accuracy is managed like a model: measured against a fixed test
set and promoted through environments.

## Success measures

Share of questions answered correctly on the test set; MIS tickets avoided; time to answer.

## Open questions for the bank

- Which data products and columns may analysts query, and at what aggregation level?
- Who owns and approves the metric definitions?
- Is row-level security by branch or business line required?
