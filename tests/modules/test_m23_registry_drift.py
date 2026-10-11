"""Canonical-source and import safety pins; no network calls in these tests."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
MODULE=ROOT/'backend/app/modules/m23_study_abroad'

def load():
 s=importlib.util.spec_from_file_location('m23_drift_audit',MODULE/'public_source_audit.py')
 m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class CanonicalTests(unittest.TestCase):
 def test_derived_registry_matches_canonical_projection(self):
  m=load()
  canonical=json.loads((MODULE/'admitted_cases.json').read_text())
  derived=json.loads((MODULE/'public_source_registry_v1.json').read_text())
  self.assertEqual(derived,m.normalize_sources(canonical,required_count=20))
 def test_canonical_role_explicit(self):
  doc=(ROOT/'docs/M23_PUBLIC_SOURCE_AUDIT_CONTRACT.md').read_text()
  self.assertIn('admitted_cases.json remains CANONICAL',doc)
  self.assertIn('peer-reverified',doc)
 def test_import_performs_no_network_or_audit(self):
  with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('network during import')),patch('socket.getaddrinfo',side_effect=AssertionError('DNS during import')),patch('time.sleep',side_effect=AssertionError('sleep during import')):
   load()
if __name__=='__main__':unittest.main()
