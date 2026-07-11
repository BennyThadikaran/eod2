from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, cast

import numpy as np
import pandas as pd
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.backend_bases import DrawEvent, MouseEvent
from matplotlib.collections import LineCollection

from defs.config import config

from .dtypes import Timeframe
from .util import index_to_iso, iso_to_index, randomChar

DatePoint = tuple[str, float]


@dataclass(slots=True)
class Drawing:
    """A single user-drawn annotation."""

    kind: Literal["axhline", "tline", "aline", "hline"]
    points: list[DatePoint]
    color: str
    url: str


class BlitPreview:
    """Fast preview renderer for interactive drawing."""

    def __init__(self) -> None:
        self.ax: Axes | None = None
        self.canvas = None
        self.background = None
        self.artist: Artist | None = None

    def set_axes(self, ax: Axes) -> None:
        self.ax = ax
        self.canvas = ax.figure.canvas

        self.canvas.mpl_connect("draw_event", self._on_draw)

    def _on_draw(self, event: DrawEvent | None = None) -> None:
        if self.ax is None or self.canvas is None:
            raise ValueError("Axes or canvas is not set")
        # Capture clean axes background after a full draw.
        self.background = self.canvas.copy_from_bbox(self.ax.bbox)

    def ensure_background(self) -> None:
        if self.background is None:
            self.canvas.draw()
            self.background = self.canvas.copy_from_bbox(self.ax.bbox)

    def set_artist(self, artist: Artist) -> None:
        self.artist = artist
        self.artist.set_animated(True)

    def draw(self) -> None:
        if self.canvas is None or self.ax is None or self.artist is None:
            return

        self.canvas.restore_region(self.background)
        self.ax.draw_artist(self.artist)
        self.canvas.blit(self.ax.bbox)
        self.canvas.flush_events()

    def clear(self) -> None:
        if self.canvas is None or self.artist is None:
            return

        self.canvas.restore_region(self.background)
        self.canvas.blit(self.ax.bbox)

        self.artist.remove()
        self.artist = None


