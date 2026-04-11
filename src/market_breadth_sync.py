import logging

from httpx import ConnectError
from nse import NSE
from pathlib import Path
import json
import zipfile
from typing import Optional
import pandas as pd
from datetime import datetime

from defs.dates import Dates
from defs.utils import writeJson, getDataFrame
from defs.defs import checkForHolidays


def ema(price, period, prev_ema):
    """Calculate current EMA from previous EMA"""
    alpha = 2 / (period + 1)
    return alpha * price + (1 - alpha) * prev_ema


def load_symbol(sym) -> Optional[pd.DataFrame]:
    file = DAILY / f"{sym.lower()}.csv"

    if not file.exists():
        print(f"{sym} not found")
        return None

    df = getDataFrame(file, period=260, columns=["Date", "High", "Low", "Close"])

    df.loc[:, "MA50"] = df.Close.rolling(50).mean().round(2)
    df.loc[:, "MA200"] = df.Close.rolling(200).mean().round(2)
    df.loc[:, "52WH"] = df.High.rolling(252).max().shift(1).round(2)
    df.loc[:, "52WL"] = df.Low.rolling(252).min().shift(1).round(2)
    df.loc[:, "pclose"] = df.Close.shift(1)

    return df


def extract_pr_zip(zip_file) -> Optional[pd.DataFrame]:
    with zipfile.ZipFile(zip_file) as zf:
        namelist = zf.namelist()
        file_to_extract = None

        for name in namelist:
            if name.lower().endswith(".csv") and "mcap" in name.lower():
                file_to_extract = name
                break

        if file_to_extract:
            file_info = zf.getinfo(file_to_extract)

            if file_info.file_size == 0:
                return None

            with zf.open(file_to_extract) as f:
                mcap = pd.read_csv(
                    f,
                    index_col="Symbol",
                    usecols=pd.Index(["Symbol", "Series", "Category"]),
                )

                mcap.columns = mcap.columns.str.strip()
                mcap.Category = mcap.Category.str.strip()

                mcap = mcap[
                    mcap.Series.isin(priority)
                    & mcap.Category.isin(("Listed", "Permitted"))
                    & ~mcap.index.str.contains(r"-RE\d*$", na=False)  # -RE or -RE1 etc
                ]

                mcap.loc[:, "rank"] = mcap.Series.map(priority)
                mcap = mcap.sort_values("rank")
                mcap = mcap[~mcap.index.duplicated(keep="first")]

            return mcap


logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)

DIR = Path(__file__).parent
DAILY = DIR / "eod2_data/daily"
META_FILE = DIR / "eod2_data/meta.json"
MARKET_TRACKER_FILE = DIR / "eod2_data/market_tracker.csv"


meta = json.loads(META_FILE.read_bytes())
dates = Dates(meta["market_breadth_last_update"])

eod2_last_updated = datetime.fromisoformat(meta["lastUpdate"])

# Date guard - don't sync beyond EOD2 last update
if dates.lastUpdate >= eod2_last_updated:
    if eod2_last_updated.replace(tzinfo=None) < dates.today:
        print("Make sure EOD2 data is synced, before running.")
    print("All upto date")
    exit()

try:
    nse = NSE(DIR, server=True)
except (TimeoutError, ConnectionError, ConnectError) as e:
    logger.warning(f"Network error connecting to NSE - Please try again later. - {e!r}")
    exit()

priority = dict(EQ=1, BE=2, BZ=3)


# McClellan Oscillator settings
slow_ema_len = 39
fast_ema_len = 19

mb_df = pd.read_csv(MARKET_TRACKER_FILE, index_col="Date", parse_dates=["Date"])

prev_net_new_high, prev_ad_line, prev_fast_ema, prev_slow_ema = mb_df.loc[
    mb_df.index[-1],
    ["NET_NEW_HIGHS", "AD_LINE", "FAST_EMA", "SLOW_EMA"],
]

fast_ema = slow_ema = osc = None
modified = False

