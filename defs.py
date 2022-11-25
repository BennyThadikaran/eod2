from requests import get
from requests.exceptions import ReadTimeout
import os
from datetime import datetime, timedelta
from json import load, dump
from re import compile, search
from pandas import read_csv, concat
from zipfile import ZipFile
from sys import platform
import pickle

# Check if system is windows or linux
if 'win' in platform:
    # enable color support in Windows
    system('color')

today = datetime.combine(datetime.today(), datetime.min.time())

DIR = os.path.dirname(os.path.realpath(__file__))

nseBaseUrl = 'https://archives.nseindia.com/content'
nseActionsFile = DIR + '/nse_actions.json'

# delivery headings
header_text = 'Date,TTL_TRD_QNTY,NO_OF_TRADES,QTY_PER_TRADE,DELIV_QTY,DELIV_PER\n'

userAgent = 'Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0'

isin = read_csv(f'{DIR}/isin.csv', index_col='ISIN')
etf_index = read_csv(f'{DIR}/etf.csv', index_col='SYMBOL').index

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

    with open(f'{DIR}/cookies', 'wb') as f:
        pickle.dump(cookies, f)

    return cookies


def getCookies():
    file = f'{DIR}/cookies'

    if os.path.isfile(file):
        with open(file, 'rb') as f:
            cookies = pickle.load(f)

        if hasCookiesExpired(cookies):
            cookies = setCookies()

        return cookies

    return setCookies()


def hasCookiesExpired(cookies):
    for cookie in cookies:
        if cookie.is_expired():
            return True

    return False


def getLastUpdated(file):
    file = DIR + file

    if not os.path.isfile(file):
        return today - timedelta(1)

    with open(file) as f:
        dt = datetime.fromisoformat(f.read().strip())

    return dt


def setLastUpdated(dt, file):
    with open(DIR + file, 'w') as f:
        f.write(dt.isoformat())


def getNextDate(dt):
    curTime = datetime.today()
    nxtDt = dt + timedelta(1)

    if nxtDt > curTime or (nxtDt.day == curTime.day and curTime.hour < 19):
        exit('All Up To Date')

    if nxtDt.isoweekday() in (6, 7):
        return getNextDate(nxtDt + timedelta(1))

    return nxtDt


def checkForHolidays(dt):
    file = DIR + '/holiday.json'

    fileModifiedDate = datetime.fromtimestamp(os.path.getmtime(file))

    if os.path.isfile(file) and fileModifiedDate.year == dt.year:
        # holidays are updated for current year
        with open(file) as f:
            holidays = load(f)
    else:
        # new year get new holiday list
        holidays = getHolidayList()

        with open(file, 'w') as f:
            dump(holidays, f, indent=3)
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

    if not os.path.isfile(nseActionsFile):
        getActions(dt, dt + timedelta(8))
    else:
        lastModifiedTS = os.path.getmtime(nseActionsFile)

        if dt.timestamp() - lastModifiedTS > 7 * 24 * 60 * 60:
            fmt = '%d %b %Y'
            frm_dt = datetime.fromtimestamp(lastModifiedTS) + timedelta(7)
            print('Updating NSE actions file')
            getActions(frm_dt, dt + timedelta(8))


def getActions(from_dt, to_dt):

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

    with open(f'{DIR}/nse_actions.json', 'w') as f:
        dump(data, f, indent=3)


def download(url):
    fname = f'{DIR}/{url.split("/")[-1]}'

    r = get(url, stream=True, headers=headers, timeout=15)

    with open(fname, 'wb') as f:
        for chunk in r.iter_content(chunk_size=128):
            f.write(chunk)
    return fname


