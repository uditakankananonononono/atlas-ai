"""Five independent refusal fixtures for the frozen local-rename core."""
import importlib.util
from pathlib import Path
import unittest
PATH = Path(__file__).resolve().parents[2] / 'backend/app/modules/m20_general_cognitive_worker/local_rename_refactor689.py'
spec = importlib.util.spec_from_file_location('signature_pins', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class SignaturePins(unittest.TestCase):
    def test_single_non_function_statement(self):
        with self.assertRaisesRegex(ValueError, '^exactly one plain function required$'):
            module.rename_local('subtotal = 1\n', 'subtotal', 'total')

    def test_positional_default_only(self):
        with self.assertRaisesRegex(ValueError, '^decorators, annotations, defaults and variadics unsupported$'):
            module.rename_local('def f(x=1):\n subtotal = x\n return subtotal\n', 'subtotal', 'total')

    def test_keyword_default_only(self):
        with self.assertRaisesRegex(ValueError, '^decorators, annotations, defaults and variadics unsupported$'):
            module.rename_local('def f(*, x=1):\n subtotal = x\n return subtotal\n', 'subtotal', 'total')

    def test_varargs_only(self):
        with self.assertRaisesRegex(ValueError, '^decorators, annotations, defaults and variadics unsupported$'):
            module.rename_local('def f(*args):\n subtotal = 1\n return subtotal\n', 'subtotal', 'total')

    def test_kwargs_only(self):
        with self.assertRaisesRegex(ValueError, '^decorators, annotations, defaults and variadics unsupported$'):
            module.rename_local('def f(**kwargs):\n subtotal = 1\n return subtotal\n', 'subtotal', 'total')

if __name__ == '__main__': unittest.main(verbosity=2)
