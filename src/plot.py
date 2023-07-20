from pandas import read_csv
from sys import argv
import mplfinance as mpf
from pathlib import Path
from defs.Config import Config


def getDeliveryLevels(dq):
    if dq is None:
        return (None,) * config.PLOT_DAYS

    # Average of traded volume
    avgTrdQty = dq['QTY_PER_TRADE'].rolling(
        config.PLOT_AVG_DAYS).mean().round(2)

    # Average of delivery
    avgDlvQty = dq['DELIV_QTY'].rolling(config.PLOT_AVG_DAYS).mean().round(2)

    # above average delivery days
    dq['DQ'] = dq['DELIV_QTY'] > avgDlvQty

    # above average Traded volume days
    dq['TQ'] = dq['QTY_PER_TRADE'] > avgTrdQty

    # get combination of above average traded volume and delivery days
    dq['JP'] = (dq['QTY_PER_TRADE'] > avgTrdQty) & (
        dq['DELIV_QTY'] > avgDlvQty)

    dq = dq[dq['JP'] == True][['JP']]

    # see https://github.com/matplotlib/mplfinance/blob/master/examples/marketcolor_overrides.ipynb
    df['MCOverrides'] = None

    for idx in dq.index:
        df.loc[idx, 'MCOverrides'] = 'midnightblue'

    mco = df['MCOverrides'].values
    return mco


# Detection of price support and resistance levels in Python
# -- Gianluca Malato
# https://towardsdatascience.com/detection-of-price-support-and-resistance-levels-in-python-baedc44c34c9
def isFarFromLevel(level):
    return sum([abs(level - x[1]) < mean_candle_size for x in levels]) == 0


def getLevels():
    # get support and resistance levels

    local_max = df['High'][
        (df['High'].shift(1) < df['High']) &
        (df['High'].shift(2) < df['High'].shift(1)) &
        (df['High'].shift(-1) < df['High']) &
        (df['High'].shift(-2) < df['High'].shift(-1))
    ].dropna()

    local_min = df['Low'][
        (df['Low'].shift(1) > df['Low']) &
        (df['Low'].shift(2) > df['Low'].shift(1)) &
        (df['Low'].shift(-1) > df['Low']) &
        (df['Low'].shift(-2) > df['Low'].shift(-1))
    ].dropna()

    for idx in local_max.index:
        level = local_max[idx]

        if isFarFromLevel(level):
            levels.append((idx, level))

    for idx in local_min.index:
        level = local_min[idx]

        if isFarFromLevel(level):
            levels.append((idx, level))

    alines = []
    lastDt = df.index[-1]

    for level in levels:
        seq = [(level[0], level[1]), (lastDt, level[1])]
        alines.append(seq)

    return alines


config = Config()
DIR = Path(__file__).parent
argv_len = len(argv)

if argv_len == 1:
    exit('Usage:\npython3 plot.py <symbol>')

if hasattr(config, argv[1].upper()):
    fileName = getattr(config, argv[1].upper())
    watch = config.toList(fileName)
else:
    watch = argv[1:]

for symbol in watch:
    symbol = symbol.lower()
    delivery_path = DIR / 'eod2_data' / 'delivery' / f'{symbol}.csv'
    daily_path = DIR / 'eod2_data' / 'daily' / f'{symbol}.csv'

    if not daily_path.exists():
        exit(f'No such file in daily folder: {symbol}.csv')

    if delivery_path.exists():
        dq = read_csv(delivery_path,
                      index_col='Date',
                      parse_dates=True,
                      na_filter=True)[-config.PLOT_DAYS:]
    else:
        print('No delivery data found')
        dq = None

    df = read_csv(
        daily_path,
        index_col='Date',
        parse_dates=True,
        na_filter=False,
    )[-config.PLOT_DAYS:]

    levels = []
    mean_candle_size = (df['High'] - df['Low']).mean()

    # Coloring Individual Candlesticks
    # https://github.com/matplotlib/mplfinance/blob/master/examples/marketcolor_overrides.ipynb
    mco = getDeliveryLevels(dq)

    alines = getLevels()

    mpf.plot(df,
             type='candle',
             title=symbol.upper(),
             alines={
                 'alines': alines,
                 'linewidths': 0.7
             },
             style='yahoo',
             marketcolor_overrides=mco)
