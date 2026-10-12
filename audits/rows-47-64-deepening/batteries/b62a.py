D = "backend/app/modules/c32/dossier.py"
P = "backend/app/modules/c31/replicate_plan.py"
TD = "tests/modules/test_c32_dossier_s27.py tests/modules/test_c62_dossier_plan_deepening.py"
TP = "tests/modules/test_c31_replicate_plan_s12.py tests/modules/test_c62_dossier_plan_deepening.py"
MUT = [
 ("G1 private-facts refusal removed", 62, D, "    if include_private:\n        raise", "    if False:\n        raise", TD),
 ("G2 subject-name filter removed", 62, D, "if not any(t in low for t in tokens):", "if False:", TD),
 ("G3 per-dimension fact cap removed", 62, D, "if len(bucket) < MAX_FACTS_PER_DIM:", "if True:", TD),
 ("G4 completeness denominator wrong", 62, D, "round(covered / len(DIMENSIONS), 6)", "round(covered / 4, 6)", TD),
 ("G5 sentences split on period only", 62, D, 'if ch in ".!?":', 'if ch in ".":', TD),
 ("G6 trailing unterminated sentence dropped", 62, D, "    if tail:\n        out.append(tail)", "    if False:\n        out.append(tail)", TD),
 ("G7 source cap removed", 62, D, "if len(sources) > MAX_SOURCES:", "if False:", TD),
 ("G8 matching is case-sensitive", 62, D, "low = s.lower()", "low = s", TD),
 ("G9 citations not counted", 62, D, "citation_count += 1", "pass", TD),
 ("G10 'award' keyword dropped", 62, D, '"recognition": ("award", "recognition"', '"recognition": ("recognition"', TD),
 ("G11 empty sources accepted", 62, D, "if not sources:", "if False:", TD),
 ("G12 source records not type-checked", 62, D, "if not isinstance(src, dict):", "if False:", TD),
 ("R1 bsd not an open license", 62, P, 'OPEN_LICENSES = ("mit", "apache", "bsd")', 'OPEN_LICENSES = ("mit", "apache")', TP),
 ("R2 closed-source copy refusal removed", 62, P, "if copy_closed and license_ not in OPEN_LICENSES:", "if False:", TP),
 ("R3 route inverted", 62, P, 'route = "integrate" if license_ in OPEN_LICENSES else "build_ourselves"', 'route = "build_ourselves" if license_ in OPEN_LICENSES else "integrate"', TP),
 ("R4 acceptance tests not first", 62, P, '"acceptance_tests_first": True', '"acceptance_tests_first": False', TP),
 ("R5 duplicate capabilities not merged", 62, P, "sorted({policy.clean_text(c, PREFIX, \"capability\", 128) for c in caps})", "sorted([policy.clean_text(c, PREFIX, \"capability\", 128) for c in caps])", TP),
 ("R6 tickets not sorted", 62, P, 'tickets.sort(key=lambda r: (r["capability"], r["tool"]))', "pass", TP),
 ("R7 license value not validated", 62, P, 'if license_ not in OPEN_LICENSES + ("gpl", "proprietary", "unknown"):', "if False:", TP),
 ("R8 tool cap removed", 62, P, "if len(tools) > MAX_TOOLS:", "if False:", TP),
 ("R9 gpl treated as open", 62, P, 'OPEN_LICENSES = ("mit", "apache", "bsd")', 'OPEN_LICENSES = ("mit", "apache", "bsd", "gpl")', TP),
 ("R10 integrate and build counts swapped", 62, P, '"integrate_count": sum(1 for r in tickets if r["route"] == "integrate"),', '"integrate_count": sum(1 for r in tickets if r["route"] == "build_ourselves"),', TP),
 ("R11 empty tools accepted", 62, P, "    if not tools:\n        raise", "    if False:\n        raise", TP),
 ("R12 unlicensed copy refused only for gpl", 62, P, 'if copy_closed and license_ not in OPEN_LICENSES:', 'if copy_closed and license_ == "gpl":', TP),
]
