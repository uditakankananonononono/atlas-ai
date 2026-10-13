# Row152 Attention Mechanisms

Exact description: "Focuses on relevant input parts".
Source: https://docs.google.com/document/d/1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY/edit

Actual single-head scaled dot-product attention over supplied query/key/value
matrices, stable masked softmax and weighted value outputs. True mask allows key,
False yields exact zero weight; fully masked query refused. Query/key widths must
match; key/value row counts match; value width can differ. Existing method unchanged.

Caps32rows and16columns per matrix, finite strict int/float values+-1000. Complete
masked/unmasked menu, asymmetric reference queries/keys and three-value outputs,
sqrt(2) scaling reference, nonuniform weighted sums, excluded largest score,
extreme exponent stability, uniform mean, every matrix cap/type/shape boundary,
mask shape/bool/allmasked refusals and no mutation tested.

SCOPED supplied-projection attention calculation/PARTIAL literal feature.
Dot-product compatibility does not certify semantic relevance. No learned projection,
model training, multi-head attention or causal explanation, auth/persistence/runtime
integration. Outputs retain value units; weights dimensionless after supplied
compatibility convention. No external effects.
