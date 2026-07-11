from __future__ import annotations

from typing import Any

from mplfinance import make_addplot

from .utils import average_true_range

"""
Average True Range (ATR) plugin.

Calculates the Average True Range (ATR) and plots it as a lower-panel
indicator using ``mplfinance.make_addplot``.

Configuration options are supplied through the plugin's entry in
``CHART_PLUGINS`` within ``defs/user.json``. At runtime, the plugin
runner injects the panel assignment into the options dictionary.

Available Options:
    period (int, optional):
        ATR calculation period. Defaults to ``14``. If omitted, the
        plugin also checks the ``length`` option.

    length (int, optional):
        Alias for ``period``.

    line_color (str, optional):
        Color of the ATR line. Defaults to ``"firebrick"``.

    width (float, optional):
        Width of the ATR line. Defaults to ``1.5``.

    label (str, optional):
        Legend label for the plotted line.
        Defaults to ``f"ATR {period}"``.

    ylabel (str, optional):
        Y-axis label for the indicator panel.
        Defaults to ``"ATR"``.

    plot_panel (int | str, optional):
        Panel number assigned by the plugin runner. This value is
        automatically injected at runtime based on the panel allocation
        specified in ``user.json``. Defaults to ``"lower"``.

    secondary_y (bool, optional):
        Indicates whether the indicator should be plotted on the
        secondary y-axis of the assigned panel. Automatically injected
        by the plugin runner. Defaults to ``False``.

Example Configuration:
    Add the following entry to the top-level ``CHART_PLUGINS`` object
    in ``defs/user.json``::

        {
          "ATR": {
            "name": "atr",
            "option": "atr",
            "help": "Add ATR indicator.",
            "lookback": 100,
            "panel": {
              "kind": "lower",
              "axes": 1,
              "share": true,
              "preferred_axis": "any",
              "allow_volume_panel": true
            },
            "period": 14,
            "line_color": "firebrick",
            "width": 1.5,
            "ylabel": "ATR"
          }
        }
"""


def apply(
    df,
    plot_args: dict[str, Any],
    options: dict[str, Any],
    display_period: int,
) -> None:
    period = int(options.get("period", options.get("length", 14)))

    line_color = options.get("line_color", "firebrick")
    width = float(options.get("width", 1.5))

    panel = options.get("plot_panel", "lower")
    secondary_y = bool(options.get("secondary_y", False))

    label = options.get("label", f"ATR {period}")
    ylabel = options.get("ylabel", "ATR")

    atr = average_true_range(
        high=df.High,
        low=df.Low,
        close=df.Close,
        length=period,
    )

    addplots = plot_args.setdefault("addplot", list())
    addplots.append(
        make_addplot(
            atr.iloc[-display_period:],
            label=label,
            panel=panel,
            secondary_y=secondary_y,
            color=line_color,
            ylabel=ylabel,
            width=width,
        )
    )
