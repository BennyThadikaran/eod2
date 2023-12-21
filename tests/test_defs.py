import unittest
from unittest.mock import Mock, patch
from context import defs
from datetime import datetime


class TestGetMuhuratHolidayInfo(unittest.TestCase):

    def test_matching_description(self):
        holidays = {
            '2022-11-01': [{
                'description': 'Diwali'
            }, {
                'description': 'Laxmi Pujan'
            }],
            '2022-12-25': [{
                'description': 'Christmas'
            }],
            '2023-01-01': [{
                'description': 'New Year'
            }, {
                'description': 'Laxmi Pujan Celebration'
            }],
        }

        result = defs.getMuhuratHolidayInfo(holidays)

        expected = {'description': 'Laxmi Pujan'}
        self.assertEqual(result, expected)

    def test_no_matching_description(self):
        holidays = {
            '2022-11-01': [{
                'description': 'Diwali'
            }],
            '2022-12-25': [{
                'description': 'Christmas'
            }],
            '2023-01-01': [{
                'description': 'New Year'
            }],
        }

        result = defs.getMuhuratHolidayInfo(holidays)

        expected = {}
        self.assertEqual(result, expected)


class TestGetHolidayList(unittest.TestCase):

    def test_sucessful_request(self):
        mock_nse = Mock()
        mock_nse.holidays.return_value = {
            'CM': [{
                'tradingDate': '2023-11-12',
                'description': 'Diwali Laxmi Pujan'
            }]
        }

        result = defs.getHolidayList(mock_nse)

        expected = {'2023-11-12': 'Diwali Laxmi Pujan'}

        self.assertEqual(result, expected)

    def test_failed_request(self):
        mock_nse = Mock()
        exc = Exception('Download failed.')
        mock_nse.holidays.side_effect = exc

        with self.assertRaises(SystemExit) as exit_exception:
            defs.getHolidayList(mock_nse)

        self.assertEqual(exit_exception.exception.code,
                         f"{exc!r}\nFailed to download holidays")


class TestCheckForHolidays(unittest.TestCase):

    @patch.object(defs, 'getHolidayList')
    @patch.object(defs, 'hasLatestHolidays', False)
    def test_not_holiday(self, mock_get_holiday_list):
        '''Current date is not a holiday'''

        # Mock NSE class
        mock_nse = Mock()

        # Set up mock for getHolidayList
        mock_get_holiday_list.return_value = {}

        # Call the function
        with patch.object(defs, 'meta', {}):
            result = defs.checkForHolidays(mock_nse)

        # Assertions
        self.assertFalse(result)
        mock_get_holiday_list.assert_called_once_with(mock_nse)
        mock_nse.holidays.assert_not_called()

    @patch.object(defs, 'dates')
    @patch.object(defs, 'getHolidayList')
    @patch.object(defs, 'hasLatestHolidays', False)
    def test_holiday_not_today(self, mock_get_holiday_list, _):
        '''Today's date and current date are different. Current date is a holiday.'''

        defs.dates.dt = datetime(2023, 1, 1)
        defs.dates.today = datetime(2023, 1, 2)

        # Mock NSE class
        mock_nse = Mock()

        holiday_obj = {'01-Jan-2023': 'New Year'}
        meta_obj = {'holidays': holiday_obj, 'year': 2023}

        # Set up mock for getHolidayList
        mock_get_holiday_list.return_value = holiday_obj

        with patch.object(defs, 'meta', meta_obj):
            result = defs.checkForHolidays(mock_nse)

        self.assertTrue(result)
        mock_get_holiday_list.assert_called_once()

    @patch.object(defs, 'dates')
    @patch.object(defs, 'getHolidayList')
    @patch.object(defs, 'hasLatestHolidays', False)
    def test_holiday_today(self, mock_get_holiday_list, _):
        '''Today's date and current date are same. Today is a holiday.'''

        defs.dates.dt = defs.dates.today = datetime(2023, 1, 2)

        # Mock NSE class
        mock_nse = Mock()

        holiday_obj = {'02-Jan-2023': 'New Year'}
        meta_obj = {'holidays': holiday_obj, 'year': 2023}

        # Set up mock for getHolidayList
        mock_get_holiday_list.return_value = holiday_obj

        with patch.object(defs, 'meta', meta_obj):
            with self.assertRaises(SystemExit):
                defs.checkForHolidays(mock_nse)

        mock_get_holiday_list.assert_called_once()


