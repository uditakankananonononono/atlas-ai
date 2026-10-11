# Model JSON traversal resource order

extract_json retains its100000-character text limit, duplicate-key/nonfinite-number checks, depth64 and20000 decoded-value node budget. Dict keys are not charged as decoded-value nodes. Provider output has no new per-list200 limit.

After decoding, each container's prospective count includes visited nodes, pending stack entries and its direct children. The count and next-child depth are checked before asking for a child iterator or extending the stack. Oversized trees refuse the existing ValueError message: model JSON exceeds depth64/node20000 boundary. At depth64 an empty container is allowed; any child would exceed depth and refuses before traversal. Decoder RecursionError still uses the existing decoder-boundary message.

The guard bounds post-decoder traversal allocation, not json.loads allocation. The text cap remains the decoder input bound. Tests use exact builtin dict/list objects returned by patched json.loads and instrument the child-iterator helper to prove no invocation on refused containers. Real decoding and pending-sibling boundaries are separately pinned.
