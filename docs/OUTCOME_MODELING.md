# Outcome modeling and source provenance

Win-chance training is disabled until enough real labeled outcomes exist. Accepted evidence sources are official competition winner pages/announcements, official APIs, YouTube Data API records from official channels, and Atlas users' own recorded applied/won/lost outcomes. Every training row keeps its source URL/type/record ID and observation time. Every prediction must persist the exact evidence IDs and model version used, and present the evidence list with the prediction.

No synthetic winners, inferred labels, scraped private profiles, or fabricated training examples are allowed. A minimum sample, holdout policy, calibration report, and versioned feature definition must be approved before a predictive model can activate. Until then Atlas may show descriptive similarities and eligibility/match scores only, never a claimed probability of winning.

Login-gated sources such as Unstop may be collected only through a user-authorized browser session, at a logged/configurable human-speed cadence of a few checks per day. Stop and back off on throttling or challenges. Credentials remain in the vault and never enter datasets or logs.
