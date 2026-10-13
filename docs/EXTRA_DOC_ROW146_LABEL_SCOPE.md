# Row146 Self-Supervised Learning

Exact description: "Creates labels from data structure".
Source: https://docs.google.com/document/d/1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY/edit

Actual next-token prefix/label pairs or single-position masked-token reconstruction
pairs, generated from supplied token sequences with preserved sequence index and
label position. Complete deterministic mode menu, no random mask selection. Original
tokens remain unchanged, output contexts independent of input sequence lists.
Existing planning-only method unchanged. Mask sentinel collision refused.

Caps100sequences x100tokens x120characters, strict list/string/nonblank shapes.
Worst-case10000examples; context copying bounded to1million token references.
Exact asymmetric/repeated-token references, custom mask/Unicode pass-through,
future exclusion, every mode, cap/label/type/empty/mask collision refusals tested.
Original sequences must be split before generation to avoid prefix/mask leakage;
returned source indices support that separation but do not authenticate provenance.

SCOPED structural pretext-label generation/PARTIAL literal feature. No model fitting,
embeddings, downstream probe, semantic-label verification, tokenizer, augmentation
learning, split independence certification, auth/persistence/runtime integration.
Generated label truth is the supplied token only, not an external semantic claim.
No external effects.
