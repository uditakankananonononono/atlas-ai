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
