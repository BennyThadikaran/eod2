# EOD2

An automated python script to download and update NSE stocks, indices, and delivery data.

Stock Data is stored as CSV files and adjusted for splits and bonus. Ideal for use in backtesting.

## Installation, Usage and other Details - [See Wiki](https://github.com/BennyThadikaran/eod2/wiki)

## Updates
- 10th Jul 2023: Added an optional feature to format bhavcopy in Amibroker format.
   - To enable this feature, edit `Config.py` and set `AMIBROKER = True`.
   - On first run, the `eod2_data/amibroker` folder will be created and 365 days of bhavcopy data is downloaded and formatted.
   - Executing `py defs.py` will now print the script version and configuration info.
- 23rd May 2023: Major rework on the code and new added features
  - **New Rollback feature**: Any errors during the data sync process can result in partially updated files and can be mess to resolve. With the updated code, any changes to the files can be rolled back to the last updated date without any manual intervention. See [Installation for details](#installation)
  - All the data files are now placed in a submodule, separated from the actual code. ([see eod2_data](https://github.com/BennyThadikaran/eod2_data)). Commit logs will now be much cleaner.
  - File downloads are much faster.
- 13th Jan 2022: EOD2 now uses pathlib module for handling file paths. This resolves file path errors on Windows platform.

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
