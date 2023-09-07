from pathlib import Path
from datetime import datetime, timedelta
from json import loads, dumps
from os.path import getmtime, getsize
from defs.NSE import NSE
from defs.Dates import Dates
from zipfile import ZipFile
from pandas import read_csv, concat
from sys import platform
from os import system, SEEK_END, SEEK_CUR
from re import compile
from defs.Config import Config
from time import sleep
from typing import Literal

if 'win' in platform:
    # enable color support in Windows
    system('color')


DIR = Path(__file__).parent.parent
daily_folder = DIR / 'eod2_data' / 'daily'
delivery_folder = DIR / 'eod2_data' / 'delivery'
equityActionsFile = DIR / 'eod2_data' / 'nse_actions.json'
smeActionsFile = DIR / 'eod2_data' / 'sme_actions.json'
isin_file = DIR / 'eod2_data' / 'isin.csv'
amibroker_folder = DIR / 'eod2_data' / 'amibroker'

config = Config()

if config.AMIBROKER and not amibroker_folder.exists():
    amibroker_folder.mkdir()

isin = read_csv(isin_file, index_col='ISIN')
etfs = (DIR / 'eod2_data' / 'etf.csv').read_text().strip().split('\n')

header_text = 'Date,TTL_TRD_QNTY,NO_OF_TRADES,QTY_PER_TRADE,DELIV_QTY,DELIV_PER\n'

split_regex = compile(r'(\d+\.?\d*)[\/\- a-z\.]+(\d+\.?\d*)')

bonus_regex = compile(r'(\d+) ?: ?(\d+)')

# initiate the dates class from utils.py
dates = Dates()

has_latest_holidays = False


def getHolidayList(nse: NSE, file: Path):
    """Makes a request for NSE holiday list for the year.
    Saves and returns the holiday Object"""

    global has_latest_holidays

    url = 'https://www.nseindia.com/api/holiday-master'

    params = {'type': 'trading'}

    data = nse.makeRequest(url, params)

    # CM pertains to capital market or equity holdays
    data = {k['tradingDate']: k['description'] for k in data['CM']}

    file.write_text(dumps(data, indent=3))

    print('NSE Holiday list updated')

    has_latest_holidays = True
    return data


def isHolidaysFileUpdated(file: Path):
    """Returns True if the holiday.json files exists and
    year of download matches the current year"""

    return file.is_file() and datetime.fromtimestamp(getmtime(file)).year == dates.dt.year


def checkForHolidays(nse: NSE):
    """Returns True if current date is a holiday.
    Exits the script if today is a holiday"""

    file = DIR / 'eod2_data' / 'holiday.json'

    if isHolidaysFileUpdated(file):
        # holidays are updated for current year
        holidays = loads(file.read_bytes())
    else:
        # new year get new holiday list
        holidays = getHolidayList(nse, file)

    # the current date for which data is being synced
    curDt = dates.dt.strftime('%d-%b-%Y')
    isToday = curDt == dates.today.strftime('%d-%b-%Y')

    if curDt in holidays:
        if not has_latest_holidays:
            holidays = getHolidayList(nse, file)

        if not isToday:
            print(f'{curDt} Market Holiday: {holidays[curDt]}')
            return True

        exit(f'Market Holiday: {holidays[curDt]}')

    return False


def validateNseActionsFile(nse: NSE):
    """Check if the NSE Corporate actions() file exists.
    If exists, check if the file is older than 7 days.
    Else request actions for the next 8 days from current date.
    The actionsFile pertains to Bonus, Splits, dividends etc.
    """

    for file in (equityActionsFile, smeActionsFile):
        index = 'sme' if 'sme' in file.name else 'equities'

        if not file.is_file():
            getActions(file, nse, dates.dt, dates.dt + timedelta(8), index)
        else:
            lastModifiedTS = getmtime(file)

            # Update every 7 days from last download
            if dates.dt.timestamp() - lastModifiedTS > 7 * 24 * 60 * 60:
                frm_dt = datetime.fromtimestamp(lastModifiedTS) + timedelta(7)
                getActions(file, nse, frm_dt, dates.dt + timedelta(8), index)


