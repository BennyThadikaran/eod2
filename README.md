# EOD2

An automated python script to download and update NSE stocks, indices, and delivery data.

Stock Data is stored as CSV files and adjusted for splits and bonus. Ideal for use in backtesting.

## Installation, Usage and other Details - [See Wiki](https://github.com/BennyThadikaran/eod2/wiki)

## Updates

- 22nd Jul 2023: Major changes to folder structure, centralized configuration, code improvements.
  - All EOD2 python code is now moved into `src` folder providing separation of core python code from other files. Also useful for those using python venv within the project root.
  - All EOD2 configuration is now centralized into `defs/Config.py`. To override the config, create a `user.json` in defs folder. See [wiki on configuration](https://github.com/BennyThadikaran/eod2/wiki/Usage#configuration)
- Other recent updates see [Wiki](https://github.com/BennyThadikaran/eod2/wiki)

## Features

- Daily EOD data for over 2000 NSE stocks since 1995.
- Stores OHLCV and delivery data of individual stocks and indices in csv files.
- Automatically syncs data up to the current date while keeping track of NSE holidays.
- Makes historical adjustments for splits and bonuses.
- Keeps track of stock ISIN for changes in company/symbol code and applies changes.
- Prints colored alerts when [NIFTY PE](https://www.samco.in/knowledge-center/articles/nifty-50-pe-ratio/) is below 20 and above 25.
- Plot OHLC data with marked support and resistance levels and colored bars for high delivery days.
- Works in both Linux and Windows.

### Plot with plot.py

![plot screenshot](https://res.cloudinary.com/doyu4uovr/image/upload/e_improve,f_auto/v1689126755/EOD2/plot_tb7oq2.png)

### Delivery analysis with dget.py

![screenshot](https://res.cloudinary.com/doyu4uovr/image/upload/f_auto/v1689126755/EOD2/dget-args_xy0suw.png)

### Notes

- 'Daily' and 'Delivery' folders contain OHLC and delivery data for individual stocks.
- All available indices are listed in 'sector_watchlist.csv'. Additional indices can be added by editing this file.
- **Stock data before 2005 may not be fully adjusted** as NSE does not provide adjustment data before this year.
