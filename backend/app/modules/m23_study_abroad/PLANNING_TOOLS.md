# M23: 20 new student-owned planning checks

`POST /study-abroad/planning/{tool}` accepts `{"data":{...}}`. In the Study Abroad workbench, each operation has an editable example. All are deterministic analyses of the supplied fields, not imported current admission data. No submission, essay generation, admission prediction, spending, or external effects occur. Individual examples and assertions are in `tests/modules/test_m23_planning_tools.py`. API errors return 404 for unknown tools and 422 for invalid inputs handled by the operation. Production decisions still require checking current official school and government sources.

| # | Tool | Operational result | Status |
|---:|---|---|---|
| 1 | deadline_triage | overdue and upcoming dates, ordered by days left | Verified fixture |
| 2 | workload_calendar | weekly time split and capacity warning | Verified fixture |
| 3 | requirement_gap | completed vs missing requirements | Verified fixture |
| 4 | school_list_balance | counts of student-assessed reach/target/likely labels | Verified fixture |
| 5 | program_language_fit | supplied language vs instruction language | Verified fixture |
| 6 | tuition_scenario | annual/program cost gap after confirmed aid | Verified fixture |
| 7 | scholarship_eligibility | preliminary match, mismatch, unknown facts | Verified fixture |
| 8 | document_inventory | missing confirmed documents | Verified fixture |
| 9 | recommender_timeline | date to request by for a supplied lead time | Verified fixture |
| 10 | essay_prompt_matrix | lexical evidence candidates for prompts (no drafted prose) | Verified fixture |
| 11 | essay_overlap | pairwise lexical overlap of student-owned drafts | Verified fixture |
| 12 | word_limit | exact whitespace word count, remaining/over-limit | Verified fixture |
| 13 | activity_evidence | missing confirmation, source or description per activity | Verified fixture |
| 14 | interview_question_bank | evidence-seeking practice questions, never answers | Verified fixture |
| 15 | application_status | rollup and pending review list | Verified fixture |
| 16 | decision_comparison | net annual cost for confirmed offers, no recommendation | Verified fixture |
| 17 | visa_checklist | flags requirements lacking an official URL | Verified fixture |
| 18 | source_freshness | supplied checked dates beyond supplied threshold | Verified fixture |
| 19 | source_domain_check | HTTPS/domain parsing, never certifies an official claim | Verified fixture |
| 20 | privacy_minimization | flags common sensitive fields before sharing | Verified fixture |

"Verified fixture" means a focused test exercises the logic, not live acceptance at universities or government sites. These are narrow helpers, not a complete end-to-end admissions workflow. Student-provided status/category/source claims are not independently verified.
