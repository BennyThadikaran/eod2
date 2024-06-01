import sys
from defs.utils import writeJson
from defs import defs
from argparse import ArgumentParser
from nse import NSE


logger = defs.configure_logger(__name__)

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

# download the latest special_sessions.txt from eod2_data repo
special_sessions = defs.downloadSpecialSessions()

nse = NSE(defs.DIR)

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

    if defs.checkForHolidays(nse, special_sessions):
        continue

    # Validate NSE actions file
    defs.validateNseActionsFile(nse)

    # Download all files and validate for errors
    logger.info("Downloading Files")

    try:
        # NSE bhav copy
        BHAV_FILE = nse.equityBhavcopy(defs.dates.dt)

        # Index file
        INDEX_FILE = nse.indicesBhavcopy(defs.dates.dt)
    except (RuntimeError, Exception) as e:
        if defs.dates.dt.weekday() == 5:
            if defs.dates.dt != defs.dates.today:
                logger.info(
                    f'{defs.dates.dt:%a, %d %b %Y}: Market Closed\n{"-" * 52}'
                )

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

    try:
        # NSE delivery
        DELIVERY_FILE = nse.deliveryBhavcopy(defs.dates.dt)
    except (RuntimeError, Exception):
        defs.meta["DLV_PENDING_DATES"].append(defs.dates.dt.isoformat())
        DELIVERY_FILE = None
        logger.warning(
            "Delivery Report Unavailable. Will retry in subsequent sync"
        )

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
    defs.cleanOutDated()

    defs.meta["lastUpdate"] = defs.dates.lastUpdate = defs.dates.dt
    writeJson(defs.META_FILE, defs.meta)

    logger.info(f'{defs.dates.dt:%d %b %Y}: Done\n{"-" * 52}')