def downloadNseDelivery():
    url = 'https://archives.nseindia.com/products/content/sec_bhavdata_full_{}.csv'
    url = url.format(dt.strftime('%d%m%Y'))

    try:
        df = read_csv(url, index_col='SYMBOL')
    except UnicodeDecodeError as e:
        print('Delivery file corrupted.', e.reason)
        return None

    folder = f'{DIR}/nseDelivery/{dt.year}'

    if not os.path.isdir(folder):
        os.mkdir(folder)

    df.to_csv(f'{folder}/{url.split("/")[-1]}')

    df = df[(df[' SERIES'] == ' EQ') | (
        df[' SERIES'] == ' BE') | (df[' SERIES'] == ' BZ')]

    return df


def downloadNseBhav():
    dt_str = dt.strftime('%d%b%Y').upper()
    month = dt_str[2:5].upper()

    url = f'https://archives.nseindia.com/content/historical/EQUITIES/{dt.year}/{month}/cm{dt_str}bhav.csv.zip'

    bhavFile = download(url)

    if not os.path.isfile(bhavFile) or os.path.getsize(bhavFile) < 50000:
        exit('Download Failed: ' + bhavFile)

    return bhavFile


def updateNseEOD(bhavFile):

    with ZipFile(bhavFile) as zip:
        csvFile = bhavFile.split('/')[-1].replace('.zip', '')

        with zip.open(csvFile) as f:
            df = read_csv(f, index_col='ISIN')

            folder = f'{DIR}/nseBhav/{dt.year}'

            if not os.path.isdir(folder):
                os.mkdir(folder)

            df.to_csv(f'{folder}/{csvFile}')

            df = df[(df['SERIES'] == 'EQ') | (
                df['SERIES'] == 'BE') | (df['SERIES'] == 'BZ')]

            dup = None

            if df.index.has_duplicates:
                dup = df[df.index.duplicated(keep=False)]

                dup = dup[dup['SERIES'] == 'EQ']

            pandas_dt = dt.strftime('%Y-%m-%d')

            for idx in df.index:
                sym = df.loc[idx, 'SYMBOL']

                if '-RE' in sym or sym in etf_index:
                    continue

                sym_file = f'{DIR}/daily/{sym.lower()}.csv'

                if not idx in isin.index:
                    isin.loc[idx, 'SYMBOL'] = sym

                if sym != isin.loc[idx, 'SYMBOL']:
                    old = isin.loc[idx, 'SYMBOL']

                    new = sym

                    isin.loc[idx, 'SYMBOL'] = new

                    try:
                        os.rename(f'{DIR}/daily/{old.lower()}.csv',
                                  f'{DIR}/daily/{new.lower()}.csv')
                    except FileNotFoundError:
                        print(
                            f'ERROR: Renaming daily/{old.lower()}.csv to {new.lower()}.csv. No such file.')

                    try:
                        os.rename(f'{DIR}/delivery/{old.lower()}.csv',
                                  f'{DIR}/delivery/{new.lower()}.csv')
                    except FileNotFoundError:
                        print(
                            f'ERROR: Renaming delivery/{old.lower()}.csv to {new.lower()}.csv. No such file.')

                    sym_file = f'{DIR}/daily/{new.lower()}.csv'

                    print(f'Name Changed: {old} to {new}')

                if not dup is None and idx in dup.index:
                    O, H, L, C, V = dup.loc[idx, [
                        'OPEN', 'HIGH', 'LOW', 'CLOSE', 'TOTTRDQTY']]
                else:
                    O, H, L, C, V = df.loc[idx, [
                        'OPEN', 'HIGH', 'LOW', 'CLOSE', 'TOTTRDQTY']]

                updateNseSymbol(sym_file, O, H, L, C, V)

    isin.to_csv(f'{DIR}/isin.csv')


def updateDelivery(df):
    if df is None:
        return None

    for sym in df.index:
        if '-RE' in sym or sym in etf_index:
            continue

        series, v, trd_count, dq = df.loc[sym, [
            ' SERIES', ' TTL_TRD_QNTY', ' NO_OF_TRADES', ' DELIV_QTY']]

        updateDeliveryData(sym, series, v, int(trd_count), dq)

    print('Delivery Data updated')


