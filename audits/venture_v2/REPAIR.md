# V1-V8 pin-and-fix child

Parent: 3fb547d375d6c66b557b6864e3c63596290fd44d.

Product fix: policy.guard refuses non-string action and source IDs before hash membership. List/dict payloads now yield Refusal and HTTP 422, not TypeError/500. Routes, algorithms, fail-closed policy and scope are unchanged.

Added frozen full-output V1-V8 regression pins, alternate branch outputs, exact numeric/type/refusal checks, one-sided limit checks, real SQLite index/order/restart checks, source/URL/payload boundaries, and malformed HTTP checks. 34 tests pass.

Fresh wider local battery tested 959 AST mutants: 937 killed, 22 survivors, zero invalid. Scope: short constants, arithmetic/comparison operators, if guards and explicit refusal removal across policy, transforms, engines, store. Every mutant including survivors is reported in repair-mutation-results.json. Survivors carry review notes, including known Refusal-constructor harness gap and detail-text pin gaps. This is not a zero-survivor claim and cannot replace independent auditor results. The initial wider intermediate run was 853 killed / 106 survivors; added pins brought the final full rerun to 937 / 22.

Python 3.12, focused pytest with repository conftest active. No external model validation, no live effects, no scope increase. No remote push.
