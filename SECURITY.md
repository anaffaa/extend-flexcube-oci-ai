# Reporting security vulnerabilities

Oracle values the independent security research community and believes that responsible disclosure of security
vulnerabilities helps us ensure the security and privacy of all our users.

Please do NOT raise a GitHub Issue to report a security vulnerability. If you believe you have found a security
vulnerability, please submit a report to [secalert_us@oracle.com](mailto:secalert_us@oracle.com) preferably with a proof of
concept. Please review some additional information on
[how to report security vulnerabilities to Oracle](https://www.oracle.com/corporate/security-practices/assurance/vulnerability/reporting.html).

## Security practices in this sample

- No passwords, tokens or keys are stored in this repository. Terraform generates database passwords into OCI Vault; the
  scripts read them from Vault or prompt for them; the Slack token lives in the AIDP Credential Store.
- All data in `foundation/source/sample-bank/` is synthetic.
- Database access is least privilege: a read-only user for the source, a publisher user and a read-only agent user for the
  serving layer.
- The full control set for a bank deployment is in
  [docs/path-to-production/01_security_and_privacy.md](docs/path-to-production/01_security_and_privacy.md).
