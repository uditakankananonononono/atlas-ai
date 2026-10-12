F = "backend/app/modules/m21_claire/social_signal_review.py"
T = "tests/modules/test_m21_social_signal_review_standalone.py"
MUT = [
 ("V1 tenant not validated", 61, F, "if not tenant_id.strip() or not 0 <= min_score <= 1", "if not 0 <= min_score <= 1", T),
 ("V2 score upper bound dropped", 61, F, "not 0 <= min_score <= 1", "not 0 <= min_score", T),
 ("V3 limit upper bound dropped", 61, F, "not 1 <= limit <= 100", "not 1 <= limit", T),
 ("V4 naive since accepted", 61, F, "if since is not None and since.tzinfo is None:", "if False:", T),
 ("V5 scan window not scaled", 61, F, "limit=min(500, limit * 10)", "limit=limit", T),
 ("V6 limit not enforced", 61, F, "        if len(cards) >= limit:\n            break", "        if False:\n            break", T),
 ("V7 score threshold exclusive", 61, F, "if score < min_score:", "if score <= min_score:", T),
 ("V8 missing score counted as passing", 61, F, 'score = signal.get("signal_score") or 0', 'score = signal.get("signal_score") or 1', T),
 ("V9 non-https sources accepted", 61, F, 'url.scheme != "https" or', "", T),
 ("V10 userinfo in url accepted", 61, F, " or url.username or url.password:", ":", T),
 ("V11 excerpt not capped", 61, F, '(signal.get("text") or "")[:600]', '(signal.get("text") or "")', T),
 ("V12 card marked contacted", 61, F, '"contacted": False', '"contacted": True', T),
 ("V13 status label dropped", 61, F, '"status": "unverified_external_observation_for_owner_review"', '"status": "verified"', T),
 ("V14 external effects listed as present", 61, F, '"external_effects": []', '"external_effects": ["post"]', T),
 ("V15 hostless url accepted", 61, F, "or not url.hostname", "", T),
 ("V16 since not passed to the store", 61, F, "list_signals(tenant_id, since=since,", "list_signals(tenant_id, since=None,", T),
]
