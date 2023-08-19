# EOD2

An automated python script to download and update NSE stocks, indices, and delivery data.

Stock Data is stored as CSV files and adjusted for splits and bonus. Ideal for use in backtesting.

### Notes

- 'Daily' and 'Delivery' folders contain OHLC and delivery data for individual stocks.
- All available indices are listed in 'sector_watchlist.csv'. Additional indices can be added by editing this file.
- **Stock data before 2005 may not be fully adjusted** as NSE does not provide adjustment data before this year.

If you :heart: my work so far, please :star2: this repo.

## Installation, Usage and other Details - [See Wiki](https://github.com/BennyThadikaran/eod2/wiki)

_**Existing users of EOD2:** Make sure to update `mplfinance` to latest version to ensure `plot.py` runs without errors._

## Updates

- 19th Aug 2023: _**Major update to `plot.py` and `dget.py`, minor changes in init.py**_
  - `plot.py` has been rewritten providing improved chart features, indicators and multiple options and is fully configurable.
  - A new delivery mode is available in plot.py to visualize the delivery data.
  - `dget.py` and `lookup.py` has been merged into a single script with some updated options.
  - `mplfinance` dependency has been updated to the latest version providing support for labels.
  - Wiki is being updated with the latest documentation and will be completed in a day or 2.
- Other recent updates see [Wiki](https://github.com/BennyThadikaran/eod2/wiki)

## Features

- Daily EOD data for over 2000 NSE stocks since 1995.
- Stores OHLCV and delivery data of individual stocks and indices in csv files.
- Automatically syncs data up to the current date while keeping track of NSE holidays.
- Makes historical adjustments for splits and bonuses.
- Keeps track of stock ISIN for changes in company/symbol code and applies changes.
- Prints colored alerts when [NIFTY PE](https://www.samco.in/knowledge-center/articles/nifty-50-pe-ratio/) is below 20 and above 25.
- Works in both Linux and Windows.
- Robust and stable error handling mechanisms to protect data.

### Plot beautiful charts with plot.py

- Add volume, sma, ema, stock Relative strength analysis.
- Perform analysis on weekly or daily charts.
- Lots of configuration options

![plot.py screenshot](https://res.cloudinary.com/doyu4uovr/image/upload/s--8i_eMc1u--/c_scale,f_auto,w_800/v1692094407/EOD2/tcs-weekly-stan_pxs8bv.png)

### Run Weekly sector analysis

![plot.py nifty IT weekly chart](https://res.cloudinary.com/doyu4uovr/image/upload/s--UnD2PZWk--/c_scale,f_auto,w_800/v1692455651/EOD2/plot-nifty-it-weekly_xttawt.png)

### Visualise NSE delivery data

![Plot.py delivery mode](https://res.cloudinary.com/doyu4uovr/image/upload/s--knbRWhva--/c_scale,f_auto,w_800/v1692361362/EOD2/glenmark-delivery-mode_n2zd3o.png)

### Analyse the delivery data with dget.py

![dget.py screenshot](https://res.cloudinary.com/doyu4uovr/image/upload/s--dJi3GbMN--/f_auto/v1692426345/EOD2/dget-basic_cy2bsp.png)
