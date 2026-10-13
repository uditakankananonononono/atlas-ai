# Outbound declared-count repair

Found via peer review. The gate used count 1 when replaying every prior
outbound dispatch, even if the action declared a larger count. Each decision
now records its effective P70 count, and history replays that count.

Breaking change: persisted outbound ledgers from before count accounting
refuse to load. Deployment/migration path: archive the old ledger intact and
start a fresh ledger explicitly. Do not silently default unknown counts to 1
or rewrite old rows. Archive custody and the operational reset are the
operator's responsibility. Restarting history is not proof of unused vendor
capacity; preserve necessary declared rate history conservatively.

The pytest suite converts both peer probes to normal repository imports,
including the real GuardrailEnforcer path, independent effects, boundary,
roundtrip, malformed/default counts, and tamper tests. Frozen legacy fixture
SHA256: b4e6d2f139378643809b980e02c84b2f8556b15fe1946939292f36a402bb967b.

Before repair: 6 failed, 6 passed. After repair: 12 passed.
These are hermetic mechanism tests, not vendor policy or deployment proof.
