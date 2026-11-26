# Use case 04: SME supply chain and customer life events

**Status:** design (not yet built). **Builds on:** use case 01 (cash-flow features) and the foundation, plus `FTTB_CONTRACT_MASTER`.
**Business owners:** SME and corporate banking, retail product and marketing.

Two growth signals that FLEXCUBE already holds, delivered through the same copilot and alert pattern as use case 01.

## A. SME supply chain

**Problem.** An SME rarely fails alone: when its main buyer pays late or a large supplier is in trouble, the stress travels
through the payment network. Banks see these payments between their own customers but rarely connect them.

**What it will answer**

- Who are each SME's main buyers and suppliers, inside and outside the bank, and how concentrated are they?
- Which SMEs depend on a counterparty that is itself showing early-warning signals?
- Which outside counterparties pay many of our SMEs (anchor buyers) and are prospects for supply-chain finance?

**Design**

| Layer | Plan |
|---|---|
| FLEXCUBE tables | `FTTB_CONTRACT_MASTER` (funds transfers with debit and credit accounts), foundation `transactions` |
| Gold (`fcubs_lake.gold_supply_chain`) | `counterparty_edges` (payer, payee, monthly value and count, inside or outside the bank), `sme_concentration` (top-buyer and top-supplier shares, Herfindahl index), `contagion_watch` (SMEs whose top counterparties are HIGH in use case 01), `anchor_prospects` |
| ML | Optional graph features (degree, payment regularity, delay trend) added to the use case 01 arrears model |
| Serving and agent | `SME_CONCENTRATION`, `CONTAGION_WATCH`; new tools on the RM copilot: `get_sme_counterparties`, `get_contagion_risk` |

## B. Customer life events

**Problem.** The best moment to offer the right product is when a customer's situation changes, and the core sees those
changes first in the cash flow.

**What it will detect** (from transactions, never from protected attributes)

| Event | Signal |
|---|---|
| First salary or new employer | Salary credits start, or the paying employer changes |
| Pay rise | Salary up 15 percent or more for 2 months |
| Large one-off inflow | Inflow above 6 months of salary (bonus, end of service, property sale) |
| Approaching retirement horizon | Age band from `customer_360` combined with salary pattern, for pension and investment conversations |
| New business owner | Individual customer starts receiving business-like receipts |

**Design.** Gold `life_events` (customer, event, date, evidence) and `next_best_conversation` (event to product rules agreed
with product teams); serving table `LIFE_EVENTS`; RM copilot tool `get_life_events`; weekly RM digest in the existing alert
notebook.

## Guardrails for both

Consent and marketing preferences must be honoured before any outreach. No event uses nationality, gender, marital status or
health. Every suggestion carries the evidence ("salary up from AED 18,000 to AED 22,500 since August").

## Success measures

SME early-warning precision with network features; supply-chain finance leads; conversion of life-event conversations
against a control group.

## Open questions for the bank

- Which product rules apply to each life event, and which customers have opted out of marketing?
- How to identify outside counterparties consistently (names in payment narratives, IBAN or account identifiers)?
