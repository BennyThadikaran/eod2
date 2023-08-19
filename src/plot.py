from defs.Plotter import Plotter, processPlot
from defs.utils import getChar, loadJson, writeJson
from defs.Config import Config
from argparse import ArgumentParser
from datetime import datetime
from os import system
from sys import platform

config = Config()

parser = ArgumentParser(prog='plot.py')

group = parser.add_mutually_exclusive_group(required=True)

group.add_argument('--sym',
                   nargs='+',
                   metavar='SYM',
                   help='Space separated list of stock symbols.')

group.add_argument('--watch',
                   metavar='NAME',
                   help='load a watchlist file by NAME.')

group.add_argument('--watch-add',
                   nargs=2,
                   metavar=('NAME', 'FILENAME'),
                   help='Save a watchlist by NAME and FILENAME')

group.add_argument('--watch-rm',
                   metavar='NAME',
                   help='Remove a watchlist by NAME and FILENAME')

group.add_argument('--preset',
                   help='Load command line options saved by NAME.',
                   metavar='NAME')

parser.add_argument('--preset-save',
                    action='store',
                    metavar='str',
                    help='Save command line options by NAME.')

group.add_argument('--preset-rm',
                   action='store',
                   metavar='str',
                   help='Remove preset by NAME.')

group.add_argument('--ls',
                   action='store_true',
                   help='List available presets and watchlists.')

parser.add_argument('-s',
                    '--save',
                    action='store_true',
                    help='Save chart as png.')


parser.add_argument('-v',
                    '--volume',
                    action='store_true',
                    help='Add Volume')

parser.add_argument('--rs',
                    action='store_true',
                    help='Dorsey Relative strength indicator.')

parser.add_argument('--m-rs',
                    action='store_true',
                    help='Mansfield Relative strength indicator.')

parser.add_argument('--tf',
                    action='store',
                    choices=('weekly', 'daily'),
                    default='daily',
                    help="Timeframe. Default 'daily'")

parser.add_argument('--sma',
                    type=int,
                    nargs='+',
                    metavar='int',
                    help='Simple Moving average')

parser.add_argument('--ema',
                    type=int,
                    nargs='+',
                    metavar='int',
                    help='Exponential Moving average')

parser.add_argument('-d',
                    '--date',
                    type=datetime.fromisoformat,
                    metavar='str',
                    help='ISO format date YYYY-MM-DD.')

parser.add_argument('--period',
                    action='store',
                    type=int,
                    metavar='int',
                    help=f'Number of Candles to plot. Default {config.PLOT_DAYS}')

parser.add_argument('--snr',
                    action='store_true',
                    help='Add Support and Resistance lines on chart')

parser.add_argument('-r',
                    '--resume',
                    action='store_true',
                    help='Resume a watchlist from last viewed chart.')

parser.add_argument('--dlv',
                    action='store_true',
                    help='Delivery Mode. Plot delivery data on chart.')

args = parser.parse_args()

plotter = Plotter(args, config, parser)

symList = plotter.symList

if args.preset:
    args = plotter.args

if len(symList) < 5 or args.save:
    if args.save:
        from concurrent.futures import ProcessPoolExecutor

        with ProcessPoolExecutor() as executor:
            for sym in symList:
                executor.submit(processPlot,
                                plotter.plot(sym),
                                plotter.plot_args)
        exit('Done')

    for sym in symList:
        plotter.plot(sym)
    exit('Done')

# PROMPT BETWEEN EACH CHART
sym_idx = 0
sym_len = len(symList)
answer = 'n'

if args.resume and hasattr(config, 'PLOT_RESUME'):
    resume = getattr(config, 'PLOT_RESUME')

    if resume['watch'] == args.watch:
        sym_idx = resume['idx']

WHITE = '\033[1;37m'
ENDC = '\033[0m'

# Check if system is windows or linux
if 'win' in platform:
    # enable color support in Windows
    system('color')

print(f'{WHITE}n: Next, p: Previous, q: Quit, c: Current Chart{ENDC}')

while True:
    if answer in ('n', 'p', 'c'):
        if sym_idx == sym_len:
            break

        print(f'{sym_idx + 1} of {sym_len}', flush=True, end='\r' * 11)

        plotter.plot(symList[sym_idx])

    answer = getChar()

    if answer == 'n':
        if sym_idx == sym_len:
            exit('\nDone')
        sym_idx += 1

    elif answer == 'p':
        if sym_idx == 0:
            print('\nAt first Chart')
            continue
        sym_idx -= 1
    elif answer == 'q':
        if args.watch:
            if plotter.configPath.is_file():
                userObj = loadJson(plotter.configPath)
            else:
                userObj = {}

            userObj['PLOT_RESUME'] = {
                'watch': args.watch,
                'idx': sym_idx
            }
            writeJson(plotter.configPath, userObj)
        exit('\nquiting')

print("Done")
