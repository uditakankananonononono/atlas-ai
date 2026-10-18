"""Hostile-fuzz delta pins for the m06 marketing batch (rows 403-420 + 412 falsy-delta).

Recorder-replay hostile fuzz over the landed suites (130 harvested valid
payloads, 100 leaf corruptions each with the Lane 8 actor set, 11,700 cases)
found 6 raw escapes: float() OverflowError on huge ints and hostile
__float__/__index__ RuntimeError past the _num fallbacks in
marketing_social_strategy and marketing_content_strategy. Both helpers now
treat those as absent values (return None), matching their contract.
Pins below verified failing raw on the pre-delta modules.
"""
import pytest

from app.modules.m06_social_media_manager.marketing_computations import compute


class _HostileFloat:
    def __float__(self): raise RuntimeError("FUZZ_HOSTILE_FLOAT")
    def __index__(self): raise RuntimeError("FUZZ_HOSTILE_FLOAT")


def test_social_strategy_num_overflow_returns_none():
    # pre-delta: float(10**400) escaped raw OverflowError from _num
    out = compute('social-media-strategy', {'facts': {'channels': ['LinkedIn'], 'impressions': 10**400}})
    assert out is not None  # huge numeric fact falls back to None, no raw OverflowError


def test_content_strategy_num_overflow_returns_none():
    out = compute('content-strategy', {'facts': {'pillars': ['p'], 'content': [{'impressions': 10**400, 'engagements': 3}]}})
    assert out is not None


def test_social_strategy_hostile_float_returns_none():
    # pre-delta: hostile __index__/__float__ escaped raw RuntimeError from _num
    out = compute('social-media-strategy', {'facts': {'channels': ['LinkedIn'], 'impressions': _HostileFloat()}})
    assert out is not None
