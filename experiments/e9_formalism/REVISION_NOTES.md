# V2 independent-audit changes

Based on current main `4f68f54a0d0742982192aa643c2fa92d61437c9b`.

- Replaced fabricated future-output perturbation with actual transition-matrix
  switching at t=24 with continuous latent state. Raw switched future outputs,
  predictions and suffix counts are committed. Updated the unit test to a real
  scalar transition switch from multiplication by 2 to multiplication by 3.
- Renamed the iteration-cap field to `indices_under_iteration_cap_10000`.
  RESULTS.md explicitly says this is a count, not an executed iteration baseline.
- Recorded that all 60 fitted orders equal the latent dimension, so reduced
  order is not tested, and that enumeration sees the complete 24-point prefix.
  60/60 inferred minimal-order operators have coefficients outside the
  enumerator's grammar. Equivalent higher-order fits exist in two cases; no
  universal unrepresentability claim is made.
- Disclosed that the family transfer set has only three policies, discrete
  AUC values 0.5/0.75/1.0, and uses admitted subdivision, not main-run relabel.
- Disclosed repeated transformation randomization seeds across graph seeds.
- This v2 patch contains 15 new files including this revision record. No existing
  files are changed. It supersedes v1 and should not be applied on top of v1.

The previous 0/5 delayed-change row was not experimental evidence because its
output was defined as old truth plus one. The new row is an actual switched
trajectory experiment. Prior v1 claim should be discarded, not reused.
