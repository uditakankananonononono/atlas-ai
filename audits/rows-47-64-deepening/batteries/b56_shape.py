A = "backend/app/modules/m23_study_abroad/admitted_cases.py"
J = "backend/app/modules/m23_study_abroad/admitted_cases.json"
T = "tests/modules/test_m23_admitted_cases.py tests/modules/test_m23_admitted_cases_shape_deepening.py"
OLIN = '"id": "olin",\n    "publisher": "Olin College",\n    "url": "https://www.olin.edu/blogs/voices-olins-class-2028-college-essay-snippets",'
HAM = '"id": "hamilton",\n    "publisher": "Hamilton College",\n    "url": "https://www.hamilton.edu/'
MUT = [
 ("Z1 duplicate id check removed", 56, A, "assert len(entries) == len({item['id'] for item in entries})", "pass", T),
 ("Z2 duplicate host check removed", 56, A, "assert len(entries) == len({urlparse(item['url']).hostname for item in entries})", "pass", T),
 ("Z3 https-only check removed", 56, A, "assert all(urlparse(item['url']).scheme == 'https' for item in entries)", "pass", T),
 ("Z5 search not case-folded", 56, A, "needle = query.casefold().strip()", "needle = query.strip()", T),
 ("Z6 evidence_type filter ignored", 56, A, "(not evidence_type or evidence_type == row['evidence_type']) and", "True and", T),
 ("Z7 search fields narrowed", 56, A, "for key in ('publisher', 'title', 'evidence_type')", "for key in ('publisher',)", T),
 ("Z8 unknown case id returns empty", 56, A, "    if row is None:\n        raise KeyError(case_id)", "    if row is None:\n        return {}", T),
 ("Z9 reading route claims live status", 56, A, "'live_status': 'source_only'", "'live_status': 'reachable'", T),
 ("Z10 reading route drops the no-rehost reason", 56, A, "'reason': 'Open the original publisher page for personal reading; Atlas does not rehost this text.'", "'reason': ''", T),
 ("Z11 data: olin url downgraded to http", 56, J, OLIN, OLIN.replace("https://www.olin", "http://www.olin"), T),
 ("Z12 data: hamilton id duplicates olin", 56, J, HAM, HAM.replace('"hamilton"', '"olin"', 1), T),
 ("Z13 data: hamilton host duplicates olin", 56, J, HAM, HAM.replace("https://www.hamilton.edu/", "https://www.olin.edu/", 1), T),
 ("Z14 data: olin evidence type changed", 56, J, '"evidence_type": "institution_published_essay",\n    "title": "Incoming Class of 2028 essay snippets"', '"evidence_type": "third_party_case_study",\n    "title": "Incoming Class of 2028 essay snippets"', T),
 ("Z15 data: olin title changed", 56, J, '"title": "Incoming Class of 2028 essay snippets"', '"title": "Incoming Class of 2028 essays (full text)"', T),
]
