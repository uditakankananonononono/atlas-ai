# Fresh S4.3 delta replay

Original historical logs never landed and are not recovered here. That provenance gap remains. These runs are FRESH current-base scoped evidence on731f6d4a, not retroactive proof of the older delta.

Original old-site config replay: baselinePASS,4CAUGHT/2INVALID-SITE. The two recipient-control strings used the older policy.FORBIDDEN_CATEGORIES expression, absent from current source. Those missing sites are not kills. original-operator-replay.json retains that exact config.

Current-site config replay: baselinePASS,6CAUGHT/0other, exact restores. The two control operators now target the actual recipient Cc/Zl/Zp category expression. No production waiver logic changed.

Runner creates the missing audit parent and uses the shared single-site runner. CAUGHT needs rc1+FAILED IDs with no ERROR/collection/skip marker. FAILED can include product exceptions: failure sensitivity, not assertion-only proof. Invalid sites, timeout, no tests and process failure are not CAUGHT. Direct child timeout is not escaped-descendant isolation.

Run: python tests/modules/s43_delta_mutations.py --output NEW_OUTPUT. Output must be fresh, never overwritten. Exact selectors are in operators.json. No send, approval, registration, account or provider effect.

Raw originals retained privately, not included. Receipt log hashes bind original bytes; the table below binds delivered normalized bytes. Original-line SHA and line number identify changed lines without disclosing private paths. Path-root substitutions use VENV, REPO, PYTEST_TMP, HOME, ROOT and RUNTIME_DIR. Timings/test IDs/outcomes unchanged. Checkout status/hashes record local pre-commit evidence only, not final release identity or authenticated historical provenance.

Delivered normalization also removes trailing whitespace on pytest output lines. Original raw bytes remain unchanged privately; every changed line and updated delivered hash is listed below.

