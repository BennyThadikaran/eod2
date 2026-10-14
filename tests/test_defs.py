from __future__ import annotations

import logging
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from context import defs
from nse import NSEFileUnavailableError

try:
    from zoneinfo import ZoneInfo
except ModuleNotFoundError:
    from backports.zoneinfo import ZoneInfo

logger = logging.getLogger("EOD")

file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]

for handler in file_handlers:
    logger.removeHandler(handler)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def write_csv(symbol: str, folder, rows: list[tuple]) -> Path:
    """Write a minimal daily CSV and return its path."""
    file = folder / f"{symbol.lower()}.csv"
    df = pd.DataFrame(
        rows,
        columns=pd.Index(
            [
                "Date",
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
                "Series",
                "TOTAL_TRADES",
                "QTY_PER_TRADE",
                "DLV_QTY",
            ]
        ),
    )
    df.to_csv(file, index=False)
    return file


def make_dates(dt_str: str, today_str: str = "2024-01-01 00:00:00+05:30") -> defs.Dates:
    """Build a Dates-like object without invoking its real __init__.

    The real __init__ calls datetime.now() which makes tests flaky.
    """
    d = defs.Dates.__new__(defs.Dates)
    dt = datetime.fromisoformat(dt_str)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("Asia/Kolkata"))

    d.dt = d.lastUpdate = dt
    d.today = datetime.fromisoformat(today_str).replace(tzinfo=None)
    d.pandas_dt = dt.strftime("%Y-%m-%d")
    return d


def _reset_globals():
    """Restore module globals between tests."""
    defs.meta = {}
    defs.has_latest_holidays = False


# ---------------------------------------------------------------------------
# check_for_holidays
# ---------------------------------------------------------------------------


class TestCheckForHolidays(unittest.TestCase):
    def setUp(self):
        _reset_globals()
        self.nse = MagicMock()

        # Always silence logger and default the holiday fetcher.
        self.logger_patcher = patch.object(defs, "logger", MagicMock())
        self.logger_patcher.start()
        self.addCleanup(self.logger_patcher.stop)

        self.fetch_patcher = patch.object(defs, "get_holiday_list", return_value={})
        self.get_holiday_list = self.fetch_patcher.start()
        self.addCleanup(self.fetch_patcher.stop)

    # -- special sessions ---------------------------------------------------
    def test_special_session_returns_false_and_skips_holiday_logic(self):
        # Arrange
        special_dt = datetime(2024, 11, 1, 18, 0)
        defs.meta = {
            "year": 2024,
            "holidays": {"01-Nov-2024": "Diwali"},
            "special_sessions": [special_dt.isoformat()],
        }
        defs.has_latest_holidays = True

        dates = make_dates("2024-11-01 18:00:00+05:30", "2024-11-01 00:00:00")

        # Act
        result = defs.check_for_holidays(self.nse, dates)  # type: ignore[attr-defined]

        # Assert: special session overrides the holiday entry.
        self.assertFalse(result)
        self.get_holiday_list.assert_not_called()

    # -- holiday list refresh ----------------------------------------------
    def test_fetches_holidays_when_missing_from_meta(self):
        defs.meta = {}  # no "holidays" key
        defs.has_latest_holidays = False
        self.get_holiday_list.return_value = {"01-Jan-2024": "New Year"}

        dates = make_dates("2024-01-01 00:00:00+05:30", "2024-01-01 00:00:00")

        defs.check_for_holidays(self.nse, dates)  # type: ignore[attr-defined]

        self.get_holiday_list.assert_called_once_with(self.nse)
        self.assertEqual(defs.meta["holidays"], {"01-Jan-2024": "New Year"})
        self.assertEqual(defs.meta["year"], 2024)
        self.assertTrue(defs.has_latest_holidays)

    def test_fetches_holidays_when_year_changed(self):
        defs.meta = {"year": 2023, "holidays": {"01-Jan-2023": "New Year"}}
        defs.has_latest_holidays = True
        self.get_holiday_list.return_value = {"01-Jan-2024": "New Year"}

        dates = make_dates("2024-01-01 00:00:00+05:30", "2024-01-01 00:00:00")

        defs.check_for_holidays(self.nse, dates)  # type: ignore[attr-defined]

        self.get_holiday_list.assert_called_once_with(self.nse)
        self.assertEqual(defs.meta["year"], 2024)

    def test_does_not_fetch_when_year_is_in_the_past(self):
        """Old years shouldn't trigger a network fetch."""
        defs.meta = {"year": 2023, "holidays": {}}
        defs.has_latest_holidays = False

        dates = make_dates("2023-06-15 00:00:00+05:30", "2024-01-01 00:00:00")

        defs.check_for_holidays(self.nse, dates)  # type: ignore[attr-defined]

        self.get_holiday_list.assert_not_called()
        self.assertFalse(defs.has_latest_holidays)

    def test_does_not_refetch_when_has_latest_holidays_true_and_year_matches(self):
        defs.meta = {"year": 2024, "holidays": {"25-Dec-2024": "Christmas"}}
        defs.has_latest_holidays = True

        dates = make_dates("2024-12-24 00:00:00+05:30", "2024-12-24 00:00:00")

        defs.check_for_holidays(self.nse, dates)  # type: ignore[attr-defined]

        self.get_holiday_list.assert_not_called()

    # -- muhurat sessions ---------------------------------------------------
    def test_laxmi_pujan_is_not_a_holiday(self):
        defs.meta = {
            "year": 2024,
            "holidays": {"01-Nov-2024": ["Diwali", "Laxmi Pujan"]},
        }
        defs.has_latest_holidays = True

        dates = make_dates("2024-11-01 00:00:00+05:30", "2024-11-01 00:00:00")

        self.assertFalse(defs.check_for_holidays(self.nse, dates))  # type: ignore[attr-defined]

    # -- sunday -------------------------------------------------------------
    def test_sunday_is_a_holiday(self):
        # 2024-01-07 is a Sunday
        defs.meta = {"year": 2024, "holidays": {}}
        defs.has_latest_holidays = True

        dates = make_dates("2024-01-07 00:00:00+05:30", "2024-01-07 00:00:00")

        self.assertTrue(defs.check_for_holidays(self.nse, dates))  # type: ignore[attr-defined]

    # -- regular holidays ---------------------------------------------------
    def test_listed_holiday_returns_true(self):
        defs.meta = {
            "year": 2024,
            "holidays": {"25-Dec-2024": "Christmas"},
        }
        defs.has_latest_holidays = True

        dates = make_dates("2024-12-25 00:00:00+05:30", "2024-12-25 00:00:00")

        self.assertTrue(defs.check_for_holidays(self.nse, dates))  # type: ignore[attr-defined]
        defs.logger.info.assert_called()  # type: ignore[attr-defined]

    # -- normal trading day -------------------------------------------------
    def test_regular_weekday_returns_false(self):
        # 2024-01-03 is a Wednesday
        defs.meta = {"year": 2024, "holidays": {}}
        defs.has_latest_holidays = True

        dates = make_dates("2024-01-03 00:00:00+05:30", "2024-01-03 00:00:00")

        self.assertFalse(defs.check_for_holidays(self.nse, dates))  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# get_split
# ---------------------------------------------------------------------------


