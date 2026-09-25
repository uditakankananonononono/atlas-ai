# Integration
Mounted through `spec.router` (`/api/v1/tools-hub`). Candidate discovery is read-only. Legacy in-memory installation proposals redact secret/token-like config and require Module 0 approval.

Installation runs through the durable pipeline in `pipeline.py` (routes in `pipeline_routes.py`, prefix `/api/v1/tools-hub/pipeline`):

0. Optional discovery: `POST /discoveries {query}` persists ranked candidates (`GET /candidates`). `POST /candidates/{id}/proposals {version?, entrypoint?, permissions?}` fetches the PyPI wheel / npm tarball, checks the registry digest, and continues at step 1 automatically. GitHub-only candidates are refused (no published digest).
1. `POST /proposals` with `artifact_base64` (ZIP) + `manifest` - scans first, stores bytes content-addressed, submits a Module 0 `integrate_tool` approval binding the install subject.
2. After a human approves in Module 0: `POST /proposals/{id}/install-jobs` queues one job.
3. The Celery beat task `atlas.m22.drain_install_jobs` (or `POST /jobs/{id}/run`) runs it: approval re-check, hash re-check, re-scan, then `ToolInstaller.install` with a single-use grant. The installer writes the receipt.
4. `GET /portfolio` lists active installs (`?include_history=true` for superseded/rolled back).
5. Smoke-run (optional, approval-gated): `POST /installs/{operation_id}/smoke-proposals` -> approve `smoke_run_tool` -> `POST /installs/{operation_id}/smoke-jobs {approval_id}`; the worker runs it and stores evidence under `portfolio[].smoke`. Runner: M4's `SandboxBackend` for Python when merged, else bundled bubblewrap (`smoke.py`); the worker image needs `bwrap` (and `node` for npm tools). `ATLAS_SMOKE_BACKEND=bundled` pins the bundled runner.
6. Rollback: `POST /installs/{operation_id}/rollback-proposals` -> approve `rollback_tool` in Module 0 -> `POST /installs/{operation_id}/rollback-jobs`.

Config: `ATLAS_TOOLS_ROOT` (default `/tmp/atlas-tools`) holds artifacts, per-tenant installs, backups, receipts and consumed-grant state. Tables: `m22_tool_candidates`, `m22_install_proposals`, `m22_install_jobs`, `m22_tool_portfolio`.

## Discovery sources (`sources.py`, verified live 2026-09-25)

All free, all public endpoints, no account or key required unless noted. Discovery fans out concurrently; a source that fails is skipped and recorded in `Service.last_errors` (and `GET /tools-hub/sources`), it never sinks the rest.

| collector | kind | endpoint | notes |
|---|---|---|---|
| github | repository | `api.github.com/search/repositories` | pre-existing |
| gitlab | repository | `gitlab.com/api/v4/projects?search=` | recency-scored from `last_activity_at` |
| codeberg | repository | `codeberg.org/api/v1/repos/search` | Gitea API; archived repos score 0.1 |
| devto | blog | `dev.to/api/articles?tag=` | official Forem API; tag-scoped (query is slugified), not full-text |
| wordpress | blog | `public-api.wordpress.com/rest/v1.2/read/search?q=` | WordPress.com Reader full-text search; HTML stripped from excerpts |
| hackernews | article | `hn.algolia.com/api/v1/search` | official Algolia HN API; Ask-HN style items fall back to the news.ycombinator.com item URL |
| medium | blog | `medium.com/feed/tag/{tag}` | RSS tag feeds via the shared feed parser |
| itunes | podcast | `itunes.apple.com/search?media=podcast` | Apple Search API; candidate evidence carries the show's `feed_url` for `feed_collector` follow-up |
| podcastindex | podcast | `api.podcastindex.org/api/1.0/search/byterm` | OPTIONAL keyed free tier; only registered when `ATLAS_PODCASTINDEX_API_KEY` + `ATLAS_PODCASTINDEX_API_SECRET` are set, signed per the Podcast Index auth spec |

