"""Ruling delta canaries on the real supplied-draft runtime."""
import importlib.util
from pathlib import Path
import sys
import pytest

P=Path(__file__).resolve().parents[2]/'backend/app/modules/c35/waiver_drafts.py'
spec=importlib.util.spec_from_file_location('s43_delta',P)
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)

def req(**kw):
    return {'as_of':'2026-10-11','profile':{'name':'N','school':'S'},'template':'Dear {contact}: {fee} for {opportunity}', 'opportunities':[{'id':'o','title':'Contest','fee':'USD 25','contact_email':'x@y.org'}],**kw}
def refuse(code,data):
    with pytest.raises(ValueError) as e:m.run(data)
    assert str(e.value)==code


def test_iso_calendar_year_zero_refuses():
    refuse('APPLY_REFUSED_BAD_TYPE:as_of',req(as_of='0000-01-01'))


@pytest.mark.parametrize('char',['\x80','\x81','\x9f'])
def test_c1_control_recipient_invalid_not_silently_valid(char):
    r=req();r['opportunities'][0]['contact_email']='x'+char+'@y.org'
    d=m.run(r)['drafts'][0]
    assert d['recipient'] is None
    assert d['needs_recipient'] is True
    assert d['recipient_invalid'] is True
    r['strict']=True
    refuse('APPLY_REFUSED_NORECIPIENT:contact_email',r)


def test_control_recipient_nonstrict_never_shared_clean_refusal():
    r=req();r['opportunities'][0]['contact_email']='x\x00@y.org'
    assert m.run(r)['drafts'][0]['recipient_invalid'] is True


def test_real_conftest_loaded_real_dependencies():
    from app.auth import context
    from app.core import providers, database, approvals, models
    from app.modules import types
    for module in (context,providers,database,approvals,models,types):
        assert module.__file__ is not None
        assert '/backend/app/' in module.__file__
    assert hasattr(context,'OIDCVerifier')
    assert providers.generate.__module__=='app.core.providers'


def test_year_one_accepted():
    assert m.run(req(as_of='0001-01-01'))['scope']['as_of']=='0001-01-01'


@pytest.mark.parametrize('email',['\x00x@y.org','x@y.org\x00','x\u2028@y.org','x\u2029@y.org'])
def test_raw_controls_never_stripped_into_valid_recipient(email):
    r=req();r['opportunities'][0]['contact_email']=email
    d=m.run(r)['drafts'][0]
    assert (d['recipient'],d['needs_recipient'],d['recipient_invalid'])==(None,True,True)


@pytest.mark.parametrize('control',['\n','\t','\r\n','\x85','\u2028','\u2029'])
@pytest.mark.parametrize('edge',['leading','trailing'])
def test_raw_edge_controls_are_invalid(control,edge):
    email=control+'a@b.co' if edge=='leading' else 'a@b.co'+control
    r=req();r['opportunities'][0]['contact_email']=email
    d=m.run(r)['drafts'][0]
    assert (d['recipient'],d['needs_recipient'],d['recipient_invalid'])==(None,True,True)


@pytest.mark.parametrize('email,expected',[
    (' a@b.co ','a@b.co'),
    ('\u00a0a@b.co\u00a0','a@b.co'),
    ('a\u200b@b.co','a\u200b@b.co'),
])
def test_zs_padding_and_cf_are_not_banned(email,expected):
    r=req();r['opportunities'][0]['contact_email']=email
    d=m.run(r)['drafts'][0]
    assert (d['recipient'],d['needs_recipient'],d['recipient_invalid'])==(expected,False,False)
