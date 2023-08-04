from pathlib import Path
from json import loads

DIR = Path(__file__).parent.parent


class Config:
    '''A class to store all configuration related to EOD2

    Attributes for AMIBROKER
        AMIBROKER:          If True, converts bhavcopy to Amibroker format on
                            sync. Data is stored in src/eod2_data/amibroker/
                            Default False.

        AMI_UPDATE_DAYS:    Number of days bhavcopy must be downloaded and formated
                            to Amibroker.
                            Only applies if src/eod2_data/amibroker/ is empty.
                            Default 365.

    Attributes for plot.py
        PLOT_DAYS:          Number of days to be plotted with plot.py.
                            Default 180.

        PLOT_AVG_DAYS:      Number of days average to calculate above average
                            delivery. Default 60.

    Attributes for lookup.py
        LOOKUP_DAYS:        Number of days delivery analysis to return.
                            Default 15.

        LOOKUP_AVG_DAYS:    Number of days average to calculate above average
                            delivery. Default 60.

    Keywords passed to dget.py and plot.py.
        WATCH:              watchlist.csv
        IT:                 it.csv
        BANK:               bank.csv

        Additional keywords can be defined with a user.json file in src/defs/.
        KEYWORD must be UPPERCASE and filename must be a file in src/data/.
        {
            "KEYWORD": <filename.csv>
        }

    To override the attributes of this class, create a user.json file in
    src/defs/ with the option you wish to override.

    All attributes in user.json must be uppercase.
    '''

    def __init__(self) -> None:
        self.AMIBROKER = False
        self.AMI_UPDATE_DAYS = 365
        self.PLOT_DAYS = 180
        self.PLOT_AVG_DAYS = 60
        self.LOOKUP_AVG_DAYS = 60
        self.LOOKUP_DAYS = 15
        self.WATCH = "watchlist.csv"
        self.IT = "it.csv"
        self.BANK = "bank.csv"
        self.ADDITIONAL_INDICES = []

        if (user_config := DIR / "defs" / "user.json").exists():
            self.__dict__.update(loads(user_config.read_bytes()))

    # DO NOT EDIT BELOW
    VERSION = '3.0.1'

    def toList(self, filename: str):
        return (DIR / 'data' / filename).read_text().strip().split("\n")

    def __str__(self):
        txt = f'EOD2 | Version: {self.VERSION}\n'

        for p in self.__dict__:
            txt += f'{p}: {getattr(self, p)}\n'

        return txt
