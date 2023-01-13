from pandas import read_csv
from sys import argv
import mplfinance as mpf
from pathlib import Path


def getDeliveryLevels(dq):
    if dq is None:
        return (None,) * plot_period

    # Average of traded volume
    avgTrdQty = dq['QTY_PER_TRADE'].rolling(avg_days).mean().round(2)

    # Average of delivery
    avgDlvQty = dq['DELIV_QTY'].rolling(avg_days).mean().round(2)

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


DIR = Path(__file__).parent
arg_length = len(argv)

if arg_length == 1:
    exit('Usage:\npython3 plot.py <symbol> [<int avg_days> <int plot_period>]')

avg_days = int(argv[2]) if arg_length == 3 else 60
plot_period = int(argv[3]) if arg_length == 4 else 180

fpath = DIR / 'delivery' / f'{argv[1]}.csv'

try:
    dq = read_csv(fpath,
                  index_col='Date',
                  parse_dates=True,
                  infer_datetime_format=True,
                  na_filter=True)[-plot_period:]

except FileNotFoundError:
    print('No delivery data found')
    dq = None

try:
    df = read_csv(
        f'{DIR}/daily/{argv[1]}.csv',
        index_col='Date',
        parse_dates=True,
        na_filter=False,
        infer_datetime_format=True)[-plot_period:]
except FileNotFoundError as e:
    exit(f'No such file in daily folder: {argv[1]}.csv')


levels = []
mean_candle_size = (df['High'] - df['Low']).mean()

# Coloring Individual Candlesticks
# https://github.com/matplotlib/mplfinance/blob/master/examples/marketcolor_overrides.ipynb
mco = getDeliveryLevels(dq)

alines = getLevels()

mpf.plot(df,
         type='candle',
         alines={
             'alines': alines,
             'linewidths': 0.6
         },
         style='yahoo',
         marketcolor_overrides=mco)
