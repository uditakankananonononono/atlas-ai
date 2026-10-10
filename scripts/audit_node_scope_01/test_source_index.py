"""Authored NOT RUN. Only helper loaded; target source never imported/executed."""
import importlib.util
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('atlas_audit_node_scope_01', HERE / 'source_index.py')
index = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = index
SPEC.loader.exec_module(index)


@pytest.fixture
def source_root(tmp_path):
    (tmp_path / 'test_fixture.py').write_text((HERE / 'fixture_source.txt').read_text(), encoding='utf-8')
    return tmp_path


@pytest.mark.parametrize('node', ['test_module', 'test_async_module',
                                  'TestOuter::test_method', 'TestOuter::test_async_method',
                                  'TestOuter::TestInner::test_inner'])
def test_explicit_module_and_class_paths(source_root, node):
    result = index.validate_reference('test_fixture.py::' + node, root=source_root)
    assert result.structural_source_match
    assert result.reason == 'structural_source_match'
    assert not result.parameter_case_verified


@pytest.mark.parametrize('node', ['test_method', 'test_async_method', 'test_inner', 'test_nested',
                                  'helper::test_nested', 'Utility::helper::test_hidden',
                                  'MissingClass::test_method', 'TestOuter::test_absent'])
def test_nested_bare_methods_and_nonexistent_paths_fail(source_root, node):
    result = index.validate_reference('test_fixture.py::' + node, root=source_root)
    assert not result.structural_source_match
    assert result.reason == 'node_path_not_found'


@pytest.mark.parametrize('reference', ['', 'test_fixture.py', 'test_fixture.py::',
                                       'test_fixture.py::test_module[]',
                                       'test_fixture.py::test_module[a[b]]',
                                       'test_fixture.py::test_module[case',
                                       'test_fixture.py::Test Outer::test_method',
                                       'test_fixture.py::helper', '../test_fixture.py::test_module',
                                       '/tmp/test_fixture.py::test_module',
                                       'fixture.txt::test_module', 'test_fixture.py::test_module\n', None])
def test_malformed_inputs_distinct(source_root, reference):
    result = index.validate_reference(reference, root=source_root)
    assert not result.structural_source_match and result.reason == 'malformed_reference'


def test_parameter_suffix_never_verifies_case_existence(source_root):
    result = index.validate_reference('test_fixture.py::test_module[nonexistent-case]', root=source_root)
    assert result.structural_source_match and result.parameter_suffix_present
    assert result.parameter_case_verified is False


def test_missing_and_directory_are_distinct(source_root):
    assert index.validate_reference('missing.py::test_module', root=source_root).reason == 'source_missing'
    (source_root / 'directory.py').mkdir()
    assert index.validate_reference('directory.py::test_module', root=source_root).reason == 'source_not_regular_file'


def test_unreadable_source_distinct(source_root, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError('synthetic unreadable file')
    monkeypatch.setattr(Path, 'read_text', denied)
    result = index.validate_reference('test_fixture.py::test_module', root=source_root)
    assert result.reason == 'source_unreadable' and not result.structural_source_match


def test_decode_and_syntax_invalid_are_distinct(source_root):
    (source_root / 'invalid.py').write_text('def test_broken(:', encoding='utf-8')
    assert index.validate_reference('invalid.py::test_broken', root=source_root).reason == 'source_syntax_invalid'
    (source_root / 'bytes.py').write_bytes(b'\xff')
    assert index.validate_reference('bytes.py::test_module', root=source_root).reason == 'source_decode_error'


def test_symlink_escape_fails_closed(source_root, tmp_path):
    outside = tmp_path.parent / (tmp_path.name + '-outside.py')
    outside.write_text('def test_outside(): pass', encoding='utf-8')
    (source_root / 'link.py').symlink_to(outside)
    result = index.validate_reference('link.py::test_outside', root=source_root)
    assert not result.structural_source_match and result.reason == 'source_path_outside_root'


def test_duplicate_or_rebound_declarations_fail_closed():
    source = ('def test_duplicate(): pass\ndef test_duplicate(): pass\n'
              'def test_rebound(): pass\ntest_rebound = 1\n'
              'class TestDuplicate:\n def test_m(): pass\n'
              'class TestDuplicate:\n def test_n(): pass\n')
    assert index.structural_paths(source) == frozenset()


def test_conditional_declarations_not_claimed():
    source = 'if True:\n def test_conditional(): pass\n'
    assert index.structural_paths(source) == frozenset()


def test_embedded_nul_filename_is_malformed(source_root):
    result = index.validate_reference('bad\x00.py::test_module', root=source_root)
    assert not result.structural_source_match and result.reason == 'malformed_reference'


def test_utf8_bom_source_supported(source_root):
    (source_root / 'bom.py').write_bytes(b'\xef\xbb\xbfdef test_bom(): pass\n')
    result = index.validate_reference('bom.py::test_bom', root=source_root)
    assert result.structural_source_match and result.reason == 'structural_source_match'


@pytest.mark.parametrize('statement', [
    'for test_name in []:\n pass\n',
    'with manager() as test_name:\n pass\n',
    'try:\n pass\nexcept Exception as test_name:\n pass\n',
    '(test_name := 1)\n',
    'del test_name\n',
])
def test_complex_bindings_are_explicitly_outside_static_contract(statement):
    # This records non-coverage, not runtime survival of the declaration.
    source = 'def test_name(): pass\n' + statement
    assert index.structural_paths(source) == frozenset({('test_name',)})
