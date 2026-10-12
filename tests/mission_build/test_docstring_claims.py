"""Module docstrings state what the code does: deterministic recompute, digest matching, one SQLite file."""
import app.mission_build.acceptance as acceptance
import app.mission_build.durable_jobs as durable_jobs
import app.mission_build.exact_math as exact_math
from app.mission_build.exact_math import analyze


def test_docstrings_make_only_checkable_claims():
    assert 'independently replayable' not in exact_math.__doc__
    assert 'deterministically recompute' in exact_math.__doc__
    assert 'across instances' not in durable_jobs.__doc__ and 'one shared SQLite file' in durable_jobs.__doc__
    assert 'match the source and test digests' in acceptance.__doc__


def test_certificate_recompute_is_deterministic():
    data={'coefficients':[1,2,3],'at':2}
    assert analyze(data)==analyze(dict(data))