def updateNseSymbol(sym_file, o, h, l, c, v):
    text = ''

    if not os.path.isfile(sym_file):
        text += 'Date,O,H,L,C,V\n'

    text += f'{pandas_dt},{o},{h},{l},{c},{v}\n'

    with open(sym_file, 'a') as f:
        f.write(text)


def updateDeliveryData(sym, series, v, trd_count, dq):
    file = f'{DIR}/delivery/{sym.lower()}.csv'
    text = ''

    if not os.path.isfile(file):
        text += header_text

    if series == ' BE' or series == ' BZ':
        dq = v
    else:
        dq = int(dq)

    text += '{},{},{},{},{}\n'.format(
        pandas_dt,
        v,
        trd_count,
        round(v / trd_count, 2),
        dq
    )

    with open(file, 'a') as f:
        f.write(text)


def downloadIndexFile():
    dt_str = dt.strftime('%d%m%Y')
    url = f'{nseBaseUrl}/indices/ind_close_all_{dt_str}.csv'

    df = read_csv(url, index_col='Index Name')

    folder = f'{DIR}/nseIndices/{dt.year}'

    if not os.path.isdir(folder):
        os.mkdir(folder)

    df.to_csv(f'{folder}/{url.split("/")[-1]}')

    return df


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
    file = DIR + f'/daily/{symbol.lower()}.csv'

    if not os.path.isfile(file):
        print(f'{symbol}: File not found')
        return

    df = read_csv(file,
                  index_col='Date',
                  parse_dates=True,
                  infer_datetime_format=True,
                  na_filter=True)

    idx = df.index.get_loc(dt)

    last = df.iloc[idx:]

    df = df.iloc[:idx].copy()

    for col in df.columns:
        if col == 'V':
            continue

        # nearest 0.05 = round(nu / 0.05) * 0.05
        df[col] = ((df[col] / split / 0.05).round() * 0.05).round(2)

    df = concat([df, last])
    df.to_csv(file)


def updateIndice(sym, O, H, L, C, V):
    file = f'{DIR}/daily/{sym.lower()}.csv'

    text = ''

    if not os.path.isfile(file):
        text += 'Date,O,H,L,C,V\n'

    with open(file, 'a') as f:
        f.write(f"{pandas_dt},{O},{H},{L},{C},{V}\n")


def updateIndexEOD(df):
    watch = read_csv(f'{DIR}/sector_watchlist.csv', index_col='index')

    pe = float(df.loc['Nifty 50', 'P/E'])

    if pe >= 25 or pe <= 20:
        print(f'\033[1;32m### Alert: Nifty PE at {pe}! ###\033[0;94m')

    for sym in watch.index:
        O, H, L, C, V = df.loc[sym, [
            'Open Index Value', 'High Index Value',
            'Low Index Value', 'Closing Index Value', 'Volume'
        ]]

        updateIndice(sym, O, H, L, C, V)


def adjustNseStocks():
    dt_str = dt.strftime('%d-%b-%Y')

    with open(nseActionsFile) as f:
        actions = load(f)

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
            f.seek(-2, os.SEEK_END)

            # seek backwards 2 bytes till the next line ending
            while f.read(1) != b'\n':
                f.seek(-2, os.SEEK_CUR)

        except OSError:
            # catch OSError in case of a one line file
            f.seek(0)

        # we have the last line
        lastLine = f.readline().decode()

    # split the line (Date, O, H, L, C) and get the first item (Date)
    return lastLine.split(',')[0]


def cleanup(files_lst):
    for file in files_lst:
        os.remove(file)

    # remove outdated files
    deadline = today - timedelta(365)
    count = 0
    fmt = '%Y-%m-%d'

    with os.scandir(f'{DIR}/daily') as it:
        for entry in it:

            lastUpdated = datetime.strptime(getLastDate(entry.path), fmt)
            dlvry_file = f'{DIR}/delivery/{entry.name}'

            if lastUpdated < deadline:
                os.remove(entry.path)

                if os.path.isfile(dlvry_file):
                    os.remove(dlvry_file)

                count += 1

    print(f'{count} files deleted')
