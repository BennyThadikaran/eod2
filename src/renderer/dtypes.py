from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from defs.config import config

if TYPE_CHECKING:
    from .annotations import DrawingManager
    from .breadth_render import BreadthRenderer
    from .candle_render import CandlestickRenderer
    from .indicators import IndicatorPipeline
    from .loader import EODFileLoader
    from .persistence import SessionStore
    from .plugins import PluginRunner


class Modifier(Enum):
    CTRL = auto()
    SHIFT = auto()
    CTRL_SHIFT = auto()


SourceKind = Literal["symbols", "file", "watch", "breadth"]
Timeframe = Literal["d", "w", "m", "q"]
SnrVersion = Literal["v1", "v2"]
BreadthOption = Literal["sma", "50", "200", "nethighs", "adline", "osc"]

TF_MAP = dict(d="Daily", w="Weekly", m="Monthly", q="Quarterly")


@dataclass(frozen=True)
class AppPaths:
    root: Path
    data_path: Path
    breadth_file: Path
    rs_index_file: Path
    config_path: Path
    drawings: Path
    selections: Path
    save_dir: Path

    @classmethod
    def from_root(cls, root: Path) -> AppPaths:
        data_path = root / "eod2_data" / "daily"

        return cls(
            root=root,
            data_path=data_path,
            breadth_file=root / "eod2_data" / "market_tracker.csv",
            rs_index_file=data_path / f"{config.PLOT_RS_INDEX}.csv",
            config_path=root / "defs" / "user.json",
            drawings=root / "data" / "drawings.json",
            selections=root / "selections.csv",
            save_dir=root / "SAVED_CHARTS",
        )


@dataclass(frozen=True)
class PanelAssignment:
    panel: int
    secondary_y: bool | None = False


@dataclass
class RenderContext:
    loader: EODFileLoader
    renderer: CandlestickRenderer | BreadthRenderer
    indicator_pipeline: IndicatorPipeline | None
    drawing_manager: DrawingManager | None
    plot_args: dict
    session_store: SessionStore | None = None
    plugin_runner: PluginRunner | None = None
    panel_layout: dict[str, PanelAssignment] = field(default_factory=dict)


@dataclass(frozen=True)
class BreadthIndicator:
    columns: list[str]
    title: str


@dataclass(slots=True)
class ResumeCommand:
    watch: str
    idx: int


@dataclass(slots=True)
class WatchCommand:
    name: str
    resume: ResumeCommand | None = None


@dataclass(slots=True)
class BreadthCommand:
    index: str
    indicators: list[BreadthOption] = field(default_factory=list)


@dataclass(slots=True)
class PlotSource:
    kind: SourceKind
    mode: Literal["stock", "breadth"] = "stock"
    symbols: list[str] = field(default_factory=list)
    file: Path | None = None
    watch: WatchCommand | None = None
    breadth: BreadthCommand | None = None


@dataclass(slots=True)
class PlotCommand:
    source: PlotSource
    user_set_timeframe: bool
    timeframe: Timeframe
    period: int
    save: bool = False
    volume: bool = False
    rs: bool = False
    mansfield_rs: bool = False
    sma: list[int] = field(default_factory=list)
    ema: list[int] = field(default_factory=list)
    vol_sma: list[int] = field(default_factory=list)
    date: datetime | None = None
    snr: SnrVersion | None = None
    delivery: bool = False
    plugins: dict[str, dict[str, Any]] = field(default_factory=dict)
