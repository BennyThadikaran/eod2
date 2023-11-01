from sys import platform
import json
import numpy as np
from nse import NSE
from pathlib import Path
from datetime import datetime, timedelta
from defs.Dates import Dates
from pandas import read_csv, concat
from os import system, SEEK_END, SEEK_CUR
from re import compile
from defs.Config import Config
from typing import cast, Any

# Avoid side effects in case this file is directly executed
# instead of being imported
if __name__ != '__main__':

    if 'win' in platform:
        # enable color support in Windows
        system('color')

    DIR = Path(__file__).parents[1]
    DAILY_FOLDER = DIR / 'eod2_data' / 'daily'
    ISIN_FILE = DIR / 'eod2_data' / 'isin.csv'
    AMIBROKER_FOLDER = DIR / 'eod2_data' / 'amibroker'

    META_FILE = DIR / 'eod2_data' / 'meta.json'

    meta: dict = json.loads(META_FILE.read_bytes())

    config = Config()

    if config.AMIBROKER and not AMIBROKER_FOLDER.exists():
        AMIBROKER_FOLDER.mkdir()

    isin = read_csv(ISIN_FILE, index_col='ISIN')

    headerText = 'Date,Open,High,Low,Close,Volume,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n'

    splitRegex = compile(r'(\d+\.?\d*)[\/\- a-z\.]+(\d+\.?\d*)')

    bonusRegex = compile(r'(\d+) ?: ?(\d+)')

    # initiate the dates class from utils.py
    dates = Dates(meta['lastUpdate'])

    hasLatestHolidays = False


def getHolidayList(nse: NSE):
    """Makes a request for NSE holiday list for the year.
    Saves and returns the holiday Object"""
    try:
        data = nse.holidays(type=nse.HOLIDAY_TRADING)
    except Exception as e:
        exit(f'{e!r}\nFailed to download holidays')

    # CM pertains to capital market or equity holdays
    data = {k['tradingDate']: k['description'] for k in data['CM']}
    print('NSE Holiday list updated')

    return data


def checkForHolidays(nse: NSE):
    """Returns True if current date is a holiday.
    Exits the script if today is a holiday"""

    global hasLatestHolidays

    # the current date for which data is being synced
    curDt = dates.dt.strftime('%d-%b-%Y')
    isToday = curDt == dates.today.strftime('%d-%b-%Y')

    if not 'holidays' in meta or meta['holidayYear'] != dates.dt.year:
        meta['holidays'] = getHolidayList(nse)
        meta['holidayYear'] = dates.dt.year
        hasLatestHolidays = True

    if curDt in meta['holidays']:
        if not hasLatestHolidays:
            meta['holidays'] = getHolidayList(nse)

        if not isToday:
            print(f'{curDt} Market Holiday: {meta["holdays"][curDt]}')
            return True

        exit(f'Market Holiday: {meta["holidays"][curDt]}')

    return False


def validateNseActionsFile(nse: NSE):
    """Check if the NSE Corporate actions() file exists.
    If exists, check if the file is older than 7 days.
    Else request actions for the next 8 days from current date.
    The actionsFile pertains to Bonus, Splits, dividends etc.
    """

    for actions in ('equityActions', 'smeActions'):
        segment = 'sme' if 'sme' in actions else 'equities'

        if not actions in meta:
            print(f'Updating NSE {segment.upper()} actions file')

            try:
                meta[actions] = nse.actions(segment=segment,
                                            from_date=dates.dt,
                                            to_date=dates.dt + timedelta(8))
            except Exception as e:
                exit(f'{e!r}\nFailed to download {segment} actions')

            meta[f'{actions}Expiry'] = (dates.dt + timedelta(7)).isoformat()
        else:
            expiryDate = datetime.fromisoformat(meta[f'{actions}Expiry'])
            newExpiry = (expiryDate + timedelta(7)).isoformat()

            # Update every 7 days from last download
            if dates.dt < expiryDate:
                continue

            print(f'Updating NSE {segment.upper()} actions file')

            try:
                meta[actions] = nse.actions(segment=segment,
                                            from_date=expiryDate,
                                            to_date=expiryDate + timedelta(8))
            except Exception as e:
                exit(f'{e!r}\nFailed to download {segment} actions')

            meta[f'{actions}Expiry'] = newExpiry


def isAmiBrokerFolderUpdated():
    'Returns true if the folder has files'

    return any(AMIBROKER_FOLDER.iterdir())


