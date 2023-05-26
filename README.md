# EOD2

An automated python script to download and update NSE stocks, indices, and delivery data.

**Update**

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

## Installation

To clone the repo and the `eod2_data` submodule

```
git clone --recurse-submodules https://github.com/BennyThadikaran

pip install requests pandas mplfinance
```

Mplfinance is optional. Only required for plotting data using plot.py

`eod2_data` folder contains all the csv data files.

Run `$ py init.py` to get the latest data.

**For Non Git Users**

Download the zip file for this repository and extract the contents.

Install the dependencies.
`$ pip install requests pandas mplfinance`

Run `$ py setup.py` from the project directory to download and extract the eod2_data.

Run `$ py init.py` to get the latest data.

Ideally run `init.py` daily or atleast weekly after 7pm India Time to keep your data in sync.

## Usage

`$ py init.py`

Output

```
Updating NSE actions file
Downloading Files
Starting Data Sync
EOD sync complete
Index sync complete.
Makings adjustments for splits and bonus
PDSL: face value split (sub-division) - from rs 10/- per share to rs 2/- per share
Cleaning up files
0 files deleted
26 Aug 2022: Done
```

For Linux users: **[Automate eod2](/automate.md)**

For Windows users: **[Automating Python Scripts Using Windows Task Scheduler ](https://www.shortautomaton.com/automating-python-scripts-using-windows-task-scheduler/)**

### Plotting candlesticks, delivery, and support & Resistance

`py plot.py tcs`
![plot screenshot](/images/plot.png)

Dark Blue bars represent above-average delivery and traded volume.
[See Analysing Delivery data](delivery-analysis.md).

Horizontal lines mark support and resistance.

By default:

- plot.py uses 60 days average to compare delivery and traded volume.
- 180 trading days are plotted.

To change this, plot.py takes additional integer arguments:

> plot.py \<symbolcode\> \<Average Days\> \<plot period\>

`py plot.py tcs 30 60`

### Delivery analysis

See [Analysing delivery data](delivery-analysis.md) for explanation.

> dget.py [\<symbol1\> \<symbol2\> ...]

`py dget.py hdfcbank marksans idfcfirstb`

![screenshot](/images/dget-args.png)

`py dget.py`

![screenshot](/images/dget.png)

If no symbols are specified, a default list of symbols are displayed.
To edit this list, open dget.py in a text editor and edit the symbols in the watch variable.

```
if len(argv) == 1:
    #### EDIT YOUR WATCHLIST HERE ####
    watch = ["AMARAJABAT", "APLLTD", "AUROPHARMA", "DIXON", "GODREJCP", "GODREJIND", "HCLTECH", "INFY", "LATENTVIEW", "M&M", "MARKSANS", "MOL", "TATAPOWER", "TCS"]
    # DO NOT EDIT BELOW THIS LINE
else:
    watch = argv[1:]
```

## Notes

- 'Daily' and 'Delivery' folders contain OHLC and delivery data for individual stocks.
- All available indices are listed in 'sector_watchlist.csv'. Additional indices can be added by editing this file.
- **Stock data before 2005 may not be fully adjusted** as NSE does not provide adjustment data before this year.
