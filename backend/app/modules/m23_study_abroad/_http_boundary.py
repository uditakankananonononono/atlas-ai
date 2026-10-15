"""Pure mapping from identity-interview answer exceptions to HTTP status and detail.

Kept free of web-framework imports so it can be tested without the app stack.
Messages are fixed text: driver errors and their causes are never copied into
the response. Returns None for exceptions this module does not own, so callers
re-raise them instead of hiding them.
"""
from ._commit_contract import (CommitOutcomeUnknown, IntegrityWriteError,
                               UnclassifiedIntegrityError)


def map_answer_error(exc):
    if isinstance(exc, CommitOutcomeUnknown):
        return 500, {"code": "commit_outcome_unknown",
                     "message": "The answer may or may not have been saved. "
                                "Read the interview before resubmitting."}
    if isinstance(exc, IntegrityWriteError):
        return 500, {"code": "integrity_write_failed",
                     "message": "The answer was not written (database integrity error)."}
    if isinstance(exc, UnclassifiedIntegrityError):
        return 500, {"code": "integrity_unclassified",
                     "message": "The answer was not written (unrecognized database integrity error)."}
    if type(exc) is LookupError:  # exact type: a KeyError/IndexError from a bug is not "not found"
        return 404, "identity interview not found"
    if isinstance(exc, ValueError):
        return 409, str(exc)
    return None
