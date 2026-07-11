from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from .dtypes import BreadthIndicator, BreadthOption
from .util import debounce, setup_xaxis

BREADTH_INDICATORS = {
    "sma": BreadthIndicator(
        columns=["PCT_50", "PCT_200", "Close"],
        title="% Stocks above 50 & 200 SMA",
    ),
    "50": BreadthIndicator(
        columns=["PCT_50", "Close"],
        title="% Stocks above 50 SMA",
    ),
    "200": BreadthIndicator(
        columns=["PCT_200", "Close"],
        title="% Stocks above 200 SMA",
    ),
    "nethighs": BreadthIndicator(
        columns=["NET_NEW_HIGHS", "Close"],
        title="Net 52-Week Highs (Cumulative)",
    ),
    "adline": BreadthIndicator(
        columns=["AD_LINE", "Close"],
        title="Advance-Decline Line",
    ),
    "osc": BreadthIndicator(
        columns=["MCCLELLAN_OSC", "Close"],
        title="McClellan Oscillator (Ratio Adjusted)",
    ),
}


class BreadthRenderer:
    """Renders market breadth line charts."""

    def __init__(self, index_name: str, timeframe: str) -> None:
        self.index_name = index_name
        self.timeframe = timeframe

    def render(
        self,
        df: pd.DataFrame,
        plot_args: dict[str, Any],
        symbol: str | BreadthOption,
    ) -> tuple[Figure, list[Axes]]:
        """
        Render breadth line chart on the given axes.
        """
        x = range(len(df))

        if symbol == "osc":
            info = BREADTH_INDICATORS[symbol]

            col_name = info.columns[0]

            # ===== 2-PANEL LAYOUT =====
            fig, (ax1, ax2) = plt.subplots(
                2,
                1,
                **plot_args,
                sharex=True,
                gridspec_kw={"height_ratios": [7, 3]},
            )

            # Bottom: McClellan Oscillator
            ax2.plot(
                x,
                df[col_name],
                color="red",
                label=col_name,
            )
            ax2.set_ylabel(col_name, color="red")
            ax2.grid(True)

            # Zero line
            ax2.axhline(0, color="black", linewidth=1, linestyle="--")

            # Optional fill
            ax2.fill_between(
                x,
                df[col_name],
                0,
                where=df[col_name] >= 0,
                color="green",
                alpha=0.3,
            )
            ax2.fill_between(
                x,
                df[col_name],
                0,
                where=df[col_name] < 0,
                color="red",
                alpha=0.3,
            )

            ax1.format_coord = self._make_format_coords(df, symbol)
        else:
            # Purposeful naming of ax2, since ax2.twinx draws above ax1 - it is to be
            # considered the main_axes for drawings lines and text
            fig, ax2 = plt.subplots(**plot_args)

            ax1 = ax2.twinx()

            info = BREADTH_INDICATORS[symbol]

            if symbol == "sma":
                col_50, col_200, _ = info.columns
                ax2.plot(x, df[col_50], color="green", label="% > 50 SMA")
                ax2.plot(x, df[col_200], color="red", label="% > 200 SMA")
                ax2.set_ylabel("Breadth (%)")
                ax2.legend()
            else:
                col_name = info.columns[0]
                ax2.plot(x, df[col_name], color="red", label=col_name)
                ax2.set_ylabel(col_name, color="red")

            ax1.format_coord = self._make_format_coords(df, symbol)

        ax1.plot(x, df.Close, color="blue", label=self.index_name)
        ax1.set_ylabel("Index Price", color="blue")
        ax1.set_title(f"{info.title} vs {self.index_name.upper()} • {self.timeframe}")
        ax1.grid(True)

        # X-axis formatting
        setup_xaxis(ax1, df)

        return fig, [ax1, ax2]

    def _make_format_coords(self, df: pd.DataFrame, symbol):
        """Create a debounced format_coords function."""
        data = df.to_numpy()
        index = df.index
        n = len(df)
        separator = " " * 5

        close_idx = df.columns.get_loc("Close")

        breadth_config = {
            "sma": (("PCT_50", "PCT_200"), (">50MA", ">200MA")),
            "50": (("PCT_50",), (">50MA",)),
            "200": (("PCT_200",), (">200MA",)),
            "nethighs": (("NET_NEW_HIGHS",), ("NET_HIGHS",)),
            "adline": (("AD_LINE",), ("AD_LINE",)),
            "osc": (("MCCLELLAN_OSC",), ("MCCLELLAN_OSC",)),
        }

        columns, labels = breadth_config[symbol]

        column_indices = [df.columns.get_loc(col) for col in columns]

        @debounce(interval=0.025)
        def format_coords(x: float, y: float) -> str:
            i = round(x)

            if not 0 <= i < n:
                return ""

            row = data[i]

            parts = [
                f"{index[i]:%d %b %Y}".upper(),
                f"Index: {row[close_idx]:.2f}",
                f"{labels[0]}: {row[column_indices[0]]:.2f}",
            ]

            if len(column_indices) == 2:
                parts.append(f"{labels[1]}: {row[column_indices[1]]:.2f}")

            parts.append(f"Y: {y:.2f}")

            return separator.join(parts)

        return format_coords
