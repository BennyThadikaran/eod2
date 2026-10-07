import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from context import defs

HEADER = (
    b"Date,Open,High,Low,Close,Volume,Series,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n"
)
ROW_1 = b"2024-05-01,1,1,1,1,100,EQ,10,10.0,50\n"
ROW_2 = b"2024-05-02,2,2,2,2,200,EQ,20,10.0,60\n"


class TestRollbackRowBoundaries(unittest.TestCase):
    """A rollback must leave every row newline terminated, so a row appended
    by the next sync starts on its own line instead of welding onto the
    previous row."""

    def setUp(self) -> None:
        with NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(HEADER + ROW_1 + ROW_2)
            self.tempfile = Path(f.name)

    def tearDown(self) -> None:
        self.tempfile.unlink()

    def test_rollback_preserves_trailing_newline(self):
        self.assertTrue(defs.deleteLastLineByDate(self.tempfile, "2024-05-02"))
        self.assertTrue(self.tempfile.read_bytes().endswith(b"\n"))

    def test_row_appended_after_rollback_starts_new_line(self):
        self.assertTrue(defs.deleteLastLineByDate(self.tempfile, "2024-05-02"))

        # mimics the next sync: updateNseSymbol appends the session row
        with patch.object(
            defs, "dates", SimpleNamespace(pandasDt="2024-05-02", dt=None)
        ):
            defs.updateNseSymbol(self.tempfile, "EQ", 2, 2, 2, 2, 200, 20, 60)

        df = pd.read_csv(self.tempfile)
        self.assertEqual(list(df["Date"]), ["2024-05-01", "2024-05-02"])


if __name__ == "__main__":
    unittest.main()
