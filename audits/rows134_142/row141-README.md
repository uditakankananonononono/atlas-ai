# Row 141: per-project verified tool bar

Evidence tier: actual local gate code, declared fixture inputs and inert effect
spies. Not live external enforcement or universal runtime adoption.

Exact released selector, Python 3.12, repository root:

```sh
PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/runtime/guardrails/test_tool_usage_bar.py -q -rf
```

Run the five exact-site mutations via:

```sh
python scripts/release/scoped_mutations.py audits/rows134_142/row141.json OUT
```

Per-run timeout: 45 seconds. CAUGHT requires rc1 with FAILED test IDs and no
collection error; crashes/skips/timeouts/invalid sites are not caught. Every
restore is byte-SHA256 verified. External receipts/logs preserve test IDs,
spec/log hashes and actual outcomes. All five final mutations caught.
Initial non-kills: none. Initial receipts
remain retained. Added exact sensitivity or authority tests to the selector
where needed; no runtime guard weakened or changed.

UNTESTED: Declared verified tool names, not proof of 200 real tool executions or useful breadth. Whole-repository regression, hostile-process containment,
provider truth and global effect interception are untested. Source restore
and direct pytest timeout do not isolate escaped descendants. Literal scope
remains PARTIAL; computed egress labels are declared wiring inventory, never
certification of every path. Development-auth env is local test fixture only.
