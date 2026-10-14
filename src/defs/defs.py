from __future__ import annotations

import itertools
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Dict, List, NamedTuple, Optional, Tuple, Type, TypedDict, Union, cast

import dateutil
import numpy as np
import pandas as pd
import tzlocal
from nse import NSE, NSEFileUnavailableError

from defs.config import config

from .dates import Dates
from .symbol_tracker import SymbolTracker

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

try:
    import httpx
except ModuleNotFoundError:
    exit("Please run `pip install 'nse~=5.0.0'`")


class PreviousCommit(TypedDict):
    file: Path
    df: pd.DataFrame


ReportStatus = TypedDict(
    "ReportStatus",
    {
        "CM-UDIFF-BHAVCOPY-CSV": bool,
        "CM-BHAVDATA-FULL": bool,
        "INDEX-SNAPSHOT": bool,
    },
)


class BhavCopyRow(NamedTuple):
    Index: str
    TckrSymb: str
    SctySrs: str
    OpnPric: float
    HghPric: float
    LwPric: float
    ClsPric: float
    TtlTradgVol: float


def configure_logger():
    """Return a logger instance by name

    Creates a file handler to log messages with level WARNING and above

    Creates a stream handler to log messages with level INFO and above
    """
    stream_handler = logging.StreamHandler()
    file_handler = logging.FileHandler(DIR / "error.log")

    file_handler.setLevel(logging.WARNING)

    try:
        file_handler.setFormatter(
            logging.Formatter(
                "%(levelname)s: %(asctime)s - %(name)s - %(message)s - EOD2 v%(eod_v)s - NSE v%(nse_v)s - %(last_update)s",
                defaults=meta_info,
            )
        )
    except TypeError:
        # Python < 3.10 does not support the `defaults` parameter.
        file_handler.setFormatter(
            logging.Formatter("%(levelname)s: %(asctime)s - %(name)s - %(message)s")
        )

    logging.basicConfig(
        format="%(levelname)s: %(asctime)s - %(name)s - %(message)s",
        datefmt="%d-%m-%Y %H:%M",
        level=logging.INFO,
        handlers=(stream_handler, file_handler),
    )


def is_version_compatible(version: str, major: int, minor: int, patch: int) -> bool:
    """
    Check whether a version satisfies the minimum required semantic version.

    A version is considered compatible if:
    - Its major version matches `major`.
    - Its `(minor, patch)` version is greater than or equal to
      `(minor, patch)` according to semantic version ordering.

    Pre-release metadata is ignored (e.g. "1.2.3-alpha" is treated as
    "1.2.3").

    Args:
        version: A semantic version string (e.g. "1.2.3" or "1.2.3-beta").
        major: Required major version.
        minor: Required minimum minor version.
        patch: Required minimum patch version within the required minor
            version.

    Returns:
        True if the version is compatible, otherwise False.
    """
    v_major, v_minor, v_patch = map(int, version.split("-")[0].split("."))

    return v_major == major and (v_minor, v_patch) >= (minor, patch)


def load_module(module_str: str) -> Union[ModuleType, Type]:
    """
    Load a module specified by the given string.

    Arguments
    module_str (str): Module filepath, optionally adding the class name
        with format <filePath>:<className>

    Raises:
    ModuleNotFoundError: If module is not found
    AttributeError: If class name is not found in module.

    Returns: ModuleType
    """
    import importlib.util

    class_name = None
    module_path = module_str

    if "|" in module_str:
        module_path, class_name = module_str.split("|")

    module_path = Path(module_path).expanduser().resolve()

    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)

    if not spec or not spec.loader:
        raise ModuleNotFoundError(f"Could not load module {module_path.stem}")

    module = importlib.util.module_from_spec(spec)

    sys.modules[module_path.stem] = module

    spec.loader.exec_module(module)

    return getattr(module, class_name) if class_name else module


def log_unhandled_exception(exc_type, exc_value, exc_traceback):
    # Log the unhandled exception
    logger.critical(
        "Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback)
    )