class TestValidateNseActionsFile(unittest.TestCase):

    @patch.object(defs, 'meta', {})
    @patch.object(defs, 'dates')
    def test_missing_actions_successful_request(self, *_):
        '''Missing `equityActions` or `smeActions` key on `meta` object.
        Request for NSE actions successful
        '''

        dt = datetime(2023, 1, 1)
        expiry = datetime(2023, 1, 8).isoformat()
        defs.dates.dt = defs.dates.today = dt

        # Mock NSE class
        mock_nse = Mock()

        mock_nse.actions.return_value = None

        defs.validateNseActionsFile(mock_nse)

        expect = {
            'equityActions': None,
            'equityActionsExpiry': expiry,
            'smeActions': None,
            'smeActionsExpiry': expiry
        }

        self.assertEqual(mock_nse.actions.call_count, 2)
        self.assertEqual(defs.meta, expect)

    @patch.object(defs, 'meta', {})
    def test_missing_actions_failed_request(self, *_):
        '''Missing `equityActions` or `smeActions` key on `meta` object.
        Request for NSE actions fails.'''

        # Mock NSE class
        mock_nse = Mock()

        exc = Exception("Download Failed")
        mock_nse.actions.side_effect = exc

        with self.assertRaises(SystemExit) as exit_exception:
            defs.validateNseActionsFile(mock_nse)

        expected_exc = f'{exc!r}\nFailed to download equity actions'

        mock_nse.actions.assert_called_once()
        self.assertEqual(exit_exception.exception.code, expected_exc)

    @patch.object(defs, 'meta', {})
    @patch.object(defs, 'dates')
    def test_expired_successful_request(self, _):
        '''Actions data expired. Request for NSE actions successful'''

        dt = datetime(2023, 1, 1)
        expiry = datetime(2023, 1, 1).isoformat()
        newExpiry = datetime(2023, 1, 8).isoformat()

        defs.dates.dt = defs.dates.today = dt
        defs.meta = {
            'equityActions': None,
            'smeActions': None,
            'equityActionsExpiry': expiry,
            'smeActionsExpiry': expiry
        }

        # Mock NSE class
        mock_nse = Mock()

        mock_nse.actions.return_value = None

        defs.validateNseActionsFile(mock_nse)

        self.assertEqual(mock_nse.actions.call_count, 2)
        self.assertEqual(defs.meta['equityActionsExpiry'], newExpiry)
        self.assertEqual(defs.meta['smeActionsExpiry'], newExpiry)

    @patch.object(defs, 'meta', {})
    @patch.object(defs, 'dates')
    def test_expired_failed_request(self, _):
        '''Actions data expired. Request for NSE actions fails'''

        dt = datetime(2023, 1, 1)
        expiry = datetime(2023, 1, 1).isoformat()

        defs.dates.dt = defs.dates.today = dt
        defs.meta = {
            'equityActions': None,
            'smeActions': None,
            'equityActionsExpiry': expiry,
            'smeActionsExpiry': expiry
        }

        # Mock NSE class
        mock_nse = Mock()

        exc = Exception("Download Failed")
        mock_nse.actions.side_effect = exc

        with self.assertRaises(SystemExit) as exit_exception:
            defs.validateNseActionsFile(mock_nse)

        expected_exc = f'{exc!r}\nFailed to update equity actions'

        mock_nse.actions.assert_called_once()
        self.assertEqual(exit_exception.exception.code, expected_exc)

    @patch.object(defs, 'meta', {})
    @patch.object(defs, 'dates')
    def test_not_expired(self, _):
        '''NSE actions data is fresh. No need to update'''

        dt = datetime(2023, 1, 1)
        expiry = datetime(2023, 1, 3).isoformat()

        defs.dates.dt = defs.dates.today = dt
        meta_obj = {
            'equityActions': None,
            'smeActions': None,
            'equityActionsExpiry': expiry,
            'smeActionsExpiry': expiry
        }
        defs.meta = meta_obj

        # Mock NSE class
        mock_nse = Mock()
        mock_nse.actions.return_value = None

        defs.validateNseActionsFile(mock_nse)

        mock_nse.actions.assert_not_called()
        self.assertEqual(defs.meta, meta_obj)


if __name__ == '__main__':
    unittest.main()
