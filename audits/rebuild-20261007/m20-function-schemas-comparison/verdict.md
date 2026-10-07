# Function-schema comparison

Assessed-compatible for RegisteredTool.to_function_schema and ToolRegistry.function_schemas. AST comparison against actual peer b944215 objects matches both methods exactly. Preserve our surrounding RegisteredTool implementation: detached specification copies, schema dialect validation and document-local reference restriction. The peer's direct caller-spec retention should not replace these protections.

Six comparison canaries plus existing safety-tools tests: 15 passed, 0 failed. This is schema-export contract coverage, not a claim of live provider compatibility. Remaining MERGE_GATES.md surfaces and the untested PostgreSQL unknown-hold migration production prerequisite are unchanged.