def check_reports_update_status(nse) -> ReportStatus:
    """Check if all daily reports has been updated for NSE."""
    result: ReportStatus = {
        "CM-UDIFF-BHAVCOPY-CSV": False,
        "CM-BHAVDATA-FULL": False,
        "INDEX-SNAPSHOT": False,
    }

    cm_data = nse.fetch_daily_reports_file_metadata(segment="CM")
    index_data = nse.fetch_daily_reports_file_metadata(segment="INDEX")

    if not (cm_data["CurrentDay"] or index_data["CurrentDay"]):
        return result

    cm_report_date = datetime.strptime(cm_data["currentDate"], "%d-%b-%Y")

    if cm_report_date != dates.today.replace(tzinfo=None):
        logger.info("Market is closed today")
        exit(0)

    for dct in itertools.chain(cm_data["CurrentDay"], index_data["CurrentDay"]):
        key = dct["fileKey"]

        if key in result:
            result[key] = True

    return result


def get_muhurat_holiday_info(holidays: Dict[str, List[Dict]]) -> Dict:
    for lst in holidays.values():
        for dct in lst:
            if "laxmi pujan" in dct["description"].lower():
                return dct

    return {}


def get_holiday_list(nse: NSE):
    """Makes a request for NSE holiday list for the year.
    Saves and returns the holiday Object
    """
    data = nse.holidays(type=nse.HOLIDAY_TRADING)

    # CM pertains to capital market or equity holidays
    data["CM"].append(get_muhurat_holiday_info(data))

    data = {k["tradingDate"]: k["description"] for k in data["CM"]}
    logger.info("NSE Holiday list updated")

    return data


def check_for_holidays(nse: NSE, dates_cls: Dates):
    """Returns True if current date is a holiday.
    Exits the script if today is a holiday
    """
    global has_latest_holidays

    # the current date for which data is being synced
    current_date = dates_cls.dt.strftime("%d-%b-%Y")

    if dates_cls.dt.replace(tzinfo=None) in tuple(
        datetime.fromisoformat(x) for x in meta.get("special_sessions", [])
    ):
        return False

    # no holiday list or year has changed or today is a holiday
    if (
        "holidays" not in meta
        or meta["year"] != dates_cls.dt.year
        or (current_date in meta["holidays"] and not has_latest_holidays)
    ):
        if dates_cls.dt.year == dates_cls.today.year:
            meta["holidays"] = get_holiday_list(nse)
            meta["year"] = dates_cls.dt.year
            has_latest_holidays = True

    is_muhurat = "Laxmi Pujan" in meta["holidays"].get(current_date, [])

    if is_muhurat:
        return False

    if dates_cls.dt.weekday() == 6:
        return True

    holiday_str = meta["holidays"].get(current_date)

    if holiday_str:
        logger.info(f"{current_date} Market Holiday: {holiday_str}")
        return True

    return False


def validate_nse_actions_file(nse: NSE):
    """Check if the NSE Corporate actions() file exists.
    If exists, check if the file is older than 7 days.
    Else request actions for the next 8 days from current date.
    The actionsFile pertains to Bonus, Splits, dividends etc.
    """
    for action in ("equity", "sme", "mf"):
        segment = "equities" if action == "equity" else action

        if f"{action}Actions" not in meta:
            logger.warning(f"Downloading NSE {action.upper()} actions")

            meta[f"{action}Actions"] = nse.actions(
                segment=segment,
                from_date=dates.dt,
                to_date=dates.dt + timedelta(8),
            )

            meta[f"{action}ActionsExpiry"] = (dates.dt + timedelta(7)).isoformat()
        else:
            expiry_date = datetime.fromisoformat(
                meta[f"{action}ActionsExpiry"]
            ).astimezone(tz_IN)

            new_expiry = (expiry_date + timedelta(7)).isoformat()

            # Update every 7 days from last download
            if dates.dt < expiry_date:
                continue

            logger.warning(f"Updating NSE {action.upper()} actions")

            meta[f"{action}Actions"] = nse.actions(
                segment=segment,
                from_date=expiry_date,
                to_date=expiry_date + timedelta(8),
            )

            meta[f"{action}ActionsExpiry"] = new_expiry


