from argparse import ArgumentParser
from defs.Config import Config
from defs.utils import writeJson, loadJson
from pathlib import Path
from sys import platform
from os import system
from pandas import read_csv


# Shell colors
class c:
    HEADER = "\033[95m"
    WHITE = "\033[1;37m"
    YELLOW = "\033[1;32m"
    PURPLE = "\033[1;35m"
    BLUE = "\033[94m"
    CYAN = "\033[0;96m"
    GREEN = "\033[1;92m"
    ORANGE = "\033[1;93m"
    RED = "\033[1;91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[1;4m"

    @staticmethod
    def num(nu):
        if nu >= config.DLV_L3:
            return f"{c.WHITE}{nu}{c.ENDC}"
        if nu >= config.DLV_L2:
            return f"{c.ORANGE}{nu}{c.ENDC}"
        if nu > config.DLV_L1:
            return f"{c.RED}{nu}{c.ENDC}"
        return f"{c.CYAN}{nu}{c.ENDC}"


def lookup(sym):
    fpath = DIR / "eod2_data" / "daily" / f"{sym}.csv"

    if not fpath.exists():
        exit(f"{sym}: File not found.")

    df = read_csv(fpath, index_col="Date", parse_dates=True)

    df["AVG_TRD_QTY"] = (
        df["QTY_PER_TRADE"].rolling(config.DGET_AVG_DAYS).mean().round(2)
    )

    df["AVG_DLV_QTY"] = (
        df["DLV_QTY"].rolling(config.DGET_AVG_DAYS).mean().round(2)
    )

    df["AVG_VOL"] = df["Volume"].rolling(config.DGET_AVG_DAYS).mean().round(2)

    df["DQ"] = (df["DLV_QTY"] / df["AVG_DLV_QTY"]).round(2)
    df["TQ"] = (df["QTY_PER_TRADE"] / df["AVG_TRD_QTY"]).round(2)
    df["VOL"] = (df["Volume"] / df["AVG_VOL"]).round(2)

    df["IM"] = True
    df["IM"] = df["IM"].where(
        (df["QTY_PER_TRADE"] > df["AVG_TRD_QTY"])
        & (df["DLV_QTY"] > df["AVG_DLV_QTY"]),
        "",
    )

    df["DQ"] = df["DQ"].apply(c.num)
    df["TQ"] = df["TQ"].apply(c.num)
    df["IM"] = df["IM"].apply(
        lambda v: f'{c.ORANGE}{"$$" if v else "-"}{c.ENDC}'
    )
    df["VOL"] = df["VOL"].apply(c.num)

    df = df[-config.DGET_DAYS :][["DQ", "TQ", "IM", "VOL"]]

    print(
        f"""{c.WHITE}Units represent average multiples. 1x 2x etc. < 1: below average.
DQ: Delivery qty  TQ: Qty per trade  IM: Institutional Money [Above average DQ and TQ]{c.ENDC}\n"""
    )
    print(
        f'{c.WHITE}DATE{" " * 10}DQ{" " * 5}TQ{" " * 5}VOL{" " * 4}IM{c.ENDC}'
    )

    for Index, DQ, TQ, IM, VOL in df[::-1].itertuples():
        print(
            f'{c.CYAN}{Index.strftime("%d %b %Y").ljust(13)}{c.ENDC}',
            DQ.ljust(17).ljust(17),
            TQ.ljust(17),
            VOL.ljust(17),
            IM,
        )
    exit()


parser = ArgumentParser(prog="dget.py")

group = parser.add_mutually_exclusive_group(required=True)

group.add_argument(
    "--sym",
    nargs="+",
    metavar="SYM",
    help="Space separated list of stock symbols",
)

group.add_argument(
    "--watch", metavar="NAME", help="load a watchlist file by NAME."
)

group.add_argument(
    "--watch-add",
    nargs=2,
    metavar=("NAME", "FILENAME"),
    help="Add a watchlist by NAME and FILENAME",
)

group.add_argument(
    "--watch-rm", metavar="NAME", help="Remove a watchlist by NAME"
)