def updateAmiBrokerRecords(nse: NSE):
    '''Downloads and updates the amibroker files upto the number of days
    set in Config.AMI_UPDATE_DAYS'''

    lastUpdate = datetime.fromisoformat(meta['lastUpdate'])
    dates.dt -= timedelta(config.AMI_UPDATE_DAYS)
    totalDays = config.AMI_UPDATE_DAYS

    print(f'Fetching bhavcopy for last {totalDays} days',
          'and converting to AmiBroker format.\n'
          'This is a one time process. It will take a few minutes.')

    while dates.dt <= lastUpdate:
        if dates.dt.weekday() == 5:
            dates.dt += timedelta(2)

        try:
            bhavFile = nse.equityBhavcopy(dates.dt)
        except (RuntimeError, FileNotFoundError):
            dates.dt += timedelta(1)
            continue

        toAmiBrokerFormat(bhavFile)

        bhavFile.unlink()

        daysComplete = totalDays - (lastUpdate - dates.dt).days
        pctComplete = int(daysComplete / totalDays * 100)
        print(f'{pctComplete} %', end="\r" * 5, flush=True)
        dates.dt += timedelta(1)

    print("\nDone")


def updateNseEOD(bhavFile: Path, deliveryFile: Path):
    """Update all stocks with latest price data from bhav copy"""

    isinUpdated = False

    df = read_csv(bhavFile, index_col='ISIN')
    dlvDf = read_csv(deliveryFile, index_col='SYMBOL')

    if config.AMIBROKER:
        print("Converting to AmiBroker format")
        toAmiBrokerFormat(bhavFile)

    # save the csv file to the below folder.
    BHAV_FOLDER = DIR / 'nseBhav' / str(dates.dt.year)
    DLV_FOLDER = DIR / 'nseDelivery' / str(dates.dt.year)

    # Create it if not exists
    if not BHAV_FOLDER.is_dir():
        BHAV_FOLDER.mkdir(parents=True)

    if not DLV_FOLDER.is_dir():
        DLV_FOLDER.mkdir(parents=True)

    df.to_csv(BHAV_FOLDER / bhavFile.name)
    dlvDf.to_csv(DLV_FOLDER / bhavFile.name)

    # filter the dataframe for stocks series EQ, BE and BZ
    # https://www.nseindia.com/market-data/legend-of-series
    df: DataFrame = df[(df['SERIES'] == 'EQ') |
                       (df['SERIES'] == 'BE') |
                       (df['SERIES'] == 'BZ') |
                       (df['SERIES'] == 'SM') |
                       (df['SERIES'] == 'ST')]

    # filter the dataframe for stocks series EQ, BE and BZ
    # https://www.nseindia.com/market-data/legend-of-series
    dlvDf: DataFrame = dlvDf[(dlvDf[' SERIES'] == ' EQ') |
                             (dlvDf[' SERIES'] == ' BE') |
                             (dlvDf[' SERIES'] == ' BZ') |
                             (dlvDf[' SERIES'] == ' SM') |
                             (dlvDf[' SERIES'] == ' ST')]

    # iterate over each row as a tuple
    for t in df.itertuples():
        t: Any = cast(Any, t)

        # ignore rights issue
        if '-RE' in t.SYMBOL:
            continue

        if t.SYMBOL in dlvDf.index:
            trdCnt, dq = dlvDf.loc[t.SYMBOL, [' NO_OF_TRADES', ' DELIV_QTY']]

            # BE and BZ series stocks are all delivery trades, so we use the volume
            dq = t.TOTTRDQTY if t.SERIES in ('BE', 'BZ') else int(dq)
        else:
            trdCnt = dq = np.NAN

        prefix = '_sme' if t.SERIES in ('SM', 'ST') else ''
        SYM_FILE = DAILY_FOLDER / f'{t.SYMBOL.lower()}{prefix}.csv'

        # ISIN is a unique identifier for each stock symbol.
        # When a symbol name changes its ISIN remains the same
        # This allows for tracking changes in symbol names and
        # updating file names accordingly
        if not t.Index in isin.index:
            isinUpdated = True
            isin.at[t.Index, 'SYMBOL'] = t.SYMBOL

        # if symbol name does not match the symbol name under its ISIN
        # we rename the files in daily and delivery folder
        if t.SYMBOL != isin.at[t.Index, 'SYMBOL']:
            isinUpdated = True
            old = isin.at[t.Index, 'SYMBOL'].lower()

            new = t.SYMBOL.lower()

            isin.at[t.Index, 'SYMBOL'] = t.SYMBOL

            SYM_FILE = DAILY_FOLDER / f'{new}.csv'
            OLD_FILE = DAILY_FOLDER / f'{old}.csv'

            try:
                OLD_FILE.rename(SYM_FILE)
            except FileNotFoundError:
                print(
                    f'WARN: Renaming daily/{old}.csv to {new}.csv. No such file.')

            print(f'Name Changed: {old} to {new}')

        updateNseSymbol(SYM_FILE, t.OPEN, t.HIGH, t.LOW, t.CLOSE, t.TOTTRDQTY,
                        trdCnt, dq)

    if isinUpdated:
        isin.to_csv(ISIN_FILE)