def update_pending_delivery_data(nse: NSE, date: str):
    """Return True on successful file update or max failed attempts
    else False on failed attempt
    """
    dt = datetime.fromisoformat(date)
    days_since_failure = (datetime.now(tz_IN) - dt).days
    error_context = None

    dt = dt.replace(tzinfo=None)

    try:
        FILE = nse.delivery_bhavcopy(dt)
    except (NSEFileUnavailableError, httpx.HTTPError):
        if days_since_failure == 5:
            logger.warning(
                f"Max attempts reached: Aborting Future attempts for report dated {dt}"
            )
            return True

        logger.info(f"{dt:%d %b}: Delivery report not yet updated.")
        return False

    try:
        df = pd.read_csv(FILE, index_col="SYMBOL")

        # save the csv file to the below folder.
        DLV_FOLDER = DIR / "nseDelivery" / str(dt.year)

        if not DLV_FOLDER.is_dir():
            DLV_FOLDER.mkdir(parents=True)

        df.to_csv(DLV_FOLDER / FILE.name)

        # filter the pd.DataFrame for stocks series EQ, BE and BZ
        # https://www.nseindia.com/market-data/legend-of-series
        df = df[df.SERIES.isin(VALID_SERIES)]

        df.columns = df.columns.str.strip()
        df.SERIES = df.SERIES.str.strip()

        if not pd.api.types.is_numeric_dtype(df.DELIV_QTY):
            df["DELIV_QTY"] = pd.to_numeric(df.DELIV_QTY.str.strip().replace("-", "0"))

        for sym in df.index:
            error_context = f"{sym} - {dt}"
            DAILY_FILE = DAILY_FOLDER / f"{sym.lower()}.csv"

            if not DAILY_FILE.exists():
                continue

            daily_df = pd.read_csv(DAILY_FILE, index_col="Date", parse_dates=["Date"])

            if dt not in daily_df.index:
                continue

            vol = daily_df.at[dt, "Volume"]
            series = df.at[sym, "SERIES"]

            trade_count, dq = df.loc[sym, ["NO_OF_TRADES", "DELIV_QTY"]]

            # BE and BZ series stocks are all delivery trades,
            # so we use the volume
            dq = vol if series in EQ_T2T_SERIES else dq
            avg_trade_count = round(vol / trade_count, 2)

            daily_df.at[dt, "TOTAL_TRADES"] = trade_count
            daily_df.at[dt, "QTY_PER_TRADE"] = avg_trade_count
            daily_df.at[dt, "DLV_QTY"] = dq
            daily_df.to_csv(DAILY_FILE)

        if hook and hasattr(hook, "updatePendingDeliveryData"):
            hook.updatePendingDeliveryData(df, dt)
    except Exception as e:
        logger.exception(
            f"Error updating delivery report dated {dt:%d %b %Y} - {error_context}",
            exc_info=e,
        )
        FILE.unlink()
        return False

    meta["DLV_PENDING_DATES"].remove(date)
    FILE.unlink()
    logger.info(f"Updating delivery report dated {dt:%d %b %Y}: ✓ Done")
    return True


def is_amibroker_folder_updated():
    """Returns true if the folder has files"""
    return any(AMIBROKER_FOLDER.iterdir())


def update_amibroker_records(nse: NSE):
    """Downloads and updates the amibroker files upto the number of days
    set in Config.AMI_UPDATE_DAYS
    """
    last_update = datetime.fromisoformat(meta["last_update"]) + timedelta(1)
    dt = last_update - timedelta(config.AMI_UPDATE_DAYS)
    total_days = config.AMI_UPDATE_DAYS

    logger.info(
        f"Fetching bhavcopy for last {total_days} days, to convert to AmiBroker format."
    )

    logger.info("This is a one time process. It will take a few minutes.")

    while dt < last_update:
        dt += timedelta(1)

        if dt.weekday() > 4:
            continue

        bhav_folder = DIR / "nseBhav" / str(dt.year)

        if not bhav_folder.is_dir():
            bhav_folder.mkdir(parents=True)

        if dt < udiff_start_date:
            dt_str = dt.strftime("%d%b%Y").upper()
            bhav_file = bhav_folder / f"cm{dt_str}bhav.csv"
            udiff_format = False
        else:
            bhav_file = bhav_folder / f"BhavCopy_NSE_CM_0_0_0_{dt:%Y%m%d}_F_0000.csv"
            udiff_format = True

        if not bhav_file.exists():
            try:
                bhav_file = nse.equity_bhavcopy(dt)
                bhav_file = bhav_file.rename(bhav_folder / bhav_file.name)
            except (NSEFileUnavailableError, httpx.HTTPError):
                continue
            except Exception as e:
                logger.warning(f"{e} - Please try again.")
                exit(1)

        to_amibroker_format(bhav_file, udiff_format=udiff_format)

        days_complete = total_days - (last_update - dt).days
        pct_complete = int(days_complete / total_days * 100)
        print(f"{pct_complete} %", end="\r", flush=True)

    logger.info("Amibroker file updated")