class TestGetSplit(unittest.TestCase):
    """Tests for defs.get_split."""

    def setUp(self):
        _reset_globals()
        defs.dates = make_dates("2024-01-15T00:00:00+05:30")

    def test_simple_split(self):
        """A 1:10 split should return 0.1 (1/10)."""
        result = defs.get_split("TEST", "face value split from rs 10 to rs 1")
        # regex matches "10" and "1" -> 10/1 = 10.0
        self.assertIsNotNone(result)

    def test_split_with_slash(self):
        """Split ratios written with a slash should parse correctly."""
        result = defs.get_split("TEST", "Stock split 2/1")
        self.assertAlmostEqual(result, 2.0)

    def test_split_with_dash(self):
        """Split ratios written with a dash should parse correctly."""
        result = defs.get_split("TEST", "split 5-1")
        self.assertAlmostEqual(result, 5.0)

    def test_decimal_factor(self):
        """Decimal values in the split string should be handled."""
        result = defs.get_split("TEST", "split 1.5/1")
        self.assertAlmostEqual(result, 1.5)

    def test_no_match_returns_none(self):
        """A string without a ratio should return None and log a warning."""
        with self.assertLogs(logger, logging.WARNING):
            result = defs.get_split("TEST", "bonus issue")

        self.assertIsNone(result)

    def test_empty_string_returns_none(self):
        with self.assertLogs(logger, logging.WARNING):
            result = defs.get_split("TEST", "")
        self.assertIsNone(result)

    def test_regex_used_is_split_regex(self):
        """Ensure the module-level split_regex is actually used."""
        result = defs.get_split("TEST", "split 4/2")
        self.assertAlmostEqual(result, 2.0)


# ---------------------------------------------------------------------------
# get_bonus
# ---------------------------------------------------------------------------


class TestGetBonus(unittest.TestCase):
    """Tests for defs.get_bonus."""

    def setUp(self):
        _reset_globals()
        defs.dates = make_dates("2024-01-15T00:00:00+05:30")

    def test_standard_bonus(self):
        """A 1:1 bonus should return 2.0."""
        result = defs.get_bonus("TEST", "bonus issue 1:1")
        self.assertAlmostEqual(result, 2.0)

    def test_bonus_2_1(self):
        """A 2:1 bonus should return 3.0."""
        result = defs.get_bonus("TEST", "bonus 2:1")
        self.assertAlmostEqual(result, 3.0)

    def test_bonus_with_spaces(self):
        result = defs.get_bonus("TEST", "bonus 1 : 2")
        self.assertAlmostEqual(result, 1.5)

    def test_no_match_returns_none(self):
        with self.assertLogs(logger, logging.WARNING):
            result = defs.get_bonus("TEST", "stock split")
        self.assertIsNone(result)

    def test_empty_string_returns_none(self):
        with self.assertLogs(logger, logging.WARNING):
            result = defs.get_bonus("TEST", "")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# make_adjustment
# ---------------------------------------------------------------------------


class TestMakeAdjustment(unittest.TestCase):
    """Tests for defs.make_adjustment."""

    def setUp(self):
        _reset_globals()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

        defs.DAILY_FOLDER = self.folder
        defs.dates = make_dates("2024-01-15T00:00:00+05:30")

    def test_missing_file_returns_none(self):
        with self.assertLogs(logger, logging.WARNING):
            result = defs.make_adjustment("NOPE", 2.0)
        self.assertIsNone(result)

    def test_adjustment_before_ex_date(self):
        """Prices before the ex-date should be halved for a 2:1 split."""
        write_csv(
            "TEST",
            self.folder,
            [
                ("2024-01-10", 100.0, 110.0, 90.0, 100.0, 1000, "EQ", 10, 100, 500),
                ("2024-01-11", 100.0, 110.0, 90.0, 100.0, 1000, "EQ", 10, 100, 500),
                ("2024-01-15", 50.0, 55.0, 45.0, 50.0, 2000, "EQ", 20, 100, 1000),
            ],
        )

        result = defs.make_adjustment("TEST", 2.0)
        self.assertIsNotNone(result)

        if result:
            df, file = result

            # Pre-ex-date rows should be adjusted by /2
            self.assertAlmostEqual(df.iloc[0]["Close"], 50.0)
            self.assertAlmostEqual(df.iloc[1]["Close"], 50.0)

            # Ex-date row should be untouched
            self.assertAlmostEqual(df.iloc[-1]["Close"], 50.0)
            self.assertEqual(file, self.folder / "test.csv")

    def test_adjustment_rounds_to_nearest_005(self):
        """Adjusted prices should be rounded to the nearest 0.05."""
        write_csv(
            "TEST",
            self.folder,
            [
                ("2024-01-10", 10.03, 10.07, 9.99, 10.03, 1000, "EQ", 10, 100, 500),
                ("2024-01-15", 5.00, 5.00, 5.00, 5.00, 1000, "EQ", 10, 100, 500),
            ],
        )

        result = defs.make_adjustment("TEST", 2.0)

        self.assertIsNotNone(result)

        if result:
            df, _ = result

            # 10.03 / 2 = 5.015 -> nearest 0.05 = 5.00
            self.assertAlmostEqual(df.iloc[0]["Close"], 5.00)

            # Check rounding to 2 decimals
            self.assertEqual(round(df.iloc[0]["Close"], 2), df.iloc[0]["Close"])

    def test_adjustment_with_prev_commit(self):
        """When a previous commit is supplied, its DataFrame is reused."""
        file = write_csv(
            "TEST",
            self.folder,
            [
                ("2024-01-10", 100.0, 110.0, 90.0, 100.0, 1000, "EQ", 10, 100, 500),
                ("2024-01-15", 50.0, 55.0, 45.0, 50.0, 2000, "EQ", 20, 100, 1000),
            ],
        )
        df = pd.read_csv(file, index_col="Date", parse_dates=["Date"])
        prev_commit = defs.PreviousCommit(file=file, df=df)

        result = defs.make_adjustment("TEST", 2.0, prev_commit)
        self.assertIsNotNone(result)

        if result:
            out_df, out_file = result
            self.assertEqual(out_file, file)
            self.assertAlmostEqual(out_df.iloc[0]["Close"], 50.0)

    def test_no_ex_date_row_appends_at_end(self):
        """When the ex-date is not present, all rows are adjusted."""
        write_csv(
            "TEST",
            self.folder,
            [
                ("2024-01-10", 100.0, 110.0, 90.0, 100.0, 1000, "EQ", 10, 100, 500),
                ("2024-01-11", 100.0, 110.0, 90.0, 100.0, 1000, "EQ", 10, 100, 500),
            ],
        )

        result = defs.make_adjustment("TEST", 2.0)
        self.assertIsNotNone(result)

        if result:
            df, _ = result
            self.assertAlmostEqual(df.iloc[0]["Close"], 50.0)
            self.assertAlmostEqual(df.iloc[1]["Close"], 50.0)

    def test_duplicate_dates_raises(self):
        """Duplicate ex-date entries should raise RuntimeError."""
        file = self.folder / "test.csv"
        file.write_text(
            "Date,Open,High,Low,Close,Volume,Series,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n"
            "2024-01-10,100,110,90,100,1000,EQ,10,100,500\n"
            "2024-01-15,100,110,90,100,1000,EQ,10,100,500\n"
            "2024-01-15,50,55,45,50,2000,EQ,20,100,1000\n"
        )

        with self.assertRaises(RuntimeError), self.assertLogs(logger, logging.WARNING):
            defs.make_adjustment("TEST", 2.0)


