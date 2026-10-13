# Pytest basename collision repair

Ten pure file renames give separately collected modules unique basenames. File bytes,
test names and assertions are unchanged. Historic receipts keep their historic paths;
rename-map.json maps those paths to current paths.

CI runs 38347852830 (69565d12) and 38348364527 (64f71c1e) stopped with the same ten
import-file-mismatch collection errors. test_pins/test_routes from tests/c3_layers
shadowed other directories, and wiring8/test_engine_routes shadowed wiring9.
These files existed before the current row evidence landings.

Local combined affected-directory collection: 775 collected, zero collection errors.
Importlib mode was rejected because nineteen existing unqualified sibling helper
imports failed. Full local collection was killed by the environment, so no full-suite
or CI-green claim is made. Independent full collection and CI on tip remain required.
