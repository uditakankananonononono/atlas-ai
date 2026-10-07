# Peer source provenance

The comparison source is the other account's transferred full-history Git bundle, not a fetched ref of our GitHub main. No verified peer GitHub repository URL was established.

- Bundle: atlas-recon482-full-hz28-b944215353.bundle
- Bundle SHA256: 700a76e3f66f83c433f437a77ec1e7d745245175cd71b0f1a9ea3680bbc18b8b
- Bundle ref: refs/heads/recon-482
- Commit: b944215353d8d641cb476cf3ffba8075072840da
- tools.py blob: f809e6759a3e1d54c4003b00266dff6ea92ac39a
- tools.py SHA256: 10dcd17fd370ac5cf42695a36ac9eee863329c4e9a50b8467607a9b88c8724f7

After importing the bundle into an isolated Git object store, read backend/app/modules/m20_general_cognitive_worker/tools.py at that commit and compare RegisteredTool.to_function_schema and ToolRegistry.function_schemas ASTs. The exact peer file and full bundle were transferred for independent review. No claim is made that the peer tip is an ancestor of our main.