def to_amibroker_format(file: Path, udiff_format: bool = True):
    """Converts and saves bhavcopy into amibroker format"""
    if udiff_format:
        date_column = "TradDt"
        series_column = "SctySrs"
        columns_to_read = [
            "TckrSymb",
            "TradDt",
            "OpnPric",
            "HghPric",
            "LwPric",
            "ClsPric",
            "TtlTradgVol",
            "ISIN",
        ]
    else:
        date_column = "TIMESTAMP"
        series_column = "SERIES"
        columns_to_read = [
            "SYMBOL",
            "TIMESTAMP",
            "OPEN",
            "HIGH",
            "LOW",
            "CLOSE",
            "TOTTRDQTY",
            "ISIN",
        ]

    df = pd.read_csv(file, parse_dates=[date_column])

    df = df[df[series_column].isin(VALID_SERIES)]

    df = df.loc[:, columns_to_read]

    df.columns = AMIBROKER_COLUMNS

    df.to_csv(AMIBROKER_FOLDER / file.name, index=False)


def update_nse_eod(bhav_file: Path, delivery_file: Optional[Path]):
    """Update all stocks with latest price data from bhav copy"""
    logger.info("Starting Data Sync")

    df = pd.read_csv(bhav_file, index_col="ISIN")

    BHAV_FOLDER = DIR / "nseBhav" / str(dates.dt.year)

    # Create it if not exists
    if not BHAV_FOLDER.is_dir():
        BHAV_FOLDER.mkdir(parents=True)

    df.to_csv(BHAV_FOLDER / bhav_file.name)

    # filter the pd.DataFrame for stocks series EQ, BE and BZ
    # https://www.nseindia.com/market-data/legend-of-series
    df = df[df["SctySrs"].isin(VALID_SERIES)]

    if config.AMIBROKER:
        logger.info("Converting to AmiBroker format")
        to_amibroker_format(bhav_file)

    if delivery_file:
        dlv_df = pd.read_csv(delivery_file, index_col="SYMBOL")

        # save the csv file to the below folder.
        DLV_FOLDER = DIR / "nseDelivery" / str(dates.dt.year)

        if not DLV_FOLDER.is_dir():
            DLV_FOLDER.mkdir(parents=True)

        dlv_df.to_csv(DLV_FOLDER / delivery_file.name)

        dlv_df.columns = dlv_df.columns.str.strip()
        dlv_df.SERIES = dlv_df.SERIES.str.strip()

        # filter the pd.DataFrame for stocks series EQ, BE and BZ
        # https://www.nseindia.com/market-data/legend-of-series
        dlv_df = dlv_df[dlv_df.SERIES.isin(VALID_SERIES)]

        if not pd.api.types.is_numeric_dtype(dlv_df.DELIV_QTY):
            dlv_df["DELIV_QTY"] = pd.to_numeric(
                dlv_df.DELIV_QTY.str.strip().replace("-", "0")
            )
    else:
        dlv_df = None

    # iterate over each row as a tuple
    for t in df.itertuples():
        t = cast(BhavCopyRow, t)

        # ignore rights issue
        if "-RE" in t.TckrSymb:
            continue

        if dlv_df is not None:
            if t.TckrSymb in dlv_df.index:
                trade_count, dq = dlv_df.loc[t.TckrSymb, ["NO_OF_TRADES", "DELIV_QTY"]]

                # BE and BZ series stocks are all delivery trades,
                # so we use the volume
                dq = t.TtlTradgVol if t.SctySrs in EQ_T2T_SERIES else dq
            else:
                trade_count = dq = np.nan
        else:
            trade_count = dq = ""

        suffix = "_sme" if t.SctySrs in SME_SERIES else ""
        SYM_FILE = DAILY_FOLDER / f"{t.TckrSymb.lower()}{suffix}.csv"

        if pd.isna(t.Index):
            raise ValueError(
                f"{t.TckrSymb} missing ISIN number. Please retry after few hours."
            )

        # Returns None for untracked new symbols, or symbol name
        tracked_symbol = tracker.get_last_symbol(t.Index, by="isin")

        # Update file names if name not matching existing symbol name
        if tracked_symbol is not None and t.TckrSymb != tracked_symbol:
            old = tracked_symbol.lower()
            new = t.TckrSymb.lower()

            SYM_FILE = DAILY_FOLDER / f"{new}{suffix}.csv"
            OLD_FILE = DAILY_FOLDER / f"{old}{suffix}.csv"

            try:
                OLD_FILE.rename(SYM_FILE)
            except FileNotFoundError:
                logger.warning(f"Renaming daily/{old}.csv to {new}.csv. No such file.")

            logger.warning(f"Name Changed: {old} to {new}")

        tracker.update(t.TckrSymb, t.Index, dates.dt.date())

        update_nse_symbol(
            SYM_FILE,
            t.SctySrs,
            t.OpnPric,
            t.HghPric,
            t.LwPric,
            t.ClsPric,
            t.TtlTradgVol,
            trade_count,
            dq,
        )

    logger.info("EOD sync complete")


