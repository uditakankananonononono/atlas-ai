#!/usr/bin/env python3
"""Fail-fast migration gate. Set ATLAS_EXPECTED_SCHEMA_REVISION to the image revision."""
import os,sys
expected=os.environ.get("ATLAS_EXPECTED_SCHEMA_REVISION","")
current=os.environ.get("ATLAS_CURRENT_SCHEMA_REVISION","")
if not expected or current!=expected: sys.exit("database schema revision is absent or stale")
print(current)