class DrawingTool:
    """Mouse event state machine for creating and deleting drawings."""

    def __init__(self, magnet_mode: bool, drawing_manager: DrawingManager) -> None:
        self._blit = BlitPreview()
        self._ax = None

        self._magnet_mode: bool = magnet_mode
        self._drawing_manager: DrawingManager = drawing_manager
        self._active: bool = False
        self._state = ""
        self._pending_points: list[tuple[float, float]] = []
        self._preview_artist: Artist | None = None
        self._cid: int | None = None

        self._index: pd.DatetimeIndex | None = None
        self._open: np.ndarray | None = None
        self._high: np.ndarray | None = None
        self._low: np.ndarray | None = None
        self._close: np.ndarray | None = None

    def set_axes(self, ax: Axes) -> None:
        self._ax = ax
        self._blit.set_axes(ax)

    def toggle(self) -> None:
        """Toggle draw mode on/off."""
        self._active = not self._active
        if not self._active:
            self._reset_state()

    def is_active(self) -> bool:
        """Check if draw mode is active."""
        return self._active

    def active_state(self) -> str:
        """Return current sub-mode name for status display."""
        if not self._active:
            return ""
        return self._state

    def _reset_state(self) -> None:
        """Reset internal state machine."""
        self._pending_points.clear()
        self._state = ""
        self._snap_price = None
        self._cid = None
        self._preview_artist = None

    def set_draw_state(self, key: str) -> None:
        match key:
            case "shift":
                self._state = "Trendline - Click second point or Esc"
            case "control":
                self._state = "Continous Segment - Click another point or Esc"
            case "ctrl+shift":
                self._state = "Horizontal Segment - Click second point or Esc"
            case "*":
                self._state = ""
        if self._state:
            self._drawing_manager.update_draw_state(self._state)

    def set_data(self, df: pd.DataFrame) -> None:
        self._index = cast(pd.DatetimeIndex, df.index)
        self._open = df["Open"].to_numpy()
        self._high = df["High"].to_numpy()
        self._low = df["Low"].to_numpy()
        self._close = df["Close"].to_numpy()

    def handle_click(
        self,
        x: int,
        y: float,
        event: MouseEvent,
    ) -> Drawing | None:
        """Handle left-click event. Returns a Drawing ready to be added.

        The Drawing's color is already set from the DrawingManager config.
        """
        if not self._active or self._ax is None or event.ydata is None:
            return None

        x_max = self._ax.get_xlim()[1]

        if x > x_max:
            x = round(x_max)
        elif x < 0:
            x = 0

        y = event.ydata

        # Apply magnet snapping
        if self._magnet_mode:
            if (
                self._open is None
                or self._high is None
                or self._high is None
                or self._low is None
                or self._close is None
            ):
                raise RuntimeError("Data not set on DrawingTool")

            y = self._snap_to_ohlc(
                event.ydata,
                self._open[x],
                self._high[x],
                self._low[x],
                self._close[x],
            )

        key = event.key

        # Determine sub-mode based on modifier keys
        if key is None:
            # Plain left click → axhline / horizontal line (spans the x-axis)
            return Drawing(
                kind="axhline",
                points=[("", y)],
                color=self._drawing_manager._get_color("axhline"),
                url=f"axhline:{randomChar(6)}",
            )

        if self._cid is None:
            # if guard to avoid registering multiple motion events
            self._cid = event.canvas.mpl_connect(
                "motion_notify_event", self.handle_motion
            )

        if len(self._pending_points) == 0:
            self._pending_points.append((x, y))
            self.set_draw_state(key)
            return None

        self._index = cast(pd.DatetimeIndex, self._index)

        if key == "shift":
            # Shift+click → tline / trendline (two points)
            p1 = self._pending_points[0]
            p2 = (x, y)

            if p1 == p2:
                # A trendline cannot be drawn with identical points
                return

            self._pending_points.clear()

            return Drawing(
                kind="tline",
                points=[
                    (index_to_iso(p1[0], self._index), p1[1]),
                    (index_to_iso(p2[0], self._index), p2[1]),
                ],
                color=self._drawing_manager._get_color("tline"),
                url=f"tline:{randomChar(6)}",
            )

        if key == "control":
            # Ctrl+click → aline / Continous segment
            p1 = self._pending_points[0]
            p2 = (x, y)

            if p1 == p2:
                # A segment cannot be drawn with identical points
                return
            self._pending_points.clear()
            self._pending_points.append(p2)

            return Drawing(
                kind="aline",
                points=[
                    (index_to_iso(p1[0], self._index), p1[1]),
                    (index_to_iso(p2[0], self._index), p2[1]),
                ],
                color=self._drawing_manager._get_color("aline"),
                url=f"aline:{randomChar(6)}",
            )

        if key == "ctrl+shift":
            # Ctrl+Shift+click → hline / horizontal segment
            x1, y1 = self._pending_points[0]
            p2 = (x, y1)

            if self._pending_points[0] == p2:
                # A segment cannot be drawn with identical points
                return

            return Drawing(
                kind="hline",
                points=[
                    (index_to_iso(x1, self._index), y1),
                    (index_to_iso(x, self._index), y1),
                ],
                color=self._drawing_manager._get_color("hline"),
                url=f"hline:{randomChar(6)}",
            )

        return None

    def handle_motion(self, event: MouseEvent) -> None:
        """Handle mouse motion for preview."""
        if event.xdata is None or event.ydata is None or self._ax is None:
            return

        if (
            self._open is None
            or self._high is None
            or self._high is None
            or self._low is None
            or self._close is None
        ):
            raise RuntimeError("Data not set on DrawingTool")

        if not len(self._pending_points):
            return

        x1, y1 = self._pending_points[0]
        x = round(event.xdata)
        x_max = len(self._open) - 1

        if x > x_max:
            x = x_max
        elif x < 0:
            x = 0

        if self._magnet_mode:
            y = self._snap_to_ohlc(
                event.ydata,
                self._open[x],
                self._high[x],
                self._low[x],
                self._close[x],
            )
        else:
            y = round(event.ydata, 2)

        if x1 == x and y1 == y:
            return

        self._blit.ensure_background()

        key = event.key

        if key == "ctrl+shift":
            xs = [x1, x]
            ys = [y1, y1]
            color = self._drawing_manager._get_color("hline")
        elif key == "shift":
            xs = [x1, x]
            ys = [y1, y]
            color = self._drawing_manager._get_color("tline")
        elif key == "control":
            xs = [x1, x]
            ys = [y1, y]
            color = self._drawing_manager._get_color("aline")
        else:
            return

        if self._preview_artist is None:
            self._preview_artist = self._ax.plot(xs, ys, color=color, linewidth=1)[0]
            self._blit.set_artist(self._preview_artist)
        else:
            self._preview_artist.set_data(xs, ys)
            self._preview_artist.set_color(color)
        self._blit.draw()

    def _snap_to_ohlc(
        self, y: float, open_val: float, high: float, low: float, close: float
    ) -> float:
        """Snap y-coordinate to nearest OHLC value."""
        if y >= high:
            return high
        if y <= low:
            return low

        return open_val if abs(open_val - y) < abs(close - y) else close


