"""Unit tests for the defs.Dates class."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo

from context import defs

TZ_IN = ZoneInfo("Asia/Kolkata")


def _make_dates(last_update: str) -> defs.Dates:
    """Construct a real Dates instance with a patched 'now'."""
    return defs.Dates(last_update)


class TestDatesInit(unittest.TestCase):
    """Tests for Dates.__init__."""

    @patch("defs.dates.datetime")
    def test_init_parses_last_update(self, mock_datetime):
        """The instance should expose the parsed last_update datetime."""
        fixed_now = datetime(2024, 1, 15, 10, 0, tzinfo=TZ_IN)
        mock_datetime.now.return_value = fixed_now
        mock_datetime.combine = datetime.combine
        mock_datetime.min = datetime.min
        mock_datetime.fromisoformat = datetime.fromisoformat

        d = defs.Dates(last_update="2024-01-12T00:00:00+05:30")

        self.assertEqual(d.lastUpdate.year, 2024)
        self.assertEqual(d.lastUpdate.month, 1)
        self.assertEqual(d.lastUpdate.day, 12)

    @patch("defs.dates.datetime")
    def test_pandas_dt_format(self, mock_datetime):
        """pandas_dt should be a YYYY-MM-DD string."""
        fixed_now = datetime(2024, 1, 15, 10, 0, tzinfo=TZ_IN)
        mock_datetime.now.return_value = fixed_now
        mock_datetime.combine = datetime.combine
        mock_datetime.min = datetime.min
        mock_datetime.fromisoformat = datetime.fromisoformat

        d = defs.Dates("2024-01-12T00:00:00+05:30")
        self.assertEqual(d.pandas_dt, "2024-01-12")

    @patch("defs.dates.datetime")
    def test_today_is_midnight(self, mock_datetime):
        """Today should be the current date with time stripped."""
        fixed_now = datetime(2024, 1, 15, 14, 30, tzinfo=TZ_IN)
        mock_datetime.now.return_value = fixed_now
        mock_datetime.combine = datetime.combine
        mock_datetime.min = datetime.min
        mock_datetime.fromisoformat = datetime.fromisoformat

        d = defs.Dates("2024-01-12T00:00:00+05:30")
        self.assertEqual(d.today.hour, 0)
        self.assertEqual(d.today.minute, 0)
        self.assertEqual(d.today.second, 0)


class TestDatesNextDate(unittest.TestCase):
    """Tests for Dates.nextDate."""

    def _build(self, last_update: str, now: datetime) -> defs.Dates:
        with patch("defs.dates.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min
            mock_datetime.fromisoformat = datetime.fromisoformat
            return defs.Dates(last_update)

    @patch("defs.dates.logger")
    def test_returns_false_when_all_up_to_date(self, mock_logger):
        """If next date is in the future, return False."""
        now = datetime(2024, 1, 15, 10, 0, tzinfo=TZ_IN)
        d = self._build("2024-01-14T00:00:00+05:30", now)

        with patch("defs.dates.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            result = d.nextDate()

        self.assertFalse(result)
        mock_logger.info.assert_called()

    @patch("defs.dates.logger")
    def test_advances_to_next_day(self, mock_logger):
        """On a normal day, nextDate should advance the internal dt."""
        now = datetime(2024, 1, 15, 20, 0, tzinfo=TZ_IN)
        d = self._build("2024-01-13T00:00:00+05:30", now)
        previous = d.dt

        with patch("defs.dates.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            result = d.nextDate()

        self.assertTrue(result)
        self.assertEqual(d.dt, previous + timedelta(1))
        self.assertEqual(d.pandas_dt, (previous + timedelta(1)).strftime("%Y-%m-%d"))

    @patch("defs.dates.logger")
    def test_same_day_before_4pm_returns_false(self, mock_logger):
        """If today is the target date and it's before 4pm, return False."""
        now = datetime(2024, 1, 15, 10, 0, tzinfo=TZ_IN)
        d = self._build("2024-01-14T00:00:00+05:30", now)

        with patch("defs.dates.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            result = d.nextDate()

        self.assertFalse(result)
        # Check that "Check again after" message was logged
        args, _ = mock_logger.info.call_args
        self.assertIn("Check again after", args[0])

    @patch("defs.dates.logger")
    def test_same_day_after_4pm_returns_true(self, mock_logger):
        """If today is the target date and it's after 4pm, proceed."""
        now = datetime(2024, 1, 15, 20, 0, tzinfo=TZ_IN)
        d = self._build("2024-01-14T00:00:00+05:30", now)

        with patch("defs.dates.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            result = d.nextDate()

        self.assertTrue(result)

    @patch("defs.dates.logger")
    def test_consecutive_calls_advance_by_one_day(self, mock_logger):
        """Each call should advance the internal date by exactly one day."""
        now = datetime(2024, 1, 20, 20, 0, tzinfo=TZ_IN)
        d = self._build("2024-01-14T00:00:00+05:30", now)

        with patch("defs.dates.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            d.nextDate()
            first = d.dt

            d.nextDate()
            second = d.dt

        self.assertEqual(second - first, timedelta(1))


class TestDatesTimezoneHandling(unittest.TestCase):
    """Tests that Dates normalises timezones to Asia/Kolkata."""

    @patch("defs.dates.datetime")
    def test_utc_last_update_converted(self, mock_datetime):
        """A UTC last_update should be converted to IST."""
        fixed_now = datetime(2024, 1, 15, 10, 0, tzinfo=TZ_IN)
        mock_datetime.now.return_value = fixed_now
        mock_datetime.combine = datetime.combine
        mock_datetime.min = datetime.min
        mock_datetime.fromisoformat = datetime.fromisoformat

        # 2024-01-12 18:30 UTC == 2024-01-13 00:00 IST
        d = defs.Dates("2024-01-12T18:30:00+00:00")

        self.assertEqual(d.lastUpdate.tzinfo, TZ_IN)
        self.assertEqual(d.lastUpdate.day, 13)
        self.assertEqual(d.pandas_dt, "2024-01-13")


if __name__ == "__main__":
    unittest.main()
