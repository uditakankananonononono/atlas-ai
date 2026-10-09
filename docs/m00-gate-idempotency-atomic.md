# Review gate idempotency race

Keyed review gates now write request, created event and idempotency record in one
transaction. A unique-key loser reads the committed key in a fresh session: exact
request hash returns the winning approval, other hashes conflict, and errors with
no winner propagate. No losing approval/event or request signal is retained.
Unkeyed submit and policy allow/deny paths remain unchanged.

Actual SQLite competing transactions commit a same/different-hash keyed gate during
outer preinsert flush. Base leaks an orphan and throws IntegrityError; repaired
controls return winner/conflict and retain one approval. PostgreSQL locking,
postcommit signal failure, policy changes and effect execution are unproven.
Keys remain globally scoped and request hashes include user_id; no tenant-key
namespace migration. No full M00 or external exactly-once claim.
