# LEARN-ASSESS827-828: anchored evidence assessment

Candidate SCOPED, no psychometrics/credential/mastery claim. Rebuilt methods
require explicit artifact/author IDs, rubric/evidence/ratings/control objects;
old criterion/rating copied fields and minimal payloads refuse (artifact_id).

Rubric1..32 criteria have source references and2..16 unique integer anchor levels
0..100, descriptive labels and<=64 required symbolic features. Anchors need not
be cumulative: a supplied higher level does not imply lower-anchor semantics.
Up to1000 source-bound evidence records belong to the assessed artifact and have
<=64 unique declared features. Text bounded240chars. No artifact pixels or natural
language are interpreted; source/feature claims are supplied, not verified.

Up to1000 ratings have unique IDs and criterion/rater pairs, known criterion and
anchor level, <=64 evidence refs. Missing/unknown refs differ: unknown refuses;
empty produces missing_evidence and supported=False, even for zero-feature anchor.
Observed feature union from cited evidence is compared to anchor prerequisites;
missing_required_features and conflicted flags determine supported status.

Self mode requires author=rater. Peer mode requires author!=rater and explicit
anonymization=True. Both require declared conflict_checked=True, bool anonymized,
unique conflict-rater IDs and nonempty author-response text. These are declarations,
not proof of actual anonymity, unbiased review or verified identity. Conflicted
ratings are retained but cannot support a level. Distinct supported levels produce
disagreement, no averaging and highest_anchor_supported=None. A single supported
highest declared anchor yields True only for that rubric match, never mastery.
No supported levels yields False; missing_ratings is reported separately.

Outputs retain rubric, evidence, controls and individual/criterion reports.
Truth=False, mastery=None, credential_decision=None. No persistence/shares or
external effects; existing mounted auth401/422/403owner/tenant checks apply.
Synthetic feature coverage, missing refs, identity/controls, conflicts, disagreement,
type/duplicate guards and auth are tested. Residual: supplied anchored rubric
validation only, no semantic grading, psychological validity or verified mastery.
