"""Pin scope/status provenance for the32 supplied cognitive register rows."""
import json
from pathlib import Path

SUBSTITUTES={1960,1961,1962,1963,1964,1965,1973,1974,1978,1979,1984,1985,1986,1987,1988,1989,1995,1996,2000,2001,2002,2003,2004,2005,2006,2008}
OPERATORS={1975,1976,1977,1992,1993,2009}

def test_cognitive_register_scope_matches_ledger_verbatim():
    register={r['row']:r for r in json.loads(Path('audits/coverage-register.json').read_text())['rows']}
    ledger={r['id']:r for r in json.loads(Path('audits/additional-2000-features.json').read_text())['rows']}
    assert len(SUBSTITUTES|OPERATORS)==32
    for row in sorted(SUBSTITUTES|OPERATORS):
        actual=register[row];source=ledger[row]
        qualifier='reference-substitute' if row in SUBSTITUTES else 'supplied-operator'
        assert actual['post_semantic_status']==source['status'],row
        assert actual['depth_sweep_status']==source['status']+'-'+qualifier,row
        assert actual['scope_provenance']['ledger_status']==source['status'],row
        assert actual['scope_provenance']['ledger_scope']==source['boundary'],row
