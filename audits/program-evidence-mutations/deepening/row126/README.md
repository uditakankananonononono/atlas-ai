# Row 126 observation validation deepening

Recorded run base 2f89b9fe. Initial outcomes {'CAUGHT': 1, 'SURVIVED': 4, 'INVALID': 0}; first-run survivors
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

Replay: shared deepening/replay.py with row126.json. Delivered logs intentionally
strip whitespace/replace private paths only at listed lines; originals privately
retained. Interpreter portable-normalized. Every supplied log hash pair and
normalization follows. No delivered private path hits.

- initial/baseline.log: original `f7e92aa55170dc978642f7ed70bf76f287a4383d4216a3eb0289fd2e7cddae06`; delivered `f7e92aa55170dc978642f7ed70bf76f287a4383d4216a3eb0289fd2e7cddae06`; changes none.
- initial/D126-M1.log: original `c2bb3d0d810bc19d4cf06d2878e31e3b38a38cd3e5f18192b8ac42ec020d1bfc`; delivered `c2bb3d0d810bc19d4cf06d2878e31e3b38a38cd3e5f18192b8ac42ec020d1bfc`; changes none.
- initial/D126-M2.log: original `c4c729a43670971e7b74b7a23fac451543197613173c0407d00bfe70443cd364`; delivered `c4c729a43670971e7b74b7a23fac451543197613173c0407d00bfe70443cd364`; changes none.
- initial/D126-M3.log: original `85ffe2f38212e58da9e5a126b1337ad603cacefad741b2325d0feb947e94f7bf`; delivered `85ffe2f38212e58da9e5a126b1337ad603cacefad741b2325d0feb947e94f7bf`; changes none.
- initial/D126-M4.log: original `b7af42e5e9c582b0a53bd1bd3db878f34aaa6d30ff65fa839bbbf8ac1fcee2b7`; delivered `b7af42e5e9c582b0a53bd1bd3db878f34aaa6d30ff65fa839bbbf8ac1fcee2b7`; changes none.
- initial/D126-M5.log: original `68559ebea3ceea7a09c00186b356a94a9165ca43c13cc7304b4ab35a1565b5cd`; delivered `68559ebea3ceea7a09c00186b356a94a9165ca43c13cc7304b4ab35a1565b5cd`; changes none.
- initial/restored-baseline.log: original `85ffe2f38212e58da9e5a126b1337ad603cacefad741b2325d0feb947e94f7bf`; delivered `85ffe2f38212e58da9e5a126b1337ad603cacefad741b2325d0feb947e94f7bf`; changes none.
- baseline.log: original `917eedb5eeb7ed0e7c2cf8a9e296b08de9623252d5289e874826854a8b623a16`; delivered `917eedb5eeb7ed0e7c2cf8a9e296b08de9623252d5289e874826854a8b623a16`; changes none.
- D126-M1.log: original `1b054e4437b6eb14be9311c113375d21f345b921b9c0bc4c71ed9b533bc969bd`; delivered `1b054e4437b6eb14be9311c113375d21f345b921b9c0bc4c71ed9b533bc969bd`; changes none.
- D126-M2.log: original `bb06c8f5082e542c02a6eb472775f072b9be296dd39d63b1f9ed51c454993d71`; delivered `bb06c8f5082e542c02a6eb472775f072b9be296dd39d63b1f9ed51c454993d71`; changes none.
- D126-M3.log: original `b924d991c47cb70c6766f681283e9c6d023494f510462da509501d11d0103493`; delivered `b924d991c47cb70c6766f681283e9c6d023494f510462da509501d11d0103493`; changes none.
- D126-M4.log: original `20f5a73fecf87d2647c9f3929b689ecd7b6607d79a281ba549fa7df11b36b80b`; delivered `20f5a73fecf87d2647c9f3929b689ecd7b6607d79a281ba549fa7df11b36b80b`; changes none.
- D126-M5.log: original `00635afa3def286bfcbde6d0c3c84715e20d7f563b76e9929b97a8071be6b3fc`; delivered `00635afa3def286bfcbde6d0c3c84715e20d7f563b76e9929b97a8071be6b3fc`; changes none.
- restored-baseline.log: original `f2f9626e7538d18f2908830c5086171d7872a11eedd6e78d9948eebd53c1075d`; delivered `f2f9626e7538d18f2908830c5086171d7872a11eedd6e78d9948eebd53c1075d`; changes none.
