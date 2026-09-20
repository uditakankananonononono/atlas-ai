# Data connectors

Atlas is free-first. The default scholarship crawler indexes only the configured public site registry with a clear user agent, same-domain links, pacing, deduplication, and hard stop on 403/429. The free Instagram adapter uses Instaloader anonymously for public profiles only, at least 8 seconds between accounts, limited post depth, and stops on login, challenge, or throttle signals. It never rotates identities, proxies, or user accounts.

Gmail uses the owner's Google OAuth connection. Discord uses only a bot the owner controls and has invited to the relevant servers. YouTube uses its standard free API quota. Apollo and Hunter use their free tiers where the current account permits. X's official API, Apify, and Bright Data remain optional disabled connectors; Atlas does not depend on them.

Every connector is allow-listed in `app.collectors.registry`, configured in `config/collection_connectors.json`, normalized to durable tenant-scoped collected records, deduplicated by content hash, and logged with requests and configured cost. Keys come from deployment secrets and are never stored in registry JSON.

Pinterest supports the official v5 board-pin API under the user's authorized app and a separate free public-board indexer. The public indexer accepts explicit Pinterest board URLs, waits at least five seconds between boards, limits pin depth, and stops on 403/429 rather than evading controls.

The Gmail route explicitly includes LinkedIn updates, X/Twitter digests and "posts you missed" mail, plus creator newsletters. Each message is classified (`linkedin_digest`, `x_digest`, or `creator_newsletter`), preserves the source email, and extracts linked content for downstream opportunity and relationship analysis.

Named LinkedIn creators are managed in `config/linkedin_creator_sources.json`. The free collector is no-login and robots-aware, reads only publicly rendered post/article links, waits at least ten seconds between creator pages, caps depth, and stops on 403/429. If robots.txt does not affirmatively allow a page, Atlas skips it. It does not crawl connections, authenticated search, private content, or use evasion.

Interest discovery is separate from tracking. Editable seeds in `config/discovery_interests.json` start with computational biology, AI agents, illustration, college applications, and entrepreneurship. Slow no-login public-web searches find LinkedIn, X, and Instagram profiles/posts. Every candidate is staged tenant-by-tenant with the matching topic, source URL, and excerpt. Duplicates merge evidence. Nothing is deeply tracked until the owner approves the candidate, after which Atlas promotes it into the matching collector registry. Blocks/challenges stop the run.
