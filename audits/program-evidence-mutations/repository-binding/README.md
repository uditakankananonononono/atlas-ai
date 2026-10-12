# Row123 local repository binding sensitivity

Recorded base d8668c19, HEAD/tree/status and exact product/test/config/replay byte
hashes in receipt.json. The new test file was untracked at run HEAD; its executed
bytes are bound separately, not claimed to be part of that HEAD tree. Trusted
checkout only, no sandbox or aggregate budget. Local Git/file checks, not remote
ownership, availability, authenticated origin or semantic completion. Literal
row PARTIAL. Historical row123 initial/final receipts remain untouched.

Two new tests use actual temporary Git repositories, local file:// clone and a
tracked symlink inspection error. They require an errored entry not be promoted,
a separate healthy entry retained, declared cross-references preserved and
origin presence disclosed without locator publication. The configured-origin
docstring now matches code: presence disclosed, locator/hash omitted. No
executable product change. This is not a new remote verification capability.

Five named operators: error nonpromotion, origin presence, remote nonpromotion,
ownership nonpromotion and reference retention. Recorded: 5 CAUGHT, 0 SURVIVED, 0 INVALID.
Existing tests already discriminate several operators; new tests add multi-entry
error/context discrimination, not five new independent faults. CAUGHT is rc1 plus
FAILED, including product exceptions, with ERROR-space/ERROR-at rejected; mixed
FAILED+SKIP admitted. No assertion-only or intended-failure-only guarantee.

Replay: `python audits/program-evidence-mutations/repository-binding/replay.py`.
Exact selector listed in receipt.json. Baseline/restored: 12 passed each. Every
source restore SHA-matches recorded pre-mutation bytes. Receipt-bound outcomes
are local records, not universal restoration or independent acceptance. Before/
after hashes are non-atomic, no transient/concurrent mutation protection.

Delivered logs intentionally strip whitespace and replace private paths only
where listed. Raw originals privately retained. Every original/delivered SHA pair
and changed line/path pair below and in receipt.json. Interpreter normalized to
python, not byte-identical original absolute command. No private path hits.

- baseline.log: original `5af02ab3ce1a4a1e85f4e75799d1fddbdf29350ca4034adfd7a4df3ecbb835f3`; delivered `5af02ab3ce1a4a1e85f4e75799d1fddbdf29350ca4034adfd7a4df3ecbb835f3`; changes none.
- B123-M1.log: original `295f23a27df68a53280b089830add18eb887c61870011a3fc01c23c1155fe95b`; delivered `a37f81380310c8070fd93582886b72bc4cbbff199dec27a3249ea9ac1c07bf59`; changes [{'line': 7, 'trailing_whitespace_removed': True, 'path_pairs': []}].
- B123-M2.log: original `afa034f38b7890a5ac16acc060cec661569f55f76721d03869b6516c8b25413b`; delivered `afa034f38b7890a5ac16acc060cec661569f55f76721d03869b6516c8b25413b`; changes none.
- B123-M3.log: original `3bd80bce4f76c8a01e741635a246d6d4f55b1a82956d82096298d6761afe561d`; delivered `3bd80bce4f76c8a01e741635a246d6d4f55b1a82956d82096298d6761afe561d`; changes none.
- B123-M4.log: original `b9e7c87a5cf664d6f992c62f5a0b52eab0e337cf84abfa42d558276f91d1a76e`; delivered `b9e7c87a5cf664d6f992c62f5a0b52eab0e337cf84abfa42d558276f91d1a76e`; changes none.
- B123-M5.log: original `5be113587ecc659ea0d2dc913d3b368052da3103ebc00c40035dc474cad3118a`; delivered `6d047d65ca9177752d669e0f4a3c3214dcc211c4efcfb0aac4a2d2be5b5a0641`; changes [{'line': 7, 'trailing_whitespace_removed': True, 'path_pairs': []}].
- restored-baseline.log: original `d5cad463dca075ce0547be8f305973f6f4bb4204b0258745e1a11b6f28245699`; delivered `d5cad463dca075ce0547be8f305973f6f4bb4204b0258745e1a11b6f28245699`; changes none.
