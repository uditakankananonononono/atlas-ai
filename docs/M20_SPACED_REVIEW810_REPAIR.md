# Row810 SM-2 lapse repair

Audit found a source deviation: the landed lapse branch lowered E-Factor despite
SM-2 step6 requiring repetitions to restart without changing E-Factor on q<3.
Source inspected: https://super-memory.com/english/ol/sm2.htm, step6.
Repair keeps prior ease exactly on q0/1/2; successful q3/4/5 still applies the
existing formula with1.3 floor. This is a deterministic supplied-state transition,
not empirical retention improvement, optimal scheduling or a scheduled reminder.

New pins:12 lapse quality/ease pairs plus4 successful formula/floor cases.
Old lapse-floor test corrected rather than preserving the audited deviation.
RED10 failed/20 passed against current public4da7f8e5; final30 unit passed.
Real Python3.12.14 unchanged conftest floor95 passed, one dependency deprecation.
Own9/9 named mutants killed, including lapse-ease regression and keep-ease for
successful grades. Independent gate: separate record. No global-suite or production claim.
No routes/initializer/shared engine change; runtime one-line lapse assignment only.