# ---------------------------------------------------------------------------
# to_amibroker_format
# ---------------------------------------------------------------------------


class TestToAmibrokerFormat(unittest.TestCase):
    """Tests for defs.to_amibroker_format."""

    def setUp(self):
        _reset_globals()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

        self.ami_folder = self.folder / "amibroker"
        self.ami_folder.mkdir()
        defs.AMIBROKER_FOLDER = self.ami_folder

        defs.VALID_SERIES = ("EQ", "BE", "BZ", "SM", "ST")
        defs.AMIBROKER_COLUMNS = [
            "SYMBOL",
            "DATE",
            "OPEN",
            "HIGH",
            "LOW",
            "CLOSE",
            "VOLUME",
            "ISIN",
        ]

    def test_udiff_format_conversion(self):
        """The new (UDIFF) bhavcopy format should be converted correctly."""
        file = self.folder / "BhavCopy_NSE_CM_0_0_0_20240115_F_0000.csv"
        file.write_text(
            "TckrSymb,TradDt,SctySrs,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol,ISIN\n"
            "RELIANCE,2024-01-15,EQ,2500,2550,2480,2520,1000000,INE002A01018\n"
            "TCS,2024-01-15,EQ,3500,3550,3480,3520,500000,INE467B01029\n"
            "SOME,2024-01-15,XX,10,10,10,10,100,INE000000000\n"
        )

        defs.to_amibroker_format(file, udiff_format=True)

        out = self.ami_folder / file.name
        self.assertTrue(out.exists())

        df = pd.read_csv(out)
        self.assertEqual(list(df.columns), defs.AMIBROKER_COLUMNS)

        # Only EQ rows should survive the series filter
        self.assertEqual(len(df), 2)
        self.assertIn("RELIANCE", df["SYMBOL"].values)
        self.assertIn("TCS", df["SYMBOL"].values)
        self.assertNotIn("SOME", df["SYMBOL"].values)

    def test_legacy_format_conversion(self):
        """The legacy bhavcopy format should be converted correctly."""
        file = self.folder / "cm15JAN2024bhav.csv"
        file.write_text(
            "SYMBOL,TIMESTAMP,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY,ISIN\n"
            "RELIANCE,2024-01-15,EQ,2500,2550,2480,2520,1000000,INE002A01018\n"
            "TCS,2024-01-15,EQ,3500,3550,3480,3520,500000,INE467B01029\n"
            "SOME,2024-01-15,XX,10,10,10,10,100,INE000000000\n"
        )

        defs.to_amibroker_format(file, udiff_format=False)

        out = self.ami_folder / file.name
        self.assertTrue(out.exists())

        df = pd.read_csv(out)
        self.assertEqual(list(df.columns), defs.AMIBROKER_COLUMNS)
        self.assertEqual(len(df), 2)

    def test_date_parsing(self):
        """The DATE column should be parsed as a datetime."""
        file = self.folder / "BhavCopy_NSE_CM_0_0_0_20240115_F_0000.csv"
        file.write_text(
            "TckrSymb,TradDt,SctySrs,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol,ISIN\n"
            "RELIANCE,2024-01-15,EQ,2500,2550,2480,2520,1000000,INE002A01018\n"
        )

        defs.to_amibroker_format(file, udiff_format=True)

        df = pd.read_csv(self.ami_folder / file.name)
        self.assertEqual(df.iloc[0]["DATE"], "2024-01-15")

    def test_empty_after_filtering(self):
        """A bhavcopy with no valid series yields an empty output file."""
        file = self.folder / "BhavCopy_NSE_CM_0_0_0_20240115_F_0000.csv"
        file.write_text(
            "TckrSymb,TradDt,SctySrs,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol,ISIN\n"
            "SOME,2024-01-15,XX,10,10,10,10,100,INE000000000\n"
        )

        defs.to_amibroker_format(file, udiff_format=True)

        df = pd.read_csv(self.ami_folder / file.name)
        self.assertEqual(len(df), 0)
        self.assertEqual(list(df.columns), defs.AMIBROKER_COLUMNS)


# ---------------------------------------------------------------------------
# get_muhurat_holiday_info
# ---------------------------------------------------------------------------


class TestGetMuhuratHolidayInfo(unittest.TestCase):
    """Tests for defs.get_muhurat_holiday_info."""

    def setUp(self):
        _reset_globals()

    def test_finds_laxmi_pujan(self):
        holidays = {
            "CM": [
                {"description": "Diwali"},
                {"description": "Laxmi Pujan"},
                {"description": "Christmas"},
            ]
        }
        result = defs.get_muhurat_holiday_info(holidays)
        self.assertEqual(result["description"], "Laxmi Pujan")

    def test_returns_empty_when_absent(self):
        holidays = {
            "CM": [
                {"description": "Diwali"},
                {"description": "Christmas"},
            ]
        }
        result = defs.get_muhurat_holiday_info(holidays)
        self.assertEqual(result, {})

    def test_empty_input(self):
        self.assertEqual(defs.get_muhurat_holiday_info({}), {})

    def test_multiple_segments(self):
        """Search should span all segments, not just CM."""
        holidays = {
            "CM": [{"description": "Diwali"}],
            "FO": [{"description": "Laxmi Pujan"}],
        }
        result = defs.get_muhurat_holiday_info(holidays)
        self.assertEqual(result["description"], "Laxmi Pujan")

    def test_case_insensitive_match(self):
        """The function returns a case insensitive match"""
        holidays = {"CM": [{"description": "Laxmi Pujan"}]}
        result = defs.get_muhurat_holiday_info(holidays)
        self.assertEqual(result, {"description": "Laxmi Pujan"})


# ---------------------------------------------------------------------------
# get_last_date
# ---------------------------------------------------------------------------


