# Frontier layer port: scope and limits

Ported (pure logic with two file touches: GapClosureEngine reads the bundled requirements_backlog.json at construction, and TrainingDataGate.export writes under a configured export_root): closure, compiler, cycle, data_gate, evaluator_inventor, evidence, novelty_debt, preference_model, representation_inventor, research_router, skill_ecology, requirements_backlog.json.

Changed from the bundle (each has a regression test that fails on the bundle code):
- PreferenceCodec rejects dimensions over 80 chars instead of truncating and aliasing them.
- RepresentationInventor leakage signature is input only (labels ignored); feature vocabulary comes from train only and other splits may not add names.
- EvidenceLattice resolves each domain independent of input order: stances are tracked separately, a domain with both support and refutation is marked intra_domain_conflict and the grade is contested; a neutral item never hides a lone supporting or refuting one.
- GapClosureEngine demotes preseeded verified_complete rows unless a verifier confirms the digests in the row's own evidence; record_safe_substitute closes only with a verified receipt digest, otherwise substitute_proposed. Imported safe_substitute rows and every imported receipt digest are revalidated (hex format plus verifier) at construction.
- SkillEcology rejects held-out cases that reuse authored test inputs. Independence from the skill author is caller-attested, not verified.
- TrainingDataGate.export requires export_root. The root is opened with O_NOFOLLOW and its device/inode pinned at configuration, so a root replaced by a symlink or another directory is refused. It walks directories component by component with O_NOFOLLOW and opens both the dataset and the manifest file with O_NOFOLLOW relative to a directory fd, so symlinks (including ones swapped in after validation) are refused. Limits: it can leave the dataset file in place if the manifest write is refused, and it does not defend against a hostile process that can write inside export_root and rename directories concurrently beyond the O_NOFOLLOW checks, or against hard links.
- canonical_json rejects NaN/Infinity.
- GapClosureEngine no longer reaches verified_complete from caller-supplied hashes. Without a receipt_verifier it records attested_unverified.
- PreferenceCodec takes a PreferenceStore port (in-memory reference included) instead of reaching into a SQLite store.

Not ported, with reasons:
- runtime.py (own SQLite workflow runtime and approvals): duplicates Atlas durable_execution and approved_execution.
- api.py / frontier_main.py: own auth context; Atlas auth would have to be wired in. Not mounted.
- claire_gap OAuth, connectors, ingestion, social_actions, web_research, media_ingestion, store, form_assistant, coding_agent, model_providers: own token handling and outbound HTTP bypassing Atlas auth and the GuardrailEnforcer.dispatch_outbound egress gate. Any port must route egress through dispatch_outbound.

Nothing here is mounted; no module status changed. Heuristic scores (research_router, closure priority) are uncalibrated.

Remaining limits: receipt verifiers are not implemented here (callers must supply one backed by real artifact storage); evidence domain grouping approximates registrable domains; uncalibrated heuristic scores; exact-match leakage checks only.
