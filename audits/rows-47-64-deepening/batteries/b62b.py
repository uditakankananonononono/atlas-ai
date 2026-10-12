P = "backend/app/modules/c37/patents.py"
T = "tests/modules/test_c37_patents_v2.py tests/modules/test_c37_patents_text_deepening.py"
MUT = [
 ("T1 owner check removed", 62, P, 'if inv.get("owner") != "self" or not _is_str(inv.get("owner")):', "if False:", T),
 ("T2 draft label dropped from claims", 62, P, '"text": t, "label": DRAFT}', '"text": t, "label": ""}', T),
 ("T3 single-component claim body joined wrong", 62, P, "    if len(components) == 1:\n        body = components[0]", "    if False:\n        body = components[0]", T),
 ("T4 dependent claims numbered from 1", 62, P, "enumerate(features, start=2)", "enumerate(features, start=1)", T),
 ("T5 dependent claim text loses 'of claim 1'", 62, P, '"%d. The %s of claim 1, wherein %s."', '"%d. The %s, wherein %s."', T),
 ("T6 https-only url check removed", 62, P, 'not value.startswith("https://")', 'not value.startswith("http")', T),
 ("T7 duplicate prior-art ids allowed", 62, P, "        if pid in seen:\n            _refuse", "        if False:\n            _refuse", T),
 ("T8 novelty source not checked", 62, P, 'or nov.get("source") != "c32.ideate"', "", T),
 ("T9 novelty range upper bound dropped", 62, P, "not 0 <= v <= 1", "not 0 <= v", T),
 ("T10 novelty value not rounded", 62, P, '"value": round(v, 6)', '"value": v', T),
 ("T11 calendar-invalid dates accepted", 62, P, '        datetime.strptime(value, "%Y-%m-%d")\n    except ValueError:', '        pass\n    except ValueError:', T),
 ("T12 control characters allowed in text", 62, P, '{"Cc", "Cf", "Zl", "Zp"} for c in value)', '{"Zl"} for c in value)', T),
 ("T13 owner assertion not labeled unverified", 62, P, '"owner_assertion": UNVERIFIED', '"owner_assertion": "verified"', T),
 ("T14 whitespace-only text allowed", 62, P, "if not value.strip() or any(", "if any(", T),
 ("T15 unhostnamed url allowed", 62, P, "    if not host:\n        _refuse", "    if False:\n        _refuse", T),
 ("T16 prior-art cap removed", 62, P, '"prior_art": PA_CAP}', '"prior_art": 10**9}', T),
]
