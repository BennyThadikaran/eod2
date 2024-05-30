import unittest
import tempfile
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

        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            self.tmp_file = Path(f.name)

    def tearDown(self) -> None:
        self.fname.unlink()
        self.tmp_file.unlink()

    def test_without_class(self):
        """Load a module without Class"""

        module = defs.load_module(str(self.fname))
        self.assertIsInstance(module, ModuleType)
        self.assertEqual(module.__name__, self.fname.stem)

    def test_with_class(self):
        """Load a module specifying the class. Returns the class"""

        module = defs.load_module(f"{self.fname}|Test")
        self.assertIsInstance(module, type)
        self.assertEqual(module.__name__, "Test")
        self.assertEqual(module().foo(), "bar")

    def test_with_nonexistent_module(self):
        """Passing a nonexistent_module raises FileNotFoundError"""

        with self.assertRaises(FileNotFoundError):
            defs.load_module("nonexistent_module.py")

    def test_with_nonexistent_class(self):
        """Passing a non existent class raises AttributeError"""

        with self.assertRaises(AttributeError):
            defs.load_module(f"{self.fname}|NonexistentClass")

    def test_loading_from_any_directory(self):
        """Module can be loaded from any directory even outside of project root"""

        module = defs.load_module(f"{self.tmp_file}|Test")
        self.assertIsInstance(module, type)
        self.assertEqual(module.__name__, "Test")


if __name__ == "__main__":
    unittest.main()
