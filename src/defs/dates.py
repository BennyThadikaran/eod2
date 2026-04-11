from datetime import datetime, timedelta
import logging

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

import tzlocal

logger = logging.getLogger(__name__)

tz_IN = ZoneInfo("Asia/Kolkata")
tz_local = tzlocal.get_localzone()


class Dates:
    "A class for date related functions in EOD2"

    def __init__(self, lastUpdate: str):
        today = datetime.now(tz_IN)

        self.today = datetime.combine(today, datetime.min.time())

        dt = datetime.fromisoformat(lastUpdate).astimezone(tz_IN)

        self.dt = self.lastUpdate = dt

        self.pandasDt = self.dt.strftime("%Y-%m-%d")

    def nextDate(self):
        """Set the next trading date and return True.
        If its a future date, return False"""

        curTime = datetime.now(tz_IN)
        self.dt = self.dt + timedelta(1)

        if self.dt > curTime:
            logger.info("All Up To Date")
            return False

        if self.dt.day == curTime.day and curTime.hour < 16:
            # Display the users local time
            local_time = curTime.replace(hour=19, minute=0).astimezone(tz_local)

            t_str = local_time.strftime("%I:%M%p")  # 07:00PM

            logger.info(
                f"All Up To Date. Check again after {t_str} for today's EOD data"
            )
            return False

        self.pandasDt = self.dt.strftime("%Y-%m-%d")
        return True
