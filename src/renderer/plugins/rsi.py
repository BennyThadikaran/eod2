from __future__ import annotations

from typing import Any

import pandas as pd
from mplfinance import make_addplot

from .utils import relative_strength_index

"""
Relative Strength Index (RSI) plugin.

Calculates the Relative Strength Index and plots it with overbought and
oversold reference lines in a lower chart panel using
``mplfinance.make_addplot``.

Configuration options are supplied through the plugin's entry in
``CHART_PLUGINS`` within ``defs/user.json``. At runtime, the plugin
runner injects the panel assignment into the options dictionary.

Available Options:
    period (int, optional):
        RSI calculation period.
        Defaults to ``14``.

    line_color (str, optional):
        Color of the RSI line.
        Defaults to ``"#0F766E"``.

    overbought (int | float, optional):
        Value used for the overbought reference line.
        Defaults to ``70``.

    oversold (int | float, optional):
        Value used for the oversold reference line.
        Defaults to ``30``.

    overbought_color (str, optional):
        Color of the overbought reference line.
        Defaults to ``"#64748B"``.

    oversold_color (str, optional):
        Color of the oversold reference line.
        Defaults to ``"#64748B"``.

    plot_panel (int | str, optional):
        Panel number assigned by the plugin runner. This value is
        automatically injected at runtime based on the panel allocation
        specified in ``user.json``. Defaults to ``"lower"``.

    secondary_y (bool, optional):
        Indicates whether the RSI and reference lines should be plotted
        on the secondary y-axis of the assigned panel. Automatically
        injected by the plugin runner. Defaults to ``False``.

Example Configuration:
    Add the following entry to the top-level ``CHART_PLUGINS`` object
    in ``defs/user.json``::

        {
          "RSI": {
            "name": "rsi",
            "option": "rsi",
            "help": "Add RSI indicator.",
            "lookback": 100,
            "panel": {
              "kind": "lower",
              "axes": 1,
              "share": true,
              "preferred_axis": "any",
              "allow_volume_panel": true
            },
            "period": 14,
            "line_color": "#0F766E",
            "overbought": 70,
            "oversold": 30,
            "overbought_color": "#64748B",
            "oversold_color": "#64748B"
          }
        }
"""


def apply(
    df, plot_args: dict[str, Any], options: dict[str, Any], display_period: int
) -> None:
    period = int(options.get("period", 14))
    line_color = options.get("line_color", "#0F766E")
    overbought_color = options.get("overbought_color", "#64748B")
    oversold_color = options.get("oversold_color", "#64748B")
    overbought_value = options.get("overbought", 70)
    oversold_value = options.get("oversold", 30)

    panel = options.get("plot_panel", "lower")
    secondary_y = bool(options.get("secondary_y", False))

    rsi = relative_strength_index(
        source=df.Close,
        length=period,
    )

    addplots = plot_args.setdefault("addplot", list())

    overbought = pd.Series(data=overbought_value, index=df.index[-display_period:])
    oversold = pd.Series(data=oversold_value, index=df.index[-display_period:])

    addplots.extend(
        [
            make_addplot(
                rsi.iloc[-display_period:],
                label="RSI",
                panel=panel,
                secondary_y=secondary_y,
                color=line_color,
                ylabel="RSI",
                width=2,
            ),
            make_addplot(
                overbought,
                panel=panel,
                secondary_y=secondary_y,
                color=overbought_color,
                linestyle="dashed",
                width=1,
            ),
            make_addplot(
                oversold,
                panel=panel,
                secondary_y=secondary_y,
                color=oversold_color,
                linestyle="dashed",
                width=1,
            ),
        ]
    )
