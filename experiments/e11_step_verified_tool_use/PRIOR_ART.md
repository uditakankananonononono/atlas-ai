# E11 prior art (checked 2026-10-21, web sources cited)

| Work | What it does | How e11 differs |
|---|---|---|
| ReAct (Yao et al. 2022, arXiv:2210.03629) | Interleaved reasoning+acting loop; errors surface only as observations | e11's baseline IS a ReAct-style loop. The verified condition adds per-step pre-execution gating and post-execution effect-predicate checks. |
| ToolVerifier (Mekala et al. 2024, arXiv:2402.14158, EMNLP Findings) | A MODEL scores two candidate tool calls at selection time to pick one | e11's verifier is programmatic (schema + precondition + executable effect predicates), not a trained model, and it checks AFTER execution against the world, not between candidates before it. |
| StepTool (Yu et al. 2024, arXiv:2410.07745; first author Yuanqing Yu) | Step-grained REWARD MODEL for RL training of tool use | e11 does no training and uses no reward model; verification is inference-time and executable. REPLICATED in rev10: step-grained training beats final-only training here too, and a trained actor matches or beats verification alone; the two stack. |
| CRITIC (Gou et al. 2023, arXiv:2305.11738, ICLR 2024) | The LLM critiques its own output using tool feedback, then revises | e11's check is not a model-generated critique; the actor states an executable expected-effect predicate BEFORE the call and the mismatch report is structured (stage, tool, detail). |
| Reflexion (Shinn et al. 2023, arXiv:2303.11366) | Verbal self-reflection stored in episodic memory to improve later attempts | e11 has no learned/verbal reflection; repairs are driven by structured violations within one episode. |

No "first" claim: the combination (actor-stated executable prediction
contracts + pre-execution precondition gating + structured repair
feedback, with no model in the verifier) is presented as a mechanism
we built and measured, not as a claimed world-first. The closest
neighbor on the pre/post axis is CRITIC's tool-interactive correction
loop, which relies on the model's own critique rather than executable
predicates.
