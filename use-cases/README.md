# Use-case modules

Each module extends FLEXCUBE with one business capability on the shared foundation. Modules are independent: enable,
upgrade or remove one without touching the others.

| # | Module | Business owner | Status | What it delivers |
|---|---|---|---|---|
| 01 | [Cash-flow intelligence](01-cashflow-intelligence/README.md) | RMs, collections, credit risk | **Available** | Early warning (rules and ML), collections worklist, SME runway, RM copilot, daily RM alerts |
| 02 | [Reconciliation watch](02-reconciliation-watch/README.md) | Finance, operations | Design | Daily break detection on GLs, references and balances, with ageing and anomaly scores |
| 03 | [FLEXCUBE data copilot](03-flexcube-data-copilot/README.md) | Analysts, MIS | Design | Governed plain-language questions over curated data products |
| 04 | [SME supply chain and life events](04-sme-supply-chain-and-life-events/README.md) | SME and retail banking | Design | Counterparty concentration and contagion; life-event triggers for the next conversation |

## Module contract

Every module follows the same layout and rules, so a new one can be added by copying `01-cashflow-intelligence`:

```text
use-cases/<NN-name>/
  README.md                 business problem, capabilities, enable steps, objects it adds, how to remove it
  notebooks/src/*.py        sources of truth (<prefix>_01_..., quality checks as <prefix>_02_quality_checks)
  notebooks/*.ipynb         built with tools/build_notebooks.py
  sql/*serving_tables.sql   serving tables in FCUBS_GOLD, with SELECT grants to AIDP_AGENT
  agent/*.md                agent specification: instructions, tools, guardrails, model settings, test questions
  docs/                     the module's playbook chapters
```

1. **Read only from the foundation.** Read silver (and bronze for raw details); never write to either. List any extra
   FLEXCUBE tables in the README and add their grants to `foundation/source/own-flexcube/01_create_aidp_reader.sql`.
2. **Own your schema.** Write only to `fcubs_lake.gold_<module>` and your own serving tables.
3. **Gate before you publish.** A quality-check notebook runs after gold and fails the run on bad data.
4. **Publish, then serve.** Agents read the serving schema only, through `AIDP_AGENT`.
5. **Explain every output** and keep protected attributes out of features, rules and rankings.
6. **Ship tests.** Add the module's notebooks to `tests/local/run_pipeline_local.py` with expected results on the sample bank.
