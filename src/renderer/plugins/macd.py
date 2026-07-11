from __future__ import annotations

from typing import Any

from mplfinance import make_addplot

from .utils import macd

"""
Moving Average Convergence Divergence (MACD) plugin.

Calculates the MACD line, signal line, and histogram, and plots them in
a dedicated lower panel using ``mplfinance.make_addplot``.

The MACD plugin requires an exclusive panel because it plots the MACD and
signal lines on one y-axis and the histogram on the other.

Configuration options are supplied through the plugin's entry in
``CHART_PLUGINS`` within ``defs/user.json``. At runtime, the plugin
runner injects the panel assignment into the options dictionary.

Available Options:
    source (str, optional):
        DataFrame column used as the input price series.
        Defaults to ``"Close"``.

    fastlen (int, optional):
        Fast exponential moving average period.
        Defaults to ``12``. The alias ``fast`` is also accepted.

    slowlen (int, optional):
        Slow exponential moving average period.
        Defaults to ``26``. The alias ``slow`` is also accepted.

    siglen (int, optional):
        Signal line exponential moving average period.
        Defaults to ``9``. The alias ``signal`` is also accepted.

    line_color (str, optional):
        Color of the MACD line.
        Defaults to ``"royalblue"``.

    signal_color (str, optional):
        Color of the signal line.
        Defaults to ``"red"``.

    hist_positive_color (str, optional):
        Color used for positive histogram bars.
        Defaults to ``"darkgray"``.

    hist_negative_color (str, optional):
        Color used for negative histogram bars.
        Defaults to ``"darkgray"``.

    line_width (float, optional):
        Width of the MACD line.
        Defaults to ``1.5``.

    signal_width (float, optional):
        Width of the signal line.
        Defaults to ``1.2``.

    ylabel (str, optional):
        Y-axis label for the MACD line and signal line.
        Defaults to ``f"MACD {fastlen},{slowlen}"``.

    plot_panel (int | str, optional):
        Panel number assigned by the plugin runner. This value is
        automatically injected at runtime based on the panel allocation
        specified in ``user.json``. Defaults to ``"lower"``.

    secondary_y (bool, optional):
        Indicates whether the MACD and signal lines should be plotted on
        the secondary y-axis of the assigned panel. Automatically
        injected by the plugin runner. Defaults to ``False``.

Example Configuration:
    Add the following entry to the top-level ``CHART_PLUGINS`` object
    in ``defs/user.json``::

        {
          "MACD": {
            "name": "macd",
            "option": "macd",
            "help": "Add MACD indicator.",
            "lookback": 100,
            "panel": {
              "kind": "lower",
              "axes": 2,
              "share": false
            },
            "source": "Close",
            "fastlen": 12,
            "slowlen": 26,
            "siglen": 9,
            "line_color": "royalblue",
            "signal_color": "red",
            "hist_positive_color": "darkgray",
            "hist_negative_color": "darkgray"
          }
        }
"""


def apply(
    df, plot_args: dict[str, Any], options: dict[str, Any], display_period: int
) -> None:
    source_name = options.get("source", "Close")
    fastlen = int(options.get("fastlen", options.get("fast", 12)))
    slowlen = int(options.get("slowlen", options.get("slow", 26)))
    siglen = int(options.get("siglen", options.get("signal", 9)))

    line_color = options.get("line_color", "royalblue")
    signal_color = options.get("signal_color", "red")

    hist_positive_color = options.get("hist_positive_color", "darkgray")
    hist_negative_color = options.get("hist_negative_color", "darkgray")

    line_width = float(options.get("line_width", 1.5))
    signal_width = float(options.get("signal_width", 1.2))

    panel = options.get("plot_panel", "lower")
    ylabel = options.get("ylabel", f"MACD {fastlen},{slowlen}")

    macd_line, signal_line, histogram = macd(
        source=df[source_name],
        fastlen=fastlen,
        slowlen=slowlen,
        siglen=siglen,
    )

    histogram_positive = histogram.where(histogram >= 0)
    histogram_negative = histogram.where(histogram < 0)

    addplots = plot_args.setdefault("addplot", list())
    addplots.extend(
        [
            make_addplot(
                macd_line.iloc[-display_period:],
                label=ylabel,
                panel=panel,
                secondary_y=True,
                color=line_color,
                width=line_width,
            ),
            make_addplot(
                signal_line.iloc[-display_period:],
                label=f"Signal {siglen}",
                panel=panel,
                secondary_y=True,
                color=signal_color,
                width=signal_width,
            ),
            make_addplot(
                histogram_positive.iloc[-display_period:],
                type="bar",
                panel=panel,
                secondary_y=False,
                color=hist_positive_color,
                ylabel="MACD Histogram",
            ),
            make_addplot(
                histogram_negative.iloc[-display_period:],
                type="bar",
                panel=panel,
                secondary_y=False,
                color=hist_negative_color,
            ),
        ]
    )
