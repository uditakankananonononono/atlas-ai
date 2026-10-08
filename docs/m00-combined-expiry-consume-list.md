# Combined consume-expiry and status-list repairs

This integration on A14 main retains the peer runtime changes from
35eaf2cb11acc0c6844a96ba3f9bd986ebbd42b7 (consume expiry commits before refusal)
and 57ec1c01ff2bb0ccd2b0dd5645717db4c2a92d73 (classify overdue pending rows before
status-filtered limits). Recorded author for both imported commits: Instinct Agent.
Both original controls remain; the EOF test conflict retained each side. The
runtime edits merged without conflict. Earlier decision CAS, lazy-expiry CAS,
permit insert-race controls and five mixed expiry/decision cases remain.

Additional local SQLite controls cover four decision winner/loser pairs and
four permit exactness cases (same, changed effect, changed payload, ID occupied
by another approval). Same-tree checks include M03 protections and A14 planner
consumer. No notification/callback behavior is added by either new repair.
These repairs do not prove PostgreSQL locks/deadlocks, actor/role authority,
approval immutability, external exactly-once execution or full M00 closure.