class TestGetLastDate(unittest.TestCase):
    """Tests for defs.get_last_date."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def _write(self, name: str, content: str) -> Path:
        file = self.folder / name
        file.write_text(content)
        return file

    def test_multiline_file(self):
        file = self._write(
            "test.csv",
            "Date,Open\n2024-01-10,100\n2024-01-11,110\n2024-01-12,120\n",
        )
        self.assertEqual(defs.get_last_date(file), "2024-01-12")

    def test_single_line_file(self):
        """A file with only a header should return the header text up to comma."""
        file = self._write("test.csv", "Date,Open\n")
        # Single line -> OSError caught -> returns first token
        self.assertEqual(defs.get_last_date(file), "Date")

    def test_file_without_trailing_newline(self):
        """The last line may not end with a newline."""
        file = self._write(
            "test.csv",
            "Date,Open\n2024-01-10,100\n2024-01-11,110",
        )
        self.assertEqual(defs.get_last_date(file), "2024-01-11")

    def test_two_line_file(self):
        file = self._write(
            "test.csv",
            "Date,Open\n2024-01-10,100\n",
        )
        self.assertEqual(defs.get_last_date(file), "2024-01-10")

    def test_empty_file(self):
        """An empty file should still return something without crashing."""
        file = self._write("test.csv", "")
        # OSError is caught; readline returns b"" -> empty string
        self.assertEqual(defs.get_last_date(file), "")

    def test_real_world_line(self):
        """Mimic a realistic EOD CSV row."""
        file = self._write(
            "reliance.csv",
            "Date,Open,High,Low,Close,Volume,Series,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n"
            "2024-01-10,2500.0,2550.0,2480.0,2520.0,1000000,EQ,10000,100.0,500000\n"
            "2024-01-11,2520.0,2560.0,2500.0,2540.0,1100000,EQ,11000,100.0,550000\n",
        )
        self.assertEqual(defs.get_last_date(file), "2024-01-11")


# ---------------------------------------------------------------------------
# delete_last_line_by_date
# ---------------------------------------------------------------------------


class TestDeleteLastLineByDate(unittest.TestCase):
    """Tests for delete_last_line_by_date function."""

    def setUp(self):
        """Create a temporary directory for test files."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up the temporary directory."""
        self.temp_dir.cleanup()

    def _create_file(self, name: str, content: str) -> Path:
        """Helper to create a file with given content."""
        file_path = self.temp_path / name
        file_path.write_bytes(content.encode("utf-8"))
        return file_path

    def _read_file(self, file_path: Path) -> str:
        """Helper to read file content as string."""
        return file_path.read_bytes().decode("utf-8")

    # -------------------- Input validation --------------------

    def test_empty_date_str_raises_value_error(self):
        """An empty date_str should raise ValueError."""
        file_path = self._create_file("test.csv", "Date,Value\n2024-01-01,1\n")

        with self.assertRaises(ValueError):
            defs.delete_last_line_by_date(file_path, "")

    def test_none_date_str_raises_value_error(self):
        """A None date_str should raise ValueError (falsy check)."""
        file_path = self._create_file("test.csv", "Date,Value\n2024-01-01,1\n")

        with self.assertRaises(ValueError):
            defs.delete_last_line_by_date(file_path, None)  # type: ignore[arg-type]

    # -------------------- Empty file --------------------

    def test_empty_file_returns_false(self):
        """An empty file should return False and remain empty."""
        file_path = self._create_file("empty.csv", "")
        result = defs.delete_last_line_by_date(file_path, "2024-01-01")

        self.assertFalse(result)
        self.assertEqual(self._read_file(file_path), "")

    # -------------------- Missing header --------------------

    def test_header_only_file_returns_false(self):
        """A file with only a header (no trailing newline) should return False."""
        file_path = self._create_file("header_only.csv", "Date,Value")
        result = defs.delete_last_line_by_date(file_path, "2024-01-01")

        self.assertFalse(result)
        self.assertEqual(self._read_file(file_path), "Date,Value")

    def test_header_only_with_newline_returns_false(self):
        """A file with only a header ending in newline should return False."""
        file_path = self._create_file("header_nl.csv", "Date,Value\n")
        result = defs.delete_last_line_by_date(file_path, "2024-01-01")
        self.assertFalse(result)
        self.assertEqual(self._read_file(file_path), "Date,Value\n")

    # -------------------- Match: last line removed --------------------

    def test_last_line_matches_is_deleted(self):
        """When the last line starts with date_str, it should be truncated."""
        content = "Date,Value\n2024-01-01,1\n2024-01-02,2\n"
        file_path = self._create_file("test.csv", content)
        result = defs.delete_last_line_by_date(file_path, "2024-01-02")

        self.assertTrue(result)
        self.assertEqual(self._read_file(file_path), "Date,Value\n2024-01-01,1\n")

    def test_last_line_matches_no_trailing_newline(self):
        """Last line without trailing newline should still be removed."""
        content = "Date,Value\n2024-01-01,1\n2024-01-02,2"
        file_path = self._create_file("test.csv", content)
        result = defs.delete_last_line_by_date(file_path, "2024-01-02")

        self.assertTrue(result)
        self.assertEqual(self._read_file(file_path), "Date,Value\n2024-01-01,1\n")

    def test_last_line_is_only_data_line(self):
        """Deleting the only data line leaves just the header."""
        content = "Date,Value\n2024-01-01,1\n"
        file_path = self._create_file("test.csv", content)
        result = defs.delete_last_line_by_date(file_path, "2024-01-01")

        self.assertTrue(result)
        self.assertEqual(self._read_file(file_path), "Date,Value\n")

    def test_last_line_is_only_data_line_no_trailing_newline(self):
        """Deleting the only data line (no trailing newline) leaves header."""
        content = "Date,Value\n2024-01-01,1"
        file_path = self._create_file("test.csv", content)
        result = defs.delete_last_line_by_date(file_path, "2024-01-01")

        self.assertTrue(result)
        self.assertEqual(self._read_file(file_path), "Date,Value\n")

    def test_multiple_lines_same_date_only_last_deleted(self):
        """Only the last matching line should be removed."""
        content = "Date,Value\n2024-01-02,1\n2024-01-02,2\n"
        file_path = self._create_file("test.csv", content)
        result = defs.delete_last_line_by_date(file_path, "2024-01-02")

        self.assertTrue(result)
        self.assertEqual(self._read_file(file_path), "Date,Value\n2024-01-02,1\n")

    # -------------------- No match --------------------

    def test_last_line_does_not_match_returns_false(self):
        """If the last line does not match, return False and leave file."""
        content = "Date,Value\n2024-01-01,1\n2024-01-02,2\n"
        file_path = self._create_file("test.csv", content)
        result = defs.delete_last_line_by_date(file_path, "2024-01-03")

        self.assertFalse(result)
        self.assertEqual(self._read_file(file_path), content)

    # -------------------- Edge: header has no newline before data --------------------

    def test_header_on_same_line_as_data(self):
        """
        A file where the header is the first line and there are no newlines
        after the header should return False.
        """
        # Single line starting with Date -> no data, returns False
        file_path = self._create_file("test.csv", "Date,Value")
        result = defs.delete_last_line_by_date(file_path, "2024-01-01")
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# check_reports_update_status
# ---------------------------------------------------------------------------