def toAmiBrokerFormat(file: Path):
    'Converts and saves bhavcopy into amibroker format'

    cols = ['SYMBOL', 'TIMESTAMP', 'OPEN', 'HIGH',
            'LOW', 'CLOSE', 'TOTTRDQTY', 'ISIN']

    rcols = list(cols)
    rcols[1] = 'DATE'
    rcols[-2] = 'VOLUME'

    df = read_csv(file, parse_dates=['TIMESTAMP'])

    df = df[(df['SERIES'] == 'EQ') |
            (df['SERIES'] == 'BE') |
            (df['SERIES'] == 'BZ') |
            (df['SERIES'] == 'SM') |
            (df['SERIES'] == 'ST')]

    df = df[cols]
    df.columns = rcols
    df['DATE'] = df['DATE'].dt.strftime("%Y%m%d")
    df.to_csv(AMIBROKER_FOLDER / file.name, index=False)


def updateNseSymbol(symFile: Path, o, h, l, c, v, trdCnt, dq):
    'Appends EOD stock data to end of file'

    text = ''

    if not symFile.is_file():
        text += headerText

    avgTrdCnt = round(v / trdCnt, 2)

    text += f'{dates.pandasDt},{o},{h},{l},{c},{v},{trdCnt},{avgTrdCnt},{dq}\n'

    with symFile.open('a') as f:
        f.write(text)


def getSplit(sym, string):
    '''Run a regex search for splits related corporate action and
    return the adjustment factor'''

    match = splitRegex.search(string)

    if match is None:
        print(f'{sym}: Not Matched. {string}')
        return match

    return float(match.group(1)) / float(match.group(2))


def getBonus(sym, string):
    '''Run a regex search for bonus related corporate action and
    return the adjustment factor'''

    match = bonusRegex.search(string)

    if match is None:
        print(f'{sym}: Not Matched. {string}')
        return match

    return 1 + int(match.group(1)) / int(match.group(2))


def makeAdjustment(symbol: str, adjustmentFactor: float):
    '''Makes adjustment to stock data prior to ex date,
    returning a tuple of pandas DataFrame and filename'''

    file = DAILY_FOLDER / f'{symbol.lower()}.csv'

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

    for col in ('Open', 'High', 'Low', 'Close'):
        # nearest 0.05 = round(nu / 0.05) * 0.05
        df[col] = ((df[col] / adjustmentFactor / 0.05).round() * 0.05).round(2)

    df = concat([df, last])
    return (df, file)


def updateIndice(sym, O, H, L, C, V):
    'Appends Index EOD data to end of file'

    file = DAILY_FOLDER / f'{sym.lower()}.csv'

    text = ''

    if not file.is_file():
        text += headerText

    text += f"{dates.pandasDt},{O},{H},{L},{C},{V},,,\n"

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

    dtStr = dates.dt.strftime('%d-%b-%Y')

    for actions in ('equityActions', 'smeActions'):
        actions = meta[actions]

        # Store all Dataframes with associated files names to be saved to file
        # if no error occurs
        dfCommits = []

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

                if ('split' in purpose or 'splt' in purpose) and ex == dtStr:
                    adjustmentFactor = getSplit(sym, purpose)

                    if adjustmentFactor is None:
                        continue

                    dfCommits.append(makeAdjustment(sym, adjustmentFactor))

                    print(f'{sym}: {purpose}')

                if 'bonus' in purpose and ex == dtStr:
                    adjustmentFactor = getBonus(sym, purpose)

                    if adjustmentFactor is None:
                        continue

                    dfCommits.append(makeAdjustment(sym, adjustmentFactor))

                    print(f'{sym}: {purpose}')
        except Exception as e:
            # discard all Dataframes and raise error,
            # so changes can be rolled back
            dfCommits.clear()
            raise e

        # commit changes
        for df, file in dfCommits:
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

    dt = dates.pandasDt
    print(f"Rolling back changes from {dt}: {folder}")

    for file in folder.iterdir():
        df = read_csv(file, index_col='Date',
                      parse_dates=True, na_filter=False)

        if dt in df.index:
            df = df.drop(dt)
            df.to_csv(file)

    print('Rollback successful')


def cleanup(filesLst):
    '''Remove files downloaded from nse and stock csv files not updated
    in the last 365 days'''

    for file in filesLst:
        file.unlink()

    # remove outdated files
    deadline = dates.today - timedelta(365)
    count = 0
    fmt = '%Y-%m-%d'

    for file in DAILY_FOLDER.iterdir():
        lastUpdated = datetime.strptime(getLastDate(file), fmt)

        if lastUpdated < deadline:
            file.unlink()
            count += 1

    print(f'{count} files deleted')