def update_nse_symbol(
    sym_file: Path, series, open, high, low, close, volume, trade_count, dq
):
    """Appends EOD stock data to end of file"""
    text = b""

    if not sym_file.exists():
        sme_file = DAILY_FOLDER / f"{sym_file.stem}_sme.csv"

        if "_sme" not in sym_file.name and sme_file.exists():
            logger.info(f"{sym_file.stem.upper()} switched from SME to EQ")
            sme_file.rename(sym_file)
        else:
            text += header_text

    avg_trade_count = "" if trade_count == "" else round(volume / trade_count, 2)

    text += bytes(
        f"{dates.pandas_dt},{open},{high},{low},{close},{volume},{series},{trade_count},{avg_trade_count},{dq}\n",
        encoding="utf-8",
    )

    with sym_file.open("ab") as f:
        f.write(text)

    if hook and hasattr(hook, "updateNseSymbol"):
        hook.updateNseSymbol(
            dates.dt,
            sym_file.stem,
            series,
            open,
            high,
            low,
            close,
            volume,
            trade_count,
            avg_trade_count,
            dq,
        )


def check_special_sessions(nse: NSE) -> bool:
    last_update_str = meta.get("special_sessions_last_update")

    if last_update_str is None:
        last_update = (dates.dt - timedelta(5)).replace(tzinfo=None)
        meta["special_sessions"] = []
    else:
        last_update = datetime.fromisoformat(last_update_str)

    circulars = nse.circulars(
        dept_code="CMTR",
        from_date=last_update,
        to_date=dates.today.replace(tzinfo=None),
    )
    updated = False

    for circular in circulars["data"]:
        subject = circular["sub"].lower()

        if "trading holiday" in subject and "on account of" in subject:
            # If holidays not in meta, it will be auto updated later
            # Dont create a holiday object here
            if "holidays" in meta:
                try:
                    dt = dateutil.parser.parse(subject, fuzzy=True)
                except dateutil.parser.ParserError:
                    logger.warning(
                        f"Unable to parse date from circular dated {circular['cirDisplayDate']}: {circular['sub']}"
                    )
                    continue

                dt_key = dt.strftime("%d-%b-%Y")

                if dt_key not in meta["holidays"]:
                    meta["holidays"][dt_key] = subject
                    logger.warning(f"Circular: {subject}")
            continue

        if "live trading session" not in subject:
            continue

        try:
            dt = dateutil.parser.parse(subject, fuzzy=True)
        except dateutil.parser.ParserError:
            logger.warning(
                f"Unable to parse date from circular dated {circular['cirDisplayDate']}: {circular['sub']}"
            )
            continue

        iso_date = dt.isoformat()

        if iso_date not in meta["special_sessions"]:
            meta["special_sessions"].append(iso_date)

        # Set to warning level for test period to log to error.log file
        logger.warning(f"Circular: {subject}")
        updated = True

    meta["special_sessions_last_update"] = dates.today.date().isoformat()
    return updated


def get_split(sym, string):
    """Run a regex search for splits related corporate action and
    return the adjustment factor
    """
    match = split_regex.search(string)

    if match is None:
        logger.warning(f"{sym}: Not Matched. {string} - {dates.dt}")
        return match

    return float(match.group(1)) / float(match.group(2))


def get_bonus(sym, string):
    """Run a regex search for bonus related corporate action and
    return the adjustment factor
    """
    match = bonus_regex.search(string)

    if match is None:
        logger.warning(f"{sym}: Not Matched. {string} - {dates.dt}")
        return match

    return 1 + int(match.group(1)) / int(match.group(2))


