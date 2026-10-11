# M20 Quote Audit (U29) contract

## The quote (word for word, from the owner's brief relayed by Main)
"Please use external validation with your auditors and external tools (chatgpt, deepseek, claude, perplexity) to check whether it adds every essence of my word into working code."

The quote reached this work through Main relaying the owner's WhatsApp brief. It is not independently verified here.

## Existing mechanism (read first)
- `backend/app/core/providers.py` has live provider clients (openai, anthropic, gemini, deepseek, ollama and others) that call the network with environment-variable keys.
- `backend/app/modules/m00_approval_center/service.py` is where irreversible actions are proposed. It executes nothing itself.
- No audit harness exists on main.

## Delta (what this adds)
New file `quote_audit_u29.py`, offline and additive:
- `audit_unit`: for each essence (an exact fragment of the quote) checks that the declared evidence (file, symbol, test, text) exists in caller-supplied sources and that caller-supplied test results are "passed". Reports per-essence status (evidenced, missing, test_failed, tests_not_run) and quote words no essence covers. No scores or percentages.
- `build_external_packet`: assembles what would go to an external validator and a `pending_owner_approval` proposal for the approval center. Refuses excerpts that are not exact source text or that look like credentials.
- `release_packet`: returns the payload only against a matching owner approval. It sends nothing.

## LIMITS
- Structural evidence only. It does not judge meaning and cannot say the code does what the quote means.
- It runs no tests and reads no disk; the caller supplies sources and results.
- No network, no keys, no sending. No provider is called by this code.
- Real external validation by chatgpt, deepseek, claude or perplexity needs the owner's keys and her approval of exactly what is sent, through the approval center. Neither is present here.
- Not wired into anything. Not applied to providers.py.

## S9.1 additions (child commit; v2 S9.1 is peer-supplied, not verified as owner words)
- Packet now carries `code_summary`, `tests` and `limits` next to the quote, report, excerpts and fixed question. All are credential-scanned and hashed.
- `record_response` stores a validator response verbatim (no trim, no parsing) with its sha256, tagged `evidence_not_approval`, `approval: False`.
- `tickets_from_gaps` makes one open ticket per gap the caller lists. It does not read gaps out of the response text.
- Reports carry a `scope` block: implemented, not_implemented, data_source, as_of.
- Not done: no ledger diff (needs the ledger mapper), no browser lane, no route, module stays m20, refusals keep the `U29: ` prefix.
