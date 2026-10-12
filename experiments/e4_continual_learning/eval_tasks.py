"""Exact-match eval of a Needle .cact on held-out files.
Usage: eval_tasks.py WEIGHTS OUT_ROWS.jsonl TEST.jsonl [TEST2.jsonl ...]
Prints one summary line per file and writes one row per query (query, expected, got, match) to OUT_ROWS.jsonl.
Warnings are not suppressed. Counts are single-run counts on authored rows."""
import json, sys
import needle

weights, out_path = sys.argv[1], sys.argv[2]
with open(out_path, "w") as out:
    for path in sys.argv[3:]:
        rows = [json.loads(l) for l in open(path)]
        agent = needle.Needle(tools=rows[0]["tools"], weights=weights, stateless=True)
        ok = n = refuse_ok = refuse_n = 0
        for r in rows:
            resp = agent.complete(r["query"])
            calls = [{"name": c.get("name"), "arguments": c.get("arguments")} for c in resp.get("function_calls") or []]
            match = calls == (r["answers"] or [])
            out.write(json.dumps({"test": path, "weights": weights, "query": r["query"], "expected": r["answers"], "got": calls, "match": match}) + "\n")
            if r["answers"]:
                n += 1; ok += match
            else:
                refuse_n += 1; refuse_ok += match
        print(f"EVAL weights={weights} test={path} exact {ok}/{n} refusals_correct {refuse_ok}/{refuse_n}", flush=True)
