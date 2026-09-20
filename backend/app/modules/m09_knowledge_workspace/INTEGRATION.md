# Module 9 integration

The graph is a real tenant-scoped SQL adjacency list. Node creation computes an embedding through an injected provider and proposes similarity and NER links; it never silently accepts a link. Hierarchical and dependency relationships reject cycles. Optimistic versions prevent lost edits. Audit rows record graph mutations. `/planner-context` exports bounded graph context without exposing another tenant.

For production, inject Atlas's embedding and NER services in `get_service`; the offline default intentionally produces no speculative links. PostgreSQL can later add a pgvector HNSW column/index without changing the service boundary. Register `spec` in `modules/registry.py` and mark catalog item 9 implemented.

Frontend dependency: `@xyflow/react`. The included component uses the actual React Flow canvas, MiniMap, controls, type filters and double-click selection.
