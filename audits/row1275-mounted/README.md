# Row1275 dedicated mounted arbitration bookkeeping

Scoped mounted bookkeeping independently reviewed; literal Arbitration remains PARTIAL.
Historical builder base:134e0dcd. Python3.12.14. Existing scipy available; cvxpy1.9.3 installed in
local venv successfully, no pyproject/dependency lock changes. App imports and
mounted tests executed through actual app.main, not a non-mounted probe.

Dedicated POST /api/v1/api/modules/20/arbitration/1275/organize takes the engine's
jurisdiction/as_of/authorities/items payload directly. This differs from shared
legal-1260-1309/support row_inputs contract; no misleading same-payload comparison.
Shared route remains unchanged and template-only. Production OIDC signature tests
use local key fixtures, no public identity/provider calls. Output identity comes
from authenticated principal; tenant/actor input keys refused by engine shape.

Initial 15-case mounted RED:14 failures plus1 auth PASS. Final19-case selector independently rerun without mount on current composition:18 HTTP404 assertion failures plus1 auth PASS; mounted19P. First GREEN combined201passed.
After decoder-specific pins and cap/date tests: combined205passed, one existing
Starlette/httpx deprecation warning. Final mounted selector19passed. Eight named
route/mount operators caught with rc1+FAILED IDs; restore SHAs recorded. No
whole-repository regression, network isolation or legal competence claim.

Initial partial battery: M1-M3 caught, M4 duplicate-check removal SURVIVED. The
initial malformed duplicate request also failed engine shape, masking decoder
removal. Partial logs retained under initial-partial/; no complete initial
receipt or M5-M8 first-run claim. Added valid-shape duplicate/nonfinite requests
pin exact INVALID_JSON. Full later battery8caught, not rewritten initial history.

Body cap32768 bounds retained streamed bytes, not upstream transport allocation
or whole-request memory. Strict UTF8, duplicate-key and NaN/Infinity refusal;
application/json required. Engine remains caller-declared closed-vocabulary
bookkeeping, no arbitration determination, authority authenticity, legal advice,
filing/contact/spend. Counsel review required. Existing Cs/Co/Cn text residuals
retained; JSON/serializer constraints may reject data accepted standalone.

Original raw logs privately retained. Delivery intentionally strips whitespace
and replaces private workspace prefixes with <private-workspace>. Exact changed
lines and original/delivered SHA pairs in receipt/additional-log-provenance,
listed below. Interpreter portable-normalized. Local version-bound results,
not independent acceptance/universal restoration. No pushes.

