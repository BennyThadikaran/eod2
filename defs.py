from requests import get
from requests.exceptions import ReadTimeout
from pathlib import Path
from os import system, scandir, SEEK_END, SEEK_CUR
from os.path import getmtime, getsize
from datetime import datetime, timedelta
from json import load as json_load, dump as json_dump
from re import compile
from pandas import read_csv, concat
from zipfile import ZipFile
from sys import platform
from pickle import dump as pickle_dump, load as pickle_load

# Check if system is windows or linux
if 'win' in platform:
    # enable color support in Windows
    system('color')

today = datetime.combine(datetime.today(), datetime.min.time())

DIR = Path(__file__).parent

daily_folder = DIR / 'daily'
delivery_folder = DIR / 'delivery'
nseActionsFile = DIR / 'nse_actions.json'

# delivery headings
header_text = 'Date,TTL_TRD_QNTY,NO_OF_TRADES,QTY_PER_TRADE,DELIV_QTY,DELIV_PER\n'

userAgent = 'Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0'

isin = read_csv(DIR / 'isin.csv', index_col='ISIN')

etfs = (DIR / 'etf.csv').read_text().strip().split('\n')

headers = {
    'User-Agent': userAgent,
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www1.nseindia.com'
}

# split_regex = compile('fro?m rs[\. ](\d+).+to.+(\d+)')
split_regex = compile('(\d+\.?\d*)[\/\- a-z\.]+(\d+\.?\d*)')

bonus_regex = compile('(\d+) ?: ?(\d+)')


def setCookies():
    r = makeRequest('https://www.nseindia.com/option-chain',
                    params=None,
                    headers=headers,
                    timeout=10,
                    expectJson=False)

    if not r.ok:
        exit(f'Error: set cookie. {r.status_code}: {r.reason}')

    cookies = r.cookies

    with (DIR / 'cookies').open('wb') as f:
        pickle_dump(cookies, f)

    return cookies


def getCookies():
    file = DIR / 'cookies'

    if file.is_file():
        with file.open('rb') as f:
            cookies = pickle_load(f)

        if hasCookiesExpired(cookies):
            cookies = setCookies()

        return cookies

    return setCookies()


def hasCookiesExpired(cookies):
    for cookie in cookies:
        if cookie.is_expired():
            return True

    return False


def getLastUpdated():
    file = DIR / 'lastupdate.txt'

    if not file.is_file():
        return today - timedelta(1)

    return datetime.fromisoformat(file.read_text().strip())


def setLastUpdated(dt):
    (DIR / 'lastupdate.txt').write_text(dt.isoformat())


def getNextDate(dt):
    curTime = datetime.today()
    nxtDt = dt + timedelta(1)

    if nxtDt > curTime:
        exit('All Up To Date')

    if nxtDt.day == curTime.day and curTime.hour < 19:
        exit("All Up To Date. Check again after 7pm for today's EOD data")

    week_day = nxtDt.weekday()

    if week_day > 4:
        return nxtDt + timedelta(7 - week_day)

    return nxtDt


def checkForHolidays(dt):
    file = DIR / 'holiday.json'

    fileModifiedDate = datetime.fromtimestamp(getmtime(file))

    if file.is_file() and fileModifiedDate.year == dt.year:
        # holidays are updated for current year
        with file.open() as f:
            holidays = json_load(f)
    else:
        # new year get new holiday list
        holidays = getHolidayList()

        with file.open('w') as f:
            json_dump(holidays, f, indent=3)

        print('NSE Holiday list updated')

    curDt = dt.strftime('%d-%b-%Y')
    isToday = curDt == today.strftime('%d-%b-%Y')

    for day in holidays:
        if day['tradingDate'] == curDt:
            if not isToday:
                print(f'{curDt} Market Holiday: {day["description"]}')
                return True

            exit(f'Market Holiday: {day["description"]}')

    return False


def validateNseActionsFile():

    if not nseActionsFile.is_file():
        getActions(dt, dt + timedelta(8))
    else:
        lastModifiedTS = getmtime(nseActionsFile)

        # Update every 7 days from last download
        if dt.timestamp() - lastModifiedTS > 7 * 24 * 60 * 60:
            fmt = '%d %b %Y'
            frm_dt = datetime.fromtimestamp(lastModifiedTS) + timedelta(7)
            getActions(frm_dt, dt + timedelta(8))


