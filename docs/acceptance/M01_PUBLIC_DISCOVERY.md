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
