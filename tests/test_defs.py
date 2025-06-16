import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pandas as pd

from context import defs

DIR = Path(__file__).parent / "test_data"
tz_IN = ZoneInfo("Asia/Kolkata")

defs.logging.disable(defs.logging.CRITICAL)


class TestGetMuhuratHolidayInfo(unittest.TestCase):
    def test_matching_description(self):
        holidays = {
            "2022-11-01": [
                {"description": "Diwali"},
                {"description": "Laxmi Pujan"},
            ],
            "2022-12-25": [{"description": "Christmas"}],
            "2023-01-01": [
                {"description": "New Year"},
                {"description": "Laxmi Pujan Celebration"},
            ],
        }

        result = defs.getMuhuratHolidayInfo(holidays)

        expected = {"description": "Laxmi Pujan"}
        self.assertEqual(result, expected)

    def test_no_matching_description(self):
        holidays = {
            "2022-11-01": [{"description": "Diwali"}],
            "2022-12-25": [{"description": "Christmas"}],
            "2023-01-01": [{"description": "New Year"}],
        }

        result = defs.getMuhuratHolidayInfo(holidays)

        expected = {}
        self.assertEqual(result, expected)


class TestGetHolidayList(unittest.TestCase):
    def test_sucessful_request(self):
        mock_nse = Mock()
        mock_nse.holidays.return_value = {
            "CM": [
                {
                    "tradingDate": "2023-11-12",
                    "description": "Diwali Laxmi Pujan",
                }
            ]
        }

        result = defs.getHolidayList(mock_nse)

        expected = {"2023-11-12": "Diwali Laxmi Pujan"}

        self.assertEqual(result, expected)

    def test_failed_request(self):
        mock_nse = Mock()
        exc = Exception("Download failed.")
        mock_nse.holidays.side_effect = exc

        with self.assertRaises(SystemExit):
            defs.getHolidayList(mock_nse)


class TestCheckForHolidays(unittest.TestCase):
    @patch.object(defs, "dates")
    @patch.object(defs, "getHolidayList")
    @patch.object(defs, "hasLatestHolidays", True)
    def test_is_muhurat(self, mock_get_holiday_list, _):
        defs.dates.dt = defs.dates.today = datetime(2023, 11, 12)

        meta_obj = {"holidays": {"12-Nov-2023": "Laxmi Pujan"}, "year": 2023}

        # Mock NSE class
        mock_nse = Mock()

        # Call the function
        with patch.object(defs, "meta", meta_obj):
            result = defs.checkForHolidays(mock_nse)

        self.assertFalse(result)
        mock_get_holiday_list.assert_not_called()

    @patch.object(defs, "dates")
    @patch.object(defs, "getHolidayList")
    def test_is_weekend(self, mock_get_holiday_list, _):
        defs.dates.dt = defs.dates.today = datetime(2023, 1, 1)

        # Mock NSE class
        mock_nse = Mock()

        # Call the function
        with patch.object(defs, "meta", {"holidays": {}, "year": 2023}):
            result = defs.checkForHolidays(mock_nse)

        self.assertTrue(result)
        mock_get_holiday_list.assert_not_called()

    @patch.object(defs, "getHolidayList")
    @patch.object(defs, "hasLatestHolidays", False)
    def test_not_holiday(self, mock_get_holiday_list):
        """Current date is not a holiday"""

        # Mock NSE class
        mock_nse = Mock()

        # Set up mock for getHolidayList
        mock_get_holiday_list.return_value = {}

        # Call the function
        with patch.object(defs, "meta", {}):
            result = defs.checkForHolidays(mock_nse)

        # Assertions
        self.assertFalse(result)
        mock_get_holiday_list.assert_called_once_with(mock_nse)
        mock_nse.holidays.assert_not_called()

    @patch.object(defs, "dates")
    @patch.object(defs, "getHolidayList")
    @patch.object(defs, "hasLatestHolidays", False)
    def test_holiday_not_today(self, mock_get_holiday_list, _):
        """Today's date and current date are different. Current date is a holiday."""

        defs.dates.dt = datetime(2023, 1, 1)
        defs.dates.today = datetime(2023, 1, 2)

        # Mock NSE class
        mock_nse = Mock()

        holiday_obj = {"01-Jan-2023": "New Year"}
        meta_obj = {"holidays": holiday_obj, "year": 2023}

        # Set up mock for getHolidayList
        mock_get_holiday_list.return_value = holiday_obj

        with patch.object(defs, "meta", meta_obj):
            result = defs.checkForHolidays(mock_nse)

        self.assertTrue(result)
        mock_get_holiday_list.assert_called_once()

    @patch.object(defs, "dates")
    def test_is_special_session(self, _):
        dt = datetime(2024, 3, 16)
        defs.dates.dt = defs.dates.today = dt

        # Mock NSE class
        mock_nse = Mock()

        with patch.object(defs, "meta", {"special_sessions": [dt.isoformat()]}):
            result = defs.checkForHolidays(mock_nse)

        self.assertFalse(result)


