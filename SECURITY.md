# Reporting security concerns

This is a personal playbook, not an Oracle product. Please do not raise a public GitHub issue for a security concern. Use
GitHub's private vulnerability reporting on this repository (Security tab, "Report a vulnerability"), or contact the author
through GitHub.

If you believe you have found a vulnerability in an Oracle product used here (for example OCI or Oracle AI Data Platform),
report it to Oracle through its official channels, not to this repository.

## Security practices in this sample

- No passwords, tokens or keys are stored in this repository. Terraform generates database passwords into OCI Vault; the
  scripts read them from Vault or prompt for them; the Slack token lives in the AIDP Credential Store.
- All data in `foundation/source/sample-bank/` is synthetic.
- Database access is least privilege: a read-only user for the source, a publisher user and a read-only agent user for the
  serving layer.
- The full control set for a bank deployment is in
  [docs/path-to-production/01_security_and_privacy.md](docs/path-to-production/01_security_and_privacy.md).