def make_adjustment(
    symbol: str,
    adjustment_factor: float,
    prev_commit: Optional[PreviousCommit] = None,
) -> Optional[Tuple[pd.DataFrame, Path]]:
    """Makes adjustment to stock data prior to ex date,
    returning a tuple of pandas pd.DataFrame and filename
    """
    if prev_commit:
        file: Path = prev_commit["file"]
        df: pd.DataFrame = prev_commit["df"]
    else:
        file = DAILY_FOLDER / f"{symbol.lower()}.csv"

        if not file.is_file():
            logger.warning(f"{symbol}: File not found - {dates.dt}")
            return

        df = pd.read_csv(file, index_col="Date", parse_dates=["Date"])

    # Remove timezone info as DataFrame index is not timezone aware
    dt = dates.dt.replace(tzinfo=None)

    if dt in df.index:
        idx = df.index.get_loc(dt)

        if isinstance(idx, slice):
            logger.warning(
                f"Duplicate dates detected on {symbol} making adjustment - {dates.dt}"
            )
            raise RuntimeError()

        last = df.iloc[idx:]

        df = df.iloc[:idx].copy()
    else:
        last = df.loc[dt:]
        df = df.loc[:dt].copy()
        idx = df.index.get_loc(df.index[-1])

    for col in ("Open", "High", "Low", "Close"):
        # nearest 0.05 = round(nu / 0.05) * 0.05
        df.loc[:, col] = ((df[col] / adjustment_factor / 0.05).round() * 0.05).round(2)

    df = pd.concat([df, last])

    return (df, file)


def update_index(sym, open, high, low, close, volume, pe):
    """Appends Index EOD data to end of file"""
    if "/" in sym or ":" in sym:
        sym = sym.replace("/", "-").replace(":", "-")

    file = DAILY_FOLDER / f"{sym.lower()}.csv"

    text = b""

    if not file.is_file():
        text += index_header_text

    text += bytes(
        f"{dates.pandas_dt},{open},{high},{low},{close},{volume},{pe},,,,\n",
        encoding="utf-8",
    )

    with file.open("ab") as f:
        f.write(text)

    if hook and hasattr(hook, "updateIndice"):
        hook.updateIndice(dates.dt, sym, open, high, low, close, volume)


def update_index_eod(file: Path):
    """Iterates over each symbol in NSE indices reports and
    update EOD data to respective csv file
    """
    folder = DIR / "nseIndices" / str(dates.dt.year)

    if not folder.is_dir():
        folder.mkdir(parents=True)

    df = pd.read_csv(file, index_col="Index Name")

    df.to_csv(folder / file.name)

    cols = [
        "Open Index Value",
        "High Index Value",
        "Low Index Value",
        "Closing Index Value",
        "Volume",
        "P/E",
    ]

    # replace all '-' in columns with empty string
    for col in cols:
        df.loc[:, col] = pd.to_numeric(df[col], errors="coerce")

    for sym in df.index:
        open, high, low, close, volume, pe = df.loc[sym, cols]

        update_index(sym, open, high, low, close, volume, pe)

    pe = float(df.at["Nifty 50", "P/E"])

    if pe >= 25 or pe <= 20:
        logger.info(f"\033[1;32m### Alert: Nifty PE at {pe}! ###\033[0;94m")
    else:
        logger.info(f"### Nifty PE at {pe} ###")

    logger.info("Index sync complete.")


