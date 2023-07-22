from pathlib import Path
from json import loads

DIR = Path(__file__).parent.parent


class Config:
    '''A class to store all configuration related to EOD2
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

        if (user_config := DIR / "defs" / "user.json").exists():
            self.__dict__.update(loads(user_config.read_bytes()))

    # DO NOT EDIT BELOW
    VERSION = '3.0'

    def toList(self, filename: str):
        return (DIR / 'data' / filename).read_text().strip().split("\n")

    def __str__(self):
        txt = f'EOD2 | Version: {self.VERSION}\n'

        for p in self.__dict__:
            txt += f'{p}: {getattr(self, p)}\n'

        return txt
