# M14 service call-site identity proof

Base: 41098321. Proof strengthening only: no runtime defect identified and no production
code changed. Earlier helper tests and length/cross-project checks did not independently
bind each service emit call's report_id to its actual complete identity.

Released selector:

    PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest tests/modules/test_m14_report_identity.py tests/modules/test_m14_report_gate.py tests/modules/test_m14_wiring.py -q

Mutation baseline: 60 passed, two warnings. Expanded selector adds
`tests/modules/test_m14_reports.py tests/modules/test_m14_exports.py`: 86 passed,
two warnings (selector_receipt.txt). Both new tests freeze service time to an aware timestamp
with microseconds, independently canonicalize kind/tenant/project/time/body without
calling the production _report_id helper, and compare exact ledger report_id values.
Status uses the actual returned markdown; export uses actual README and STATUS disk
bytes and also checks report_sha256. Tests run the real service and gate, not a gate spy.

Mutation receipts: six exact call-site replacements, CAUGHT=6, SURVIVED=0, INVALID=0,
NOT-APPLICABLE=0, SHA-256 restoration true. Each call site is separately replaced with
a random valid 64-character id, an empty identity body, or a wrong identity kind.
Every kill is an exact expected-id assertion failure, not a length check or KeyError.
The runner retains raw stdout/stderr logs for baseline and every mutant, full FAILED
node ids, and provenance.json with the starting commit/tree plus source/test/runner
SHA-256 values. These hashes identify the exercised bytes, including uncommitted tests;
the base tree alone is not claimed to be the final patch tree.

CAUGHT requires rc=1 plus FAILED IDs with collection/internal/fatal errors screened and
timeout uncredited. FAILED can include product KeyError/RuntimeError exceptions, not
only assertion failures; mixed FAILED plus SKIP is not rejected. Counts are selected-test
failure sensitivity, not comprehensive mutation coverage. Source restore is byte-checked.

Limits retained: direct renderer checks are transient, service ledgers in memory absent
a persistence sink, context caller-supplied, identity not authorization or dedup, and
identical complete identities can repeat. Label grammar does not verify artifact goodness
or arbitrary prose. No atomic publication/rollback work: errors after admitted writes
may leave partial files. SCOPE/artifact payloads and low-level byte utilities are not
blanket report-gated. The original early-directory survivor provenance gap is unchanged;
new raw logs do not reconstruct old missing artifacts. No external service smoke or
production deployment is claimed by these local tests.


Log normalization (content-only; no tests rerun):
Trailing spaces/tabs stripped only at run-02/03/04.log line 22 and run-05/06/07.log line 25.
Portable path substitutions across run-01.log through run-07.log: environment-specific virtualenv, runtime-directory and pytest temporary-root prefixes replaced by <VENV>, <RUNTIME_DIR> and <PYTEST_TMP> where present.
audits/m14-callsite-identity/run-01.log: original SHA-256 ccf2f23facd7697ee9ff72186502dfa69058cef6719ac773dc372ea76e73eb6d; delivered SHA-256 b18f8b114bfb2f0ddd9f1d7a01baf43b58d3d880c0855230d334b39b83d65a5f.
audits/m14-callsite-identity/run-02.log: original SHA-256 a4279206009dff0965d85c4a5a18549acce840d3f75a418ab7f12c4842d375bc; delivered SHA-256 1cbf2fae4089f0503ab7103268f1afc1ae5e7fa384e7c6a23250b32248e77c65.
audits/m14-callsite-identity/run-03.log: original SHA-256 90c55cd4c599deeb55b5cf0b6888f86c9d1e1bbdefa1d8ca6dfb4b858a502ad6; delivered SHA-256 004ab06715b05dd7c0aa541cb7236e1304de2474f41b5ec2a8f1f7ded19b4efc.
audits/m14-callsite-identity/run-04.log: original SHA-256 7685543cdbf8cbf722c5392f88b0d45340c75e6cbf0564f6d0b065cb2672851c; delivered SHA-256 031bbea8bcd84f0a695ccafdecbfe4891e0098544491da0d2c4b0fe6cc9589c8.
audits/m14-callsite-identity/run-05.log: original SHA-256 81ebf3098d8475e16bffa0ff1661bd20fb2ac6667b494bc67361ae548e341b1b; delivered SHA-256 fd197bf8310e47159ee31d587427d5376d388fb2a1867ba3bf5ebe9e192059c6.
audits/m14-callsite-identity/run-06.log: original SHA-256 b47f61dd4f14da1dd7bf67c43eb61cf94135193da63864492d2681ea52ea039a; delivered SHA-256 ae06e8623bc2161d5272bad0e628867febbe3f1266f902eb4e5620ec7e8c4370.
audits/m14-callsite-identity/run-07.log: original SHA-256 397cf3bf5d402d566ccf0fb83e51fccaf42a52228a5885c99fcde367980bd5e6; delivered SHA-256 6466b0a079c4161a0fb721418119c2ab09d4d55d73dc4d52aeae8abe9c024948.
Original raw bytes are retained privately; all seven delivered log files are intentionally changed by the disclosed whitespace/path normalization, not presented as byte-exact raw output.

## Development, replay and composition history

The original development base was 41098321. The replay workspace commit was
5eafc0e1, distinct from the landed-parent identifier. Final composition was onto
bc034bf0, followed by landed commit 29d951f0. Source/test/runner SHA-256 values
identify the exercised bytes; the replay workspace and landed tree are not asserted
to be the same tree. Historical provenance.json is retained unchanged, not altered
to imply that the recorded runs executed on the landed tree.

The OLD-six survivor result is a carried, separately reported result with NO delivered
old-test logs. The privately retained originals cover only the seven NEW runs and do
not prove the OLD-six claim. The delivered NEW logs contain one baseline and six
exact expected-id assertion failures; they do not independently establish OLD-test
survival or reconstruct absent OLD-test evidence.