def getActions(file: Path,
               nse: NSE,
               from_dt: datetime,
               to_dt: datetime,
               index: Literal['equities', 'sme'] = 'equities'):
    """Make a request for corporate actions specifing the date range."""

    print('Updating NSE corporate actions file')
    fmt = '%d-%m-%Y'

    params = {
        'index': index,
        'from_date': from_dt.strftime(fmt),
        'to_date': to_dt.strftime(fmt),
    }

    data = nse.makeRequest(
        'https://www.nseindia.com/api/corporates-corporateActions', params=params)

    file.write_text(dumps(data, indent=3))


def isAmiBrokerFolderUpdated():
    'Returns true if the folder has files'

    return any(amibroker_folder.iterdir())


def updateAmiBrokerRecords(nse):
    '''Downloads and updates the amibroker files upto the number of days
    set in Config.AMI_UPDATE_DAYS'''

    today = dates.dt
    dates.dt -= timedelta(config.AMI_UPDATE_DAYS)
    total_days = config.AMI_UPDATE_DAYS

    print(f'Fetching bhavcopy for last {total_days} days',
          'and converting to AmiBroker format.\n'
          'This is a one time process. It will take a few minutes.')

    while dates.dt <= today:
        # A small pause to not overload requests on NSE server.
        sleep(0.5)

        if dates.dt.weekday() == 5:
            dates.dt += timedelta(2)

        try:
            bhavFile = downloadNseBhav(nse, exitOnError=False)
        except FileNotFoundError:
            dates.dt += timedelta(1)
            continue

        with ZipFile(bhavFile) as zip:
            csvFile = zip.namelist()[0]

            # get first item in namelist. fixes errors due to folders in zipfile
            with zip.open(csvFile) as f:
                toAmiBrokerFormat(f, csvFile)

        bhavFile.unlink()

        days_complete = total_days - (today - dates.dt).days
        pct_complete = int(days_complete / total_days * 100)
        print(f'{pct_complete} %', end="\r" * 5, flush=True)
        dates.dt += timedelta(1)

    print("\nDone")


def downloadNseDelivery(nse: NSE):
    """Download the daily report for Equity delivery data
    and return the saved file path. Exit if the download fails"""

    url = f'https://archives.nseindia.com/products/content/sec_bhavdata_full_{dates.dt:%d%m%Y}.csv'

    delivery_file = nse.download(url)

    if not delivery_file.is_file() or getsize(delivery_file) < 50000:
        exit('Download Failed: ' + delivery_file.name)

    return delivery_file


def downloadNseBhav(nse: NSE, exitOnError=True):
    """Download the daily report for Equity bhav copy and
    return the saved file path. Exit if the download fails"""

    dt_str = dates.dt.strftime('%d%b%Y').upper()
    month = dt_str[2:5].upper()

    url = f'https://archives.nseindia.com/content/historical/EQUITIES/{dates.dt.year}/{month}/cm{dt_str}bhav.csv.zip'

    bhavFile = nse.download(url)

    if not bhavFile.is_file() or getsize(bhavFile) < 5000:
        bhavFile.unlink()
        if exitOnError:
            exit('Download Failed: ' + bhavFile.name)
        else:
            raise FileNotFoundError()

    return bhavFile


def downloadIndexFile(nse: NSE):
    """Download the daily report for Equity Index and
    return the saved file path. Exit if the download fails"""

    base_url = 'https://archives.nseindia.com/content'
    url = f'{base_url}/indices/ind_close_all_{dates.dt:%d%m%Y}.csv'

    index_file = nse.download(url)

    if not index_file.is_file() or getsize(index_file) < 5000:
        exit('Download Failed: ' + index_file.name)

    return index_file


