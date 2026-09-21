# Module 18 integration
Mount `spec.router`; inject official Reddit/YouTube adapters, existing public Pinterest collector and public-web discovery. Add tenant-scoped PostgreSQL blueprint/event repositories and optional Google Trends-compatible licensed trend provider. No unofficial TikTok API, proxy rotation, login-driven Instagram scraping, income promises or automatic purchases. Acceptance: source links survive extraction, scam signals influence analysis, score explanation and sensitivity cases are present, and duplicate fingerprints are tenant scoped.

## Shipped collector configuration

`routes.get_service()` now wires Reddit public JSON, Hacker News Algolia and dev.to by default. Optional collectors are enabled only when their owner-supplied configuration is present:

- `ATLAS_YOUTUBE_API_KEY`: official YouTube Data API v3.
- `ATLAS_PINTEREST_ACCESS_TOKEN`: official Pinterest API v5.
- `ATLAS_X_BEARER_TOKEN`: official X API v2. Meaningful X read access is generally a paid X tier, so it is never a free-profile dependency.
- `ATLAS_INSTAGRAM_GRAPH_TOKEN`: official Graph/oEmbed flow for owner-provided public post/Reel links. It does not crawl feeds or bypass login.
- `ATLAS_M18_RSS_FEEDS`: comma-separated verified HTTPS feeds.
- `ATLAS_M18_PUBLIC_URLS`: comma-separated robots-permitted public URLs.

Missing optional credentials produce `collector_not_configured:<platform>` in collection reports. No credential is hardcoded or persisted by this module. Login-driven Pinterest, X and Instagram scraping remains refused.

## Step-by-step experiment runner

The runner creates five concrete artifacts: landing-page draft, listing draft, outreach draft, capped budget plan and measurement checklist. Preparation is reversible. Publishing, sending and spending are separate exact action payloads submitted one-by-one to Module 0. Approval creates a one-shot permit only; it does not claim an effect happened. A configured official effect adapter must consume the permit and report the real result.
