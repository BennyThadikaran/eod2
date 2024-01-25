from argparse import ArgumentParser
from ta.momentum import RSIIndicator
from mplfinance import make_addplot
from pandas import Series

# To be added to src/defs/user.json
# "PLOT_PLUGINS": {
#     "RSI": {
#       "name": "rsi",
#       "overbought": 80,
#       "oversold": 20,
#       "line_color": "teal"
#     }
# }


def load(parser: ArgumentParser):
    parser.add_argument(
        "--rsi", action="store_true", help="Relative strength index"
    )


def main(df, plot_args, args, config):
    if args.rsi:
        opts = config.PLOT_PLUGINS["RSI"]

        df["RSI"] = RSIIndicator(close=df["Close"]).rsi()

        if not "addplot" in plot_args:
            plot_args["addplot"] = []

        OB_LINE = Series(data=opts["overbought"], index=df.index)
        OS_LINE = Series(data=opts["oversold"], index=df.index)

        plot_args["addplot"].extend(
            [
                make_addplot(
                    df["RSI"],
                    label="RSI",
                    panel="lower",
                    color=opts["line_color"],
                    ylabel="RSI",
                    width=2,
                ),
                make_addplot(
                    OB_LINE,
                    panel="lower",
                    color=opts["line_color"],
                    linestyle="dashed",
                    width=1.5,
                ),
                make_addplot(
                    OS_LINE,
                    panel="lower",
                    color=opts["line_color"],
                    linestyle="dashed",
                    width=1.5,
                ),
            ]
        )