Any blog or podcast RSS/Atom feed integrates through `feed_collector(url)`: it streams the response and stops after 20 items (multi-MB podcast feeds are never read in full), rejects non-https URLs, and marks entries with an audio enclosure `podcast-episode`, otherwise `blog`.

Deliberately excluded after live verification: Bitbucket (its 2.0 API no longer hosts unauthenticated global search; the endpoint 404s) and Gitee (search API returns 200 with empty results for every query tried without credentials).

Phase-2 capabilities (all tested in `tests/modules/test_m22_phase2_features.py`; network-facing ones also smoke-run live 2026-09-25):

1. Kind-filtered discovery: `POST /discoveries {"query", "kinds": ["repository"|"blog"|"article"|"podcast"|"podcast-episode"|"package"|"tool"]}` queries only matching collectors.
2. Per-source run stats (runs/failures/candidates/latency/status) on `GET /tools-hub/sources`.
3. Failure cooldown: a source that errors is skipped for `ATLAS_M22_SOURCE_COOLDOWN_SECONDS` (default 300) and reported as cooling down, instead of being retried every query.
4. Feed autodiscovery (`discover_feeds(url)`, `POST /feeds/discover`): parses feed <link> tags, verifies each advertised URL actually serves a feed (Blogger-style self-referencing links are rejected), then probes well-known paths (/feed, /rss.xml, /feeds/posts/default, ...). https only.
5. OPML import: `parse_opml` / `collectors_from_opml` / `POST /feeds/opml/parse`; non-https feeds are skipped.
6. OPML export: `feeds_to_opml` / `POST /feeds/opml/build`.
7. Canonical dedup keys: tracking params (utm_*, fbclid, gclid, mc_*) stripped, host lowercased, default ports and fragments removed.
8. Score explanation: `Candidate.explain()` / `GET /candidates/{id}/explain` shows value x weight = contribution per signal.
9. GitHub maintenance score now uses push recency (`pushed_at`), matching GitLab/Codeberg, instead of a flat 0.8/0.1.
10. Feed entries carry guid, published date, itunes duration and enclosure byte length in evidence.
11. iTunes podcast-episode search collector (`itunes-episodes`, entity=podcastEpisode; verified live).
12. Batch discovery: `POST /discoveries/batch` (up to 20 queries), per-query results plus one deduped ranked merge.
13. Custom scoring weights per request (`weights` on /discoveries and /discoveries/batch; validated signal names, non-negative, non-zero total).
14. Runtime blocklist: `GET/POST /blocks/...` adds/removes domains and patterns, persisted to `<ATLAS_TOOLS_ROOT>/m22_blocks.json` so blocks survive restarts.
15. Candidate export: `GET /candidates/export?format=json|csv|markdown`.
16. FeedWatcher (`POST /feeds/poll`): returns only entries not seen before; cursors persist in `<ATLAS_TOOLS_ROOT>/m22_feed_watches.json` (500 ids/feed cap).
17. Repository evidence refresh: `POST /candidates/{id}/refresh` re-fetches stars/forks/activity/license from GitHub/GitLab/Codeberg (GitLab project paths URL-encoded; verified live).
18. Query history (last 200): `GET /queries`.
19. Saved-query diffing: re-running a query reports added/removed candidates (`GET /discoveries/{query}/report`).
20. HTTPS-only enforcement: non-https candidate URLs are refused by default (`ATLAS_M22_ALLOW_INSECURE=1` opts out; feeds were already https-only).

Known limits: feed autodiscovery can only find feeds a site actually publishes (a moved/dead feed, e.g. a blog that removed its RSS, correctly yields none); cooldown/history/diff state is in-memory except the blocklist and watch cursors, which persist; batch discovery runs queries sequentially (each query's sources fan out concurrently).

Candidates carry a `kind` field (`tool` by default; `blog` / `article` / `podcast` / `podcast-episode` / `repository` / `package` from the collectors), persisted in the pipeline's `m22_tool_candidates.signals_json`. Discovery candidates remain read-only research leads; installs still go through the scanned, approval-gated pipeline above, and the registry installer still refuses sources without a registry-published digest.