def updateNseEOD(bhavFile: Path):
    """Update all stocks with latest price data from bhav copy"""

    isin_updated = False

    # cm01FEB2023bhav.csv.zip
    with ZipFile(bhavFile) as zip:
        csvFile = zip.namelist()[0]

        with zip.open(csvFile) as f:
            df = read_csv(f, index_col='ISIN')

            if config.AMIBROKER:
                print("Converting to AmiBroker format")
                f.seek(0)
                toAmiBrokerFormat(f, csvFile)

    # save the csv file to the below folder.
    folder = DIR / 'nseBhav' / str(dates.dt.year)

    # Create it if not exists
    if not folder.is_dir():
        folder.mkdir(parents=True)

    df.to_csv(folder / csvFile)

    # filter the dataframe for stocks series EQ, BE and BZ
    # https://www.nseindia.com/market-data/legend-of-series
    df = df[(df['SERIES'] == 'EQ') |
            (df['SERIES'] == 'BE') |
            (df['SERIES'] == 'BZ') |
            (df['SERIES'] == 'SM') |
            (df['SERIES'] == 'ST')]

    # iterate over each row as a tuple
    for t in df.itertuples(name=None):
        idx, sym, series, O, H, L, C, _, _, V, *_ = t

        # ignore rights issue and etfs
        if '-RE' in sym or sym in etfs:
            continue

        prefix = '_sme' if series in ('SM', 'ST') else ''
        sym_file = daily_folder / f'{sym.lower()}{prefix}.csv'

        # ISIN is a unique identifier for each stock symbol.
        # When a symbol name changes its ISIN remains the same
        # This allows for tracking changes in symbol names and
        # updating file names accordingly
        if not idx in isin.index:
            isin_updated = True
            isin.at[idx, 'SYMBOL'] = sym

        # if symbol name does not match the symbol name under its ISIN
        # we rename the files in daily and delivery folder
        if sym != isin.at[idx, 'SYMBOL']:
            isin_updated = True
            old = isin.at[idx, 'SYMBOL'].lower()

            new = sym.lower()

            isin.at[idx, 'SYMBOL'] = sym

            sym_file = daily_folder / f'{new}.csv'
            old_file = daily_folder / f'{old}.csv'
            old_delivery_file = delivery_folder / f'{old}.csv'

            try:
                old_file.rename(sym_file)
            except FileNotFoundError:
                print(
                    f'WARN: Renaming daily/{old}.csv to {new}.csv. No such file.')

            try:
                old_delivery_file.rename(delivery_folder / f'{new}.csv')
            except FileNotFoundError:
                print(
                    f'WARN: Renaming delivery/{old}.csv to {new}.csv. No such file.')

            print(f'Name Changed: {old} to {new}')

        updateNseSymbol(sym_file, O, H, L, C, V)

    if isin_updated:
        isin.to_csv(isin_file)


def toAmiBrokerFormat(bhav_file_handle, fileName: str):
    'Converts and saves bhavcopy into amibroker format'

    cols = ['SYMBOL', 'TIMESTAMP', 'OPEN', 'HIGH',
            'LOW', 'CLOSE', 'TOTTRDVAL', 'ISIN']

    rcols = list(cols)
    rcols[1] = 'DATE'
    rcols[-2] = 'VOLUME'

    df = read_csv(bhav_file_handle, parse_dates=['TIMESTAMP'])

    df = df[(df['SERIES'] == 'EQ') | (
        df['SERIES'] == 'BE') | (df['SERIES'] == 'BZ')]

    df = df[cols]
    df.columns = rcols
    df['DATE'] = df['DATE'].dt.strftime("%Y%m%d")
    df.to_csv(amibroker_folder / fileName, index=False)