- baseline.log: original `a8e657e0ac306717bcc21fd0a0a819a798b5b8b7fdeca75f3fa03998511926ad`; delivered `230e91a8c140e7246112e25cbae409acf70dd6c42be793f96084594542efc91e`; changed lines [{'line': 3, 'operations': ['whitespace/path-portable-normalization']}, {'line': 4, 'operations': ['whitespace/path-portable-normalization']}].
- A1275-M1.log: original `f31b914d2a7fc8787264bf531a45da38ef3a365d0c099716195361115ac3ea5c`; delivered `d1d33a09c1c83fbaa397dd66fb821ecd4752596b71575b1277ca8b04a387c27a`; changed lines [{'line': 106, 'operations': ['whitespace/path-portable-normalization']}, {'line': 107, 'operations': ['whitespace/path-portable-normalization']}].
- A1275-M2.log: original `27b9a0b8bde953380327dcb7a7d7b5e783b0e03aa7ad3da874f542dba806197f`; delivered `a9fcae8b0f855e50c56e489b61608a095e26ba0568d024758d4ec4e99ef325a8`; changed lines [{'line': 11, 'operations': ['whitespace/path-portable-normalization']}, {'line': 12, 'operations': ['whitespace/path-portable-normalization']}].
- A1275-M3.log: original `6a0ec90483fe9723c5484bfcd0d161531b2ac4f399dc39f81d94f85afff255d1`; delivered `73690777af4a3177c63e56966284002ac526625a77b0828ba3553256e7764bf3`; changed lines [{'line': 11, 'operations': ['whitespace/path-portable-normalization']}, {'line': 12, 'operations': ['whitespace/path-portable-normalization']}].
- A1275-M4.log: original `fb65a1ea25c3a7d35b62a482b7d496eeaa4affecbfb0003915dc3924fceac642`; delivered `e973e402d00e6c35d85c215902682872ca7d9dc86cadfcb114f35cc224e59d77`; changed lines [{'line': 10, 'operations': ['whitespace/path-portable-normalization']}, {'line': 11, 'operations': ['whitespace/path-portable-normalization']}].
- A1275-M5.log: original `f8991d0014807a892ca4e1184f0c55377e45adef9ad31572358c569585618107`; delivered `1d438b2a275e7353b842910fcf9563b2327909be828d385a53d389293f31c20c`; changed lines [{'line': 7, 'operations': ['whitespace/path-portable-normalization']}, {'line': 12, 'operations': ['whitespace/path-portable-normalization']}, {'line': 13, 'operations': ['whitespace/path-portable-normalization']}].
- A1275-M6.log: original `2ed8c3e4d7f266905b3ed085a63091c02f8734b2a3082f19b086ef465f254720`; delivered `80d8ecceb2084fa60ed925b72c4f46054c6d785e76331f857b447d80cb4d6a59`; changed lines [{'line': 57, 'operations': ['whitespace/path-portable-normalization']}, {'line': 58, 'operations': ['whitespace/path-portable-normalization']}].
- A1275-M7.log: original `466631939800a2b4a754f76e9dd1efbad099a31310783bfdc6da8638666c2198`; delivered `d0282036bf6426c583aa7771d4ede5e65858a23945c6f82f8e8095b0b609fdee`; changed lines [{'line': 7, 'operations': ['whitespace/path-portable-normalization']}, {'line': 13, 'operations': ['whitespace/path-portable-normalization']}, {'line': 14, 'operations': ['whitespace/path-portable-normalization']}].
- A1275-M8.log: original `cfbd92b820a03068cc96c8979033c4108f4de28bf4f5acae33f86c78dcc27bd8`; delivered `af043a7d9099b9f8126406584babe0cf81cd6016cc29bc445bbb7dda0ccf3b69`; changed lines [{'line': 7, 'operations': ['whitespace/path-portable-normalization']}, {'line': 13, 'operations': ['whitespace/path-portable-normalization']}, {'line': 14, 'operations': ['whitespace/path-portable-normalization']}].
- restored-baseline.log: original `ea271e66481c1539dcc1d245fc933eb8dc9eadf407a4783269444e86b26448d6`; delivered `cc5294563fb0c6494b028fe846b2e7fce3f4dcf13a39744d1ce0aa660a1ebd33`; changed lines [{'line': 3, 'operations': ['whitespace/path-portable-normalization']}, {'line': 4, 'operations': ['whitespace/path-portable-normalization']}].
- mounted-red.log: original `de8e3a86d2be2f0965a15017f59b4492a852427942e0a7ba8f1896a721bec11b`; delivered `d3d3fe5c83e05e15b74e5f0299965da03f2c223bf9b9de17baa394f173af0176`; changed lines [85, 86].
- initial-green-combined.log: original `81a5f7466d76973937db6406a4d989b16165d962bf07a4ac5bbd70ff6f6f624d`; delivered `12c1316ec09a2a7e15a71e7342df66fcfa196a62ac0bb177a710b20fe7ae62f4`; changed lines [5, 6].
- final-green-combined.log: original `ce5f114ca7e73fd6db76fe50e9233c0718159806b0a950d7f2da41b315eca45d`; delivered `0bedc0908b31f74a2d4bd28acad895597f0caffc9870f6d0aefc139794559c99`; changed lines [5, 6].

Initial partial log provenance (raw originals private, delivered portable normalized):
- initial-partial/A1275-M1.log: original `c5e6198892d0b1049b532ea2a45485fe3568a8db065e0daf6b90e5b170909699`; delivered `38fa1eca552fbb16dd7d238c012aa634828f62d82826d18cfa85291e479d3d03`.
- initial-partial/A1275-M2.log: original `eaf3044d19c7e4c60f8835ccf5cf08314ceae6eb1379d6a3ba2449d63bf919df`; delivered `45f7a9d91d3a2a94785d169ae8d40881a53bb49440c01c3d48e60ea3c59cfe4c`.
- initial-partial/A1275-M3.log: original `97fe0247ef08bbe4b35063d493388d536ec80363a4b8e5fd3cfbd4b58a3c7a81`; delivered `1d1b74dcaa4356daba6e56b3a47098b60ac5d9e5781718ee7404bd6867132f08`.
- initial-partial/A1275-M4.log: original `049536c0145058936b75f0ef957958bb0edc9d80b7f60e57622e0c784016cc4d`; delivered `230292b0bc1f85a1f213247265ae178d4ce4fc7cf047510851ae7e17e9c90429`.
- initial-partial/baseline.log: original `c711dd3706f50a517b42dbd1cda6b8d3a7e5e5aa28de51ae44631e39bf0c3c01`; delivered `0c6d5244470d123f2437955a67cb0d44107caa1822b33b901f0a1938e16bdfff`.

Integrator replay on the0f477cb4-based sequential1284 composition: all eight
released route/mount operators CAUGHT, original bytes restored. Existing cvxpy
>=1.6,<2 dependency is declared in pyproject.toml; CI installs .[dev]. The contract's
hermetic stdlib line describes only the standalone stage; mounted addendum depends
on FastAPI/cvxpy. The32768 cap bounds retained streamed bytes, not transport or total
memory. Original builder logs were not supplied; normalization hashes document
provenance but do not independently recover those originals. Pin refresh is deferred
to the single composed inventory after all six related routes are applied.

Composed inventory follow-up: after all five in-router additions, isolated m20
spec inventory is273 operations/104 reachable; unchanged not-bound counts. All12
stateless regression tests pass. Combined six mounted selectors plus those12 pins:
82 passed. Row1284 mounts only at app.main and is outside this spec inventory.
Earlier awaited-pin notes above describe the pre-refresh stage, not current state.
