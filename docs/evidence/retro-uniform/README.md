# Retro selector and receipt reconciliation

Twelve unit commands select fifteen distinct unit test files. The combined
release selects those fifteen files plus tests/release/test_package_mailbox.py,
so it is sixteen files, not sixteen unit commands. Historical local execution:
1059 passed and 129 subtests passed in 10.24 seconds. This is selected-file
execution, not a whole-repository or fresh current-tree result.

Exact historical portable combined command:

```sh
PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest tests/release/test_package_mailbox.py tests/modules/test_c35_sweep_s41.py tests/modules/test_c34_site_s32.py tests/troop/test_s3_1_prototyper.py tests/modules/test_c32_dossier_timeline_s27.py tests/modules/test_m06_multi_account_u07.py tests/modules/test_m19_trend_counts_u03.py tests/modules/test_m19_trend_pipeline_u03.py tests/modules/test_m19_trend_pipeline_u03_pins.py tests/modules/test_m19_u03_j1_adapter.py tests/modules/test_m20_sentencing_grid1260.py tests/modules/test_m23_s4_7_abroad_fullride.py tests/modules/test_m23_polymath_roadmap.py tests/modules/test_m02_site_application_planner.py tests/modules/test_m20_trunk698_dag.py tests/modules/test_m01_high_school_competitions_u37.py -q
```

Historical external receipts below retain mailbox/log hashes and composition
trees. Executable token is portable; exact executable/logs remain in the private
release archive. No count is reconstructed from test-name mentions.

UNTESTED: historical mutation batteries, whole repository, live integrations.
SENT1260 and APP-PLANNER list-subclass policy remains unresolved; existing
isinstance/lying-length residual is retained. APP-PLANNER accepted short-token
exact-match tradeoffs remain unchanged. U03 real J1 ledger/scorer round trip is
UNTESTED. These limitations are not closed by packaging evidence.
