C = "backend/app/modules/c31/clicky.py"
O = "backend/app/modules/c31/okara.py"
CT = "tests/modules/test_c31_clicky_a3.py tests/modules/test_c31_adapter_plan_deepening.py"
OT = "tests/modules/test_c31_okara_a3.py tests/modules/test_c31_adapter_plan_deepening.py"
def shared(pre, row, f, t):
    return [
     (pre+"1 free tier not required at identify", row, f, 'if clean["free_tier"] is not True:\n        policy.check("spend", PREFIX)', 'if False:\n        policy.check("spend", PREFIX)', t),
     (pre+"2 unknown endpoint accepted", row, f, 'if endpoint_key not in clean["endpoints"]:', 'if False:', t),
     (pre+"3 params cap removed", row, f, 'if len(params) > MAX_PARAMS:', 'if False:', t),
     (pre+"4 bool param value accepted", row, f, 'if isinstance(v, bool) or not isinstance(v, (str, int, float)):', 'if not isinstance(v, (str, int, float)):', t),
     (pre+"5 non-finite float accepted", row, f, 'if isinstance(v, float) and not math.isfinite(v):', 'if False:', t),
     (pre+"6 params not sorted", row, f, 'for k in sorted(keyed):', 'for k in keyed:', t),
     (pre+"7 http error status accepted", row, f, 'if status < 200 or status >= 300:', 'if status >= 500:', t),
     (pre+"8 NaN constant accepted", row, f, 'data = json.loads(body, parse_constant=_strict_constant)', 'data = json.loads(body)', t),
     (pre+"9 body size cap removed", row, f, 'if not isinstance(body, str) or len(body) > MAX_BODY:', 'if not isinstance(body, str):', t),
     (pre+"10 api_base slash not stripped", row, f, 'clean["api_base"].rstrip("/") + spec["path"]', 'clean["api_base"] + spec["path"]', t),
     (pre+"11 method restriction removed", row, f, 'if method not in ("GET", "POST"):\n            raise ValueError("APPLY_REFUSED_BAD_TYPE:method")\n        clean_endpoints', 'if False:\n            raise ValueError("APPLY_REFUSED_BAD_TYPE:method")\n        clean_endpoints', t),
    ]
MUT = shared("K", 57, C, CT) + shared("O", 58, O, OT) + [
 ("K12 stats limit upper bound dropped", 57, C, 'not 1 <= limit <= FREE_MAX_LIMIT', 'not 1 <= limit', CT),
 ("K13 history bound widened", 57, C, 'int(m.group(1)) <= FREE_MAX_HISTORY_DAYS', 'int(m.group(1)) <= 365', CT),
 ("K14 undocumented stats type accepted", 57, C, 'if t not in DOCUMENTED_TYPES:', 'if False:', CT),
 ("K15 bool site_id accepted", 57, C, 'if isinstance(site_id, bool) or not isinstance(site_id, int) or site_id <= 0:', 'if not isinstance(site_id, int) or site_id <= 0:', CT),
 ("K16 absolute dates accepted", 57, C, 'if not _history_days_ok(date):', 'if False:', CT),
]
