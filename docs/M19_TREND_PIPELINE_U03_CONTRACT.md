# M19 trend pipeline (U03) contract

Module: `backend/app/modules/m19_idea_incubator/trend_pipeline_u03.py` (new file). Tests: `tests/modules/test_m19_trend_pipeline_u03.py`.

## Existing mechanisms read first
- `m06 social_reading/idea_feed.py`: harvests term scores from collected posts into ideas.
- `m19 historical_ranking.py`: ranks ideas from history.
- `m06 analytics.py` trend: trends over metrics, not over terms in post text.
- `m20 calibration_predictor.py`: class-conditional calibration of predictions that are already resolved.
- `m20 strategy.py`: carries the "not investment advice" disclaimer.

## Exact delta
Nothing above is edited, wired, called or replaced. The new module adds one pure chain over posts the caller supplies:
posts -> measured trend candidates (recent window vs baseline window, stated growth formula, thresholds on posts and authors) -> templated idea candidates (human review required, never written to the incubator) -> persistence predictions with a caller-stated confidence -> scoring against later collected posts.
Scoring emits calibration-style records (same field names as a resolved record). No integration with m20 is claimed or tested.

## Functions
`extract_trends`, `ideas_from_trends`, `make_predictions`, `score_predictions`. Errors are `TrendError(ValueError)`, messages start with `TREND_U03: `.
Windows: recent = (as_of - recent_days, as_of]; baseline = the baseline_days before that. Posts after as_of are excluded and listed. A term counts once per post.
Scoring counts posts in (predicted_at, predicted_at + horizon]; fewer than 20 scored predictions carries a "too few" caveat.

## Limits
- Not investment advice. Does not predict markets, prices or business outcomes. No accuracy is promised.
- Measures term frequency in the supplied posts only. Sampling bias and bots are not detected.
- English, ASCII-token tokenizer.
- No collection, network, accounts, clock or model calls. No impersonation, no posting.

## Count-series input and calibration bins (`trend_counts_u03.py`, new file)
- `extract_count_trends(series, ...)`: same windows and growth formula as above, over rows `{term, date, count, source}` (for example an exported counts file). Terms are lowercased. A row set larger than 200000 is refused with `TREND_REFUSED_OVERSIZE`.
- `calibration_bins(records, bins=5)`: stated confidence against observed hit rate per bin, from records shaped like the ones `score_predictions` returns. Under 20 records it says so.
- Oversize refusals in `trend_pipeline_u03.py` also carry the `TREND_REFUSED_OVERSIZE` code.

## Not done on purpose
- Ideas are not written to the incubator and carry no score; scoring output is separate. Nothing is wired.
- No "strategy" output: any strategy text would be a claim this module cannot measure.
- No collection, scraping, ingest, checkpointing or resumption.

## Forecast-ledger adapter (`u03_j1_adapter.py`, new file) - prepared against an early call shape only
Written against an early interface note (keyword-only calls; prediction keys claim, probability, horizon, source, made_at). The ledger and scorer are NOT in this repository at the time of writing, so nothing here imports them, calls them or has been run against them. Final integration needs the landed, audited source and one real scored round trip.
- `to_j1_predictions(predictions, *, source)`: confidence -> probability, predicted_at -> made_at (UTC), horizon_days -> an absolute horizon deadline. Exact five keys, no extras. The term and threshold go into the claim text and a side map.
- `bind_ids(pending_result, returned)`: attaches the ids the ledger returns, matching on exact content; no match or an ambiguous match is refused.
- `resolutions_from_posts(bound, later_posts, *, resolved_at)`: outcome dicts only where the horizon has passed and posts were collected inside it. Too early, no posts in the horizon, or no later data: no resolution, listed as unresolved, never a miss. Window (made_at, horizon], end inclusive.
- No local Brier, hit rate or bins in this adapter; scoring belongs to the single scorer.
- Limit: U03 cannot tell whether the later-post collection was complete, and the scorer does not verify outcome truth.
