# Consumption insert race contract

A unique-key insert loser now inspects the committed permit in a fresh session
following rollback. Same approval/effect/hash returns its existing idempotent
permit; a different winner returns ApprovalConflictError. An effect ID occupied
elsewhere also conflicts. If no committed winner explains the error, the original
IntegrityError remains a failure. No losing event is committed.

Real SQLite competing transactions commit during outer pre-insert flush; tests
cover same and different effect IDs. A separate injected unrelated IntegrityError
verifies no fabricated success. This is permit-record dedup/error mapping, not
external exactly-once execution or safe retry after an effect. Actor identity,
approval immutability, SQLite locks/PostgreSQL races and reconciliation unchanged.
Base is c27699ab; peer's separate decision/expiry CAS stack is not included.
