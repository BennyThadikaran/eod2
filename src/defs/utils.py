from json import JSONEncoder, loads, dumps
from datetime import datetime
from pandas import read_csv
from pathlib import Path
from tkinter import Tk


DIR = Path(__file__).parent.parent
daily_folder = DIR / 'eod2_data' / 'daily'
delivery_folder = DIR / 'eod2_data' / 'delivery'
save_folder = DIR / 'SAVED_CHARTS'


class DateEncoder(JSONEncoder):

    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def loadJson(fPath):
    return loads(fPath.read_bytes())


def writeJson(fPath, data):
    return fPath.write_text(dumps(data, indent=3, cls=DateEncoder))


def getChar():
    """Return a single character from stdin."""

    # figure out which function to use once, and store it in _func
    if "_func" not in getChar.__dict__:
        try:
            # for Windows-based systems
            from msvcrt import getch  # If successful, we are on Windows
            getChar._func = getch

        except ImportError:
            # for POSIX-based systems (with termios & tty support)
            from tty import setcbreak
            from sys import stdin

            # raises ImportError if unsupported
            from termios import tcgetattr, tcsetattr, TCSADRAIN

            def _ttyRead():
                fd = stdin.fileno()
                oldSettings = tcgetattr(fd)

                try:
                    # disable line buffering and read the first char
                    setcbreak(fd)
                    answer = stdin.read(1)
                finally:
                    # reset changes
                    tcsetattr(fd, TCSADRAIN, oldSettings)

                return answer

            getChar._func = _ttyRead

    return getChar._func()


def getDataFrame(fpath, tf, period, column=None, customDict=None, fromDate=None):
    df = read_csv(fpath,
                  index_col='Date',
                  parse_dates=True,
                  na_filter=True)

    if fromDate:
        df = df[:fromDate]

    dct = customDict if customDict else {
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }

    if tf == 'weekly':
        if column:
            return df[column].resample('W').apply(dct[column])[-period:]

        return df.resample('W').apply(dct)[-period:]

    return df[-period:] if column is None else df[column][-period:]


def arg_parse_dict(dct):
    lst = []
    for arg, val in dct.items():
        arg = arg.replace("_", "-")
        if val is None or val == False:
            continue

        if type(val) == list:
            lst.append(f'--{arg}')
            lst.extend(map(str, val))
        elif val == True:
            lst.append(f'--{arg}')
        else:
            lst.extend((f'--{arg}', str(val)))

    return lst


def getDeliveryLevels(df, dlv_df, config):
    if dlv_df is None:
        return (None,) * df.shape[0]

    # Average of traded volume
    avgTrdQty = dlv_df['QTY_PER_TRADE'].rolling(
        config.DLV_AVG_LEN).mean().round(2)

    # Average of delivery
    avgDlvQty = dlv_df['DELIV_QTY'].rolling(config.DLV_AVG_LEN).mean().round(2)

    # above average delivery days
    dlv_df['DQ'] = dlv_df['DELIV_QTY'] / avgDlvQty

    # above average Traded volume days
    dlv_df['TQ'] = dlv_df['QTY_PER_TRADE'] / avgTrdQty

    # get combination of above average traded volume and delivery days
    dlv_df['IM'] = (dlv_df['TQ'] > 1.2) & (dlv_df['DQ'] > 1.2)

    # see https://github.com/matplotlib/mplfinance/blob/master/examples/marketcolor_overrides.ipynb
    df['MCOverrides'] = None
    df['IM'] = float('nan')

    dlv_df = dlv_df.loc[df.index[0].date():]

    for idx in dlv_df.index:
        dq, im = dlv_df.loc[idx, ['DQ', 'IM']]

        if im:
            df.loc[idx, 'IM'] = df.loc[idx, 'Low'] * 0.99

        if dq >= config.DLV_L3:
            df.loc[idx, 'MCOverrides'] = config.PLOT_DLV_L1_COLOR
        elif dq >= config.DLV_L2:
            df.loc[idx, 'MCOverrides'] = config.PLOT_DLV_L2_COLOR
        elif dq > config.DLV_L1:
            df.loc[idx, 'MCOverrides'] = config.PLOT_DLV_L3_COLOR
        else:
            df.loc[idx, 'MCOverrides'] = config.PLOT_DLV_DEFAULT_COLOR


def isFarFromLevel(level: float, levels: list, mean_candle_size: float):
    '''Returns true if difference between the level and any of the price levels
    is greater than the mean_candle_size.'''
    # Detection of price support and resistance levels in Python -Gianluca Malato
    # source: https://towardsdatascience.com/detection-of-price-support-and-resistance-levels-in-python-baedc44c34c9
    return sum([abs(level - x[1]) < mean_candle_size for x in levels]) == 0


def getLevels(df, mean_candle_size: float):
    '''get support and resistance levels'''

    levels = []

    # filter for rejection from top
    # 2 succesive highs followed by 2 succesive lower highs
    local_max = df['High'][
        (df['High'].shift(1) < df['High']) &
        (df['High'].shift(2) < df['High'].shift(1)) &
        (df['High'].shift(-1) < df['High']) &
        (df['High'].shift(-2) < df['High'].shift(-1))
    ].dropna()

    # filter for rejection from bottom
    # 2 succesive highs followed by 2 succesive lower highs
    local_min = df['Low'][
        (df['Low'].shift(1) > df['Low']) &
        (df['Low'].shift(2) > df['Low'].shift(1)) &
        (df['Low'].shift(-1) > df['Low']) &
        (df['Low'].shift(-2) > df['Low'].shift(-1))
    ].dropna()

    for idx in local_max.index:
        level = local_max[idx]

        # Prevent clustering of support and resistance lines
        # Only add a level if it at a distance from any other price lines
        if isFarFromLevel(level, levels, mean_candle_size):
            levels.append((idx, level))

    for idx in local_min.index:
        level = local_min[idx]

        if isFarFromLevel(level, levels, mean_candle_size):
            levels.append((idx, level))

    alines = []
    lastDt = df.index[-1]

    for dt, price in levels:
        # a tuple containing start and end point coordinates for a horizontal line
        # Each tuple is composed of date and price.
        seq = [(dt, price), (lastDt, price)]
        alines.append(seq)

    return alines


def getScreenSize():
    root = Tk()
    root.withdraw()
    mm = 25.4

    width, height = root.winfo_screenmmwidth(), root.winfo_screenmmheight()

    return (round(width / mm), round(height / mm))
