"""Row 101 Authority Positioning: hermetic stdlib tests, N/N+1 pins, row-tagged refusals. Loads the module by path."""
import importlib.util
import pathlib
import sys

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/authority_positioning101.py"
_spec = importlib.util.spec_from_file_location("authority_positioning101", _SRC)
ap = importlib.util.module_from_spec(_spec)
sys.modules["authority_positioning101"] = ap
_spec.loader.exec_module(ap)

AS_OF = "2026-03-31"


def cred(cid="c1", kind="license", issuer="Board A", relevance="direct", verified_by="registry lookup", issued_on="2020-01-01",
         expires_on=None, attributable=True):
    c = {"id": cid, "kind": kind, "issuer": issuer, "relevance": relevance, "verified_by": verified_by,
         "issued_on": issued_on, "attributable": attributable}
    if expires_on is not None:
        c["expires_on"] = expires_on
    return c


def go(creds=None, claim="Qualified to review structural drawings", disclosed=True, as_of=AS_OF):
    return ap.assess({"claim": claim, "credentials": [cred()] if creds is None else creds, "as_of": as_of, "disclosed": disclosed})


def refused(fn, word):
    with pytest.raises(ap.AuthorityError) as e:
        fn()
    assert str(e.value).startswith("AUTHOR101: ")
    assert word in str(e.value)


def test_direct_verified_credential_counts_two_points_limited():
    r = go()
    assert r["row"] == 101 and r["counted"] == ["c1"] and r["uncounted"] == []
    assert r["points"] == 2 and r["distinct_issuers"] == 1 and r["assertion_level"] == "limited"
    assert r["release_allowed"] is True


def test_adjacent_counts_one_point_none_counts_zero():
    r = go([cred(relevance="adjacent")])
    assert r["points"] == 1 and r["counted"] == ["c1"]
    r = go([cred(relevance="none")])
    assert r["counted"] == [] and r["uncounted"] == [{"id": "c1", "reasons": ["not_relevant"]}]
    assert r["assertion_level"] == "none" and r["release_allowed"] is False


def test_supported_needs_4_points_and_2_issuers():
    three = go([cred("a", issuer="A"), cred("b", issuer="B", relevance="adjacent")])
    assert three["points"] == 3 and three["distinct_issuers"] == 2 and three["assertion_level"] == "limited"
    four = go([cred("a", issuer="A"), cred("b", issuer="B")])
    assert four["points"] == 4 and four["assertion_level"] == "supported"
    one_issuer = go([cred("a", issuer="A"), cred("b", issuer="A")])
    assert one_issuer["points"] == 4 and one_issuer["distinct_issuers"] == 1 and one_issuer["assertion_level"] == "limited"


def test_expiry_inclusive_on_as_of_day():
    assert go([cred(expires_on="2026-03-31")])["counted"] == ["c1"]
    r = go([cred(expires_on="2026-03-30")])
    assert r["counted"] == [] and r["uncounted"][0]["reasons"] == ["expired"]


def test_unverified_and_unattributable_are_uncounted_with_reasons_in_fixed_order():
    r = go([cred(verified_by=None, attributable=False, relevance="none")])
    assert r["uncounted"] == [{"id": "c1", "reasons": ["unverified", "unattributable", "not_relevant"]}]
    assert r["disclosure_required"] == ["c1"]
    r = go([cred(verified_by="  ")])
    assert r["uncounted"][0]["reasons"] == ["unverified"]


def test_issued_on_as_of_day_ok_next_day_refused():
    assert go([cred(issued_on="2026-03-31")])["counted"] == ["c1"]
    refused(lambda: go([cred(issued_on="2026-04-01")]), "issued_on")


def test_release_requires_disclosure():
    r = go(disclosed=False)
    assert r["assertion_level"] == "limited" and r["release_allowed"] is False
    refused(lambda: go(disclosed="yes"), "disclosed")


def test_expiry_before_issue_refused():
    refused(lambda: go([cred(issued_on="2020-01-02", expires_on="2020-01-01")]), "expires_on")


def test_credential_count_cap_100_ok_101_refused():
    ok = [cred(f"c{i}", issuer=f"I{i}") for i in range(100)]
    assert go(ok)["points"] == 200
    refused(lambda: go(ok + [cred("extra")]), "credentials")


def test_claim_length_cap_500_ok_501_refused_and_blank_refused():
    assert go(claim="x" * 500)["claim"] == "x" * 500
    refused(lambda: go(claim="x" * 501), "claim")
    refused(lambda: go(claim="   "), "claim")
    refused(lambda: go(claim=None), "claim")


def test_empty_credentials_gives_none_level():
    r = go([])
    assert r["assertion_level"] == "none" and r["points"] == 0 and r["release_allowed"] is False


def test_shape_refusals():
    refused(lambda: ap.assess([]), "mapping")
    refused(lambda: ap.assess({"claim": "x", "credentials": "no", "as_of": AS_OF, "disclosed": True}), "credentials")
    refused(lambda: go([cred(kind="rank")]), "kind")
    refused(lambda: go([cred(relevance="high")]), "relevance")
    refused(lambda: go([cred(cid="")]), "id")
    refused(lambda: go([cred("a"), cred("a", issuer="Z")]), "duplicate")
    refused(lambda: go([cred(issuer="")]), "issuer")
    refused(lambda: go([cred(attributable="yes")]), "attributable")
    refused(lambda: go([dict(cred(), extra=1)]), "unknown key")
    refused(lambda: go([cred(issued_on="2020-13-01")]), "issued_on")
    refused(lambda: go(as_of="31/03/2026"), "as_of")
    refused(lambda: ap.assess({"claim": "x", "credentials": [], "disclosed": True}), "as_of")
    refused(lambda: ap.assess({"claim": "x", "credentials": [], "as_of": AS_OF, "disclosed": True, "bonus": 1}), "unknown key")
    refused(lambda: go(["notadict"]), "credential 0")


