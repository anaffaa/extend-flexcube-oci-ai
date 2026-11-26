# Tests

| Test | What it proves | Run |
|---|---|---|
| `tests/local/run_pipeline_local.py` | Bronze, silver, quality checks, cash-flow gold and the ML notebook run end to end on the sample bank and give the documented results | see the file header |
| `foundation/source/sample-bank/generator/validate.py` | The sample data keeps its keys, foreign keys and planted scenarios | `pip install duckdb && python3 foundation/source/sample-bank/generator/validate.py` |
| `tools/build_notebooks.py --check` | Every `.ipynb` matches its `notebooks/src/*.py` source | `python3 tools/build_notebooks.py --check` |
| `.github/workflows/ci.yml` | All of the above plus `terraform fmt` and `terraform validate`, on every pull request | GitHub Actions |

The local run uses parquet instead of Delta and a file MLflow store, so it needs no AIDP. It does not test the
external catalogs, the serving layer, the agent or Slack: test those in a non-production AIDP workspace
(see [docs/path-to-production/02_environments_and_cicd.md](../docs/path-to-production/02_environments_and_cicd.md)).