def updateDelivery(file: Path):
    """Update all stocks with latest delivery data"""

    df = read_csv(file, index_col='SYMBOL')

    # save the csv file to the below folder.
    folder = DIR / 'nseDelivery' / str(dates.dt.year)

    # Create it if not exists
    if not folder.is_dir():
        folder.mkdir(parents=True)

    df.to_csv(folder / file.name)

    # filter the dataframe for stocks series EQ, BE and BZ
    # https://www.nseindia.com/market-data/legend-of-series
    df = df[(df[' SERIES'] == ' EQ') | (
        df[' SERIES'] == ' BE') | (df[' SERIES'] == ' BZ')]

    # iterate over each row as a tuple
    for t in df.itertuples(name=None):
        sym, series, *_, v, _, trd_count, dq, _ = t

        # ignore rights issue and etfs
        if '-RE' in sym or sym in etfs:
            continue

        updateDeliveryData(sym, series, v, int(trd_count), dq)

    print('Delivery Data updated')


def updateNseSymbol(sym_file: Path, o, h, l, c, v):
    'Appends EOD stock data to end of file'

    text = ''

    if not sym_file.is_file():
        text += 'Date,Open,High,Low,Close,Volume\n'

    text += f'{dates.pandas_dt},{o},{h},{l},{c},{v}\n'

    with sym_file.open('a') as f:
        f.write(text)


def updateDeliveryData(sym: str, series: str, v: int, trd_count: int, dq: int):
    """Update the delivery data for each file"""

    file = delivery_folder / f'{sym.lower()}.csv'
    text = ''

    if not file.is_file():
        text += header_text

    # BE and BZ series stocks are all delivery trades, so we use the volume
    if series == ' BE' or series == ' BZ':
        dq = v
    else:
        dq = int(dq)

    # average volume per trade.
    avg_trd_count = round(v / trd_count, 2)

    # append the line into the csv file and save it
    text += f'{dates.pandas_dt},{v},{trd_count},{avg_trd_count},{dq}\n'

    with file.open('a') as f:
        f.write(text)


def getSplit(sym, string):
    '''Run a regex search for splits related corporate action and
    return the adjustment factor'''

    match = split_regex.search(string)

    if match is None:
        print(f'{sym}: Not Matched. {string}')
        return match

    return float(match.group(1)) / float(match.group(2))


def getBonus(sym, string):
    '''Run a regex search for bonus related corporate action and
    return the adjustment factor'''

    match = bonus_regex.search(string)

    if match is None:
        print(f'{sym}: Not Matched. {string}')
        return match

    return 1 + int(match.group(1)) / int(match.group(2))


def makeAdjustment(symbol: str, adjustmentFactor: float):
    '''Makes adjustment to stock data prior to ex date,
    returning a tuple of pandas DataFrame and filename'''

    file = daily_folder / f'{symbol.lower()}.csv'

    if not file.is_file():
        print(f'{symbol}: File not found')
        return

    df = read_csv(file,
                  index_col='Date',
                  parse_dates=True,
                  na_filter=False)

    idx = df.index.get_loc(dates.dt)

    last = df.iloc[idx:]

    df = df.iloc[:idx].copy()

    for col in df.columns:
        if col == 'Volume':
            continue

        # nearest 0.05 = round(nu / 0.05) * 0.05
        df[col] = ((df[col] / adjustmentFactor / 0.05).round() * 0.05).round(2)

    df = concat([df, last])
    return (df, file)


def updateIndice(sym, O, H, L, C, V):
    'Appends Index EOD data to end of file'

    file = daily_folder / f'{sym.lower()}.csv'

    text = ''

    if not file.is_file():
        text += 'Date,Open,High,Low,Close,Volume\n'

    text += f"{dates.pandas_dt},{O},{H},{L},{C},{V}\n"

    with file.open('a') as f:
        f.write(text)


