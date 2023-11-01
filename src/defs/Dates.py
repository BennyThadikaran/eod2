from datetime import datetime, timedelta


class Dates:
    'A class for date related functions in EOD2'

    def __init__(self, lastUpdate: str):
        self.today = datetime.combine(datetime.today(), datetime.min.time())
        self.dt = self.lastUpdate = datetime.fromisoformat(lastUpdate)
        self.pandasDt = self.dt.strftime('%Y-%m-%d')

    def nextDate(self):
        '''Set the next trading date and return True.
        If its a future date, return False'''

        curTime = datetime.today()
        nxtDt = self.dt + timedelta(1)

        week_day = nxtDt.weekday()

        if week_day > 4:
            self.dt = nxtDt + timedelta(7 - week_day)
        else:
            self.dt = nxtDt

        if self.dt > curTime:
            print('All Up To Date')
            return False

        if self.dt.day == curTime.day and curTime.hour < 18:
            print("All Up To Date. Check again after 7pm for today's EOD data")
            return False

        self.pandasDt = self.dt.strftime('%Y-%m-%d')
        return True
