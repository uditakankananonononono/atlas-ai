# M01 public discovery: bounded first-slice contract

Date: 2026-10-01. Baseline: main 313309b. Status: candidate, independent audit pending.

## Acceptance

The 17 student registry routes remain present. A launch-only route makes no
network request and has no fetched timestamp. A discovery route fetches its
single fixed public source with redirects disabled, stops on non-200 responses,
streams at most 2,000,000 decoded bytes, and never follows application links.
Each returned item includes source URL, fetched UTC timestamp, SHA256 of fetched
source bytes, normalized deadline value/precision/stated timezone, source
eligibility evidence with a null personal verdict, and explicit unknowns.

Only explicit deadline cues are transcribed. Posting and event dates are not
deadlines. Missing timezone stays null; date-only values are not UTC instants.
Conflicting, malformed or unsupported dates stay unknown. Eligibility sentences
and the public list's exact legend are evidence, not a classifier or permission
to apply. No arbitrary match score, prediction, fixed probability, paid model or
third-party AI call occurs in this surface. Query is literal substring search;
results preserve source order. This is an intentional API behavior change from
legacy token-cosine ranking; consumers must not expect `score`.

## Requested seven plus ten: reconciliation

| Registry ID | Source route | Current boundary |
|---|---|---|
| ripplematch | https://ripplematch.com/ | Launch only; public profile marketing is not account matching or auto-apply |
| simplify | https://github.com/SimplifyJobs/Summer2027-Internships | Public community internship README; NOT simplify.jobs scraping, extension execution or autofill |
| raiseme | https://www.raiseme.com/ | Launch only; account portfolio/micro-scholarships not read |
| bold | https://bold.org/scholarships/ | Launch only; earlier rate-limit challenge is not circumvented |
| fastweb | https://www.fastweb.com/college-scholarships | Existing public title/link discovery, local personal noncommercial use only; no redistribution/cache license inferred |
| devpost | https://devpost.com/hackathons | Launch only; current terms forbid automated scraping/crawling, no undocumented API |
| challengerocket | https://challengerocket.com/hackathons-and-challenges.html | Existing public cards only; no new detail crawler; site-wide terms not located in this research, permission remains unverified |
| mlh | https://www.mlh.com/seasons/2026/events | Existing public event links only; 2026 URL is not automatically advanced to another season |
| internshala | https://internshala.com/internships/ | Downgraded to launch only; terms prohibit extraction for AI/RAG without prior written consent |
| scholarships360 | https://scholarships360.org/feed/ | Existing editorial feed, not complete scholarship catalog |
| unigo | https://www.unigo.com/scholarships | Launch only; no validated public catalog adapter |
| scholarshiproar | https://scholarshiproar.com/feed/ | Existing RSS; fixture execution is not current whole-catalog verification |
| scholarshipregion | https://www.scholarshipregion.com/feed/ | Existing RSS; no personalized eligibility claim |
| opportunitiesforafricans | https://www.opportunitiesforafricans.com/feed/ | Existing RSS; geography mentions are not a personal verdict |
| scholarshipunion | https://scholarshipunion.com/feed/ | Existing RSS; incomplete snippets explicitly unknown |
| opportunitiesforyouth | https://opportunitiesforyouth.org/feed/ | Existing RSS, no detail-page verification |
| kaggle | https://www.kaggle.com/competitions | Launch only; no anonymous API invented |

The Simplify fetched URL is fixed to the public raw README on its actual `dev`
branch: https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/README.md .
It is a maintained, explicitly shared community list, not an open-source license
claim about Simplify's proprietary extension. Application URLs are outputs only.
Closed rows are excluded. Repository legend markers are copied, not interpreted
as successful eligibility checks. The listing cycle is explicitly Summer 2027.

## Original blueprint versus additions

Doc1 requests the seven named platforms plus ten free/student-friendly platforms.
The 17 registry IDs above satisfy naming coverage, not 17 working integrations.
Doc2's original M01 list is a different set: Kaggle RSS, Devpost API, Unstop,
Opportunity Desk, Opportunities for Youth, Snowday, Hack Club, GitHub Topics,
LinkedIn, Instagram, X, two Reddit communities, Discord, and custom webhooks.
Opportunity Desk/Youth and several RSS/API implementations exist in the separate
legacy service. Their existence does not establish current policy compliance or
live correctness. Snowday/Hack Club named capability helpers are not verified
public discovery adapters. Social accounts, webhooks and licensed APIs are
outside this slice. Discord self-bots are not a supported route. No statement in
a source document authorizes paid APIs, account access or application submission.
The DeBERTa eligibility classifier, trained awarded/declined impact model,
persistent embeddings, PostgreSQL integration, hourly crawl, SSE and PC deployment
are not implemented or certified by this patch.

