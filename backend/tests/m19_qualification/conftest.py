# The seven test_m19_*_real* suites in this directory are standalone script runners:
# they execute their checks at import time and require M19_TREE (+ optional M19_DB).
# Run them directly, e.g.: M19_TREE=<repo>/backend python test_m19_run_store_real-08f4e5b2.py
# They are excluded from pytest collection so native repo pytest runs never import them.
collect_ignore_glob = ["test_m19_*_real*"]
