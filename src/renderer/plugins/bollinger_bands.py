from __future__ import annotations

from typing import Any

from mplfinance import make_addplot

from .utils import bollinger_bands

"""
Bollinger Bands plugin.

Calculates the middle, upper, and lower Bollinger Bands and plots them
directly on the main price panel using ``mplfinance.make_addplot``.

Configuration options are supplied through the plugin's entry in
``CHART_PLUGINS`` within ``defs/user.json``. Because Bollinger Bands are
a price overlay, the panel configuration should use ``"kind": "price"``.

Available Options:
    source (str, optional):
        DataFrame column used as the input price series.
        Defaults to ``"Close"``.

    length (int, optional):
        Moving average period used for the middle band.
        Defaults to ``20``. If omitted, the plugin also checks the
        ``period`` option.

    period (int, optional):
        Alias for ``length``.

    mult (float, optional):
        Standard-deviation multiplier used to calculate the upper and
        lower bands. Defaults to ``2.0``. If omitted, the plugin also
        checks the ``multiplier`` option.

    multiplier (float, optional):
        Alias for ``mult``.

    basis_color (str, optional):
        Color of the middle Bollinger Band.
        Defaults to ``"dodgerblue"``.

    upper_color (str, optional):
        Color of the upper Bollinger Band.
        Defaults to ``"gray"``.

    lower_color (str, optional):
        Color of the lower Bollinger Band.
        Defaults to ``"gray"``.

    basis_width (float, optional):
        Width of the middle Bollinger Band.
        Defaults to ``1.2``.

    band_width (float, optional):
        Width of the upper and lower Bollinger Bands.
        Defaults to ``1.0``.

    plot_panel (int | str, optional):
        Panel assigned by the plugin runner. For the standard Bollinger
        Bands configuration, this is panel ``0``.

Example Configuration:
    Add the following entry to the top-level ``CHART_PLUGINS`` object
    in ``defs/user.json``::

        {
          "BOLLINGER_BANDS": {
            "name": "bollinger_bands",
            "option": "bb",
            "help": "Add Bollinger Bands.",
            "lookback": 100,
            "panel": {
              "kind": "price"
            },
            "source": "Close",
            "length": 20,
            "mult": 2.0,
            "basis_color": "dodgerblue",
            "upper_color": "gray",
            "lower_color": "gray",
            "basis_width": 1.2,
            "band_width": 1.0
          }
        }
"""


def apply(
    df,
    plot_args: dict[str, Any],
    options: dict[str, Any],
    display_period: int,
) -> None:
    source_name = options.get("source", "Close")
    length = int(options.get("length", options.get("period", 20)))
    mult = float(options.get("mult", options.get("multiplier", 2.0)))

    basis_color = options.get("basis_color", "dodgerblue")
    upper_color = options.get("upper_color", "gray")
    lower_color = options.get("lower_color", "gray")

    basis_width = float(options.get("basis_width", 1.2))
    band_width = float(options.get("band_width", 1.0))

    panel = options.get("plot_panel", 0)

    basis, upper, lower = bollinger_bands(
        source=df[source_name],
        length=length,
        mult=mult,
    )

    addplots = plot_args.setdefault("addplot", list())
    addplots.extend(
        [
            make_addplot(
                basis.iloc[-display_period:],
                label=f"BB Mid {length}",
                color=basis_color,
                width=basis_width,
                panel=panel,
                secondary_y=False,
            ),
            make_addplot(
                upper.iloc[-display_period:],
                label=f"BB Upper {length}",
                color=upper_color,
                width=band_width,
                panel=panel,
                secondary_y=False,
            ),
            make_addplot(
                lower.iloc[-display_period:],
                label=f"BB Lower {length}",
                color=lower_color,
                width=band_width,
                panel=panel,
                secondary_y=False,
            ),
        ]
    )