## Research sources and decisions

- https://simplify.jobs/terms : prohibits automated extract/harvest/scrape absent
  explicit owner permission. Robots allow public paths but do not override terms.
- https://simplify.jobs/robots.txt : excludes account/private paths.
- https://github.com/SimplifyJobs/Summer2027-Internships : maintained by Pitt CSC
  and Simplify, explicitly shared tracking list, contribution guidance and legend.
- https://www.fastweb.com/terms : personal noncommercial copy allowance;
  copying/republication/redistribution including caching requires prior consent.
- https://www.fastweb.com/robots.txt : member/new paths disallowed.
- https://devpost.com/terms : prohibits manual/automated scraping/crawling.
- https://devpost.com/robots.txt : permissive generic robots does not override terms.
- https://internshala.com/terms/ : no extraction for AI systems/RAG without prior
  written consent. Existing adapter disabled, not worked around.
- https://challengerocket.com/hackathons-and-challenges.html : public challenge
  cards observed; site-wide terms not located, not interpreted as permission.
- https://challengerocket.com/robots.txt and
  https://scholarshiproar.com/robots.txt : inspected; robots alone is not a grant.
- https://ripplematch.com/ , https://www.raiseme.com/ ,
  https://bold.org/scholarships/ , https://www.unigo.com/scholarships and
  https://www.kaggle.com/competitions : own pages inspected for launch boundaries,
  not treated as evidence of working account integrations.

Policy observations are time-specific. Remaining existing sources have not all
received a complete current policy audit. This patch adds only the explicit
public shared GitHub-list adapter. It does not certify wholesale scraping rights.
No vendor prose or full catalog is bundled as a product feature. Offline fixture
is one small source-shaped row for parser regression; synthetic fixtures are tests,
never runtime fallback results. No source error returns fabricated listings.

## Reproduction and limits

Python 3.12, pytest, httpx, beautifulsoup4. Runtime student discovery imports no
legacy service, database or model provider. Run:

```sh
python -m pytest tests/modules/test_m01_student_platforms.py \
  tests/modules/test_m01_student_intelligence.py \
  tests/modules/test_m01_student_evidence.py -q
```

Live smoke is deliberately opt-in (`ATLAS_M01_LIVE_SMOKE=1`) and must be scoped to
sources whose present policy permits the intended use. One successful fetch is
not completeness, durable permission or scale proof. No recurring scraping is
scheduled. Full repo gates and independent adversarial audit are separate.

## API compatibility audit (follow-up)

Repository search of frontend and backend consumers found no frontend use of
student-platform `/discover` scores or student `deadline.evidence`. Legacy generic
opportunity scores in ranking/service and expanded-spec helpers are a different
API and remain unchanged. In-repo student tests were updated for the intentional
schema change. External clients have not been inventoried.

Breaking changes for this candidate: `/student-platforms/{id}/discover` no longer
returns `score`; query is literal substring filtering, not token ranking.
`/student-insights` deadline evidence can be a list of source statements rather
than one string. Clients must accept a list, nullable value/timezone, explicit
precision and unknowns. No production deployment or migration is implied.

Fetch timing: 15-second elapsed budget is checked before opening, between decoded
body chunks and after stream completion, with 5-second connect / 1-second read
idle timeouts. This is a cooperative elapsed cap, not guaranteed hard cancellation
of a transport blocked inside header parsing or an injected custom transport.
No hard wall-clock isolation claim is made; this remains an audit limitation.
Eligibility statements are sentence-bounded with dotted initials protected;
600-character excerpt truncation is explicitly flagged. Company-cell eligibility
markers are not asserted for inherited child rows; applicability stays unknown.

## Second audit follow-up: deliberately strict transcription

Date-only acceptance now requires all suffix text up to the next explicit
 deadline cue to be punctuation/whitespace only. Any unexplained token, including
 a newline-separated clock or a later prose sentence, makes the value unknown.