## original-sites-fresh/year_zero.log
Original SHA256 d975e0e06d2321532134f7800fd52010dc482a68cb5d378a14be63331cf5fd8b
Delivered SHA256 262f4c4486e9723a6502b1c634a9fb8056512bf84eb49536a4dabcc27e227089
Line 10; original-line SHA256 8ee59890aec2468599febcf4b7b86686b3a92cd82b2bcd8d555ba54e00fe3187; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43_delta.py:19:
```
Line 11; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
## original-sites-fresh/strict_recipient.log
Original SHA256 86c96c6601dcb00bfec20385276d256ea0b59504b2b82e714b05c81a8cadb92c
Delivered SHA256 82c535f84ace2b138ac9512d256abf3ecde496c3651266d9028c4b501a3561fa
Line 13; original-line SHA256 16508df5660c044cf3be93c94cd01831c7f192bf9c256065962ac7e41ea78522; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43.py:244:
```
Line 14; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
Line 27; original-line SHA256 8a8fa14190ade17afcff04ae0c6a634b3758ee65995b8cc932c86a82bdbec407; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43.py:240:
```
Line 28; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
Line 41; original-line SHA256 5129810decf82b8bdcaa87fe47192657d64c336ec927ed6a31d6d52d290d0a69; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43.py:248:
```
Line 42; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
Line 55; original-line SHA256 e737f3220f91684e0ce468feed5f8d55965bf1569d5123d5822f8dfd3783dfad; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43.py:520:
```
Line 56; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
Line 86; original-line SHA256 353fbcf9c3a19761523083b2ac981b0e43a094f90e37e8d0a658bb6604326325; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43.py:846:
```
Line 87; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
Line 106; original-line SHA256 b1b7f680ac3f470dba07c85f76d8e7d1ac31b67d01d11ea990346e384e4a032b; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43_delta.py:30:
```
Line 107; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
Line 132; original-line SHA256 b1b7f680ac3f470dba07c85f76d8e7d1ac31b67d01d11ea990346e384e4a032b; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43_delta.py:30:
```
Line 133; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
Line 158; original-line SHA256 b1b7f680ac3f470dba07c85f76d8e7d1ac31b67d01d11ea990346e384e4a032b; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43_delta.py:30:
```
Line 159; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
## original-sites-fresh/recipient_invalid_flag.log
Original SHA256 50a69ad4dd13451e0d72561c42e18c6de0875b65f47f4e54db3c25cc530fd8b4
Delivered SHA256 faba53e43563f58b6a39f2070ff8a6adc631719779dcbdcd654203bfe2bee9a7
Line 100; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 115; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 130; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 145; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 162; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 179; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 196; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 213; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 230; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 247; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 264; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 281; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 298; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 315; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 332; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 349; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
## original-sites-fresh/year_minimum_offbyone.log
Original SHA256 55ac79fbc97b28c567b0a4a165a69dcd5fe77c86565f538d65a6fff6cfa2d9c6
Delivered SHA256 844d5d71ac0edf29bb868d39f65fd4a34cf4e87ffd6693cc8a2fff8abaab2c19
Line 11; original-line SHA256 8f8e61f7856a55e867ce9c17ec3ffce79961e3beb99fa845192b939175ea01aa; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43_delta.py:50:
```
Line 12; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
Line 15; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
## original-sites-fresh/baseline.log
Original SHA256 9dae4229a760713660bc7fc66a2201256233cf880e71d7662279bc29d38343b2
Delivered SHA256 9dae4229a760713660bc7fc66a2201256233cf880e71d7662279bc29d38343b2
No normalized lines.
## current-sites-fresh/controls_disabled.log
Original SHA256 55db42ce01648b332f5ae0d2edebb69ad0da6003fcdf2ec252cd4a4fde1e5beb
Delivered SHA256 95d8fbbc0c2f4074b601194b3b3aaf8ca6ea7915b72b94652aae479c85848538
Line 81; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 96; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 113; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 130; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 147; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 164; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 181; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 198; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 215; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 232; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 249; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 266; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 283; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 300; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
## current-sites-fresh/year_zero.log
Original SHA256 0146271c81dc7148a66d4ea400fae425c096f95025384be52171f6b8a5d68323
Delivered SHA256 816b9b47b4d556367dc4ce6eed4a993320a05819bf85115246fdd751c2b2eaf9
Line 10; original-line SHA256 8ee59890aec2468599febcf4b7b86686b3a92cd82b2bcd8d555ba54e00fe3187; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43_delta.py:19:
```
Line 11; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
## current-sites-fresh/ascii_control_regression.log
Original SHA256 d73f51004ad8f084f23f6668bd3fa9c42a976a4b690d6c65fe8bb310181f7555
Delivered SHA256 df7acc84779f5cdc468ac551059320df7052f6fdbc9df829e6e885b438560c9c
Line 53; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 70; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 87; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 104; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 121; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 138; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
## current-sites-fresh/strict_recipient.log
Original SHA256 686bb603ac269b3f2952bf168f8674cf0381ebdfe7b1e4ca8eb04e389e35d52f
Delivered SHA256 3f94a92cf5ed57cfa64385b8962ed4ffab074f3aff918da16b81977339bce30d
Line 13; original-line SHA256 16508df5660c044cf3be93c94cd01831c7f192bf9c256065962ac7e41ea78522; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43.py:244:
```
Line 14; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
Line 27; original-line SHA256 8a8fa14190ade17afcff04ae0c6a634b3758ee65995b8cc932c86a82bdbec407; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43.py:240:
```
Line 28; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
Line 41; original-line SHA256 5129810decf82b8bdcaa87fe47192657d64c336ec927ed6a31d6d52d290d0a69; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43.py:248:
```
Line 42; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
Line 55; original-line SHA256 e737f3220f91684e0ce468feed5f8d55965bf1569d5123d5822f8dfd3783dfad; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43.py:520:
```
Line 56; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
Line 86; original-line SHA256 353fbcf9c3a19761523083b2ac981b0e43a094f90e37e8d0a658bb6604326325; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43.py:846:
```
Line 87; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
Line 106; original-line SHA256 b1b7f680ac3f470dba07c85f76d8e7d1ac31b67d01d11ea990346e384e4a032b; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43_delta.py:30:
```
Line 107; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
Line 132; original-line SHA256 b1b7f680ac3f470dba07c85f76d8e7d1ac31b67d01d11ea990346e384e4a032b; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43_delta.py:30:
```
Line 133; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
Line 158; original-line SHA256 b1b7f680ac3f470dba07c85f76d8e7d1ac31b67d01d11ea990346e384e4a032b; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43_delta.py:30:
```
Line 159; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
## current-sites-fresh/recipient_invalid_flag.log
Original SHA256 c04d2bc6b61a3f7e80a838ef2232c2029ff2423eb75daa78d53d5836b17025b5
Delivered SHA256 a5064bac0089f67e926186fe11eb7e8d6d9a7bbe03232def3207ec7f82c6ab3d
Line 100; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 115; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 130; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 145; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 162; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 179; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 196; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 213; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 230; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 247; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 264; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 281; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 298; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 315; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 332; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
Line 349; original-line SHA256 9223772bd4c49a32d281352be54db2721366012b3fc7f2edbe9c3a904717ca9d; trailing-whitespace removed=True
```
E
```
## current-sites-fresh/year_minimum_offbyone.log
Original SHA256 b279e286656be4551ecc80e2b1615cad5f8ca23f365cac22a37406ab2fed3cf7
Delivered SHA256 5795a19300db0f863dc3934071d7cdb7168a646bc6b3fdab5f3090310430fab1
Line 11; original-line SHA256 8f8e61f7856a55e867ce9c17ec3ffce79961e3beb99fa845192b939175ea01aa; trailing-whitespace removed=True
```
tests/modules/test_c35_waiver_drafts_s43_delta.py:50:
```
Line 12; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
Line 15; original-line SHA256 1b820776a681d3e670da17c1d9d803e243d9102843c1f0fd38c08fa096c27267; trailing-whitespace removed=True
```
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
```
## current-sites-fresh/baseline.log
Original SHA256 f8e3796578ee04b16087464b7b062f6f71fb358a54c9e967fa69aa39001f1fa3
Delivered SHA256 f8e3796578ee04b16087464b7b062f6f71fb358a54c9e967fa69aa39001f1fa3
No normalized lines.
