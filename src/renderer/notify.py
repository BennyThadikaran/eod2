from typing import Literal

from matplotlib.axes import Axes
from matplotlib.text import Text

HELP = """                                           ## HELP ##

N → Next chart                          R → Reset to original view

P → Prev chart                           F → Fullscreen

Q → Quit and exit app               G → Toggle Major Grids

D → Toggle draw mode             O → Zoom to Rect


                                    ## DRAW MODE ##

Horizontal Line :                    LEFT Click

Trend Line:                            Hold SHIFT key + LEFT click on chart

Continous Segments:            Hold CTRL key + LEFT click on chart

Horizontal Segment :            Hold CTRL + SHIFT key + LEFT click on chart

Delete Line:                          RIGHT click on line

Delete all lines:                     Hold SHIFT key + RIGHT click
"""


class Notify:
    def __init__(self) -> None:
        self.text: Text | None = None
        self.timer = None
        self._ax = None
        self.help_text: Text | None = None

        self.styles = {
            "success": dict(color="#2E7D32", edgecolor="#1B5E20"),
            "error": dict(color="#C62828", edgecolor="#8E0000"),
        }

    def set_axes(self, ax: Axes) -> None:
        self._ax = ax

    def add(self, message: str, level: Literal["success", "error"] = "success") -> None:
        if self._ax is None:
            raise RuntimeError("Axes not set")

        self.remove()

        self.text = self._ax.text(
            0.98,
            0.97,
            message,
            transform=self._ax.transAxes,
            ha="right",  # Anchor the right edge of the text
            va="top",  # Anchor the top edge of the text
            fontsize=12,
            color=self.styles[level]["color"],
            bbox=dict(
                boxstyle="round,pad=0.4",
                facecolor="white",
                edgecolor=self.styles[level]["edgecolor"],
                linewidth=1,
            ),
        )

        self.timer = self._ax.figure.canvas.new_timer(interval=2000)
        self.timer.add_callback(self.remove)
        self.timer.start()

    def remove(self) -> None:
        if self.text is None:
            return

        if self.timer is not None:
            self.timer.stop()
            self.timer = None

        self.text.remove()
        self.text = None

    def toggle_help(self):
        if self._ax is None:
            raise RuntimeError("Axes not set")

        if self.help_text is None:
            self.help_text = self._ax.text(
                0.02,
                0.97,
                HELP,
                transform=self._ax.transAxes,
                ha="left",
                va="top",
                color="darkslategrey",
                fontweight="bold",
                bbox=dict(
                    boxstyle="round,pad=1",
                    facecolor="mintcream",
                    edgecolor="darkslategrey",
                    linewidth=1.5,
                ),
            )
        else:
            self.help_text.remove()
            self.help_text = None