while True:
    if not dates.nextDate():
        nse.exit()

        if modified:
            mb_df.to_csv(MARKET_TRACKER_FILE)
        exit()

    if checkForHolidays(nse, dates):
        meta["market_breadth_last_update"] = dates.lastUpdate = dates.dt
        writeJson(META_FILE, meta)
        continue

    logger.info(f"Syncing data for {dates.dt:%d %b %Y}")

    PR_ZIP_FOLDER = DIR / f"nsePRZip/{dates.dt.year}"

    if not PR_ZIP_FOLDER.exists():
        PR_ZIP_FOLDER.mkdir(parents=True)

    mcap = None
    try:
        pr_zip = nse.pr_bhavcopy(dates.dt, folder=PR_ZIP_FOLDER)
        mcap = extract_pr_zip(pr_zip)
        logger.info("PR Bhavcopy downloaded and extracted.")
    except (RuntimeError, Exception) as e:
        if dates.dt.weekday() == 5:
            if dates.dt != dates.today:
                logger.info(f"{dates.dt:%a, %d %b %Y}: Market Closed\n{'-' * 52}")

                # On Error, dont exit on Saturdays, if trying to sync past dates
                continue

            # If NSE is closed and report unavailable, inform user
            logger.info(
                "Market is closed on Saturdays. If open, check availability on NSE"
            )

        # On daily sync exit on error
        nse.exit()
        logger.warning(e)
        exit()

    if mcap is None:
        continue

    new_high = new_low = 0
    count_200 = count_50 = 0
    universe_50 = universe_200 = 0
    adv = dec = total = 0

    dt = dates.dt.replace(tzinfo=None)
    logger.info("Calculating Indicator values")

    for symbol in mcap.index:
        df = load_symbol(symbol)

        if df is None or dt not in df.index:
            continue

        sma_50, sma_200, w_high, w_low, high, low, close, prev_close = df.loc[
            dt, ["MA50", "MA200", "52WH", "52WL", "High", "Low", "Close", "pclose"]
        ]

        if not pd.isna(sma_50):
            universe_50 += 1

            if close > sma_50:
                count_50 += 1

        # Stocks above 200 MA
        if not pd.isna(sma_200):
            universe_200 += 1

            if close > sma_200:
                count_200 += 1

        # New 52 week high
        if not pd.isna(w_high) and high > w_high:
            new_high += 1

        # New 52 week low
        if not pd.isna(w_low) and low < w_low:
            new_low += 1

        if pd.isna(prev_close):
            continue

        if close > prev_close:
            adv += 1

        if close < prev_close:
            dec += 1

        total += 1

    # Stocks above 50 and 200
    pct_50 = None if universe_50 == 0 else round(count_50 / universe_50 * 100, 2)
    pct_200 = None if universe_200 == 0 else round(count_200 / universe_200 * 100, 2)

    # New 52 week highs
    cumulative_net_new_highs = prev_net_new_high + (new_high - new_low)
    prev_net_new_high = cumulative_net_new_highs

    # advance decline line
    ad_line = prev_ad_line + ((adv - dec) / total if total else 0)
    prev_ad_line = ad_line

    # McClellan Ratio-Adjusted Oscillator
    net_adv_ratio = (adv - dec) / total * 100 if total else None

    if net_adv_ratio is not None:
        fast_ema = ema(net_adv_ratio, fast_ema_len, prev_fast_ema)
        prev_fast_ema = fast_ema

    if net_adv_ratio is not None:
        slow_ema = ema(net_adv_ratio, slow_ema_len, prev_slow_ema)
        prev_slow_ema = slow_ema

    if fast_ema is not None and slow_ema is not None:
        osc = fast_ema - slow_ema

    mb_df.loc[dt] = dict(
        Date=dt,
        PCT_50=pct_50,
        PCT_200=pct_200,
        NET_NEW_HIGHS=cumulative_net_new_highs,
        AD_LINE=ad_line,
        MCCLELLAN_OSC=osc,
        NET_ADV_RATIO=net_adv_ratio,
        FAST_EMA=fast_ema,
        SLOW_EMA=slow_ema,
    )

    meta["market_breadth_last_update"] = dates.lastUpdate = dates.dt
    writeJson(META_FILE, meta)

    logger.info(f"{dates.dt:%d %b %Y}: Done\n{'-' * 52}")
    modified = True