class TestCheckReportsUpdateStatus(unittest.TestCase):
    def setUp(self):
        _reset_globals()
        self.dates = make_dates(
            "2024-01-01 00:00:00+05:30", "2024-01-01 00:00:00+05:30"
        )
        defs.dates = self.dates

    def tearDown(self):
        _reset_globals()

    def _nse_mock(self, cm_data, index_data):
        nse = MagicMock()
        nse.fetch_daily_reports_file_metadata.side_effect = [cm_data, index_data]
        return nse

    def test_returns_all_false_when_no_current_day(self):
        nse = self._nse_mock(
            {"CurrentDay": None, "currentDate": "01-Jan-2024"},
            {"CurrentDay": None},
        )
        result = defs.check_reports_update_status(nse)
        self.assertEqual(
            result,
            {
                "CM-UDIFF-BHAVCOPY-CSV": False,
                "CM-BHAVDATA-FULL": False,
                "INDEX-SNAPSHOT": False,
            },
        )

    def test_exits_when_market_closed(self):
        """If the reported date differs from today, function exits."""
        nse = self._nse_mock(
            {
                "CurrentDay": [{"fileKey": "CM-UDIFF-BHAVCOPY-CSV"}],
                "currentDate": "31-Dec-2023",
            },
            {"CurrentDay": []},
        )
        with self.assertRaises(SystemExit), self.assertLogs(logger, logging.WARNING):
            defs.check_reports_update_status(nse)

    def test_marks_reports_present(self):
        nse = self._nse_mock(
            {
                "CurrentDay": [
                    {"fileKey": "CM-UDIFF-BHAVCOPY-CSV"},
                    {"fileKey": "CM-BHAVDATA-FULL"},
                ],
                "currentDate": "01-Jan-2024",
            },
            {"CurrentDay": [{"fileKey": "INDEX-SNAPSHOT"}]},
        )
        result = defs.check_reports_update_status(nse)
        self.assertTrue(all(result.values()))

    def test_ignores_unknown_keys(self):
        nse = self._nse_mock(
            {
                "CurrentDay": [
                    {"fileKey": "SOME-OTHER-REPORT"},
                    {"fileKey": "CM-UDIFF-BHAVCOPY-CSV"},
                ],
                "currentDate": "01-Jan-2024",
            },
            {"CurrentDay": []},
        )
        result = defs.check_reports_update_status(nse)
        self.assertTrue(result["CM-UDIFF-BHAVCOPY-CSV"])
        self.assertFalse(result["CM-BHAVDATA-FULL"])
        self.assertFalse(result["INDEX-SNAPSHOT"])


# ---------------------------------------------------------------------------
# validate_nse_actions_file
# ---------------------------------------------------------------------------


class TestValidateNseActionsFile(unittest.TestCase):
    def setUp(self):
        _reset_globals()
        self.dates = make_dates("2024-01-10 00:00:00+05:30")
        defs.dates = self.dates

    def tearDown(self):
        _reset_globals()

    def test_downloads_when_not_present(self):
        nse = MagicMock()
        nse.actions.return_value = [{"symbol": "TCS"}]

        with self.assertLogs(logger, logging.WARNING):
            defs.validate_nse_actions_file(nse)

        self.assertIn("equityActions", defs.meta)
        self.assertIn("smeActions", defs.meta)
        self.assertIn("mfActions", defs.meta)
        self.assertEqual(nse.actions.call_count, 3)

    def test_skips_when_not_expired(self):
        nse = MagicMock()
        expiry = (self.dates.dt + timedelta(7)).isoformat()
        defs.meta = {
            "equityActions": [{"symbol": "TCS"}],
            "equityActionsExpiry": expiry,
            "smeActions": [{"symbol": "ABC"}],
            "smeActionsExpiry": expiry,
            "mfActions": [{"symbol": "XYZ"}],
            "mfActionsExpiry": expiry,
        }

        defs.validate_nse_actions_file(nse)
        nse.actions.assert_not_called()

    def test_updates_when_expired(self):
        nse = MagicMock()
        nse.actions.return_value = [{"symbol": "TCS"}]
        expired = (self.dates.dt - timedelta(1)).isoformat()
        defs.meta = {
            "equityActions": [{"symbol": "TCS"}],
            "equityActionsExpiry": expired,
            "smeActions": [{"symbol": "ABC"}],
            "smeActionsExpiry": expired,
            "mfActions": [{"symbol": "XYZ"}],
            "mfActionsExpiry": expired,
        }

        with self.assertLogs(logger, logging.WARNING):
            defs.validate_nse_actions_file(nse)

        self.assertEqual(nse.actions.call_count, 3)

    def test_segment_mapping(self):
        nse = MagicMock()
        nse.actions.return_value = []

        with self.assertLogs(logger, logging.WARNING):
            defs.validate_nse_actions_file(nse)

        called_segments = [c.kwargs.get("segment") for c in nse.actions.call_args_list]
        self.assertIn("equities", called_segments)
        self.assertIn("sme", called_segments)
        self.assertIn("mf", called_segments)


# ---------------------------------------------------------------------------
# update_pending_delivery_data
# ---------------------------------------------------------------------------


class TestUpdatePendingDeliveryData(unittest.TestCase):
    def setUp(self):
        _reset_globals()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.daily_folder = Path(self.tmp.name) / "daily"
        self.daily_folder.mkdir()
        defs.DAILY_FOLDER = self.daily_folder

        self.dates = make_dates("2024-01-10 00:00:00+05:30")
        defs.dates = self.dates
        defs.hook = None
        defs.meta = {"DLV_PENDING_DATES": ["2024-01-10T00:00:00+05:30"]}

    def tearDown(self):
        _reset_globals()
        defs.hook = None

    def _write_daily(self, symbol, dt, volume=1000):
        write_csv(
            symbol,
            self.daily_folder,
            [
                (
                    dt.strftime("%Y-%m-%d"),
                    100,
                    110,
                    95,
                    105,
                    volume,
                    "EQ",
                    "",
                    "",
                    "",
                ),
            ],
        )

    def _make_bhavcopy(self, rows):
        """Create a temp CSV mimicking an NSE delivery bhavcopy."""
        file = Path(self.tmp.name) / "delivery.csv"
        df = pd.DataFrame(
            rows,
            columns=pd.Index(
                [
                    "SYMBOL",
                    "SERIES",
                    "NO_OF_TRADES",
                    "DELIV_QTY",
                ]
            ),
        )
        df.to_csv(file, index=False)
        # Return a Path object whose .name matches
        return file

    def test_returns_false_when_file_unavailable(self):

        nse = MagicMock()
        nse.delivery_bhavcopy.side_effect = NSEFileUnavailableError("nope")

        with self.assertLogs(logger, logging.INFO):
            ok = defs.update_pending_delivery_data(nse, self.dates.dt.isoformat())

        self.assertFalse(ok)

    def test_returns_true_after_five_days_of_failure(self):

        nse = MagicMock()
        nse.delivery_bhavcopy.side_effect = NSEFileUnavailableError("nope")

        # Force the failure date 5 days in the past
        old_dt = datetime.now(defs.tz_IN) - timedelta(days=5)
        with self.assertLogs(logger, logging.WARNING):
            ok = defs.update_pending_delivery_data(nse, old_dt.isoformat())
        self.assertTrue(ok)

    def test_successful_update(self):
        dt = self.dates.dt
        self._write_daily("tcs", dt, volume=1000)

        bhav_file = self._make_bhavcopy([("TCS", "EQ", 10, " 500")])

        bhav_path = Path(self.tmp.name) / "delivery.csv"

        nse = MagicMock()
        nse.delivery_bhavcopy.return_value = bhav_path

        with self.assertLogs(logger, logging.INFO):
            ok = defs.update_pending_delivery_data(nse, dt.isoformat())

        self.assertTrue(ok)

        # Check the daily CSV was updated
        df = pd.read_csv(self.daily_folder / "tcs.csv", index_col="Date")
        self.assertEqual(int(df.iloc[0]["TOTAL_TRADES"]), 10)
        self.assertEqual(int(df.iloc[0]["DLV_QTY"]), 500)
        # Pending date removed
        self.assertNotIn(dt.isoformat(), defs.meta["DLV_PENDING_DATES"])

    def test_be_series_uses_volume_as_delivery(self):
        dt = self.dates.dt
        self._write_daily("abc", dt, volume=1234)

        bhav_path = Path(self.tmp.name) / "delivery.csv"
        pd.DataFrame(
            [("ABC", "BE", 5, "-")],
            columns=pd.Index(["SYMBOL", "SERIES", "NO_OF_TRADES", "DELIV_QTY"]),
        ).to_csv(bhav_path, index=False)

        nse = MagicMock()
        nse.delivery_bhavcopy.return_value = bhav_path

        with self.assertLogs(logger, logging.INFO):
            ok = defs.update_pending_delivery_data(nse, dt.isoformat())

        self.assertTrue(ok)

        df = pd.read_csv(self.daily_folder / "abc.csv", index_col="Date")
        self.assertEqual(int(df.iloc[0]["DLV_QTY"]), 1234)

    def test_missing_daily_file_is_skipped(self):
        dt = self.dates.dt
        # No daily file written for TCS

        bhav_path = Path(self.tmp.name) / "delivery.csv"
        pd.DataFrame(
            [("TCS", "EQ", 10, 500)],
            columns=pd.Index(["SYMBOL", "SERIES", "NO_OF_TRADES", "DELIV_QTY"]),
        ).to_csv(bhav_path, index=False)

        nse = MagicMock()
        nse.delivery_bhavcopy.return_value = bhav_path

        with self.assertLogs(logger, logging.INFO):
            ok = defs.update_pending_delivery_data(nse, dt.isoformat())
        self.assertTrue(ok)


