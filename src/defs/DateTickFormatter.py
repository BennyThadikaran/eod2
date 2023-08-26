from matplotlib.ticker import FixedFormatter, FixedLocator


class DateTickFormatter:
    def __init__(self, dates, tf='daily'):
        '''Dates: DatetimeIndex
        tf: daily or weekly'''
        self.dates = dates
        self.len = len(dates)
        self.month = self.year = None
        self.idx = 0
        self.intervals = (2, 4, 7, 14)
        self.tf = tf

    def _formatDate(self, dt):
        '''Returns the formatted date label for the ticker.'''

        if dt.month != self.month:
            self.month = dt.month

            if dt.year != self.year:
                self.year = dt.year
                return f'{dt:%d\n%Y}'

            return f'{dt:%d\n%b}'.upper()

        return dt.day

    def _getInterval(self):
        '''Returns an integer interval at which the ticks will be labelled.'''

        idx = 0
        while True:
            if idx == len(self.intervals) - 1:
                return self.intervals[idx]

            d = self.len / self.intervals[idx]

            if d <= max(self.intervals):
                return self.intervals[idx]
            else:
                idx += 1

    def getLabels(self):
        '''Returns an instance of FixedLocator and FixedFormatter in a tuple.
        Ticker format based on number of candles in Data.
        '''

        if self.year is None:
            self.year = self.dates[0].year
            self.month = self.dates[0].month

        if self.len <= 22:
            return self._daily()

        if self.len < 200:
            return self._atInterval(self._getInterval())

        return self._monthly()

    def _daily(self):
        '''Labels ticks on every candle'''

        labels = []

        for dt in self.dates:
            if self.tf == 'daily' and dt.weekday() > 4:
                continue

            labels.append(self._formatDate(dt))

        return (FixedLocator(tuple(range(self.len))), FixedFormatter(labels))

    def _monthly(self):
        '''Labels ticks on 1st Candle of every month and year'''

        labels = []
        ticks = []

        for i, dt in enumerate(self.dates):
            if dt.month != self.month:
                self.month = dt.month

                if dt.year != self.year:
                    self.year = dt.year
                    labels.append(dt.year)
                else:
                    labels.append(f'{dt:%b}'.upper())

                ticks.append(i)
            elif i == 0:
                labels.append(f'{dt:%b\n%Y}'.upper())
                ticks.append(i)

        return (FixedLocator(ticks), FixedFormatter(labels))

    def _atInterval(self, interval):
        '''Labels ticks at every interval of candle dates'''

        labels = []
        ticks = []
        nextTick = interval

        for i, dt in enumerate(self.dates):
            if i == 1:
                labels.append(self._formatDate(dt))
                ticks.append(i)
            elif i == self.len - 1:
                break
            elif i == nextTick:
                ticks.append(i)
                labels.append(self._formatDate(dt))
                nextTick += interval

            i += 1

        return (FixedLocator(ticks), FixedFormatter(labels))
