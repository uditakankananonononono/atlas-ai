"""Behavior and refusal tests for a deliberately bounded Python refactor."""
import ast
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[2] / 'backend/app/modules/m20_general_cognitive_worker/local_rename_refactor689.py'
spec = importlib.util.spec_from_file_location('refactor689', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
rename_local = module.rename_local

class RefactorTests(unittest.TestCase):
    def reject(self, source, old='subtotal', new='total'):
        with self.assertRaises(ValueError):
            rename_local(source, old, new)

    def test_actual_source_and_behavior(self):
        source = 'def price(x):\n subtotal = x * 2\n if subtotal < 0:\n  subtotal = -subtotal\n return subtotal + 1\n'
        result = rename_local(source, 'subtotal', 'total')
        self.assertNotEqual(source, result['source'])
        self.assertNotIn('subtotal', result['source'])
        self.assertIn('total', result['source'])
        before, after = {}, {}
        exec(source, before)
        exec(result['source'], after)
        for x in [-10, -1, 0, 1, 20, 0.25]:
            self.assertEqual(before['price'](x), after['price'](x))
        self.assertEqual(result['renamed_occurrences'], 5)
        self.assertFalse(result['repository_behavior_verified'])

    def test_loop_and_augmented_assignment(self):
        source = 'def f(xs):\n subtotal = 0\n for x in xs:\n  subtotal += x\n return subtotal\n'
        result = rename_local(source, 'subtotal', 'sum_value')
        a, b = {}, {}
        exec(source, a); exec(result['source'], b)
        for xs in [[], [1, 2, 3], [-1, 2.5]]:
            self.assertEqual(a['f'](xs), b['f'](xs))

    def test_exception_behavior(self):
        source = 'def f(x):\n subtotal = 1 / x\n return subtotal\n'
        a, b = {}, {}
        exec(source, a); exec(rename_local(source, 'subtotal', 'ratio')['source'], b)
        for ns in [a, b]:
            with self.assertRaises(ZeroDivisionError): ns['f'](0)

    def test_parameter_cannot_be_renamed(self): self.reject('def f(subtotal):\n return subtotal\n')
    def test_parameter_collision(self): self.reject('def f(total):\n subtotal = 2\n return subtotal\n')
    def test_local_collision(self):
        with self.assertRaisesRegex(ValueError, 'replacement already occurs'):
            rename_local('def f(x):\n total = 1\n subtotal = x\n return total + subtotal\n', 'subtotal', 'total')
    def test_global_name_collision(self): self.reject('def f(x):\n subtotal = x\n return subtotal + total\n')
    def test_unbound_name_not_local(self): self.reject('def f(x):\n return subtotal + x\n')
    def test_calls_rejected(self): self.reject('def f(x):\n subtotal = x\n return locals()\n')
    def test_nested_scope_rejected(self): self.reject('def f(x):\n subtotal = x\n def g():\n  return subtotal\n return subtotal\n')
    def test_comprehension_rejected(self): self.reject('def f(x):\n subtotal = [a for a in x]\n return subtotal\n')
    def test_global_rejected(self): self.reject('def f(x):\n global subtotal\n subtotal = x\n return subtotal\n')
    def test_attribute_rejected(self): self.reject('def f(x):\n subtotal = x.value\n return subtotal\n')
    def test_import_rejected(self): self.reject('def f(x):\n import sys\n subtotal = x\n return subtotal\n')
    def test_module_statements_rejected(self): self.reject('x = 1\ndef f(x):\n subtotal = x\n return subtotal\n')
    def test_multiple_functions_rejected(self): self.reject('def f(x):\n subtotal = x\n return subtotal\ndef g():\n return 1\n')
    def test_invalid_identifiers(self):
        for new in ['class', '1x', '', 'subtotal', '__hidden', 'é']:
            self.reject('def f(x):\n subtotal = x\n return subtotal\n', new=new)
    def test_annotations_defaults_decorators_rejected(self):
        for source in ['def f(x: int):\n subtotal = x\n return subtotal\n', 'def f(x=1):\n subtotal = x\n return subtotal\n', '@decorator\ndef f(x):\n subtotal = x\n return subtotal\n']:
            self.reject(source)
    def test_syntax_error_and_types(self):
        self.reject('not valid python !')
        for source in [None, 123]: self.reject(source)
    def test_deterministic_hashes_and_input_untouched(self):
        source = 'def f(x):\n subtotal = x + 1\n return subtotal\n'
        a = rename_local(source, 'subtotal', 'total')
        self.assertEqual(a, rename_local(source, 'subtotal', 'total'))
        self.assertEqual(len(a['before_sha256']), 64)
        self.assertNotEqual(a['before_sha256'], a['after_sha256'])
        self.assertTrue(a['ast_alpha_equivalence_checked'])
        self.assertIn('subtotal', source)

if __name__ == '__main__': unittest.main()
