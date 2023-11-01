import json
import pandas as pd
import string
import random
from datetime import datetime
from pathlib import Path
from tkinter import Tk
from typing import Any


class DateEncoder(json.JSONEncoder):

    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def loadJson(fPath: Path):
    return json.loads(fPath.read_bytes())


def writeJson(fPath: Path, data):
    fPath.write_text(json.dumps(data, indent=3, cls=DateEncoder))


def randomChar(length):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))


def getDataFrame(fpath: Path,
                 tf: str,
                 period: int,
                 column=None,
                 customDict=None,
                 fromDate=None) -> Any:
    df = pd.read_csv(fpath,
                     index_col='Date',
                     parse_dates=True,
                     na_filter=True)

    if fromDate:
        df = df[:fromDate]

    if customDict:
        dct = customDict
    else:
        dct = {
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


def getDeliveryLevels(df, config):
    # Average of traded volume
    avgTrdQty = df['QTY_PER_TRADE'].rolling(config.DLV_AVG_LEN).mean().round(2)

    # Average of delivery
    avgDlvQty = df['DLV_QTY'].rolling(config.DLV_AVG_LEN).mean().round(2)

    # above average delivery days
    df['DQ'] = df['DLV_QTY'] / avgDlvQty

    # above average Traded volume days
    df['TQ'] = df['QTY_PER_TRADE'] / avgTrdQty

    # get combination of above average traded volume and delivery days
    df['IM_F'] = (df['TQ'] > 1.2) & (df['DQ'] > 1.2)

    # see https://github.com/matplotlib/mplfinance/blob/master/examples/marketcolor_overrides.ipynb
    df['MCOverrides'] = None
    df['IM'] = float('nan')

    for idx in df.index:
        dq, im = df.loc[idx, ['DQ', 'IM_F']]

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


def relativeStrength(close, index_close):
    return (close / index_close * 100).round(2)


def manfieldRelativeStrength(close, index_close, period):
    rs = relativeStrength(close, index_close)

    sma_rs = rs.rolling(period).mean()
    return ((rs / sma_rs - 1) * 100).round(2)