group.add_argument(
    "--ls", action="store_true", help="List available watchlists."
)

group.add_argument("-l", "--lookup", metavar="SYM", help="Symbol to lookup")

args = parser.parse_args()

config = Config()

DIR = Path(__file__).parent
configPath = DIR / "defs" / "user.json"
DAILY = DIR / "eod2_data" / "daily"

# Check if system is windows or linux
if "win" in platform:
    # enable color support in Windows
    system("color")

if args.watch_add:
    name, fName = args.watch_add

    data = loadJson(configPath) if configPath.is_file() else {}

    if not "WATCH" in data:
        data["WATCH"] = {}

    data["WATCH"][name.upper()] = fName
    writeJson(configPath, data)
    exit(f"Added watchlist '{name}' with value '{fName}'")

if args.watch_rm:
    if not args.watch_rm.upper() in getattr(config, "WATCH"):
        exit(f"Error: No watchlist named: '{args.watch_rm}'")

    if not configPath.is_file():
        exit(f"No config file")

    data = loadJson(configPath)

    del data["WATCH"][args.watch_rm.upper()]

    writeJson(configPath, data)
    exit(f"Watchlist '{args.watch_rm}' removed.")

if args.ls:
    if not len(config.WATCH):
        exit("Nothing to list")

    lst = [i.lower() for i in config.WATCH.keys()]
    exit(f'Watchlists: {",".join(lst)}')

if args.watch:
    if not args.watch.upper() in config.WATCH:
        exit(f"Error: No watchlist named '{args.watch}'")

    file = DIR / "data" / config.WATCH[args.watch.upper()]

    if not file.is_file():
        exit(f"Error: File not found {file}")

    symList = file.read_text().strip("\n").split("\n")
else:
    symList = args.sym


if args.lookup:
    lookup(args.lookup)
else:
    watch_name = args.watch.upper() if args.watch else "DEFAULT"

    heading = f"{c.WHITE}>= {config.DLV_L3}{c.ENDC}  {c.ORANGE}>= {config.DLV_L2}{c.ENDC}  {c.RED}>= {config.DLV_L1}{c.ENDC}\n\n"

    heading += f"{c.WHITE}{watch_name}{c.ENDC}\n"

    # Heading text
    heading += (
        f'{c.WHITE}SCRIP{" " * 8}DQ{" " * 9}TQ{" " * 9}VOL{" " * 5}IM{c.ENDC}\n'
    )

    txt = ""

    for sym in symList:
        fpath = DAILY / f"{sym.lower()}.csv"

        if not fpath.exists():
            print(f"Error: File not found: {fpath.name}")
            continue

        # Create Dataframe of last 30 days
        df = read_csv(fpath, index_col="Date", parse_dates=True)[
            -config.DLV_AVG_LEN :
        ]

        if df["DLV_QTY"].dropna().empty:
            print(f"No delivery data: {sym.upper()}")
            continue

        try:
            # generate average of last 30 days
            avgQty, avgDlvQty, avgVol = (
                df[["QTY_PER_TRADE", "DLV_QTY", "Volume"]]
                .mean(numeric_only=True)
                .round(2)
            )
        except ValueError:
            # New stocks may not have enough data to generate averages
            continue

        # Get the last value for each column
        tradeQty, dlvQty, volume = df.loc[
            df.index[-1], ["QTY_PER_TRADE", "DLV_QTY", "Volume"]
        ]

        tq = round(tradeQty / avgQty, 2)
        dq = round(dlvQty / avgDlvQty, 2)
        vol = round(volume / avgVol, 2)
        im = f'{c.ORANGE}{"$$" if dq > 1.2 and tq > 1.2 else "-"}{c.ENDC}'

        txt += "{} {} {} {} {}\n".format(
            c.CYAN + sym[:15].upper().ljust(12),
            c.num(dq).ljust(21),
            c.num(tq).ljust(21),
            c.num(vol).ljust(18),
            im,
        )

    if txt:
        print(heading + txt)