This is conservative abstention, not an NLP interpretation of prose. Mixed
listing text may therefore yield fewer usable dates. Tests move separate award
and eligibility statements before a terminal deadline and separately assert
that a trailing unknown token causes abstention; no assertion is weakened to
allow a wrong first-date answer. Calendar/partial-date extensions conflict.
Sept/Sept. normalize to September. Fraction precision above six digits is
unsupported and explicitly labeled; lowercase ISO t/z and compact numeric
offsets are supported. Unsupported deadline syntax has its own reason code.

Eligibility evidence retains a sentence-bounded quoted excerpt and separately
`source_context`/`source_contexts` (up to 600 source characters per context).
Any excluded context has `eligibility_context_boundary_unknown`; an actual
source context longer than 600 has `eligibility_evidence_truncated`. No claim
that subsequent sentences/newlines are irrelevant. Dotted initials and common
honorifics are protected in sentence boundaries, but this is not full semantic
eligibility interpretation. All deadline.evidence outputs, including direct
student-intelligence annotation, are now lists. No old string-producing path
remains on this student surface. External clients still need the documented
breaking-schema migration.

The timing cap remains cooperative. Independent mock stalled 25 seconds inside
a single chunk, proving it is not a hard 15-second wall-clock cap. Socket idle
timeouts do not constrain injected transports. No process isolation implemented.

## Third audit follow-up (supersedes whole-tail rule above)

Status remains candidate. Offset fields are validated before ISO parsing:
absolute hours <=14, minutes <60, and hour 14 requires minute 00. Invalid values
are unknown, never silently normalized. Unsupported precision remains explicit.
RSS/Atom text is no longer truncated before extraction: the full sanitized text
within the fetched 2 MB source is examined; returned description is still bounded
at 600, with original length and truncation flag. Eligibility contexts retain
their own explicit limits. Thus display truncation is not evidence truncation.

Suffix acceptance uses Unicode whitespace or Unicode P-category punctuation,
not a blacklist of words. Symbols/emoji/Unicode mathematical minus are unknown.
Mixed-prose dates now stop at a punctuation-separated, explicitly labeled
unrelated field (Award, Prize, Eligibility, Posted, Location and the listed
eligibility cue forms). Any later calendar date/extension is checked for conflict
before that boundary. Other unexplained suffix tokens abstain. All four original
mixed-prose date-filter/breakdown/refine fixtures are restored unchanged in fact
order and must pass. This is a narrow field-boundary grammar, not an unrestricted
semantic claim that following prose is unrelated.

Safe English grammar now includes dotted months, ordinal days, day-first named
months, explicit-year dates, whitespace inside named dates, close on/deadline is,
and submissions/applications due by. Locale-ambiguous numeric dates, missing-year,
rolling, multilingual text, ambiguous named timezones and colloquial clock
phrasing remain unsupported. Spaced single initials before a surname are
protected in eligibility excerpts. Other abbreviations can still require manual
inspection of the retained context.

The independent auditor's prior 22/56 (39.3%) result describes its purpose-authored
coverage corpus on 6d97f6a, not sampled production recall. No production recall,
precision, complete source coverage or durable policy permission is established
by these tests. No new live fetch or account action in this follow-up. D6 remains
cooperative timing only, with the blocked-chunk counterexample disclosed above.

## Fourth audit follow-up

Unrecognized qualifier words before a deadline cue cause abstention with
`qualified_or_negated_deadline`; only the/application/submission forms are
whitelisted. This rejects early-bird, registration, previous/year-specific and
negated cues rather than asserting the wrong deadline category. Past calendar
dates are preserved as source dates, not silently advanced; existing expired
filters hide them when requested. They are not asserted to be current cycle dates.

Eligibility supported cues include must-be, only-X-may-apply, restricted-to,
available-to, not-open-to, minimum-GPA and requirements. When nothing matches,
the reason is now `eligibility_not_found_by_supported_cues`, never a claim that
the listing contains no eligibility text. Later context restrictions remain
flagged and available within explicit context limits. RSS HTML block boundaries
are retained; queries inspect the same full sanitized text as extraction, while
display description remains bounded. No separate live scan is implied.

The independent fresh-corpus ~47% figure is corpus coverage, not production
recall. No measured production recall or broad semantic extraction claim is made.
Named clock/timezone prose, weekday/date disagreements and numeric locale grammar
remain outside this slice unless specifically supported by a test. Date-only
values do not assert an instant or complete eligibility. Publication remains held.
