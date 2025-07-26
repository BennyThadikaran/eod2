import json
from pathlib import Path

DIR = Path(__file__).parents[1]


class Config:
    """A class to store all configuration related to EOD2

    To override the attributes of this class, create a user.json file in
    src/defs/ with the option you wish to override.

    All key attributes in user.json must be uppercase.
    """

    INIT_HOOK = None

    ## AMIBROKER ##
    AMIBROKER = False  # converts to Amibroker format on sync
    AMI_UPDATE_DAYS = 365  # Number of days to convert on first run

    ## Delivery ##
    DLV_L1 = 1  # 1x average delivery
    DLV_L2 = 1.5  # 1.5x average delivery
    DLV_L3 = 2  # 2x average delivery
    DLV_AVG_LEN = 30  # Length used to calculate delivery average.
    VOL_AVG_LEN = 30  # Length used to calculate volume average.

    ## DGET.py ##
    DGET_AVG_DAYS = 30  # Length used to calculate avg vol, trade qty, delivery
    DGET_DAYS = 30  # No of days delivery result returned with -l option

    ## PLOT CONFIG ##

    # snap lines drawn to nearest high/Low/close/open.
    # Use mouse coordinates if false.
    MAGNET_MODE = True

    PLOT_PLUGINS = {}  # Key is plugin name, Value is a dict of plugin config.
    PLOT_DAYS = 160  # No of days to plot
    PLOT_WEEKS = 140  # No of weeks to plot

    # Mansfield Relative Strength (MRS) and # Dorsey Relative Strength (RS)
    PLOT_M_RS_LEN_D = 22  # Daily length
    PLOT_M_RS_LEN_W = 52  # Weekly length
    PLOT_RS_INDEX = "nifty 50"  # Nifty index to use for RS and MRS

    # One of binance, binancedark, blueskies, brasil, charles, checkers,
    # classic, default, ibd, kenan, mike, nightclouds, sas, starsandstripes,
    # tradingview, yahoo
    PLOT_CHART_STYLE = "tradingview"  # Chart theme

    PLOT_CHART_TYPE = "candle"  # ohlc, candle, line

    # Chart colors
    # https://matplotlib.org/stable/gallery/color/named_colors.html#base-colors
    PLOT_RS_COLOR = "darkblue"  # Dorsey Relative Strength line
    PLOT_M_RS_COLOR = "darkgreen"  # Mansfield Relative Strength line

    # Delivery - Candle colors
    PLOT_DLV_DEFAULT_COLOR = "darkgrey"  # default color
    PLOT_DLV_L1_COLOR = "red"  # level 1
    PLOT_DLV_L2_COLOR = "darkorange"  # level 2
    PLOT_DLV_L3_COLOR = "royalblue"  # level 3

    # Trendline, horizontal line colors
    PLOT_AXHLINE_COLOR = "crimson"  # horizontal line (end to end)
    PLOT_HLINE_COLOR = "royalblue"  # horizontal line (from set point to end)
    PLOT_TLINE_COLOR = "darkturquoise"  # Trend line
    PLOT_ALINE_COLOR = "mediumseagreen"  # Arbitrary line (segment)

    WATCH = {"SECTORS": (DIR / "data/sectors.csv").resolve()}
    PRESET = {}

    def __init__(self) -> None:
        user_config = DIR / "defs" / "user.json"

        if user_config.exists():
            dct = json.loads(user_config.read_bytes())

            if "WATCH" in dct:
                dct["WATCH"].update(self.WATCH)

            self.__dict__.update(dct)

    # DO NOT EDIT BELOW
    VERSION = "8.1.2"

    def toList(self, filename: str):
        return (DIR / "data" / filename).read_text().strip().split("\n")

    def __str__(self):
        txt = f"EOD2 | Version: {self.VERSION}\n"

        for p in self.__dict__:
            txt += f"{p}: {getattr(self, p)}\n"

        return txt
