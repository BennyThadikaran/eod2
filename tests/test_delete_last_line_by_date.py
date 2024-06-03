import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile
from context import defs


class TestDeleteLastLineByDate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with NamedTemporaryFile(mode="w+", delete=False) as f:
            f.write("")
            cls.empty_file = Path(f.name)

        with NamedTemporaryFile(mode="w+", delete=False) as f:
            f.write("Date,Open,High,Low,Close")
            cls.str_only_file = Path(f.name)

    @classmethod
    def tearDownClass(cls):
        cls.empty_file.unlink()
        cls.str_only_file.unlink()

    def setUp(self) -> None:
        with NamedTemporaryFile(mode="w+", delete=False) as f:
            f.write("2024-05-01,1\n2024-05-02,1\n2024-05-03,1\n")
            self.tempfile = Path(f.name)

    def tearDown(self) -> None:
        self.tempfile.unlink()

    def test_date_found(self):
        self.assertTrue(defs.deleteLastLineByDate(self.tempfile, "2024-05-03"))

        result = self.tempfile.read_text()
        self.assertEqual(result.strip(), "2024-05-01,1\n2024-05-02,1")

    def test_date_not_found(self):
        self.assertFalse(defs.deleteLastLineByDate(self.tempfile, "2024-05-04"))

    def test_empty_file(self):
        self.assertFalse(
            defs.deleteLastLineByDate(self.empty_file, "2024-05-04")
        )

    def test_file_string_no_date(self):

        self.assertFalse(
            defs.deleteLastLineByDate(self.str_only_file, "2024-05-04")
        )


if __name__ == "__main__":
    unittest.main()
