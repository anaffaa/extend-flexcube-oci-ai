# Foundation

Everything shared by the use-case modules. Deploy it once per environment.

| Folder | What it does | Guide |
|---|---|---|
| [`terraform/`](terraform) | VCN, private subnet, gateways and NSG; Vault, key and generated password secrets; staging bucket; AIDP instance; IAM policies; logging and operations topic; optional sample bank database | [Deploy, step 1](../docs/foundation/02_deploy.md#step-1-deploy-the-foundation) |
| [`source/`](source) | Sample bank (synthetic data, generator, one-command load) and the read-only user and pre-check for your own FLEXCUBE | [Source patterns](../docs/foundation/03_source_patterns.md) |
| [`lakehouse/`](lakehouse) | Notebooks `fnd_01_bronze`, `fnd_02_silver`, `fnd_03_quality_checks` | [Data foundation](../docs/foundation/04_data_foundation.md) |
| [`serving/`](serving) | Serving users `FCUBS_GOLD` and `AIDP_AGENT`, and the script that deploys every module's serving tables | [Deploy, step 6](../docs/foundation/02_deploy.md#step-6-serving-layer) |