def adjust_nse_stocks():
    """Iterates over NSE corporate actions searching for splits or bonus
    on current date and adjust the stock accordingly
    """
    logger.info("Making adjustments for splits and bonus")

    dt_str = dates.dt.strftime("%d-%b-%Y")

    for actions in ("equityActions", "smeActions", "mfActions"):
        # Store all pd.DataFrames with associated files names to be saved to file
        # if no error occurs
        df_commits: Dict[str, PreviousCommit] = {}
        post_commits: List[Tuple[str, float]] = []
        error_context = None

        try:
            for act in meta[actions]:
                sym = act["symbol"]
                purpose = act["subject"].lower()
                ex = act["exDate"]
                series = act["series"]

                if series not in VALID_SERIES:
                    continue

                if series in SME_SERIES:
                    sym += "_sme"

                if (
                    "split" in purpose
                    or "splt" in purpose
                    or "consolidation" in purpose
                ) and ex == dt_str:
                    if "consolidation" in purpose:
                        error_context = f"{sym} - consolidation - {dt_str}"
                        i = purpose.index("consolidation")
                    else:
                        error_context = f"{sym} - Split - {dt_str}"
                        i = purpose.index("spl")

                    adjustment_factor = get_split(sym, purpose[i:])

                    if adjustment_factor is None:
                        logger.warning(
                            f"Possible adjustment failure: SPLIT - {sym} - {purpose} - exDate: {dt_str}"
                        )
                        continue

                    commit = make_adjustment(
                        sym, adjustment_factor, df_commits.get(sym)
                    )

                    if commit:
                        df, file = commit

                        if sym in df_commits:
                            df_commits[sym]["df"] = df
                        else:
                            df_commits[sym] = {"file": file, "df": df}

                        post_commits.append((sym, adjustment_factor))
                        logger.info(f"{sym}: {purpose}")

                if "bonus" in purpose and ex == dt_str:
                    if (
                        "deb" in purpose
                        or "pref" in purpose
                        or "ncrps" in purpose
                        or "dvr" in purpose
                    ):
                        continue

                    error_context = f"{sym} - Bonus - {dt_str}"
                    adjustment_factor = get_bonus(sym, purpose)

                    if adjustment_factor is None:
                        logger.warning(
                            f"Possible adjustment failure: BONUS - {sym} - {purpose} - exDate: {dt_str}"
                        )
                        continue

                    commit = make_adjustment(
                        sym, adjustment_factor, df_commits.get(sym)
                    )

                    if commit:
                        df, file = commit

                        if sym in df_commits:
                            df_commits[sym]["df"] = df
                        else:
                            df_commits[sym] = {"file": file, "df": df}

                        post_commits.append((sym, adjustment_factor))
                        logger.warning(f"{sym}: {purpose}")

        except Exception as e:
            logging.critical(f"Adjustment Error - Context {error_context}")
            # discard all pd.DataFrames and raise error,
            # so changes can be rolled back
            df_commits.clear()
            raise e

        # commit changes
        for sym, commit in df_commits.items():
            file: Path = commit["file"]
            df: pd.DataFrame = commit["df"]

            dt = dates.dt.replace(tzinfo=None)

            if dt in df.index:
                idx = df.index.get_loc(dt)

                assert isinstance(idx, int)

                close = df.at[df.index[idx], "Close"]
                prev_close = df.at[df.index[idx - 1], "Close"]

                diff = close / prev_close

                if diff > 1.5 or diff < 0.67:
                    context = f"Current Close {close}, Previous Close {prev_close}"

                    logger.warning(
                        f"WARN: Possible adjustment failure in {sym}: {context} - {dates.dt}"
                    )
            else:
                logger.warning(
                    f"Unable to verify adjustment on {sym} - Please confirm manually. - {dates.dt}"
                )

            df.to_csv(file)

        df_commits.clear()

        if hook and hasattr(hook, "makeAdjustment") and post_commits:
            hook.makeAdjustment(dates.dt, post_commits)

        post_commits.clear()


def get_last_date(file):
    """Get the last updated date for a stock csv file"""
    # source: https://stackoverflow.com/a/68413780
    with open(file, "rb") as f:
        try:
            # seek 2 bytes to the last line ending ( \n )
            f.seek(-2, os.SEEK_END)

            # seek backwards 2 bytes till the next line ending
            while f.read(1) != b"\n":
                f.seek(-2, os.SEEK_CUR)

        except OSError:
            # catch OSError in case of a one line file
            f.seek(0)

        # we have the last line
        last_line = f.readline()

    # extract date being the first item separated by comma
    return last_line[: last_line.find(b",")].decode()


def delete_last_line_by_date(file: Path, date_str: str) -> bool:
    """
    Truncate the last line if line starts with date_str
    """
    if not date_str:
        raise ValueError("date_str must not be empty")

    # Get the file size
    file_size = os.path.getsize(file)

    if file_size == 0:
        return False

    date_bytes = date_str.encode("utf-8")

    with file.open("r+b") as f:
        # Start searching from the end of the file
        cur_pos = file_size - 2

        # Search backward till the newline character is found
        while cur_pos > 0:
            f.seek(cur_pos)

            if f.read(1) == b"\n":
                break

            cur_pos -= 1

        # Note: cur_pos + 1 preserves the trailing newline.
        # Fix contributed by @ArunTS96 in #353.
        last_line_start = cur_pos + 1 if cur_pos > 0 else 0

        if last_line_start == 0:
            header_prefix = b"Date"
            f.seek(0)

            if f.read(len(header_prefix)).startswith(header_prefix):
                return False

            raise ValueError(f"{file.name}: Missing column headers")

        f.seek(last_line_start)

        if not f.read().startswith(date_bytes):
            return False

        f.truncate(last_line_start)
        return True


