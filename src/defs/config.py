from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

DIR = Path(__file__).parents[1]


@dataclass
class Config:
    """Store all configuration related to EOD2.

    Values may be overridden by creating src/defs/user.json.
    """

    INIT_HOOK: Any = None

    # ---------- AMIBROKER ----------
    AMIBROKER: bool = False
    AMI_UPDATE_DAYS: int = 365

    # ---------- DELIVERY ----------
    DLV_L1: float = 1
    DLV_L2: float = 1.5
    DLV_L3: float = 2
    DLV_AVG_LEN: int = 30
    VOL_AVG_LEN: int = 30

    # ---------- DGET ----------
    DGET_AVG_DAYS: int = 30
    DGET_DAYS: int = 30

    # ---------- PLOT ----------
    CHART_RESUME: dict | None = None
    PLOT_SIZE: tuple[int, int] | None = None  # (width, height) in inches
    MAGNET_MODE: bool = True

    PLOT_PLUGINS: dict[str, dict] = field(default_factory=dict)
    CHART_PLUGINS: dict[str, dict] = field(default_factory=dict)

    PLOT_DAYS: int = 180
    PLOT_WEEKS: int = 180
    PLOT_MONTHS: int = 140
    PLOT_QUARTERS: int = 60

    # Mansfield Relative Strength (MRS) and Dorsey Relative Strength (RS)
    PLOT_M_RS_LEN_D: int = 22
    PLOT_M_RS_LEN_W: int = 52
    PLOT_M_RS_LEN_M: int = 24
    PLOT_M_RS_LEN_Q: int = 8
    PLOT_RS_INDEX: str = "nifty 50"

    PLOT_SNR_SENSITIVITY: Literal["strict", "balanced", "relaxed"] = "strict"

    # One of:
    # binance, binancedark, blueskies, brasil, charles, checkers,
    # classic, default, ibd, kenan, mike, nightclouds, sas,
    # starsandstripes, tradingview, yahoo
    PLOT_CHART_STYLE: str = "tradingview"

    # ohlc, candle, line
    PLOT_CHART_TYPE: str = "candle"

    # Relative strength colors
    PLOT_RS_COLOR: str = "darkblue"
    PLOT_M_RS_COLOR: str = "darkgreen"

    # Delivery colors
    PLOT_DLV_DEFAULT_COLOR: str = "darkgrey"
    PLOT_DLV_L1_COLOR: str = "red"
    PLOT_DLV_L2_COLOR: str = "darkorange"
    PLOT_DLV_L3_COLOR: str = "royalblue"

    # Line colors
    PLOT_AXHLINE_COLOR: str = "crimson"
    PLOT_HLINE_COLOR: str = "royalblue"
    PLOT_TLINE_COLOR: str = "darkturquoise"
    PLOT_ALINE_COLOR: str = "mediumseagreen"

    WATCH: dict[str, Path] = field(
        default_factory=lambda: {"SECTORS": (DIR / "data" / "sectors.csv").resolve()}
    )

    PRESET: dict[str, Any] = field(default_factory=dict)

    # ---------- INTERNAL ----------
    VERSION: str = "9.4.0"
    EXPECTED_DATA_VERSION: float = 3.3

    @classmethod
    def load(cls) -> Config:
        """Create Config and apply user.json overrides."""
        cfg = cls()

        user_config = DIR / "defs" / "user.json"

        if not user_config.exists():
            return cfg

        with user_config.open() as f:
            overrides = json.load(f)

        # Merge WATCH dictionaries
        if "WATCH" in overrides:
            watch = cfg.WATCH.copy()
            watch.update(overrides["WATCH"])
            overrides["WATCH"] = watch

        # Apply overrides
        for key, value in overrides.items():
            setattr(cfg, key, value)

        return cfg

    def reload(self):
        fresh = Config.load()
        self.__dict__.clear()
        self.__dict__.update(fresh.__dict__)

    def to_list(self, filename: str) -> list[str]:
        """Return lines from a file in the data directory."""
        return (DIR / "data" / filename).read_text().splitlines()

    def __str__(self) -> str:
        lines = [f"EOD2 | Version: {self.VERSION}"]

        for field_name in self.__dataclass_fields__:
            lines.append(f"{field_name}: {getattr(self, field_name)}")

        return "\n".join(lines)


# Maintain a single shared instance
config = Config.load()
