#!/bin/sh
# Isolated real-SQLite run of the M19 tenant boundary probe.
set -e
D=$(mktemp -d); cd "$(dirname "$0")/../../backend"
ATLAS_DATABASE_URL="sqlite:///$D/m19.db" PYTHONPATH=. python3 -m pytest ../tests/modules/test_m19_tenant_boundary_verify.py -q -p no:cacheprovider "$@"
