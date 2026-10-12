# E1: Claire journal retrieval, shipped lexical ranking vs supersession + recency

**Update for tip 8a79fc4 (read this first).** The tables below were scored against ef1f6af. Since then the journal landed fixes for both failure classes this experiment found (commits e2f5fb75 corrections supersede their originals; 78ef8557 equal-score topics rank newest first). Rerun of the identical script on 8a79fc4 is in `results_tip_8a79fc4.json`: the shipped ranker B0 now scores S1 top-1 0.995, S2 1.00, S3 0.987 with no stale entry ranked above the truth, i.e. it matches or beats every hybrid here, and H1's recency weighting is a net cost (S1 0.96). The ef1f6af numbers are historical; they are not a statement about tip. The H1 rankers in `rankers.py` are kept as a reference, not a proposal. All tip statements are scoped to the authored queries, SQLite in memory.

Scope: `backend/app/modules/m21_claire/persistent_journal.py` (hashed bag of words, `retrieve`, kind="decision"). Source pin: atlas-ai commit ef1f6af. Rankers read the rows the shipped journal code stores (SQLite in memory); no schema or journal change. All claims below are scoped to the authored queries in this run and, for supersession, to a correction joined to its original by exact text equality; they say nothing about owner journals. Synthetic data, 5 seeds (11-15) x 100 queries (40 plain S1, 30 corrected S2, 30 newer-decision-on-same-topic S3), 60 distractor decisions that share words with targets, top-3. Constants (weight = 0.7 + 0.3 * 0.5^(age/90 days)) frozen before scoring and not tuned. Mean over seeds; seed sd in results.json.

Rankers: B0 shipped retrieve; B1 BM25; H1a supersession only (decision with a later correction is replaced by the corrected text); H1b recency only; H1 both.

## Results (top-1 accuracy unless noted)

| Claim | Status |
|---|---|
| S1 plain: B0 0.99, B1 1.00, H1a 0.99, H1b 0.96, H1 0.96 (seed sd 0.012 / 0 / 0.012 / 0.044 / 0.044) | VERIFIED |
| S2 corrected: B0 and B1 top-1 0.00, corrected text absent from top-3 in every case, stale original ranked above truth 100%; H1a 0.99, H1 0.95 (H1 seed sd 0.078) | VERIFIED |
| S3 newer decision on same topic: B0 and B1 top-1 0.00 (older id wins ties, stale ranked first 100%); H1b and H1 0.99 | VERIFIED |
| Recency weighting costs S1 top-1 about 3 points (0.99 to 0.96), roughly 1 seed sd; possibly a small regression from reordering partial-overlap distractors; not separated from noise at 5 seeds | VERIFIED |
| Top-3 hit rate is saturated at 0.99-1.00 on S1 and S3 for every ranker, so it does not discriminate here | VERIFIED |
| S2 gain is structural: the shipped `retrieve` filters kind="decision", so a correction can never surface. H1a fixes that by a text join, not by better ranking | VERIFIED |
| BM25 beats the hashed bag of words on this corpus (S1 gap 0.01, inside noise) | UNVERIFIED |
| Gains transfer to owner journals, paraphrased queries, or semantic matching | UNVERIFIED |
| Recency decay + correction linking raises current-decision retrieval on the authored multi-session cases | VERIFIED |
| That hypothesis holds beyond the authored S2/S3 cases | UNVERIFIED |

## Honest limits
- I authored the scenarios; S2 and S3 reward supersession and recency by design. What this run reports is the S1 cost and the size of the S2/S3 effect on authored cases; it does not test whether the idea can lose.
- Queries reuse the exact topic words, so recall is easy. No paraphrase or semantic cases. A paraphrase variant (drop one topic word, synonyms) is the obvious next test and likely where lexical ranking fails.
- Supersession matches a correction to its original by exact text equality, as `correction()` stores it. If the owner edits the original wording, the join fails silently. Not tested.
- Same-topic grouping for S3 is implicit (recency re-weighting of near-equal scores); no explicit topic detection. A newer unrelated decision does not supersede anything; not tested.
- Python 3.10 here, journal module loaded standalone with SQLAlchemy on in-memory SQLite. Not run on the repo's Python 3.12 or against Postgres.

## Follow-ups (not done)
- Paraphrase set; explicit "supersedes" link column instead of text equality (needs a migration, so a separate decision); tune weight on a train split, report on a held-out one.

Reproduce: `python experiments/e1_journal_retrieval/run_experiment.py <out_dir>` (~25 s).

| At 8a79fc4, shipped B0 S2 top-1 is 1.00 and S3 top-1 is 0.987 on the authored queries (rerun, results_tip_8a79fc4.json) | VERIFIED |
| At 8a79fc4, H1 recency weighting costs S1 top-1 (0.96 vs B0 0.995) and adds nothing | VERIFIED |
