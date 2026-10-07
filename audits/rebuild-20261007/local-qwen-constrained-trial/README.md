# Small-model plumbing trial, not cognition certification

Same pinned Qwen2.5-0.5B-Instruct Q4_K_M GGUF and llama.cpp as earlier trial. Verified checksum/build at startup.2threads1024ctx1slot128output, synthetic prompts, fresh loopback ports, no tools/production routing changes, both servers stopped.

Initial request used response_format.json_schema with top-level schema based on server README. Pinned server implementation expects response_format.json_schema.schema nested under json_schema wrapper; initial run therefore constrained only generic object. Initial result/log retained. Reason42 passed; planner and reflect failed schema.

Corrected request native schema validity3/3; exact purpose pass2/3:
- Planner failed: generated cyclic s1->s2->s1; actual HTN validator rejects. Schema doesn't guarantee valid goal plan.
- Reason passed:17+25 returned string42, adapter accepted.
- Reflect passed: output matched prompt-supplied cause empty_input/fix request_nonempty_input/retryfalse. This is label adherence, not independent cause discovery or actual repair.

Corrected startup0.811s, peak675012KiB, total9.064s. Original unconstrained adapter samples remain all3failed in local-qwen-trial. Follow-up uses trial-only transport/purpose-prompt injection into actual adapter parsing, not existing provider/native schema integration or end-to-end production runtime. No general accuracy/statistical estimate from these3samples.

Public sources previously inspected:
https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF
https://github.com/ggml-org/llama.cpp
