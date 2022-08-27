from pandas import read_csv
from os import system
from os.path import dirname, realpath
from sys import argv, platform

if len(argv) == 1:
    #### EDIT YOUR WATCHLIST HERE ####
    watch = ["AMARAJABAT", "APLLTD", "AUROPHARMA", "DIXON", "GODREJCP", "GODREJIND", "HCLTECH", "INFY", "LATENTVIEW", "M&M", "MARKSANS", "MOL", "TATAPOWER", "TCS"]
    # DO NOT EDIT BELOW THIS LINE
else:
    watch = argv[1:]


# Check if system is windows or linux
if 'win' in platform:
    # enable color support in Windows
    system('color')


# Shell colors
class c:
    HEADER = '\033[95m'
    WHITE = '\033[1;37m'
    YELLOW = '\033[1;32m'
    PURPLE = '\033[1;35m'
    BLUE = '\033[94m'
    CYAN = '\033[0;96m'
    GREEN = '\033[1;92m'
    WARNING = '\033[1;93m'
    FAIL = '\033[1;91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[1;4m'

    def num(nu):
        if nu >= 1.5:
            return f'{c.WHITE}{nu}{c.ENDC}'
        if nu >= 1.2:
            return f'{c.WARNING}{nu}{c.ENDC}'
        return f'{c.FAIL if nu >= 1 else c.CYAN}{nu}{c.ENDC}'


# get the folder location
basePath = dirname(realpath(__file__))

# Helper text
txt = f'{c.WHITE}>= 1.5{c.ENDC}  {c.WARNING}>= 1.2{c.ENDC}  {c.FAIL}>= 1{c.ENDC}\n\n'

# Heading text
txt += f'{c.CYAN}SCRIP        QTY/TRD    DLV{c.ENDC}\n'

for i in watch:
    fpath = f'{basePath}/delivery/{i.lower()}.csv'

    # Create Dataframe of last 30 days
    try:
        df = read_csv(fpath, index_col='Date')[-90:]
    except FileNotFoundError as e:
        print(f'{i}: {e!r}')

    try:
        # generate average of last 30 days
        avgQty, avgDlvQty = df[
            ['QTY_PER_TRADE', 'DELIV_QTY']
        ].mean(numeric_only=True).round(2)
    except ValueError:
        # New stocks may not have enough data to generate averages
        continue

    # Get the last value for each column
    tradeQty, dlvQty = df.loc[
        df.index[-1],
        ['QTY_PER_TRADE', 'DELIV_QTY']
    ]

    qty_per_trade = round(tradeQty / avgQty, 2)
    dlv_qty = round(dlvQty / avgDlvQty, 2)

    txt += '{} {} {}\n'.format(
        c.CYAN + i[:8].upper().ljust(12),
        c.num(qty_per_trade).ljust(21),
        c.num(dlv_qty).ljust(21),
    )

print(txt)
