# P236 (L185): improvement-attempt register

Literal state: PARTIAL. The doc line is "- Try to make it into AGI-like
capability." The literal AGI-attempt is NOT implemented by a register: no
model is trained or modified, no capability is achieved, and AGI-like
capability is recorded with asserted=False in both the module docstring
and the returned doc_claims. What exists is an audit unit over
caller-supplied attempt records: it recomputes the state reconciliation
(proposed -> tested -> measured), flags tested/measured rows that lack an
evidence_ref or metric_note, and never papers over gaps.

verify() re-registers from the same attempts and compares EVERY field of
the result (feature, source_lines, doc_line, measure, limits,
attempts_sha256, attempt_rows, state_counts, issues, verdict, doc_claims);
a tampered field fails verification and is named in failed. Deterministic,
internal consistency only - evidence refs are caller-declared; presence is
checked, truth is not.
