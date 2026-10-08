# A14 LangChain product planner consumer

The prior LangChainPipeline was exercised only by the architecture fixture.
FreeFirstPlannerModel now invokes that real LangChain RunnableSequence through
prepare, generate, decode and validate stages. Each stage carries goal/context
forward. Provider selection stays in the existing free-first layer with private
routing, no automatic retry after unknown outcome, the same bounded strict JSON
parser, registry risk floors and the existing HTN validation/review gate.

The product-path fixture submits a novel goal through GCWRuntime, persists its
plan and proposed learned method, reopens a file-backed SQLite repository and
confirms the proposed method cannot match until reviewed. The fixture external
tool is never dispatched. Negative controls cover provider outcome unknown,
malformed/duplicate-key output and unknown tools; unknown holds survive restart
without a second provider call. This is fixture-provider transport/composition
acceptance, not a live LLM answer, cognition quality, hosted provider acceptance
or full A14/product closure. Prompts/state are not newly logged or persisted.

Separate OPEN gap: seeded judgment prompt-chain skills claim execution in service
comments, but DeliberativeLoop does not consume their skill.steps/prompt_chain.
This increment does not silently activate, repair or claim those skills.

Focused suite: 236 passed, zero failures (planner adapter, strict/private/unknown
outputs, runtime depth, architecture workflows, five new consumer controls).
