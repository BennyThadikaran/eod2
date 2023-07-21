from datetime import datetime, timedelta
from pathlib import Path


DIR = Path(__file__).parent.parent


class Dates:
    'A class for date related functions in EOD2'

    def __init__(self):
        self.today = datetime.combine(datetime.today(), datetime.min.time())
        self.file = DIR / 'eod2_data' / 'lastupdate.txt'
        self.dt = self.getLastUpdated()
        self.pandas_dt = self.dt.strftime('%Y-%m-%d')

    def getLastUpdated(self):
        'Get the last updated Date from lastupdate.txt'

        if not self.file.is_file():
            return self.today - timedelta(1)

        return datetime.fromisoformat(self.file.read_text().strip())

    def setLastUpdated(self):
        'Set the Date in lastupdate.txt'

        self.file.write_text(self.dt.isoformat())

    def getNextDate(self):
        'Gets the next trading date or exit if its a future date'

        curTime = datetime.today()
        nxtDt = self.dt + timedelta(1)

        week_day = nxtDt.weekday()

        if week_day > 4:
            self.dt = nxtDt + timedelta(7 - week_day)
        else:
            self.dt = nxtDt

        if self.dt > curTime:
            exit('All Up To Date')

        if self.dt.day == curTime.day and curTime.hour < 19:
            exit("All Up To Date. Check again after 7pm for today's EOD data")

        self.pandas_dt = self.dt.strftime('%Y-%m-%d')
        return
