# Atlas free-tier deployment

## Topology

| Atlas boundary | Free placement | Runtime behavior |
|---|---|---|
| Next.js UI and GitHub login | Vercel Hobby | Supabase Auth completes GitHub OAuth. The browser keeps the short-lived access token and the Vercel same-origin rewrite forwards API traffic to Render. |
| FastAPI control plane | One Render free web service | Runs API and synchronous bounded work. The service can sleep when idle and the first request after sleep is slow. |
| Durable relational/vector data | Supabase Free Postgres with `vector` extension | Render uses the transaction-pooler URL with TLS. Alembic creates the complete schema. Supabase Auth JWTs are verified against its OIDC discovery/JWKS endpoint. |
| Queue, cache, rate state | One Upstash free Redis database | TLS Redis URL. Celery is configured, but no always-on free worker is claimed. Short jobs stay synchronous; queued/background jobs are disabled until a worker is available. |
| Ollama inference | Owner PC only | No public inbound port, tunnel, or credential relay. Cloud deployment reports local Ollama unavailable unless the owner is actively using the paired-PC execution path. |
| Files | Supabase Storage Free, private buckets | Use signed, expiring URLs. Cloud Storage/GCS adapter stays disabled in this profile. |
| Scheduling | Supabase cron/Render endpoint only for essential bounded jobs | APScheduler inside a sleeping free web process is not reliable and is disabled for guarantees. |
| Telemetry | Render/Vercel logs plus Supabase dashboard | Cloud OTel/Grafana collectors are omitted on the $0 profile. Local metrics remain available in development. |

## Disabled or reduced at $0

- No Celery worker, RabbitMQ, Selenium Grid, Browserless farm, Kubernetes, Istio, Vault cluster, GCS, Grafana, or always-on scheduler.
- No cloud Ollama or GPU workload. Model calls that require the owner's PC fail plainly when that paired path is offline.
- Live dashboard refresh uses authenticated 30-second polling because native `EventSource` cannot attach the bearer token.
- Render cold starts and provider quotas are expected. This profile is for owner-driven use, not uptime or scale acceptance.
- Billing remains implemented product code, but paid checkout is disabled until the owner chooses a payment provider and explicitly enables it.

## Deployment order

1. Create Supabase, enable GitHub Auth, copy the transaction-pooler URL, project URL and anon key.
2. Create Upstash Redis and copy its TLS `rediss://` URL.
3. Deploy Render from `render.yaml`; enter secrets. The container startup validates configuration and runs `alembic upgrade head` before serving.
4. Deploy Vercel with repository root and `vercel.json`; enter the three frontend variables from `.env.free-tier.example`.
5. Add the final Vercel callback URL to Supabase Auth redirect allow-list and the Supabase callback URL to the GitHub OAuth app.
6. Sign in with GitHub, load `/api/v1/modules`, create a low-risk record, restart Render, and verify it persists.

## Her hands versus automatable work

### Owner must do

- Sign in to Vercel, Render, Supabase and Upstash with GitHub, accept their terms, and select only plans showing $0 with no card.
- In Supabase: create the project and a private Storage bucket; enable GitHub provider; copy project URL, anon key and transaction-pooler connection string. Do not paste the database password into chat or commit it.
- In GitHub: create/approve the OAuth app requested by Supabase and copy client ID/secret directly into the Supabase dashboard.
- In Upstash: create one free Redis database and copy the TLS Redis URL directly into Render.
- In Render: approve repository access, create the Blueprint, and enter secret environment variables.
- In Vercel: approve repository access, import the project, and enter frontend environment variables.
- After Vercel assigns the final hostname, add it to Supabase's allowed site/redirect URLs.
- Keep Ollama on the paired PC; do not expose port 11434 publicly.

### We can do after those approvals

- Validate configuration, migrations, health/readiness, OIDC issuer/audience, API proxying and signed-in requests.
- Run the blank-DB migration test and deployment smoke tests.
- Diagnose build logs, patch deploy config, and verify persistence/cold-start behavior.
- Keep secrets out of source control and rotate any value accidentally exposed.

## Sources checked

- Render free services: https://render.com/docs/free
- Supabase pricing: https://supabase.com/pricing
- Upstash Redis pricing: https://upstash.com/pricing/redis
- Vercel Hobby plan: https://vercel.com/docs/plans/hobby
