from pandas import read_csv
from pathlib import Path
from sys import argv

if len(argv) == 1:
    exit('Pass a scrip name')

DIR = Path(__file__).parent

avg_days = 60
lookup_days = int(argv[2]) if len(argv) == 3 else 15

fpath = DIR / 'delivery' / f'{argv[1]}.csv'

try:
    df = read_csv(fpath, index_col='Date')
except FileNotFoundError as e:
    exit(f'{argv[1]}: {e!r}')

df['AVG_TRD_QTY'] = df['QTY_PER_TRADE'].rolling(window=avg_days).mean().round(2)

df['AVG_DLV_QTY'] = df['DELIV_QTY'].rolling(window=avg_days).mean().round(2)

df['DQ'] = (df['DELIV_QTY'] / df['AVG_DLV_QTY']).round(2)
df['TQ'] = (df['QTY_PER_TRADE'] / df['AVG_TRD_QTY']).round(2)

df['JP'] = True
df['JP'] = df['JP'].where((df['QTY_PER_TRADE'] > df['AVG_TRD_QTY']) & (df['DELIV_QTY'] > df['AVG_DLV_QTY']), '')

print(df[-lookup_days:][['DQ', 'TQ', 'JP']])
