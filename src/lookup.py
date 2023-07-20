from pandas import read_csv
from pathlib import Path
from sys import argv
from defs.Config import Config

if len(argv) == 1:
    exit('Pass a scrip name')

config = Config()

DIR = Path(__file__).parent

lookup_days = int(argv[2]) if len(argv) == 3 else config.LOOKUP_DAYS
symbol = argv[1]

fpath = DIR / 'eod2_data' / 'delivery' / f'{symbol}.csv'

if not fpath.exists():
    exit(f'{symbol}: File not found.')

df = read_csv(fpath, index_col='Date')

df['AVG_TRD_QTY'] = df['QTY_PER_TRADE'].rolling(
    window=config.LOOKUP_AVG_DAYS).mean().round(2)

df['AVG_DLV_QTY'] = df['DELIV_QTY'].rolling(
    window=config.LOOKUP_AVG_DAYS).mean().round(2)

df['DQ'] = (df['DELIV_QTY'] / df['AVG_DLV_QTY']).round(2)
df['TQ'] = (df['QTY_PER_TRADE'] / df['AVG_TRD_QTY']).round(2)

df['JP'] = True
df['JP'] = df['JP'].where((df['QTY_PER_TRADE'] > df['AVG_TRD_QTY']) & (
    df['DELIV_QTY'] > df['AVG_DLV_QTY']), '')

print(df[-lookup_days:][['DQ', 'TQ', 'JP']])
