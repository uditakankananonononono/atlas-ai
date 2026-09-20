# Architecture

Phase 1 is a modular monorepo foundation: Next.js dashboard shell, FastAPI gateway, a deterministic planner, a shared module registry, and the first approval boundary. PostgreSQL/pgvector and Redis are defined in Compose; persistence, Celery workers, SSE, auth, encrypted BYOK vault, and provider adapters follow after their contracts and threat model are agreed.

## Safety and compliance decisions

- External communication, publishing, submission, deletion, and payment must enter Module 0 before execution.
- Provider credentials are BYOK and must be encrypted per tenant. No provider secret belongs in source, logs, prompts, or analytics.
- Official APIs, RSS, licensed datasets, user-authorized browser sessions, and site-permitted automation replace self-bots, unofficial TikTok wrappers, rotating residential proxies, and stealth/evasion techniques.
- Plans expose summaries, evidence, state, and failure logs. Private hidden model reasoning is not stored or displayed.
- Every autonomous loop will have step, time, cost, and retry budgets with explicit stop conditions.
