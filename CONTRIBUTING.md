# Contributing

This project welcomes contributions from the community. Before submitting a pull request, please review this guide.

## Opening issues

For bugs or enhancement requests, please file a GitHub issue unless it is security related. For security vulnerabilities, see
[SECURITY.md](SECURITY.md).

## Contributing code

We welcome your code contributions. Before submitting code via a pull request, you will need to have signed the
[Oracle Contributor Agreement](https://oca.opensource.oracle.com) (OCA) and your commits need to include the following line
using the name and e-mail address you used to sign the OCA:

```text
Signed-off-by: Your Name <you@example.org>
```

## Pull request process

1. Ensure there is an issue created to track and discuss the fix or enhancement you intend to submit.
2. Fork this repository and create a branch in your fork.
3. Edit the readable notebook sources (`*/notebooks/src/*.py`), never the `.ipynb` files, then rebuild them with
   `python3 tools/build_notebooks.py`. Run `tests/local/run_pipeline_local.py` on the sample bank and confirm every quality
   check passes. A new use case follows the layout in [use-cases/README.md](use-cases/README.md).
4. Never commit real customer data, passwords, tokens, OCIDs or tenancy names.
5. Submit the pull request, referencing the issue.

## Code of conduct

Follow the [Golden Rule](https://en.wikipedia.org/wiki/Golden_Rule). If you'd like more specific guidelines, see the
[Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/1/4/code-of-conduct/).
