# 🎇 EOD2

An automated Python script to download and update NSE stocks, indices, and delivery data.

Stock Data is stored as CSV files and adjusted for splits and bonuses. Ideal for use in backtesting.

If you :heart: my work so far, please :star2: this repo.

## Notes

- `src/eod2_data/daily` contain OHLC and delivery data for individual stocks.
- A list of available indices can be found in `src/eod2_data/sector_watchlist.csv`.
- Supports **Python version >= 3.8**

## 👽 Installation, Usage, and Other Details - [See Wiki](https://github.com/BennyThadikaran/eod2/wiki)

## 💪 EOD2 Discussions

I just opened [GitHub discussions](https://github.com/BennyThadikaran/eod2/discussions). Connect with other members and share your thoughts, views, and questions about EOD2.

## 🔥 Features

- Daily EOD data for over 2000 NSE stocks since 1995.
- Stores OHLCV and delivery data of individual stocks and indices in csv files.
- Automatically syncs data up to the current date while keeping track of NSE holidays.
- Makes historical adjustments for splits and bonuses.
- Keeps track of stock ISIN for changes in company/symbol code and applies changes.
- Prints colored alerts when [NIFTY PE](https://www.samco.in/knowledge-center/articles/nifty-50-pe-ratio/) is below 20 and above 25.
- Works cross platform (Linux, Windows, Mac).
- Robust error handling mechanisms to protect data.

### Plot beautiful charts with plot.py

- Add volume, sma, ema and stock Relative strength analysis.
- Perform analysis on weekly or daily charts.
- Detects support and resistance levels and plots them on the chart.

![plot.py screenshot](https://res.cloudinary.com/doyu4uovr/image/upload/s--3hTZGzOB--/c_scale,f_auto,w_800/v1692987992/EOD2/tcs-weekly-stan_unvmgu.png)

### Draw Trend and Trading lines - Mouse and Keyboard Interaction

![Natcopharm with trend and trading lines](https://res.cloudinary.com/doyu4uovr/image/upload/s--mIk8G6sO--/c_scale,f_auto,w_800/v1694162379/EOD2/natcopharm_d_lines_fnys25.png)

### Visualise NSE delivery data

![Plot.py delivery mode](https://res.cloudinary.com/doyu4uovr/image/upload/s--x7W48Hdi--/c_scale,f_auto,w_800/v1692988193/EOD2/glenmark-delivery-mode_kebcb7.png)

### Analyse the delivery data with dget.py

![dget.py screenshot](https://res.cloudinary.com/doyu4uovr/image/upload/s--dJi3GbMN--/f_auto/v1692426345/EOD2/dget-basic_cy2bsp.png)

### Other projects utilizing EOD2 Data

[BennyThadikaran/RRG-Lite](https://github.com/BennyThadikaran/RRG-Lite) - RRG-Lite is a Python CLI tool for displaying Relative Rotational graph (RRG) charts.

[BennyThadikaran/stock-pattern](https://github.com/BennyThadikaran/stock-pattern) - A python scanner to detect and plot stock chart patterns 
