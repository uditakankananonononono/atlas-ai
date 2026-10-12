# Isolated troop worker execution

Base: 96b4cb97. No external product invocation, paid inference or live effects.

Test-first: missing IsolatedPythonWorker import failed three acceptance cases. Five new tests subsequently execute actual bubblewrap actions: dependency values and hashes, hard timeout with blocked downstream/independent success, non-JSON rejection plus registered-source overwrite refusal, network/read-only input/outside-file boundaries, and bounded detached receipts. These run the OS namespace backend, not a synthetic sandbox. The complete tests/troop selection is recorded in the attached log.

Host explicitly selects IsolatedPythonWorker instead of ActionWorker; existing default thread callable behavior is unchanged. Code registration is host configuration, not owner approval. Registered Python source runs with stdlib and read-only system but may be malicious; namespace/rlimit protections limit effects, not correctness. Receipts are bounded in-process, not durable or independently signed. No arbitrary untrusted host objects are serialized; input/output are bounded JSON. Network isolation and inability to read one test outside path are reproduced properties, not a full sandbox penetration assessment. Existing M04 backend does not provide a measured PID/fork limit. No new general production isolation claim.

Group 88 remains PARTIAL: no actual CellCog/Strawberry/Browser Use comparative run or superiority evidence. Source research is official vendor documentation and YC/GitHub provenance, not product behavior.