class DrawingManager:
    """Stores, retrieves, and persists user drawings."""

    def __init__(self, timeframe: Timeframe) -> None:
        self._timeframe = timeframe
        self._magnet_mode: bool = config.MAGNET_MODE
        self._ax: Axes | None = None
        self._drawings: dict[str, dict[str, Drawing]] = {}
        self._artists: dict[str, dict[str, Artist]] = {}  # Track matplotlib artists

        self.line_args = dict(
            linewidth=1,
            mouseover=True,
            pickradius=3,
            picker=True,
        )

        self.segment_args: dict[str, Any] = dict(
            pickradius=3,
            picker=True,
        )

        self.color_map = {
            "axhline": config.PLOT_AXHLINE_COLOR,
            "hline": config.PLOT_HLINE_COLOR,
            "tline": config.PLOT_TLINE_COLOR,
            "aline": config.PLOT_ALINE_COLOR,
        }

    def set_axes(self, ax: Axes) -> None:
        """Set the current axes for drawing."""
        self._ax = ax

    def update_draw_state(self, state: str):
        if self._ax is not None:
            self._ax.set_title(
                state,
                loc="right",
                color="darkslategray",
            )

    def set_artists(self, symbol: str, artists: list[Artist]):
        self._artists.setdefault(symbol, {})

        for artist in artists:
            url = artist.get_url()

            if url:
                self._artists[symbol][url] = artist

    def set_index(self, index: pd.DatetimeIndex):
        self._index = index

    def get(self, symbol: str) -> dict[str, Drawing]:
        """Get all drawings for a symbol."""
        return self._drawings.get(symbol, {})

    def add(self, symbol: str, drawing: Drawing) -> None:
        """Add a drawing and immediately render it on the chart.

        Args:
            symbol: Stock symbol or indicator name
            drawing: Drawing to add
        """
        self._drawings.setdefault(symbol, {})
        self._artists.setdefault(symbol, {})

        url = drawing.url
        self._drawings[symbol][url] = drawing

        # Immediately draw on the axes if available
        if self._ax is not None:
            artist = self._draw_on_axes(drawing)

            if artist is not None:
                self._artists[symbol][url] = artist
                self._ax.figure.canvas.draw_idle()

    def remove(self, symbol: str, artist: Artist) -> bool:
        """Remove a specific drawing and its artist from the chart."""
        if symbol not in self._drawings:
            return False

        url = artist.get_url()

        if not url:
            raise ValueError("No url attached to artist")

        artist.remove()

        self._artists[symbol].pop(url)

        self._drawings[symbol].pop(url)

        if self._ax is not None:
            self._ax.figure.canvas.draw_idle()

        return True

    def remove_all(self, symbol: str) -> None:
        """Remove all drawings and artists for a symbol."""
        # Remove all artists from axes
        if symbol not in self._artists:
            return

        for artist in self._artists[symbol].values():
            artist.remove()

        del self._artists[symbol]

        del self._drawings[symbol]

        if self._ax is not None:
            self._ax.figure.canvas.draw_idle()

    def _draw_on_axes(self, drawing: Drawing) -> Any:
        """Draw a single drawing on the current axes.

        Returns:
            The matplotlib artist object, or None
        """
        if self._ax is None:
            return None

        if drawing.kind == "axhline":
            _, y = drawing.points[0]
            artist = self._ax.axhline(
                y,
                color=drawing.color,
                url=drawing.url,
                **self.line_args,
            )
            return artist

        elif drawing.kind == "hline":
            (x1, y), (x2, _) = drawing.points

            x1 = iso_to_index(x1, self._index)
            if x2 == -1:
                x2 = self._ax.get_xlim()[1]
            else:
                x2 = iso_to_index(x2, self._index)

            artist = self._ax.hlines(
                y,
                x1,
                x2,
                colors=drawing.color,
                url=drawing.url,
                **self.segment_args,
            )
            return artist

        elif drawing.kind == "tline":
            if len(drawing.points) >= 2:
                points = [(iso_to_index(x, self._index), y) for x, y in drawing.points]

                artist = self._ax.axline(
                    *points,
                    color=drawing.color,
                    linewidth=1,
                    pickradius=3,
                    picker=True,
                    url=drawing.url,
                )
                return artist

        elif drawing.kind == "aline":
            if len(drawing.points) >= 2:
                points = [(iso_to_index(x, self._index), y) for x, y in drawing.points]

                line = LineCollection(
                    [points],
                    colors=[drawing.color],
                    linewidths=1,
                    pickradius=3,
                    picker=True,
                    url=drawing.url,
                )
                self._ax.add_collection(line)
                return line

        return None

    def _get_color(self, kind: str) -> str:
        """Get the color for a drawing kind from config."""
        return self.color_map.get(kind, "black")

    def clear_artists(self, symbol: str) -> None:
        """Clear all artists for a symbol without removing from storage.

        Used when switching charts (artists are tied to old axes).
        """
        if symbol in self._artists:
            self._artists[symbol].clear()

    def to_dict(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Serialize drawings for the current timeframe.

        Shape:
            symbol -> url -> Drawing dict
        """
        return {
            sym: {url: asdict(d) for url, d in url_map.items()}
            for sym, url_map in self._drawings.items()
        }

    def from_dict(self, data: dict[str, dict[str, Any]]) -> None:
        """Restore drawings for the current timeframe.

        Expects:
            symbol -> url -> Drawing dict
        """
        self._drawings.clear()
        self._artists.clear()

        for sym, url_map in data.items():
            self._drawings[sym] = {}
            self._artists[sym] = {}

            for url, d in url_map.items():
                if not d:
                    continue
                self._drawings[sym][url] = Drawing(
                    kind=d["kind"],
                    points=[tuple(p) for p in d["points"]],
                    color=d["color"],
                    url=d["url"],
                )
