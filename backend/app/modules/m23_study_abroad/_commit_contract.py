"""Driver-identified integrity classification and the ambiguous-commit contract.

Supported identification: SQLite (sqlite3 extended result codes, with a
message fallback for manually constructed or pre-3.11 exceptions) and
PostgreSQL (SQLSTATE, where 23505 is unique_violation, via psycopg). Any
other driver signal is REFUSED classification rather than guessed: an
unclassified integrity error is never collision-labeled and never retried
as a collision. This module identifies constraint classes only; it does not
establish crash recovery, cross-driver parity beyond these two drivers, or
any automatic retry/compensation policy.
"""
import sqlite3

# sqlite3 extended result codes: base SQLITE_CONSTRAINT (19) with extended
# high byte. 2067 = UNIQUE, 1555 = PRIMARYKEY; both are unique-index collisions.
_UNIQUE_SQLITE_CODES = frozenset({2067, 1555})
_UNIQUE_SQLITE_NAMES = frozenset({"SQLITE_CONSTRAINT_UNIQUE", "SQLITE_CONSTRAINT_PRIMARYKEY"})
_UNIQUE_SQLSTATE = "23505"


class CommitOutcomeUnknown(RuntimeError):
    """A call failed during commit or after a returned commit, so its write
    may have persisted. No automatic retry, compensation or deduplication is
    performed: reconcile by reading current state before resubmitting."""


class IntegrityWriteError(RuntimeError):
    """A recognized integrity error that is NOT a unique collision. The
    transaction rolled back without the write; the error is never
    collision-labeled and never retried as a collision."""


class UnclassifiedIntegrityError(RuntimeError):
    """An integrity error whose driver signal this build cannot classify.
    The transaction rolled back without the write; the error is never
    collision-labeled."""


def classify_integrity_error(exc) -> str:
    """Return 'unique', 'non_unique' or 'unsupported' for an IntegrityError.

    Accepts a SQLAlchemy IntegrityError (DBAPI exception in .orig) or a raw
    DBAPI exception. 'unsupported' means the driver signal is outside the
    identified set, not that the constraint kind is unknown-but-guessable.
    """
    orig = getattr(exc, "orig", None)
    if orig is None:
        orig = exc
    code = getattr(orig, "sqlite_errorcode", None)
    if code:
        return "unique" if code in _UNIQUE_SQLITE_CODES else "non_unique"
    name = getattr(orig, "sqlite_errorname", None)
    if name:
        return "unique" if name in _UNIQUE_SQLITE_NAMES else "non_unique"
    sqlstate = (
        getattr(orig, "sqlstate", None)
        or getattr(getattr(orig, "diag", None), "sqlstate", None)
        or getattr(orig, "pgcode", None)
    )
    if sqlstate:
        return "unique" if sqlstate == _UNIQUE_SQLSTATE else "non_unique"
    if isinstance(orig, sqlite3.IntegrityError):
        # Manually constructed or pre-3.11 exceptions carry no result codes.
        return "unique" if "UNIQUE constraint failed" in str(orig) else "non_unique"
    return "unsupported"
