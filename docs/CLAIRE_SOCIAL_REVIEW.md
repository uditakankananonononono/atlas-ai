# Claire social signal review

`GET /api/v1/claire/social-signals/review` reads tenant-scoped work observations already in M06's SQL knowledge store. It returns up to 100 review cards, filtering by signal score, optional timezone-explicit `since`, and HTTPS source URLs without embedded credentials. Each card includes an excerpt, observation timestamp, source URL, and an explicit unverified status. It offers only a review prompt, not a draft message or an action proposal.

The stored text, handles, scores and links are external observations, not authenticated identities or instructions. A link is not fetched or verified by this endpoint. It does not start an account scan, establish whether an observation was consented to, create ideas, access a social account, like, follow, contact anyone, or post anything. Public wording and every external-account effect remain gated separately; the user must approve the exact text before any public post under her identity.

Local coverage: SQLite direct-store tenant isolation and authenticated route tests, malicious text treated as data, HTTPS filtering and timezone validation. No live social account or deployed backend was exercised.