class TestValidateNseActionsFile(unittest.TestCase):
    @patch.object(defs, "meta", {})
    @patch.object(defs, "dates")
    def test_missing_actions_successful_request(self, *_):
        """Missing `equityActions` or `smeActions` key on `meta` object.
        Request for NSE actions successful
        """

        dt = datetime(2023, 1, 1)
        expiry = datetime(2023, 1, 8).isoformat()
        defs.dates.dt = defs.dates.today = dt

        # Mock NSE class
        mock_nse = Mock()

        mock_nse.actions.return_value = None

        defs.validateNseActionsFile(mock_nse)

        expect = {
            "equityActions": None,
            "equityActionsExpiry": expiry,
            "smeActions": None,
            "smeActionsExpiry": expiry,
            "mfActions": None,
            "mfActionsExpiry": expiry,
        }

        self.assertEqual(mock_nse.actions.call_count, 3)
        self.assertEqual(defs.meta, expect)

    @patch.object(defs, "meta", {})
    def test_missing_actions_failed_request(self, *_):
        """Missing `equityActions` or `smeActions` key on `meta` object.
        Request for NSE actions fails."""

        # Mock NSE class
        mock_nse = Mock()

        exc = Exception("Download Failed")
        mock_nse.actions.side_effect = exc

        with self.assertRaises(SystemExit):
            defs.validateNseActionsFile(mock_nse)

        mock_nse.actions.assert_called_once()

    @patch.object(defs, "meta", {})
    @patch.object(defs, "dates")
    def test_expired_successful_request(self, _):
        """Actions data expired. Request for NSE actions successful"""

        dt = datetime(2023, 1, 1).astimezone(tz_IN)
        expiry = datetime(2023, 1, 1).astimezone(tz_IN).isoformat()
        newExpiry = datetime(2023, 1, 8).astimezone(tz_IN).isoformat()

        defs.dates.dt = defs.dates.today = dt
        defs.meta = {
            "equityActions": None,
            "smeActions": None,
            "equityActionsExpiry": expiry,
            "smeActionsExpiry": expiry,
            "mfActions": None,
            "mfActionsExpiry": expiry,
        }

        # Mock NSE class
        mock_nse = Mock()

        mock_nse.actions.return_value = None

        defs.validateNseActionsFile(mock_nse)

        self.assertEqual(mock_nse.actions.call_count, 3)
        self.assertEqual(defs.meta["equityActionsExpiry"], newExpiry)
        self.assertEqual(defs.meta["smeActionsExpiry"], newExpiry)
        self.assertEqual(defs.meta["mfActionsExpiry"], newExpiry)

    @patch.object(defs, "meta", {})
    @patch.object(defs, "dates")
    def test_expired_failed_request(self, _):
        """Actions data expired. Request for NSE actions fails"""

        dt = datetime(2023, 1, 1).astimezone(tz_IN)
        expiry = datetime(2023, 1, 1).astimezone(tz_IN).isoformat()

        defs.dates.dt = defs.dates.today = dt
        defs.meta = {
            "equityActions": None,
            "smeActions": None,
            "equityActionsExpiry": expiry,
            "smeActionsExpiry": expiry,
        }

        # Mock NSE class
        mock_nse = Mock()

        exc = Exception("Download Failed")
        mock_nse.actions.side_effect = exc

        with self.assertRaises(SystemExit):
            defs.validateNseActionsFile(mock_nse)

        mock_nse.actions.assert_called_once()


