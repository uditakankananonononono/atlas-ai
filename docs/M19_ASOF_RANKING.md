# M19 as-of filtered ranking integration

Additive /portfolio/ranking/as-of route reuses existing authenticated tenant
repository dependency and legacy scoring. Existing /ranking unchanged. Required
aware as_of; default drops experiments changed after it. Backdated evidence
recorded later is excluded. Current idea stages and row field values remain
current, so this is NOT historical reconstruction. Diagnostic scope covers rows
visited for eligible current-stage ideas, not a complete repository census.
Provenance digest binds actual filtered scoring rows and policy, not only IDs.
It is a deterministic identity checksum, not authenticity or external permission.
Repository method reads are separate snapshots; concurrent changes can yield a
mixed read. No point-in-time SQL transaction or historical-stage reconstruction
is claimed. Tests use offline fixtures; production load is unmeasured.

Independent verdict ataba76ce2: new tests25PASS. Initial verifier wholeM19
had271PASS9FAIL8SKIP with identical nine failures at basef37156c7. All nine
async tests lacked pytest-asyncio in reviewer environment; after installing
pytest-asyncio1.4.0 (declared dev dependency), independent rerun280PASS8SKIP,
matching builder. No network/credentials/candidate-code involvement.
Diagnostics remain visited rows only. Digest binds INCLUDED scoring values and
EXCLUDED kind/id/reason, not excluded values or all repository content. Editing
an excluded future row's strength need not change it. No full-integrity or
authenticity claim. Full suite requires the project's declared dev dependencies.
