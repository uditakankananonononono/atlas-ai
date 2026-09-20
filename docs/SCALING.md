# Collection scale and run-rate controls

Atlas does not hard-cap the source universe at 500,000 accounts or 10,000 keywords. The database and distributed queue use source rows, priority indexes, batched dispatch, content-hash dedupe, and horizontally scalable Celery workers. Scale comes from worker count, provider quotas, cadence, and budget, not a code loop.

## Collector types

- `official_api`: preferred, quota/cost-aware, provider-authenticated
- `rss`: cheap periodic feed reads with conditional requests
- `public_page`: only when terms/robots allow, rate limited
- `authorized_session`: owner's account, human-speed, a few checks/day by default, full cadence logging, immediate challenge/throttle stop
- `webhook`: push-first source, near-zero polling

Each source has priority (0-100), cadence seconds, daily request cap, cost per 1,000 requests, next-run time, throttle-until time, and JSON adapter config. The scheduler dispatches due sources every minute; workers fan out horizontally. Records dedupe on tenant + SHA-256 content hash. Run rows record requests, new records, estimated cost, duration, and outcome.

## Conservative defaults and scale dials

Authenticated browser sources default to 3 checks/day. RSS defaults to hourly. Webhooks do not poll. Official APIs use the quota and cadence selected for that account. Operators can raise worker replicas and queue throughput without changing collector code. Before a high-scale run starts, the dashboard must show estimated daily requests and daily/monthly cost.

Provider tiers change. Atlas stores pricing as configuration and never hard-codes a remembered price as current truth. X API access, LinkedIn partner APIs, Instagram Graph API, YouTube Data API, Semantic Scholar, Kaggle, GitHub, and other providers each unlock only their documented endpoints and quota. The operator must enter the current tier/quota/cost from the provider's live account page before enabling a metered collector. Higher X tiers typically unlock more posts/reads and greater throughput; they do not authorize prohibited collection or bypass account/content restrictions.

## 500k-account ambition

At 500,000 sources, even one daily request is 15 million requests/month. Browser automation is neither safe nor economical at that scale. The viable mix is webhooks, bulk/licensed feeds, official APIs, RSS, and partner data agreements. User-authorized browser collectors remain a small high-value tier. Partner-network access to RippleMatch, RaiseMe, Bold.org, Fastweb, Simplify, Devpost, ChallengeRocket, and similar platforms is a business roadmap item; until agreements exist, Atlas operates the owner's accounts through the Browser Agent rather than cloning their systems.

Unstop credentials are deferred per owner request. Its collector stays parked until enabled later.