def updateIndexEOD(file: Path):
    '''Iterates over each symbol in NSE indices reports and
    update EOD data to respective csv file'''

    folder = DIR / 'nseIndices' / str(dates.dt.year)

    if not folder.is_dir():
        folder.mkdir(parents=True)

    df = read_csv(file, index_col='Index Name')

    df.to_csv(folder / file.name)

    indices = (DIR / 'eod2_data' /
               'sector_watchlist.csv').read_text().strip().split("\n")

    if any(config.ADDITIONAL_INDICES):
        indices.extend([
            sym for sym in config.ADDITIONAL_INDICES if sym not in indices
        ])

    for sym in indices:
        O, H, L, C, V = df.loc[sym, [
            'Open Index Value', 'High Index Value',
            'Low Index Value', 'Closing Index Value', 'Volume'
        ]]

        updateIndice(sym, O, H, L, C, V)

    pe = float(df.at['Nifty 50', 'P/E'])

    if pe >= 25 or pe <= 20:
        print(f'\033[1;32m### Alert: Nifty PE at {pe}! ###\033[0;94m')


def adjustNseStocks():
    '''Iterates over NSE corporate actions searching for splits or bonus
    on current date and adjust the stock accordingly'''

    dt_str = dates.dt.strftime('%d-%b-%Y')

    for actionFile in (equityActionsFile, smeActionsFile):
        actions = loads(actionFile.read_bytes())

        # Store all Dataframes with associated files names to be saved to file
        # if no error occurs
        df_commits = []

        try:
            for act in actions:
                sym = act['symbol']
                purpose = act['subject'].lower()
                ex = act['exDate']
                series = act['series']

                if not series in ('EQ', 'BE', 'BZ', 'SM', 'ST'):
                    continue

                if series in ('SM', 'ST'):
                    sym += '_sme'

                if ('split' in purpose or 'splt' in purpose) and ex == dt_str:
                    adjustmentFactor = getSplit(sym, purpose)

                    if adjustmentFactor is None:
                        continue

                    df_commits.append(makeAdjustment(sym, adjustmentFactor))

                    print(f'{sym}: {purpose}')

                if 'bonus' in purpose and ex == dt_str:
                    adjustmentFactor = getBonus(sym, purpose)

                    if adjustmentFactor is None:
                        continue

                    df_commits.append(makeAdjustment(sym, adjustmentFactor))

                    print(f'{sym}: {purpose}')
        except Exception as e:
            # discard all Dataframes and raise error,
            # so changes can be rolled back
            df_commits.clear()
            raise e

        # commit changes
        for df, file in df_commits:
            df.to_csv(file)


def getLastDate(file):
    'Get the last updated date for a stock csv file'

    # source: https://stackoverflow.com/a/68413780
    with open(file, 'rb') as f:
        try:
            # seek 2 bytes to the last line ending ( \n )
            f.seek(-2, SEEK_END)

            # seek backwards 2 bytes till the next line ending
            while f.read(1) != b'\n':
                f.seek(-2, SEEK_CUR)

        except OSError:
            # catch OSError in case of a one line file
            f.seek(0)

        # we have the last line
        lastLine = f.readline().decode()

    # split the line (Date, O, H, L, C) and get the first item (Date)
    return lastLine.split(',')[0]


def rollback(folder: Path):
    '''Iterate over all files in folder and delete any lines
    pertaining to the current date'''

    dt = dates.pandas_dt
    print(f"Rolling back changes from {dt}: {folder}")

    for file in folder.iterdir():
        df = read_csv(file, index_col='Date',
                      parse_dates=True, na_filter=False)

        if dt in df.index:
            df = df.drop(dt)
            df.to_csv(file)

    print('Rollback successful')


def cleanup(files_lst):
    '''Remove files downloaded from nse and stock csv files not updated
    in the last 365 days'''

    for file in files_lst:
        file.unlink()

    # remove outdated files
    deadline = dates.today - timedelta(365)
    count = 0
    fmt = '%Y-%m-%d'

    for file in daily_folder.iterdir():
        lastUpdated = datetime.strptime(getLastDate(file), fmt)

        dlvry_file = delivery_folder / file.name

        if lastUpdated < deadline:
            file.unlink()

            if dlvry_file.is_file():
                dlvry_file.unlink()

            count += 1

    print(f'{count} files deleted')
