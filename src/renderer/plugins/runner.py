from __future__ import annotations

from importlib import import_module
from typing import Any

import pandas as pd

from renderer.cli import CliError
from renderer.dtypes import PanelAssignment


class PluginError(CliError):
    """Raised when a chart plugin cannot be loaded or executed."""


class PluginRunner:
    def __init__(
        self,
        plugins: dict[str, dict[str, Any]],
        panel_layout: dict[str, PanelAssignment],
    ) -> None:
        self.plugins = plugins
        self.panel_layout = panel_layout

    def apply(
        self,
        df: pd.DataFrame,
        plot_args: dict[str, Any],
        display_period: int,
    ) -> None:
        for plugin_key, plugin_config in self.plugins.items():
            options = dict(plugin_config)

            module_name = str(options.pop("name", plugin_key.lower()))

            assignment = self.panel_layout.get(f"plugin:{plugin_key}")

            if assignment is not None:
                options["plot_panel"] = assignment.panel

                if assignment.secondary_y is not None:
                    options["secondary_y"] = assignment.secondary_y

            try:
                module = import_module(f"renderer.plugins.{module_name}")
            except ModuleNotFoundError as exc:
                if exc.name in (module_name, f"renderer.plugins.{module_name}"):
                    raise PluginError(
                        f"Could not load plugin '{plugin_key}' from module 'renderer.plugins.{module_name}'"
                    ) from exc

                raise

            module.apply(df, plot_args, options, display_period)
