import argparse
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from defs.utils import getDataFrame

# ---- CONFIG ----
DIR = Path(__file__).parent
INDEX_DATA_DIR = DIR / "eod2_data/daily"
INDICATOR_FILE = DIR / "eod2_data/market_tracker.csv"

INDICATOR_MAP = {
    "sma": (("PCT_50", "PCT_200"), "% Stocks above 50 & 200 SMA"),
    "50": ("PCT_50", "% Stocks above 50"),
    "200": ("PCT_200", "% Stocks above 200"),
    "nethighs": ("NET_NEW_HIGHS", "Net 52 Week highs (Cumulative)"),
    "adline": ("AD_LINE", "Advance decline line"),
    "osc": ("MCCLELLAN_OSC", "McClellan Oscillator (Ratio adjusted)"),
}


# ---- ARGPARSE ----
def parse_args():
    parser = argparse.ArgumentParser(description="Plot Index with Breadth Indicator")

    parser.add_argument(
        "-i", "--index", default="nifty 50", help="Index name (default: nifty 50)"
    )

    parser.add_argument(
        "-ind", required=True, choices=INDICATOR_MAP.keys(), help="Indicator to plot"
    )

    parser.add_argument(
        "--tf", default="D", choices=("D", "W"), help="Timeframe: D (daily), W (weekly)"
    )

    parser.add_argument(
        "--period",
        action="store",
        type=int,
        metavar="int",
        default=160,
        help="Number of Candles to plot. Default 160",
    )

    # parser.add_argument("--file", required=True, help="Path to breadth CSV file")

    return parser.parse_args()


def parse_tf(tf):
    return "Daily" if tf == "D" else "Weekly"


# ---- RESAMPLE ----
def resample_df(df, tf):
    if tf == "D":
        return df.resample("W").last().dropna().reset_index()
    return df


# ---- MAIN ----
def main():
    args = parse_args()

    indicator_info, ind_title = INDICATOR_MAP[args.ind]

    # Load data
    index_df = getDataFrame(
        INDEX_DATA_DIR / f"{args.index}.csv",
        period=args.period,
        columns=["Date", "Close"],
    )

    ind_df = getDataFrame(
        INDICATOR_FILE,
        period=args.period,
        columns=[
            "Date",
            "PCT_50",
            "PCT_200",
            "NET_NEW_HIGHS",
            "AD_LINE",
            "MCCLELLAN_OSC",
        ],
    )

    # Merge
    df = pd.merge(index_df, ind_df, on="Date", how="inner")

    # Resample if needed
    if args.tf != "D":
        df = resample_df(df, args.tf)

    # ---- PLOT ----
    if args.ind == "osc":
        # ===== 2-PANEL LAYOUT =====
        fig, (ax1, ax2) = plt.subplots(
            2,
            1,
            figsize=(12, 6),
            sharex=True,
            gridspec_kw={"height_ratios": [7, 3]},
            constrained_layout=True,
        )

        # Bottom: McClellan Oscillator
        ax2.plot(df.index, df[indicator_info], color="red", label=indicator_info)
        ax2.set_ylabel(indicator_info, color="red")
        ax2.grid(True)

        # Zero line
        ax2.axhline(0, color="black", linewidth=1, linestyle="--")

        # Optional fill
        ax2.fill_between(
            df.index,
            df[indicator_info],
            0,
            where=df[indicator_info] >= 0,
            color="green",
            alpha=0.3,
        )
        ax2.fill_between(
            df.index,
            df[indicator_info],
            0,
            where=df[indicator_info] < 0,
            color="red",
            alpha=0.3,
        )

    else:
        fig, ax1 = plt.subplots(figsize=(12, 6), constrained_layout=True)

        ax2 = ax1.twinx()

        if args.ind == "sma":
            col_50, col_200 = indicator_info
            ax2.plot(df.index, df[col_50], color="green", label="% > 50 SMA")
            ax2.plot(df.index, df[col_200], color="red", label="% > 200 SMA")
            ax2.set_ylabel("Breadth (%)")
            ax2.legend()
        else:
            ax2.plot(df.index, df[indicator_info], color="red", label=indicator_info)
            ax2.set_ylabel(indicator_info, color="red")

    ax1.plot(df.index, df.Close, color="blue", label=args.index)
    ax1.set_ylabel("Index Price", color="blue")
    ax1.set_title(f"{args.index.upper()} vs {ind_title} - {parse_tf(args.tf)}")
    ax1.grid(True)

    plt.show()


if __name__ == "__main__":
    main()
