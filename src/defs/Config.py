from pathlib import Path
import json

DIR = Path(__file__).parents[1]


class Config:
    """A class to store all configuration related to EOD2

    Attributes for AMIBROKER
        AMIBROKER:              If True, converts bhavcopy to Amibroker format on
                                sync. Data is stored in src/eod2_data/amibroker/
                                Default False.

        AMI_UPDATE_DAYS:        Number of days bhavcopy must be downloaded and
                                formated to Amibroker.
                                Only applies if src/eod2_data/amibroker/ is empty.
                                Default 365.

        DLV_L1,L2,L3            This is a multiple of average delivery.
                                L3 being highest delivery multiple

        DLV_AVG_LEN:            Length used to calculate delivery average.
                                Default 60.

        VOL_AVG_LEN             Length used to calculate volume average.
                                Default 30

    Attributes for plot.py
        PLOT_PLUGINS:           A dictionary of plugins to load. Dict values
                                must be a dictionary containing plugin
                                configuration.

        PLOT_DAYS:              Number of days to be plotted with plot.py.
                                Default 160.

        PLOT_WEEKS:             Number of weeks to be plotted with plot.py.
                                Default 140.

        PLOT_M_RS_LEN_D:        Length used to calculate Mansfield
                                Relative Strength on daily TF. Default 60.

        PLOT_M_RS_LEN_W:        Length used to calculate Mansfield
                                Relative Strength on Weekly TF. Default 52.

        PLOT_RS_INDEX:          Index used to calculate Dorsey Relative strength
                                and Mansfield relative strength.
                                Default 'nifty 50'

        MAGNET_MODE:            When True, lines snap to closest High, Low,
                                Close or Open. If False, mouse click coordinates on
                                chart are used.
                                Default True

        PLOT_CHART_STYLE:       Chart theme
        PLOT_CHART_TYPE:        Chart type. One of: ohlc, candle, line

        PLOT_RS_COLOR:          Dorsey RS line color
        PLOT_M_RS_COLOR:        Mansfield RS line color
        PLOT_DLV_L1_COLOR:      Delivery mode L1 bar color
        PLOT_DLV_L2_COLOR:      Delivery mode L2 bar color
        PLOT_DLV_L3_COLOR:      Delivery mode L3 bar color
        PLOT_DLV_DEFAULT_COLOR: Delivery mode default color

    Attributes for DGET.py
        DGET_DAYS:            Number of days delivery analysis to return.
                                Default 15.

        DGET_AVG_DAYS:        Number of days average to calculate above average
                                delivery. Default 60.

    To override the attributes of this class, create a user.json file in
    src/defs/ with the option you wish to override.

    All key attributes in user.json must be uppercase.
    """

    AMIBROKER = False
    AMI_UPDATE_DAYS = 365
    INIT_HOOK = None

    # Delivery
    DLV_L1 = 1
    DLV_L2 = 1.5
    DLV_L3 = 2
    DLV_AVG_LEN = 60
    VOL_AVG_LEN = 30

    # DGET
    DGET_AVG_DAYS = 60
    DGET_DAYS = 15

    # PLOT CONFIG
    PLOT_PLUGINS = {}
    PLOT_DAYS = 160
    PLOT_WEEKS = 140
    PLOT_M_RS_LEN_D = 60
    PLOT_M_RS_LEN_W = 52
    PLOT_RS_INDEX = "nifty 50"
    MAGNET_MODE = True

    PRESET = {}
    WATCH = {"SECTORS": "sectors.csv"}

    # PLOT THEMES AND COLORS
    # 'binance', 'binancedark', 'blueskies', 'brasil', 'charles',
    # 'checkers', 'classic', 'default', 'ibd', 'kenan', 'mike',
    # 'nightclouds', 'sas', 'starsandstripes', 'tradingview', 'yahoo'
    PLOT_CHART_STYLE = "tradingview"

    # ohlc, candle, line
    PLOT_CHART_TYPE = "candle"

    # https://matplotlib.org/stable/gallery/color/named_colors.html#base-colors
    PLOT_RS_COLOR = "darkblue"
    PLOT_M_RS_COLOR = "darkgreen"
    PLOT_DLV_L1_COLOR = "red"
    PLOT_DLV_L2_COLOR = "darkorange"
    PLOT_DLV_L3_COLOR = "royalblue"
    PLOT_DLV_DEFAULT_COLOR = "darkgrey"

    PLOT_AXHLINE_COLOR = "crimson"
    PLOT_TLINE_COLOR = "darkturquoise"
    PLOT_ALINE_COLOR = "mediumseagreen"
    PLOT_HLINE_COLOR = "royalblue"

    ADDITIONAL_INDICES = []

    def __init__(self) -> None:
        user_config = DIR / "defs" / "user.json"

        if user_config.exists():
            dct = json.loads(user_config.read_bytes())

            if "WATCH" in dct:
                dct["WATCH"].update(self.WATCH)

            self.__dict__.update(dct)

    # DO NOT EDIT BELOW
    VERSION = "6.0.3"

    def toList(self, filename: str):
        return (DIR / "data" / filename).read_text().strip().split("\n")

    def __str__(self):
        txt = f"EOD2 | Version: {self.VERSION}\n"

        for p in self.__dict__:
            txt += f"{p}: {getattr(self, p)}\n"

        return txt
