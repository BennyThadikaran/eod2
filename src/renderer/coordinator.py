"""PlotCoordinator - central orchestrator for chart navigation and interaction."""

from __future__ import annotations

from typing import cast

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.backend_bases import KeyEvent, MouseEvent, PickEvent
from matplotlib.figure import Figure

from renderer.candle_render import CandlestickRenderer

from .annotations import DrawingTool
from .breadth_render import BREADTH_INDICATORS
from .cli import PlotCommand
from .dtypes import TF_MAP, Modifier, RenderContext
from .navigation import NavigationList
from .notify import Notify
from .shortcuts import ShortcutHandler


class PlotCoordinator:
    """Central orchestrator for the charting application.

    Owns the interaction loop, delegates to all components.
    """

    def __init__(
        self,
        cmd: PlotCommand,
        nav: NavigationList,
        context: RenderContext,
        drawing_tool: DrawingTool | None = None,
    ) -> None:
        """Initialize the plot coordinator."""
        self.cmd = cmd
        self.loader = context.loader
        self.nav = nav
        self.indicator_pipeline = context.indicator_pipeline
        self._renderer = context.renderer
        self.drawing_manager = context.drawing_manager
        self.plot_args = context.plot_args

        self.plugin_runner = context.plugin_runner
        self.panel_layout = context.panel_layout

        self.is_stock_mode = cmd.source.mode == "stock"
        self.drawing_tool = drawing_tool
        self.session_store = context.session_store
        self._fullscreen_applied = False

        # Interactive mode state
        self._fig: Figure | None = None
        self._axs: list[Axes] = []
        self._main_ax: Axes | None = None
        self._data_len: int | None = None
        self._current_symbol: str = ""
        self._selections: set[str] = set()
        self._modifier_pressed: Modifier | None = None

        self._notify = Notify()

        self.modifier: dict[str, Modifier] = {
            "control": Modifier.CTRL,
            "shift": Modifier.SHIFT,
            "ctrl+shift": Modifier.CTRL_SHIFT,
        }

        # Drawing state
        self._events: list[int] = []

        self._all_data: dict[str, pd.DataFrame] = {}
        self.tf_str = TF_MAP[cmd.timeframe]

        # Keep track of symbols visited to suppress repeated warnings
        self.visited = set()

    def run(self) -> None:
        """Start the interactive chart."""
        plt.ion()
        self._show_current()

    def _show_current(self) -> None:
        """Load and display the current symbol."""
        symbol = self.nav.current()
        self._current_symbol = symbol

        plot_args = self.plot_args.copy()

        # Get preloaded data
        if self.is_stock_mode:
            if not self.indicator_pipeline:
                raise RuntimeError("IndicatorPipeline not set")

            symbol, _, meta = symbol.partition(",")
            visited = symbol in self.visited

            title = symbol.upper()

            if meta:
                title += f" • {meta.upper()}"

            title += f" • {self.tf_str}"

            plot_args["title"] = title

            df = self.loader.load(symbol)

            if df is None or df.empty:
                if not visited:
                    print(f"WARN: No data for {symbol}. Skipping...")
                    self.visited.add(symbol)
                self._auto_advance()
                return

            # Enrich with indicators
            df = self.indicator_pipeline.enrich(title, df, visited)

            self._data_len = len(df)
            period = min(self._data_len, self.cmd.period)

            if self.plugin_runner:
                self.plugin_runner.apply(df, plot_args, period)

            df = df[-period:]
            df = cast(pd.DataFrame, df)

            if self.drawing_tool:
                self.drawing_tool.set_data(df)

            # Add SNR levels
            if self.cmd.snr and self.is_stock_mode:
                snr_levels = self.indicator_pipeline.get_snr_levels(df)
                if snr_levels:
                    plot_args["alines"] = dict(
                        alines=snr_levels,
                        linewidths=0.7,
                    )

            # Check for marketcolor overrides (delivery)
            if "MCOverrides" in df.columns:
                plot_args["marketcolor_overrides"] = df["MCOverrides"].values

            # Add some padding both sides of chart.
            # + 15 on right to clear space for annotations
            plot_args["xlim"] = (-2, df.shape[0] + 15)

            if self.drawing_manager and self.session_store:
                index = cast(pd.DatetimeIndex, df.index)
                self.drawing_manager.set_index(index)
                self.drawing_manager.from_dict(self.session_store.load_drawings())
        else:
            df = self.loader.load_breadth_indicators()

            self._data_len = len(df)
            breadth_info = BREADTH_INDICATORS[symbol]
            df = df[breadth_info.columns]

        df = cast(pd.DataFrame, df)
        # Render with mplfinance
        fig, axs = self._renderer.render(df, plot_args, symbol)

        # Connect keyboard handler
        self._fig = fig
        self._axs = axs
        self.shortcut_handler = ShortcutHandler(self._fig, self)

        # Apply custom rendering (x-axis, drawings overlay)
        self._main_ax = axs[0]

        self._notify.set_axes(self._main_ax)

        if self.drawing_manager and self.drawing_tool:
            self.drawing_manager.set_axes(self._main_ax)
            self.drawing_tool.set_axes(self._main_ax)

            drawings = self.drawing_manager.get(symbol)
            assert isinstance(self._renderer, CandlestickRenderer)
            artists = self._renderer.overlay_drawings(self._main_ax, drawings, df)

            self.drawing_manager.set_artists(symbol, artists)

        # Set title
        self._main_ax.set_title(
            f"#{self.nav.current_index + 1} of {len(self.nav.items)}     SHIFT + H → Help     Q → Quit",
            loc="left",
            color="darkslategray",
        )

        # Fullscreen only apply once
        if not self._fullscreen_applied:
            fig_manager = plt.get_current_fig_manager()

            if fig_manager is not None:
                fig_manager.full_screen_toggle()

        self.visited.add(symbol)
        # mpf.show(block=True)
        plt.show(block=True)

    def _connect_drawing_events(self) -> None:
        """Connect mouse events for drawing tool."""
        if self._fig is None or self.drawing_tool is None:
            return

        self._events = []

        self._events.append(
            self._fig.canvas.mpl_connect("key_press_event", self._on_key_press)
        )
        self._events.append(
            self._fig.canvas.mpl_connect("key_release_event", self._on_key_release)
        )
        self._events.append(
            self._fig.canvas.mpl_connect("button_press_event", self._on_button_press)
        )
        self._events.append(self._fig.canvas.mpl_connect("pick_event", self._on_pick))

    def _on_key_press(self, event: KeyEvent) -> None:
        key = event.key

        if key is None or self._main_ax is None:
            return

        modifier = self.modifier.get(key)

        if modifier is None or modifier == self._modifier_pressed:
            return

        self._modifier_pressed = modifier

        match key:
            case "control":
                self._main_ax.set_title(
                    "Continous Segment - Click a point to start",
                    loc="right",
                    color="darkslategray",
                )
            case "shift":
                self._main_ax.set_title(
                    "Trendline - Click a point to start",
                    loc="right",
                    color="darkslategray",
                )
            case "ctrl+shift":
                self._main_ax.set_title(
                    "Horizontal Segment - Click a point to start",
                    loc="right",
                    color="darkslategray",
                )
            case "*":
                self._key_pressed = False

    def _on_key_release(self, event: KeyEvent) -> None:
        """Handle key release events (modifier keys for drawing)."""
        if event.key in self.modifier:
            self._modifier_pressed = None

            if self.drawing_tool._cid:
                self._fig.canvas.mpl_disconnect(self.drawing_tool._cid)

            self.drawing_tool._reset_state()

            self._main_ax.set_title(
                "DRAW MODE",
                loc="right",
                color="darkslategray",
            )

    def _on_button_press(self, event: MouseEvent) -> None:
        """Handle mouse button press for drawing creation/deletion."""
        # Right click - deletion
        if event.button == 3:
            if event.key == "shift":
                self.drawing_manager.remove_all(self._current_symbol)
            return

        # Left click - drawing creation
        if event.xdata is None or event.ydata is None or event.xdata > self._data_len:
            return

        x = round(event.xdata)
        y = round(event.ydata, 2)

        drawing = self.drawing_tool.handle_click(x, y, event)

        if drawing is not None:
            self.drawing_manager.add(self._current_symbol, drawing)

    def _on_pick(self, event: PickEvent) -> None:
        """Handle pick events (clicking on existing drawings)."""
        if event.mouseevent.button == 3:
            # Right click on a drawing
            artist = event.artist

            self.drawing_manager.remove(self._current_symbol, artist)

    def _auto_advance(self) -> None:
        """Automatically advance to next symbol if current one fails."""
        if self.nav.can_go_next():
            self.nav.next()
            self._show_current()
        else:
            print("No valid symbols to display")
            self._close_all()

    def navigate_next(self) -> None:
        """Navigate to the next symbol."""
        if not self.nav.can_go_next():
            self._notify.add("At Last Chart", "error")
            return
        self.nav.next()
        if self._fig:
            self._notify.remove()
            plt.close(self._fig)
        self._show_current()

    def navigate_previous(self) -> None:
        """Navigate to the previous symbol."""
        if not self.nav.can_go_previous():
            self._notify.add("At first Chart", "error")
            return
        self.nav.previous()
        if self._fig:
            self._notify.remove()
            plt.close(self._fig)
        self._show_current()

    def jump_to(self, index: int) -> None:
        if self.nav.jump_to(index):
            if self._fig:
                self._notify.remove()
                plt.close(self._fig)
            self._show_current()
            return
        else:
            if index > 0:
                self._notify.add(
                    f"Cannot jump to {index}. Valid range 1 to {self.nav.length}",
                    level="error",
                )

    def add_jump_status(self, status: str) -> None:
        if status:
            self._main_ax.set_title(
                f"{status}: Press j to jump chart",
                loc="right",
                color="darkslategray",
            )
        else:
            if self.drawing_tool and self.drawing_tool.is_active():
                status = "DRAW MODE"

            self._main_ax.set_title(
                status,
                loc="right",
                color="darkslategray",
            )

    def toggle_draw_mode(self) -> None:
        """Toggle drawing mode on/off."""
        if self.drawing_tool is None:
            return

        self.drawing_tool.toggle()

        if not self._main_ax:
            return

        if self.drawing_tool.is_active():
            self._connect_drawing_events()
            self._main_ax.set_title(
                "DRAW MODE",
                loc="right",
                color="darkslategray",
            )
            return

        self._main_ax.set_title(
            "",
            loc="right",
        )

        for evt in self._events:
            self._fig.canvas.mpl_disconnect(evt)
        self._events.clear()

    def plot_help(self) -> None:
        self._notify.toggle_help()

    def add_to_selection(self) -> None:
        """Add current symbol to the selection set."""
        if self._current_symbol in self._selections:
            self._notify.add("Already added")
        else:
            self._selections.add(self._current_symbol)
            self._notify.add("✓ Added to selection")
            print(
                f"Added to selection: {self._current_symbol.upper()} "
                f"({len(self._selections)} total)"
            )

    def draw_mode_enabled(self):
        return self.drawing_tool.is_active()

    def quit(self) -> None:
        """Save state and exit."""
        self._notify.remove()
        # Save selections
        if self.session_store:
            if self._selections:
                self.session_store.save_selections(self._selections)
                print(f"\nSaved {len(self._selections)} selections to selections.csv")

            # Save drawings
            if self.drawing_manager:
                drawings_data = self.drawing_manager.to_dict()
                self.session_store.save_drawings(drawings_data)

            # Save watch resume
            watch_name = ""
            if self.cmd.source.watch:
                watch_name = self.cmd.source.watch.name

            if watch_name:
                self.session_store.save_watch_resume(watch_name, self.nav.current_index)

        self._close_all()
        exit(0)

    def _close_all(self) -> None:
        """Close all matplotlib figures."""
        plt.close("all")