def test_output_states_limits_and_is_deterministic():
    a, b = go(), go()
    assert a == b
    assert "supplied declarations only" in " ".join(a["limits"]).lower()
    assert "no credential is verified by this function" in " ".join(a["limits"]).lower()
    for banned in ("persuad", "guarantee", "will convince", "manipulat"):
        assert banned not in " ".join(a["limits"]).lower().replace("not a prediction of persuasion", "")


def test_input_not_mutated():
    creds = [cred()]
    import copy
    before = copy.deepcopy(creds)
    go(creds)
    assert creds == before


def test_adjacent_alone_is_limited_not_none():
    assert go([cred(relevance="adjacent")])["assertion_level"] == "limited"


def test_every_declared_kind_is_accepted_and_other_refused():
    for k in ("degree", "license", "publication", "experience", "affiliation"):
        assert go([cred(kind=k)])["counted"] == ["c1"]


def test_expires_on_issue_day_is_accepted():
    assert go([cred(issued_on="2020-01-01", expires_on="2020-01-01")], as_of="2020-01-01")["counted"] == ["c1"]


def test_output_echoes_as_of_and_claim():
    r = go()
    assert r["as_of"] == AS_OF and r["claim"] == "Qualified to review structural drawings"


def test_exact_refusal_messages_for_top_level_shape():
    with pytest.raises(ap.AuthorityError) as e:
        ap.assess([])
    assert str(e.value) == "AUTHOR101: input must be a mapping"
    with pytest.raises(ap.AuthorityError) as e:
        ap.assess({"claim": "x", "credentials": [], "disclosed": True})
    assert str(e.value) == "AUTHOR101: as_of required"
    with pytest.raises(ap.AuthorityError) as e:
        go(disclosed=1)
    assert str(e.value) == "AUTHOR101: disclosed must be true or false"


def test_limits_text_is_exact():
    assert go()["limits"] == [
        "Supplied declarations only; this function checks consistency and dates, not the truth of any declaration.",
        "No credential is verified by this function; 'verified_by' is the caller's own statement of a check.",
        "Not a prediction of persuasion or any outcome; cite only counted credentials, and disclose the uncounted ones.",
    ]


def test_malformed_as_of_message_is_exact():
    with pytest.raises(ap.AuthorityError) as e:
        go(as_of="31/03/2026")
    assert str(e.value) == "AUTHOR101: as_of must be an ISO date string YYYY-MM-DD"


def exact(fn,message):
    with pytest.raises(ap.AuthorityError) as error:fn()
    assert str(error.value)=='AUTHOR101: '+message


@pytest.mark.parametrize('field',['as_of','issued_on','expires_on'])
@pytest.mark.parametrize('value',[20260101,None,b'2026-10-11',[], '2026-W41-3','20261011','2026-284','2026-10-11\n','٢٠٢٦-١٠-١١','2026-02-30'])
def test_date_canonical_and_types_exact(field,value):
    name='as_of' if field=='as_of' else 'credential 0 '+field
    if field=='as_of':fn=lambda:go(as_of=value)
    else:
        c=cred();c[field]=value;fn=lambda:go([c])
    exact(fn,name+' must be an ISO date string YYYY-MM-DD')


@pytest.mark.parametrize('value',['x',[],None,5])
def test_credential_exact_dict_type(value):
    exact(lambda:go([value]),'credential 0 must be a mapping')


def test_canonical_asof_byte_identical():
    assert go(as_of='2026-10-11')['as_of'].encode()==b'2026-10-11'


@pytest.mark.parametrize('field,value,message',[
 ('id','', 'credential 0 id must be a non-empty string'),
 ('issuer','', 'credential 0 issuer must be a non-empty string'),
 ('kind','bad','credential 0 kind must be one of degree, license, publication, experience, affiliation'),
 ('relevance','bad','credential 0 relevance must be one of direct, adjacent, none'),
 ('attributable',1,'credential 0 attributable must be true or false'),
 ('issued_on','2027-01-01','credential 0 issued_on is after as_of'),
 ('expires_on','2019-01-01','credential 0 expires_on is before issued_on'),
 ('extra',1,"credential 0 has unknown key 'extra'")])
def test_credential_message_sites_exact(field,value,message):
    c=cred();c[field]=value;exact(lambda:go([c]),message)


def test_duplicate_message_exact():
    exact(lambda:go([cred(),cred()]),"duplicate credential id 'c1'")


def test_top_message_sites_exact():
    exact(lambda:go(claim=None),'claim must be a non-empty string of at most 500 characters')
    exact(lambda:go('bad'),'credentials must be a list of at most 100 records')
    x=dict(claim='c',credentials=[],as_of=AS_OF,disclosed=True,extra=1)
    exact(lambda:ap.assess(x),"unknown key 'extra'")


@pytest.mark.parametrize('value',['2026-10-11x','x'*(10*1024*1024)],ids=['raw11','ten-megabytes'])
@pytest.mark.parametrize('field',['as_of','issued_on','expires_on'])
def test_raw_date_length_refused_before_regex(monkeypatch,value,field):
    def forbidden_regex(*args,**kwargs):
        raise AssertionError('oversize raw date reached regex')
    monkeypatch.setattr(ap.re,'fullmatch',forbidden_regex)
    name='as_of' if field=='as_of' else 'credential 0 '+field
    exact(lambda:ap._day(value,name),name+' must be an ISO date string YYYY-MM-DD')
