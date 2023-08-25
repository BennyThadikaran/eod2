from matplotlib.ticker import FixedFormatter, FixedLocator


class DateTickFormatter:
    def __init__(self, dates, tf='daily'):
        self.dates = dates
        self.len = len(dates)
        self.month = self.year = None
        self.idx = 0
        self.intervals = (2, 4, 7, 14)
        self.tf = tf

    def formatDate(self, dt):
        if dt.month != self.month:
            self.month = dt.month

            if dt.year != self.year:
                self.year = dt.year
                return f'{dt:%d\n%Y}'

            return f'{dt:%d\n%b}'.upper()

        return dt.day

    def getInterval(self):
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
        if self.year is None:
            self.year = self.dates[0].year
            self.month = self.dates[0].month

        if self.len <= 22:
            return self.daily()

        if self.len < 200:
            return self.atInterval(self.getInterval())

        return self.monthly()

    def daily(self):
        labels = []

        for dt in self.dates:
            if self.tf == 'daily' and dt.weekday() > 4:
                continue

            labels.append(self.formatDate(dt))

        return (FixedLocator(tuple(range(self.len))), FixedFormatter(labels))

    def monthly(self):
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

    def atInterval(self, interval):
        labels = []
        ticks = []
        nextTick = interval

        for i, dt in enumerate(self.dates):
            if i == 1:
                labels.append(self.formatDate(dt))
                ticks.append(i)
            elif i == self.len - 1:
                break
            elif i == nextTick:
                ticks.append(i)
                labels.append(self.formatDate(dt))
                nextTick += interval

            i += 1

        return (FixedLocator(ticks), FixedFormatter(labels))
