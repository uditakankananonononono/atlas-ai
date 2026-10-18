"""Envelope pins for legacy marketing_computations engines (delta on 298fe826 + clm06n).

SOURCE repair (marketing_computations.py): every ENGINES entry is wrapped in a
guarded envelope and public module names are rebound to the wrapped callables,
so compute() and direct engine calls both code raw AttributeError/RuntimeError/
custom-exception escapes from .get/iteration sites as ValueError
'<slug>: invalid field value: ...'. Module-raised ValueErrors pass through
verbatim. Golden pins prove valid-payload outputs byte-identical (canonical
JSON sha256 computed on the pre-patch module).
"""
import hashlib
import json

import pytest

from app.modules.m06_social_media_manager import marketing_computations as mc


class _Boom(Exception):
    pass


class _HostileDunders:
    def __getattr__(self, name): raise _Boom("FUZZ_HOSTILE_GETATTR")
    def __iter__(self): raise _Boom("FUZZ_HOSTILE_ITER")
    def __bool__(self): raise _Boom("FUZZ_HOSTILE_BOOL")


GOLDENS = [
    ('segmentation', {'business': 'Acme Robotics', 'product': 'Kit-1', 'audience': 'STEM educators', 'goals': ['waitlist signups'], 'facts': {'users': '400 schools'}, 'contacts': [], 'provided_metrics': {}}, "eaca1b5d75b1483c0147e4d8b71cac6b36ef722263c6b4e4e7a096f2768fec33"),
    ('targeting', {'business': 'Acme Robotics', 'product': 'Kit-1', 'audience': 'STEM educators', 'goals': ['waitlist signups'], 'facts': {'users': '400 schools'}, 'contacts': [], 'provided_metrics': {}}, "c636709247c1069632fb5021e78866b588fbee3b928490876bcf1113364af028"),
    ('positioning', {'business': 'Acme Robotics', 'product': 'Kit-1', 'audience': 'STEM educators', 'goals': ['waitlist signups'], 'facts': {'users': '400 schools'}, 'contacts': [], 'provided_metrics': {}}, "9c8394c0bfa5df7e826136fbf0df018f9ba17b355d20b953ba3ceefc1ef5b2fa"),
    ('brand-architecture', {'business': 'Acme Robotics', 'product': 'Kit-1', 'audience': 'STEM educators', 'goals': ['waitlist signups'], 'facts': {'users': '400 schools'}, 'contacts': [], 'provided_metrics': {}}, "85c6b9101ab766f3f4d4e6c9c86be910751d7ef3c4beeda4d0e4459661be20c6"),
    ('brand-voice', {'business': 'Acme Robotics', 'product': 'Kit-1', 'audience': 'STEM educators', 'goals': ['waitlist signups'], 'facts': {'users': '400 schools'}, 'contacts': [], 'provided_metrics': {}}, "b26a372b1d04134235b17f7ac90912886d62e6f19c91d4501328daa3b1783fe6"),
    ('messaging-framework', {'business': 'Acme Robotics', 'product': 'Kit-1', 'audience': 'STEM educators', 'goals': ['waitlist signups'], 'facts': {'users': '400 schools'}, 'contacts': [], 'provided_metrics': {}}, "b6f8b722ef3e8b94c353d6692913282a17a91bd80f4dc35a7ec9455454e95326"),
    ('content-strategy', {'business': 'Acme Robotics', 'product': 'Kit-1', 'audience': 'STEM educators', 'goals': ['waitlist signups'], 'facts': {'users': '400 schools'}, 'contacts': [], 'provided_metrics': {}}, "7a33cf423b57a03830e73b9d0681ddedab7adb3a7702b1bc0bdade173a2abcda"),
    ('seo-optimization', {'business': 'Acme Robotics', 'product': 'Kit-1', 'audience': 'STEM educators', 'goals': ['waitlist signups'], 'facts': {'users': '400 schools'}, 'contacts': [], 'provided_metrics': {}}, "66242251edc698519b6f745be89697b44b132609c6b4c73f06acafebd5f431c8"),
]


def test_compute_envelope_codes_structural_junk():
    with pytest.raises(ValueError, match="segmentation: invalid field value"):
        mc.compute("segmentation", 5)


def test_direct_engine_call_hits_envelope():
    with pytest.raises(ValueError, match="segmentation: invalid field value"):
        mc.segmentation(5)


def test_envelope_codes_custom_exception_dunder():
    with pytest.raises(ValueError, match="segmentation: invalid field value"):
        mc.compute("segmentation", {"facts": _HostileDunders(), "goals": []})


def test_valueerror_passes_through_verbatim():
    with pytest.raises(ValueError, match="^customers must be numeric$"):
        mc.compute("segmentation", {"facts": {"segment_metrics": [{"name": "a", "customers": "x"}]}})


def test_unknown_slug_still_coded():
    with pytest.raises(ValueError, match="unknown marketing engine"):
        mc.compute("nope", {})


def test_valid_payloads_byte_identical():
    for slug, payload, want in GOLDENS:
        got = mc.compute(slug, payload)
        have = hashlib.sha256(json.dumps(got, sort_keys=True, default=str).encode()).hexdigest()
        assert have == want, slug