def getActions(from_dt, to_dt):

    print('Updating NSE corporate actions file')
    cookies = getCookies()
    fmt = '%d-%m-%Y'

    params = {
        'index': 'equities',
        'from_date': from_dt.strftime(fmt),
        'to_date': to_dt.strftime(fmt),
    }

    data = makeRequest('https://www.nseindia.com/api/corporates-corporateActions',
                       params=params,
                       headers=headers,
                       cookies=cookies)

    with nseActionsFile.open('w') as f:
        json_dump(data, f, indent=3)


def download(url):
    fname = DIR / url.split("/")[-1]

    r = get(url, stream=True, headers=headers, timeout=15)

    with open(fname, 'wb') as f:
        for chunk in r.iter_content(chunk_size=128):
            f.write(chunk)
    return fname


def downloadNseDelivery():
    url = f'https://archives.nseindia.com/products/content/sec_bhavdata_full_{dt:%d%m%Y}.csv'

    delivery_file = download(url)

    if not delivery_file.is_file() or getsize(delivery_file) < 50000:
        exit('Download Failed: ' + delivery_file.name)

    return delivery_file


def downloadNseBhav():
    dt_str = dt.strftime('%d%b%Y').upper()
    month = dt_str[2:5].upper()

    url = f'https://archives.nseindia.com/content/historical/EQUITIES/{dt.year}/{month}/cm{dt_str}bhav.csv.zip'

    bhavFile = download(url)

    if not bhavFile.is_file() or getsize(bhavFile) < 50000:
        exit('Download Failed: ' + bhavFile.name)

    return bhavFile


def updateNseEOD(bhavFile):
    isin_updated = False

    with ZipFile(bhavFile) as zip:
        csvFile = bhavFile.name.replace('.zip', '')

        with zip.open(csvFile) as f:
            df = read_csv(f, index_col='ISIN')

    folder = DIR / 'nseBhav' / str(dt.year)

    if not folder.is_dir():
        folder.mkdir(parents=True)

    df.to_csv(folder / csvFile)

    df = df[(df['SERIES'] == 'EQ') | (
        df['SERIES'] == 'BE') | (df['SERIES'] == 'BZ')]

    for t in df.itertuples(name=None):
        idx, sym, _, O, H, L, C, _, _, V, *_ = t

        if '-RE' in sym or sym in etfs:
            continue

        sym_file = daily_folder / f'{sym.lower()}.csv'

        if not idx in isin.index:
            isin_updated = True
            isin.at[idx, 'SYMBOL'] = sym

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
                    f'ERROR: Renaming daily/{old}.csv to {new}.csv. No such file.')

            try:
                old_delivery_file.rename(delivery_folder / f'{new}.csv')
            except FileNotFoundError:
                print(
                    f'ERROR: Renaming delivery/{old}.csv to {new}.csv. No such file.')

            print(f'Name Changed: {old} to {new}')

        updateNseSymbol(sym_file, O, H, L, C, V)

    if isin_updated:
        isin.to_csv(DIR / 'isin.csv')


def updateDelivery(file):
    df = read_csv(file, index_col='SYMBOL')

    folder = DIR / 'nseDelivery' / str(dt.year)

    if not folder.is_dir():
        folder.mkdir(parents=True)

    df.to_csv(folder / file.name)

    df = df[(df[' SERIES'] == ' EQ') | (
        df[' SERIES'] == ' BE') | (df[' SERIES'] == ' BZ')]

    for t in df.itertuples(name=None):
        sym, series, *_, v, _, trd_count, dq, _ = t

        if '-RE' in sym or sym in etfs:
            continue

        updateDeliveryData(sym, series, v, int(trd_count), dq)

    print('Delivery Data updated')


def updateNseSymbol(sym_file, o, h, l, c, v):
    text = ''

    if not sym_file.is_file():
        text += 'Date,Open,High,Low,Close,Volume\n'

    text += f'{pandas_dt},{o},{h},{l},{c},{v}\n'

    with sym_file.open('a') as f:
        f.write(text)


def updateDeliveryData(sym, series, v, trd_count, dq):
    file = delivery_folder / f'{sym.lower()}.csv'
    text = ''

    if not file.is_file():
        text += header_text

    if series == ' BE' or series == ' BZ':
        dq = v
    else:
        dq = int(dq)

    avg_trd_count = round(v / trd_count, 2)
    text += f'{pandas_dt},{v},{trd_count},{avg_trd_count},{dq}\n'

    with file.open('a') as f:
        f.write(text)


