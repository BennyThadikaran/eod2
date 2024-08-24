from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path

from defs.Config import Config
from defs.Plotter import Plotter, processPlot
from defs.Plugin import Plugin
from defs.utils import loadJson, writeJson

DIR = Path(__file__).parent
config = Config()
plugin = Plugin()

parser = ArgumentParser(prog="plot.py")

group = parser.add_mutually_exclusive_group(required=True)

group.add_argument(
    "--sym",
    nargs="+",
    metavar="SYM",
    help="Space separated list of stock symbols.",
)

group.add_argument(
    "--watch", metavar="NAME", help="load a watchlist file by NAME."
)

group.add_argument(
    "--watch-add",
    nargs=2,
    metavar=("NAME", "FILENAME"),
    help="Save a watchlist by NAME and FILENAME",
)

group.add_argument(
    "--watch-rm", metavar="NAME", help="Remove a watchlist by NAME and FILENAME"
)

group.add_argument(
    "--preset", help="Load command line options saved by NAME.", metavar="NAME"
)

parser.add_argument(
    "--preset-save",
    action="store",
    metavar="str",
    help="Save command line options by NAME.",
)

group.add_argument(
    "--preset-rm", action="store", metavar="str", help="Remove preset by NAME."
)

group.add_argument(
    "--ls", action="store_true", help="List available presets and watchlists."
)

parser.add_argument(
    "-s", "--save", action="store_true", help="Save chart as png."
)

parser.add_argument("-v", "--volume", action="store_true", help="Add Volume")

parser.add_argument(
    "--rs", action="store_true", help="Dorsey Relative strength indicator."
)

parser.add_argument(
    "--m-rs", action="store_true", help="Mansfield Relative strength indicator."
)

parser.add_argument(
    "--tf",
    action="store",
    choices=("weekly", "daily"),
    default="daily",
    help="Timeframe. Default 'daily'",
)

parser.add_argument(
    "--sma", type=int, nargs="+", metavar="int", help="Simple Moving average"
)

parser.add_argument(
    "--ema",
    type=int,
    nargs="+",
    metavar="int",
    help="Exponential Moving average",
)

parser.add_argument(
    "--vol-sma",
    type=int,
    nargs="+",
    metavar="int",
    help="Volume Moving average",
)

parser.add_argument(
    "-d",
    "--date",
    type=datetime.fromisoformat,
    metavar="str",
    help="ISO format date YYYY-MM-DD.",
)

parser.add_argument(
    "--period",
    action="store",
    type=int,
    metavar="int",
    help=f"Number of Candles to plot. Default {config.PLOT_DAYS}",
)

parser.add_argument(
    "--snr",
    action="store_true",
    help="Add Support and Resistance lines on chart",
)

parser.add_argument(
    "--snr-v2",
    action="store_true",
    help="Add Support and Resistance lines on chart",
)

parser.add_argument(
    "-r",
    "--resume",
    action="store_true",
    help="Resume a watchlist from last viewed chart.",
)

parser.add_argument(
    "--dlv",
    action="store_true",
    help="Delivery Mode. Plot delivery data on chart.",
)

if len(config.PLOT_PLUGINS):
    plugin.register(config.PLOT_PLUGINS, parser)

args = parser.parse_args()

if args.tf == "weekly" and args.dlv:
    exit("WARN: Delivery data not available on Weekly Timeframe")

plotter = Plotter(args, config, plugin, parser, DIR)

symList = plotter.symList

if args.preset:
    args = plotter.args

if args.save:
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor() as executor:
        for sym in symList:
            executor.submit(processPlot, plotter.plot(sym), plotter.plot_args)
    exit("Done")

# PROMPT BETWEEN EACH CHART
plotter.idx = 0
plotter.len = len(symList)
answer = "n"

if args.resume and hasattr(config, "PLOT_RESUME"):
    resume = getattr(config, "PLOT_RESUME")

    if resume["watch"] == args.watch:
        plotter.idx = resume["idx"]

while True:
    if answer in ("n", "p"):
        if plotter.idx == plotter.len:
            break

        print(f"{plotter.idx + 1} of {plotter.len}", flush=True, end="\r" * 11)

        plotter.plot(symList[plotter.idx])

    answer = plotter.key

    if answer == "n":
        if plotter.idx == plotter.len:
            exit("\nDone")
        plotter.idx += 1

    elif answer == "p":
        if plotter.idx == 0:
            print("\nAt first Chart")
            answer = ""
            continue
        plotter.idx -= 1
    elif answer == "q":
        if args.watch:
            if plotter.configPath.is_file():
                userObj = loadJson(plotter.configPath)
            else:
                userObj = {}

            userObj["PLOT_RESUME"] = {"watch": args.watch, "idx": plotter.idx}
            writeJson(plotter.configPath, userObj)
        exit("\nquiting")

print("\nDone")