# ---------------------------------------------------------------------------
# update_nse_symbol
# ---------------------------------------------------------------------------


class TestUpdateNseSymbol(unittest.TestCase):
    def setUp(self):
        _reset_globals()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.daily_folder = Path(self.tmp.name) / "daily"
        self.daily_folder.mkdir()
        defs.DAILY_FOLDER = self.daily_folder

        self.dates = make_dates("2024-01-10 00:00:00+05:30")
        defs.dates = self.dates
        defs.hook = None

    def tearDown(self):
        _reset_globals()
        defs.hook = None

    def test_creates_new_file_with_header(self):
        sym_file = self.daily_folder / "tcs.csv"
        defs.update_nse_symbol(sym_file, "EQ", 100, 110, 95, 105, 1000, 10, 500)
        content = sym_file.read_text()
        self.assertTrue(content.startswith("Date,Open,High,Low,Close"))
        self.assertIn("2024-01-10,100,110,95,105,1000,EQ,10,100.0,500", content)

    def test_appends_to_existing_file(self):
        sym_file = self.daily_folder / "tcs.csv"
        defs.update_nse_symbol(sym_file, "EQ", 100, 110, 95, 105, 1000, 10, 500)

        self.dates.dt = self.dates.dt + timedelta(1)
        self.dates.pandas_dt = self.dates.dt.strftime("%Y-%m-%d")

        defs.update_nse_symbol(sym_file, "EQ", 106, 115, 100, 112, 2000, 20, 800)

        lines = sym_file.read_text().splitlines()
        self.assertEqual(len(lines), 3)  # header + 2 data rows
        self.assertIn("2024-01-11,106,115,100,112,2000,EQ,20,100.0,800", lines[-1])

    def test_renames_sme_to_eq(self):
        sme_file = self.daily_folder / "abc_sme.csv"
        sme_file.write_text("Date,Open\n2024-01-01,1\n")

        sym_file = self.daily_folder / "abc.csv"

        with self.assertLogs(logger, logging.INFO):
            defs.update_nse_symbol(sym_file, "EQ", 100, 110, 95, 105, 1000, 10, 500)

        self.assertFalse(sme_file.exists())
        self.assertTrue(sym_file.exists())
        self.assertIn("2024-01-10", sym_file.read_text())


# ---------------------------------------------------------------------------
# update_index
# ---------------------------------------------------------------------------


class TestUpdateIndex(unittest.TestCase):
    def setUp(self):
        _reset_globals()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.daily_folder = Path(self.tmp.name) / "daily"
        self.daily_folder.mkdir()
        defs.DAILY_FOLDER = self.daily_folder

        self.dates = make_dates("2024-01-10 00:00:00+05:30")
        defs.dates = self.dates
        defs.hook = None

    def tearDown(self):
        _reset_globals()
        defs.hook = None

    def test_creates_new_index_file(self):
        defs.update_index("Nifty 50", 100, 110, 95, 105, 1000, 22.5)
        file = self.daily_folder / "nifty 50.csv"
        self.assertTrue(file.exists())
        content = file.read_text()
        self.assertTrue(content.startswith("Date,Open,High,Low,Close,Volume,P/E"))
        self.assertIn("2024-01-10,100,110,95,105,1000,22.5", content)

    def test_sanitizes_slashes_and_colons(self):
        defs.update_index("Nifty/500:Test", 100, 110, 95, 105, 1000, 22.5)
        expected = self.daily_folder / "nifty-500-test.csv"
        self.assertTrue(expected.exists())


# ---------------------------------------------------------------------------
# update_nse_eod
# ---------------------------------------------------------------------------