def downloadIndexFile():
    base_url = 'https://archives.nseindia.com/content'
    url = f'{base_url}/indices/ind_close_all_{dt:%d%m%Y}.csv'

    index_file = download(url)

    if not index_file.is_file() or getsize(index_file) < 5000:
        exit('Download Failed: ' + index_file.name)

    return index_file


def makeRequest(url, params, headers, cookies=None, expectJson=True, timeout=15):
    try:
        r = get(url, params=params, headers=headers,
                cookies=cookies, timeout=timeout)
    except ReadTimeout:
        raise TimeoutError('Request timed out')

    if not r.ok:
        raise ConnectionError(f'{r.status_code}: {r.reason}')

    if expectJson:
        return r.json()

    return r


def getSplit(sym, string):
    match = split_regex.search(string)

    if match is None:
        print(f'{sym}: Not Matched. {string}')
        return match

    return float(match.group(1)) / float(match.group(2))


def getBonus(sym, string):
    match = bonus_regex.search(string)

    if match is None:
        print(f'{sym}: Not Matched. {string}')
        return match

    return 1 + int(match.group(1)) / int(match.group(2))


def makeAdjustment(symbol, split):
    print(symbol)
    file = daily_folder / f'{symbol.lower()}.csv'

    if not file.is_file():
        print(f'{symbol}: File not found')
        return

    df = read_csv(file,
                  index_col='Date',
                  parse_dates=True,
                  na_filter=False)

    idx = df.index.get_loc(dt)

    last = df.iloc[idx:]

    df = df.iloc[:idx].copy()

    for col in df.columns:
        if col == 'Volume':
            continue

        # nearest 0.05 = round(nu / 0.05) * 0.05
        df[col] = ((df[col] / split / 0.05).round() * 0.05).round(2)

    df = concat([df, last])
    df.to_csv(file)


def updateIndice(sym, O, H, L, C, V):
    file = daily_folder / f'{sym.lower()}.csv'

    text = ''

    if not file.is_file():
        text += 'Date,Open,High,Low,Close,Volume\n'

    with file.open('a') as f:
        f.write(f"{pandas_dt},{O},{H},{L},{C},{V}\n")


def updateIndexEOD(file):
    folder = DIR / 'nseIndices' / str(dt.year)

    if not folder.is_dir():
        folder.mkdir(parents=True)

    df = read_csv(file, index_col='Index Name')

    df.to_csv(folder / file.name)

    with (DIR / 'sector_watchlist.csv').open() as f:
        while sym := f.readline().strip():
            O, H, L, C, V = df.loc[sym, [
                'Open Index Value', 'High Index Value',
                'Low Index Value', 'Closing Index Value', 'Volume'
            ]]

            updateIndice(sym, O, H, L, C, V)

    pe = float(df.at['Nifty 50', 'P/E'])

    if pe >= 25 or pe <= 20:
        print(f'\033[1;32m### Alert: Nifty PE at {pe}! ###\033[0;94m')


def adjustNseStocks():
    dt_str = dt.strftime('%d-%b-%Y')

    with nseActionsFile.open() as f:
        actions = json_load(f)

    for act in actions:
        sym = act['symbol']
        purpose = act['subject'].lower()
        ex = act['exDate']
        series = act['series']

        if not series in ('EQ', 'BE', 'BZ'):
            continue

        if ('split' in purpose or 'splt' in purpose) and ex == dt_str:
            split = getSplit(sym, purpose)

            if split is None:
                continue

            makeAdjustment(sym, split)

            print(f'{sym}: {purpose}')

        if 'bonus' in purpose and ex == dt_str:
            bonus = getBonus(sym, purpose)

            if bonus is None:
                continue

            makeAdjustment(sym, bonus)

            print(f'{sym}: {purpose}')


def getHolidayList():
    url = 'https://www.nseindia.com/api/holiday-master'

    params = {
        'type': 'trading',
    }

    headers['Referer'] = 'https://www1.nseindia.com'

    data = makeRequest(url, params, headers)

    return data['CM']


def getLastDate(file):
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


def cleanup(files_lst):
    for file in files_lst:
        file.unlink()

    # remove outdated files
    deadline = today - timedelta(365)
    count = 0
    fmt = '%Y-%m-%d'

    with scandir(daily_folder) as it:
        for entry in it:

            lastUpdated = datetime.strptime(getLastDate(entry.path), fmt)

            dlvry_file = delivery_folder / entry.name

            if lastUpdated < deadline:
                Path(entry.path).unlink()

                if dlvry_file.is_file():
                    dlvry_file.unlink()

                count += 1

    print(f'{count} files deleted')
