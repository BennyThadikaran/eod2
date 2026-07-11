from __future__ import annotations

from typing import Any

import mplfinance as mpf
import pandas as pd
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure

from defs.config import config
from renderer.dtypes import PanelAssignment

from .annotations import Drawing
from .util import debounce, setup_xaxis


class CandlestickRenderer:
    """Renders OHLC candlestick charts using mplfinance."""

    def __init__(
        self,
        panel_layout: dict[str, PanelAssignment] | None = None,
    ) -> None:
        self.panel_layout = panel_layout or dict()

    def render(
        self,
        df: pd.DataFrame,
        plot_args: dict[str, Any],
        symbol: str,
    ) -> tuple[Figure, list[Axes]]:

        added_plots = self._build_added_plots(df)

        if added_plots:
            if "addplot" in plot_args:
                plot_args["addplot"].extend(added_plots)
            else:
                plot_args["addplot"] = added_plots

        fig, axs = mpf.plot(df, **plot_args, returnfig=True)

        # Set up x-axis formatting
        setup_xaxis(axs[0], df)

        # Set format_coords
        format_fn = self._make_format_coords(df)
        for ax in axs:
            ax.format_coord = format_fn

        return fig, axs

    def _assignment(self, key: str) -> PanelAssignment:
        return self.panel_layout.get(
            key,
            PanelAssignment(panel=1, secondary_y=False),
        )

    def _build_added_plots(self, df: pd.DataFrame):
        """Build mplfinance addplot list from DataFrame indicators."""
        added_plots = []

        if "RS" in df.columns:
            assignment = self._assignment("rs")

            added_plots.append(
                mpf.make_addplot(
                    df["RS"],
                    panel=assignment.panel,
                    secondary_y=bool(assignment.secondary_y),
                    color=config.PLOT_RS_COLOR,
                    width=2.5,
                    ylabel="Dorsey RS",
                )
            )

        if "M_RS" in df.columns:
            assignment = self._assignment("m_rs")
            zero_line = pd.Series(data=0, index=df.index)

            added_plots.extend(
                [
                    mpf.make_addplot(
                        df["M_RS"],
                        panel=assignment.panel,
                        secondary_y=bool(assignment.secondary_y),
                        color=config.PLOT_M_RS_COLOR,
                        width=2.5,
                        ylabel="Mansfield RS",
                    ),
                    mpf.make_addplot(
                        zero_line,
                        panel=assignment.panel,
                        secondary_y=bool(assignment.secondary_y),
                        color=config.PLOT_M_RS_COLOR,
                        linestyle="dashed",
                        width=1.5,
                    ),
                ]
            )

        for col in df.columns:
            if col.startswith("SMA_"):
                period = col.replace("SMA_", "")
                added_plots.append(
                    mpf.make_addplot(df[col], label=f"SM{period}", secondary_y=False)
                )
            elif col.startswith("EMA_"):
                period = col.replace("EMA_", "")
                added_plots.append(
                    mpf.make_addplot(df[col], label=f"EM{period}", secondary_y=False)
                )
            elif col.startswith("VMA_"):
                period = col.replace("VMA_", "")
                assignment = self._assignment("vol_sma")

                added_plots.append(
                    mpf.make_addplot(
                        df[col],
                        label=f"MA{period}",
                        panel=assignment.panel,
                        secondary_y=bool(assignment.secondary_y),
                        linewidths=0.7,
                    )
                )

        if "IM" in df.columns:
            added_plots.append(
                mpf.make_addplot(
                    df["IM"],
                    type="scatter",
                    marker="*",
                    color="midnightblue",
                    label="IM",
                    secondary_y=False,
                )
            )

        return added_plots

    def overlay_drawings(
        self,
        ax: Axes,
        drawings: dict[str, Drawing],
        df: pd.DataFrame,
    ) -> list[Artist]:
        """Overlay all drawings on the chart."""
        artists = []

        if df.empty:
            return artists

        index_start = df.index[0]
        index_end = df.index[-1]

        visible_low = df["Low"].min()
        visible_high = df["High"].max()

        def x_to_index_if_visible(x) -> int | None:
            x = pd.Timestamp(x)

            if not index_start <= x <= index_end:
                return None

            x = df.index.get_loc(x)

            return x if isinstance(x, int) else None

        def price_in_visible_range(y) -> bool:
            return visible_low <= y <= visible_high

        for url, drawing in drawings.items():
            if drawing.kind == "axhline":
                _, y = drawing.points[0]

                if not price_in_visible_range(y):
                    continue

                artists.append(
                    ax.axhline(
                        y,
                        color=drawing.color,
                        url=url,
                        linewidth=1,
                        pickradius=3,
                        picker=True,
                    )
                )

            elif drawing.kind == "hline":
                (x1, y), (x2, _) = drawing.points

                if not price_in_visible_range(y):
                    continue

                x1 = x_to_index_if_visible(x1)
                if x1 is None:
                    continue

                if x2 == -1:
                    x2 = len(df) - 1
                else:
                    x2 = x_to_index_if_visible(x2)
                    if x2 is None:
                        continue

                artists.append(
                    ax.hlines(
                        y,
                        x1,
                        x2,
                        color=drawing.color,
                        url=url,
                        linewidth=1,
                        pickradius=3,
                        picker=True,
                    )
                )

            elif drawing.kind == "tline":
                if len(drawing.points) < 2:
                    continue

                (x1, y1), (x2, y2) = drawing.points

                x1 = x_to_index_if_visible(x1)
                x2 = x_to_index_if_visible(x2)

                if x1 is None or x2 is None:
                    continue

                artists.append(
                    ax.axline(
                        (x1, y1),
                        (x2, y2),
                        url=url,
                        color=drawing.color,
                        linewidth=1,
                        pickradius=3,
                        picker=True,
                    )
                )

            elif drawing.kind == "aline":
                if len(drawing.points) < 2:
                    continue

                points = []

                for x, y in drawing.points:
                    x = x_to_index_if_visible(x)

                    if x is None:
                        points = None
                        break

                    points.append((x, y))

                if points is None:
                    continue

                line = LineCollection(
                    [points],
                    colors=[drawing.color],
                    url=url,
                    linewidths=1,
                    pickradius=3,
                    picker=True,
                )

                ax.add_collection(line)
                artists.append(line)

        return artists

    def _make_format_coords(self, df: pd.DataFrame):
        """Create a debounced format_coords function."""
        index = df.index
        n = len(df)

        # Avoid repeated column checks
        has_mrs = "M_RS" in df.columns
        has_rs = "RS" in df.columns

        # Cache column indexes to use integer lookups (faster)
        open_i = df.columns.get_loc("Open")
        high_i = df.columns.get_loc("High")
        low_i = df.columns.get_loc("Low")
        close_i = df.columns.get_loc("Close")
        vol_i = df.columns.get_loc("Volume")

        mrs_i = df.columns.get_loc("M_RS") if has_mrs else None
        rs_i = df.columns.get_loc("RS") if has_rs else None

        # Faster row access
        rows = df.to_numpy(copy=False)
        separator = " " * 5

        @debounce(0.025)
        def format_coords(x: float, y: float) -> str:
            i = round(x)

            if i < 0 or i >= n:
                return ""

            row = rows[i]
            dt = index[i]
            dt_str = f"{dt:%d %b %Y}".upper()

            out = (
                f"{dt_str}"
                f"{separator}O: {row[open_i]}"
                f"{separator}H: {row[high_i]}"
                f"{separator}L: {row[low_i]}"
                f"{separator}C: {row[close_i]}"
                f"{separator}V: {row[vol_i]:,.0f}"
            )

            if mrs_i is not None:
                out += f"{separator}MRS: {row[mrs_i]}"
            elif rs_i is not None:
                out += f"{separator}RS: {row[rs_i]}"

            out += f"{separator}Y: {y:.2f}"
            return out

        return format_coords
