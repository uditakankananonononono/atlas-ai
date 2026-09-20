# Required environment configuration

Atlas never ships real credentials. Copy the relevant names into the deployment secret store and provide values for the features you enable. Empty or example values are not usable credentials.

## Platform services

| Variable | Required when | Value shape |
|---|---|---|
| `ATLAS_DATABASE_URL` | Every durable deployment | SQLAlchemy URL. Use PostgreSQL in production. |
| `ATLAS_REDIS_URL` | Celery workers, beat, and Redis events | Redis URL, including deployment password/TLS settings. |
| `ATLAS_TOKEN_KEY` | Encrypting stored OAuth tokens | Deployment-generated random secret, at least 32 bytes. |
| `ATLAS_API_KEY_ENCRYPTION_KEY` | Encrypted per-user provider credentials | Deployment-generated 32-byte base64 key. |
| `POSTGRES_PASSWORD` | Bundled PostgreSQL container | Deployment-generated database password. |
| `REDIS_PASSWORD` | Bundled Redis container | Deployment-generated Redis password. |

Set `ATLAS_ENV=production` outside local development. Set worker concurrency and API worker counts to the deployment's capacity; these are tuning values, not secrets.

## Model and embedding providers

At least one configured model provider is required for model-backed generation. Never put keys in source control.

| Variable | Provider or use |
|---|---|
| `OPENAI_API_KEY` | OpenAI generation and OpenAI embeddings |
| `ANTHROPIC_API_KEY` | Anthropic generation |
| `GEMINI_API_KEY` | Gemini generation |
| `ATLAS_OPENAI_MODEL`, `ATLAS_ANTHROPIC_MODEL`, `ATLAS_GEMINI_MODEL` | Optional model overrides |
| `ATLAS_EMBEDDING_PROVIDER` | `openai` or `ollama` |
| `ATLAS_OPENAI_EMBEDDING_MODEL` | Optional OpenAI embedding-model override |
| `ATLAS_OLLAMA_URL`, `ATLAS_OLLAMA_EMBEDDING_MODEL` | Required when local Ollama embeddings are selected |

## Email and Google

| Variable | Required when |
|---|---|
| `ATLAS_SMTP_HOST`, `ATLAS_SMTP_FROM` | Approved outreach delivery is enabled |
| `ATLAS_SMTP_PORT` | Optional SMTP port override, default `587` |
| `ATLAS_SMTP_USERNAME`, `ATLAS_SMTP_PASSWORD` | SMTP server requires authentication |
| `ATLAS_GOOGLE_CLIENT_ID`, `ATLAS_GOOGLE_CLIENT_SECRET` | Gmail OAuth mailbox sync is enabled |
| `ATLAS_PUBSUB_VERIFICATION_TOKEN` | Gmail Pub/Sub webhook sync is enabled |
| `GOOGLE_OAUTH_ACCESS_TOKEN` | Google-backed grounding or configured Google collectors use a service token |

## Billing

| Variable | Required when |
|---|---|
| `STRIPE_SECRET_KEY` | Stripe-backed billing is enabled |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook ingestion is enabled |

Keep Stripe in test mode until production billing is separately reviewed and approved.

## Official APIs and enrichment

These are required only for the matching adapter. Leave an adapter disabled when its credential is absent.

- `YOUTUBE_API_KEY`: official YouTube Data API.
- `HUNTER_API_KEY`: Hunter email verification/finder.
- `CLEARBIT_API_KEY`: Clearbit enrichment.
- `APOLLO_API_KEY`: Apollo enrichment collector.
- `CORE_API_KEY`: CORE open-access API.
- `SEMANTIC_SCHOLAR_API_KEY`: higher-quota Semantic Scholar requests.
- `NCBI_API_KEY`: higher-quota NCBI E-utilities requests.
- `GITHUB_TOKEN`: authenticated GitHub public API requests.
- `PINTEREST_ACCESS_TOKEN`: official Pinterest API.
- `APIFY_API_TOKEN`: user-configured Apify jobs.
- `BRIGHT_DATA_API_TOKEN`: user-configured Bright Data jobs.
- `X_BEARER_TOKEN`: collector-level X API access.

## Social publishing APIs

Provide only the official API credentials for platforms enabled in Module 6:

- `ATLAS_META_ACCESS_TOKEN` and `ATLAS_META_IG_USER_ID`
- `ATLAS_X_BEARER_TOKEN`
- `ATLAS_LINKEDIN_ACCESS_TOKEN` and `ATLAS_LINKEDIN_ORG_ID`
- `ATLAS_TIKTOK_ACCESS_TOKEN`

Every publish action remains subject to Atlas's exact-preview approval gate even when credentials are configured.

## Deliberately unsupported credential paths

Do not configure Discord user tokens or self-bot credentials. Atlas permits only official bot/API integrations that comply with platform rules; login-driven mass scraping, evasion, fake accounts, and credential invention are outside the product boundary.
