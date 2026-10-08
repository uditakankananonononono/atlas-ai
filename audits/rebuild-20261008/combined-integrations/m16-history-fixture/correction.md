# Historical-forward seam correction

Original batch25: 2 failed, 205 passed. Both SQLite/PostgreSQL failures were the expected identity_forward revision versus new view_version head. Product graph unchanged.

Exactly two calls changed from migrate('upgrade','head') to migrate('upgrade','20261008_m16_identity_forward'). Every refusal, row-count, version, unique-index and irreversible-downgrade assertion remains unchanged. This historical seam does not depend on later M10/view migrations. Separate combined clean-head and two SQLite cycles remain required; no combined PostgreSQL cycle claim.
