# Row 127 observation validation deepening

Recorded run base 2f89b9fe. Initial outcomes {'CAUGHT': 0, 'SURVIVED': 5, 'INVALID': 0}; first-run survivors
preserved under initial/ and uncredited. Final five named operators: 5 CAUGHT,
0 SURVIVED, 0 INVALID. Not exhaustive coverage or five distinct new faults.
No production edits. Narrow tests add exact count/type/length edges and isolated
status-drift (126), negative-duration error retention and workload nonpromotion
(127). These use local Git fixtures and controlled snapshots/receipts where noted,
not external benchmark comparison, semantic equivalence or task completion.
Literal row PARTIAL. Historical batteries unchanged;128 parked,129/130 blocked.

Exact selectors/configs and HEAD/tree/status/product/test/config/replay SHA
bindings in initial/final receipts. New test bytes are separately bound from
run HEAD tree. Per-mutant restore SHA recorded. Crash-inclusive rc1+FAILED
sensitivity, ERROR-space/ERROR-at/timeout uncredited, mixed skips admitted.
Local recorded outcomes, not independent acceptance/universal restore guarantee.
No sandbox/aggregate budget, atomic snapshot or transient-drift guarantee.

Replay: shared deepening/replay.py with row127.json. Delivered logs intentionally
strip whitespace/replace private paths only at listed lines; originals privately
retained. Interpreter portable-normalized. Every supplied log hash pair and
normalization follows. No delivered private path hits.

- initial/baseline.log: original `6c9a501bdfb4cc931d09f27ba5f8e40b6f6b1d1c0c932c0c33a8200c41710633`; delivered `6c9a501bdfb4cc931d09f27ba5f8e40b6f6b1d1c0c932c0c33a8200c41710633`; changes none.
- initial/D127-M1.log: original `cae71f1e5ebb2a265be401160db78fa13dc64b3aa5995e706b34c667039c3a08`; delivered `cae71f1e5ebb2a265be401160db78fa13dc64b3aa5995e706b34c667039c3a08`; changes none.
- initial/D127-M2.log: original `933dc0a7ded8b65a4d4ff538f5c47ac4f3f9a87b6c1cde28bda7df81ac035aa6`; delivered `933dc0a7ded8b65a4d4ff538f5c47ac4f3f9a87b6c1cde28bda7df81ac035aa6`; changes none.
- initial/D127-M3.log: original `933dc0a7ded8b65a4d4ff538f5c47ac4f3f9a87b6c1cde28bda7df81ac035aa6`; delivered `933dc0a7ded8b65a4d4ff538f5c47ac4f3f9a87b6c1cde28bda7df81ac035aa6`; changes none.
- initial/D127-M4.log: original `1c446df41096238bf8bc5f26599d9d0a76838559bc5547aab6940d958ad95220`; delivered `1c446df41096238bf8bc5f26599d9d0a76838559bc5547aab6940d958ad95220`; changes none.
- initial/D127-M5.log: original `40fb98dae45a942a330f5c8175d1d3ec6c38b06e6089953580720b6bb19adaa7`; delivered `40fb98dae45a942a330f5c8175d1d3ec6c38b06e6089953580720b6bb19adaa7`; changes none.
- initial/restored-baseline.log: original `41b760daa5721f495a71e6e811b3ad410586c02d5445ff30e04ef2e5bef6e7b0`; delivered `41b760daa5721f495a71e6e811b3ad410586c02d5445ff30e04ef2e5bef6e7b0`; changes none.
- baseline.log: original `08c3d72899535847b27217de9a949e10adfdeea592d6d74097d17c746fbdef2d`; delivered `08c3d72899535847b27217de9a949e10adfdeea592d6d74097d17c746fbdef2d`; changes none.
- D127-M1.log: original `249aa847c37a176b6f452da54f16b960e90386472531601b03a7cdd623f3a2e6`; delivered `249aa847c37a176b6f452da54f16b960e90386472531601b03a7cdd623f3a2e6`; changes none.
- D127-M2.log: original `9ad41d7324f48d8c6a8be1082eee7986a858953b73df738e724998ea63649ed9`; delivered `9ad41d7324f48d8c6a8be1082eee7986a858953b73df738e724998ea63649ed9`; changes none.
- D127-M3.log: original `487b6638a6fe8badf6f7de2becba375de6998733da080432e4476bd904119e53`; delivered `487b6638a6fe8badf6f7de2becba375de6998733da080432e4476bd904119e53`; changes none.
- D127-M4.log: original `1d5baefd3031e85582e3055d2d95b7fbc877aa0406c87248d14965fb85763a1f`; delivered `1d5baefd3031e85582e3055d2d95b7fbc877aa0406c87248d14965fb85763a1f`; changes none.
- D127-M5.log: original `305bda75c43054c9b413ffd3b2301419396912bf9b4bb0e5e6395f098434ee31`; delivered `305bda75c43054c9b413ffd3b2301419396912bf9b4bb0e5e6395f098434ee31`; changes none.
- restored-baseline.log: original `82a00accee8564cd3041c0e1a205611e55c80435e858089dd61d1b49b1c14043`; delivered `82a00accee8564cd3041c0e1a205611e55c80435e858089dd61d1b49b1c14043`; changes none.
