import logging
import sys
from argparse import ArgumentParser

from nse import NSE

from defs import defs
from defs.utils import writeJson


logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)

if not defs.version_checker(NSE.__version__, major=1, minor=2, patch=4):
    logger.warning("Require NSE version 1.2.4. Run `pip install -U nse`")
    exit()


# Set the sys.excepthook to the custom exception handler
sys.excepthook = defs.log_unhandled_exception

parser = ArgumentParser(prog="init.py")

group = parser.add_mutually_exclusive_group()

group.add_argument(
    "-v", "--version", action="store_true", help="Print the current version."
)

group.add_argument(
    "-c", "--config", action="store_true", help="Print the current config."
)

args = parser.parse_args()

if args.version:
    exit(f"EOD2 init.py: version {defs.config.VERSION}")

if args.config:
    exit(str(defs.config))

try:
    nse = NSE(defs.DIR, server=True)
except (TimeoutError, ConnectionError) as e:
    logger.warning(f"Network error connecting to NSE - Please try again later. - {e!r}")
    exit()

if defs.check_special_sessions(nse):
    writeJson(defs.META_FILE, defs.meta)

if defs.config.AMIBROKER and not defs.isAmiBrokerFolderUpdated():
    defs.updateAmiBrokerRecords(nse)

if "DLV_PENDING_DATES" not in defs.meta:
    defs.meta["DLV_PENDING_DATES"] = []

if len(defs.meta["DLV_PENDING_DATES"]):
    pendingList = defs.meta["DLV_PENDING_DATES"].copy()

    logger.info("Updating pending delivery reports.")

    for dateStr in pendingList:
        if defs.updatePendingDeliveryData(nse, dateStr):
            writeJson(defs.META_FILE, defs.meta)

while True:
    if not defs.dates.nextDate():
        nse.exit()
        exit()

    if defs.checkForHolidays(nse):
        defs.meta["lastUpdate"] = defs.dates.lastUpdate = defs.dates.dt
        writeJson(defs.META_FILE, defs.meta)
        continue

    # Validate NSE actions file
    defs.validateNseActionsFile(nse)

    # Download all files and validate for errors
    logger.info("Downloading Files")

    report_status = None

    if defs.dates.dt.date() == defs.dates.today.date():
        report_status = defs.check_reports_update_status(nse)

        required_reports = {
            "CM-UDIFF-BHAVCOPY-CSV": "Equity Bhavcopy not yet updated.",
            "INDEX-SNAPSHOT": "Indices report not yet updated.",
            "CM-BHAVDATA-FULL": "Delivery Report Unavailable. Will retry in subsequent sync",
        }

        for key, msg in required_reports.items():
            if not report_status.get(key):
                logger.warning(msg)

                if key != "CM-BHAVDATA-FULL":
                    nse.exit()
                    exit()

    try:
        # NSE bhav copy
        BHAV_FILE = nse.equityBhavcopy(defs.dates.dt)

        # Index file
        INDEX_FILE = nse.indicesBhavcopy(defs.dates.dt)
    except (RuntimeError, Exception) as e:
        if defs.dates.dt.weekday() == 5:
            if defs.dates.dt != defs.dates.today:
                logger.info(f"{defs.dates.dt:%a, %d %b %Y}: Market Closed\n{'-' * 52}")

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

    if report_status is None or report_status["CM-BHAVDATA-FULL"]:
        try:
            # NSE delivery
            DELIVERY_FILE = nse.deliveryBhavcopy(defs.dates.dt)
        except (RuntimeError, Exception):
            defs.meta["DLV_PENDING_DATES"].append(defs.dates.dt.isoformat())
            DELIVERY_FILE = None
            logger.warning("Delivery Report Unavailable. Will retry in subsequent sync")

    else:
        DELIVERY_FILE = None
        defs.meta["DLV_PENDING_DATES"].append(defs.dates.dt.isoformat())

    try:
        defs.updateNseEOD(BHAV_FILE, DELIVERY_FILE)

        # INDEX sync
        defs.updateIndexEOD(INDEX_FILE)
    except Exception as e:
        # rollback
        logger.exception("Error during data sync.", exc_info=e)
        defs.rollback(defs.DAILY_FOLDER)
        defs.cleanup((BHAV_FILE, DELIVERY_FILE, INDEX_FILE))

        defs.meta["lastUpdate"] = defs.dates.lastUpdate
        writeJson(defs.META_FILE, defs.meta)
        nse.exit()
        exit()

    # No errors continue

    # Adjust Splits and bonus
    try:
        defs.adjustNseStocks()
    except Exception as e:
        logger.exception(
            "Error while making adjustments.\nAll adjustments have been discarded.",
            exc_info=e,
        )

        defs.rollback(defs.DAILY_FOLDER)
        defs.cleanup((BHAV_FILE, DELIVERY_FILE, INDEX_FILE))

        defs.meta["lastUpdate"] = defs.dates.lastUpdate
        writeJson(defs.META_FILE, defs.meta)
        nse.exit()
        exit()

    if defs.hook and hasattr(defs.hook, "on_complete"):
        defs.hook.on_complete()

    defs.cleanup((BHAV_FILE, DELIVERY_FILE, INDEX_FILE))

    if defs.dates.today == defs.dates.dt:
        defs.cleanOutDated()

    defs.meta["lastUpdate"] = defs.dates.lastUpdate = defs.dates.dt
    writeJson(defs.META_FILE, defs.meta)

    logger.info(f"{defs.dates.dt:%d %b %Y}: Done\n{'-' * 52}")
