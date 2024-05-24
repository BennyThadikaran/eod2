import unittest
from context import defs
from pathlib import Path
from types import ModuleType

dir = Path(__file__).parent

code = """class Test:
    def foo(self):
        return "bar"
"""


class TestGetModule(unittest.TestCase):
    def setUp(self) -> None:
        self.fname = dir / "mod_test.py"
        self.fname.write_text(code)

    def tearDown(self) -> None:
        self.fname.unlink()

    def test_load_module_without_class(self):
        module = defs.load_module(str(self.fname))
        self.assertIsInstance(module, ModuleType)
        self.assertEqual(module.__name__, self.fname.stem)

    def test_load_module_with_class(self):
        module = defs.load_module(f"{self.fname}:Test")
        self.assertIsInstance(module, type)
        self.assertEqual(module.__name__, "Test")

    def test_load_nonexistent_module(self):
        with self.assertRaises(ModuleNotFoundError):
            defs.load_module("nonexistent_module.py")

    def test_load_module_with_nonexistent_class(self):
        with self.assertRaises(AttributeError):
            defs.load_module(f"{self.fname}:NonexistentClass")
