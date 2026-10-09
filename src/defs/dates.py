from __future__ import annotations

import logging
from datetime import datetime, timedelta

import tzlocal

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo


logger = logging.getLogger(__name__)

TZ_IN = ZoneInfo("Asia/Kolkata")
TZ_LOCAL = tzlocal.get_localzone()


class Dates:
    """A class for date related functions in EOD2"""

    def __init__(self, last_update: str):
        today = datetime.now(TZ_IN)

        self.today = datetime.combine(today, datetime.min.time())

        dt = datetime.fromisoformat(last_update).astimezone(TZ_IN)

        self.dt = self.lastUpdate = dt

        self.pandas_dt = self.dt.strftime("%Y-%m-%d")

    def nextDate(self):
        """Set the next trading date and return True.
        If its a future date, return False
        """
        cur_time = datetime.now(TZ_IN)
        self.dt = self.dt + timedelta(1)

        if self.dt > cur_time:
            logger.info("All Up To Date")
            return False

        if self.dt.day == cur_time.day and cur_time.hour < 16:
            # Display the users local time
            local_time = cur_time.replace(hour=19, minute=0).astimezone(TZ_LOCAL)

            t_str = local_time.strftime("%I:%M%p")  # 07:00PM

            logger.info(
                f"All Up To Date. Check again after {t_str} for today's EOD data"
            )
            return False

        self.pandas_dt = self.dt.strftime("%Y-%m-%d")
        return True