@patch.object(defs, "meta", {})
@patch.object(defs, "dates")
def test_not_expired(self, _):
    """NSE actions data is fresh. No need to update"""

    dt = datetime(2023, 1, 1).astimezone(tz_IN)
    expiry = datetime(2023, 1, 3).astimezone(tz_IN).isoformat()

    defs.dates.dt = defs.dates.today = dt
    meta_obj = {
        "equityActions": None,
        "smeActions": None,
        "mfActions": None,
        "equityActionsExpiry": expiry,
        "smeActionsExpiry": expiry,
        "mfActionsExpiry": expiry,
    }
    defs.meta = meta_obj

    # Mock NSE class
    mock_nse = Mock()
    mock_nse.actions.return_value = None

    defs.validateNseActionsFile(mock_nse)

    mock_nse.actions.assert_not_called()
    self.assertEqual(defs.meta, meta_obj)


class TestUpdateNseEOD(unittest.TestCase):
    def setUp(self):
        year = f"{datetime.now():%Y}"
        # Create temporary folders and files for testing
        self.bhav_file_path = DIR / "bhav_copy.csv"
        self.delivery_file_path = DIR / "delivery_data.csv"
        self.bhav_folder = DIR / f"nseBhav/{year}"
        self.dlv_folder = DIR / f"nseDelivery/{year}"

    def tearDown(self) -> None:
        bhav_file = self.bhav_folder / "bhav_copy.csv"
        dlv_file = self.dlv_folder / "delivery_data.csv"

        bhav_file.unlink()
        dlv_file.unlink()

        bhav_file.parents[0].rmdir()
        bhav_file.parents[1].rmdir()

        dlv_file.parents[0].rmdir()
        dlv_file.parents[1].rmdir()

    @patch.multiple(
        defs,
        DIR=DIR,
        isin=pd.read_csv(DIR / "isin.csv", index_col="ISIN"),
        ISIN_FILE=DIR / "isin.csv",
        DAILY_FOLDER=DIR,
    )
    @patch.object(defs, "config")
    @patch.object(defs, "updateNseSymbol")
    def test_updateNseEOD_with_delivery_file(self, mock_update_nse_symbol, mock_config):
        mock_update_nse_symbol.return_value = None

        mock_config.AMIBROKER = False

        # Call the function
        defs.updateNseEOD(self.bhav_file_path, self.delivery_file_path)

        symbols = ("bob", "jam", "jax", "fax_sme", "kax_sme")

        # Make assertions
        # Only EQ, BE, BZ, SM and ST series are allowed
        self.assertEqual(mock_update_nse_symbol.call_count, 5)

        for i, call in enumerate(mock_update_nse_symbol.call_args_list):
            args = call.args

            expected_filename = f"{symbols[i]}.csv"

            # first argument must be pathlib.Path
            self.assertTrue(
                isinstance(args[0], Path) and args[0].name == expected_filename
            )

            i = i + 1  # zero indexed

            # check if args are passed correctly
            # OHLC data starts at 100 and increments by 100 for each symbol
            # remaining data starts at 1000 and increments by 1000 for each symbols
            # (100, 100, 100, 100, 1000, 1000, 1000)
            # (200, 200, 200, 200, 2000, 2000, 2000)
            expected_args = (i * 100,) * 4 + (i * 1000,) * 3
            self.assertEqual(args[1:], expected_args)


if __name__ == "__main__":
    unittest.main()
