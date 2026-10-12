import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from context import utils


class TestGetDataFrame(unittest.TestCase):
    """Test suite for utils.get_dataframe function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_fpath = Path("/tmp/test_data.csv")
        self.period = 10

        # Create sample OHLC data for testing
        dates = pd.date_range(start="2024-01-01", periods=50, freq="D")
        self.sample_df = pd.DataFrame(
            {
                "Open": range(100, 150),
                "High": range(105, 155),
                "Low": range(95, 145),
                "Close": range(102, 152),
                "Volume": range(1000, 1050),
            },
            index=dates,
        )

        # Sample weekly data
        weekly_dates = pd.date_range(start="2024-01-01", periods=10, freq="W")
        self.weekly_df = pd.DataFrame(
            {
                "Open": range(100, 110),
                "High": range(105, 115),
                "Low": range(95, 105),
                "Close": range(102, 112),
                "Volume": range(1000, 1010),
            },
            index=weekly_dates,
        )

    @patch("context.utils.csv_loader")
    def test_daily_dataframe_default_parameters(self, mock_csv_loader):
        """Test daily timeframe with default parameters."""
        mock_csv_loader.return_value = self.sample_df

        result = utils.get_dataframe(self.test_fpath, self.period)

        # Verify csv_loader was called correctly
        mock_csv_loader.assert_called_once_with(
            self.test_fpath, self.period, end_date=None, use_columns=None
        )

        # Verify result
        self.assertEqual(len(result), self.period)
        pd.testing.assert_frame_equal(result, self.sample_df[-self.period :])

    @patch("context.utils.csv_loader")
    def test_daily_dataframe_with_columns(self, mock_csv_loader):
        """Test daily timeframe with specific columns."""
        columns = ["Open", "Close"]
        filtered_df = self.sample_df[columns]
        mock_csv_loader.return_value = filtered_df

        result = utils.get_dataframe(
            self.test_fpath, self.period, tf="daily", columns=columns
        )

        mock_csv_loader.assert_called_once_with(
            self.test_fpath, self.period, end_date=None, use_columns=columns
        )

        self.assertEqual(len(result), self.period)
        self.assertListEqual(list(result.columns), columns)

    @patch("context.utils.csv_loader")
    def test_daily_dataframe_with_toDate(self, mock_csv_loader):
        """Test daily timeframe with toDate parameter."""
        to_date = datetime(2024, 2, 1)
        mock_csv_loader.return_value = self.sample_df

        result = utils.get_dataframe(
            self.test_fpath, self.period, tf="daily", toDate=to_date
        )

        mock_csv_loader.assert_called_once_with(
            self.test_fpath, self.period, end_date=to_date, use_columns=None
        )

        self.assertEqual(len(result), self.period)

    @patch("context.utils.csv_loader")
    def test_weekly_dataframe_calculation(self, mock_csv_loader):
        """Test that weekly timeframe correctly calculates candle count."""
        mock_csv_loader.return_value = self.sample_df

        result = utils.get_dataframe(self.test_fpath, self.period, tf="weekly")

        # For weekly, candle_count should be period * 5
        expected_candle_count = self.period * 5
        mock_csv_loader.assert_called_once_with(
            self.test_fpath, expected_candle_count, end_date=None, use_columns=None
        )

    @patch("context.utils.csv_loader")
    def test_weekly_dataframe_resampling(self, mock_csv_loader):
        """Test weekly resampling functionality."""
        mock_csv_loader.return_value = self.sample_df

        result = utils.get_dataframe(self.test_fpath, self.period, tf="weekly")

        # Verify result is resampled to weekly
        self.assertIsInstance(result, pd.DataFrame)
        # Weekly data should have fewer rows than daily
        self.assertLessEqual(len(result), len(self.sample_df))

    @patch("context.utils.csv_loader")
    def test_weekly_dataframe_with_columns(self, mock_csv_loader):
        """Test weekly timeframe with specific columns."""
        columns = ["Open", "Close"]
        mock_csv_loader.return_value = self.sample_df

        result = utils.get_dataframe(
            self.test_fpath, self.period, tf="weekly", columns=columns
        )

        # Should only include specified columns
        self.assertTrue(all(col in result.columns for col in columns))
        self.assertFalse(any(col not in columns for col in result.columns))

    @patch("context.utils.csv_loader")
    def test_weekly_dataframe_invalid_columns(self, mock_csv_loader):
        """Test weekly timeframe with invalid column names."""
        columns = ["Open", "invalid_column", "Close"]
        mock_csv_loader.return_value = self.sample_df

        result = utils.get_dataframe(
            self.test_fpath, self.period, tf="weekly", columns=columns
        )

        # Invalid columns should be filtered out
        self.assertNotIn("invalid_column", result.columns)
        self.assertIn("Open", result.columns)
        self.assertIn("Close", result.columns)

    @patch("context.utils.csv_loader")
    def test_empty_dataframe(self, mock_csv_loader):
        """Test behavior with empty dataframe."""
        empty_df = pd.DataFrame()
        mock_csv_loader.return_value = empty_df

        result = utils.get_dataframe(self.test_fpath, self.period)

        self.assertTrue(result.empty)

    @patch("context.utils.csv_loader")
    def test_insufficient_data(self, mock_csv_loader):
        """Test behavior when dataframe has fewer rows than period."""
        short_df = self.sample_df[:5]  # Only 5 rows
        mock_csv_loader.return_value = short_df

        result = utils.get_dataframe(self.test_fpath, self.period)

        # Should return all available data
        self.assertEqual(len(result), 5)

    @patch("context.utils.csv_loader")
    def test_csv_loader_exception(self, mock_csv_loader):
        """Test exception handling from csv_loader."""
        mock_csv_loader.side_effect = FileNotFoundError("File not found")

        with self.assertRaises(FileNotFoundError):
            utils.get_dataframe(self.test_fpath, self.period)

    @patch("context.utils.csv_loader")
    def test_weekly_with_toDate(self, mock_csv_loader):
        """Test weekly timeframe with toDate parameter."""
        to_date = datetime(2024, 2, 1)
        mock_csv_loader.return_value = self.sample_df

        result = utils.get_dataframe(
            self.test_fpath, self.period, tf="weekly", toDate=to_date
        )

        expected_candle_count = self.period * 5
        mock_csv_loader.assert_called_once_with(
            self.test_fpath, expected_candle_count, end_date=to_date, use_columns=None
        )

    @patch("context.utils.csv_loader")
    def test_period_boundary_conditions(self, mock_csv_loader):
        """Test boundary conditions for period parameter."""
        mock_csv_loader.return_value = self.sample_df

        # Test with period = 1
        result = utils.get_dataframe(self.test_fpath, 1)
        self.assertEqual(len(result), 1)

        # Test with period larger than available data
        result = utils.get_dataframe(self.test_fpath, 1000)
        self.assertEqual(len(result), len(self.sample_df))


class TestJsonFunctions(unittest.TestCase):
    def test_date_encoder(self):
        date_encoder = utils.DateEncoder()
        test_datetime = datetime(2023, 1, 1, 12, 0, 0)

        result = date_encoder.default(test_datetime)
        self.assertEqual(result, "2023-01-01T12:00:00")

    def test_write_json(self):
        # temp file
        filepath = Path("test.json")

        data = {"key": "value", "date": datetime(2023, 1, 1, 12)}

        utils.write_json(filepath, data)

        file_content = filepath.read_text()

        expected_json_string = json.dumps(data, indent=2, cls=utils.DateEncoder)

        self.assertEqual(file_content, expected_json_string)

        # Clean up: Remove the temp file
        filepath.unlink()


if __name__ == "__main__":
    unittest.main()
