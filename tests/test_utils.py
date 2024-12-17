import json
import unittest
from datetime import datetime
from pathlib import Path

import pandas as pd
from context import utils


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

        utils.writeJson(filepath, data)

        file_content = filepath.read_text()

        expected_json_string = json.dumps(data, indent=3, cls=utils.DateEncoder)

        self.assertEqual(file_content, expected_json_string)

        # Clean up: Remove the temp file
        filepath.unlink()


class TestArgParseDict(unittest.TestCase):
    def test_different_values(self):
        args = utils.arg_parse_dict(
            {"sym": "tcs", "sma": [20, 50, 200], "volume": True}
        )

        expected = ["--sym", "tcs", "--sma", "20", "50", "200", "--volume"]

        self.assertEqual(args, expected)

    def test_boolean_false(self):
        args = utils.arg_parse_dict({"sym": "tcs", "volume": False})

        # volume argument not included
        expected = ["--sym", "tcs"]

        self.assertEqual(args, expected)

    def test_none(self):
        args = utils.arg_parse_dict({"sym": "tcs", "watch": None})

        # watch argument not included
        expected = ["--sym", "tcs"]

        self.assertEqual(args, expected)


class TestGetDataFrameFunction(unittest.TestCase):
    def setUp(self):
        # Create a temporary CSV file with sample data for testing
        self.csv_path = Path("test_data.csv")

        data = {
            "Date": pd.date_range(start="2022-01-01", periods=10),
            "Open": [100, 105, 110, 95, 102, 108, 115, 98, 105, 112],
            "High": [105, 112, 115, 100, 110, 118, 120, 104, 110, 118],
            "Low": [98, 100, 105, 92, 96, 104, 110, 94, 98, 105],
            "Close": [102, 110, 112, 98, 105, 112, 118, 100, 105, 114],
            "Volume": [
                100000,
                120000,
                95000,
                110000,
                105000,
                98000,
                115000,
                102000,
                108000,
                112000,
            ],
        }

        pd.DataFrame(data).to_csv(self.csv_path, index=False)

    def tearDown(self):
        # Remove the temporary CSV file after the test
        self.csv_path.unlink()

    def test_default(self):
        result = utils.getDataFrame(self.csv_path, tf="daily", period=2)

        expected = pd.read_csv(
            self.csv_path, parse_dates=True, index_col="Date"
        )[-2:]

        pd.testing.assert_frame_equal(result, expected)

    def test_weekly(self):
        result = utils.getDataFrame(Path(self.csv_path), tf="weekly", period=2)

        dct = {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }

        expected = (
            pd.read_csv(self.csv_path, parse_dates=True, index_col="Date")
            .resample("W", label="left")
            .apply(dct)[-2:]
        )

        pd.testing.assert_frame_equal(result, expected)

    def test_weekly_close_column(self):
        result = utils.getDataFrame(
            Path(self.csv_path), tf="weekly", period=2, column="Close"
        )

        expected = (
            pd.read_csv(self.csv_path, parse_dates=True, index_col="Date")[
                "Close"
            ]
            .resample("W", label="left")
            .apply("last")[-2:]
        )

        pd.testing.assert_series_equal(result, expected)

    def test_toDate(self):
        result = utils.getDataFrame(
            Path(self.csv_path),
            tf="daily",
            period=2,
            toDate=datetime(2022, 1, 5),
        )

        expected = pd.read_csv(
            self.csv_path, parse_dates=True, index_col="Date"
        )[:"2022-01-05"][-2:]

        pd.testing.assert_frame_equal(result, expected)


class TestGetLevels(unittest.TestCase):
    def setUp(self):
        # Price level 60 as resistance and 30 as support
        data = {
            "High": (50.0, 55.0, 60.0, 55.0, 50.0, 45.0, 40.0, 45.0, 50.0),
            "Low": (40.0, 45.0, 50.0, 45.0, 40.0, 35.0, 30.0, 35.0, 40.0),
        }

        index = tuple(datetime(2023, 1, i) for i in range(1, 10))

        self.df = pd.DataFrame(data, index=pd.DatetimeIndex(index))

    def test_data_types(self):
        mean_candle_size = 2.0

        # List[ Tuple[ Tuple[date, price], Tuple[date, price] ] ]
        result = utils.getLevels(self.df, mean_candle_size)

        self.assertIsInstance(result, list)

        # Tuple[ Tuple[date, price], Tuple[date, price] ]
        for level in result:
            # each level is tuple
            self.assertIsInstance(level, tuple)
            # level has two tuples within
            self.assertIsInstance(level[0], tuple)
            self.assertIsInstance(level[1], tuple)

            # each tuple contains datetime and float values
            self.assertIsInstance(level[0][0], pd.Timestamp)
            self.assertIsInstance(level[1][0], pd.Timestamp)
            self.assertIsInstance(level[0][1], float)
            self.assertIsInstance(level[1][1], float)

        # First resistance line is at 60
        self.assertEqual(result[0][0][1], 60)

        # second support line is at 30
        self.assertEqual(result[1][0][1], 30)


class TestIsFarFromLevel(unittest.TestCase):
    level = 50.0
    mean_size = 5.0

    def test_far_from_all_levels(self):
        levels = [(1, 45.0), (2, 55.0), (3, 60.0)]

        result = utils.isFarFromLevel(self.level, levels, self.mean_size)

        self.assertTrue(result)

    def test_close_to_one(self):
        levels = [(1, 45.0), (2, 49.0), (3, 60.0)]

        result = utils.isFarFromLevel(self.level, levels, self.mean_size)

        self.assertFalse(result)

    def test_no_levels(self):
        levels = []

        result = utils.isFarFromLevel(self.level, levels, self.mean_size)

        self.assertTrue(result)


class TestRelativeStrength(unittest.TestCase):
    def test_relative_strength(self):
        # Test data
        stock_close_prices = pd.Series((50, 55, 52, 48, 53))
        index_close_prices = pd.Series((1000, 1010, 1005, 990, 995))

        # Expected result based on manual calculation
        expected = pd.Series((5.0, 5.45, 5.17, 4.85, 5.33))

        # Calculate relative strength
        result = utils.relativeStrength(stock_close_prices, index_close_prices)

        # Perform the assertion
        pd.testing.assert_series_equal(result, expected)


class TestManfieldRelativeStrength(unittest.TestCase):
    def test_manfield_relative_strength(self):
        stock_close_prices = pd.Series((50, 55, 52, 48, 53))
        index_close_prices = pd.Series((1000, 1010, 1005, 990, 995))

        # Expected result based on manual calculation
        expected = pd.Series((None, None, -0.7, -5.95, 4.17))

        # Calculate Mansfield Relative Strength
        result = utils.manfieldRelativeStrength(
            stock_close_prices, index_close_prices, 3
        )

        # Perform the assertion
        pd.testing.assert_series_equal(result, expected)


class TestRandomChar(unittest.TestCase):
    def test_random_char(self):
        for length in (5, 10, 15):
            result = utils.randomChar(length)

            self.assertEqual(len(result), length)


if __name__ == "__main__":
    unittest.main()