class TestUpdateNseEod(unittest.TestCase):
    def setUp(self):
        _reset_globals()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.root = Path(self.tmp.name)
        defs.DIR = self.root
        self.daily_folder = self.root / "daily"
        self.daily_folder.mkdir()
        defs.DAILY_FOLDER = self.daily_folder
        defs.AMIBROKER_FOLDER = self.root / "amibroker"
        defs.VALID_SERIES = ("EQ", "BE", "BZ", "SM", "ST")
        defs.AMIBROKER_COLUMNS = [
            "SYMBOL",
            "DATE",
            "OPEN",
            "HIGH",
            "LOW",
            "CLOSE",
            "VOLUME",
            "ISIN",
        ]

        self.dates = make_dates("2024-01-10 00:00:00+05:30")
        defs.dates = self.dates
        defs.hook = None
        defs.config = MagicMock()
        defs.config.AMIBROKER = False

    def tearDown(self):
        _reset_globals()
        defs.hook = None

    def _make_bhavcopy(self, rows):
        """Rows: list of tuples matching BhavCopyRow fields plus ISIN."""
        file = Path(self.tmp.name) / "bhav.csv"
        cols = [
            "ISIN",
            "TckrSymb",
            "SctySrs",
            "OpnPric",
            "HghPric",
            "LwPric",
            "ClsPric",
            "TtlTradgVol",
            "Index",
        ]
        df = pd.DataFrame(rows, columns=pd.Index(cols))
        df.to_csv(file, index=False)
        return file

    def _install_tracker(self):
        """Install a simple SymbolTracker-like mock on defs."""
        tracker = MagicMock()
        tracker.get_last_symbol.return_value = None
        tracker.update = MagicMock()
        defs.tracker = tracker
        return tracker

    def test_basic_update_creates_files(self):
        self._install_tracker()
        bhav = self._make_bhavcopy(
            [
                ("INE001A01036", "TCS", "EQ", 100, 110, 95, 105, 1000, "Nifty 50"),
            ]
        )

        with self.assertLogs(logger, logging.INFO):
            defs.update_nse_eod(bhav, None)

        self.assertTrue((self.daily_folder / "tcs.csv").exists())
        content = (self.daily_folder / "tcs.csv").read_text()
        self.assertIn("2024-01-10,100,110,95,105,1000,EQ", content)

    def test_skips_rights_issue(self):
        self._install_tracker()
        bhav = self._make_bhavcopy(
            [
                ("INE001A01036", "TCS-RE", "EQ", 100, 110, 95, 105, 1000, "Nifty 50"),
            ]
        )

        with self.assertLogs(logger, logging.INFO):
            defs.update_nse_eod(bhav, None)

        self.assertFalse((self.daily_folder / "tcs-re.csv").exists())

    def test_sme_suffix(self):
        self._install_tracker()
        bhav = self._make_bhavcopy(
            [
                ("INE001A01036", "ABC", "SM", 100, 110, 95, 105, 1000, "Nifty 50"),
            ]
        )

        with self.assertLogs(logger, logging.INFO):
            defs.update_nse_eod(bhav, None)

        self.assertTrue((self.daily_folder / "abc_sme.csv").exists())

    def test_missing_isin_raises(self):
        self._install_tracker()
        bhav = self._make_bhavcopy(
            [
                (None, "TCS", "EQ", 100, 110, 95, 105, 1000, "Nifty 50"),
            ]
        )
        with self.assertRaises(ValueError), self.assertLogs(logger, logging.INFO):
            defs.update_nse_eod(bhav, None)

    def test_symbol_rename(self):
        tracker = self._install_tracker()
        tracker.get_last_symbol.return_value = "OLDNAME"

        # Create the old file
        (self.daily_folder / "oldname.csv").write_text(
            "Date,Open,High,Low,Close,Volume,Series,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n"
        )

        bhav = self._make_bhavcopy(
            [
                ("INE001A01036", "NEWNAME", "EQ", 100, 110, 95, 105, 1000, "Nifty 50"),
            ]
        )

        with self.assertLogs(logger, logging.INFO):
            defs.update_nse_eod(bhav, None)

        self.assertFalse((self.daily_folder / "oldname.csv").exists())
        self.assertTrue((self.daily_folder / "newname.csv").exists())

    def test_with_delivery_file(self):
        self._install_tracker()
        bhav = self._make_bhavcopy(
            [
                ("INE001A01036", "TCS", "EQ", 100, 110, 95, 105, 1000, "Nifty 50"),
            ]
        )
        dlv = Path(self.tmp.name) / "delivery.csv"
        pd.DataFrame(
            [("TCS", "EQ", 10, 500)],
            columns=pd.Index(["SYMBOL", "SERIES", "NO_OF_TRADES", "DELIV_QTY"]),
        ).to_csv(dlv, index=False)

        with self.assertLogs(logger, logging.INFO):
            defs.update_nse_eod(bhav, dlv)

        content = (self.daily_folder / "tcs.csv").read_text()
        self.assertIn(",10,100.0,500", content)


# ---------------------------------------------------------------------------
# update_index_eod
# ---------------------------------------------------------------------------


class TestUpdateIndexEod(unittest.TestCase):
    def setUp(self):
        _reset_globals()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.root = Path(self.tmp.name)
        defs.DIR = self.root
        self.daily_folder = self.root / "daily"
        self.daily_folder.mkdir()
        defs.DAILY_FOLDER = self.daily_folder

        self.dates = make_dates("2024-01-10 00:00:00+05:30")
        defs.dates = self.dates
        defs.hook = None

    def tearDown(self):
        _reset_globals()
        defs.hook = None

    def _make_index_file(self, rows):
        file = Path(self.tmp.name) / "ind_close_all.csv"
        cols = [
            "Index Name",
            "Open Index Value",
            "High Index Value",
            "Low Index Value",
            "Closing Index Value",
            "Volume",
            "P/E",
        ]
        pd.DataFrame(rows, columns=pd.Index(cols)).to_csv(file, index=False)
        return file

    def test_updates_all_indices(self):
        file = self._make_index_file(
            [
                ("Nifty 50", 100, 110, 95, 105, 1000, 22.5),
                ("Nifty Bank", 200, 210, 195, 205, 2000, 18.0),
            ]
        )

        with self.assertLogs(logger, logging.INFO):
            defs.update_index_eod(file)

        self.assertTrue((self.daily_folder / "nifty 50.csv").exists())
        self.assertTrue((self.daily_folder / "nifty bank.csv").exists())

    def test_handles_dash_values(self):
        file = self._make_index_file(
            [
                ("Nifty 50", 100, 110, 95, 105, 1000, 22.5),
                ("Test Index", "-", "-", "-", "-", "-", "-"),
            ]
        )

        with self.assertLogs(logger, logging.INFO):
            defs.update_index_eod(file)

        self.assertTrue((self.daily_folder / "test index.csv").exists())

    def test_saves_raw_report(self):
        file = self._make_index_file(
            [
                ("Nifty 50", 100, 110, 95, 105, 1000, 22.5),
            ]
        )

        with self.assertLogs(logger, logging.INFO):
            defs.update_index_eod(file)

        folder = self.root / "nseIndices" / "2024"
        self.assertTrue((folder / file.name).exists())


# ---------------------------------------------------------------------------
# adjust_nse_stocks
# ---------------------------------------------------------------------------


