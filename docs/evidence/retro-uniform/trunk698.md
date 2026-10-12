# TRUNK698 scoped reproduction

Landed unit reference: `407d1adf + 9bbd507e`. Scope is the supplied/offline behavior
in its existing contract, not full-module or real-world completion.

Exact released selector from repository root, Python 3.12:

```sh
PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest tests/modules/test_m20_trunk698_dag.py -q
```

The development-auth values reproduce the local test fixture only; production
policy is unchanged. This selector does not assert repository-wide coverage.

Mailbox packaging uses `scripts/release/package_mailbox.py` with the exact
listed test files. The external receipt records the real executable, actual
selector result and log SHA256, mailbox SHA256, base/result commits and trees,
and the verified git-am result tree. It is not an embedded self-hash or a claim
that prior delivery logs had those fields. Check the receipt for the actual
result; historical ledger test or mutant counts are not fresh execution.

UNTESTED: historical mutation batteries not rerun; whole-repository regression;
live integrations, provider effects and supplied-data semantic correctness.
Runtime authority, scope and accepted refusal contracts are unchanged.