def rollback(folder: Path):
    """Iterate over all files in folder and delete any lines
    pertaining to the current date
    """
    dt = dates.pandas_dt
    logger.info(f"Rolling back changes from {dt}: {folder}")

    for file in folder.iterdir():
        delete_last_line_by_date(file, dt)

    logger.info("Rollback successful")

    if hook and hasattr(hook, "on_error"):
        hook.on_error()


def cleanup(files_list):
    """Remove files downloaded from nse"""
    for file in files_list:
        if file is None:
            continue
        file.unlink(missing_ok=True)


def clean_outdated():
    """Delete CSV files not updated in the last 365 days"""
    logger.info("Cleaning up files")

    deadline = dates.today - timedelta(365)
    count = 0
    removed = []

    for file in DAILY_FOLDER.iterdir():
        last_updated = datetime.strptime(get_last_date(file), "%Y-%m-%d")

        if last_updated < deadline:
            removed.append(file.stem)
            file.unlink()
            count += 1

    logger.info(f"{count} files deleted")

    if hook and hasattr(hook, "cleanOutDated") and removed:
        hook.cleanOutDated(removed)


# Avoid side effects in case this file is directly executed
# instead of being imported
if __name__ != "__main__":
    DIR = Path(__file__).parents[1]
    DAILY_FOLDER = DIR / "eod2_data" / "daily"
    AMIBROKER_FOLDER = DIR / "eod2_data" / "amibroker"
    META_FILE = DIR / "eod2_data" / "meta.json"
    ISIN_SYMBOL_MAP_FILE = DIR / "eod2_data/isin_symbol_map.json"

    has_latest_holidays = False

    split_regex = re.compile(r"(\d+\.?\d*)[\/\- a-z\.]+(\d+\.?\d*)")

    bonus_regex = re.compile(r"(\d+) ?: ?(\d+)")

    date_regex = re.compile(r"\b[A-Za-z]+, [A-Za-z]+ \d{2}, \d{4}\b")

    header_text = (
        b"Date,Open,High,Low,Close,Volume,Series,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n"
    )

    index_header_text = b"Date,Open,High,Low,Close,Volume,P/E,Series,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n"

    EQ_T2T_SERIES = ("BE", "BZ")
    SME_SERIES = ("SM", "ST", "SZ")
    VALID_SERIES = ("EQ",) + EQ_T2T_SERIES + SME_SERIES

    AMIBROKER_COLUMNS = [
        "SYMBOL",
        "DATE",
        "OPEN",
        "HIGH",
        "LOW",
        "CLOSE",
        "VOLUME",
        "ISIN",
    ]

    logger = logging.getLogger("EOD")

    tz_local = tzlocal.get_localzone()
    tz_IN = ZoneInfo("Asia/Kolkata")

    udiff_start_date = datetime(2024, 7, 7, tzinfo=tz_IN)

    if "win" in sys.platform:
        # enable color support in Windows
        os.system("color")

    meta: Dict = json.loads(META_FILE.read_bytes())

    meta_info = dict(
        eod_v=config.VERSION,
        nse_v=NSE.__version__,
        last_update=meta.get("lastUpdate"),
    )

    configure_logger()

    if config.AMIBROKER and not AMIBROKER_FOLDER.exists():
        AMIBROKER_FOLDER.mkdir()

    hook = None  # INIT_HOOK

    if config.INIT_HOOK:
        import warnings

        warnings.warn(
            "INIT_HOOK is deprecated and will be removed in a future release.",
            FutureWarning,
            stacklevel=2,
        )
        hook = load_module(config.INIT_HOOK)

        if isinstance(hook, type):
            # hook is a Class
            hook = hook()

    # initiate the dates class from utils.py
    dates = Dates(meta["lastUpdate"])

    tracker = SymbolTracker(data_file=ISIN_SYMBOL_MAP_FILE)