class TestAdjustNseStocks(unittest.TestCase):
    def setUp(self):
        _reset_globals()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.daily_folder = Path(self.tmp.name) / "daily"
        self.daily_folder.mkdir()
        defs.DAILY_FOLDER = self.daily_folder

        self.dates = make_dates("2024-01-10 00:00:00+05:30")
        defs.dates = self.dates
        defs.hook = None
        defs.VALID_SERIES = ("EQ", "BE", "BZ", "SM", "ST")

    def tearDown(self):
        _reset_globals()
        defs.hook = None

    def _write_history(self, symbol, prices):
        """prices: list of (date_str, close)"""
        rows = [(d, 100.0, 110.0, 95.0, c, 1000, "EQ", "", "", "") for d, c in prices]
        write_csv(symbol, self.daily_folder, rows)

    def test_split_adjustment(self):
        self._write_history("tcs", [("2024-01-08", 100), ("2024-01-09", 200)])
        defs.meta = {
            "equityActions": [
                {
                    "symbol": "TCS",
                    "series": "EQ",
                    "exDate": "10-Jan-2024",
                    "subject": "Face Value Split From Rs 10 To Rs 5",
                }
            ],
            "smeActions": [],
            "mfActions": [],
        }

        with self.assertLogs(logger, logging.INFO):
            defs.adjust_nse_stocks()

        df = pd.read_csv(self.daily_folder / "tcs.csv", index_col="Date")
        # Adjustment factor = 10/5 = 2 → prices halved
        self.assertAlmostEqual(float(df.iloc[0]["Close"]), 50.0, places=2)
        self.assertAlmostEqual(float(df.iloc[1]["Close"]), 100.0, places=2)

    def test_bonus_adjustment(self):
        self._write_history("abc", [("2024-01-08", 150), ("2024-01-09", 300)])
        defs.meta = {
            "equityActions": [
                {
                    "symbol": "ABC",
                    "series": "EQ",
                    "exDate": "10-Jan-2024",
                    "subject": "Bonus 1:2",
                }
            ],
            "smeActions": [],
            "mfActions": [],
        }

        with self.assertLogs(logger, logging.INFO):
            defs.adjust_nse_stocks()

        df = pd.read_csv(self.daily_folder / "abc.csv", index_col="Date")
        # Bonus factor = 1 + 1/2 = 1.5
        self.assertAlmostEqual(float(df.iloc[0]["Close"]), 100.0, places=2)

    def test_non_ex_date_is_ignored(self):
        self._write_history("xyz", [("2024-01-08", 100)])
        defs.meta = {
            "equityActions": [
                {
                    "symbol": "XYZ",
                    "series": "EQ",
                    "exDate": "20-Jan-2024",
                    "subject": "Split From Rs 10 To Rs 5",
                }
            ],
            "smeActions": [],
            "mfActions": [],
        }

        with self.assertLogs(logger, logging.INFO):
            defs.adjust_nse_stocks()

        df = pd.read_csv(self.daily_folder / "xyz.csv", index_col="Date")
        self.assertAlmostEqual(float(df.iloc[0]["Close"]), 100.0, places=2)

    def test_invalid_series_ignored(self):
        self._write_history("pqr", [("2024-01-08", 100)])
        defs.meta = {
            "equityActions": [
                {
                    "symbol": "PQR",
                    "series": "XX",
                    "exDate": "10-Jan-2024",
                    "subject": "Split From Rs 10 To Rs 5",
                }
            ],
            "smeActions": [],
            "mfActions": [],
        }

        with self.assertLogs(logger, logging.INFO):
            defs.adjust_nse_stocks()

        df = pd.read_csv(self.daily_folder / "pqr.csv", index_col="Date")
        self.assertAlmostEqual(float(df.iloc[0]["Close"]), 100.0, places=2)

    def test_sme_suffix_used(self):
        self._write_history("abc_sme", [("2024-01-08", 100)])
        defs.meta = {
            "equityActions": [],
            "smeActions": [
                {
                    "symbol": "ABC",
                    "series": "SM",
                    "exDate": "10-Jan-2024",
                    "subject": "Bonus 1:1",
                }
            ],
            "mfActions": [],
        }

        with self.assertLogs(logger, logging.INFO):
            defs.adjust_nse_stocks()

        self.assertTrue((self.daily_folder / "abc_sme.csv").exists())


# ---------------------------------------------------------------------------
# clean_outdated
# ---------------------------------------------------------------------------


class TestCleanOutdated(unittest.TestCase):
    def setUp(self):
        _reset_globals()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.daily_folder = Path(self.tmp.name) / "daily"
        self.daily_folder.mkdir()
        defs.DAILY_FOLDER = self.daily_folder

        self.dates = make_dates("2024-01-10 00:00:00+05:30")
        defs.dates = self.dates
        defs.hook = None

    def tearDown(self):
        _reset_globals()
        defs.hook = None

    def _write_dated(self, symbol, date_str):
        file = self.daily_folder / f"{symbol}.csv"
        file.write_text(
            f"Date,Open,High,Low,Close,Volume,Series,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n"
            f"{date_str},1,2,0.5,1.5,100,EQ,,,\n"
        )

    def test_deletes_files_older_than_a_year(self):
        self._write_dated("old", "2020-01-01")
        self._write_dated("new", "2023-12-01")

        with self.assertLogs(logger, logging.INFO):
            defs.clean_outdated()

        self.assertFalse((self.daily_folder / "old.csv").exists())
        self.assertTrue((self.daily_folder / "new.csv").exists())


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------


class TestRollback(unittest.TestCase):
    def setUp(self):
        _reset_globals()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.folder = Path(self.tmp.name) / "daily"
        self.folder.mkdir()
        defs.DAILY_FOLDER = self.folder

        self.dates = make_dates("2024-01-10 00:00:00+05:30")
        defs.dates = self.dates
        defs.hook = None

    def tearDown(self):
        _reset_globals()
        defs.hook = None

    def test_removes_matching_last_line(self):
        file = self.folder / "tcs.csv"
        file.write_text(
            "Date,Open,High,Low,Close,Volume,Series,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n"
            "2024-01-09,1,2,0.5,1.5,100,EQ,,,\n"
            "2024-01-10,1,2,0.5,1.5,100,EQ,,,\n"
        )

        with self.assertLogs(logger, logging.INFO):
            defs.rollback(self.folder)

        content = file.read_text()
        self.assertNotIn("2024-01-10", content)
        self.assertIn("2024-01-09", content)

    def test_preserves_files_without_matching_date(self):
        file = self.folder / "abc.csv"
        file.write_text(
            "Date,Open,High,Low,Close,Volume,Series,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n"
            "2024-01-09,1,2,0.5,1.5,100,EQ,,,\n"
        )

        with self.assertLogs(logger, logging.INFO):
            defs.rollback(self.folder)

        self.assertIn("2024-01-09", file.read_text())


class TestIsVersionCompatible(unittest.TestCase):
    """Tests for defs.is_version_compatible."""

    def test_exact_match(self):
        self.assertTrue(defs.is_version_compatible("1.2.3", 1, 2, 3))

    def test_higher_patch(self):
        self.assertTrue(defs.is_version_compatible("1.2.4", 1, 2, 3))

    def test_higher_minor_same_patch(self):
        self.assertTrue(defs.is_version_compatible("1.3.3", 1, 2, 3))

    def test_higher_minor_lower_patch(self):
        self.assertTrue(defs.is_version_compatible("1.3.0", 1, 2, 3))

    def test_higher_minor_and_patch(self):
        self.assertTrue(defs.is_version_compatible("1.4.5", 1, 2, 3))

    def test_lower_minor(self):
        self.assertFalse(defs.is_version_compatible("1.1.9", 1, 2, 3))

    def test_lower_patch_same_minor(self):
        self.assertFalse(defs.is_version_compatible("1.2.2", 1, 2, 3))

    def test_lower_minor_and_patch(self):
        self.assertFalse(defs.is_version_compatible("1.1.1", 1, 2, 3))

    def test_different_major_higher(self):
        self.assertFalse(defs.is_version_compatible("2.2.3", 1, 2, 3))

    def test_different_major_lower(self):
        self.assertFalse(defs.is_version_compatible("0.2.3", 1, 2, 3))

    def test_prerelease_ignored_exact(self):
        self.assertTrue(defs.is_version_compatible("1.2.3-alpha", 1, 2, 3))

    def test_prerelease_ignored_higher(self):
        self.assertTrue(defs.is_version_compatible("1.2.4-beta.1", 1, 2, 3))

    def test_prerelease_ignored_incompatible(self):
        self.assertFalse(defs.is_version_compatible("1.2.2-rc.1", 1, 2, 3))

    def test_required_zero_minor_patch(self):
        self.assertTrue(defs.is_version_compatible("1.0.0", 1, 0, 0))

    def test_empty_string_raises(self):
        with self.assertRaises(ValueError):
            defs.is_version_compatible("", 1, 2, 3)

    def test_prerelease_with_dots(self):
        # Ensure split on "-" only once; metadata with dots is fine
        self.assertTrue(defs.is_version_compatible("1.2.3-beta.1.2", 1, 2, 3))


if __name__ == "__main__":
    unittest.main()
