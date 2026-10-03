# Corrections to the raw real-model run files (raw files are kept unedited)
Counts below were taken from the per-turn lines of each raw file (turns 1-4 ask a next question; turn 5 only extracts).

## qwen0.5b raw file (…_qwen0.5b_RAW_stale_summary.txt)
- Its final SUMMARY line is STALE: it was printed by an earlier version of the script that counted only source "adaptive_local_model", so it shows model_backed_question_turns 0 / fallback 2. Actual per-turn lines: anchored questions on turns 1 and 3 (2), fixed-script fallback on turns 2 and 4 (2). Extraction: 0 proposed, 9 rejected (2+1+2+2+2).
- My earlier message said "3 turns got an anchored question". That was wrong: it is 2 of 4.
- Spans are weak (turn 1 span "nobody else would").

## qwen1.5b raw file (…_qwen1.5b_RAW_memory_bound.txt)
- Anchored questions on turns 1 and 4 (2), fallback on turns 2 and 3 (2). Extraction: none_no_model on all 5 turns (every extraction call failed or timed out), 0 proposed, 0 rejected. Per-turn times 29-40s.
- Its SUMMARY line is the stale-script version too and shows 0 model-backed questions; trust the per-turn lines.

## Timeout bound (exact)
- Production default CALL_TIMEOUT_S = 20s (env INSTINCT_INTERVIEW_CALL_TIMEOUT), applied as the urllib socket timeout of each model call. Rev1 used 8s; rev2 changed it to 20s, so my rev1 message's "8s" does not describe rev2.
- Up to 2 calls per answer (span, extraction), so about 40s worst case per answer in the normal case. The 1.5B per-turn times (29-40s) match 2 x 20s timeouts. The 1.5B run used the same code, not a separate script limit.
- urllib's timeout is per blocking socket operation, not a total deadline, so a server that trickles bytes could exceed 20s. Not a hard wall-clock cap. The server keeps generating after the client gives up.
