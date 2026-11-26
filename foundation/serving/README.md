# Serving layer

Agents and applications never query the lakehouse directly. Each module publishes curated tables into schema `FCUBS_GOLD` in
the AIDP Lakehouse:

| User | Rights | Used by |
|---|---|---|
| `FCUBS_GOLD` | Owns the serving tables | Publish notebooks, through catalog `fcubs_serving_rw` |
| `AIDP_AGENT` | SELECT on serving tables only | Agent SQL tools, through catalog `fcubs_serving` |

```bash
bash foundation/serving/deploy_serving_layer.sh <AIDP Lakehouse OCID> [module folder ...]
```

The script runs [`sql/00_serving_users.sql`](sql/00_serving_users.sql), then every `use-cases/<module>/sql/*serving_tables.sql`
(all modules, or the ones you name). Passwords come from Vault (`FROM_TERRAFORM=true` or `*_SECRET_OCID` in
`foundation/source/sample-bank/deploy.env`, or `DEPLOY_ENV` pointing to another file), or are prompted. Existing users and
tables are kept, so it is safe to re-run.

Console alternative: in the Lakehouse's Database Actions as ADMIN, run `00_serving_users.sql` with both password placeholders
replaced, then each module's serving SQL.
